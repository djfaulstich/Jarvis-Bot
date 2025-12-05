'''
Name: Models Package
Type: Module
User: Bot
Last Updated: 2025-12-04
Function: Aggregate ORM models for easy import.
'''

from .user_profile import UserProfile
from .tag_report import TagReport

__all__ = [
    "UserProfile",
    "TagReport",
]
