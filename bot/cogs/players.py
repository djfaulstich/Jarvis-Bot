'''
Name: Players Cog
Type: Cog
User: Bot
Last Updated: 2025-12-06
Function: Manage UN Sim players and their resources (money, tech points).
'''


import io
from sqlalchemy import select

import discord
from discord.ext import commands
from discord import app_commands

from ..db import SessionLocal
from ..models import ResourceType, Player  # Player used for balances queries
from ..utils.amounts import parse_amount_with_suffix, format_amount_with_suffix
from ..utils.players import get_or_create_player, adjust_resource, get_resource_amount


class PlayersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _resource_autocomplete(
        self, interaction: discord.Interaction, current: str
    ) -> list[app_commands.Choice[str]]:
        """
        Autocomplete resource keys from DB ResourceType.
        """
        current_l = (current or "").lower()

        with SessionLocal() as session:
            resources = session.scalars(
                select(ResourceType).where(ResourceType.is_active == True)  # noqa: E712
            ).all()

        choices: list[app_commands.Choice[str]] = []
        for r in resources:
            label = f"{r.display_name} ({r.key})"
            if current_l in r.key.lower() or current_l in (r.display_name or "").lower():
                choices.append(app_commands.Choice(name=label[:100], value=r.key))

        # Discord max is 25 choices
        return choices[:25]

    def _format_resource_value(self, resource_key: str, amount: int) -> str:
        """
        Format display by resource type:
        - money uses $ + suffix
        - everything else uses commas
        """
        if resource_key == "money":
            return f"${format_amount_with_suffix(amount)}"
        return f"{amount:,}"

    def _parse_resource_amount(self, resource_key: str, raw: str) -> int:
        """
        Parse amount input:
        - money supports suffixes (10K, 2.5M, etc.)
        - other resources must be int
        """
        if resource_key == "money":
            return parse_amount_with_suffix(raw)

        # allow commas for non-money too
        cleaned = raw.replace(",", "").strip()
        return int(cleaned)

    @app_commands.command(
        name="balance",
        description="Check resource balances for yourself or another player.",
    )
    @app_commands.describe(user="Player to inspect (defaults to yourself if omitted).")
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        target = user or interaction.user

        with SessionLocal() as session:
            player = get_or_create_player(session, target)
            money = get_resource_amount(session, player, "money")
            tech = get_resource_amount(session, player, "tech_points")

        embed = discord.Embed(
            title=f"{target.display_name}'s Resources",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Money", value=f"${format_amount_with_suffix(money)}", inline=False)
        embed.add_field(name="Tech Points", value=f"{tech:,}", inline=False)

        await interaction.response.send_message(embed=embed)
#---------------------------------------------------------------------------------------------------------------------------------------------------------------





#---------------------------------------------------------------------------------------------------------------------------------------------------------------
    @app_commands.command(
        name="give_resource",
        description="Give a resource to a player (dynamic resources supported).",
    )
    @app_commands.describe(
        user="Player to receive it (you can pick yourself).",
        resource="Resource key (autocomplete)",
        amount="Amount to add (Money supports 10K/5M/etc; others use integers)",
    )
    @app_commands.autocomplete(resource=_resource_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def give_resource(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        resource: str,
        amount: str,
    ):
        target = user

        # Validate resource exists + get display name
        with SessionLocal() as session:
            rtype = session.scalar(select(ResourceType).where(ResourceType.key == resource))
            if not rtype:
                await interaction.response.send_message(
                    f"Unknown resource key: `{resource}`",
                    ephemeral=True,
                )
                return

        # Parse amount
        try:
            delta = self._parse_resource_amount(resource, amount)
        except ValueError:
            await interaction.response.send_message(
                "Invalid amount format. Money examples: `500K`, `2.5M`. Other resources: `1200`.",
                ephemeral=True,
            )
            return

        if delta == 0:
            await interaction.response.send_message("Amount must be non-zero.", ephemeral=True)
            return

        # Apply
        with SessionLocal() as session:
            player = get_or_create_player(session, target)
            new_amount = adjust_resource(session, player, resource, delta)

        display_name = rtype.display_name or resource
        await interaction.response.send_message(
            f"Gave **{self._format_resource_value(resource, delta)}** {display_name} to {target.mention}.\n"
            f"New {display_name}: **{self._format_resource_value(resource, new_amount)}**."
        )
#---------------------------------------------------------------------------------------------------------------------------------------------------------------




 #---------------------------------------------------------------------------------------------------------------------------------------------------------------
    @app_commands.command(
        name="set_resource",
        description="Override-set a player's resource to an exact amount (dynamic resources supported).",
    )
    @app_commands.describe(
        user="Player to modify",
        resource="Resource key (autocomplete)",
        amount="Exact value (Money supports 10K/5M/etc; others use integers)",
    )
    @app_commands.autocomplete(resource=_resource_autocomplete)
    @app_commands.checks.has_permissions(manage_guild=True)
    async def set_resource(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        resource: str,
        amount: str,
    ):
        # Validate resource exists
        with SessionLocal() as session:
            rtype = session.scalar(select(ResourceType).where(ResourceType.key == resource))
            if not rtype:
                await interaction.response.send_message(
                    f"Unknown resource key: `{resource}`",
                    ephemeral=True,
                )
                return

        # Parse desired amount
        try:
            desired = self._parse_resource_amount(resource, amount)
        except ValueError:
            await interaction.response.send_message(
                "Invalid amount format. Money examples: `500K`, `2.5M`. Other resources: `1200`.",
                ephemeral=True,
            )
            return

        if desired < 0:
            await interaction.response.send_message(
                "Amount cannot be negative.",
                ephemeral=True,
            )
            return

        # Set = override by applying delta
        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            current = get_resource_amount(session, player, resource)
            delta = desired - current
            new_amount = adjust_resource(session, player, resource, delta)

        display_name = rtype.display_name or resource
        await interaction.response.send_message(
            f"Set {user.mention}'s **{display_name}** to **{self._format_resource_value(resource, new_amount)}**."
        )

    @app_commands.command(
        name="leaderboard",
        description="Show the top players for a specific resource.",
    )
    @app_commands.describe(
        resource="Resource key (autocomplete)",
        limit="How many to show (default 10, max 25)",
    )
    @app_commands.autocomplete(resource=_resource_autocomplete)
    async def leaderboard(
        self,
        interaction: discord.Interaction,
        resource: str,
        limit: int = 10,
    ):
        guild = interaction.guild
        if guild is None:
            await interaction.response.send_message("This command must be used in a server.", ephemeral=True)
            return

        limit = max(1, min(limit, 25))

        with SessionLocal() as session:
            rtype = session.scalar(select(ResourceType).where(ResourceType.key == resource))
            if not rtype:
                await interaction.response.send_message(f"Unknown resource key: `{resource}`", ephemeral=True)
                return

            players = session.scalars(select(Player)).all()

            rows = []
            for p in players:
                amt = get_resource_amount(session, p, resource)
                member = guild.get_member(p.discord_id)
                name = member.display_name if member else p.name or str(p.discord_id)
                rows.append((name, amt))

        rows.sort(key=lambda x: x[1], reverse=True)
        rows = rows[:limit]

        embed = discord.Embed(
            title=f"Leaderboard — {rtype.display_name or rtype.key}",
            color=discord.Color.gold(),
        )

        desc_lines = []
        for i, (name, amt) in enumerate(rows, start=1):
            desc_lines.append(f"**{i}. {name}** — {self._format_resource_value(resource, amt)}")
        embed.description = "\n".join(desc_lines) if desc_lines else "No players found."

        await interaction.response.send_message(embed=embed)



async def setup(bot: commands.Bot):
    await bot.add_cog(PlayersCog(bot))
