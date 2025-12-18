'''
Name: Resource Autocomplete
Type: Function
User: Bot
Last Updated: 2025-12-17
Function: Provide slash-command autocomplete from ResourceType table.
'''

from __future__ import annotations

import time
import discord
from sqlalchemy import select

from bot.db import SessionLocal
from bot.models.resource_type import ResourceType

_CACHE_TTL = 15  # seconds
_cache = {"ts": 0.0, "items": []}  # items = list[(key, display_name)]


def _refresh_cache():
    with SessionLocal() as session:
        rows = session.execute(
            select(ResourceType.key, ResourceType.display_name)
            .where(ResourceType.is_active == True)
            .order_by(ResourceType.key.asc())
        ).all()
    _cache["items"] = [(k, dn) for (k, dn) in rows]
    _cache["ts"] = time.time()


def get_resource_items_cached():
    if time.time() - _cache["ts"] > _CACHE_TTL:
        _refresh_cache()
    return list(_cache["items"])


async def resource_key_autocomplete(
    interaction: discord.Interaction,
    current: str,
):
    current_l = (current or "").lower()
    items = get_resource_items_cached()

    # Show "key — Display Name" in the dropdown, but the value passed is the key
    matches = []
    for key, display_name in items:
        if current_l in key.lower() or current_l in display_name.lower():
            matches.append((key, display_name))
        if len(matches) >= 25:
            break

    return [
        discord.app_commands.Choice(name=f"{k} — {dn}", value=k)
        for (k, dn) in matches
    ]
