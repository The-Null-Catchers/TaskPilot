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

Test database and object-storage restores periodically. A backup that has never been restored is not a verified backup.

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
- WebSockets require the reverse proxy to support upgrade headers.
- Redis must be shared by all API/worker instances because it backs realtime events, Celery, and distributed rate limiting.

## 9. Production checklist

Before exposing TaskPilot publicly:

- DNS and TLS configured
- `APP_ENV=production`
- development/default secrets rejected
- CORS restricted to real origins
- reverse proxy strips/replaces forwarding headers
- database and object-storage backups configured
- SMTP configured and tested
- push credentials configured only for channels in use
- MinIO console not exposed publicly
- logs shipped to centralized storage
- error/uptime monitoring configured
- restore procedure tested
- GitHub Actions green for the exact commit being deployed
