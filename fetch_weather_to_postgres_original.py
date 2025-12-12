#!/usr/bin/env python3
"""
Fetch hourly weather from Open-Meteo and store it into PostgreSQL for one or more locations.

 - Always pulls hourly metrics into `weather_hourly` for each location's configured hours of interest.
- Also writes windowed derived metrics into `weather_window_metrics`
  for morning (9-11), lunch (11-14), mid-day (14-17), dinner (17-21).
- Default: fetch yesterday's data (start=end). Override with --start-date/--end-date.
- Locations are defined in-script via LOCATIONS (list of LocationConfig).

Usage examples:
    python fetch_weather_to_postgres.py
    python fetch_weather_to_postgres.py --start-date 2025-01-01 --end-date 2025-01-07
    python fetch_weather_to_postgres.py --dry-run
"""

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import psycopg2
import requests
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_batch

# ============================
# 🔐 CONFIG: FILL THESE IN
# ============================

DB_CONFIG = {
    "host": "YOUR_DB_HOST",  # e.g. "localhost" or "db" (if in Docker)
    "port": 5432,  # default PostgreSQL port
    "dbname": "YOUR_DB_NAME",
    "user": "YOUR_DB_USER",
    "password": "YOUR_DB_PASSWORD",
}

# Philadelphia (default) configuration constants
PHILADELPHIA_LOCATION_NAME = "Market at the Fareway"
PHILADELPHIA_LATITUDE = 40.074176
PHILADELPHIA_LONGITUDE = -75.202588
PHILADELPHIA_TIMEZONE = "America/New_York"
PHILADELPHIA_INTEREST_HOUR_START = 8  # earliest weather hour we care about
PHILADELPHIA_INTEREST_HOUR_END = 22  # last (exclusive) hour to retain
PHILADELPHIA_ADDRESS = "8221 Germantown Ave"
PHILADELPHIA_CITY = "Philadelphia"
PHILADELPHIA_STATE = "PA"
PHILADELPHIA_POSTAL_CODE = "19118"

HOURLY_VARIABLES = [
    "temperature_2m",
    "apparent_temperature",
    "relativehumidity_2m",
    "dewpoint_2m",
    "precipitation",
    "rain",
    "snowfall",
    "cloudcover",
    "windspeed_10m",
    "windgusts_10m",
    "winddirection_10m",
    "pressure_msl",
    "visibility",
    "uv_index",
    "precipitation_probability",
    "weathercode",
    "is_day",
]

DAILY_VARIABLES = [
    "sunrise",
    "sunset",
    "temperature_2m_max",
    "temperature_2m_min",
    "apparent_temperature_max",
    "apparent_temperature_min",
]

WINDOWS = [
    {"name": "morning", "start_hour": 9, "end_hour": 11},
    {"name": "lunch", "start_hour": 11, "end_hour": 14},
    {"name": "mid_day", "start_hour": 14, "end_hour": 17},
    {"name": "dinner", "start_hour": 17, "end_hour": 21},
]


@dataclass(frozen=True)
class MetricDocumentation:
    description: str
    units: Optional[str]
    source: str


HOURLY_METRIC_DOCS: Dict[str, MetricDocumentation] = {
    "temp_f": MetricDocumentation(
        description="Ambient air temperature measured 2m above ground and converted from Celsius",
        units="degF",
        source="Open-Meteo hourly.temperature_2m",
    ),
    "apparent_temp_f": MetricDocumentation(
        description="Feels-like temperature converted from Celsius",
        units="degF",
        source="Open-Meteo hourly.apparent_temperature",
    ),
    "relative_humidity_percent": MetricDocumentation(
        description="Relative humidity reported as percent saturation",
        units="percent",
        source="Open-Meteo hourly.relativehumidity_2m",
    ),
    "dew_point_f": MetricDocumentation(
        description="Dew point temperature converted to Fahrenheit",
        units="degF",
        source="Open-Meteo hourly.dewpoint_2m",
    ),
    "precip_mm": MetricDocumentation(
        description="Total precipitation depth including all forms (rain, freezing rain, snow)",
        units="millimeters",
        source="Open-Meteo hourly.precipitation",
    ),
    "rain_mm": MetricDocumentation(
        description="Liquid rain depth accumulated during the hour",
        units="millimeters",
        source="Open-Meteo hourly.rain",
    ),
    "snowfall_mm": MetricDocumentation(
        description="Snow water equivalent converted to millimeters",
        units="millimeters",
        source="Open-Meteo hourly.snowfall",
    ),
    "cloud_cover_percent": MetricDocumentation(
        description="Fraction of sky covered by clouds over the hour",
        units="percent",
        source="Open-Meteo hourly.cloudcover",
    ),
    "wind_speed_10m_mps": MetricDocumentation(
        description="Sustained wind speed measured at 10 meters above ground",
        units="m/s",
        source="Open-Meteo hourly.windspeed_10m",
    ),
    "wind_gusts_10m_mps": MetricDocumentation(
        description="Maximum wind gust measured at 10 meters for the hour",
        units="m/s",
        source="Open-Meteo hourly.windgusts_10m",
    ),
    "wind_direction_10m_deg": MetricDocumentation(
        description="Wind bearing using meteorological convention (0 deg = north, clockwise)",
        units="degrees",
        source="Open-Meteo hourly.winddirection_10m",
    ),
    "pressure_msl_hpa": MetricDocumentation(
        description="Mean sea level pressure adjusted from the model's surface pressure",
        units="hPa",
        source="Open-Meteo hourly.pressure_msl",
    ),
    "visibility_m": MetricDocumentation(
        description="Horizontal visibility distance",
        units="meters",
        source="Open-Meteo hourly.visibility",
    ),
    "uv_index": MetricDocumentation(
        description="Ultraviolet index following WHO guidance",
        units="index",
        source="Open-Meteo hourly.uv_index",
    ),
    "precip_probability_percent": MetricDocumentation(
        description="Probability that measurable precipitation occurs within the hour",
        units="percent",
        source="Open-Meteo hourly.precipitation_probability",
    ),
    "weather_code": MetricDocumentation(
        description="WMO weather code summarizing observed or forecast conditions",
        units=None,
        source="Open-Meteo hourly.weathercode",
    ),
    "is_day": MetricDocumentation(
        description="Day (True) or night (False) indicator based on solar position",
        units=None,
        source="Open-Meteo hourly.is_day",
    ),
}

