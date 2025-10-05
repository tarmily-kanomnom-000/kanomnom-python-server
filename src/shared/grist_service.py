"""
Grist service - interface for Grist table operations.
Handles API communication, caching, data processing, and filtering.
"""

from __future__ import annotations

import json
import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import polars as pl
import requests

from core.cache.cache_service import get_cache_service
from shared.grist_schema import MaterialPurchaseSchema
from shared.polars_cleaners import sanitize_numeric_columns, sanitize_string_columns

logger = logging.getLogger(__name__)

# Grist API configuration
GRIST_ENDPOINT = os.getenv("GRIST_ENDPOINT")
GRIST_API_KEY = os.getenv("GRIST_API_KEY")
GRIST_OPEX_DOCUMENT_ID = os.getenv("GRIST_OPEX_DOCUMENT_ID")
GRIST_MATERIAL_PURCHASES_TABLE_ID = os.getenv("GRIST_MATERIAL_PURCHASES_TABLE_ID")
_GRIST_RESPONSE_DUMP_DIR = Path(os.getenv("GRIST_RESPONSE_DUMP_DIR", "request_dumps"))
_IGNORED_RESPONSE_FIELDS: frozenset[str] = frozenset({"material_price_summaries", "receipt"})


def _describe_dtypes(dataframe: pl.DataFrame) -> dict[str, str]:
    """Return a mapping of column name to dtype string for logging."""

    return {column: str(dtype) for column, dtype in zip(dataframe.columns, dataframe.dtypes)}


def _epoch_to_datetime(epoch_seconds: Any) -> datetime | None:
    """Convert epoch seconds to a naive datetime, guarding against invalid inputs."""

    if epoch_seconds is None:
        return None

    try:
        return datetime.fromtimestamp(int(epoch_seconds))
    except (TypeError, ValueError, OverflowError) as exc:
        logger.error("Unable to convert epoch value '%s' to datetime: %s", epoch_seconds, exc)
        return None


def _convert_epoch_seconds_to_datetime(dataframe: pl.DataFrame, column: str) -> pl.DataFrame:
    """Convert an epoch-seconds column to timezone-naive datetimes."""

    if column not in dataframe.columns:
        return dataframe

    return dataframe.with_columns(
        pl.when(pl.col(column).is_null())
        .then(None)
        .otherwise(
            pl.col(column)
            .cast(pl.Int64, strict=False)
            .map_elements(_epoch_to_datetime, return_dtype=pl.Datetime(time_unit="us"))
        )
        .alias(column)
    )


def _log_date_column_stats(dataframe: pl.DataFrame, column: str) -> None:
    """Log min/max/sample values for a datetime column if data exists."""

    if column not in dataframe.columns or dataframe.is_empty():
        return

    series = dataframe.get_column(column)
    logger.info(
        "Converted %s to datetime. Range: %s to %s",
        column,
        series.min(),
        series.max(),
    )
    logger.info("Sample dates from results: %s", series.head(3).to_list())


def _persist_grist_response(payload: dict[str, Any]) -> Path | None:
    """Persist the raw Grist payload for debugging purposes."""

    if not payload:
        return None

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    target_directory = _GRIST_RESPONSE_DUMP_DIR
    target_path = target_directory / f"grist_material_purchases_{timestamp}.json"

    try:
        target_directory.mkdir(parents=True, exist_ok=True)
        target_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
        logger.info("Persisted Grist response for debugging: %s", target_path)
        return target_path
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to write Grist debug payload: %s", exc)
        return None


def _normalize_rows_for_polars(rows: list[dict[str, Any]]) -> None:
    """Ensure columns with string entries coerce other types to strings before DataFrame creation."""

    if not rows:
        return

    string_columns: set[str] = set()
    for row in rows:
        for column, value in row.items():
            if isinstance(value, str):
                string_columns.add(column)

    if not string_columns:
        return

    for row in rows:
        for column in string_columns:
            if column not in row:
                continue
            value = row[column]
            if value is None or isinstance(value, str):
                continue
            row[column] = str(value)


def _remove_complex_typed_fields(rows: list[dict[str, Any]]) -> None:
    """Drop columns containing list/dict values that Polars cannot coerce reliably."""

    complex_columns: set[str] = set()
    for row in rows:
        for column, value in list(row.items()):
            if isinstance(value, (list, dict)):
                complex_columns.add(column)
                row.pop(column, None)

    if complex_columns:
        logger.info(
            "Dropped complex-typed Grist columns prior to DataFrame creation: %s",
            sorted(complex_columns),
        )


