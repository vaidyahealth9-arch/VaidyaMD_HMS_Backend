"""
VaidyaMD HMS — Canonical Timezone & Timestamp Utilities
Enforces Indian Standard Time (IST / Asia/Kolkata, UTC+05:30) for storage,
timestamps, and API response serialization.
"""
from datetime import datetime, date
from zoneinfo import ZoneInfo
from typing import Optional

# Canonical Clinical Timezone for Indian Healthcare Operations
IST = ZoneInfo("Asia/Kolkata")


def get_now_ist() -> datetime:
    """Return timezone-aware datetime in Indian Standard Time (Asia/Kolkata, UTC+05:30)."""
    return datetime.now(IST)


def get_now_ist_naive() -> datetime:
    """
    Return current wall-clock datetime in IST as a naive datetime.
    Used for SQLAlchemy models using TIMESTAMP WITHOUT TIME ZONE columns so that
    the timestamp saved in the database reflects actual Indian Standard Time.
    """
    return datetime.now(IST).replace(tzinfo=None)


def get_today_ist() -> date:
    """
    Return current calendar date in IST.
    Prevents UTC midnight boundary rollbacks where Indian local time between
    00:00 and 05:30 is still the previous calendar day in UTC.
    """
    return datetime.now(IST).date()


def to_ist_iso(dt: Optional[datetime]) -> Optional[str]:
    """
    Serialize datetime to ISO-8601 with explicit IST (+05:30) timezone offset.
    If dt is naive, it assumes it represents IST wall-clock time and attaches +05:30.
    If dt is timezone-aware, it converts it to IST.
    """
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=IST)
    else:
        dt = dt.astimezone(IST)
    return dt.isoformat()
