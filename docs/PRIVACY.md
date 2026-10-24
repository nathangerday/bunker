# Android telemetry changes

This branch disables telemetry in the original Global 3.7.1 ARM64 client:

- Turn off Unity's built-in analytics and analytics startup in its serialized
  settings (two boolean bytes, guarded by whole-file hashes).
- Deactivate Firebase Analytics and automatic Crashlytics/Facebook reporting;
  remove advertising permissions, ad auto-init providers and Adjust's referrer
  receiver. Shared Firebase/Facebook initialization and messaging stay intact.
- Apply 10 fingerprint-checked ARM64 patches: Unity Analytics startup,
  Crashlytics reporting, Facebook Android events and Adjust startup. Unknown
  binaries are refused and reapplying the patch is safe.

The game, local server, update checker, notifications and IronSource ad/reward
methods retain their upstream code. No firewall or emulator configuration is
part of this change. Build this branch using the normal build instructions;
these patches are not deployed to the upstream hosted builder. Game files and
private signing material stay local.

## Updates

`GAME_PATCH` is 2 because the game's library, manifest and startup data change.
Rebuild older installations from the original APK and use the same signing key
when installing over an existing app to retain its data. There is no additional
privacy-policy version field.

Update checks keep using upstream Bunker releases. An upstream release with a
different game-patch revision requires a rebuild; its hosted builder does not
include this branch's telemetry changes. Upstream update bundles can also replace
this fork's packaging tools. Automatic preservation across arbitrary upstream
updates is therefore not promised: rebuild from this branch with the newer
launcher, use compatible fork releases, or integrate these changes upstream.

## Validation

The retained native sites and the two Unity settings bytes are checked against
the original APK; tests also check manifest round trips, idempotence, unknown
binary rejection, compatible update packaging and untouched messaging/ad code.
Connected runtime verification is being repeated after the trim. The earlier
build reached the title screen and contacted GitHub with Internet enabled, but
that does not prove this smaller patch's behavior. Facebook Graph traffic was
not classified; this is not a guarantee that every SDK connection is absent.
