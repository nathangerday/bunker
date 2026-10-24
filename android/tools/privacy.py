"""Consent-independent telemetry hardening for the Global 3.7.1 ARM64 client.

Only analytics, crash reporting and advertising/attribution SDK paths are
changed. Bunker's updater, Firebase Messaging and local notifications stay
available. Android's INTERNET permission remains unchanged.
"""
import hashlib
import json
from pathlib import Path
import struct
import xml.etree.ElementTree as ET

import axml
from axml import Attr, Element

PATCH_FILE = Path(__file__).with_name("telemetry_patches.json")
SITES = json.loads(PATCH_FILE.read_text(encoding="utf-8"))["sites"]

# Firebase's permanent deactivation takes precedence over runtime consent.
# Other flags disable automatic collection. The few native patches below
# stop SDK startup or explicit event/reporting calls.
COLLECTION_FLAGS = {
    "firebase_analytics_collection_deactivated": True,
    "firebase_analytics_collection_enabled": False,
    "firebase_crashlytics_collection_enabled": False,
    "google_analytics_adid_collection_enabled": False,
    "google_analytics_default_allow_ad_personalization_signals": False,
    "com.facebook.sdk.AutoLogAppEventsEnabled": False,
    "com.facebook.sdk.AdvertiserIDCollectionEnabled": False,
}
AUTO_INIT_PROVIDERS = {
    # SDK 14.1.1 fetches Graph settings during sdkInitialize even with events off.
    "com.facebook.internal.FacebookInitProvider",
    "com.facebook.ads.AudienceNetworkContentProvider",
    "com.applovin.sdk.AppLovinInitProvider",
    "com.google.android.gms.ads.MobileAdsInitProvider",
    "com.ironsource.lifecycle.IronsourceLifecycleProvider",
}
TRACKING_RECEIVERS = {"com.adjust.sdk.AdjustReferrerReceiver"}
AD_PERMISSIONS = {
    "com.google.android.gms.permission.AD_ID",
    "android.permission.ACCESS_ADSERVICES_AD_ID",
    "android.permission.ACCESS_ADSERVICES_ATTRIBUTION",
    "android.permission.ACCESS_ADSERVICES_TOPICS",
}
NAME, VALUE = 0x01010003, 0x01010024

# UnityConnectSettings, decoded with UnityPy 1.25.0 from Global 3.7.1.
# Only UnityAnalyticsSettings.m_Enabled and .m_InitializeOnStartup change;
# shared services, purchasing, ads and reporting settings retain their values.
# Hash the whole serialized file so the offsets cannot target another build.
UNITY_SETTINGS = "assets/bin/Data/globalgamemanagers"
UNITY_SETTINGS_ORIGINAL = "3b7c1fee129931a7baa8a66de1961bdfb40cb2e4279897645a58229c3d0295d6"
UNITY_SETTINGS_PATCHED = "07b4133ba2a75df8d5744592cdd89316face11899b313b6ea64e24defdfcf5d2"
UNITY_ANALYTICS_OFFSETS = (20495228, 20495230)


def patch_unity_settings(data):
    """Disable native Unity analytics before the engine initializes it."""
    digest = hashlib.sha256(data).hexdigest()
    if digest == UNITY_SETTINGS_PATCHED:
        return bytes(data)
    if digest != UNITY_SETTINGS_ORIGINAL:
        raise ValueError("Unsupported game data: expected Global 3.7.1 UnityConnectSettings")
    result = bytearray(data)
    for offset in UNITY_ANALYTICS_OFFSETS:
        result[offset] = 0
    if hashlib.sha256(result).hexdigest() != UNITY_SETTINGS_PATCHED:
        raise ValueError("Unexpected Unity analytics settings patch result")
    return bytes(result)


def _registration(name):
    return name.startswith("com.google.firebase.components:") and any(
        part in name for part in (".crashlytics.", ".analytics.")
    )


