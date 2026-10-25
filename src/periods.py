"""Helpers for time periods. A period is identified by its START date as 'YYYY-MM-DD' (UTC).

day   -> the day itself
week  -> the Monday of that week
month -> the 1st of that month

The same rule is implemented in JavaScript inside the MapReduce map function, so Python
and MongoDB label every post with the identical period (this is checked by tests).
"""
from datetime import date, datetime, timedelta


def to_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def period_start(value, granularity: str) -> str:
    d = to_date(value)
    if granularity == "day":
        start = d
    elif granularity == "week":
        start = d - timedelta(days=d.weekday())  # Monday
    elif granularity == "month":
        start = d.replace(day=1)
    else:
        raise ValueError(f"Unknown granularity: {granularity}")
    return start.isoformat()


def next_period(period: str, granularity: str) -> str:
    d = to_date(period)
    if granularity == "day":
        nxt = d + timedelta(days=1)
    elif granularity == "week":
        nxt = d + timedelta(days=7)
    elif granularity == "month":
        nxt = date(d.year + (d.month == 12), 1 if d.month == 12 else d.month + 1, 1)
    else:
        raise ValueError(f"Unknown granularity: {granularity}")
    return nxt.isoformat()


def period_range(start: str, end: str, granularity: str) -> list:
    """All periods from start to end inclusive (both must already be period starts)."""
    periods, current = [], start
    while current <= end:
        periods.append(current)
        current = next_period(current, granularity)
    return periods
