"""Telemetry flags, binary guards and preservation of game/messaging code."""
import struct
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET
import zipfile

import axml
from axml import Attr, Document, Element
import privacy


def manifest():
    app = Element("application", children=[
        Element("meta-data", [Attr.string("name", "firebase_analytics_collection_deactivated", privacy.NAME),
                              Attr.boolean("value", False, privacy.VALUE)]),
        Element("meta-data", [Attr.string("name", "com.facebook.sdk.AutoLogAppEventsEnabled", privacy.NAME),
                              Attr.boolean("value", True, privacy.VALUE)]),
        Element("meta-data", [Attr.string("name", "game.setting", privacy.NAME), Attr.string("value", "keep", privacy.VALUE)]),
        Element("provider", [Attr.string("name", "com.google.firebase.provider.FirebaseInitProvider", privacy.NAME)]),
        Element("provider", [Attr.string("name", "com.facebook.internal.FacebookInitProvider", privacy.NAME)]),
        Element("provider", [Attr.string("name", "com.applovin.sdk.AppLovinInitProvider", privacy.NAME)]),
        Element("provider", [Attr.string("name", "org.veritr1x.bunker.GameProcessProvider", privacy.NAME)]),
        Element("meta-data", [Attr.string("name", "firebase_messaging_auto_init_enabled", privacy.NAME),
                              Attr.boolean("value", True, privacy.VALUE)]),
        Element("service", [Attr.string("name", "com.google.firebase.messaging.FirebaseMessagingService", privacy.NAME)]),
        Element("receiver", [Attr.string("name", "com.adjust.sdk.AdjustReferrerReceiver", privacy.NAME)]),
        Element("service", [Attr.string("name", "com.google.firebase.components.ComponentDiscoveryService", privacy.NAME)], [
            Element("meta-data", [Attr.string("name", "com.google.firebase.components:com.google.firebase.crashlytics.CrashlyticsRegistrar", privacy.NAME)]),
            Element("meta-data", [Attr.string("name", "unrelated.component", privacy.NAME)]),
        ]),
    ])
    return Element("manifest", children=[
        Element("uses-permission", [Attr.string("name", "android.permission.INTERNET", privacy.NAME)]),
        Element("uses-permission", [Attr.string("name", "com.google.android.gms.permission.AD_ID", privacy.NAME)]), app])


def elf():
    # Small synthetic ELF: each original instruction sequence gets its own
    # executable mapping at the real RVA; no copyrighted game file is needed.
    count = len(privacy.SITES)
    start = 64 + count * 56
    data = bytearray(start + count * 32)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, count)
    offsets = []
    for index, site in enumerate(privacy.SITES):
        offset = start + index * 32
        struct.pack_into("<IIQQQQQQ", data, 64 + index * 56, 1, 5, offset, site["rva"], 0, 16, 16, 4)
        data[offset:offset + 16] = bytes.fromhex(site["original"])
        offsets.append(offset)
    return data, offsets


