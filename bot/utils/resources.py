'''
Name: Resource Utils
Type: Function
User: Bot
Last Updated: 2026-02-21
Function: Manage dynamic resource types from the SQLite database.
'''

from __future__ import annotations

from sqlalchemy import select

from ..models import ResourceType


DEFAULT_RESOURCES = [
    ("money", "Money"),
    ("tech_points", "Tech Points"),
]


def ensure_default_resources(session) -> None:
    """Seed baseline resources once, while keeping everything DB-driven."""
    existing = {r.key: r for r in session.scalars(select(ResourceType)).all()}

    changed = False
    for key, display_name in DEFAULT_RESOURCES:
        if key not in existing:
            session.add(ResourceType(key=key, display_name=display_name, is_active=True))
            changed = True

    if changed:
        session.commit()


def list_active_resource_types(session) -> list[ResourceType]:
    """Return all active resource categories ordered by key."""
    return session.scalars(
        select(ResourceType)
        .where(ResourceType.is_active == True)
        .order_by(ResourceType.key.asc())
    ).all()
