'''
Name: Tag Cog
Type: Cog
User: Bot
Last Updated: 2025-12-04
Function: Provide tag reporting via buttons and modals, logging to the database.
'''

import datetime
import discord
from discord.ext import commands
from discord import app_commands

from ..db import SessionLocal
from ..models import TagReport
from zoneinfo import ZoneInfo


def find_tag_channel(interaction: discord.Interaction) -> discord.TextChannel | None:
    """
    Finds a text channel in the guild whose name contains 'tag' (case-insensitive).
    Returns None if no matching channel exists.
    """
    if not interaction.guild:
        return None

    name_match = "tag"
    for channel in interaction.guild.text_channels:
        if name_match in channel.name.lower():
            return channel

    return None

def _ordinal(n: int) -> str:
    """
    Helper: return 1 -> '1st', 2 -> '2nd', etc.
    """
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _format_human_datetime(dt: datetime.datetime) -> str:
    """
    Helper: format datetime like 'December 25th 2025 at 8:30 PM EST'.
    Assumes dt is already converted to Eastern time.
    """
    month = dt.strftime("%B")
    day_ordinal = _ordinal(dt.day)
    year = dt.year
    time_str = dt.strftime("%I:%M %p").lstrip("0")
    return f"{month} {day_ordinal} {year} at {time_str} EST"



class TagAmountModal(discord.ui.Modal, title="Report Tags"):
    """
    Modal asking the user how many tags they want to report.
    """

    def __init__(self, tag_type: str):
        super().__init__()
        self.tag_type = tag_type

        self.tag_count_input = discord.ui.TextInput(
            label="How many tags do you want to report?",
            placeholder="Enter a number",
            required=True,
            max_length=3,
        )
        self.add_item(self.tag_count_input)

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.user

        try:
            count = int(self.tag_count_input.value)
            if count <= 0:
                raise ValueError
        except ValueError:
            await interaction.response.send_message(
                "Please enter a valid positive number.",
                ephemeral=True,
            )
            return

        # Create timestamps
        now_utc = datetime.datetime.now(tz=datetime.timezone.utc)
        now_est = now_utc.astimezone(ZoneInfo("America/New_York"))
        human_time = _format_human_datetime(now_est)

        # Acknowledge to the user
        await interaction.response.send_message(
            f"You have reported **{count} {self.tag_type or 'normal'} tag(s)**.\n"
            f"Logged at **{human_time}**.",
            ephemeral=True,
        )

        # Send alert to channel
        channel = find_tag_channel(interaction)

        if channel:
            tag_label = (self.tag_type or "normal").upper()
            if count == 1:
                msg = (
                    f"@everyone **TAG!!!** - - - **{human_time}**")
            else:
                msg = (
                    f"@everyone TAG x{count}!!! - - - **{human_time}**"
                )
            await channel.send(msg)
        else:
            # Fallback: let the user know no tag channel was found
            await interaction.followup.send(
                "⚠️ No channel containing 'tag' was found in this server — unable to send the alert.",
                ephemeral=True,
            )


        # Log to DB (keep UTC for machine use, human string in EST)
        with SessionLocal() as session:
            report = TagReport(
                user_id=user.id,
                username=f"{user.name}#{user.discriminator}",
                tag_type=self.tag_type or "normal",
                count=count,
                channel_id=find_tag_channel(),
                timestamp_utc=now_utc.replace(tzinfo=None),  # if your model expects naive
                timestamp_human=human_time,
            )
            session.add(report)
            session.commit()


class TagView(discord.ui.View):
    """
    View with buttons for Normal Tag / Proxy Tag / Cancel.
    """

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Normal Tag", style=discord.ButtonStyle.green)
    async def normal_tag(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = TagAmountModal(tag_type="normal")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Proxy Tag", style=discord.ButtonStyle.blurple)
    async def proxy_tag(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        modal = TagAmountModal(tag_type="proxy")
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
    async def cancel(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        try:
            await interaction.message.delete()
        except Exception:
            pass

        await interaction.response.send_message(
            "Tag has been canceled!", ephemeral=True
        )


class TagCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="tag",
        description="Report a tag and notify the guild.",
    )
    async def tag_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="Tag Report!",
            description="Please confirm the type of tag you're reporting.",
            color=discord.Color.orange(),
        )
        embed.set_thumbnail(
            url=(
                "https://static-00.iconduck.com/assets.00/"
                "caution-sign-emoji-2047x2048-sgki3f8a.png"
            )
        )
        await interaction.response.send_message(
            embed=embed,
            view=TagView(),
            ephemeral=True
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TagCog(bot))
