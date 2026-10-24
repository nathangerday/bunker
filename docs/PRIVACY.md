# Android privacy fork

This fork hardens the Global 3.7.1 ARM64 client against its original telemetry
SDKs. The existing consent dialog is not a reliable indication of collection:
the patched methods deny Unity Analytics consent regardless of the saved choice.
The game, game assets and master data are still supplied locally by the player.

## What the APK changes

- Permanently deactivates Firebase Analytics through Android manifest metadata,
  disables its advertising-ID collection, and forces both managed collection
  setter arguments to false without skipping Firebase's normal initialization.
- Suppresses Unity Analytics startup/event/flush paths and reports consent as
  denied. Legacy managed Unity Analytics calls return AnalyticsDisabled.
- Suppresses Crashlytics initialization, logging, user identification and exception
  recording, and removes its automatic component registration.
- Suppresses Facebook app, purchase and activation events; disables automatic
  Facebook initialization/event logging and advertiser-ID collection.
- Suppresses IronSource ad SDK initialization and network ad entry points.
  Bunker's existing local rewarded-video replacement is retained.
- Disables Firebase Messaging listener setup and default automatic initialization.
- Suppresses Adjust automatic/manual startup, lifecycle, event, revenue,
  subscription, consent and sharing calls. Suppresses the IronSource integration
  diagnostic, which reads an advertising identifier even without ad initialization.
- Removes the listed analytics/ad automatic providers and advertising permissions.
  Android's INTERNET permission stays because the local server needs it.
- Defaults update checks to off. This fork's launcher checks this fork's releases,
  not the upstream release channel, if the player explicitly enables checking.

The 66 ARM64 sites in android/tools/telemetry_patches.json were resolved from the
original 3.7.1 metadata using Il2CppDumper 6.7.46. Every site includes an original
instruction fingerprint and executable-ELF range validation. All sites are checked
before changing any bytes; a mismatch aborts the build. Reapplying is idempotent.
No asynchronous method is replaced with null or an unfinished Task.

The policy is applied by both the direct/web assembler and the apktool build.
The game-patch revision is bumped to 3 (privacy policy 2): older Bunker installations must be rebuilt
from the original APK rather than being labelled as hardened by a launcher update.
Updates made by these tools retain and reapply the manifest policy. The public web
builder hosted by the original author does not include these fork changes.

## Enforce external-network blocking on a PC emulator

SDK deactivation is not a universal network sandbox. Native Unity engine code and
unreviewed SDK paths may still attempt connections. For enforced IP egress
blocking, use the supplied helper with a root-enabled Android emulator. An
Android 11 Google APIs x86_64 image is a suitable test target: it supports ARM64
translation and adb root. A Google Play production image does not provide adb root.

The native server build uses a checked Go 1.25.8 source overlay to select its
portable CPU paths on Android. The API 30 ARM translator advertises CPUID and AES
support but crashes on the MIDR register read and AESE instruction. Android does
not support Go's early GODEBUG CPU override, so this is handled at build time,
before runtime hash initialization. This also sacrifices optional Go CPU
optimizations on real ARM devices. On x86 emulators the launcher additionally
sets `GODEBUG=cpu.all=off` for third-party CPU detection during later package
initialization. The installed Go toolchain stays intact. A different Go version
or source fingerprint requires review before building.

After installing the hardened APK, list devices and select the intended emulator:

```powershell
adb devices
adb -s emulator-5554 root
python scripts/emulator_network.py run --serial emulator-5554
```

The helper stops the game, discovers its installed UID in Android user 0, creates
dedicated IPv4 and IPv6 OUTPUT rules for that UID, and starts the launcher only
after verifying both policies. Localhost remains available. All other destination
addresses are rejected, including native TCP/UDP sockets. No other app UID or
host-PC firewall rule is changed. If root, owner matching, IPv6, or verification
fails, it exits unsuccessfully and does not launch the game.

```powershell
python scripts/emulator_network.py status --serial emulator-5554
python scripts/emulator_network.py remove --serial emulator-5554
```

Rules are runtime state: reapply after an emulator reboot or reinstall (which may
change the UID). Remove rules before uninstalling to avoid leaving a rule for an
old UID. A saved emulator snapshot may also contain these rules. Android may
delegate DNS queries to a system resolver outside the game's UID; the helper does
not claim to silence all system DNS traffic. For zero external emulator traffic,
disconnect the emulator's network as well. Loopback remains usable offline.

These changes apply to Android. The iOS build is not claimed to have equivalent
SDK hardening. Full game compatibility and actual device network behavior must
be assessed by runtime testing, not merely a successful APK build.

## Signing and saves

Use your own private signing key for a persistent installation. Do not upload
game APKs, resource dumps, master data, saves, or signing keys to the repository.
An APK signed with a different key cannot update an existing installation.
Export saves through Bunker before replacing an installation; uninstalling an
app deletes its private data. Keep your private key for future builds.

The original Bunker project and its authors retain their credits and licenses.
Upstream: https://github.com/veritr1x/bunker
