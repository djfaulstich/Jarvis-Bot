"""
Name: Bot Main
Type: Function
User: Bot
Last Updated: 2026-02-21
Function: Entry point for the Discord bot with slash commands and SQLite-backed storage.
"""

import logging

import discord
from discord.ext import commands

from . import models  # noqa: F401 - ensure model registration with SQLAlchemy metadata
from .config import DISCORD_TOKEN
from .db import Base, SessionLocal, engine
from .utils.resources import ensure_default_resources


def init_db():
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        ensure_default_resources(session)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False

        super().__init__(
            command_prefix="!",
            intents=intents,
            application_id=None,
        )

    async def setup_hook(self):
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.tag")
        await self.load_extension("bot.cogs.videos")
        await self.load_extension("bot.cogs.players")
        await self.load_extension("bot.cogs.blackjack")
        await self.load_extension("bot.cogs.slots")
        await self.load_extension("bot.cogs.resources_admin")

        try:
            synced = await self.tree.sync()
            logger.info("Synced %s global app commands.", len(synced))
        except Exception as e:
            logger.exception("Failed to sync commands:", exc_info=e)

    async def on_ready(self):
        logger.info("Logged in as %s (ID: %s)", self.user, self.user.id)
        logger.info("------")


def main():
    init_db()
    bot = MyBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