WINDOW_METRIC_DOCS: Dict[str, MetricDocumentation] = {
    "temp_avg_f": MetricDocumentation(
        description="Average Fahrenheit temperature for hours within the window",
        units="degF",
        source="Derived mean of hourly.temp_f",
    ),
    "apparent_temp_avg_f": MetricDocumentation(
        description="Average feels-like temperature across the window",
        units="degF",
        source="Derived mean of hourly.apparent_temp_f",
    ),
    "precip_total_mm": MetricDocumentation(
        description="Sum of precipitation depth (all forms) inside the window",
        units="millimeters",
        source="Sum of hourly.precip_mm",
    ),
    "rain_total_mm": MetricDocumentation(
        description="Sum of liquid precipitation only during the window",
        units="millimeters",
        source="Sum of hourly.rain_mm",
    ),
    "snowfall_total_mm": MetricDocumentation(
        description="Sum of snow water equivalent for window hours",
        units="millimeters",
        source="Sum of hourly.snowfall_mm",
    ),
    "cloud_cover_avg_percent": MetricDocumentation(
        description="Average cloud cover for sampled hours",
        units="percent",
        source="Mean of hourly.cloud_cover_percent",
    ),
    "wind_speed_max_mps": MetricDocumentation(
        description="Maximum sustained wind speed observed in the window",
        units="m/s",
        source="Max of hourly.wind_speed_10m_mps",
    ),
    "wind_gusts_max_mps": MetricDocumentation(
        description="Maximum gust recorded in the window",
        units="m/s",
        source="Max of hourly.wind_gusts_10m_mps",
    ),
    "wind_direction_avg_deg": MetricDocumentation(
        description="Average of hourly wind bearings using a simple mean",
        units="degrees",
        source="Mean of hourly.wind_direction_10m_deg",
    ),
    "uv_index_max": MetricDocumentation(
        description="Highest UV index across the window",
        units="index",
        source="Max of hourly.uv_index",
    ),
    "precip_probability_avg_percent": MetricDocumentation(
        description="Average probability of precipitation defined by Open-Meteo",
        units="percent",
        source="Mean of hourly.precip_probability_percent",
    ),
    "precip_probability_max_percent": MetricDocumentation(
        description="Maximum precipitation probability in the window",
        units="percent",
        source="Max of hourly.precip_probability_percent",
    ),
    "weather_code": MetricDocumentation(
        description="Dominant WMO weather code across the window",
        units=None,
        source="Mode of hourly.weather_code",
    ),
    "sunrise": MetricDocumentation(
        description="Sunrise time for the calendar day of the window",
        units="timestamp",
        source="Open-Meteo daily.sunrise",
    ),
    "sunset": MetricDocumentation(
        description="Sunset time for the calendar day of the window",
        units="timestamp",
        source="Open-Meteo daily.sunset",
    ),
    "daylight_minutes": MetricDocumentation(
        description="Minutes between sunrise and sunset",
        units="minutes",
        source="Derived from sunrise/sunset",
    ),
    "day_temp_min_f": MetricDocumentation(
        description="Daily minimum temperature converted to Fahrenheit",
        units="degF",
        source="Open-Meteo daily.temperature_2m_min",
    ),
    "day_temp_max_f": MetricDocumentation(
        description="Daily maximum temperature converted to Fahrenheit",
        units="degF",
        source="Open-Meteo daily.temperature_2m_max",
    ),
    "day_apparent_temp_min_f": MetricDocumentation(
        description="Daily minimum feels-like temperature converted to Fahrenheit",
        units="degF",
        source="Open-Meteo daily.apparent_temperature_min",
    ),
    "day_apparent_temp_max_f": MetricDocumentation(
        description="Daily maximum feels-like temperature converted to Fahrenheit",
        units="degF",
        source="Open-Meteo daily.apparent_temperature_max",
    ),
    "sample_count": MetricDocumentation(
        description="Number of hourly samples included in the aggregation",
        units="count",
        source="Derived from hourly row count",
    ),
}

WEATHER_CODE_DESCRIPTIONS: Dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow fall",
    73: "Moderate snow fall",
    75: "Heavy snow fall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

