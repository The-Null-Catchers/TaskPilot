from datetime import UTC, datetime

from app.planning_models import Milestone


def test_milestone_model_accepts_timezone_aware_due_date():
    due = datetime(2026, 10, 1, 12, 30, tzinfo=UTC)
    item = Milestone(title="Release", description="", due_date=due)
    assert item.title == "Release"
    assert item.due_date.tzinfo is UTC