def _log_mixed_type_columns(rows: list[dict[str, Any]]) -> None:
    """Inspect row data to identify columns with heterogeneous Python types."""

    type_map: dict[str, set[str]] = defaultdict(set)
    samples: dict[str, list[Any]] = defaultdict(list)

    for row in rows:
        for column, value in row.items():
            if value is None:
                continue
            value_type = type(value).__name__
            type_map[column].add(value_type)
            if len(samples[column]) < 3:
                samples[column].append(value)

    mixed_columns = {column: types for column, types in type_map.items() if len(types) > 1}

    if mixed_columns:
        for column, types in sorted(mixed_columns.items()):
            logger.error(
                "Mixed value types detected for column '%s': %s | samples=%s",
                column,
                sorted(types),
                samples[column],
            )


def get_grist_table() -> pl.DataFrame:
    """
    Fetch Grist table data and return as Polars DataFrame with proper data types.
    Uses caching to avoid repeated API calls.
    """

    cache_service = get_cache_service()
    schema = MaterialPurchaseSchema.default()

    cached_df = cache_service.material_purchases_cache.get_dataframe_from_cache()
    if cached_df is not None and not cached_df.is_empty():
        logger.info("Using cached material purchases data: %d records", cached_df.height)
        return cached_df

    logger.info("Cache miss - fetching fresh data from Grist API")

    table_records_response = requests.get(
        url=(f"{GRIST_ENDPOINT}/api/docs/{GRIST_OPEX_DOCUMENT_ID}/tables/{GRIST_MATERIAL_PURCHASES_TABLE_ID}/records"),
        headers={"Authorization": f"Bearer {GRIST_API_KEY}"},
        timeout=30,
    )

    if table_records_response.status_code != 200:
        logger.error(
            "Failed to fetch Grist table: %s - %s",
            table_records_response.status_code,
            table_records_response.text,
        )
        return pl.DataFrame()

    try:
        data = table_records_response.json()
        _persist_grist_response(data)
        records = data.get("records", [])

        if not records:
            logger.warning("No records found in response")
            return pl.DataFrame()

        rows: list[dict[str, object]] = []
        for record in records:
            row = dict(record.get("fields", {}))
            row["id"] = record.get("id")
            for ignored_field in _IGNORED_RESPONSE_FIELDS:
                row.pop(ignored_field, None)
            rows.append(row)

        _normalize_rows_for_polars(rows)
        _remove_complex_typed_fields(rows)

        try:
            dataframe = pl.DataFrame(rows)
        except Exception:
            _log_mixed_type_columns(rows)
            raise

        if dataframe.is_empty():
            return dataframe

        logger.info("Converting data types...")

        try:
            resolved = schema.resolve(dataframe)
        except KeyError as exc:
            logger.error("Unable to resolve Grist schema columns: %s", exc)
            return pl.DataFrame()

        purchase_date_col = resolved.get("purchase_date", "Purchase_Date")
        if purchase_date_col not in dataframe.columns:
            purchase_date_col = "Purchase_Date"

        string_columns = tuple(
            column
            for column in (resolved.get("material_name"), resolved.get("unit"))
            if column and column in dataframe.columns
        )
        dataframe = sanitize_string_columns(dataframe, string_columns)

        numeric_role_names = (
            "package_size",
            "quantity",
            "total_unit_cost",
            "total_cost",
        )
        numeric_columns = [
            resolved[role] for role in numeric_role_names if resolved.get(role) and resolved[role] in dataframe.columns
        ]
        if purchase_date_col in dataframe.columns:
            numeric_columns.append(purchase_date_col)

        dataframe = sanitize_numeric_columns(dataframe, numeric_columns)

        if purchase_date_col in dataframe.columns:
            dataframe = _convert_epoch_seconds_to_datetime(dataframe, purchase_date_col)
            _log_date_column_stats(dataframe, purchase_date_col)

        if "id" in dataframe.columns:
            dataframe = dataframe.with_columns(pl.col("id").cast(pl.Int64, strict=False).alias("id"))

        logger.info(
            "DataFrame created with %d rows and %d columns",
            dataframe.height,
            len(dataframe.columns),
        )
        logger.info("DataFrame dtypes: %s", _describe_dtypes(dataframe))

        cache_service.material_purchases_cache.save_cache(dataframe)
        cache_service.invalidate_dependent_caches("material_purchases")

        return dataframe

    except Exception as exc:  # noqa: BLE001
        logger.error("Error processing Grist response: %s", exc)
        return pl.DataFrame()


