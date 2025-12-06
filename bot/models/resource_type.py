'''
Name: ResourceType Model
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Define dynamic resource types (Money, Tech Points, etc.).
'''

from sqlalchemy import Column, Integer, String, Boolean
from ..db import Base


class ResourceType(Base):
    __tablename__ = "resource_types"

    id = Column(Integer, primary_key=True)

    # Internal key, used in code (e.g., "money", "donated_money", "tech_points")
    key = Column(String(50), unique=True, nullable=False)

    # Human-friendly name
    display_name = Column(String(100), nullable=False)

    # If you ever want to “turn off” a resource without deleting it
    is_active = Column(Boolean, default=True, nullable=False)
