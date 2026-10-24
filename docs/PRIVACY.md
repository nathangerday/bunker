# Android telemetry changes

This branch disables telemetry in the original Global 3.7.1 ARM64 client:

- Turn off Unity's built-in analytics and analytics startup in its serialized
  settings (two boolean bytes, guarded by whole-file hashes).
- Deactivate Firebase Analytics and automatic Crashlytics/Facebook reporting;
  remove advertising permissions, ad auto-init providers and Adjust's referrer
  receiver. Firebase initialization and messaging stay intact. Remove Facebook's
  automatic initializer to prevent its background Graph configuration fetches.
- Remove Firebase Analytics and Crashlytics component registrars while keeping
  the Messaging registrar.
- Apply 12 fingerprint-checked ARM64 patches: Unity Analytics startup,
  Crashlytics reporting, Facebook Android events, Adjust startup and the two
  IronSource initialization overloads. Unknown binaries are refused and
  reapplying the patch is safe.

Blocking IronSource initialization prevents the roulette from starting the ad
mediation system. Availability checks, video display and reward callbacks retain
their upstream code, including Bunker's existing local roulette replacement.
The local server, login/account flows, update checker and notifications are
unchanged. Removing the advertising-ID permission alone only restricts access
on Android 13 and later; it does not hide the ID on older Android versions.
No firewall or emulator configuration is part of this change. Build this branch
using the normal build instructions; these patches are not deployed to the
upstream hosted builder. Game files and private signing material stay local.

## Updates

`GAME_PATCH` is 2 because the game's library, manifest and startup data change.
Rebuild older installations from the original APK and use the same signing key
when installing over an existing app to retain its data. There is no additional
privacy-policy version field.

Update checks keep using upstream Bunker releases and still notify you. Upstream
currently uses game-patch revision 1, so its releases are offered as requiring
the web builder instead of an in-app installation. That button opens the official
builder, which does not include these telemetry changes. Rebuild from this branch
with the newer launcher and the same signing key to retain the protection and
your data. Upstream update bundles can also replace this fork's packaging tools;
automatic preservation across arbitrary upstream updates is not promised.
Compatible fork releases or upstream integration would resolve this limitation.

## Validation

The focused Python suite covers original-file guards, manifest round trips,
idempotence, compatible update packaging and untouched messaging/reward code.
Eight tests are in `test_privacy.py`; the original-APK boundary test runs locally
and is skipped in CI, where game files are unavailable.
Android build/lint passed on the separate emulator test branch (run 40134021585).
Before the two IronSource additions, the rebuilt APK was verified to contain the
10 patches with the 47 removed sites restored. A 90-second connected startup reached the existing profile's title
screen and contacted GitHub; Firebase reported analytics deactivated and Adjust
reported uninitialized. No Unity analytics DNS queries or new startup exceptions
were observed. This short test does not cover every game path.

Facebook SDK 14.1.1's remaining startup requests were intercepted locally:
`GET /v14.0/app` fetches SDK settings and `GET /v14.0/app/mobile_sdk_gk` fetches
feature flags. They carried SDK/platform information and the application's
credential, with no event payload or advertising ID observed. Removing
`FacebookInitProvider` stopped both request types in the repeat startup probe.
A subsequent 90-second connected startup of the normal APK showed no Facebook
DNS queries or TLS hostname, while GitHub remained reachable. All original game
DEX files are unchanged; the diagnostic redirect is not included in the patch.
