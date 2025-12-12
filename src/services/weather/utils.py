"""Utility helpers for weather services."""

from __future__ import annotations

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo


def seconds_until_next_run(now: datetime, target_time: time, tz: ZoneInfo) -> float:
    """Seconds until the next target run time in the provided timezone."""
    target = datetime.combine(now.date(), target_time, tzinfo=tz)
    if now >= target:
        target += timedelta(days=1)
    return (target - now).total_seconds()


__all__ = ["seconds_until_next_run"]
