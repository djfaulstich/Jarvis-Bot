"""
Name: ORM Models
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Define database models for the bot.
"""

from sqlalchemy import Column, Integer, String, BigInteger
from .db import Base


class UserProfile(Base):
    __tablename__ = "user_profiles"

    id = Column(Integer, primary_key=True, index=True)
    discord_id = Column(BigInteger, unique=True, index=True, nullable=False)
    display_name = Column(String(100), nullable=False)
    points = Column(Integer, default=0)
