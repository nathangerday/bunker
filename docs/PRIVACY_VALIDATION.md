# Android privacy validation — 2026-10-24

The tested launcher was built from `fcdcdd6` by the fork's
`Privacy Android validation` workflow. The complete game APK was assembled and
signed locally with a private RSA key. Game files and signing material were not
uploaded. Later documentation commits do not change that launcher binary.

## Checks completed

- 46 focused Python tests passed, including packaging/update tests against the
  real original and launcher manifests. CI also passed Android `assembleDebug`
  and `lintDebug`.
- All 66 checked native sites matched the original ARM64 3.7.1 library. The
  telemetry changes modify 299 native bytes; reapplying is idempotent. The signed
  output's manifest flags, providers, advertising permissions and Adjust receiver
  were inspected. Build metadata records game patch 3 and privacy policy 2.
- Android's `apksigner verify` accepted the v2 signature. `zipalign -c -P 16 4`
  accepted the complete APK. The original APK's hash remained unchanged.
- Actual socket probes under the game's UID connected to IPv4 and IPv6 loopback
  listeners. External IPv4 and IPv6 TCP probes were rejected, with matching
  counters in the dedicated firewall chains.
- The official Google APIs Android 11 x86_64 image (revision 16), emulator
  37.2.12 and Windows WHPX booted the launcher and its local server. The build
  required the portable Go CPU paths documented in PRIVACY.md. Graphics used the
  host GPU with `GLESDynamicVersion` enabled (OpenGL ES 3.1).
- Resource preparation verified CRC32 for 201,073 revision-0 files totalling
  20,907,771,934 bytes. Preparation used the PC's 7-Zip and an `adb exec-in` tar
  stream; the on-device archive-import UI was not exercised.
- In a local test profile, the game's ad-tracking dialog was answered Yes. The
  game registered the profile, fetched user/master data from the local server,
  completed its initial 65 MB download over loopback, and rendered the opening
  sequence. Firebase logged “App measurement deactivated via the manifest”.
  Adjust startup and the IronSource identifier diagnostic were absent.
- The emulator's external Ethernet interface was also disabled. This covers DNS
  delegation through Android system services, beyond the game-UID IP filter.

## Limits

Unity's native engine still attempts to contact `cdp.cloud.unity3d.com` and
`config.uca.cloud.unity3d.com`; those attempts failed in the disconnected test.
SDK suppression alone is not a guarantee of zero external traffic. Keep both
the UID policy and the disconnected emulator uplink for that guarantee.

Opening-sequence rendering and scene-progress calls were observed. Movement,
battles, later content and the rewarded-video replacement have not been fully
validated. A comparison with the original telemetry behavior stalled during
loading, so it did not establish a gameplay-control baseline. Windows mouse
automation was unavailable: its helper failed to initialize with
`failed to write kernel assets: The system cannot find the path specified.
(os error 3)`.

The pull request remains a draft pending that wider compatibility validation.
This is not a claim that every game mode has been played through or that the
APK can enforce the emulator's firewall policy by itself.
