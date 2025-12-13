"""Common cleaning utilities for working with Polars data frames."""

from __future__ import annotations

import polars as pl

_EMPTY_LITERALS = ("", "none", "null", "nan", "nat")
_NUMERIC_INVALIDS = ("", "-", ".")


def sanitize_string_columns(dataframe: pl.DataFrame, columns: tuple[str, ...] | list[str]) -> pl.DataFrame:
    """Strip whitespace and normalize empty string representations to null for each column."""

    for column in columns:
        if not column or column not in dataframe.columns:
            continue

        text = pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars()
        dataframe = dataframe.with_columns(
            pl.when(text.is_null() | text.str.to_lowercase().is_in(_EMPTY_LITERALS))
            .then(None)
            .otherwise(text)
            .alias(column)
        )

    return dataframe


def sanitize_numeric_columns(dataframe: pl.DataFrame, columns: tuple[str, ...] | list[str]) -> pl.DataFrame:
    """Normalize numeric-looking columns by removing currency markers and casting to floats."""

    for column in columns:
        if not column or column not in dataframe.columns:
            continue

        text = pl.col(column).cast(pl.Utf8, strict=False).str.strip_chars()
        cleaned = text.str.replace_all(r"[^0-9\\.-]", "")

        dataframe = dataframe.with_columns(
            pl.when(text.is_null() | text.str.to_lowercase().is_in(_EMPTY_LITERALS))
            .then(None)
            .otherwise(pl.when(cleaned.is_in(_NUMERIC_INVALIDS)).then(None).otherwise(cleaned))
            .cast(pl.Float64, strict=False)
            .alias(column)
        )

    return dataframe
