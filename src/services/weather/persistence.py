"""Database helpers for weather ingestion."""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extensions import connection as PgConnection
from psycopg2.extras import execute_batch

from .config import DatabaseConfig, LocationConfig
from .documentation import HOURLY_METRIC_DOCS, WINDOW_METRIC_DOCS, apply_column_comments

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
    open_weekdays SMALLINT[] NOT NULL,
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
    open_weekdays,
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
    %(open_weekdays)s,
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
    open_weekdays = EXCLUDED.open_weekdays,
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


def get_db_connection(db_config: DatabaseConfig) -> PgConnection:
    try:
        conn = psycopg2.connect(
            host=db_config.host,
            port=db_config.port,
            dbname=db_config.dbname,
            user=db_config.user,
            password=db_config.password,
        )
        return conn
    except Exception as exc:
        print("❌ Failed to connect to PostgreSQL:", exc, file=sys.stderr)
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
                    "open_weekdays": list(location.open_weekdays),
                    "active": location.active,
                    "notes": location.notes,
                },
            )
            location_id = cur.fetchone()[0]
            ids[(location.name, location.address)] = location_id
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


__all__ = [
    "get_db_connection",
    "ensure_location_table_exists",
    "ensure_hourly_table_exists",
    "ensure_window_table_exists",
    "upsert_locations_and_get_ids",
    "upsert_hourly_weather_rows",
    "upsert_window_metrics_rows",
]
