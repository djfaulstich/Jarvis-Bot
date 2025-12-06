'''
Name: PlayerResource Model
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Store amounts of each resource per player.
'''

from sqlalchemy import Column, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from ..db import Base


class PlayerResource(Base):
    __tablename__ = "player_resources"

    id = Column(Integer, primary_key=True)

    player_id = Column(Integer, ForeignKey("players.id"), nullable=False)
    resource_id = Column(Integer, ForeignKey("resource_types.id"), nullable=False)

    amount = Column(Integer, default=0, nullable=False)

    player = relationship("Player")
    resource = relationship("ResourceType")

    __table_args__ = (
        UniqueConstraint("player_id", "resource_id", name="uix_player_resource"),
    )
