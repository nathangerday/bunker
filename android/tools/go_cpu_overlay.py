#!/usr/bin/env python3
"""Use portable Go CPU paths for this Android emulator build.

The API 30 Google ARM64 translator advertises HWCAP_CPUID but raises SIGILL on
MRS MIDR_EL1 and AESE. Android does not support Go's early GODEBUG CPU override,
so select the generic paths before runtime hash initialization. This sacrifices
optional Go CPU optimizations on Android, including real ARM devices. A Go
overlay leaves the installed toolchain untouched; review when updating Go.
"""
import hashlib
import json
from pathlib import Path
import subprocess

EXPECTED = "1828fb8a6a21a10d023f82767a14e3b37742d47d9077f64818274d7cedeea8fa"


def main():
    version = subprocess.check_output(["go", "env", "GOVERSION"], text=True).strip()
    if version != "go1.25.8":
        raise RuntimeError("Review the Android CPU overlay for this Go version: " + version)
    goroot = Path(subprocess.check_output(["go", "env", "GOROOT"], text=True).strip())
    source = goroot / "src/internal/cpu/cpu_arm64_hwcap.go"
    original = source.read_bytes()
    if hashlib.sha256(original).hexdigest() != EXPECTED:
        raise RuntimeError("Go CPU source changed; refusing an unchecked overlay")
    needle = b"func hwcapInit(os string) {"
    if original.count(needle) != 1:
        raise RuntimeError("Expected one ARM64 feature initializer")
    directory = Path(__file__).resolve().parents[2] / ".build/android-go"
    directory.mkdir(parents=True, exist_ok=True)
    patched = directory / source.name
    patched.write_bytes(original.replace(needle, needle + b'\n\tif os == "android" {\n\t\treturn\n\t}'))
    overlay = directory / "overlay.json"
    overlay.write_text(json.dumps({"Replace": {str(source): str(patched)}}), encoding="utf-8")
    print(overlay)


if __name__ == "__main__":
    main()
