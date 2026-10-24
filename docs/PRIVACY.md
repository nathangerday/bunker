# Android privacy

Android builds disable identified analytics, crash reporting, attribution and
advertising startup paths in the original Global 3.7.1 ARM64 client. The
command-line and browser APK build paths apply the same controls.

## Scope

- Disable Unity analytics and its automatic startup in the serialized game
  settings. Whole-file hashes guard the two changed bytes.
- Deactivate Firebase Analytics, automatic Crashlytics reporting and Facebook
  event/advertising-ID collection through manifest settings. Remove analytics
  and crash-reporting component registrations, advertising permissions,
  advertising SDK startup providers and Adjust's referrer receiver.
- Remove Facebook's automatic initializer, which fetches SDK settings and
  feature flags even when automatic event logging is disabled. Explicit account
  functionality remains available.
- Apply the 12 ARM64 patches listed in
  [telemetry_patches.json](../android/tools/telemetry_patches.json): Unity
  Analytics startup, Crashlytics reporting, Facebook events, Adjust startup and
  both IronSource initialization overloads. Original instructions and executable
  mappings are checked before patching. Unsupported binaries are rejected;
  applying the controls again is safe.

IronSource initialization is blocked before it starts advertising mediation.
The existing local roulette replacement, video availability/display methods
and reward callbacks are preserved. Pre-init calls still pass the local game
user ID, consent and mediation metadata to the uninitialized Java SDK, where
these calls appear in local logs. No IronSource DNS/TLS traffic was observed in
the tested run; this does not prove that every possible connection is blocked.
Removing the advertising-ID permission only restricts access on Android 13 and
later, not on older versions.

The local server, account flows, Firebase Messaging, local notifications and
update checks retain their existing behavior. Internet access remains available;
no firewall, DNS rules or emulator configuration is required.

## Upgrading existing installations

Android game-patch revision 2 includes these controls. Upgrading from revision 1
changes the game's library, manifest and startup settings. In-app updates
preserve the installed game files, so the upgrade requires rebuilding from the
original APK and matching master data. Use the same signing key and install over the
existing app to retain its data.

The updater continues checking for releases. A different game-patch revision
requires the web builder; updates with a matching revision retain the patched
game files. See [Updating](../README.md#updating).

## Validation

The privacy tests cover binary and settings guards, manifest round trips,
idempotence, and preserved messaging, rewarded-video and reward-callback entry
points:

```sh
python3 -m unittest discover -s android/tools -p test_privacy.py
```

The boundary test uses `inputs/game-3.7.1.apk` when available and is skipped when
private game files are absent. Synthetic fixtures cover the other tests without
redistributing game code. See the [validation log](VALIDATION.md#android-privacy--2026-10-25)
for the build, roulette and network observations and their limits.
