"""Utility helpers for date range normalization and validation."""

from __future__ import annotations
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple


def resolve_date_range(
    *,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
    days: Optional[int] = None,
    default_days_back: int = 1,
) -> Tuple[datetime, datetime]:
    """Resolve a (start, end) UTC-aware datetime range.

    Priority:
      1. Explicit start & end
      2. days back from now (UTC)
      3. default_days_back

    Ensures both datetimes are timezone-aware (UTC) and start <= end.
    """
    now = datetime.now(timezone.utc)
    if start and end:
        s = _ensure_utc(start)
        e = _ensure_utc(end)
    elif days:
        e = now
        s = e - timedelta(days=days)
    else:
        e = now
        s = e - timedelta(days=default_days_back)
    if s > e:
        raise ValueError("start date must be before or equal to end date")
    return s, e


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
