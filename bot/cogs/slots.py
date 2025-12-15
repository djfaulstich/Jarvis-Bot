'''
Name: Slots Cog
Type: Cog
User: Bot
Last Updated: 2025-12-06
Function: Slot machine game using the UN Sim Money resource with a fast GIF animation.
'''

import random
from io import BytesIO
from typing import Dict

import discord
from discord.ext import commands
from discord import app_commands

from PIL import Image, ImageDraw
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Player, ResourceType, PlayerResource
from pathlib import Path

# ---------- Game config ----------

SYMBOLS = ["🍒", "🍋", "🍊", "⭐", "🔔", "7️⃣", "🍀", "💀"]

# (payout for 2-in-a-row, payout for 3-in-a-row) * bet
PAYOUTS = {
    "🍒": (2, 5),
    "🍋": (2, 6),
    "🍊": (2, 7),
    "⭐": (3, 10),
    "🔔": (4, 15),
    "7️⃣": (10, 50),
    "🍀": (3, 10),
    "💀": (0, 0),
}

# Simple background colors per symbol (R, G, B)
SYMBOL_COLORS: Dict[str, tuple[int, int, int]] = {
    "🍒": (220, 20, 60),
    "🍋": (255, 215, 0),
    "🍊": (255, 140, 0),
    "⭐": (255, 215, 0),
    "🔔": (218, 165, 32),
    "7️⃣": (148, 0, 211),
    "🍀": (34, 139, 34),
    "💀": (47, 79, 79),
}

ASSETS_DIR = Path(__file__).resolve().parents[1] / "assets" / "Slots-PNG"

# Map your symbols to icon filenames
SYMBOL_ICON_FILES = {
    "🍒": "cherry.png",
    "🍋": "lemon.png",
    "🍊": "orange.png",
    "⭐": "star.png",
    "🔔": "bell.png",
    "7️⃣": "seven.png",
    "🍀": "clover.png",
    "💀": "skull.png",
}


# ---------- Money helpers (same style as players/blackjack) ----------

def parse_amount_with_suffix(raw: str) -> int:
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


DEFAULT_RESOURCES = [
    ("money", "Money"),
    ("tech_points", "Tech Points"),
]


def ensure_default_resources(session):
    existing = {r.key: r for r in session.scalars(select(ResourceType)).all()}
    for key, display_name in DEFAULT_RESOURCES:
        if key not in existing:
            rt = ResourceType(key=key, display_name=display_name, is_active=True)
            session.add(rt)
    session.commit()


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


def get_money_balance(session, player: Player) -> int:
    ensure_default_resources(session)
    money_type = session.scalar(
        select(ResourceType).where(ResourceType.key == "money")
    )
    if not money_type:
        return 0

    pr = session.scalar(
        select(PlayerResource).where(
            PlayerResource.player_id == player.id,
            PlayerResource.resource_id == money_type.id,
        )
    )
    return pr.amount if pr else 0


def change_money_balance(session, player: Player, delta: int) -> int:
    ensure_default_resources(session)
    money_type = session.scalar(
        select(ResourceType).where(ResourceType.key == "money")
    )
    if not money_type:
        raise RuntimeError("Money resource type not defined.")

    pr = session.scalar(
        select(PlayerResource).where(
            PlayerResource.player_id == player.id,
            PlayerResource.resource_id == money_type.id,
        )
    )
    if not pr:
        pr = PlayerResource(
            player_id=player.id, resource_id=money_type.id, amount=0
        )
        session.add(pr)

    pr.amount += delta
    session.commit()
    session.refresh(pr)
    return pr.amount


# Cache loaded icon images (PIL.Image) by symbol
_ICON_CACHE: Dict[str, Image.Image] = {}


def _load_symbol_icon(symbol: str, size: int) -> Image.Image:
    """
    Load & resize an icon PNG for a given symbol. Cached for speed.
    """
    key = f"{symbol}:{size}"
    if key in _ICON_CACHE:
        return _ICON_CACHE[key].copy()

    filename = SYMBOL_ICON_FILES.get(symbol)
    if not filename:
        # fallback placeholder icon
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.ellipse((4, 4, size - 4, size - 4), outline=(255, 255, 255, 255), width=3)
        _ICON_CACHE[key] = img
        return img.copy()

    path = ASSETS_DIR / filename
    if not path.exists():
        # fallback placeholder icon if asset missing
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rectangle((6, 6, size - 6, size - 6), outline=(255, 255, 255, 255), width=3)
        _ICON_CACHE[key] = img
        return img.copy()

    img = Image.open(path).convert("RGBA")
    img = img.resize((size, size), Image.Resampling.LANCZOS)
    _ICON_CACHE[key] = img
    return img.copy()


