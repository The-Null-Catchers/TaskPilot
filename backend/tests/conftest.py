import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
