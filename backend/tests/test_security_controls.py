from app.security_controls import rate_limit_key


def test_rate_limit_key_does_not_expose_subject() -> None:
    key = rate_limit_key("login", "203.0.113.5:user@example.com")
    assert key.startswith("taskpilot:rate:login:")
    assert "203.0.113.5" not in key
    assert "user@example.com" not in key


def test_rate_limit_key_is_stable_and_bucket_scoped() -> None:
    first = rate_limit_key("login", "same")
    second = rate_limit_key("login", "same")
    other = rate_limit_key("upload", "same")
    assert first == second
    assert first != other
