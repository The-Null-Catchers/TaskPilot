# Oracle VPS deployment

This runbook deploys TaskPilot on a shared Oracle VPS without exposing PostgreSQL, Redis, or MinIO directly to the public internet. It reuses the existing production Compose stack and a host-level Caddy instance.

## Port allocation

The Oracle template intentionally avoids the repository defaults so TaskPilot can coexist with other applications:

- Web: `127.0.0.1:3200`
- API: `127.0.0.1:8200`
- MinIO API: `127.0.0.1:9200`
- MinIO console: `127.0.0.1:9201` (do not proxy publicly)

The deployment helper refuses to start if any of these ports are already in use. PostgreSQL and Redis remain internal Docker services and are never published on the host.

## 1. Clone and prepare

```bash
cd ~
git clone https://github.com/The-Null-Catchers/TaskPilot.git
cd TaskPilot
cp .env.oracle.example .env
chmod 600 .env
```

Edit `.env` and replace every placeholder/blank secret. At minimum configure:

- `POSTGRES_PASSWORD`
- `DATABASE_URL` with the same PostgreSQL password
- `JWT_SECRET`
- `NOTIFICATION_SECRET`
- `INTEGRATION_SECRET`
- `MINIO_ROOT_USER`
- `MINIO_ROOT_PASSWORD`
- `STORAGE_KEY`
- `STORAGE_SECRET`
- `APP_URL`, `API_URL`, `NEXT_PUBLIC_API_URL`, `CORS_ORIGINS`
- `STORAGE_PUBLIC_ENDPOINT`

Generate independent secrets, for example:

```bash
openssl rand -hex 32
```

Do not reuse secrets between fields.

## 2. DNS

Create DNS records for three public names pointing at the Oracle VPS:

- web origin, e.g. `taskpilot.example.com`
- API origin, e.g. `api.taskpilot.example.com`
- attachment origin, e.g. `files.taskpilot.example.com`

Only Caddy should listen publicly on ports 80/443.

## 3. Shared Caddy routes

Append equivalent routes to the existing host Caddyfile, replacing the domains with the real values from `.env`:

```caddyfile
taskpilot.example.com {
    reverse_proxy 127.0.0.1:3200
}

api.taskpilot.example.com {
    reverse_proxy 127.0.0.1:8200
}

files.taskpilot.example.com {
    reverse_proxy 127.0.0.1:9200
}
```

Do **not** expose `9201`; that is the MinIO administrative console.

Validate and reload Caddy using the method already used by the host. For a system package installation this is typically:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

If Caddy itself runs in Docker, validate/reload it through that existing container instead of creating a second Caddy instance.

## 4. Preflight

Before deployment, verify the chosen loopback ports are unused:

```bash
sudo ss -ltnp | grep -E ':(3200|8200|9200|9201)\b' || true
```

The deployment helper performs the same check and refuses to overwrite an existing listener.

## 5. Deploy

```bash
cd ~/TaskPilot
chmod +x deploy/oracle-deploy.sh
./deploy/oracle-deploy.sh
```

The helper:

1. requires `BIND_HOST=127.0.0.1`
2. rejects missing required secrets and placeholder database credentials
3. refuses to deploy if a TaskPilot host port is already occupied
4. validates the production Compose configuration
5. builds the production API and web images
6. starts PostgreSQL, Redis, MinIO, migrations, API, web, one worker, and one Beat
7. waits for `/health/ready`
8. verifies all expected long-running services are running
9. verifies exactly one Beat service
10. prints Worker/Beat logs for operational evidence

All containers and volumes are namespaced under the Compose project name `taskpilot` by default.

## 6. Verify locally on the host

```bash
cd ~/TaskPilot
export COMPOSE_PROJECT_NAME=taskpilot

docker compose --env-file .env -f docker-compose.prod.yml ps
curl -fsS http://127.0.0.1:8200/health/live
curl -fsS http://127.0.0.1:8200/health/ready

docker compose --env-file .env -f docker-compose.prod.yml logs --tail=200 worker beat
```

Expected release evidence:

- PostgreSQL healthy
- Redis healthy
- API ready
- web running
- one Celery worker running
- exactly one Celery Beat running
- worker logs show task execution when Beat emits a scheduled task

## 7. Verify public TLS routing

After DNS resolves and Caddy is reloaded:

```bash
curl -fsS https://api.taskpilot.example.com/health/live
curl -fsS https://api.taskpilot.example.com/health/ready
curl -I https://taskpilot.example.com
```

Do not consider the deployment validated until HTTPS works and the production origins match `.env`.

## 8. Worker/Beat evidence

Beat schedules notification dispatch, invitation delivery, webhook dispatch, deadline reminders, and notification digests. After startup, watch both services:

```bash
docker compose --env-file .env -f docker-compose.prod.yml logs -f worker beat
```

Capture evidence that:

- Beat starts once
- Beat sends a scheduled TaskPilot task
- Worker receives it
- Worker logs `worker_task_started`
- Worker logs `worker_task_finished` or a controlled failure/retry

If SMTP/push provider credentials are intentionally absent, job execution still counts as worker validation; do not claim provider delivery without provider evidence.

## 9. Security checks

Before declaring the Oracle deployment production-ready:

```bash
sudo ss -ltnp
```

Confirm:

- public listeners are limited to the intended SSH/HTTP/HTTPS services
- TaskPilot 3200/8200/9200/9201 are bound only to `127.0.0.1`
- PostgreSQL 5432 is not published on the host
- Redis 6379 is not published on the host
- MinIO console 9201 is not routed by Caddy
- CORS contains only the real web origin
- `TRUST_PROXY_HEADERS=true` is used only because API access is forced through trusted Caddy

## 10. Updating

Before applying a migration that changes important data, take a database/object backup according to `BACKUP_RESTORE_ROLLBACK.md`.

Then:

```bash
cd ~/TaskPilot
git fetch origin
git pull --ff-only origin main
./deploy/oracle-deploy.sh
```

## 11. Release validation after deployment

After Oracle is healthy:

1. run the guarded deployment smoke against the Oracle web/API domains
2. capture exact deployed Git SHA
3. verify one Worker and exactly one Beat
4. observe at least one real scheduled/background task
5. perform the safe staging backup/restore drill
6. connect the included observability stack if desired
7. update `RELEASE_EVIDENCE.md` with only evidence actually observed