def generate_slots_gif(spin: list[str], winnings: int, bet: int) -> BytesIO:
    """
    All reels spin at the same speed.
    Stop left reel first, then middle, then right.
    Hold the final result for ~1–2 seconds.
    """
    width, height = 360, 160
    bg_color = (15, 15, 20)
    border_color = (230, 230, 230)

    reel_count = 3
    reel_width = 90
    reel_height = 100
    gap = 10

    total_width = reel_count * reel_width + (reel_count - 1) * gap
    offset_x = (width - total_width) // 2
    offset_y = (height - reel_height) // 2

    frames: list[Image.Image] = []

    # ---- Timing knobs ----
    duration_ms = 90          # slower = less flashing (try 80–110)
    spin_frames = 8          # all reels spinning together
    stop_frames_per_reel = 8  # how many frames between each reel stopping
    hold_frames = 18          # hold final (18 * 90ms = 1.62s)

    icon_size = 62

    # Start positions (all reels random)
    reel_indices = [random.randint(0, len(SYMBOLS) - 1) for _ in range(3)]

    # Which reels are stopped yet?
    stopped = [False, False, False]

    def render_frame(frame_idx: int) -> Image.Image:
        img = Image.new("RGBA", (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        draw.rounded_rectangle(
            [5, 5, width - 6, height - 6],
            radius=20,
            outline=border_color,
            width=3,
        )

        # Payline
        draw.line(
            (8, offset_y + reel_height // 2, width - 8, offset_y + reel_height // 2),
            fill=(255, 255, 255, 90),
            width=2,
        )

        for r in range(reel_count):
            x0 = offset_x + r * (reel_width + gap)
            y0 = offset_y

            # Choose what symbol is shown on each reel
            if stopped[r]:
                symbol = spin[r]  # locked to final
            else:
                # All reels tick at the same speed (use their index)
                symbol = SYMBOLS[reel_indices[r]]

            color = SYMBOL_COLORS.get(symbol, (80, 80, 80))

            draw.rounded_rectangle(
                [x0, y0, x0 + reel_width, y0 + reel_height],
                radius=15,
                fill=color,
                outline=(0, 0, 0),
                width=2,
            )

            icon = _load_symbol_icon(symbol, icon_size)
            ix = int(x0 + (reel_width - icon_size) / 2)
            iy = int(y0 + (reel_height - icon_size) / 2)
            img.paste(icon, (ix, iy), icon)

        return img

    # Phase 1: all reels spin together (same speed)
    for i in range(spin_frames):
        # tick all reels once per frame
        reel_indices = [(idx + 1) % len(SYMBOLS) for idx in reel_indices]
        frames.append(render_frame(i))

    # Phase 2: stop reels one-by-one (left -> middle -> right)
    # Between each stop, keep spinning the reels that aren't stopped yet
    for reel_to_stop in range(3):
        for i in range(stop_frames_per_reel):
            # tick only reels that are still spinning
            for r in range(3):
                if not stopped[r]:
                    reel_indices[r] = (reel_indices[r] + 1) % len(SYMBOLS)
            frames.append(render_frame(i))

        # lock this reel to final result
        stopped[reel_to_stop] = True
        frames.append(render_frame(0))  # one extra frame immediately after locking

    # Phase 3: hold final result
    for i in range(hold_frames):
        frames.append(render_frame(i))

    buf = BytesIO()
    frames[0].save(
        buf,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=duration_ms,
        loop=0,
        disposal=2,
    )
    buf.seek(0)
    return buf


def make_slots_file(spin: list[str], winnings: int, bet: int) -> discord.File:
    buf = generate_slots_gif(spin, winnings, bet)
    return discord.File(buf, filename="slots.gif")


# ---------- Cog ----------

class SlotsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="slots",
        description="Spin the slot machine using your Money balance.",
    )
    @app_commands.describe(
        bet="Bet amount (e.g. 1000, 500K, 5M, 2.5B)."
    )
    async def slots(self, interaction: discord.Interaction, bet: str):
        user = interaction.user

        # Parse bet
        try:
            bet_int = parse_amount_with_suffix(bet)
        except ValueError:
            await interaction.response.send_message(
                "Invalid bet. Examples: `1000`, `500K`, `5M`, `2.5B`.",
                ephemeral=True,
            )
            return

        if bet_int <= 0:
            await interaction.response.send_message(
                "Bet must be greater than zero.",
                ephemeral=True,
            )
            return

        # Check & deduct balance
        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            balance = get_money_balance(session, player)
            if bet_int > balance:
                await interaction.response.send_message(
                    f"You don’t have enough Money for that bet.\n"
                    f"Current balance: **${format_amount_with_suffix(balance)}**.",
                    ephemeral=True,
                )
                return

            # Deduct bet
            change_money_balance(session, player, -bet_int)

        # Spin 3 reels
        spin = [random.choice(SYMBOLS) for _ in range(3)]

        # Auto-loss if skull appears anywhere
        if "💀" in spin:
            winnings = 0
            result_text = (
                f"🎰 {' | '.join(spin)} 🎰\n"
                f"💀 A skull appeared! You lose your bet of "
                f"**${format_amount_with_suffix(bet_int)}**."
            )
        else:
            # Count matches
            winnings = 0
            for symbol in set(spin):
                count = spin.count(symbol)
                if count == 2:
                    winnings = max(winnings, PAYOUTS[symbol][0] * bet_int)
                elif count == 3:
                    winnings = max(winnings, PAYOUTS[symbol][1] * bet_int)

            if winnings > 0:
                result_text = (
                    f"🎰 {' | '.join(spin)} 🎰\n"
                    f"✅ You won **${format_amount_with_suffix(winnings)}**!"
                )
            else:
                result_text = (
                    f"🎰 {' | '.join(spin)} 🎰\n"
                    f"❌ No matches, better luck next time!"
                )

        # Apply winnings (if any)
        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            if winnings > 0:
                change_money_balance(session, player, winnings)
            final_balance = get_money_balance(session, player)

        # Append balance info
        result_text += f"\nBalance: **${format_amount_with_suffix(final_balance)}**"

        # Generate GIF (fast, small)
        file = make_slots_file(spin, winnings, bet_int)

        await interaction.response.send_message(content=result_text, file=file)


async def setup(bot: commands.Bot):
    await bot.add_cog(SlotsCog(bot))