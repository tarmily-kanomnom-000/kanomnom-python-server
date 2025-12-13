"""Utilities for resolving Grist column names to canonical roles."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import polars as pl

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class MaterialPurchaseSchema:
    """Resolves material purchase column roles to actual Grist column names."""

    column_aliases: dict[str, list[str]]
    required_roles: set[str] = field(default_factory=set)

    @classmethod
    def default(cls) -> "MaterialPurchaseSchema":
        return cls(
            column_aliases={
                "material_name": ["material"],
                "purchase_date": ["Purchase_Date"],
                "unit": ["unit"],
                "package_size": ["package_size"],
                "quantity": ["quantity_purchased"],
                "total_cost": ["total_cost_USD"],
                "total_unit_cost": ["total_unit_cost_USD"],
                "purchase_source": ["purchase_source"],
                "purchase_unit_price": [
                    "purchase_unit_price",
                    "purchase_unit_price_USD",
                ],
                "purchase_price_per_item": [
                    "purchase_price_per_item",
                    "purchase_price_per_item_USD",
                    "purchase_price_per_item_original",
                ],
                "purchase_price_per_item2": [
                    "purchase_price_per_item2",
                    "purchase_price_per_item2_USD",
                ],
            },
            required_roles={"material_name", "unit", "package_size", "quantity", "total_cost"},
        )

    def resolve(self, dataframe: pl.DataFrame) -> dict[str, str]:
        """Resolve all known roles to actual dataframe column names."""

        resolved: dict[str, str] = {}
        missing_required: list[str] = []
        for role in self.column_aliases:
            column = self._resolve_column(dataframe, role)
            if column is None:
                if role in self.required_roles:
                    missing_required.append(role)
                continue
            resolved[role] = column

        if missing_required:
            raise KeyError("Missing required Grist columns for roles: " + ", ".join(sorted(missing_required)))

        logger.debug("Resolved Grist roles: %s", resolved)
        return resolved

    def _resolve_column(self, dataframe: pl.DataFrame, role: str) -> str | None:
        """Resolve a single role to a matching column."""

        candidates = list(self.column_aliases.get(role, ()))

        lower_map = {col.lower(): col for col in dataframe.columns}

        for candidate in candidates:
            if candidate in dataframe.columns:
                return candidate
            lowered = candidate.lower()
            if lowered in lower_map:
                actual = lower_map[lowered]
                logger.debug(
                    "Resolved role '%s' using case-insensitive match '%s' -> '%s'",
                    role,
                    candidate,
                    actual,
                )
                return actual

        return None


__all__ = ["MaterialPurchaseSchema"]