class PrivacyTests(unittest.TestCase):
    def test_tracking_flags_preserve_local_server_and_messaging(self):
        root = manifest()
        privacy.harden_manifest(root)
        app = root.find_all("application")[0]
        flags = {x.get("name").raw: bool(x.get("value").data) for x in app.find_all("meta-data")
                 if x.get("name").raw in privacy.COLLECTION_FLAGS}
        self.assertTrue(flags["firebase_analytics_collection_deactivated"])
        self.assertFalse(flags["com.facebook.sdk.AutoLogAppEventsEnabled"])
        self.assertFalse(flags["firebase_crashlytics_collection_enabled"])
        permissions = {x.get("name").raw for x in root.find_all("uses-permission")}
        self.assertIn("android.permission.INTERNET", permissions)
        self.assertNotIn("com.google.android.gms.permission.AD_ID", permissions)
        self.assertEqual([x.get("name").raw for x in app.find_all("provider")], [
            "com.google.firebase.provider.FirebaseInitProvider",
            "org.veritr1x.bunker.GameProcessProvider"])
        self.assertEqual(app.find_all("receiver"), [])
        self.assertEqual([x.get("name").raw for x in app.find_all("service")[1].find_all("meta-data")], ["unrelated.component"])
        self.assertEqual(app.find_all("service")[0].get("name").raw,
                         "com.google.firebase.messaging.FirebaseMessagingService")
        messaging = next(x for x in app.find_all("meta-data") if x.get("name").raw == "firebase_messaging_auto_init_enabled")
        self.assertTrue(messaging.get("value").data)

    def test_binary_manifest_round_trip_and_idempotence(self):
        root = manifest()
        privacy.harden_manifest(root)
        namespaces = [("android", axml.ANDROID_NS, 0)]
        first = axml.serialize(Document(root, namespaces))
        doc = axml.parse(first)
        privacy.harden_manifest(doc.root)
        self.assertEqual(first, axml.serialize(doc))

    def test_apktool_manifest_gets_the_same_flags(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "AndroidManifest.xml"
            path.write_text('<manifest xmlns:android="' + axml.ANDROID_NS + '"><uses-permission android:name="android.permission.INTERNET"/>'
                            '<application><meta-data android:name="firebase_analytics_collection_deactivated" android:value="false"/>'
                            '<provider android:name="com.facebook.internal.FacebookInitProvider"/></application></manifest>')
            privacy.harden_text_manifest(path)
            first = path.read_bytes()
            privacy.harden_text_manifest(path)
            self.assertEqual(first, path.read_bytes())
            root = ET.parse(path).getroot()
            flags = {x.get("{" + axml.ANDROID_NS + "}name"): x.get("{" + axml.ANDROID_NS + "}value")
                     for x in root.find("application").findall("meta-data")}
            self.assertEqual(flags, {k: str(v).lower() for k, v in privacy.COLLECTION_FLAGS.items()})
            self.assertEqual(len(root.find("application").findall("provider")), 0)
            self.assertIsNotNone(root.find("uses-permission"))

    def test_native_patches_are_checked_idempotent_and_localized(self):
        source, offsets = elf()
        original = bytes(source)
        patched = privacy.patch_library(source)
        self.assertEqual(bytes(source), original)
        allowed = set()
        for site, offset in zip(privacy.SITES, offsets):
            replacement = bytes.fromhex(site["replacement"])
            self.assertEqual(patched[offset:offset + len(replacement)], replacement)
            allowed.update(range(offset, offset + len(replacement)))
        self.assertTrue(all(a == b or index in allowed for index, (a, b) in enumerate(zip(original, patched))))
        self.assertEqual(privacy.patch_library(patched), patched)

    def test_unknown_instruction_fails_before_mutating_input(self):
        source, offsets = elf()
        source[offsets[-1] + 12] ^= 1
        original = bytes(source)
        with self.assertRaisesRegex(ValueError, "Unsupported game binary"):
            privacy.patch_library(source)
        self.assertEqual(bytes(source), original)

    def test_non_executable_mapping_and_wrong_architecture_are_rejected(self):
        source, _ = elf()
        struct.pack_into("<I", source, 64 + 4, 4)
        with self.assertRaisesRegex(ValueError, "outside executable"):
            privacy.patch_library(source)
        struct.pack_into("<H", source, 18, 62)
        with self.assertRaisesRegex(ValueError, "ARM64"):
            privacy.patch_library(source)

    def test_unrecognized_unity_settings_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unsupported game data"):
            privacy.patch_unity_settings(b"another game's settings")

    def test_real_game_settings_messaging_and_rewards_boundary(self):
        apk = Path(__file__).resolve().parents[2] / "inputs/game-3.7.1.apk"
        if not apk.is_file():
            self.skipTest("requires the user's original APK")
        with zipfile.ZipFile(apk) as archive:
            original = archive.read(privacy.UNITY_SETTINGS)
            patched = privacy.patch_unity_settings(original)
            self.assertEqual([i for i, (a, b) in enumerate(zip(original, patched)) if a != b],
                             list(privacy.UNITY_ANALYTICS_OFFSETS))
            self.assertEqual(privacy.patch_unity_settings(patched), patched)
            changed = bytearray(original)
            changed[0] ^= 1
            with self.assertRaises(ValueError):
                privacy.patch_unity_settings(changed)
            library = archive.read("lib/arm64-v8a/libil2cpp.so")
            patched = privacy.patch_library(library)
            segments = privacy._segments(library)
            # Messaging, ad display and IronSource availability/reward callbacks
            # retain the original game's instructions.
            for rva in (0x53C8CD4, 0x53C9600, 0x53C903C, 0x53C9110,
                        53027100, 53027280, 53028000, 53027640,
                        53026144, 53025940, 53026920, 53025564):
                offset = next(file + rva - address for file, address, size in segments
                              if address <= rva < address + size)
                self.assertEqual(patched[offset:offset + 16], library[offset:offset + 16])


if __name__ == "__main__":
    unittest.main()
