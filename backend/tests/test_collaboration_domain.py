from uuid import uuid4

import pytest

from app.domain import can_invite_role, can_manage_member, would_create_dependency_cycle


@pytest.mark.parametrize(
    ("actor", "requested", "allowed"),
    [
        ("owner", "admin", True),
        ("owner", "member", True),
        ("owner", "guest", True),
        ("admin", "admin", False),
        ("admin", "member", True),
        ("admin", "guest", True),
        ("member", "guest", False),
        ("guest", "member", False),
    ],
)
def test_invitation_role_policy(actor: str, requested: str, allowed: bool) -> None:
    assert can_invite_role(actor, requested) is allowed


def test_admin_cannot_manage_another_admin() -> None:
    assert can_manage_member("admin", "admin", "member") is False
    assert can_manage_member("admin", "member", "guest") is True


def test_owner_can_manage_non_owner_roles() -> None:
    assert can_manage_member("owner", "admin", "member") is True
    assert can_manage_member("owner", "member", "admin") is True
    assert can_manage_member("owner", "owner", "admin") is False


def test_dependency_cycle_detection() -> None:
    task_a = uuid4()
    task_b = uuid4()
    task_c = uuid4()
    edges = [(task_a, task_b), (task_b, task_c)]

    assert would_create_dependency_cycle(edges, task_c, task_a) is True
    assert would_create_dependency_cycle(edges, task_a, task_c) is False
    assert would_create_dependency_cycle(edges, task_a, task_a) is True