TABLE_METRIC_DOCS: Dict[str, Dict[str, MetricDocumentation]] = {
    "weather_hourly": HOURLY_METRIC_DOCS,
    "weather_window_metrics": WINDOW_METRIC_DOCS,
}


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
    active: bool = True
    notes: Optional[str] = None


def _location_identity(location: LocationConfig) -> Tuple[str, str]:
    """Unique key for identifying a location record in the database."""
    return (location.name, location.address)


PHILADELPHIA_LOCATION = LocationConfig(
    name=PHILADELPHIA_LOCATION_NAME,
    latitude=PHILADELPHIA_LATITUDE,
    longitude=PHILADELPHIA_LONGITUDE,
    timezone=PHILADELPHIA_TIMEZONE,
    interest_hour_start=PHILADELPHIA_INTEREST_HOUR_START,
    interest_hour_end=PHILADELPHIA_INTEREST_HOUR_END,
    address=PHILADELPHIA_ADDRESS,
    city=PHILADELPHIA_CITY,
    state=PHILADELPHIA_STATE,
    postal_code=PHILADELPHIA_POSTAL_CODE,
    active=True,
    notes="Flagship bakery and production kitchen",
)

LOCATIONS: List[LocationConfig] = [
    PHILADELPHIA_LOCATION,
    # Add additional domestic locations here. Toggle `active=False` to keep a
    # closed shop in the database without fetching weather for it.
]

DUMP_DIR = Path("request_dumps")
DUMP_DIR.mkdir(exist_ok=True)


def _format_metric_doc_comment(doc: MetricDocumentation) -> str:
    extras: List[str] = []
    if doc.units:
        extras.append(f"Units: {doc.units}")
    extras.append(f"Source: {doc.source}")
    extras_str = "; ".join(extras)
    return f"{doc.description} ({extras_str})"


def describe_metric_table(table_name: str) -> None:
    normalized = table_name.strip().lower()
    docs = TABLE_METRIC_DOCS.get(normalized)
    if docs is None:
        raise ValueError(f"Unknown table '{table_name}'. Known tables: {', '.join(TABLE_METRIC_DOCS.keys())}")
    print(f"Column documentation for {normalized}:")
    for column, doc in docs.items():
        units_display = doc.units or "unitless"
        print(f" - {column}: {doc.description} [units={units_display}; source={doc.source}]")
    if "weather_code" in docs:
        print(" Weather code legend (WMO):")
        for code, description in sorted(WEATHER_CODE_DESCRIPTIONS.items()):
            print(f"   - {code}: {description}")


def apply_column_comments(
    conn: PgConnection,
    table_name: str,
    docs: Dict[str, MetricDocumentation],
) -> None:
    with conn.cursor() as cur:
        for column, doc in docs.items():
            cur.execute(
                f"COMMENT ON COLUMN {table_name}.{column} IS %s",
                (_format_metric_doc_comment(doc),),
            )
    conn.commit()


# ============================
# Helpers
# ============================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch hourly weather from Open-Meteo and store in PostgreSQL.")
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Default: yesterday.",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Default: same as start-date.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch and print data without writing to database.",
    )
    parser.add_argument(
        "--describe-table",
        type=str,
        help="Print column documentation for either 'weather_hourly' or 'weather_window_metrics' and exit.",
    )
    return parser.parse_args()


def get_default_dates(args: argparse.Namespace) -> Tuple[str, str]:
    """Determine start and end dates (YYYY-MM-DD). Default is yesterday."""
    if args.start_date:
        start = date.fromisoformat(args.start_date)
    else:
        start = date.today() - timedelta(days=1)

    if args.end_date:
        end = date.fromisoformat(args.end_date)
    else:
        end = start

    if end < start:
        raise ValueError("end-date cannot be earlier than start-date")

    return start.isoformat(), end.isoformat()


def fetch_weather_forecast(start_date: str, end_date: str, location: LocationConfig) -> Dict[str, Any]:
    hourly_params = ",".join(HOURLY_VARIABLES)
    daily_params = ",".join(DAILY_VARIABLES)

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={location.latitude}"
        f"&longitude={location.longitude}"
        f"&hourly={hourly_params}"
        f"&daily={daily_params}"
        f"&timezone={location.timezone}"
        f"&start_date={start_date}"
        f"&end_date={end_date}"
    )

    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    if "hourly" not in data or "time" not in data["hourly"]:
        raise RuntimeError(f"Unexpected Open-Meteo response: {json.dumps(data, indent=2)}")
    if "daily" not in data or "time" not in data["daily"]:
        raise RuntimeError(f"Missing daily block in Open-Meteo response: {json.dumps(data, indent=2)}")

    return data


