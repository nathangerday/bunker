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

## Runtime scope

The previous build rendered the title/opening sequence and served its initial
65 MB resource download locally. Adjust startup and the IronSource identifier
diagnostic were suppressed; Firebase reported analytics deactivation.

That build still attempted native Unity analytics connections. The revised
Unity startup-settings patch addresses their initialization directly. Fresh
runtime verification is required before claiming those requests have stopped.

Movement, battles, later content, notification delivery and the local rewarded
video replacement have not been fully validated. The PR remains a draft.
Windows mouse automation failed to initialize in this environment; no complete
gameplay-control baseline was established.

No game files, signing secrets or saves are uploaded with the source/CI artifacts.
