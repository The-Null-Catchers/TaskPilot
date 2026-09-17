from collections.abc import Iterable
from uuid import UUID

MANAGER_ROLES = {"owner", "admin"}
WRITE_ROLES = {"owner", "admin", "member"}
MEMBER_ROLES = {"owner", "admin", "member", "guest"}


def can_invite_role(actor_role: str, requested_role: str) -> bool:
    if actor_role == "owner":
        return requested_role in {"admin", "member", "guest"}
    if actor_role == "admin":
        return requested_role in {"member", "guest"}
    return False


def can_manage_member(actor_role: str, target_role: str, requested_role: str | None = None) -> bool:
    if target_role == "owner":
        return False
    if actor_role == "owner":
        return requested_role in {None, "admin", "member", "guest"}
    if actor_role == "admin":
        if target_role == "admin":
            return False
        return requested_role in {None, "member", "guest"}
    return False


def would_create_dependency_cycle(
    edges: Iterable[tuple[UUID, UUID]], blocker_id: UUID, blocked_id: UUID
) -> bool:
    if blocker_id == blocked_id:
        return True
    adjacency: dict[UUID, set[UUID]] = {}
    for source, target in edges:
        adjacency.setdefault(source, set()).add(target)
    # Adding blocker -> blocked is invalid if blocked already reaches blocker.
    stack = [blocked_id]
    seen: set[UUID] = set()
    while stack:
        current = stack.pop()
        if current == blocker_id:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(adjacency.get(current, ()))
    return False
