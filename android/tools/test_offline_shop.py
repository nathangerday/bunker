"""Shop patch guards plus optional execution against the player's own library.

BUNKER_GAME_LIB=... python -m unittest discover -s android/tools -p test_offline_shop.py
Install unicorn to also execute the patched ARM64 completion and price paths.
No game code or metadata is included in the test fixtures.
"""
import importlib.util
import os
from pathlib import Path
import struct
import unittest

import offline_shop


def fixture():
    data = bytearray(0xA000)
    data[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<H", data, 18, 183)
    struct.pack_into("<Q", data, 32, 64)
    struct.pack_into("<HH", data, 54, 56, 1)
    struct.pack_into("<IIQQQQQQ", data, 64, 1, 5, 0x1000, 0x282C000, 0, 0x9000, 0x9000, 0x1000)
    for rva, originals, replacement in offline_shop.SITES:
        at = offline_shop.executable_offset(data, rva, len(replacement))
        data[at:at + len(replacement)] = originals[0]
    return data


class Guards(unittest.TestCase):
    def test_manifest_disables_checkout_and_preserves_other_components(self):
        import axml
        def named(kind, name):
            return axml.Element(kind, [axml.Attr.string("name", name, 0x01010003)])
        doc = axml.Document(axml.Element("manifest", children=[
            named("uses-permission", offline_shop.BILLING_PERMISSION),
            named("uses-permission", "android.permission.INTERNET"),
            axml.Element("application", children=[
                *(named("activity", name) for name in sorted(offline_shop.BILLING_ACTIVITIES)),
                named("activity", "org.veritr1x.bunker.MainActivity"),
                named("service", "org.veritr1x.bunker.ServerService"),
            ]),
        ]), [("android", axml.ANDROID_NS, 0)])
        patched = offline_shop.disable_billing_manifest(axml.serialize(doc))
        root = axml.parse(patched).root
        self.assertEqual([p.get("name").raw for p in root.find_all("uses-permission")],
                         ["android.permission.INTERNET"])
        app = root.find_all("application")[0]
        self.assertEqual([a.get("name").raw for a in app.find_all("activity")],
                         ["org.veritr1x.bunker.MainActivity"])
        self.assertEqual(app.find_all("service")[0].get("name").raw, "org.veritr1x.bunker.ServerService")
        self.assertEqual(offline_shop.disable_billing_manifest(patched), patched)

    def test_nonidentity_elf_mapping_and_idempotence(self):
        original = fixture()
        patched = offline_shop.patch(original)
        self.assertNotEqual(patched, original)
        self.assertEqual(len(patched), len(original))
        self.assertEqual(offline_shop.patch(patched), patched)
        for rva, _, replacement in offline_shop.SITES:
            at = offline_shop.executable_offset(original, rva, len(replacement))
            self.assertEqual(patched[at:at + len(replacement)], replacement)

    def test_unknown_code_does_not_partially_mutate_input(self):
        for rva, _, replacement in offline_shop.SITES:
            data = fixture()
            data[offline_shop.executable_offset(data, rva, len(replacement))] ^= 0xff
            before = bytes(data)
            with self.assertRaisesRegex(RuntimeError, "Unsupported game binary"):
                offline_shop.patch(data)
            self.assertEqual(data, before)

    def test_invalid_or_nonexecutable_library_is_refused(self):
        for data in (b"", b"not ELF", fixture()[:80]):
            with self.assertRaises(RuntimeError):
                offline_shop.patch(data)
        data = fixture()
        struct.pack_into("<I", data, 68, 4)  # PT_LOAD, read-only
        with self.assertRaisesRegex(RuntimeError, "outside executable"):
            offline_shop.patch(data)


@unittest.skipUnless(os.environ.get("BUNKER_GAME_LIB"), "set BUNKER_GAME_LIB to original 3.7.1 ARM64 library")
class GameLibrary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original = Path(os.environ["BUNKER_GAME_LIB"]).read_bytes()
        cls.patched = offline_shop.patch(cls.original)

    def test_original_and_upstream_patched_library(self):
        root = Path(__file__).resolve().parents[2]
        spec = importlib.util.spec_from_file_location("upstream_patch", root / "upstream/lunar-scripts/android/patch_apk.py")
        upstream = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(upstream)
        data = bytearray(self.original)
        for site in upstream.IL2CPP_PATCHES:
            data[site["rva"]:site["rva"] + len(site["bytes"])] = site["bytes"]
        patched = offline_shop.patch(data)
        self.assertEqual(offline_shop.patch(patched), patched)

    @unittest.skipUnless(importlib.util.find_spec("unicorn"), "install unicorn for ARM64 execution")
    def test_sdk_cannot_initialize_or_checkout_with_existing_controller(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X21, UC_ARM64_REG_X30, UC_ARM64_REG_PC
        vm = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        vm.mem_map(0, (len(self.patched) + 4095) & ~4095)
        vm.mem_write(0, self.patched)
        vm.reg_write(UC_ARM64_REG_X30, 0x10000)
        vm.reg_write(UC_ARM64_REG_X0, 0x20000)
        vm.emu_start(0x2830E68, 0x10000, count=4)
        self.assertEqual(vm.reg_read(UC_ARM64_REG_PC), 0x10000)
        self.assertEqual(vm.reg_read(UC_ARM64_REG_X0), 0)
        for controller in (0, 0x20000):
            vm.reg_write(UC_ARM64_REG_X21, controller)
            vm.emu_start(0x2834028, 0x28342F4, count=2)
            self.assertEqual(vm.reg_read(UC_ARM64_REG_PC), 0x28342F4)

    @unittest.skipUnless(importlib.util.find_spec("unicorn"), "install unicorn for ARM64 execution")
    def test_success_and_refusal_execute_distinct_completion_paths(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM, UC_HOOK_CODE
        from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X8, UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_X30, UC_ARM64_REG_PC

        for error in (0, 9):
            vm = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
            vm.mem_map(0, (len(self.patched) + 4095) & ~4095)
            vm.mem_write(0, self.patched)
            vm.reg_write(UC_ARM64_REG_X0, error)
            vm.reg_write(UC_ARM64_REG_X8, error)
            vm.reg_write(UC_ARM64_REG_X19, 0x10000)  # async state
            vm.reg_write(UC_ARM64_REG_X20, 0x20000)  # DarkPurchase
            calls = []
            targets = {0x25C6FCC: "allocate", 0x2B5C8EC: "connecting_out", 0x2F94C74: "send",
                       0x2831564: "success", 0x282DC7C: "receipt_error", 0x28313F0: "error"}

            def called(uc, address, size, context):
                name = targets.get(address)
                if name:
                    calls.append(name)
                    if name == "allocate":
                        uc.reg_write(UC_ARM64_REG_X0, 0x30000)
                    if name == "success":
                        self.assertEqual(uc.reg_read(UC_ARM64_REG_X0), 0)  # no overflow
                        self.assertEqual(uc.reg_read(UC_ARM64_REG_X1), 0)
                        uc.reg_write(UC_ARM64_REG_X0, 0x40000)
                    if name == "error":
                        self.assertEqual(uc.reg_read(UC_ARM64_REG_X0), error)
                        uc.reg_write(UC_ARM64_REG_X0, 0x50000)
                    uc.reg_write(UC_ARM64_REG_PC, uc.reg_read(UC_ARM64_REG_X30))
            vm.hook_add(UC_HOOK_CODE, called)
            vm.emu_start(0x2831C18, 0x2831FEC, count=100)
            self.assertEqual(vm.reg_read(UC_ARM64_REG_PC), 0x2831FEC)
            self.assertEqual(calls, ["allocate", "connecting_out", "send", "success"] if error == 0
                             else ["receipt_error", "error"])
            self.assertEqual(vm.reg_read(UC_ARM64_REG_X0), 0x40000 if error == 0 else 0x50000)

    @unittest.skipUnless(importlib.util.find_spec("unicorn"), "install unicorn for ARM64 execution")
    def test_forced_initialization_and_fractional_prices(self):
        from unicorn import Uc, UC_ARCH_ARM64, UC_MODE_ARM
        from unicorn.arm64_const import UC_ARM64_REG_X0, UC_ARM64_REG_X1, UC_ARM64_REG_X19, UC_ARM64_REG_X20, UC_ARM64_REG_X24, UC_ARM64_REG_PC
        vm = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        vm.mem_map(0, (len(self.patched) + 4095) & ~4095)
        vm.mem_write(0, self.patched)
        vm.reg_write(UC_ARM64_REG_X20, 0x10000)
        vm.reg_write(UC_ARM64_REG_X24, 0x20000)
        for initialized in (0, 1):
            for force in (0, 1):
                vm.mem_write(0x10020, bytes([initialized]))
                vm.mem_write(0x20028, bytes([force]))
                vm.emu_start(0x2830830, 0x2830C54, count=10)
                self.assertEqual(vm.reg_read(UC_ARM64_REG_PC), 0x2830C54)
        # Decimal's flags/hi and lo/mid halves for 0.99, 9.99, 79.99.
        for cents in (99, 999, 7999):
            vm.reg_write(UC_ARM64_REG_X19, 2 << 16)
            vm.reg_write(UC_ARM64_REG_X20, cents)
            vm.emu_start(0x282C964, 0x282C9AC, count=10)
            self.assertEqual(vm.reg_read(UC_ARM64_REG_PC), 0x282C9AC)
            self.assertEqual(vm.reg_read(UC_ARM64_REG_X0), 2 << 16)
            self.assertEqual(vm.reg_read(UC_ARM64_REG_X1), cents)


if __name__ == "__main__":
    unittest.main()
