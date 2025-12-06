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
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Player, ResourceType, PlayerResource


# ---------- Amount formatting / parsing ----------

def parse_amount_with_suffix(raw: str) -> int:
    """
    Parse strings like:
      '1000', '1k', '1K', '2.5M', '10m', '3B', '1.2T'
    into an integer.
    """
    s = raw.replace(",", "").strip().upper()
    if not s:
        raise ValueError("Empty amount")

    multiplier = 1
    if s[-1] in ("K", "M", "B", "T"):
        suffix = s[-1]
        num_part = s[:-1]
        if suffix == "K":
            multiplier = 1_000
        elif suffix == "M":
            multiplier = 1_000_000
        elif suffix == "B":
            multiplier = 1_000_000_000
        elif suffix == "T":
            multiplier = 1_000_000_000_000
    else:
        num_part = s

    value = float(num_part)
    result = int(round(value * multiplier))
    return result


def format_amount_with_suffix(value: int) -> str:
    """
    Format large integers as:
      1234        -> '1.23K'
      10000000    -> '10M'
      2500000000  -> '2.5B'
    Smaller numbers use commas: 123 -> '123'
    """
    n = value
    abs_n = abs(n)

    def fmt(x, suffix):
        if x.is_integer():
            return f"{int(x)}{suffix}"
        return f"{x:.2f}{suffix}".rstrip("0").rstrip(".")

    if abs_n >= 1_000_000_000_000:
        return fmt(n / 1_000_000_000_000, "T")
    elif abs_n >= 1_000_000_000:
        return fmt(n / 1_000_000_000, "B")
    elif abs_n >= 1_000_000:
        return fmt(n / 1_000_000, "M")
    elif abs_n >= 1_000:
        return fmt(n / 1_000, "K")
    else:
        return f"{n:,}"


# ---------- DB helpers ----------

# Only MONEY and TECH_POINTS now
DEFAULT_RESOURCES = [
    ("money", "Money"),
    ("tech_points", "Tech Points"),
]


def ensure_default_resources(session):
    """
    Make sure Money and Tech Points exist in resource_types.
    """
    existing = {
        r.key: r
        for r in session.scalars(select(ResourceType)).all()
    }

    for key, display in DEFAULT_RESOURCES:
        if key not in existing:
            rt = ResourceType(key=key, display_name=display, is_active=True)
            session.add(rt)

    session.commit()


def get_or_create_player(session, user: discord.abc.User) -> Player:
    """
    Get or create a Player row for the given Discord user.
    """
    player = session.scalar(
        select(Player).where(Player.discord_id == user.id)
    )
    if player:
        player.name = user.display_name
        session.commit()
        return player

    player = Player(
        discord_id=user.id,
        name=user.display_name,
    )
    session.add(player)
    session.commit()
    return player


def adjust_resource(session, player: Player, resource_key: str, delta: int) -> int:
    """
    Add delta to the specified resource for a player.
    Returns the new amount.
    """
    ensure_default_resources(session)

    rtype = session.scalar(
        select(ResourceType).where(ResourceType.key == resource_key)
    )
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


def get_player_resources(session, player: Player) -> dict[str, int]:
    """
    Returns dict like {'money': 1000000, 'tech_points': 123}
    Missing resources are treated as 0.
    """
    ensure_default_resources(session)

    rtypes = {r.id: r for r in session.scalars(select(ResourceType)).all()}
    key_by_id = {r.id: r.key for r in rtypes.values()}

    balances = {key: 0 for key, _ in DEFAULT_RESOURCES}

    rows = session.scalars(
        select(PlayerResource).where(PlayerResource.player_id == player.id)
    ).all()

    for row in rows:
        key = key_by_id.get(row.resource_id)
        if key:
            balances[key] = row.amount

    return balances


# ---------- Cog ----------

class PlayersCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # --- Public command: check your own or someone else's balance ---
    @app_commands.command(
        name="balance",
        description="Check resource balances for yourself or another player.",
    )
    @app_commands.describe(
        user="Player to inspect (defaults to yourself if omitted)."
    )
    async def balance(
        self,
        interaction: discord.Interaction,
        user: discord.Member | None = None,
    ):
        target = user or interaction.user

        with SessionLocal() as session:
            player = get_or_create_player(session, target)
            balances = get_player_resources(session, player)

        money_str = format_amount_with_suffix(balances["money"])
        tech_str = f"{balances['tech_points']:,}"

        embed = discord.Embed(
            title=f"{target.display_name}'s Resources",
            color=discord.Color.gold(),
        )
        embed.add_field(name="Money", value=f"${money_str}", inline=False)
        embed.add_field(name="Tech Points", value=tech_str, inline=False)

        # PUBLIC now (no ephemeral)
        await interaction.response.send_message(embed=embed)

    # --- Admin command: give money ---

    @app_commands.command(
        name="give_money",
        description="Give a player money (use numbers with suffixes like 10M, 500K, etc.).",
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

        delta_str = format_amount_with_suffix(delta)
        new_str = format_amount_with_suffix(new_amount)

        # PUBLIC, and @ mention the recipient
        await interaction.response.send_message(
            f"Gave **${delta_str}** to {user.mention}.\n"
            f"New balance: **${new_str}**.",
        )

    # --- Admin command: give tech points ---

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
            await interaction.response.send_message(
                "Amount must be non-zero.",
            )
            return

        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            new_amount = adjust_resource(session, player, "tech_points", amount)

        # PUBLIC, and @ mention the recipient
        await interaction.response.send_message(
            f"Gave **{amount:,}** Tech Points to {user.mention}.\n"
            f"New Tech Points: **{new_amount:,}**.",
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayersCog(bot))
