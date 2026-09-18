# Signed iOS releases

TaskPilot keeps the normal pull-request CI unsigned so forks and contributors do not need Apple signing credentials. Production archives use the separate `.github/workflows/ios-release.yml` manual workflow.

No certificate, provisioning profile, App Store Connect private key, or signing password should be committed to the repository.

## Required GitHub Secrets

Configure these repository or protected-environment secrets:

- `IOS_CERTIFICATE_BASE64` — base64-encoded Apple Distribution `.p12`
- `IOS_CERTIFICATE_PASSWORD` — password for that `.p12`
- `IOS_PROVISIONING_PROFILE_BASE64` — base64-encoded App Store provisioning profile matching the production bundle ID
- `APPLE_TEAM_ID` — Apple Developer Team ID

For optional TestFlight upload also configure:

- `ASC_KEY_ID` — App Store Connect API key ID
- `ASC_ISSUER_ID` — App Store Connect issuer ID
- `ASC_PRIVATE_KEY_BASE64` — base64-encoded App Store Connect `.p8` private key

Prefer GitHub environment protection for production release secrets so an authorized reviewer must approve a release job.

## Preparing secrets locally

Base64 should be emitted without extra line wrapping.

macOS examples:

```bash
base64 -i TaskPilotDistribution.p12 | pbcopy
base64 -i TaskPilot_AppStore.mobileprovision | pbcopy
base64 -i AuthKey_ABC123XYZ.p8 | pbcopy
```

On GNU/Linux:

```bash
base64 -w 0 TaskPilotDistribution.p12
base64 -w 0 TaskPilot_AppStore.mobileprovision
base64 -w 0 AuthKey_ABC123XYZ.p8
```

Store the results only in GitHub Secrets or an approved secret manager. Do not paste them into issues, PR comments, CI logs, or source files.

## Running a signed release

Open **Actions → TaskPilot iOS signed release → Run workflow**.

Provide:

- `api_url` — the public HTTPS TaskPilot API origin to compile into the app
- `bundle_id` — the exact production iOS bundle identifier covered by the provisioning profile
- `upload_testflight` — leave false to export an IPA only, or enable to upload the IPA to App Store Connect

The workflow:

1. checks out the exact commit selected for the manual run
2. generates the iOS host project without adding generated host files to source control
3. runs `flutter analyze` and `flutter test`
4. prepares Flutter iOS dependencies
5. creates an ephemeral keychain and imports the distribution certificate
6. installs only the supplied provisioning profile
7. creates a signed Xcode archive
8. exports an App Store Connect IPA
9. uploads the IPA and archive as a short-lived GitHub Actions artifact
10. optionally uploads the IPA to TestFlight with App Store Connect API-key authentication
11. removes the temporary keychain, provisioning profile, and App Store Connect key material even when the job fails

The ordinary `ci.yml` unsigned iOS release build remains the contributor gate and does not consume signing secrets.

## Apple-side prerequisites

Before the workflow can succeed:

- the bundle ID must exist as an explicit App ID in Apple Developer
- the App ID capabilities must match the app, including Push Notifications when enabled
- the distribution certificate must be valid and not revoked
- the provisioning profile must be an App Store profile for the same bundle ID and team
- App Store Connect must contain the matching app record
- the App Store Connect API key used for TestFlight must have permission to upload builds
- version/build numbers must satisfy App Store Connect requirements

Push-enabled releases must also follow [PUSH_NOTIFICATIONS.md](PUSH_NOTIFICATIONS.md).

## Rotation and revocation

When a signing certificate, provisioning profile, or App Store Connect API key is rotated:

1. create the replacement in Apple Developer / App Store Connect
2. update the corresponding GitHub Secret
3. run the signed workflow and validate the exported artifact
4. revoke the old credential after the replacement is verified

If any release credential is accidentally exposed, revoke it immediately rather than relying only on deleting the leaked value from Git history.

## Manual release validation

Before promoting a TestFlight build:

- install it on a real supported iPhone
- authenticate, refresh a session, and sign out
- create/edit/move/archive/restore tasks
- test attachments against production-like object storage
- test WebSocket reconnect after background/foreground transitions
- validate FCM/APNs notification delivery and deep links
- verify offline queued changes and conflict handling
- verify dark mode, text scaling, and small-device layouts
- confirm production API, CORS, TLS, and signed-file URLs are correct

A successful IPA export proves signing, not end-to-end production readiness.
