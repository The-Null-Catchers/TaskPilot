#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

ENV_FILE="${ENV_FILE:-.env}"
COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-taskpilot}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "Missing $ENV_FILE. Copy .env.oracle.example to .env and fill required values." >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ "${BIND_HOST:-}" != "127.0.0.1" ]]; then
  echo "Refusing deployment: BIND_HOST must remain 127.0.0.1 on the shared Oracle VPS." >&2
  exit 1
fi

for value in POSTGRES_PASSWORD JWT_SECRET NOTIFICATION_SECRET INTEGRATION_SECRET MINIO_ROOT_USER MINIO_ROOT_PASSWORD STORAGE_KEY STORAGE_SECRET; do
  if [[ -z "${!value:-}" ]]; then
    echo "Refusing deployment: $value is empty." >&2
    exit 1
  fi
done

if [[ "${DATABASE_URL:-}" == *"CHANGE_ME"* ]]; then
  echo "Refusing deployment: DATABASE_URL still contains CHANGE_ME." >&2
  exit 1
fi

for port in "${WEB_PORT:-3200}" "${API_PORT:-8200}" "${MINIO_API_PORT:-9200}" "${MINIO_CONSOLE_PORT:-9201}"; do
  if ss -H -ltn "sport = :$port" | grep -q .; then
    echo "Refusing deployment: TCP port $port is already in use." >&2
    exit 1
  fi
done

compose=(docker compose --project-name "$PROJECT_NAME" --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

printf '\n==> Validating Compose configuration\n'
"${compose[@]}" config >/dev/null

printf '\n==> Building production images\n'
"${compose[@]}" build

printf '\n==> Starting TaskPilot\n'
"${compose[@]}" up -d

printf '\n==> Waiting for API readiness\n'
api_port="${API_PORT:-8200}"
for _ in {1..60}; do
  if curl -fsS "http://127.0.0.1:${api_port}/health/ready" >/tmp/taskpilot-health.json 2>/dev/null; then
    cat /tmp/taskpilot-health.json
    echo
    break
  fi
  sleep 2
done

if ! curl -fsS "http://127.0.0.1:${api_port}/health/ready" >/tmp/taskpilot-health.json; then
  echo "API readiness check failed." >&2
  "${compose[@]}" ps
  "${compose[@]}" logs --tail=120 backend worker beat
  exit 1
fi

running_services="$(${compose[@]} ps --status running --services)"
for svc in backend web worker beat postgres redis minio; do
  if ! grep -qx "$svc" <<<"$running_services"; then
    echo "Expected service '$svc' is not running." >&2
    "${compose[@]}" ps
    exit 1
  fi
done

beat_count="$(${compose[@]} ps --status running --services beat | wc -l | tr -d ' ')"
if [[ "$beat_count" != "1" ]]; then
  echo "Expected exactly one running Beat service, found $beat_count." >&2
  exit 1
fi

printf '\n==> Deployment healthy\n'
"${compose[@]}" ps
printf '\nWorker/Beat tail:\n'
"${compose[@]}" logs --tail=80 worker beat
