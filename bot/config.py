"""
Name: Config Loader
Type: Function
User: Bot
Last Updated: 2026-02-21
Function: Load configuration values from environment with SQLite as the default storage backend.
"""

import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
SQLITE_DB_PATH = os.getenv("SQLITE_DB_PATH", "./bot.db")
DATABASE_URL = f"sqlite:///{SQLITE_DB_PATH}"

if not DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set in the environment variables.")
