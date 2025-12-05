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

    # Simple ping command
    @app_commands.command(name="ping", description="Check if the bot is alive.")
    async def ping(self, interaction: Interaction):
        await interaction.response.send_message("Pong!", ephemeral=True)

    # Example: register a user in DB
    @app_commands.command(name="register", description="Register yourself in the bot database.")
    async def register(self, interaction: Interaction):
        user_id = interaction.user.id
        display_name = interaction.user.display_name

        with SessionLocal() as session:
            profile = session.query(UserProfile).filter_by(discord_id=user_id).first()
            if profile:
                await interaction.response.send_message(
                    f"You're already registered, {profile.display_name}! You have {profile.points} points.",
                    ephemeral=True,
                )
                return

            new_profile = UserProfile(
                discord_id=user_id,
                display_name=display_name,
                points=0,
            )
            session.add(new_profile)
            session.commit()

        await interaction.response.send_message(
            f"Registered {display_name} in the database! 🎉",
            ephemeral=True,
        )

    # Example: add points
    @app_commands.command(name="addpoints", description="Add points to yourself.")
    @app_commands.describe(amount="Number of points to add")
    async def addpoints(self, interaction: Interaction, amount: int):
        user_id = interaction.user.id

        if amount <= 0:
            await interaction.response.send_message("Amount must be positive.", ephemeral=True)
            return

        with SessionLocal() as session:
            profile = session.query(UserProfile).filter_by(discord_id=user_id).first()
            if not profile:
                await interaction.response.send_message(
                    "You are not registered yet. Use `/register` first.",
                    ephemeral=True,
                )
                return

            profile.points += amount
            session.commit()

            await interaction.response.send_message(
                f"Added {amount} points. You now have {profile.points} points.",
                ephemeral=True,
            )


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))
