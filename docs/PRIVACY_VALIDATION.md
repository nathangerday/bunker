# Android tracker validation — 2026-10-24

The earlier draft combined SDK suppression with complete emulator network
isolation. That isolation has been removed from this PR: updates must continue
to work. Its disconnected runtime results do not establish the revised build's
behavior with Internet access.

## Source and original-file checks

- All 57 retained native sites match the original Global 3.7.1 ARM64 library.
  Patching is guarded and idempotent. Tests also verify that the four previously
  modified Firebase Messaging methods and four ad-display methods stay intact.
- Decoding the original UnityConnectSettings showed native analytics and
  initialize-on-startup enabled. The revised patch changes exactly those two
  booleans. Shared services, purchasing, crash reporting and ads settings retain
  their original values. Whole-file hashes guard the two offsets.
- Manifest tests preserve INTERNET, shared Firebase/Facebook initialization,
  Messaging service/auto-init configuration and Bunker's local server provider,
  while removing only targeted analytics/ad components and permissions.
- The updater source is restored byte-for-byte to upstream: checks enabled by
  default, original GitHub release endpoint and original hosted builder URL.
- Repackaging/update tests verify that compatible launcher/server updates still
  replace Bunker's files and preserve the game's files and local data inputs.
- 43 focused local tests passed: 26 Android privacy/packaging/update tests,
  16 release/version/notices tests and the web-builder import check. Android
  build and lint CI passed for privacy source `50a00f9` and the separate emulator
  test combination `adf4648` (runs 40129156830 and 40129187634).
- Broad upstream discovery also includes manual scripts requiring save inputs,
  optional dependencies and Unix-specific checks that fail on this Windows
  setup. Those unrelated tests were not changed; the focused results above
  must not be read as a claim that broad discovery passed.

## Runtime scope

The previous build rendered the title/opening sequence and served its initial
65 MB resource download locally. Adjust startup and the IronSource identifier
diagnostic were suppressed; Firebase reported analytics deactivation.

The revised APK was rebuilt from the original game, privately signed and
installed over the earlier draft. Its v2 signature and 16 KB ZIP alignment
verified, and the installed APK hash matched the built artifact. Saves and
imported assets were retained; the title screen displayed the existing user ID.

Both earlier UID firewall chains were removed and the emulator uplinks were
restored. An external TCP connection under the game's actual UID succeeded.
A 90-second connected startup capture observed the launcher's GitHub DNS/TLS
connection. The previously observed `cdp.cloud.unity3d.com` and
`config.uca.cloud.unity3d.com` queries did not appear, and Firebase logged
analytics deactivation. Adjust startup and the IronSource identifier diagnostic
were not observed. This short capture is not proof about every later game path
or requests that could use cached DNS information.

The capture also included `graph.facebook.com` and Firebase installation-service
traffic. Firebase Messaging initialization is deliberately preserved. Facebook
SDK settings caches were present, but the encrypted Graph requests were not
decrypted or classified. Do not claim that all Facebook traffic or every
possible telemetry path has been eliminated. No endpoint-wide Facebook ban or
blanket external-network block was added.

Movement, battles, later content, notification delivery and the local rewarded
video replacement have not been fully validated. The PR remains a draft.
Windows mouse automation failed to initialize in this environment; no complete
gameplay-control baseline was established.

No game files, signing secrets or saves are uploaded with the source/CI artifacts.
