# TaskPilot observability stack

This directory turns TaskPilot's existing provider-neutral telemetry into a runnable reference monitoring stack. It is intentionally separate from the application architecture: the API keeps exposing protected Prometheus metrics and JSON logs, while collectors can be replaced by a managed platform later.

## What it runs

- Prometheus for TaskPilot/API, PostgreSQL, Redis, queue, and probe metrics
- Blackbox Exporter for API liveness/readiness and MinIO readiness
- PostgreSQL Exporter
- Redis Exporter, including the Celery broker queue length for the fixed `celery` key
- Loki for operational logs and log-based alert rules
- Grafana Alloy for Docker log discovery/forwarding
- Alertmanager for alert routing
- Grafana with provisioned Prometheus/Loki data sources and a TaskPilot overview dashboard

Monitoring UIs bind to loopback only. Put authentication/TLS in front of them before any remote access; do not publish Prometheus, Loki, Alertmanager, or Grafana directly to the internet.

## Prerequisites

In the production TaskPilot environment set:

```env
METRICS_ENABLED=true
METRICS_TOKEN=<long-random-monitoring-token>
GRAFANA_ADMIN_PASSWORD=<strong-separate-password>
```

Create the Prometheus credential file from the same metrics token:

```bash
mkdir -p ops/observability/secrets
printf '%s' "$METRICS_TOKEN" > ops/observability/secrets/metrics_token
chmod 600 ops/observability/secrets/metrics_token
```

The directory is gitignored. Never commit this file.

The PostgreSQL exporter reuses `POSTGRES_USER` and `POSTGRES_PASSWORD` from the deployment environment. For a hardened deployment, create a dedicated read-only monitoring database role and supply that credential instead.

## Start

Run the application and monitoring extension as one Compose project so internal DNS names such as `api`, `postgres`, `redis`, and `minio` resolve:

```bash
docker compose \
  -f docker-compose.prod.yml \
  -f ops/observability/docker-compose.observability.yml \
  up -d
```

Local operator endpoints:

- Grafana: `http://127.0.0.1:3001`
- Prometheus: `http://127.0.0.1:9090`
- Alertmanager: `http://127.0.0.1:9093`
- Loki: `http://127.0.0.1:3100`

The provisioned Grafana folder contains **TaskPilot Production Overview** with request rate, 5xx rate, p95 latency, WebSocket connections, PostgreSQL/Redis status, Celery queue size, MinIO readiness, and application logs.

## Alert coverage

Prometheus rules cover:

- `/health/ready` failure
- sustained 5xx ratio
- high API p95 latency
- PostgreSQL failure
- Redis failure
- MinIO readiness failure
- Celery queue backlog
- sustained realtime failure metrics

Loki rules cover:

- Celery task failure events
- notification delivery retry exhaustion
- webhook delivery retry exhaustion
- repeated storage-operation failures
- WebSocket realtime failure events

Thresholds are production starting points, not universal SLOs. Tune them after observing normal workload. The queue threshold deliberately watches one known Celery list key instead of scanning arbitrary Redis keys.

## Alert delivery is intentionally manual

The committed Alertmanager configuration has a no-op receiver. Before relying on alerts, configure an approved receiver such as email, Slack, PagerDuty, Opsgenie, or a controlled webhook. Credentials for that receiver belong in runtime secrets, not git.

Use a private network, reverse proxy, VPN, or managed ingress for operator access. The application `/metrics` endpoint still requires its bearer token and must not be exposed publicly.

## Log privacy

Alloy only keeps TaskPilot Compose services relevant to operations. The application JSON formatter uses an allowlist. Do not add request bodies, authorization headers, cookies, refresh/invitation tokens, push targets, attachment content, webhook secrets, SMTP credentials, or storage credentials to labels/log fields.

Docker socket access is read-only but still security-sensitive. On a hardened orchestrator, prefer the platform-native log source or a socket proxy with the minimum required permissions.

## Managed-service migration

This reference stack is not a requirement to self-host monitoring. The same signals can be routed to Grafana Cloud, Datadog, Sentry, OpenTelemetry collectors, CloudWatch, or another provider. Preserve the bounded labels, request IDs, sanitization rules, and protected metrics endpoint when switching collectors.
