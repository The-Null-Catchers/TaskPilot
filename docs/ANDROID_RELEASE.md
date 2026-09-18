# Signed Android releases

TaskPilot keeps normal pull-request and main CI credential-free. The regular `taskpilot-android` artifact proves that the Flutter Android host can be generated, analyzed, tested, and built, but it is **not** the production distribution path.

Production Android releases use the manual `.github/workflows/android-release.yml` workflow. No keystore, Firebase client file, Play service-account credential, or signing password belongs in source control.

## Artifact types

| Artifact | Source | Signing / purpose |
| --- | --- | --- |
| `taskpilot-android` | `TaskPilot CI` | Contributor/test build. Uses generated Android host and placeholder API URL. Do not publish it to a store. |
| `taskpilot-android-production-signed` APK | `TaskPilot Android signed release` | Production-signed installable APK for controlled distribution and physical-device validation. |
| `taskpilot-android-production-signed` AAB | `TaskPilot Android signed release` | Production-signed Android App Bundle intended for Google Play. |
| Google Play internal build | Optional release-workflow upload | The signed AAB uploaded to the Play internal-testing track. |

## Required GitHub Secrets

Configure these repository or protected-environment secrets:

- `ANDROID_KEYSTORE_BASE64` — base64-encoded release JKS/keystore
- `ANDROID_KEYSTORE_PASSWORD`
- `ANDROID_KEY_ALIAS`
- `ANDROID_KEY_PASSWORD`

For Firebase Messaging on real devices also configure:

- `ANDROID_GOOGLE_SERVICES_JSON_BASE64` — base64-encoded production `google-services.json` for the exact Android application ID

For optional Google Play upload configure:

- `GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_BASE64` — base64-encoded JSON key for a Google Cloud service account granted access to the app in Play Console

Prefer a protected GitHub environment for production release secrets and require reviewer approval before the job can access them.

## Preparing secrets

GNU/Linux:

```bash
base64 -w 0 taskpilot-release.jks
base64 -w 0 google-services.json
base64 -w 0 google-play-service-account.json
```

macOS:

```bash
base64 -i taskpilot-release.jks
base64 -i google-services.json
base64 -i google-play-service-account.json
```

Store the resulting strings only in GitHub Secrets or an approved secret manager.

## Running a production Android release

Open **Actions → TaskPilot Android signed release → Run workflow** and provide:

- `api_url` — public HTTPS API origin
- `application_id` — production package/application ID registered in Firebase and Play Console
- `version_name` — human-readable version such as `1.0.0`
- `version_code` — positive integer that must increase for Play uploads
- `upload_play` — false for artifact-only release, true to upload the AAB to the Play internal track

The workflow validates inputs and required secrets, generates the Android host without committing it, creates ephemeral signing configuration, optionally injects Firebase client configuration, runs Flutter analyze/tests, builds the signed APK and AAB, verifies their signatures, uploads short-lived GitHub artifacts, optionally uploads the AAB to Play internal testing, and deletes temporary credentials even when the job fails.

## Firebase / FCM validation

A successful signed build does not prove push delivery. When push is enabled, the Firebase Android app must be registered for the exact production application ID and the injected `google-services.json` must come from that Firebase app. The backend must separately receive its FCM service-account credential.

Use the real-device matrix in [PUSH_NOTIFICATIONS.md](PUSH_NOTIFICATIONS.md) before promoting a release.

## Rotation

If the Android signing key/password, Firebase configuration, or Play service-account credential changes:

1. create/obtain the replacement
2. update the corresponding protected GitHub Secret
3. run an artifact-only signed release and verify installation/signatures
4. verify Play internal upload where relevant
5. revoke old credentials only after the replacement succeeds

If a release credential is exposed, revoke/rotate it immediately; deleting the value from Git history is not sufficient.
