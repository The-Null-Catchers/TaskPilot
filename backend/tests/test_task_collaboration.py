from uuid import UUID, uuid4

from app.api.routes.task_collaboration import ALLOWED_REACTIONS, extract_mention_ids


def test_extract_mention_ids_deduplicates_and_ignores_invalid_values():
    first = uuid4()
    second = uuid4()
    body = f"Hello @[{first}] and @[{second}] and again @[{first}] and @[not-a-uuid]"

    assert extract_mention_ids(body) == {first, second}


def test_supported_reactions_are_small_explicit_allowlist():
    assert "👍" in ALLOWED_REACTIONS
    assert "🚀" in ALLOWED_REACTIONS
    assert "<script>" not in ALLOWED_REACTIONS
    assert all(isinstance(value, str) and value for value in ALLOWED_REACTIONS)


def test_extract_mention_ids_returns_uuid_objects():
    user_id = uuid4()
    result = extract_mention_ids(f"@[{user_id}]")

    assert result == {UUID(str(user_id))}
