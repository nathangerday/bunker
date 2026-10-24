# Android tracker suppression

This fork targets analytics, crash reporting and advertising/attribution SDKs
present in the original Global 3.7.1 ARM64 game. It does not disable Internet
access. Bunker's update checker, release URLs and installation behavior remain
unchanged from upstream. Firebase Messaging and local notification code also
remain unchanged.

## Changes

- Disable native Unity Analytics in the serialized startup settings before the
  engine initializes it. Only `UnityAnalyticsSettings.m_Enabled` and
  `m_InitializeOnStartup` change; purchasing and shared services retain their
  original settings.
- Suppress managed Unity Analytics startup, event and upload paths, including
  its analytics-specific consent checks and legacy event calls.
- Permanently deactivate Firebase Analytics using manifest metadata and force
  its collection setters off. Suppress Crashlytics recording and automatic
  registration. Keep the shared Firebase provider and Messaging components.
- Suppress Facebook activation, purchase and event logging, and disable its
  automatic event and advertising-ID collection. Keep its shared initializer.
- Suppress Adjust startup, lifecycle, event and attribution/reporting paths and
  remove its install-referrer receiver.
- Disable advertising SDK automatic providers and IronSource initialization,
  identifier/metadata calls and identifier diagnostic. Preserve Bunker's existing
  local rewarded-video replacement; its availability check still returns true.
  The game's ad-display entry points are not replaced by this privacy policy.
- Remove advertising-ID/AdServices permissions. Keep Android's INTERNET
  permission for both the local server and legitimate update connections.

The 57 ARM64 locations in `android/tools/telemetry_patches.json` were resolved
from the original metadata using Il2CppDumper 6.7.46. The patcher checks original
instructions and executable ELF ranges before changing bytes. Unknown binaries
are refused; reapplying is idempotent. No asynchronous method is replaced with
null or an unfinished Task.

The native Unity settings were decoded with UnityPy 1.25.0. Only two boolean
bytes are patched, guarded by SHA-256 hashes of the original and patched file.
UnityPy is an analysis tool, not a new build or browser dependency.

These changes apply through both the direct/web assembler and apktool packaging.
Game patch 4 / privacy policy 3 requires rebuilding older installations from the
original APK. A launcher-only update cannot undo the earlier draft's game-code
or manifest changes. Later compatible launcher updates preserve these patches.

## Build and update

Follow [BUILD.md](BUILD.md) or use this fork's `Privacy Android validation`
launcher artifact. Supply the original APK and master data locally. On Windows,
set `$env:PYTHONUTF8='1'` for the Python assembly tools. The upstream hosted
builder does not include this fork's patches.

Update checks stay enabled by default and use upstream Bunker releases. Android
still requires the same signing key to update an installation. As in upstream,
an installation signed with your own key must be rebuilt and signed with that
key; the public-key self-installer cannot replace it. Retain your private key
and install the replacement APK over the existing app to preserve saves.

No firewall, DNS, emulator network, push-notification or CPU configuration change
is included in this privacy PR. The earlier emulator CPU workaround is isolated
on `compat/android-arm-translation`; it is optional compatibility work.

## Verification limits

This is targeted SDK suppression, not a universal network sandbox. A successful
build or a quiet log is not proof that every possible tracking path is absent.
See [PRIVACY_VALIDATION.md](PRIVACY_VALIDATION.md) for evidence and remaining
runtime/gameplay checks. No equivalent iOS hardening is claimed.

Game files, resource dumps, saves and private signing material stay local and
must not be committed or uploaded. Original project credits and licenses remain.
Upstream: https://github.com/veritr1x/bunker
