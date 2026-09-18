import json
import logging
from uuid import UUID
from redis.asyncio import Redis
from redis.exceptions import RedisError
from app.core.config import settings
from app.observability import REALTIME_FAILURES, report_exception

logger = logging.getLogger(__name__)


def channel(workspace_id: UUID) -> str:
    return f"taskpilot:workspace:{workspace_id}"


async def publish(workspace_id: UUID, event: str, payload: dict) -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        await redis.publish(channel(workspace_id), json.dumps({"event": event, "payload": payload}, default=str))
    except RedisError:
        REALTIME_FAILURES.labels("publish").inc()
        report_exception(
            logger,
            "realtime_publish_failed",
            workspace_id=str(workspace_id),
            event=event,
            operation="publish",
        )
    finally:
        await redis.aclose()
