"""
Name: General Cog
Type: Cog
User: Bot
Last Updated: 2025-12-04
Function: Provide basic slash commands and demonstrate DB usage.
"""

from discord.ext import commands
from discord import app_commands, Interaction

from ..db import SessionLocal
from ..models import UserProfile


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
