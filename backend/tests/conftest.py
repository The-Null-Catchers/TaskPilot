import pytest
from httpx import ASGITransport, AsyncClient
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db import engine, get_db
from app.main import app


@pytest.fixture
async def api_client():
    async with engine.connect() as connection:
        outer = await connection.begin()
        session = AsyncSession(
            bind=connection,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )

        async def override_db():
            yield session

        app.dependency_overrides[get_db] = override_db
        try:
            async with AsyncClient(
                transport=ASGITransport(app=app),
                base_url="http://testserver",
            ) as client:
                yield client
        finally:
            app.dependency_overrides.pop(get_db, None)
            await session.close()
            await outer.rollback()
            await engine.dispose()



async def _clear_rate_limit_keys() -> None:
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    try:
        keys = [key async for key in redis.scan_iter(match="taskpilot:rate:*")]
        if keys:
            await redis.delete(*keys)
    finally:
        await redis.aclose()


@pytest.fixture(autouse=True)
async def isolate_rate_limits():
    await _clear_rate_limit_keys()
    try:
        yield
    finally:
        await _clear_rate_limit_keys()
