from pydantic import ValidationError
import pytest

from app.api.routes.account import ResetPasswordIn, TokenIn, _dev_token
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
