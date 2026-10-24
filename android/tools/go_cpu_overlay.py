#!/usr/bin/env python3
"""Avoid Go's optional MIDR probe on Android ARM translators.

The API 30 Google ARM64 translator advertises HWCAP_CPUID but raises SIGILL on
MRS MIDR_EL1. Go uses that register only to select a Neoverse performance path.
Keep the other capability checks and use the generic path on Android. A Go
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
    needle = b"if ARM64.HasCPUID {"
    if original.count(needle) != 1:
        raise RuntimeError("Expected one MIDR capability guard")
    directory = Path(__file__).resolve().parents[2] / ".build/android-go"
    directory.mkdir(parents=True, exist_ok=True)
    patched = directory / source.name
    patched.write_bytes(original.replace(needle, b'if ARM64.HasCPUID && os != "android" {'))
    overlay = directory / "overlay.json"
    overlay.write_text(json.dumps({"Replace": {str(source): str(patched)}}), encoding="utf-8")
    print(overlay)


if __name__ == "__main__":
    main()