def _safe_item(values: List[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


def transform_hourly_weather(
    hourly: Dict[str, Any],
    location: LocationConfig,
    location_id: Optional[int],
) -> List[Dict[str, Any]]:
    """
    Transform Open-Meteo hourly response into a list of rows for weather_hourly.
    Stores an aware timestamp using the configured timezone and filters to the
    location's hours-of-interest window (interest_hour_start <= hour < interest_hour_end).
    """
    times = hourly["time"]
    tz = ZoneInfo(location.timezone)
    interest_hour_start = location.interest_hour_start
    interest_hour_end = location.interest_hour_end

    get = hourly.get
    temperature_c = get("temperature_2m", [])
    apparent_temperature_c = get("apparent_temperature", [])
    humidity = get("relativehumidity_2m", [])
    dew_point = get("dewpoint_2m", [])
    precipitation = get("precipitation", [])
    rain = get("rain", [])
    snowfall = get("snowfall", [])
    cloud_cover = get("cloudcover", [])
    wind_speed_10m = get("windspeed_10m", [])
    wind_gusts_10m = get("windgusts_10m", [])
    wind_direction_10m = get("winddirection_10m", [])
    pressure_msl = get("pressure_msl", [])
    visibility = get("visibility", [])
    uv_index = get("uv_index", [])
    precip_probability = get("precipitation_probability", [])
    weather_code = get("weathercode", [])
    is_day_values = get("is_day", [])

    rows: List[Dict[str, Any]] = []

    for i, time_str in enumerate(times):
        observed_naive = datetime.fromisoformat(time_str)
        observed_at = observed_naive.replace(tzinfo=tz)

        local_hour = observed_at.hour
        if local_hour < interest_hour_start or local_hour >= interest_hour_end:
            continue

        is_day_value = _safe_item(is_day_values, i)

        temp_c = _safe_item(temperature_c, i)
        apparent_c = _safe_item(apparent_temperature_c, i)
        dew_point_c = _safe_item(dew_point, i)

        rows.append(
            {
                "location_id": location_id,
                "location_name": location.name,
                "location_latitude": location.latitude,
                "location_longitude": location.longitude,
                "location_timezone": location.timezone,
                "observed_at": observed_at,
                "temp_f": None if temp_c is None else (temp_c * 9 / 5) + 32,
                "apparent_temp_f": None if apparent_c is None else (apparent_c * 9 / 5) + 32,
                "relative_humidity_percent": _safe_item(humidity, i),
                "dew_point_f": None if dew_point_c is None else (dew_point_c * 9 / 5) + 32,
                "precip_mm": _safe_item(precipitation, i),
                "rain_mm": _safe_item(rain, i),
                "snowfall_mm": _safe_item(snowfall, i),
                "cloud_cover_percent": _safe_item(cloud_cover, i),
                "wind_speed_10m_mps": _safe_item(wind_speed_10m, i),
                "wind_gusts_10m_mps": _safe_item(wind_gusts_10m, i),
                "wind_direction_10m_deg": _safe_item(wind_direction_10m, i),
                "pressure_msl_hpa": _safe_item(pressure_msl, i),
                "visibility_m": _safe_item(visibility, i),
                "uv_index": _safe_item(uv_index, i),
                "precip_probability_percent": _safe_item(precip_probability, i),
                "weather_code": _safe_item(weather_code, i),
                "is_day": (None if is_day_value is None else bool(is_day_value)),
            }
        )

    return rows


def _mean_or_none(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    if not clean:
        return None
    return sum(clean) / len(clean)


def _max_or_none(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return max(clean) if clean else None


def _sum_or_none(values: List[Optional[float]]) -> Optional[float]:
    clean = [v for v in values if v is not None]
    return sum(clean) if clean else None


def _mode_or_none(values: List[Any]) -> Optional[Any]:
    counts: Dict[Any, int] = {}
    best_value: Optional[Any] = None
    best_count = 0
    for value in values:
        counts[value] = counts.get(value, 0) + 1
        if counts[value] > best_count:
            best_value = value
            best_count = counts[value]
    return best_value


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(value)


def _daylight_minutes(sunrise: Optional[datetime], sunset: Optional[datetime]) -> Optional[int]:
    if sunrise is None or sunset is None:
        return None
    delta = sunset - sunrise
    return int(delta.total_seconds() // 60)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def _serialize_rows_for_dump(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [{k: _json_safe_value(v) for k, v in row.items()} for row in rows]


def _sanitize_location_name(name: str) -> str:
    sanitized = "".join(ch.lower() if ch.isalnum() else "_" for ch in name)
    sanitized = sanitized.strip("_")
    return sanitized or "location"


def dump_dry_run_results(
    start_date: str,
    end_date: str,
    location: LocationConfig,
    hourly_rows: List[Dict[str, Any]],
    window_rows: List[Dict[str, Any]],
) -> Path:
    timestamp = datetime.now(tz=ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%S")
    filename = f"weather_dry_run_{_sanitize_location_name(location.name)}_" f"{start_date}_{end_date}_{timestamp}.json"
    payload = {
        "metadata": {
            "start_date": start_date,
            "end_date": end_date,
            "location": {
                "name": location.name,
                "latitude": location.latitude,
                "longitude": location.longitude,
                "timezone": location.timezone,
                "interest_hour_start": location.interest_hour_start,
                "interest_hour_end": location.interest_hour_end,
                "address": location.address,
                "city": location.city,
                "state": location.state,
                "postal_code": location.postal_code,
                "active": location.active,
                "notes": location.notes,
            },
            "hourly_row_count": len(hourly_rows),
            "window_row_count": len(window_rows),
            "generated_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
        },
        "hourly_rows": _serialize_rows_for_dump(hourly_rows),
        "window_rows": _serialize_rows_for_dump(window_rows),
    }

    output_path = DUMP_DIR / filename
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    return output_path


def build_daily_context(daily: Dict[str, Any]) -> Dict[date, Dict[str, Any]]:
    days = daily.get("time", [])
    sunrise = daily.get("sunrise", [])
    sunset = daily.get("sunset", [])
    temp_max = daily.get("temperature_2m_max", [])
    temp_min = daily.get("temperature_2m_min", [])
    apparent_max = daily.get("apparent_temperature_max", [])
    apparent_min = daily.get("apparent_temperature_min", [])

    context: Dict[date, Dict[str, Any]] = {}
    for i, day_str in enumerate(days):
        day_obj = date.fromisoformat(day_str)
        sunrise_dt = _parse_iso_datetime(_safe_item(sunrise, i))
        sunset_dt = _parse_iso_datetime(_safe_item(sunset, i))
        temp_max_c = _safe_item(temp_max, i)
        temp_min_c = _safe_item(temp_min, i)
        apparent_max_c = _safe_item(apparent_max, i)
        apparent_min_c = _safe_item(apparent_min, i)
        context[day_obj] = {
            "sunrise": sunrise_dt,
            "sunset": sunset_dt,
            "daylight_minutes": _daylight_minutes(sunrise_dt, sunset_dt),
            "temperature_max_f": None if temp_max_c is None else (temp_max_c * 9 / 5) + 32,
            "temperature_min_f": None if temp_min_c is None else (temp_min_c * 9 / 5) + 32,
            "apparent_temperature_max_f": None if apparent_max_c is None else (apparent_max_c * 9 / 5) + 32,
            "apparent_temperature_min_f": None if apparent_min_c is None else (apparent_min_c * 9 / 5) + 32,
        }

    return context


def build_window_metrics(
    hourly_rows: List[Dict[str, Any]],
    location: LocationConfig,
    daily_context: Dict[date, Dict[str, Any]],
    location_id: Optional[int],
) -> List[Dict[str, Any]]:
    """Aggregate hourly rows into windowed summaries enriched with daily context."""
    if not hourly_rows:
        return []

    tz = ZoneInfo(location.timezone)
    by_date: Dict[date, List[Dict[str, Any]]] = {}
    for row in hourly_rows:
        observed_at: datetime = row["observed_at"]
        local_dt = observed_at.astimezone(tz)
        by_date.setdefault(local_dt.date(), []).append({**row, "observed_local": local_dt})

    window_rows: List[Dict[str, Any]] = []

    for day, rows_for_day in by_date.items():
        day_ctx = daily_context.get(day, {})
        for window in WINDOWS:
            start = datetime.combine(day, time(hour=window["start_hour"], tzinfo=tz))
            end = datetime.combine(day, time(hour=window["end_hour"], tzinfo=tz))

            window_slice = [r for r in rows_for_day if start <= r["observed_local"] < end]

            if not window_slice:
                continue

            temp_values = [r["temp_f"] for r in window_slice]
            apparent_values = [r["apparent_temp_f"] for r in window_slice]
            precip_values = [r["precip_mm"] for r in window_slice]
            rain_values = [r["rain_mm"] for r in window_slice]
            snowfall_values = [r["snowfall_mm"] for r in window_slice]
            cloud_values = [r["cloud_cover_percent"] for r in window_slice]
            wind_speed_values = [r["wind_speed_10m_mps"] for r in window_slice]
            wind_gust_values = [r["wind_gusts_10m_mps"] for r in window_slice]
            wind_dir_values = [r["wind_direction_10m_deg"] for r in window_slice]
            uv_values = [r["uv_index"] for r in window_slice]
            precip_probability_values = [r["precip_probability_percent"] for r in window_slice]
            weather_codes = [r["weather_code"] for r in window_slice if r["weather_code"] is not None]

            temp_avg = _mean_or_none(temp_values)
            apparent_avg = _mean_or_none(apparent_values)
            precip_total = _sum_or_none(precip_values)
            rain_total = _sum_or_none(rain_values)
            snowfall_total = _sum_or_none(snowfall_values)
            cloud_avg = _mean_or_none(cloud_values)
            wind_speed_max = _max_or_none(wind_speed_values)
            wind_gust_max = _max_or_none(wind_gust_values)
            wind_dir_avg = _mean_or_none(wind_dir_values)
            uv_max = _max_or_none(uv_values)
            precip_prob_avg = _mean_or_none(precip_probability_values)
            precip_prob_max = _max_or_none(precip_probability_values)
            dominant_weather_code = _mode_or_none(weather_codes)

            window_rows.append(
                {
                    "location_id": location_id,
                    "location_name": location.name,
                    "location_latitude": location.latitude,
                    "location_longitude": location.longitude,
                    "location_timezone": location.timezone,
                    "window_date": day,
                    "window_name": window["name"],
                    "window_start": start,
                    "window_end": end,
                    "temp_avg_f": temp_avg,
                    "apparent_temp_avg_f": apparent_avg,
                    "precip_total_mm": precip_total,
                    "rain_total_mm": rain_total,
                    "snowfall_total_mm": snowfall_total,
                    "cloud_cover_avg_percent": cloud_avg,
                    "wind_speed_max_mps": wind_speed_max,
                    "wind_gusts_max_mps": wind_gust_max,
                    "wind_direction_avg_deg": wind_dir_avg,
                    "uv_index_max": uv_max,
                    "precip_probability_avg_percent": precip_prob_avg,
                    "precip_probability_max_percent": precip_prob_max,
                    "weather_code": dominant_weather_code,
                    "sunrise": day_ctx.get("sunrise"),
                    "sunset": day_ctx.get("sunset"),
                    "daylight_minutes": day_ctx.get("daylight_minutes"),
                    "day_temp_min_f": day_ctx.get("temperature_min_f"),
                    "day_temp_max_f": day_ctx.get("temperature_max_f"),
                    "day_apparent_temp_min_f": day_ctx.get("apparent_temperature_min_f"),
                    "day_apparent_temp_max_f": day_ctx.get("apparent_temperature_max_f"),
                    "sample_count": len(window_slice),
                    "raw_json": json.dumps(
                        {
                            "hours": [r["observed_local"].isoformat() for r in window_slice],
                            "window": window,
                            "_location": {
                                "name": location.name,
                                "latitude": location.latitude,
                                "longitude": location.longitude,
                                "timezone": location.timezone,
                            },
                        }
                    ),
                }
            )

    return window_rows


CREATE_LOCATION_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_locations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    latitude NUMERIC NOT NULL,
    longitude NUMERIC NOT NULL,
    timezone TEXT NOT NULL,
    interest_hour_start INTEGER NOT NULL,
    interest_hour_end INTEGER NOT NULL,
    address TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (name, address)
);
"""


UPSERT_LOCATION_SQL = """
INSERT INTO weather_locations (
    name,
    latitude,
    longitude,
    timezone,
    interest_hour_start,
    interest_hour_end,
    address,
    city,
    state,
    postal_code,
    active,
    notes,
    updated_at
) VALUES (
    %(name)s,
    %(latitude)s,
    %(longitude)s,
    %(timezone)s,
    %(interest_hour_start)s,
    %(interest_hour_end)s,
    %(address)s,
    %(city)s,
    %(state)s,
    %(postal_code)s,
    %(active)s,
    %(notes)s,
    NOW()
)
ON CONFLICT (name, address) DO UPDATE SET
    latitude = EXCLUDED.latitude,
    longitude = EXCLUDED.longitude,
    timezone = EXCLUDED.timezone,
    interest_hour_start = EXCLUDED.interest_hour_start,
    interest_hour_end = EXCLUDED.interest_hour_end,
    city = EXCLUDED.city,
    state = EXCLUDED.state,
    postal_code = EXCLUDED.postal_code,
    active = EXCLUDED.active,
    notes = EXCLUDED.notes,
    updated_at = NOW()
RETURNING id;
"""


CREATE_HOURLY_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_hourly (
    location_id               INTEGER REFERENCES weather_locations(id) ON DELETE RESTRICT,
    observed_at               TIMESTAMPTZ,
    temp_f                    NUMERIC,
    apparent_temp_f           NUMERIC,
    relative_humidity_percent NUMERIC,
    dew_point_f               NUMERIC,
    precip_mm                 NUMERIC,
    rain_mm                   NUMERIC,
    snowfall_mm               NUMERIC,
    cloud_cover_percent       NUMERIC,
    wind_speed_10m_mps        NUMERIC,
    wind_gusts_10m_mps        NUMERIC,
    wind_direction_10m_deg    NUMERIC,
    pressure_msl_hpa          NUMERIC,
    visibility_m              NUMERIC,
    uv_index                  NUMERIC,
    precip_probability_percent NUMERIC,
    weather_code               INTEGER,
    is_day                     BOOLEAN,
    raw_json                  JSONB,
    created_at                TIMESTAMPTZ DEFAULT NOW(),
    updated_at                TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (location_id, observed_at)
);
"""

UPSERT_HOURLY_SQL = """
INSERT INTO weather_hourly (
    location_id,
    observed_at,
    temp_f,
    apparent_temp_f,
    relative_humidity_percent,
    dew_point_f,
    precip_mm,
    rain_mm,
    snowfall_mm,
    cloud_cover_percent,
    wind_speed_10m_mps,
    wind_gusts_10m_mps,
    wind_direction_10m_deg,
    pressure_msl_hpa,
    visibility_m,
    uv_index,
    precip_probability_percent,
    weather_code,
    is_day,
    raw_json,
    updated_at
) VALUES (
    %(location_id)s,
    %(observed_at)s,
    %(temp_f)s,
    %(apparent_temp_f)s,
    %(relative_humidity_percent)s,
    %(dew_point_f)s,
    %(precip_mm)s,
    %(rain_mm)s,
    %(snowfall_mm)s,
    %(cloud_cover_percent)s,
    %(wind_speed_10m_mps)s,
    %(wind_gusts_10m_mps)s,
    %(wind_direction_10m_deg)s,
    %(pressure_msl_hpa)s,
    %(visibility_m)s,
    %(uv_index)s,
    %(precip_probability_percent)s,
    %(weather_code)s,
    %(is_day)s,
    %(raw_json)s,
    NOW()
)
ON CONFLICT (location_id, observed_at) DO UPDATE SET
    temp_f = EXCLUDED.temp_f,
    apparent_temp_f = EXCLUDED.apparent_temp_f,
    relative_humidity_percent = EXCLUDED.relative_humidity_percent,
    dew_point_f = EXCLUDED.dew_point_f,
    precip_mm = EXCLUDED.precip_mm,
    rain_mm = EXCLUDED.rain_mm,
    snowfall_mm = EXCLUDED.snowfall_mm,
    cloud_cover_percent = EXCLUDED.cloud_cover_percent,
    wind_speed_10m_mps = EXCLUDED.wind_speed_10m_mps,
    wind_gusts_10m_mps = EXCLUDED.wind_gusts_10m_mps,
    wind_direction_10m_deg = EXCLUDED.wind_direction_10m_deg,
    pressure_msl_hpa = EXCLUDED.pressure_msl_hpa,
    visibility_m = EXCLUDED.visibility_m,
    uv_index = EXCLUDED.uv_index,
    precip_probability_percent = EXCLUDED.precip_probability_percent,
    weather_code = EXCLUDED.weather_code,
    is_day = EXCLUDED.is_day,
    raw_json = EXCLUDED.raw_json,
    updated_at = NOW();
"""

CREATE_WINDOW_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS weather_window_metrics (
    location_id               INTEGER REFERENCES weather_locations(id) ON DELETE RESTRICT,
    window_date              DATE,
    window_name              TEXT,
    window_start             TIMESTAMPTZ,
    window_end               TIMESTAMPTZ,
    temp_avg_f               NUMERIC,
    apparent_temp_avg_f      NUMERIC,
    precip_total_mm          NUMERIC,
    rain_total_mm            NUMERIC,
    snowfall_total_mm        NUMERIC,
    cloud_cover_avg_percent  NUMERIC,
    wind_speed_max_mps       NUMERIC,
    wind_gusts_max_mps       NUMERIC,
    wind_direction_avg_deg   NUMERIC,
    uv_index_max             NUMERIC,
    precip_probability_avg_percent NUMERIC,
    precip_probability_max_percent NUMERIC,
    weather_code             INTEGER,
    sunrise                  TIMESTAMPTZ,
    sunset                   TIMESTAMPTZ,
    daylight_minutes         INTEGER,
    day_temp_min_f           NUMERIC,
    day_temp_max_f           NUMERIC,
    day_apparent_temp_min_f  NUMERIC,
    day_apparent_temp_max_f  NUMERIC,
    sample_count             INTEGER,
    raw_json                 JSONB,
    created_at               TIMESTAMPTZ DEFAULT NOW(),
    updated_at               TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (location_id, window_date, window_name)
);
"""

UPSERT_WINDOW_SQL = """
INSERT INTO weather_window_metrics (
    location_id,
    window_date,
    window_name,
    window_start,
    window_end,
    temp_avg_f,
    apparent_temp_avg_f,
    precip_total_mm,
    rain_total_mm,
    snowfall_total_mm,
    cloud_cover_avg_percent,
    wind_speed_max_mps,
    wind_gusts_max_mps,
    wind_direction_avg_deg,
    uv_index_max,
    precip_probability_avg_percent,
    precip_probability_max_percent,
    weather_code,
    sunrise,
    sunset,
    daylight_minutes,
    day_temp_min_f,
    day_temp_max_f,
    day_apparent_temp_min_f,
    day_apparent_temp_max_f,
    sample_count,
    raw_json,
    updated_at
) VALUES (
    %(location_id)s,
    %(window_date)s,
    %(window_name)s,
    %(window_start)s,
    %(window_end)s,
    %(temp_avg_f)s,
    %(apparent_temp_avg_f)s,
    %(precip_total_mm)s,
    %(rain_total_mm)s,
    %(snowfall_total_mm)s,
    %(cloud_cover_avg_percent)s,
    %(wind_speed_max_mps)s,
    %(wind_gusts_max_mps)s,
    %(wind_direction_avg_deg)s,
    %(uv_index_max)s,
    %(precip_probability_avg_percent)s,
    %(precip_probability_max_percent)s,
    %(weather_code)s,
    %(sunrise)s,
    %(sunset)s,
    %(daylight_minutes)s,
    %(day_temp_min_f)s,
    %(day_temp_max_f)s,
    %(day_apparent_temp_min_f)s,
    %(day_apparent_temp_max_f)s,
    %(sample_count)s,
    %(raw_json)s,
    NOW()
)
ON CONFLICT (location_id, window_date, window_name) DO UPDATE SET
    temp_avg_f = EXCLUDED.temp_avg_f,
    apparent_temp_avg_f = EXCLUDED.apparent_temp_avg_f,
    precip_total_mm = EXCLUDED.precip_total_mm,
    rain_total_mm = EXCLUDED.rain_total_mm,
    snowfall_total_mm = EXCLUDED.snowfall_total_mm,
    cloud_cover_avg_percent = EXCLUDED.cloud_cover_avg_percent,
    wind_speed_max_mps = EXCLUDED.wind_speed_max_mps,
    wind_gusts_max_mps = EXCLUDED.wind_gusts_max_mps,
    wind_direction_avg_deg = EXCLUDED.wind_direction_avg_deg,
    uv_index_max = EXCLUDED.uv_index_max,
    precip_probability_avg_percent = EXCLUDED.precip_probability_avg_percent,
    precip_probability_max_percent = EXCLUDED.precip_probability_max_percent,
    weather_code = EXCLUDED.weather_code,
    sunrise = EXCLUDED.sunrise,
    sunset = EXCLUDED.sunset,
    daylight_minutes = EXCLUDED.daylight_minutes,
    day_temp_min_f = EXCLUDED.day_temp_min_f,
    day_temp_max_f = EXCLUDED.day_temp_max_f,
    day_apparent_temp_min_f = EXCLUDED.day_apparent_temp_min_f,
    day_apparent_temp_max_f = EXCLUDED.day_apparent_temp_max_f,
    sample_count = EXCLUDED.sample_count,
    raw_json = EXCLUDED.raw_json,
    updated_at = NOW();
"""


def get_db_connection() -> PgConnection:
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            dbname=DB_CONFIG["dbname"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
        )
        return conn
    except Exception as e:
        print("❌ Failed to connect to PostgreSQL:", e, file=sys.stderr)
        sys.exit(1)


def ensure_location_table_exists(conn: PgConnection) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_LOCATION_TABLE_SQL)
    conn.commit()


def upsert_locations_and_get_ids(conn: PgConnection, locations: List[LocationConfig]) -> Dict[Tuple[str, str], int]:
    ids: Dict[Tuple[str, str], int] = {}
    with conn.cursor() as cur:
        for location in locations:
            cur.execute(
                UPSERT_LOCATION_SQL,
                {
                    "name": location.name,
                    "latitude": location.latitude,
                    "longitude": location.longitude,
                    "timezone": location.timezone,
                    "interest_hour_start": location.interest_hour_start,
                    "interest_hour_end": location.interest_hour_end,
                    "address": location.address,
                    "city": location.city,
                    "state": location.state,
                    "postal_code": location.postal_code,
                    "active": location.active,
                    "notes": location.notes,
                },
            )
            location_id = cur.fetchone()[0]
            ids[_location_identity(location)] = location_id
    conn.commit()
    return ids


def ensure_hourly_table_exists(conn: PgConnection) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_HOURLY_TABLE_SQL)
    conn.commit()
    apply_column_comments(conn, "weather_hourly", HOURLY_METRIC_DOCS)


def upsert_hourly_weather_rows(conn: PgConnection, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("No rows to insert.")
        return

    for row in rows:
        if row.get("location_id") is None:
            raise ValueError("Cannot upsert hourly weather row without location_id")

    with conn.cursor() as cur:
        execute_batch(cur, UPSERT_HOURLY_SQL, rows, page_size=500)
    conn.commit()


def ensure_window_table_exists(conn: PgConnection) -> None:
    with conn.cursor() as cur:
        cur.execute(CREATE_WINDOW_TABLE_SQL)
    conn.commit()
    apply_column_comments(conn, "weather_window_metrics", WINDOW_METRIC_DOCS)


def upsert_window_metrics_rows(conn: PgConnection, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        print("No window metrics to insert.")
        return

    for row in rows:
        if row.get("location_id") is None:
            raise ValueError("Cannot upsert window metrics row without location_id")

    with conn.cursor() as cur:
        execute_batch(cur, UPSERT_WINDOW_SQL, rows, page_size=100)
    conn.commit()


# ============================
# Main
# ============================


def main() -> None:
    args = parse_args()
    if args.describe_table:
        describe_metric_table(args.describe_table)
        return
    start_date, end_date = get_default_dates(args)

    conn = None
    location_ids: Dict[Tuple[str, str], int] = {}
    if not args.dry_run:
        conn = get_db_connection()
        ensure_location_table_exists(conn)
        ensure_hourly_table_exists(conn)
        ensure_window_table_exists(conn)
        location_ids = upsert_locations_and_get_ids(conn, LOCATIONS)

    for location in LOCATIONS:
        if not location.active:
            print(f"⏭️ Skipping inactive location {location.name} ({location.city}, {location.state})")
            continue

        print(
            "📅 Fetching hourly weather from "
            f"{start_date} to {end_date} for {location.name} "
            f"({location.city}, {location.state})..."
        )

        location_key = _location_identity(location)
        location_db_id = location_ids.get(location_key) if conn is not None else None
        if conn is not None and location_db_id is None:
            raise RuntimeError(f"No database id found for location {location.name} ({location.address})")

        forecast = fetch_weather_forecast(start_date, end_date, location)
        hourly = forecast["hourly"]
        daily_context = build_daily_context(forecast["daily"])
        hourly_rows = transform_hourly_weather(hourly, location, location_db_id)
        window_rows = build_window_metrics(hourly_rows, location, daily_context, location_db_id)

        if args.dry_run:
            dump_path = dump_dry_run_results(
                start_date=start_date,
                end_date=end_date,
                location=location,
                hourly_rows=hourly_rows,
                window_rows=window_rows,
            )
            print("🔎 Dry run – showing first few hourly rows:")
            for r in hourly_rows[:5]:
                print(r)
            print(f"Total hourly rows for {location.name}: {len(hourly_rows)}")
            print("🔎 Derived window metrics:")
            for r in window_rows:
                print(r)
            print(f"💾 Full dry run output saved to {dump_path}")
            continue

        upsert_hourly_weather_rows(conn, hourly_rows)
        upsert_window_metrics_rows(conn, window_rows)

        print(f"✅ Inserted/updated {len(hourly_rows)} rows into weather_hourly for {location.name}.")
        print(f"✅ Inserted/updated {len(window_rows)} rows into weather_window_metrics for {location.name}.")

    if conn:
        conn.close()


if __name__ == "__main__":
    main()
