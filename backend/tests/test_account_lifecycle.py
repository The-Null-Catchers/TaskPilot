from pydantic import ValidationError
import pytest

from app.api.routes.account import ProfileUpdateIn, ResetPasswordIn, TokenIn, _dev_token
from app.core import config
from app.core.security import token_digest


def test_account_tokens_are_hashed_before_storage():
    raw = "sensitive-reset-token-value"
    digest = token_digest(raw)
    assert digest != raw
    assert len(digest) == 64
    assert digest == token_digest(raw)
    assert digest != token_digest(raw + "-different")


def test_reset_password_requires_strong_password_and_nontrivial_token():
    with pytest.raises(ValidationError):
        ResetPasswordIn(token="short", password="short")
    with pytest.raises(ValidationError):
        TokenIn(token="too-short")


def test_development_tokens_are_never_returned_in_production(monkeypatch):
    monkeypatch.setattr(config.settings, "app_env", "production")
    assert _dev_token("raw-token") == {}
    monkeypatch.setattr(config.settings, "app_env", "development")
    assert _dev_token("raw-token") == {"development_token": "raw-token"}


def test_profile_input_normalizes_safe_identity_fields():
    profile = ProfileUpdateIn(
        name="  Mohammed Emad  ",
        username="Mohammed.Emad",
        avatar_url="https://example.com/avatar.png",
        job_title="  Software Engineer  ",
        bio="TaskPilot builder",
        timezone="Asia/Hebron",
        language="en-us",
    )
    assert profile.name == "Mohammed Emad"
    assert profile.username == "mohammed.emad"
    assert profile.job_title == "Software Engineer"
    assert profile.language == "en-US"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("timezone", "Mars/Olympus"),
        ("avatar_url", "javascript:alert(1)"),
        ("name", "   "),
    ],
)
def test_profile_input_rejects_unsafe_or_invalid_values(field, value):
    data = {
        "name": "Task Pilot",
        "username": "task.pilot",
        "avatar_url": "https://example.com/avatar.png",
        "job_title": "Engineer",
        "bio": "",
        "timezone": "UTC",
        "language": "en",
    }
    data[field] = value
    with pytest.raises(ValidationError):
        ProfileUpdateIn(**data)