class DataFilterManager:
    """Manages data filtering operations for Grist data."""

    def __init__(self) -> None:
        self.grist_dataframe: pl.DataFrame | None = None
        self.filtered_grist_dataframe: pl.DataFrame | None = None
        self.start_date: datetime | None = None
        self.end_date: datetime | None = None
        self._schema = MaterialPurchaseSchema.default()
        self._set_default_date_range()

    def _set_default_date_range(self) -> None:
        """Set default date range to the trailing year."""
        now = datetime.now()
        trailing_year = now - timedelta(days=365)
        self.start_date = trailing_year
        self.end_date = now

    def load_grist_data(self) -> None:
        """Load Grist data and apply initial time filtering."""
        try:
            logger.info("Loading Grist material purchases data...")
            self.grist_dataframe = get_grist_table()

            if self.grist_dataframe.is_empty():
                logger.warning("No Grist data loaded")
                return

            logger.info("Loaded %d records from Grist", self.grist_dataframe.height)

            self.apply_time_filter()

        except Exception as exc:  # noqa: BLE001
            logger.error("Error loading Grist data: %s", exc)
            self.grist_dataframe = pl.DataFrame()
            self.filtered_grist_dataframe = pl.DataFrame()

    def apply_time_filter(self) -> None:
        """Apply time range filter to the Grist dataframe."""
        if self.grist_dataframe is None or self.grist_dataframe.is_empty():
            logger.warning("No Grist data to filter")
            self.filtered_grist_dataframe = pl.DataFrame()
            return

        try:
            df = self.grist_dataframe.clone()

            schema_resolved: dict[str, str] = {}
            try:
                schema_resolved = self._schema.resolve(df)
            except KeyError as exc:
                logger.error("Unable to resolve Grist schema in filter: %s", exc)

            purchase_date_col = schema_resolved.get("purchase_date", "Purchase_Date")
            if purchase_date_col not in df.columns:
                logger.warning("%s column not found in Grist data", purchase_date_col)
                self.filtered_grist_dataframe = df
                return

            start_filter = self.start_date
            end_filter = self.end_date

            if start_filter and end_filter:
                filtered_df = df.filter(
                    (pl.col(purchase_date_col) >= start_filter) & (pl.col(purchase_date_col) <= end_filter)
                )
                logger.info(
                    "Applied date filter: %s to %s",
                    start_filter.strftime("%Y-%m-%d"),
                    end_filter.strftime("%Y-%m-%d"),
                )
            elif start_filter:
                filtered_df = df.filter(pl.col(purchase_date_col) >= start_filter)
                logger.info(
                    "Applied start date filter: from %s",
                    start_filter.strftime("%Y-%m-%d"),
                )
            elif end_filter:
                filtered_df = df.filter(pl.col(purchase_date_col) <= end_filter)
                logger.info(
                    "Applied end date filter: until %s",
                    end_filter.strftime("%Y-%m-%d"),
                )
            else:
                filtered_df = df
                logger.info("No date filter applied")

            self.filtered_grist_dataframe = filtered_df

            logger.info(
                "Filtered from %d to %d records",
                df.height,
                filtered_df.height,
            )
            if not filtered_df.is_empty():
                min_date = filtered_df.select(pl.col(purchase_date_col).min()).item()
                max_date = filtered_df.select(pl.col(purchase_date_col).max()).item()
                logger.info("Filtered date range: %s to %s", min_date, max_date)
                material_col = schema_resolved.get("material_name", "material2")
                if material_col in filtered_df.columns:
                    unique_materials = filtered_df.select(pl.col(material_col).n_unique()).item()
                    logger.info("Unique materials in filtered data: %d", unique_materials)

        except Exception as exc:  # noqa: BLE001
            logger.error("Error applying time filter: %s", exc)
            self.filtered_grist_dataframe = (
                self.grist_dataframe.clone() if self.grist_dataframe is not None else pl.DataFrame()
            )

    def update_date_range(self, start_date: datetime, end_date: datetime) -> None:
        """Update the date range and reapply filter."""
        self.start_date = start_date
        self.end_date = end_date
        self.apply_time_filter()

    def get_filtered_data(self) -> pl.DataFrame:
        """Get the current filtered dataframe."""
        if self.filtered_grist_dataframe is not None:
            return self.filtered_grist_dataframe
        return pl.DataFrame()
