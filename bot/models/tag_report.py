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

    # Who reported it
    user_id = Column(BigInteger, index=True, nullable=False)
    username = Column(String(100), nullable=False)  # "Name#1234"

    # e.g. "normal" or "proxy"
    tag_type = Column(String(50), nullable=False)

    # How many tags
    count = Column(Integer, nullable=False)

    # Channel where the alert was sent (optional)
    channel_id = Column(BigInteger, nullable=True)

    # Raw UTC timestamp for queries
    timestamp_utc = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False
    )

    # Human-readable timestamp like "December 25th 2025 at 8:30 PM UTC"
    timestamp_human = Column(String(64), nullable=False)
