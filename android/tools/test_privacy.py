"""Privacy regressions: old consent, both manifest formats and unknown binaries."""
import struct
import tempfile
from pathlib import Path
import unittest
import xml.etree.ElementTree as ET

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
        Element("provider", [Attr.string("name", "org.veritr1x.bunker.GameProcessProvider", privacy.NAME)]),
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
    def test_old_consent_is_overridden_without_breaking_local_server(self):
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
        self.assertEqual([x.get("name").raw for x in app.find_all("provider")], ["org.veritr1x.bunker.GameProcessProvider"])
        self.assertEqual(app.find_all("receiver"), [])
        self.assertEqual([x.get("name").raw for x in app.find_all("service")[0].find_all("meta-data")], ["unrelated.component"])

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
            self.assertEqual(root.find("application").findall("provider"), [])
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


if __name__ == "__main__":
    unittest.main()
