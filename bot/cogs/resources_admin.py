'''
Name: Resources Admin Cog
Type: Cog
User: Bot
Last Updated: 2025-12-17
Function: Admin commands to add/remove/list dynamic resource types.
'''

import re
import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import select

from bot.db import SessionLocal
from bot.models.resource_type import ResourceType


KEY_RE = re.compile(r"^[a-z][a-z0-9_]{1,49}$")  # 2-50 chars, snake_case


class ResourcesAdmin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="add_resource_type",
        description="Add (or re-activate) a resource type by key + display name.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(
        key="Internal key (snake_case), e.g. money, tech_points, oil",
        display_name="Human name, e.g. Money, Tech Points, Oil",
    )
    async def add_resource_type(
        self,
        interaction: discord.Interaction,
        key: str,
        display_name: str,
    ):
        key = key.strip().lower()

        if not KEY_RE.match(key):
            await interaction.response.send_message(
                "Invalid key. Use snake_case like `money`, `tech_points`, `rare_metal` (letters/numbers/_).",
                ephemeral=True,
            )
            return

        display_name = display_name.strip()
        if not display_name:
            await interaction.response.send_message("Display name cannot be empty.", ephemeral=True)
            return

        with SessionLocal() as session:
            existing = session.execute(
                select(ResourceType).where(ResourceType.key == key)
            ).scalar_one_or_none()

            if existing:
                existing.display_name = display_name
                existing.is_active = True
                created = False
            else:
                session.add(ResourceType(key=key, display_name=display_name, is_active=True))
                created = True

            session.commit()

        await interaction.response.send_message(
            f"✅ {'Created' if created else 'Updated'} resource type: **{key}** → **{display_name}**",
            ephemeral=False,
        )

    @app_commands.command(
        name="remove_resource_type",
        description="Disable a resource type (keeps history in DB).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    @app_commands.describe(key="Resource key to disable.")
    async def remove_resource_type(self, interaction: discord.Interaction, key: str):
        key = key.strip().lower()

        with SessionLocal() as session:
            rt = session.execute(
                select(ResourceType).where(ResourceType.key == key)
            ).scalar_one_or_none()

            if not rt:
                await interaction.response.send_message("Resource type not found.", ephemeral=True)
                return

            rt.is_active = False
            session.commit()

        await interaction.response.send_message(f"🗑️ Disabled resource type: **{key}**", ephemeral=False)

    @app_commands.command(
        name="list_resource_types",
        description="List all active resource types.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def list_resource_types(self, interaction: discord.Interaction):
        with SessionLocal() as session:
            rows = session.execute(
                select(ResourceType).where(ResourceType.is_active == True).order_by(ResourceType.key.asc())
            ).scalars().all()

        if not rows:
            await interaction.response.send_message("No active resource types found.", ephemeral=True)
            return

        text = "\n".join([f"- **{r.key}** → {r.display_name}" for r in rows])
        await interaction.response.send_message(text, ephemeral=False)


async def setup(bot: commands.Bot):
    await bot.add_cog(ResourcesAdmin(bot))
