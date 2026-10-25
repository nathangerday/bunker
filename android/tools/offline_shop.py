"""Complete Android 3.7.1 real-money shop purchases through Lunar Tear only.

CreatePurchaseTransaction already grants the contents on the local server. The
old lunar-scripts patch then calls BuyProduct and reports cancellation when no
Google store controller exists. Finish after the successful server response,
release the menu's input blocker, and return PurchaseResult.Success instead.
Server errors still follow the original error path. No receipt is fabricated or
saved, and neither Google billing nor its recovery/revenue path is entered.

RVAs and original bytes are from the original ARM64 3.7.1 APK. Accept upstream's
existing patches too; check every site before writing anything. Prices remain
in master data: force the game's own fallback and retain its Decimal cents.
"""
import struct


def branch(source, target, link=False):
    delta = target - source
    if delta % 4 or not -(1 << 27) <= delta < (1 << 27):
        raise ValueError("Invalid ARM64 branch")
    return struct.pack("<I", (0x94000000 if link else 0x14000000) | ((delta // 4) & 0x3ffffff))


def completion():
    # Same ConnectingOut request as the original purchase completion. The
    # metadata reference stays on the same PC page; BLs are relocated below.
    start = 0x2831E4C
    code = bytearray.fromhex("28510290 08e940f9 000140f9")
    code += branch(start + len(code), 0x25C6FCC, True)  # il2cpp object allocation
    code += bytes.fromhex("f50300aa e1031faa")         # x21 = request; MethodInfo = NULL
    code += branch(start + len(code), 0x2B5C8EC, True)  # ConnectingOutParameter .ctor
    code += bytes.fromhex("e00315aa e1031faa")
    code += branch(start + len(code), 0x2F94C74, True)  # RequestBus.Send
    code += bytes.fromhex("e0031faa e1031faa")         # no overflow; MethodInfo = NULL
    code += branch(start + len(code), 0x2831564, True)  # PurchaseResult.Success
    code += branch(start + len(code), 0x2831FEC)       # original async SetResult/epilogue
    return bytes(code)


# (RVA, accepted unpatched/upstream bytes, replacement).
SITES = (
    # Also stop the SDK entry points themselves. In particular the old upstream
    # BuyProduct guard only avoided billing when _storeController was NULL;
    # a phone with Play installed can have a non-NULL controller.
    # InitializeAndroid returns a completed non-generic UniTask (one NULL pointer).
    (0x2830E68, (bytes.fromhex("ff4302d1f72b00f9"),), bytes.fromhex("e0031faac0035fd6")),
    (0x2834028, (bytes.fromhex("f51a00b4"), bytes.fromhex("751600b4")), branch(0x2834028, 0x28342F4)),
    # Even a forced Initialize must not start Unity Purchasing/Google billing.
    (0x2830834, (bytes.fromhex("68000034"), bytes.fromhex("1f2003d5")), branch(0x2830834, 0x2830C54)),
    (0x2831CA8, (bytes.fromhex("e8160034"),), bytes.fromhex("1f2003d5")),
    (0x2831CAC, (bytes.fromhex("610a43a9"),), branch(0x2831CAC, 0x2831D10)),
    # Success-only block, reached after CreateBridgeTransactionAsync.GetResult
    # tests ErrorType == None. Leave the RPC, awaiters and error handling intact.
    (0x2831E4C, (bytes.fromhex(
        "085b02b008c147f9000140f91dd56894683240f9e81f00b4e01f00b4"
        "612a40f9020940f9e3031faae2e03794682640f9481f00b41f0900f9"),), completion()),
    (0x282C7A8, (bytes.fromhex("200500b4"),), branch(0x282C7A8, 0x282C84C)),
    (0x282CBFC, (bytes.fromhex("600500b4"),), branch(0x282CBFC, 0x282CCA8)),
    # The fallback used to cast Decimal -> int -> Decimal, dropping cents.
    (0x282C96C, (bytes.fromhex("e2031faa"),), branch(0x282C96C, 0x282C9AC)),
)


def executable_offset(data, rva, size):
    if len(data) < 64 or data[:6] != b"\x7fELF\x02\x01" or struct.unpack_from("<H", data, 18)[0] != 183:
        raise RuntimeError("Expected the Android ARM64 game library")
    table = struct.unpack_from("<Q", data, 32)[0]
    stride, count = struct.unpack_from("<HH", data, 54)
    if stride < 56 or table + stride * count > len(data):
        raise RuntimeError("Invalid game library program headers")
    for i in range(count):
        kind, flags, offset, address, _, length, _, _ = struct.unpack_from("<IIQQQQQQ", data, table + i * stride)
        if kind == 1 and flags & 1 and address <= rva and rva + size <= address + length:
            at = offset + rva - address
            if at + size <= len(data):
                return at
    raise RuntimeError(f"Shop patch 0x{rva:X} is outside executable ELF data")


def patch(data):
    changes = []
    for rva, originals, replacement in SITES:
        at = executable_offset(data, rva, len(replacement))
        if data[at:at + len(replacement)] not in (*originals, replacement):
            raise RuntimeError(f"Unsupported game binary: expected 3.7.1 shop code at 0x{rva:X}")
        changes.append((at, replacement))
    result = bytearray(data)
    for at, replacement in changes:
        result[at:at + len(replacement)] = replacement
    return bytes(result)


def patch_game(game):
    path = game / "lib/arm64-v8a/libil2cpp.so"
    path.write_bytes(patch(path.read_bytes()))
    print("Offline shop enabled (original prices; no store billing)")


BILLING_PERMISSION = "com.android.vending.BILLING"
BILLING_ACTIVITIES = {"com.android.billingclient.api.ProxyBillingActivity",
                      "com.android.billingclient.api.ProxyBillingActivityV2"}


def disable_billing_manifest(data):
    """Remove the Android permission and activity used to open the Play checkout.

    Keep this in addition to the local purchase flow, so no SDK entry point can
    open a Google payment screen in an offline build.
    """
    import axml
    doc = axml.parse(data)
    for permission in list(doc.root.find_all("uses-permission")):
        if permission.get("name").raw == BILLING_PERMISSION:
            doc.root.children.remove(permission)
    for app in doc.root.find_all("application"):
        for activity in list(app.find_all("activity")):
            if activity.get("name").raw in BILLING_ACTIVITIES:
                app.children.remove(activity)
    return axml.serialize(doc)
