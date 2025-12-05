"""
Name: Config Loader
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Load configuration values from environment.
"""

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bot.db")

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in the environment variables.")