def harden_manifest(manifest):
    """Apply policy after all launcher permissions/components have been merged."""
    app = manifest.find_all("application")[0]
    manifest.children[:] = [entry for entry in manifest.children
                            if not (isinstance(entry, Element) and entry.name == "uses-permission"
                                    and entry.get("name") and entry.get("name").raw in AD_PERMISSIONS)]
    app.children[:] = [entry for entry in app.children
                       if not (isinstance(entry, Element) and entry.get("name") and (
                           entry.name == "provider" and entry.get("name").raw in AUTO_INIT_PROVIDERS
                           or entry.name == "receiver" and entry.get("name").raw in TRACKING_RECEIVERS
                           or entry.name == "meta-data" and entry.get("name").raw in COLLECTION_FLAGS))]
    for entry in app.children:
        if isinstance(entry, Element) and entry.name == "service":
            entry.children[:] = [child for child in entry.children
                                 if not (isinstance(child, Element) and child.name == "meta-data"
                                         and child.get("name") and _registration(child.get("name").raw))]
    for name, value in COLLECTION_FLAGS.items():
        app.children.append(Element("meta-data", [Attr.string("name", name, NAME), Attr.boolean("value", value, VALUE)]))


def harden_text_manifest(path):
    """The apktool/command-line path must apply exactly the same policy."""
    path = Path(path)
    tree = ET.parse(path)
    root = tree.getroot()
    app = root.find("application")
    if app is None:
        raise ValueError("Game manifest has no application")
    name_attr = "{" + axml.ANDROID_NS + "}name"
    value_attr = "{" + axml.ANDROID_NS + "}value"
    for entry in list(root):
        if entry.tag == "uses-permission" and entry.get(name_attr) in AD_PERMISSIONS:
            root.remove(entry)
    for entry in list(app):
        if entry.tag == "provider" and entry.get(name_attr) in AUTO_INIT_PROVIDERS \
                or entry.tag == "receiver" and entry.get(name_attr) in TRACKING_RECEIVERS \
                or entry.tag == "meta-data" and entry.get(name_attr) in COLLECTION_FLAGS:
            app.remove(entry)
        elif entry.tag == "service":
            for child in list(entry):
                if child.tag == "meta-data" and _registration(child.get(name_attr, "")):
                    entry.remove(child)
    for name, value in COLLECTION_FLAGS.items():
        ET.SubElement(app, "meta-data", {name_attr: name, value_attr: str(value).lower()})
    tree.write(path, encoding="utf-8", xml_declaration=True)


def _segments(data):
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise ValueError("Telemetry hardening requires the Android ARM64 ELF library")
    table = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride < 56 or not count or table + stride * count > len(data):
        raise ValueError("Invalid ELF program headers")
    segments = []
    for index in range(count):
        kind, flags, offset, address, _, size, _, _ = struct.unpack_from("<IIQQQQQQ", data, table + index * stride)
        if kind == 1 and flags & 1 and offset + size <= len(data):
            segments.append((offset, address, size))
    return segments


def patch_library(data):
    """Validate every site first, then patch. Recognize our own output idempotently.

    Sites were resolved with Il2CppDumper 6.7.46 from the original Global 3.7.1
    metadata; instruction guards include unchanged surrounding instructions.
    No task-returning method is replaced with null or an incomplete task.
    """
    segments = _segments(data)
    changes = []
    for site in SITES:
        expected = bytes.fromhex(site["original"])
        replacement = bytes.fromhex(site["replacement"])
        offset = next((file + site["rva"] - address for file, address, size in segments
                       if address <= site["rva"] and site["rva"] + len(expected) <= address + size), None)
        if offset is None:
            raise ValueError("Telemetry site outside executable ELF data: " + site["name"])
        actual = data[offset:offset + len(expected)]
        patched = replacement + expected[len(replacement):]
        if actual not in (expected, patched):
            raise ValueError("Unsupported game binary at telemetry site: " + site["name"])
        changes.append((offset, replacement))
    result = bytearray(data)
    for offset, replacement in changes:
        result[offset:offset + len(replacement)] = replacement
    return bytes(result)
