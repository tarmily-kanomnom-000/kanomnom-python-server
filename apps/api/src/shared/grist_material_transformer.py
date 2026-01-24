"""Shared transformations for Grist material purchase datasets."""

from __future__ import annotations

from typing import Iterable

import polars as pl
from shared.grist_schema import MaterialPurchaseSchema
from shared.polars_cleaners import sanitize_numeric_columns, sanitize_string_columns

_STRING_ROLES: tuple[str, ...] = ("material_name", "unit", "purchase_source")
_NUMERIC_ROLES: tuple[str, ...] = (
    "package_size",
    "quantity",
    "total_cost",
    "total_unit_cost",
    "purchase_unit_price",
    "purchase_price_per_item",
    "purchase_price_per_item2",
)
_ROLE_TO_CANONICAL: dict[str, str] = {
    "material_name": "material",
    "purchase_date": "purchase_date",
    "unit": "unit",
    "package_size": "package_size",
    "quantity": "quantity",
    "total_cost": "total_cost",
    "total_unit_cost": "total_unit_cost",
    "purchase_source": "purchase_source",
    "purchase_unit_price": "purchase_unit_price",
    "purchase_price_per_item": "purchase_price_per_item",
    "purchase_price_per_item2": "purchase_price_per_item2",
}
_CANONICAL_COLUMN_ORDER: list[str] = [
    "material",
    "purchase_date",
    "unit",
    "package_size",
    "quantity",
    "units_purchased",
    "total_cost",
    "unit_cost",
    "total_unit_cost",
    "purchase_source",
]


def normalize_material_purchase_dataframe(
    dataframe: pl.DataFrame,
    schema: MaterialPurchaseSchema,
) -> pl.DataFrame:
    """Return a canonical material purchase dataframe ready for downstream analytics."""

    resolved = schema.resolve(dataframe)

    sanitized = sanitize_string_columns(
        dataframe.clone(),
        _collect_existing_columns(resolved, _STRING_ROLES),
    )
    sanitized = sanitize_numeric_columns(
        sanitized,
        _collect_existing_columns(resolved, _NUMERIC_ROLES),
    )

    rename_map = _canonical_rename_map(resolved)
    normalized = sanitized.rename(rename_map)
    normalized = _ensure_numeric_columns(normalized)
    normalized = _add_units_purchased(normalized)
    normalized = _add_total_cost(normalized)
    normalized = _add_unit_cost(normalized)
    normalized = _ensure_optional_columns(normalized)

    return normalized.select(
        [column for column in _CANONICAL_COLUMN_ORDER if column in normalized.columns]
    )


def _collect_existing_columns(
    resolved: dict[str, str], roles: Iterable[str]
) -> list[str]:
    columns: list[str] = []
    for role in roles:
        column = resolved.get(role)
        if column:
            columns.append(column)
    return columns


def _canonical_rename_map(resolved: dict[str, str]) -> dict[str, str]:
    rename_map: dict[str, str] = {}
    for role, column in resolved.items():
        canonical = _ROLE_TO_CANONICAL.get(role)
        if canonical and column:
            rename_map[column] = canonical
    return rename_map


def _ensure_numeric_columns(dataframe: pl.DataFrame) -> pl.DataFrame:
    numeric_columns = (
        "package_size",
        "quantity",
        "total_cost",
        "total_unit_cost",
        "purchase_unit_price",
        "purchase_price_per_item",
        "purchase_price_per_item2",
    )
    available = [column for column in numeric_columns if column in dataframe.columns]
    if not available:
        return dataframe

    casts = [
        pl.col(column).cast(pl.Float64, strict=False).alias(column)
        for column in available
    ]
    return dataframe.with_columns(casts)


