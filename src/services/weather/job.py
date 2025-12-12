"""Orchestrates weather ingestion runs."""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from psycopg2.extensions import connection as PgConnection

from .config import DatabaseConfig, LocationConfig, WEEKDAY_NAMES
from .datasource import (
    build_daily_context,
    build_window_metrics,
    dump_dry_run_results,
    fetch_weather_forecast,
    transform_hourly_weather,
)
from .persistence import (
    ensure_hourly_table_exists,
    ensure_location_table_exists,
    ensure_window_table_exists,
    get_db_connection,
    upsert_hourly_weather_rows,
    upsert_locations_and_get_ids,
    upsert_window_metrics_rows,
)


def determine_date_range(start: Optional[str], end: Optional[str]) -> Tuple[str, str]:
    if start:
        start_date = date.fromisoformat(start)
    else:
        start_date = date.today() - timedelta(days=1)

    if end:
        end_date = date.fromisoformat(end)
    else:
        end_date = start_date

    if end_date < start_date:
        raise ValueError("end-date cannot be earlier than start-date")

    return start_date.isoformat(), end_date.isoformat()


def _dates_in_range(start_iso: str, end_iso: str) -> List[date]:
    start_day = date.fromisoformat(start_iso)
    end_day = date.fromisoformat(end_iso)
    delta = (end_day - start_day).days
    return [start_day + timedelta(days=offset) for offset in range(delta + 1)]


def _weekday_name(index: int) -> str:
    normalized = index % len(WEEKDAY_NAMES)
    return WEEKDAY_NAMES[normalized]


def _format_weekday_set(days: Iterable[int]) -> str:
    names = sorted({_weekday_name(day) for day in days})
    return ", ".join(names) if names else "none"


class WeatherIngestJob:
    """Coordinates fetching Open-Meteo data and persisting/dumping it."""

    def __init__(
        self,
        db_config: DatabaseConfig,
        locations: List[LocationConfig],
        dump_dir: Optional[Path] = None,
    ) -> None:
        self.db_config = db_config
        self.locations = locations
        self.dump_dir = dump_dir or Path("request_dumps")
        self.dump_dir.mkdir(exist_ok=True)

    def run(self, start_date: str, end_date: str, dry_run: bool) -> None:
        conn: Optional[PgConnection] = None
        location_ids: Dict[Tuple[str, str], int] = {}
        requested_days = _dates_in_range(start_date, end_date)

        if not dry_run:
            conn = get_db_connection(self.db_config)
            ensure_location_table_exists(conn)
            ensure_hourly_table_exists(conn)
            ensure_window_table_exists(conn)
            location_ids = upsert_locations_and_get_ids(conn, self.locations)

        for location in self.locations:
            if not location.active:
                print(f"⏭️ Skipping inactive location {location.name} ({location.city}, {location.state})")
                continue

            open_days = [day for day in requested_days if location.is_open_on(day)]
            if not open_days:
                print(
                    f"🚫 Skipping {location.name}: closed for {start_date} to {end_date}. "
                    f"Open weekdays: {_format_weekday_set(location.open_weekdays)}."
                )
                continue

            friendly_open_days = ", ".join(
                f"{day.isoformat()} ({_weekday_name(day.weekday())})" for day in open_days
            )
            print(
                "📅 Fetching hourly weather for open days "
                f"{friendly_open_days} "
                f"at {location.name} ({location.city}, {location.state})..."
            )

            location_key = (location.name, location.address)
            location_db_id = location_ids.get(location_key) if conn is not None else None
            if conn is not None and location_db_id is None:
                raise RuntimeError(f"No database id found for location {location.name} ({location.address})")

            location_hourly_rows: List[Dict[str, Any]] = []
            location_window_rows: List[Dict[str, Any]] = []

            for target_day in open_days:
                day_iso = target_day.isoformat()
                print(f"   ↻ Fetching weather for {day_iso}")
                forecast = fetch_weather_forecast(day_iso, day_iso, location)
                hourly_rows = transform_hourly_weather(forecast["hourly"], location, location_db_id)
                daily_context = build_daily_context(forecast["daily"])
                window_rows = build_window_metrics(hourly_rows, location, daily_context, location_db_id)
                location_hourly_rows.extend(hourly_rows)
                location_window_rows.extend(window_rows)

            if dry_run:
                dump_path = dump_dry_run_results(
                    start_date=start_date,
                    end_date=end_date,
                    location=location,
                    hourly_rows=location_hourly_rows,
                    window_rows=location_window_rows,
                    dump_dir=self.dump_dir,
                    processed_dates=open_days,
                )
                print("🔎 Dry run – showing first few hourly rows:")
                for row in location_hourly_rows[:5]:
                    print(row)
                print(f"Total hourly rows for {location.name}: {len(location_hourly_rows)}")
                print("🔎 Derived window metrics:")
                for row in location_window_rows:
                    print(row)
                print(f"💾 Full dry run output saved to {dump_path}")
                continue

            if conn is None:
                raise RuntimeError("Database connection required for non dry-run mode")

            upsert_hourly_weather_rows(conn, location_hourly_rows)
            upsert_window_metrics_rows(conn, location_window_rows)

            print(f"✅ Inserted/updated {len(location_hourly_rows)} rows into weather_hourly for {location.name}.")
            print(
                "✅ Inserted/updated "
                f"{len(location_window_rows)} rows into weather_window_metrics for {location.name}."
            )

        if conn:
            conn.close()


__all__ = [
    "WeatherIngestJob",
    "determine_date_range",
]
