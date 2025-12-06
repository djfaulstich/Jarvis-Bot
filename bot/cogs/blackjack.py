'''
Name: Blackjack Cog
Type: Cog
User: Bot
Last Updated: 2025-12-06
Function: Provide a blackjack game using the UN Sim Money resource with card images.
'''

import os
from pathlib import Path
import random
from io import BytesIO
from typing import Dict, Any

import discord
from discord.ext import commands
from discord import app_commands

from PIL import Image
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Player, ResourceType, PlayerResource

import requests

# ---------- Paths & card constants ----------

BOT_DIR = Path(__file__).resolve().parents[1]

# Your PNG-cards-1.3 folder is directly inside /bot
CARD_ASSET_PATH = BOT_DIR / "PNG-cards-1.3"

SUIT_MAP = {"♠": "S", "♥": "H", "♦": "D", "♣": "C"}


# ---------- Money helpers (reuse same idea as players cog) ----------

def parse_amount_with_suffix(raw: str) -> int:
    """
    Parse strings like '1000', '1k', '2.5M', '10m', '3B', '1.2T' into an integer.
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
    Format large integers as 10K, 2.5M, 3B, etc., smaller numbers with commas.
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


DEFAULT_RESOURCES = [
    ("money", "Money"),
    ("tech_points", "Tech Points"),
]


def ensure_default_resources(session):
    existing = {r.key: r for r in session.scalars(select(ResourceType)).all()}
    for key, display in DEFAULT_RESOURCES:
        if key not in existing:
            rt = ResourceType(key=key, display_name=display, is_active=True)
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


# ---------- Blackjack core logic ----------

def draw_card() -> str:
    ranks = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K"]
    suits = ["♠", "♥", "♦", "♣"]
    return random.choice(ranks) + random.choice(suits)


def hand_value(hand) -> int:
    value, aces = 0, 0
    for card in hand:
        rank = card[:-1]
        if rank in ["J", "Q", "K"]:
            value += 10
        elif rank == "A":
            value += 11
            aces += 1
        else:
            value += int(rank)
    while value > 21 and aces:
        value -= 10
        aces -= 1
    return value


def format_hand(hand) -> str:
    return " ".join(hand) + f" (value: {hand_value(hand)})"


def render_game_text(game: Dict[str, Any], reveal_dealer: bool = False) -> str:
    dealer = game["dealer"]
    if reveal_dealer:
        dealer_display = " ".join(dealer) + f" (value: {hand_value(dealer)})"
    else:
        dealer_display = f"{dealer[0]} ??"

    lines = [f"Dealer: {dealer_display}"]

    for i, hand in enumerate(game["hands"]):
        prefix = "➡️" if i == game["current_hand"] else f"{i+1}."
        lines.append(f"{prefix} Hand {i+1}: {format_hand(hand)}")

    bets_str = ", ".join(f"${b}" for b in game["bets"])
    lines.append(f"\nBets: {bets_str}")

    return "\n".join(lines)


# ---------- Card image helpers ----------

# Our internal representation uses "A♠", "10♥", etc.
SUIT_NAME_MAP = {
    "♠": "spades",
    "♥": "hearts",
    "♦": "diamonds",
    "♣": "clubs",
}

RANK_NAME_MAP = {
    "A": "ace",
    "J": "jack",
    "Q": "queen",
    "K": "king",
    # '2'..'10' stay as strings
}


def card_to_filename(card: str) -> str:
    """
    Convert a card like 'A♠' or '10♥' to a filename like
    'ace_of_spades.png' or '10_of_hearts.png'.
    """
    rank = card[:-1]          # 'A', '10', 'J', etc.
    suit_symbol = card[-1]    # '♠', '♥', '♦', '♣'

    rank_name = RANK_NAME_MAP.get(rank, rank)  # A -> ace, 2..10 stay 2..10
    suit_name = SUIT_NAME_MAP.get(suit_symbol, "spades")

    filename = f"{rank_name}_of_{suit_name}.png"
    return os.path.join(CARD_ASSET_PATH, filename)


# We'll auto-detect a reasonable card back the first time we need it
_BACK_FILEPATH: str | None = None
_BACK_CANDIDATES = [
    "card_back.png",
    "back.png",
    "back_of_card.png",
    "purple_back.png",
    "blue_back.png",
    "red_back.png",
    "red_joker.png",
    "black_joker.png",
]


def _get_back_filepath() -> str | None:
    global _BACK_FILEPATH
    if _BACK_FILEPATH is not None:
        return _BACK_FILEPATH

    for name in _BACK_CANDIDATES:
        candidate = os.path.join(CARD_ASSET_PATH, name)
        if os.path.exists(candidate):
            _BACK_FILEPATH = candidate
            return _BACK_FILEPATH

    # nothing found
    _BACK_FILEPATH = None
    return None


def load_card_image(card: str, hidden: bool = False) -> Image.Image:
    """
    Load a single card image from the PNG-cards-1.3 set.
    If hidden=True, load the card back instead (auto-detected).
    """
    if hidden:
        back_path = _get_back_filepath()
        if back_path and os.path.exists(back_path):
            try:
                return Image.open(back_path).convert("RGBA")
            except Exception:
                pass
        # fall through to placeholder if back image missing

    else:
        path = card_to_filename(card)
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass

    # Fallback placeholder if anything fails
    return Image.new("RGBA", (100, 150), (0, 128, 0, 255))


def generate_blackjack_image(game: Dict[str, Any], reveal_dealer: bool) -> BytesIO:
    dealer_cards = game["dealer"]
    hands = game["hands"]

    # Use first dealer card to determine card size
    sample_card = load_card_image(dealer_cards[0])
    card_w, card_h = sample_card.size

    rows = 1 + len(hands)  # 1 dealer row + 1 row per player hand
    max_cards = max(len(dealer_cards), max(len(h) for h in hands))

    padding_x = 20
    padding_y = 20
    gap_x = 10
    gap_y = 40

    img_w = padding_x * 2 + max_cards * card_w + (max_cards - 1) * gap_x
    img_h = padding_y * 2 + rows * card_h + (rows - 1) * gap_y

    table = Image.new("RGBA", (img_w, img_h), (0, 100, 0, 255))  # green felt

    def paste_row(cards, row_index, hide_for_dealer=False):
        y = padding_y + row_index * (card_h + gap_y)
        for i, card in enumerate(cards):
            x = padding_x + i * (card_w + gap_x)
            hidden = False
            if hide_for_dealer and not reveal_dealer and i >= 1:
                hidden = True
            card_img = load_card_image(card, hidden=hidden)
            table.paste(card_img, (x, y), card_img)

    # Dealer row (index 0)
    paste_row(dealer_cards, 0, hide_for_dealer=True)

    # Player rows
    for idx, hand in enumerate(hands, start=1):
        paste_row(hand, idx, hide_for_dealer=False)

    buf = BytesIO()
    table.save(buf, format="PNG")
    buf.seek(0)
    return buf


def make_blackjack_file(game: Dict[str, Any], reveal_dealer: bool) -> discord.File:
    buf = generate_blackjack_image(game, reveal_dealer=reveal_dealer)
    return discord.File(buf, filename="blackjack.png")


# ---------- Interactive view ----------

class BlackjackView(discord.ui.View):
    def __init__(self, cog: "BlackjackCog", owner_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message(
                "This is not your game.", ephemeral=True
            )
            return False
        return True

    async def disable_all(self, interaction: discord.Interaction | None = None):
        for child in self.children:
            child.disabled = True
        try:
            if interaction and interaction.message:
                await interaction.message.edit(view=self)
        except Exception:
            pass

    # --------- Buttons ---------

    @discord.ui.button(label="Hit", style=discord.ButtonStyle.primary)
    async def hit_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        try:
            await interaction.response.defer()
            game = self.cog.active_games.get(self.owner_id)
            if not game:
                await interaction.followup.send(
                    "Game not found or already ended.", ephemeral=True
                )
                return

            hand = game["hands"][game["current_hand"]]
            hand.append(draw_card())

            if hand_value(hand) > 21:
                game["current_hand"] += 1
                text = f"❌ Busted: {format_hand(hand)}\n\n" + render_game_text(
                    game, reveal_dealer=False
                )
                file = make_blackjack_file(game, reveal_dealer=False)
                await interaction.message.edit(
                    content=text,
                    attachments=[file],
                    view=self,
                )

                if game["current_hand"] < len(game["hands"]):
                    await interaction.followup.send(
                        f"➡️ Now playing hand {game['current_hand']+1}: "
                        f"{format_hand(game['hands'][game['current_hand']])}"
                    )
                else:
                    await self.cog.resolve_blackjack(interaction, game)
                    await self.disable_all(interaction)
            else:
                text = render_game_text(game, reveal_dealer=False)
                file = make_blackjack_file(game, reveal_dealer=False)
                await interaction.message.edit(
                    content=text,
                    attachments=[file],
                    view=self,
                )

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Stand", style=discord.ButtonStyle.secondary)
    async def stand_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        try:
            await interaction.response.defer()
            game = self.cog.active_games.get(self.owner_id)
            if not game:
                await interaction.followup.send(
                    "Game not found or already ended.", ephemeral=True
                )
                return

            game["current_hand"] += 1

            if game["current_hand"] < len(game["hands"]):
                text = (
                    f"➡️ Now playing hand {game['current_hand']+1}: "
                    f"{format_hand(game['hands'][game['current_hand']])}\n\n"
                    + render_game_text(game, reveal_dealer=False)
                )
                file = make_blackjack_file(game, reveal_dealer=False)
                await interaction.message.edit(
                    content=text,
                    attachments=[file],
                    view=self,
                )
            else:
                await self.cog.resolve_blackjack(interaction, game)
                await self.disable_all(interaction)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Double", style=discord.ButtonStyle.success)
    async def double_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        try:
            await interaction.response.defer()
            game = self.cog.active_games.get(self.owner_id)
            if not game:
                await interaction.followup.send(
                    "Game not found or already ended.", ephemeral=True
                )
                return

            idx = game["current_hand"]
            hand = game["hands"][idx]

            if len(hand) != 2:
                await interaction.followup.send(
                    "You can only double on your first two cards.", ephemeral=True
                )
                return

            base_bet = game["bets"][idx]

            # Check balance
            with SessionLocal() as session:
                player = get_or_create_player(session, interaction.user)
                bal = get_money_balance(session, player)
                if base_bet > bal:
                    await interaction.followup.send(
                        "Not enough balance to double down.", ephemeral=True
                    )
                    return
                change_money_balance(session, player, -base_bet)

            game["bets"][idx] *= 2
            hand.append(draw_card())

            if hand_value(hand) > 21:
                game["current_hand"] += 1
                text = (
                    f"❌ Busted after doubling: {format_hand(hand)}\n\n"
                    + render_game_text(game, reveal_dealer=False)
                )
                file = make_blackjack_file(game, reveal_dealer=False)
                await interaction.message.edit(
                    content=text,
                    attachments=[file],
                    view=self,
                )

                if game["current_hand"] < len(game["hands"]):
                    await interaction.followup.send(
                        f"➡️ Now playing hand {game['current_hand']+1}: "
                        f"{format_hand(game['hands'][game['current_hand']])}"
                    )
                else:
                    await self.cog.resolve_blackjack(interaction, game)
                    await self.disable_all(interaction)
            else:
                game["current_hand"] += 1
                if game["current_hand"] < len(game["hands"]):
                    text = render_game_text(game, reveal_dealer=False)
                    file = make_blackjack_file(game, reveal_dealer=False)
                    await interaction.message.edit(
                        content=text,
                        attachments=[file],
                        view=self,
                    )
                else:
                    await self.cog.resolve_blackjack(interaction, game)
                    await self.disable_all(interaction)

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)

    @discord.ui.button(label="Split", style=discord.ButtonStyle.secondary)
    async def split_button(
        self, interaction: discord.Interaction, _: discord.ui.Button
    ):
        try:
            await interaction.response.defer()
            game = self.cog.active_games.get(self.owner_id)
            if not game:
                await interaction.followup.send(
                    "Game not found or already ended.", ephemeral=True
                )
                return

            if game["split"]:
                await interaction.followup.send(
                    "You already split.", ephemeral=True
                )
                return

            hand = game["hands"][0]
            if len(hand) != 2 or hand[0][:-1] != hand[1][:-1]:
                await interaction.followup.send(
                    "You can only split identical ranks and only on your initial two cards.",
                    ephemeral=True,
                )
                return

            base_bet = game["bets"][0]

            # Check balance
            with SessionLocal() as session:
                player = get_or_create_player(session, interaction.user)
                bal = get_money_balance(session, player)
                if base_bet > bal:
                    await interaction.followup.send(
                        "Not enough balance to split.", ephemeral=True
                    )
                    return
                change_money_balance(session, player, -base_bet)

            hand1 = [hand[0], draw_card()]
            hand2 = [hand[1], draw_card()]
            game["hands"] = [hand1, hand2]
            game["bets"] = [base_bet, base_bet]
            game["split"] = True
            game["current_hand"] = 0

            text = (
                f"Hands split:\n1️⃣ {format_hand(hand1)}\n2️⃣ {format_hand(hand2)}\n\n"
                + render_game_text(game, reveal_dealer=False)
            )
            file = make_blackjack_file(game, reveal_dealer=False)
            await interaction.message.edit(
                content=text,
                attachments=[file],
                view=self,
            )

        except Exception as e:
            await interaction.followup.send(f"An error occurred: {e}", ephemeral=True)


# ---------- Cog ----------

class BlackjackCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.active_games: Dict[int, Dict[str, Any]] = {}

    def end_game(self, user_id: int):
        self.active_games.pop(user_id, None)

    async def resolve_blackjack(
        self, interaction: discord.Interaction, game: Dict[str, Any]
    ):
        dealer = game["dealer"]
        while hand_value(dealer) < 17:
            dealer.append(draw_card())

        owner_id = game["owner"]

        results = []

        # Get DB player
        with SessionLocal() as session:
            user = interaction.user
            player = get_or_create_player(session, user)

            for i, hand in enumerate(game["hands"]):
                player_val = hand_value(hand)
                dealer_val = hand_value(dealer)
                bet = game["bets"][i]

                if player_val > 21:
                    results.append(f"{format_hand(hand)} → Bust (-${bet})")
                    continue

                if dealer_val > 21 or player_val > dealer_val:
                    # player wins: pay 2x bet (return + winnings)
                    change_money_balance(session, player, bet * 2)
                    results.append(
                        f"{format_hand(hand)} beats dealer ({dealer_val}) → +${bet}"
                    )
                elif dealer_val == player_val:
                    # push: refund bet
                    change_money_balance(session, player, bet)
                    results.append(
                        f"{format_hand(hand)} pushes with dealer ({dealer_val}) → $0"
                    )
                else:
                    results.append(
                        f"{format_hand(hand)} loses to dealer ({dealer_val}) → -${bet}"
                    )

            final_balance = get_money_balance(session, player)

        final_text = (
            f"Dealer's hand: {format_hand(dealer)}\n"
            + "\n".join(results)
            + f"\nBalance: ${format_amount_with_suffix(final_balance)}"
        )
        file = make_blackjack_file(game, reveal_dealer=True)

        try:
            await interaction.message.edit(
                content=final_text,
                attachments=[file],
                view=None,
            )
        except Exception:
            await interaction.followup.send(final_text, file=file)

        self.end_game(owner_id)

    # ---------- Slash command to start game ----------

    @app_commands.command(
        name="blackjack",
        description="Play blackjack using your Money balance.",
    )
    @app_commands.describe(
        bet="Bet amount (e.g. 1000, 500K, 10M, 2.5B)."
    )
    async def blackjack(self, interaction: discord.Interaction, bet: str):
        user = interaction.user

        # Parse bet
        try:
            bet_int = parse_amount_with_suffix(bet)
        except ValueError:
            await interaction.response.send_message(
                "Invalid bet. Examples: `1000`, `500K`, `10M`, `2.5B`.",
                ephemeral=True,
            )
            return

        if bet_int <= 0:
            await interaction.response.send_message(
                "Bet must be greater than zero.",
                ephemeral=True,
            )
            return

        if user.id in self.active_games:
            await interaction.response.send_message(
                "You are already in a blackjack game.",
                ephemeral=True,
            )
            return

        # Check and deduct balance
        with SessionLocal() as session:
            player = get_or_create_player(session, user)
            balance = get_money_balance(session, player)
            if bet_int > balance:
                await interaction.response.send_message(
                    f"You don't have enough Money for that bet. "
                    f"Current balance: ${format_amount_with_suffix(balance)}",
                    ephemeral=True,
                )
                return

            # Deduct bet up front
            change_money_balance(session, player, -bet_int)

        # Initialize game state
        player_hand = [draw_card(), draw_card()]
        dealer_hand = [draw_card(), draw_card()]

        game = {
            "owner": user.id,
            "hands": [player_hand],
            "dealer": dealer_hand,
            "bets": [bet_int],
            "current_hand": 0,
            "split": False,
        }
        self.active_games[user.id] = game

        # Check instant blackjack
        player_val = hand_value(player_hand)
        dealer_val = hand_value(dealer_hand)

        if player_val == 21:
            with SessionLocal() as session:
                player = get_or_create_player(session, user)
                if dealer_val == 21:
                    # push: refund bet
                    change_money_balance(session, player, bet_int)
                    balance = get_money_balance(session, player)
                    msg = (
                        f"Your hand: {format_hand(player_hand)}\n"
                        f"Dealer: {format_hand(dealer_hand)}\n"
                        f"Push — both have Blackjack. Your bet is returned.\n"
                        f"Balance: ${format_amount_with_suffix(balance)}"
                    )
                    await interaction.response.send_message(msg)
                else:
                    # player wins 3:2 (we already deducted bet)
                    payout = int(bet_int * 2.5)
                    change_money_balance(session, player, payout)
                    balance = get_money_balance(session, player)
                    winnings = payout - bet_int
                    msg = (
                        f"Your hand: {format_hand(player_hand)}\n"
                        f"Dealer: {dealer_hand[0]} ??\n"
                        f"BLACKJACK! You win ${format_amount_with_suffix(winnings)} "
                        f"(3:2 payout).\n"
                        f"Balance: ${format_amount_with_suffix(balance)}"
                    )
                    await interaction.response.send_message(msg)

            self.end_game(user.id)
            return

        # Normal start: show image + buttons
        content = (
            render_game_text(game, reveal_dealer=False)
            + "\n\nUse the buttons below: Hit / Stand / Double / Split"
        )
        file = make_blackjack_file(game, reveal_dealer=False)
        view = BlackjackView(self, user.id)
        await interaction.response.send_message(content, file=file, view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(BlackjackCog(bot))
