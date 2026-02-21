'''
Name: Player DB Utils
Type: Function
User: Bot
Last Updated: 2025-12-06
Function: Common DB helpers for players and their resources.
'''

import discord
from sqlalchemy import select

from ..models import Player, ResourceType, PlayerResource

def get_or_create_player(session, user: discord.abc.User) -> Player:
    player = session.scalar(select(Player).where(Player.discord_id == user.id))
    if player:
        player.name = user.display_name
        session.commit()
        return player

    player = Player(discord_id=user.id, name=user.display_name)
    session.add(player)
    session.commit()
    return player


def get_resource_amount(session, player: Player, resource_key: str) -> int:
    rtype = session.scalar(select(ResourceType).where(ResourceType.key == resource_key))
    if not rtype:
        return 0

    pr = session.scalar(
        select(PlayerResource).where(
            PlayerResource.player_id == player.id,
            PlayerResource.resource_id == rtype.id,
        )
    )
    return pr.amount if pr else 0


def adjust_resource(session, player: Player, resource_key: str, delta: int) -> int:
    rtype = session.scalar(select(ResourceType).where(ResourceType.key == resource_key))
    if not rtype:
        raise RuntimeError(f"Resource type '{resource_key}' is not defined.")

    pr = session.scalar(
        select(PlayerResource).where(
            PlayerResource.player_id == player.id,
            PlayerResource.resource_id == rtype.id,
        )
    )
    if not pr:
        pr = PlayerResource(player_id=player.id, resource_id=rtype.id, amount=0)
        session.add(pr)

    pr.amount += delta
    session.commit()
    session.refresh(pr)
    return pr.amount
