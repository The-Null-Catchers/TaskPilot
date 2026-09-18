# Push notification deployment and validation

TaskPilot supports Web Push, FCM, and APNs through provider adapters on the backend. Mobile push is optional at runtime: the Flutter app remains usable when no Firebase client configuration is bundled.

No Firebase service account, APNs private key, certificate, provisioning profile, or signing secret belongs in this repository.

## Android / FCM setup

1. Create or select the Firebase project used for the production Android app.
2. Register the Android application with the exact production package name.
3. Download the Firebase Android client configuration during release preparation and place it only in the generated Android host project or inject it in CI from an encrypted secret/artifact source.
4. Create a Firebase service account with only the permissions needed to send FCM messages.
5. Store the complete service-account JSON in the deployment secret manager and expose it to the API/worker as `FCM_SERVICE_ACCOUNT_JSON`.
6. Start the API and worker and confirm `GET /api/v1/notifications/provider-config` reports `fcm_enabled: true` for an authenticated user.
7. Install the signed Android build on a real device. Grant notification permission when Android requests it.
8. Confirm the app registers exactly one active FCM subscription for the signed-in account through `GET /api/v1/notifications/subscriptions`.
9. Trigger a TaskPilot notification such as an assignment or mention and verify delivery while the app is backgrounded.
10. Tap the notification and confirm task notifications deep-link to `/tasks/{taskId}`; other notification payloads should open the notification inbox.
11. Leave the app in the foreground and verify receiving a push does not crash, duplicate the current screen, or lose navigation state.
12. Rotate the FCM token (reinstalling the app or clearing app data is a practical test) and verify the new token becomes active.
13. Sign out and confirm the subscription is revoked server-side and the local FCM token is deleted.

The backend treats a push target as owned by only one account at a time. If the same FCM/APNs/Web Push target is registered by another account, the previous account's matching subscription is revoked. This prevents stale account sessions from continuing to receive notifications on a shared device/browser endpoint.

## iOS / APNs setup

TaskPilot's backend APNs adapter uses token-based authentication. Configure:

- `APNS_TEAM_ID`
- `APNS_KEY_ID`
- `APNS_PRIVATE_KEY`
- `APNS_BUNDLE_ID`
- `APNS_USE_SANDBOX=true` only for development/sandbox validation

For a production Flutter build:

1. Use the exact App ID / bundle identifier configured in Apple Developer and Firebase, if FCM is used as the client transport.
2. Enable Push Notifications for the App ID.
3. Enable the Remote notifications background mode when required by the release behavior.
4. Create the APNs signing key in Apple Developer and store the `.p8` material only in the deployment secret manager.
5. Ensure the provisioning profile contains the push entitlement.
6. Build/sign with the matching distribution certificate and provisioning profile.
7. Install through TestFlight or an ad-hoc/development path appropriate to the environment.
8. Validate foreground, background, terminated-app launch, deep links, token rotation, logout revocation, and account switching on a real iPhone.

If the Flutter client uses Firebase Messaging on iOS, also add the production Firebase iOS client configuration during release preparation and configure the Firebase project's APNs key/certificate according to Firebase's current setup flow. Keep those files and credentials outside source control.

## Deep-link payload contract

Backend notification deliveries include:

```json
{
  "notification_id": "<uuid>",
  "kind": "task.mention",
  "entity_type": "task",
  "entity_id": "<task uuid>",
  "url": "/app/tasks/<task uuid>"
}
```

The Flutter app routes payloads with `entity_type == "task"` and a non-empty `entity_id` to the native task detail route. Other push taps open the native notification inbox.

## Token lifecycle expectations

Automated coverage verifies:

- registering the same target repeatedly for one account is idempotent
- the same target cannot remain active for two accounts
- explicit subscription deletion marks the subscription revoked
- provider adapters fail closed/skip cleanly when credentials are absent
- provider-invalid/gone subscriptions can be revoked by delivery handling

Manual device validation must still cover provider-issued token refresh events because CI does not have access to production Firebase/APNs credentials or physical devices.

## Failure validation

Before launch, intentionally test:

- invalid/revoked FCM credential
- invalid APNs key or bundle ID
- network outage between worker and provider
- provider returning a stale/unregistered token
- Celery worker stopped while notifications accumulate

Expected behavior: TaskPilot records delivery failure/retry state, does not block core task operations, and does not expose provider credentials or raw device tokens in logs.

## Secret handling

Recommended locations are GitHub Actions encrypted secrets for release-only material and a production secret manager for runtime provider credentials. Never place provider keys in `.env.example`, mobile source files, Docker images, screenshots, CI logs, or test fixtures.
