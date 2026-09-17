from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.productivity_schemas import CustomFieldCreate, SavedViewCreate, TimeEntryManual


def test_dropdown_custom_field_requires_options():
    with pytest.raises(ValidationError):
        CustomFieldCreate(name='Sprint', field_type='dropdown')

    field = CustomFieldCreate(
        name='Sprint',
        field_type='dropdown',
        options=['Sprint 1', 'Sprint 2'],
    )
    assert field.options == ['Sprint 1', 'Sprint 2']


def test_non_dropdown_custom_field_rejects_options():
    with pytest.raises(ValidationError):
        CustomFieldCreate(
            name='Story Points',
            field_type='number',
            options=['1', '2'],
        )


def test_manual_time_entry_requires_forward_time_range():
    started_at = datetime.now(UTC)
    with pytest.raises(ValidationError):
        TimeEntryManual(
            started_at=started_at,
            ended_at=started_at - timedelta(minutes=1),
        )

    entry = TimeEntryManual(
        started_at=started_at,
        ended_at=started_at + timedelta(minutes=15),
        note='Pairing session',
    )
    assert entry.ended_at > entry.started_at


def test_saved_view_has_productivity_defaults():
    view = SavedViewCreate(
        workspace_id=uuid4(),
        name='My critical tasks',
        filters={'priority': 'high'},
    )
    assert view.sort_by == 'updated_at'
    assert view.sort_direction == 'desc'
    assert view.display_mode == 'list'
