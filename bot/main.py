"""
Name: Bot Main
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Entry point for the Discord bot with slash commands and DB.
"""

import logging
import discord
from discord.ext import commands
from discord import app_commands

from .config import DISCORD_TOKEN
from .db import engine, Base

from .config import DISCORD_TOKEN
from .db import engine, Base
from . import models  


def init_db():
    # Importing models above ensures they are registered with Base
    Base.metadata.create_all(bind=engine)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bot")


class MyBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False  # you can enable if you need it

        super().__init__(
            command_prefix="!",      # needed if you ever want prefix cmds
            intents=intents,
            application_id=None,     # can set your app ID if you want faster sync
        )

    async def setup_hook(self):
        # Load cogs
        await self.load_extension("bot.cogs.general")
        await self.load_extension("bot.cogs.tag")
        await self.load_extension("bot.cogs.videos")
        await self.load_extension("bot.cogs.players")

        # Sync slash commands globally (can use guild-specific first for faster dev)
        try:
            synced = await self.tree.sync()
            logger.info(f"Synced {len(synced)} global app commands.")
        except Exception as e:
            logger.exception("Failed to sync commands:", exc_info=e)

    async def on_ready(self):
        logger.info(f"Logged in as {self.user} (ID: {self.user.id})")
        logger.info("------")


def init_db():
    Base.metadata.create_all(bind=engine)

def main():
    init_db()
    bot = MyBot()
    bot.run(DISCORD_TOKEN)


if __name__ == "__main__":
    main()
