import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def validate_idempotency_key(value: str | None) -> str | None:
    if value is not None and not _KEY_PATTERN.fullmatch(value):
        raise HTTPException(status_code=400, detail="Invalid Idempotency-Key header")
    return value


def matches_last_mutation(
    resource: Any,
    expected_version: int,
    mutation_id: str | None,
    values: dict[str, Any],
) -> bool:
    return bool(
        mutation_id
        and getattr(resource, "last_mutation_id", None) == mutation_id
        and getattr(resource, "version", None) == expected_version + 1
        and all(getattr(resource, field, None) == value for field, value in values.items())
    )


async def add_idempotent(
    db: AsyncSession,
    model: type[Any],
    instance: Any,
    filters: list[Any],
    expected_values: dict[str, Any],
    mutation_id: str | None,
) -> tuple[Any, bool]:
    if mutation_id is None:
        db.add(instance)
        await db.flush()
        return instance, True

    async def existing_record():
        return await db.scalar(select(model).where(*filters))

    def validate_existing(existing: Any) -> Any:
        if any(getattr(existing, field, None) != value for field, value in expected_values.items()):
            raise HTTPException(
                status_code=409,
                detail="Idempotency key was already used for a different mutation.",
            )
        return existing

    existing = await existing_record()
    if existing is not None:
        return validate_existing(existing), False

    try:
        async with db.begin_nested():
            db.add(instance)
            await db.flush()
    except IntegrityError:
        existing = await existing_record()
        if existing is None:
            raise
        return validate_existing(existing), False

    return instance, True