def _add_units_purchased(dataframe: pl.DataFrame) -> pl.DataFrame:
    if "package_size" not in dataframe.columns or "quantity" not in dataframe.columns:
        return dataframe.with_columns(
            pl.lit(0.0).cast(pl.Float64).alias("units_purchased")
        )

    package_expr = pl.col("package_size").fill_null(0.0)
    quantity_expr = pl.col("quantity").fill_null(0.0)
    product_expr = package_expr * quantity_expr

    return dataframe.with_columns(
        pl.when(product_expr > 0)
        .then(product_expr)
        .otherwise(quantity_expr)
        .fill_null(0.0)
        .cast(pl.Float64, strict=False)
        .alias("units_purchased")
    )


def _add_total_cost(dataframe: pl.DataFrame) -> pl.DataFrame:
    quantity_expr = pl.col("quantity").fill_null(0.0)
    package_expr = pl.col("package_size").fill_null(0.0)

    candidate_exprs: list[pl.Expr] = []

    if "total_cost" in dataframe.columns:
        candidate_exprs.append(
            pl.when(pl.col("total_cost") > 0).then(pl.col("total_cost")).otherwise(None)
        )

    if "total_unit_cost" in dataframe.columns:
        candidate_exprs.append(
            pl.when(pl.col("total_unit_cost") > 0)
            .then(pl.col("total_unit_cost") * package_expr * quantity_expr)
            .otherwise(None)
        )

    if "purchase_unit_price" in dataframe.columns:
        candidate_exprs.append(
            pl.when(pl.col("purchase_unit_price") > 0)
            .then(pl.col("purchase_unit_price") * package_expr * quantity_expr)
            .otherwise(None)
        )

    if "purchase_price_per_item" in dataframe.columns:
        candidate_exprs.append(
            pl.when(pl.col("purchase_price_per_item") > 0)
            .then(pl.col("purchase_price_per_item") * quantity_expr)
            .otherwise(None)
        )

    if "purchase_price_per_item2" in dataframe.columns:
        candidate_exprs.append(
            pl.when(pl.col("purchase_price_per_item2") > 0)
            .then(pl.col("purchase_price_per_item2") * quantity_expr)
            .otherwise(None)
        )

    if candidate_exprs:
        dataframe = dataframe.with_columns(
            pl.coalesce(candidate_exprs).alias("__total_cost_candidate")
        )
    else:
        dataframe = dataframe.with_columns(pl.lit(0.0).alias("__total_cost_candidate"))

    return dataframe.with_columns(
        pl.col("__total_cost_candidate")
        .fill_null(0.0)
        .cast(pl.Float64, strict=False)
        .alias("total_cost")
    ).drop("__total_cost_candidate")


def _add_unit_cost(dataframe: pl.DataFrame) -> pl.DataFrame:
    unit_cost_candidates: list[pl.Expr] = []

    if "total_unit_cost" in dataframe.columns:
        unit_cost_candidates.append(
            pl.when(pl.col("total_unit_cost") > 0)
            .then(pl.col("total_unit_cost"))
            .otherwise(None)
        )

    unit_cost_candidates.append(
        pl.when(
            (pl.col("units_purchased") > 0)
            & pl.col("total_cost").is_not_null()
            & (pl.col("total_cost") > 0)
        )
        .then(pl.col("total_cost") / pl.col("units_purchased"))
        .otherwise(None)
    )

    return dataframe.with_columns(
        pl.coalesce(unit_cost_candidates)
        .cast(pl.Float64, strict=False)
        .alias("unit_cost")
    )


def _ensure_optional_columns(dataframe: pl.DataFrame) -> pl.DataFrame:
    required_columns: dict[str, pl.DataType] = {
        "total_unit_cost": pl.Float64,
        "purchase_source": pl.Utf8,
    }

    expressions: list[pl.Expr] = []
    for column, dtype in required_columns.items():
        if column not in dataframe.columns:
            expressions.append(pl.lit(None).cast(dtype).alias(column))

    if expressions:
        dataframe = dataframe.with_columns(expressions)

    dataframe = dataframe.with_columns(
        [
            pl.col("total_cost").fill_null(0.0).alias("total_cost"),
            pl.col("units_purchased").fill_null(0.0).alias("units_purchased"),
        ]
    )

    return dataframe


__all__ = ["normalize_material_purchase_dataframe"]
