from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo


def now_local(tz_name: str) -> datetime:
    return datetime.now(ZoneInfo(tz_name))


def infer_time_of_day(hour: int) -> str:
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 22:
        return "evening"
    return "night"
