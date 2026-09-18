import hashlib
import logging

from fastapi import HTTPException, Request
from redis.asyncio import Redis

from app.core.config import settings

logger = logging.getLogger("taskpilot.rate_limit")


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        forwarded = request.headers.get("x-forwarded-for", "")
        if forwarded:
            first = forwarded.split(",", 1)[0].strip()
            if first:
                return first[:64]
    return (request.client.host if request.client else "unknown")[:64]


def rate_limit_key(bucket: str, subject: str) -> str:
    digest = hashlib.sha256(subject.encode()).hexdigest()
    return f"taskpilot:rate:{bucket}:{digest}"


async def enforce_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
    subject: str | None = None,
) -> None:
    identity = subject or client_ip(request)
    key = rate_limit_key(bucket, identity)
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.ttl(key)
            count, ttl = await pipe.execute()
        if int(count) == 1 or int(ttl) < 0:
            await redis.expire(key, window_seconds)
            ttl = window_seconds
        if int(count) > limit:
            raise HTTPException(
                status_code=429,
                detail="Too many requests",
                headers={"Retry-After": str(max(int(ttl), 1))},
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("Rate limiter unavailable for bucket %s", bucket)
    finally:
        await redis.aclose()
