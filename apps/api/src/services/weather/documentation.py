"""Human-readable documentation for weather metrics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from psycopg2.extensions import connection as PgConnection


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


def describe_metric_table(table_name: str) -> None:
    normalized = table_name.strip().lower()
    docs = TABLE_METRIC_DOCS.get(normalized)
    if docs is None:
        raise ValueError(
            f"Unknown table '{table_name}'. Known tables: {', '.join(TABLE_METRIC_DOCS.keys())}"
        )
    print(f"Column documentation for {normalized}:")
    for column, doc in docs.items():
        units_display = doc.units or "unitless"
        print(
            f" - {column}: {doc.description} [units={units_display}; source={doc.source}]"
        )
    if "weather_code" in docs:
        print(" Weather code legend (WMO):")
        for code, description in sorted(WEATHER_CODE_DESCRIPTIONS.items()):
            print(f"   - {code}: {description}")


def _format_metric_doc_comment(doc: MetricDocumentation) -> str:
    extras = []
    if doc.units:
        extras.append(f"Units: {doc.units}")
    extras.append(f"Source: {doc.source}")
    extras_str = "; ".join(extras)
    return f"{doc.description} ({extras_str})"


def apply_column_comments(
    conn: PgConnection, table_name: str, docs: Dict[str, MetricDocumentation]
) -> None:
    with conn.cursor() as cur:
        for column, doc in docs.items():
            cur.execute(
                f"COMMENT ON COLUMN {table_name}.{column} IS %s",
                (_format_metric_doc_comment(doc),),
            )
    conn.commit()


__all__ = [
    "MetricDocumentation",
    "HOURLY_METRIC_DOCS",
    "WINDOW_METRIC_DOCS",
    "describe_metric_table",
    "apply_column_comments",
]
