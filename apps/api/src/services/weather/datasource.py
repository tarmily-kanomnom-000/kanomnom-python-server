"""Open-Meteo interaction and transformation helpers."""

from __future__ import annotations

import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

import requests

from .config import LocationConfig

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


def fetch_weather_forecast(
    start_date: str, end_date: str, location: LocationConfig
) -> Dict[str, Any]:
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
        raise RuntimeError(
            f"Unexpected Open-Meteo response: {json.dumps(data, indent=2)}"
        )
    if "daily" not in data or "time" not in data["daily"]:
        raise RuntimeError(
            f"Missing daily block in Open-Meteo response: {json.dumps(data, indent=2)}"
        )
    return data


def transform_hourly_weather(
    hourly: Dict[str, Any],
    location: LocationConfig,
    location_id: Optional[int],
) -> List[Dict[str, Any]]:
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
                "apparent_temp_f": (
                    None if apparent_c is None else (apparent_c * 9 / 5) + 32
                ),
                "relative_humidity_percent": _safe_item(humidity, i),
                "dew_point_f": (
                    None if dew_point_c is None else (dew_point_c * 9 / 5) + 32
                ),
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
            "temperature_max_f": (
                None if temp_max_c is None else (temp_max_c * 9 / 5) + 32
            ),
            "temperature_min_f": (
                None if temp_min_c is None else (temp_min_c * 9 / 5) + 32
            ),
            "apparent_temperature_max_f": (
                None if apparent_max_c is None else (apparent_max_c * 9 / 5) + 32
            ),
            "apparent_temperature_min_f": (
                None if apparent_min_c is None else (apparent_min_c * 9 / 5) + 32
            ),
        }
    return context


def build_window_metrics(
    hourly_rows: List[Dict[str, Any]],
    location: LocationConfig,
    daily_context: Dict[date, Dict[str, Any]],
    location_id: Optional[int],
) -> List[Dict[str, Any]]:
    if not hourly_rows:
        return []
    tz = ZoneInfo(location.timezone)
    by_date: Dict[date, List[Dict[str, Any]]] = {}
    for row in hourly_rows:
        observed_at: datetime = row["observed_at"]
        local_dt = observed_at.astimezone(tz)
        by_date.setdefault(local_dt.date(), []).append(
            {**row, "observed_local": local_dt}
        )

    window_rows: List[Dict[str, Any]] = []
    for day, rows_for_day in by_date.items():
        day_ctx = daily_context.get(day, {})
        for window in WINDOWS:
            start = datetime.combine(day, time(hour=window["start_hour"], tzinfo=tz))
            end = datetime.combine(day, time(hour=window["end_hour"], tzinfo=tz))
            window_slice = [
                r for r in rows_for_day if start <= r["observed_local"] < end
            ]
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
            precip_probability_values = [
                r["precip_probability_percent"] for r in window_slice
            ]
            weather_codes = [
                r["weather_code"] for r in window_slice if r["weather_code"] is not None
            ]

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
                    "day_apparent_temp_min_f": day_ctx.get(
                        "apparent_temperature_min_f"
                    ),
                    "day_apparent_temp_max_f": day_ctx.get(
                        "apparent_temperature_max_f"
                    ),
                    "sample_count": len(window_slice),
                    "raw_json": json.dumps(
                        {
                            "hours": [
                                r["observed_local"].isoformat() for r in window_slice
                            ],
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


def dump_dry_run_results(
    start_date: str,
    end_date: str,
    location: LocationConfig,
    hourly_rows: List[Dict[str, Any]],
    window_rows: List[Dict[str, Any]],
    dump_dir: Path,
    processed_dates: List[date],
) -> Path:
    dump_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(tz=ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%S")
    filename = (
        f"weather_dry_run_{_sanitize_location_name(location.name)}_"
        f"{start_date}_{end_date}_{timestamp}.json"
    )
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
                "open_weekdays": list(location.open_weekdays),
                "active": location.active,
                "notes": location.notes,
            },
            "processed_dates": [d.isoformat() for d in processed_dates],
            "hourly_row_count": len(hourly_rows),
            "window_row_count": len(window_rows),
            "generated_at": datetime.now(tz=ZoneInfo("UTC")).isoformat(),
        },
        "hourly_rows": _serialize_rows_for_dump(hourly_rows),
        "window_rows": _serialize_rows_for_dump(window_rows),
    }
    output_path = dump_dir / filename
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return output_path


def _safe_item(values: List[Any], index: int) -> Any:
    return values[index] if index < len(values) else None


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


def _daylight_minutes(
    sunrise: Optional[datetime], sunset: Optional[datetime]
) -> Optional[int]:
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


__all__ = [
    "HOURLY_VARIABLES",
    "DAILY_VARIABLES",
    "WINDOWS",
    "fetch_weather_forecast",
    "transform_hourly_weather",
    "build_daily_context",
    "build_window_metrics",
    "dump_dry_run_results",
]
