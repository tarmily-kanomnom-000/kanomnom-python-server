"""Configuration objects and defaults for weather ingestion."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, time
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DatabaseConfig:
    host: str
    port: int
    dbname: str
    user: str
    password: str


@dataclass
class LocationConfig:
    name: str
    latitude: float
    longitude: float
    timezone: str
    interest_hour_start: int
    interest_hour_end: int
    address: str
    city: str
    state: str
    postal_code: str
    open_weekdays: Tuple[int, ...]
    active: bool = True
    notes: Optional[str] = None

    def is_open_on(self, target_day: date) -> bool:
        """Return True when the store is open on the provided date."""
        return target_day.weekday() in self.open_weekdays


DEFAULT_LOCATIONS: List[LocationConfig] = [
    LocationConfig(
        name="Market at the Fareway",
        latitude=40.074176,
        longitude=-75.202588,
        timezone="America/New_York",
        interest_hour_start=8,
        interest_hour_end=22,
        address="8221 Germantown Ave",
        city="Philadelphia",
        state="PA",
        postal_code="19118",
        open_weekdays=(2, 3, 4, 5, 6),
        active=True,
        notes="Flagship bakery and production kitchen",
    ),
]

DEFAULT_DATABASE_CONFIG = DatabaseConfig(
    host=os.environ.get("WEATHER_DB_HOST", "YOUR_DB_HOST"),
    port=int(os.environ.get("WEATHER_DB_PORT", "5432")),
    dbname=os.environ.get("WEATHER_DB_NAME", "YOUR_DB_NAME"),
    user=os.environ.get("WEATHER_DB_USER", "YOUR_DB_USER"),
    password=os.environ.get("WEATHER_DB_PASSWORD", "YOUR_DB_PASSWORD"),
)

WEATHER_FETCH_TIME = time(hour=5, minute=0)


def weather_scheduler_timezone() -> ZoneInfo:
    """Resolve the timezone used for scheduling weather ingestion."""
    env_tz = os.environ.get("SERVER_TIMEZONE")
    if env_tz:
        return ZoneInfo(env_tz)

    local_tz = datetime.now().astimezone().tzinfo
    if isinstance(local_tz, ZoneInfo):
        return local_tz
    if local_tz:
        try:
            return ZoneInfo(str(local_tz))
        except Exception:
            pass
    return ZoneInfo("UTC")


WEEKDAY_NAMES: Tuple[str, ...] = (
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
)


__all__ = [
    "DatabaseConfig",
    "LocationConfig",
    "DEFAULT_LOCATIONS",
    "DEFAULT_DATABASE_CONFIG",
    "WEATHER_FETCH_TIME",
    "weather_scheduler_timezone",
    "WEEKDAY_NAMES",
]
