'''
Name: Players Cog
Type: Cog
User: Bot
Last Updated: 2025-12-06
Function: Manage UN Sim players and their resources (money, tech points).
'''

import discord
from discord.ext import commands
from discord import app_commands

from ..db import SessionLocal
from ..utils.amounts import parse_amount_with_suffix, format_amount_with_suffix
from ..utils.players import get_or_create_player, adjust_resource, get_resource_amount


class PlayersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

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

    @app_commands.command(
        name="give_money",
        description="Give a player money (use suffixes like 10M, 500K, etc.).",
    )
    @app_commands.describe(
        user="Player to give money to.",
        amount="Amount (e.g., 1000, 500K, 10M, 2.5B).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def give_money(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: str,
    ):
        try:
            delta = parse_amount_with_suffix(amount)
        except ValueError:
            await interaction.response.send_message(
                "Invalid amount. Examples: `1000`, `500K`, `10M`, `2.5B`.",
            )
            return

        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            new_amount = adjust_resource(session, player, "money", delta)

        await interaction.response.send_message(
            f"Gave **${format_amount_with_suffix(delta)}** to {user.mention}.\n"
            f"New balance: **${format_amount_with_suffix(new_amount)}**."
        )

    @app_commands.command(
        name="setbalance",
        description="Set a player's Money balance to an exact value (supports suffixes like 10M, 500K).",
    )
    @app_commands.describe(
        user="Player whose balance you want to set.",
        amount="Exact amount (e.g., 1000, 500K, 10M, 2.5B).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def setbalance(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: str,
    ):
        try:
            desired = parse_amount_with_suffix(amount)
        except ValueError:
            await interaction.response.send_message(
                "Invalid amount. Examples: `1000`, `500K`, `10M`, `2.5B`.",
            )
            return

        if desired < 0:
            await interaction.response.send_message("Balance cannot be negative.")
            return

        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            current = get_resource_amount(session, player, "money")
            delta = desired - current
            new_amount = adjust_resource(session, player, "money", delta)

        await interaction.response.send_message(
            f"Set {user.mention}'s Money to **${format_amount_with_suffix(new_amount)}**."
        )

    @app_commands.command(
        name="give_tech",
        description="Give a player Tech Points.",
    )
    @app_commands.describe(
        user="Player to give tech points to.",
        amount="Number of tech points (integer).",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def give_tech(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: int,
    ):
        if amount == 0:
            await interaction.response.send_message("Amount must be non-zero.")
            return

        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            new_amount = adjust_resource(session, player, "tech_points", amount)

        await interaction.response.send_message(
            f"Gave **{amount:,}** Tech Points to {user.mention}.\n"
            f"New Tech Points: **{new_amount:,}**."
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayersCog(bot))
