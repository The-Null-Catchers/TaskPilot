import json
import logging
import sys
from contextvars import ContextVar
from datetime import UTC, datetime
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

from app.core.config import settings

request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)

HTTP_REQUESTS = Counter(
    "taskpilot_http_requests_total",
    "HTTP requests handled by the TaskPilot API.",
    ("method", "route", "status"),
)
HTTP_LATENCY = Histogram(
    "taskpilot_http_request_duration_seconds",
    "HTTP request latency for the TaskPilot API.",
    ("method", "route"),
)
REALTIME_FAILURES = Counter(
    "taskpilot_realtime_failures_total",
    "Realtime transport failures.",
    ("operation",),
)
WEBSOCKET_CONNECTIONS = Gauge(
    "taskpilot_websocket_connections",
    "Currently authenticated workspace WebSocket connections.",
)


_SAFE_EXTRA_FIELDS = (
    "event",
    "request_id",
    "method",
    "path",
    "route",
    "status",
    "duration_ms",
    "workspace_id",
    "task_id",
    "task_name",
    "operation",
)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        correlation_id = getattr(record, "request_id", None) or request_id_var.get()
        if correlation_id:
            payload["request_id"] = correlation_id
        for field in _SAFE_EXTRA_FIELDS:
            value = getattr(record, field, None)
            if value is not None and field != "request_id":
                payload[field] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_logging() -> None:
    root = logging.getLogger()
    root.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    if settings.log_json:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root.handlers.clear()
    root.addHandler(handler)


def report_exception(
    logger: logging.Logger,
    message: str,
    *,
    exc_info: bool = True,
    **context: Any,
) -> None:
    safe_context = {key: value for key, value in context.items() if key in _SAFE_EXTRA_FIELDS}
    logger.error(message, exc_info=exc_info, extra=safe_context)
