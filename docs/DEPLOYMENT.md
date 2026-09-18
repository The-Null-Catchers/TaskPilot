# Production deployment

TaskPilot ships with a separate production Compose stack in `docker-compose.prod.yml`. It is intentionally different from the local development stack: no source-code bind mounts, no auto-reload, non-root application containers, persistent Redis, one-shot migrations, health-gated startup, and loopback-only host bindings by default.

## 1. Prepare environment

Copy the production template and replace every blank or placeholder secret:

```bash
cp .env.production.example .env
```

At minimum set strong values for:

- `POSTGRES_PASSWORD`
- `JWT_SECRET`
- `NOTIFICATION_SECRET`
- `INTEGRATION_SECRET`
- `MINIO_ROOT_USER` / `MINIO_ROOT_PASSWORD`
- `STORAGE_KEY` / `STORAGE_SECRET`
- real `APP_URL`, `API_URL`, `NEXT_PUBLIC_API_URL`, and `CORS_ORIGINS`

For production email/invitation delivery also configure `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, and credentials when required by the provider. Workspace invitations remain usable through their one-time secure link when SMTP is absent, but automatic invitation email delivery will stay pending.

Use independent random secrets; do not reuse the JWT, notification, integration, database, or storage credentials.

`TRUST_PROXY_HEADERS=true` should only be enabled when the API is reachable exclusively through a reverse proxy that overwrites untrusted forwarding headers.

## 2. TLS and public routing

The production Compose file binds web, API, and MinIO ports to `127.0.0.1` by default. Put a TLS-terminating reverse proxy or managed load balancer in front of them.

Suggested routing:

- `https://taskpilot.example.com` -> `127.0.0.1:3000`
- `https://api.taskpilot.example.com` -> `127.0.0.1:8000`
- `https://files.taskpilot.example.com` -> `127.0.0.1:9000`

PostgreSQL and Redis are not published to the host.

If MinIO is replaced by managed S3-compatible storage, remove the MinIO service and point the storage variables at the managed endpoint.

## 3. Validate configuration

Before starting services:

```bash
docker compose --env-file .env -f docker-compose.prod.yml config
```

This catches missing required Compose variables.

## 4. Build and start

```bash
docker compose --env-file .env -f docker-compose.prod.yml build
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

The `migrate` service runs `alembic upgrade head` once. API, Celery worker, and Celery Beat only start after migrations complete successfully. The web service waits for the API health check.

## 5. Verify

```bash
curl -fsS http://127.0.0.1:8000/health
docker compose --env-file .env -f docker-compose.prod.yml ps
docker compose --env-file .env -f docker-compose.prod.yml logs --tail=200 backend worker beat web
```

The public API should only be considered ready after PostgreSQL and Redis report healthy through `/health`.

## 6. Backups

Back up at least:

- PostgreSQL database
- MinIO/S3 attachment objects
- secrets and environment configuration in your secret manager

Redis is configured with append-only persistence in the production Compose stack, but it should not be treated as the source of truth for application data.

Test database and object-storage restores periodically. A backup that has never been restored is not a verified backup. The exact backup, restore-drill, data-restore, and rollback procedures are in [BACKUP_RESTORE_ROLLBACK.md](BACKUP_RESTORE_ROLLBACK.md).

## 7. Updating

Use a database backup before migrations that change production data.

```bash
git pull --ff-only
docker compose --env-file .env -f docker-compose.prod.yml build
docker compose --env-file .env -f docker-compose.prod.yml up -d
```

Compose recreates changed services. The migration service runs before the API and workers.

## 8. Scaling notes

- Increase `WEB_CONCURRENCY` for API workers only after measuring database connection pressure.
- Increase `CELERY_CONCURRENCY` independently for background workloads.
- Run only one Celery Beat instance.
- For multi-host deployment, move PostgreSQL, Redis, and object storage to durable managed services or dedicated clustered infrastructure.
- WebSockets require the reverse proxy to support upgrade headers. The workspace socket URL contains no access token; clients connect first and immediately send an authentication JSON frame. Avoid proxy rules that buffer or strip initial WebSocket client messages.
- Redis must be shared by all API/worker instances because it backs realtime events, Celery, and distributed rate limiting.


## 10. Push notification deployment

Backend push delivery is provider-driven and secret-free by default. Configure only the providers you actually use:

- Web Push: `WEBPUSH_VAPID_PRIVATE_KEY`, `WEBPUSH_VAPID_PUBLIC_KEY`, `WEBPUSH_VAPID_SUBJECT`
- FCM: `FCM_SERVICE_ACCOUNT_JSON`
- APNs: `APNS_TEAM_ID`, `APNS_KEY_ID`, `APNS_PRIVATE_KEY`, `APNS_BUNDLE_ID`, and `APNS_USE_SANDBOX` as appropriate

Flutter FCM registration is runtime-optional. The mobile binary also needs the platform Firebase client configuration generated for your Firebase project. Keep deployment-specific Firebase configuration and signing credentials outside source control and inject/copy them as part of your release pipeline.

Validate push on real devices before enabling it as a promised production channel. Server credentials being present does not prove that Android/iOS client entitlement and provider routing are correct.

## 11. Invitation email delivery

Workspace invitations are created synchronously but delivered asynchronously by Celery Beat/worker. The worker reads an encrypted one-time delivery token from PostgreSQL, attempts SMTP delivery, records delivery status/retries, and clears the encrypted copy after a successful send.

Operational implications:

- worker and Beat must both be running for automatic invitation email delivery
- `APP_URL` must be the public web origin so emailed invitation links resolve correctly
- SMTP failures can be inspected through invitation delivery state without exposing raw invitation tokens in logs
- the creation response still returns the one-time secure invitation link so administrators are not blocked by a temporary SMTP outage

## 12. Production checklist

Before exposing TaskPilot publicly:

- DNS and TLS configured
- `APP_ENV=production`
- development/default secrets rejected
- CORS restricted to real origins
- reverse proxy strips/replaces forwarding headers
- database and object-storage backups configured
- SMTP configured and tested
- push credentials configured only for channels in use
- Flutter Firebase/APNs platform configuration included in signed release builds when mobile push is enabled
- SMTP invitation delivery tested from worker to a real mailbox
- MinIO console not exposed publicly
- logs shipped to centralized storage
- error/uptime monitoring configured
- restore procedure tested
- GitHub Actions green for the exact commit being deployed
