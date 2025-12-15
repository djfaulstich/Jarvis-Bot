'''
Name: Resource Utils
Type: Function
User: Bot
Last Updated: 2025-12-06
Function: Ensure default resource types exist.
'''

from sqlalchemy import select
from ..models import ResourceType

DEFAULT_RESOURCES = [
    ("money", "Money"),
    ("tech_points", "Tech Points"),
]

def ensure_default_resources(session) -> None:
    existing = {r.key: r for r in session.scalars(select(ResourceType)).all()}
    for key, display_name in DEFAULT_RESOURCES:
        if key not in existing:
            session.add(ResourceType(key=key, display_name=display_name, is_active=True))
    session.commit()
