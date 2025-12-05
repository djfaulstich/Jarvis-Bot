'''
Name: Videos Cog
Type: Cog
User: Bot
Last Updated: 2025-12-04
Function: Provide a slash command to link the latest tag videos playlist.
'''

import discord
from discord.ext import commands
from discord import app_commands

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLG-Yl_vCaRsjWWtxtdGi2rsk3NnmsVacL"




class VideosCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="videos",
        description="Check the latest tag videos playlist.",
    )
    async def videos_command(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="TAG Playlist",
            url=PLAYLIST_URL,  # clicking the title opens the playlist
            description="",
            color=discord.Color.red(),
        )

        # Fake the little YouTube look a bit
        embed.set_author(
            name="YouTube",
        )

        await interaction.response.send_message(
            embed=embed,
            ephemeral=False,  # set True if you want only the caller to see it
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(VideosCog(bot))
