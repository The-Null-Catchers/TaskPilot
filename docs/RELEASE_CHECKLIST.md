# Production release checklist

Use this checklist for a TaskPilot production release. GitHub Actions should be green for the exact commit being released; local commands are useful for reproducing failures, not as a substitute for the protected CI result.

## 1. Release candidate

- [ ] Release commit is on `main`.
- [ ] No unrelated uncommitted or unreviewed work is included.
- [ ] User-visible behavior in README/release notes matches what is actually implemented.
- [ ] No secrets, certificates, provisioning profiles, Firebase credentials, private keys, or production `.env` files are committed.
- [ ] Dependency/security alerts for the release commit have been reviewed.
- [ ] A pre-release database backup exists for any migration-bearing release.
- [ ] Current Alembic revision and release commit have been recorded.

## 2. Backend

From `backend/`:

```bash
pip install '.[dev]'
ruff check app tests
pytest -q
alembic upgrade head
```

CI additionally validates a clean database through:

```bash
alembic upgrade head
alembic downgrade base
alembic upgrade head
```

Release gate:

- [ ] Ruff passes.
- [ ] pytest passes.
- [ ] Empty-database migration upgrade passes.
- [ ] CI downgrade/upgrade validation passes.
- [ ] Production backend Docker image builds.
- [ ] `/health/live` responds successfully.
- [ ] `/health/ready` confirms PostgreSQL and Redis.
- [ ] No new endpoint bypasses workspace/project authorization.
- [ ] Any new background task has visible failure/retry behavior.

Do not run `alembic downgrade base` in production. CI uses it only against a disposable database.

## 3. Web

From `web/`:

```bash
npm install
npm audit --omit=dev --audit-level=high
npm run lint
npm test
npm run typecheck
npm run build
npm run e2e
```

Release gate:

- [ ] Runtime dependency audit passes at configured severity.
- [ ] ESLint passes.
- [ ] Vitest passes.
- [ ] TypeScript typecheck passes.
- [ ] Next.js production build passes.
- [ ] Playwright real-browser E2E passes.
- [ ] Keyboard navigation remains usable for primary workflows.
- [ ] Dialog focus/Escape behavior is verified.
- [ ] Small-width layout has no blocking overflow or hidden primary actions.
- [ ] Loading, empty, permission, offline, and error states are understandable.

## 4. Flutter / Android

From `mobile/`:

```bash
flutter pub get
flutter analyze
flutter test
flutter build apk --release --dart-define=API_URL=https://api.example.com
flutter build appbundle --release --dart-define=API_URL=https://api.example.com
```

Use the real production API URL for an actual release.

Release gate:

- [ ] Flutter analyzer passes.
- [ ] Flutter tests pass.
- [ ] Release APK builds.
- [ ] Release AAB builds.
- [ ] Offline cached reads work on a physical/emulated device.
- [ ] Queued edits replay after reconnect.
- [ ] HTTP 409 conflicts are visible in Sync Center.
- [ ] Session expiry does not silently discard queued edits.
- [ ] Logout removes local credentials and revokes the registered push subscription where possible.
- [ ] Deep links from task notifications open the intended native task.

## 5. iOS

Contributor CI must pass the unsigned release build.

For a signed release, follow [IOS_RELEASE.md](IOS_RELEASE.md) and run the manual **TaskPilot iOS signed release** workflow.

Release gate:

- [ ] Unsigned iOS CI compilation passes.
- [ ] Apple Distribution certificate is valid.
- [ ] App Store provisioning profile matches the exact bundle ID.
- [ ] Signed archive succeeds.
- [ ] IPA export succeeds.
- [ ] If selected, TestFlight upload succeeds.
- [ ] TestFlight build launches on a real supported iPhone.
- [ ] Push entitlement/provider configuration is validated on-device.
- [ ] Background/foreground/terminated notification taps are validated.
- [ ] Offline/reconnect behavior is validated after app background/foreground transitions.

A successful archive proves signing only; it does not replace device-level validation.

## 6. Push and email providers

Follow [PUSH_NOTIFICATIONS.md](PUSH_NOTIFICATIONS.md).

- [ ] SMTP production credentials are configured in the secret manager.
- [ ] Workspace invitation email delivery has been tested to a real mailbox.
- [ ] FCM server credentials are configured only in deployment secrets.
- [ ] Android Firebase client config is injected during release preparation.
- [ ] APNs/App Store/Firebase iOS configuration is complete.
- [ ] Push token refresh has been exercised.
- [ ] Account switching does not leave the same device target active for the previous account.
- [ ] Logout/revocation behavior has been validated.
- [ ] Provider outage does not block core TaskPilot writes.

## 7. Infrastructure and Compose

```bash
docker compose --env-file .env -f docker-compose.prod.yml config
docker compose --env-file .env -f docker-compose.prod.yml build
```

Release gate:

- [ ] Production Compose validates.
- [ ] PostgreSQL and Redis are not publicly exposed.
- [ ] MinIO/S3 public access is limited to intended signed object flows.
- [ ] Web/API public traffic terminates TLS.
- [ ] WebSocket upgrade headers are preserved by the reverse proxy.
- [ ] `CORS_ORIGINS` contains only intended web origins.
- [ ] Default/development secrets are not accepted in production.
- [ ] `LOG_JSON=true` or equivalent structured log collection is configured.
- [ ] Uptime/readiness monitoring is configured.
- [ ] Metrics endpoint, if enabled, is private or bearer protected.
- [ ] Only one Celery Beat scheduler runs.
- [ ] Worker and Beat are both healthy for invitation/notification/webhook delivery.

## 8. Backup and rollback

Follow [BACKUP_RESTORE_ROLLBACK.md](BACKUP_RESTORE_ROLLBACK.md).

- [ ] PostgreSQL backup is complete and stored off-host.
- [ ] Object-storage backup/versioning policy is healthy.
- [ ] A recent restore drill has succeeded.
- [ ] Previous known-good application revision is identified.
- [ ] Migration compatibility with that revision is understood.
- [ ] Operators know whether incident rollback means code rollback, schema downgrade, or point-in-time data restore.

## 9. Smoke test after deployment

After the production release:

- [ ] `/health/live` is healthy.
- [ ] `/health/ready` is healthy.
- [ ] Sign in and refresh-token rotation work.
- [ ] Workspace/project navigation works.
- [ ] Create a task.
- [ ] Assign a second user.
- [ ] Add a comment/mention and verify notification.
- [ ] Move the task across columns and verify a second session updates.
- [ ] Complete, archive, and restore the task.
- [ ] Upload and download an attachment.
- [ ] Save/apply a task view.
- [ ] Verify worker-driven email/push/webhook behavior appropriate to the environment.
- [ ] Review structured logs and metrics for unexpected 5xx, latency spikes, or worker failures.

## 10. Release evidence

Record:

- Git commit SHA;
- CI run URL;
- deployed application/image version;
- Alembic revision;
- backup timestamp;
- deployment timestamp;
- smoke-test result;
- TestFlight/Play release identifiers when applicable;
- any accepted known limitation.

If a mandatory item is intentionally skipped, document why and who accepted the risk rather than marking it complete.
