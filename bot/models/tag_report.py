'''
Name: TagReport Model
Type: Function
User: Bot
Last Updated: 2025-12-04
Function: Store tag events with user, type, count, and human-readable time.
'''

from sqlalchemy import Column, Integer, String, BigInteger, DateTime
import datetime

from ..db import Base


class TagReport(Base):
    __tablename__ = "tag_reports"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(BigInteger, index=True, nullable=False)                    # Who reported it
    username = Column(String(100), nullable=False)                              # "Name#1234"
    tag_type = Column(String(50), nullable=False)                               # e.g. "normal" or "proxy"
    count = Column(Integer, nullable=False)                                     # How many tags
    timestamp_utc = Column(DateTime, default=datetime.datetime, nullable=False) # Raw UTC timestamp for queries
    timestamp_human = Column(String(64), nullable=False)                        # Human-readable timestamp like "December 25th 2025 at 8:30 PM UTC"

