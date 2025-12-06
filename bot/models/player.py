'''
Name: Player Model
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Store per-player identity for the UN Sim.
'''

from sqlalchemy import Column, Integer, String, BigInteger
from ..db import Base


class Player(Base):
    __tablename__ = "players"

    id = Column(Integer, primary_key=True)
    discord_id = Column(BigInteger, unique=True, index=True, nullable=False)
    name = Column(String(100), nullable=False)  # e.g., country name or player nickname
