import pytest

from app.core import config
from app.demo_seed import DEFAULT_PASSWORD, DEMO_EMAILS, seed


def test_demo_seed_defaults_are_explicitly_local_only():
    assert len(DEMO_EMAILS) == 3
    assert all(email.endswith("@taskpilot.local") for email in DEMO_EMAILS)
    assert len(DEFAULT_PASSWORD) >= 10


@pytest.mark.asyncio
async def test_demo_seed_refuses_production(monkeypatch):
    monkeypatch.setattr(config.settings, "app_env", "production")
    with pytest.raises(SystemExit, match="Refusing to seed demo data"):
        await seed(reset=False)
