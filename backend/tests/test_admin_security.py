import pytest
from fastapi import HTTPException

from app.api.routes.admin import _require_admin
from app.models import User


def _user(*, admin: bool) -> User:
    return User(
        email="admin@example.com" if admin else "user@example.com",
        name="Admin" if admin else "User",
        password_hash="hash",
        is_admin=admin,
        is_active=True,
    )


def test_admin_guard_accepts_administrator() -> None:
    _require_admin(_user(admin=True))


def test_admin_guard_rejects_standard_user() -> None:
    with pytest.raises(HTTPException) as exc:
        _require_admin(_user(admin=False))
    assert exc.value.status_code == 403
    assert exc.value.detail == "Administrator access required"
