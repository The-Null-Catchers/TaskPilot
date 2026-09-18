# Production observability

TaskPilot exposes provider-neutral observability primitives so deployments can use self-hosted or commercial systems without coupling application logic to one vendor.

## Structured logs

Set:

```env
LOG_LEVEL=INFO
LOG_JSON=true
```

Production JSON logs contain timestamp, severity, logger, message, request correlation ID, and a small allowlist of operational fields such as normalized route, HTTP status, latency, workspace ID, worker task ID/name, and realtime operation.

Request bodies, authorization headers, refresh tokens, invitation tokens, push targets, provider credentials, and other arbitrary `extra` fields are intentionally not emitted by the JSON formatter.

TaskPilot accepts a safe incoming `X-Request-ID` or generates one and returns it in the response. The same ID is available to logs created during the request through a context variable.

Log aggregation options include Loki, Elasticsearch/OpenSearch, CloudWatch, Datadog, or another JSON-capable collector.

## Metrics

Metrics are disabled by default. Enable them only on a private/internal route or require a bearer secret:

```env
METRICS_ENABLED=true
METRICS_TOKEN=<long-random-monitoring-secret>
```

Scrape:

```text
GET /metrics
Authorization: Bearer <METRICS_TOKEN>
```

Currently exposed application metrics include:

- `taskpilot_http_requests_total` by method, normalized FastAPI route, and status
- `taskpilot_http_request_duration_seconds` by method and normalized route
- `taskpilot_websocket_connections` for authenticated active workspace sockets
- `taskpilot_realtime_failures_total` by bounded realtime operation

Normalized route templates are used instead of raw URLs to avoid high-cardinality task/workspace IDs.

Prometheus can scrape this endpoint and Grafana can visualize rates, p50/p95/p99 latency, 5xx ratios, active realtime connections, and realtime failure rates.

## Background workers

Celery logs now include:

- task ID
- task name
- start event
- completion state and duration
- failure event with exception class rather than request/payload content

Celery task events are enabled so an operations deployment can attach Flower or another Celery event consumer for failed/running job visibility. Do not expose Flower publicly without authentication and network controls.

## Error reporting

`app.observability.report_exception` is the central provider-neutral boundary for operational exception reporting. Today it writes sanitized structured logs. A deployment can bridge those events into Sentry, OpenTelemetry, or another collector without inserting vendor calls throughout domain logic.

If Sentry is added, configure it at process bootstrap and keep request bodies, authorization headers, cookies, attachment contents, notification targets, and user PII out of breadcrumbs/events unless an explicit privacy review approves them.

For OpenTelemetry, export traces/metrics at the process edge and preserve the TaskPilot `X-Request-ID` as a searchable correlation attribute.

## Recommended alerts

At minimum alert on:

- `/health/ready` failing for multiple consecutive checks
- sustained 5xx response rate
- p95 API latency exceeding the service objective
- repeated realtime publish failures
- Celery task failures or growing queue depth
- notification/webhook deliveries exhausting retries
- database/Redis/object-storage availability failures
- disk/volume capacity and PostgreSQL connection saturation

Keep `/health/live` for process liveness and `/health/ready` for dependency-aware readiness. Do not restart healthy processes solely because an optional downstream notification provider is unavailable.

## Multi-process metrics

The API production Compose can run multiple Uvicorn workers. Prometheus Python client process metrics are process-local unless multiprocess mode is configured. For a single API worker, the default endpoint is sufficient. For multiple workers, configure Prometheus multiprocess collection or scrape workers independently through the chosen process manager before treating aggregate counters as authoritative.

This limitation is intentionally documented rather than silently presenting per-process counters as cluster-wide totals.


## Deployable reference stack

A runnable Prometheus/Grafana/Loki/Alloy reference deployment now lives in [ops/observability](../ops/observability/README.md). It includes protected API scraping, PostgreSQL and Redis exporters, Celery queue-depth monitoring, Blackbox readiness probes, provisioned Grafana data sources/dashboard, Alertmanager routing, and Loki rules for worker/delivery/storage/realtime failures.

The reference stack is an example integration, not a requirement to self-host. Alert destinations and production credentials stay external to source control.
