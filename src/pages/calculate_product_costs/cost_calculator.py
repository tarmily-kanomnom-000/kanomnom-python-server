"""
Complete cost calculation system for product costs.
Handles material cost basis calculation, ingredient cost lookup, time series analysis, and caching.
"""

from __future__ import annotations

import logging
from datetime import datetime
from operator import attrgetter
from typing import Optional

import polars as pl
from cachetools import LRUCache, cachedmethod
from dateutil.relativedelta import relativedelta

from core.cache.cache_dependency_manager import get_cache_dependency_manager
from shared.grist_material_transformer import normalize_material_purchase_dataframe
from shared.grist_schema import MaterialPurchaseSchema
from shared.unit_converter import get_liquid_density, get_special_conversion_factor

from .openai_client import APIBackend, create_openai_client
from .semantic_ingredient_matcher import get_semantic_matcher

logger = logging.getLogger(__name__)


class MaterialCostCalculator:
    """Complete cost calculation system with cost basis, semantic matching, and time series analysis."""

    def __init__(self) -> None:
        self.material_cost_basis: dict[str, dict[str, float]] = {}
        self.data_manager = None  # Will be set externally for time series calculations
        self._cache = LRUCache(maxsize=128)
        self._register_with_dependency_manager()
        self._semantic_matching_enabled = False
        self._schema = MaterialPurchaseSchema.default()

    def calculate_material_cost_basis(
        self, filtered_grist_dataframe: pl.DataFrame | None
    ) -> dict[str, dict[str, float]]:
        """
        Calculate cost basis per unit for each material from filtered Grist data.
        Groups by material and unit, then calculates weighted average cost per unit.

        Returns:
            dict[str, dict[str, float]]: {material_name: {unit: cost_per_unit}}
        """
        if filtered_grist_dataframe is None or filtered_grist_dataframe.is_empty():
            logger.warning("No filtered Grist data provided for cost basis calculation")
            return {}

        cost_basis = self._calculate_cost_basis_from_dataframe(filtered_grist_dataframe)
        self.material_cost_basis = cost_basis
        return cost_basis

    def _try_unit_conversion(
        self, material_name: str, target_unit: str, material_costs: dict[str, float]
    ) -> Optional[float]:
        """
        Try to convert between units using special conversions first, then density.

        Args:
            material_name: Name of the material
            target_unit: Target unit from recipe
            material_costs: Available costs {unit: cost}

        Returns:
            float: Converted cost, or None if conversion not possible
        """
        for available_unit, cost in material_costs.items():
            special_factor = get_special_conversion_factor(material_name, available_unit, target_unit)
            if special_factor:
                return cost / special_factor

        if target_unit.lower() == "g" and any(u.lower() == "ml" for u in material_costs):
            cost_per_ml = next((cost for unit, cost in material_costs.items() if unit.lower() == "ml"), None)
            if cost_per_ml is not None:
                density = get_liquid_density(material_name)
                if density is not None:
                    return cost_per_ml / density

        if target_unit.lower() == "ml" and any(u.lower() == "g" for u in material_costs):
            cost_per_g = next((cost for unit, cost in material_costs.items() if unit.lower() == "g"), None)
            if cost_per_g is not None:
                density = get_liquid_density(material_name)
                if density is not None:
                    return cost_per_g * density

        return None

    def set_data_manager(self, data_manager) -> None:
        """Set data manager for time series calculations."""
        self.data_manager = data_manager

    @cachedmethod(attrgetter("_cache"), key=lambda self: "api_client")
    def _get_api_client(self):
        """Get or create the OpenAI API client (cached)."""
        logger.info("Creating and caching OpenAI client")
        return create_openai_client(backend=APIBackend.OPENAI)

    @cachedmethod(attrgetter("_cache"), key=lambda self: "semantic_matcher")
    def _get_semantic_matcher(self):
        """Get or create the semantic matcher (cached)."""
        logger.info("Creating and caching semantic matcher")
        api_client = self._get_api_client()
        return get_semantic_matcher(api_client)

    def find_cost_in_basis(self, material_name: str, unit: str, cost_basis: dict) -> Optional[float]:
        """Find cost for a material and unit in the cost basis, with unit conversion if needed."""
        material_costs = cost_basis.get(material_name, {})

        if unit in material_costs:
            return material_costs[unit]

        for available_unit, cost in material_costs.items():
            if unit.lower() == available_unit.lower():
                return cost

        converted_cost = self._try_unit_conversion(material_name, unit, material_costs)
        if converted_cost is not None:
            return converted_cost

        return None

    def calculate_ingredient_costs(self, ingredients: dict, cost_basis: dict) -> tuple[list[tuple], float]:
        """
        Calculate ingredient costs with complete breakdown using semantic matching.

        Args:
            ingredients: dict of {ingredient: (amount, unit)}
            cost_basis: Cost basis data

        Returns:
            tuple of (sorted_ingredients_list, total_cost) where sorted_ingredients_list contains
            (ingredient, amount, unit, cost_per_unit, ingredient_cost, match_info) tuples
        """
        ingredient_costs = []
        total_product_cost = 0.0

        match_lookup: dict[str, object] = {}
        if self._semantic_matching_enabled:
            ingredient_list = list(ingredients.keys())
            available_materials = list(cost_basis.keys())

            try:
                semantic_matcher = self._get_semantic_matcher()
                match_results = semantic_matcher.find_best_matches(ingredient_list, available_materials)
                match_lookup = {result.ingredient: result for result in match_results}
            except Exception:  # noqa: BLE001
                self._semantic_matching_enabled = False
                logger.exception("Semantic ingredient matcher disabled due to errors")

        for ingredient, (amount, unit) in ingredients.items():
            match_result = match_lookup.get(ingredient)
            if match_result and match_result.matched_material:
                matched_material = match_result.matched_material
                match_info = {"matched_material": matched_material, "match_type": match_result.match_type}
            else:
                matched_material = ingredient
                match_info = {"matched_material": ingredient, "match_type": "exact"}

            cost_per_unit = self.find_cost_in_basis(matched_material, unit, cost_basis)

            if cost_per_unit is not None:
                ingredient_cost = amount * cost_per_unit
                total_product_cost += ingredient_cost
            else:
                ingredient_cost = 0.0

            ingredient_costs.append((ingredient, amount, unit, cost_per_unit, ingredient_cost, match_info))

        sorted_ingredients = sorted(ingredient_costs, key=lambda item: item[4], reverse=True)
        return sorted_ingredients, total_product_cost

    def calculate_cost_time_series(
        self,
        product_name: str,
        product_ingredients: dict,
        trailing_months: int = 6,
    ) -> list[tuple[datetime, float]]:
        """
        Calculate cost time series for a product with monthly time steps.

        Args:
            product_name: Name of the product
            product_ingredients: dict of {ingredient: (amount, unit)}
            trailing_months: Number of months to look back for cost calculation

        Returns:
            list of (datetime, cost) tuples representing the time series
        """
        validation_result = self._validate_time_series_prerequisites()
        if validation_result is not None:
            return validation_result

        time_points = self._get_time_series_points()
        cost_series = self._calculate_costs_for_time_points(time_points, product_ingredients, trailing_months)
        return cost_series

    def _validate_time_series_prerequisites(self) -> Optional[list]:
        """Validate that prerequisites for time series calculation are met."""
        if (
            self.data_manager is None
            or self.data_manager.grist_dataframe is None
            or self.data_manager.grist_dataframe.is_empty()
        ):
            logger.warning("No Grist data available for time series calculation")
            return []
        return None

    def _get_time_series_points(self) -> list[datetime]:
        """Get the time points for the time series calculation."""
        df = self.data_manager.grist_dataframe
        resolved = self._schema.resolve(df)
        purchase_date_col = resolved.get("purchase_date", "Purchase_Date")
        if purchase_date_col not in df.columns:
            logger.warning("%s column not found when building time series", purchase_date_col)
            return []

        date_series = df.get_column(purchase_date_col)
        min_date = date_series.min()
        max_date = date_series.max()

        logger.debug("Data date range: %s to %s", min_date, max_date)
        return self._generate_monthly_time_points(min_date, max_date)

    def _calculate_costs_for_time_points(
        self,
        time_points: list[datetime],
        product_ingredients: dict,
        trailing_months: int,
    ) -> list[tuple[datetime, float]]:
        """Calculate product costs for each time point."""
        cost_series: list[tuple[datetime, float]] = []
        df = self.data_manager.grist_dataframe
        resolved = self._schema.resolve(df)

        for time_point in time_points:
            cost = self._calculate_cost_at_time_point(time_point, df, resolved, product_ingredients, trailing_months)
            if cost is not None:
                cost_series.append((time_point, cost))
                logger.debug("Cost at %s: $%.4f", time_point, cost)

        return cost_series

    def _calculate_cost_at_time_point(
        self,
        time_point: datetime,
        dataframe: pl.DataFrame,
        resolved: dict[str, str],
        product_ingredients: dict,
        trailing_months: int,
    ) -> Optional[float]:
        """Calculate product cost at a specific time point."""
        purchase_date_col = resolved.get("purchase_date", "Purchase_Date")
        if purchase_date_col not in dataframe.columns:
            logger.warning("%s column not found when calculating time point", purchase_date_col)
            return None

        window_start = time_point - relativedelta(months=trailing_months)

        window_data = dataframe.filter(
            (pl.col(purchase_date_col) >= window_start) & (pl.col(purchase_date_col) <= time_point)
        )

        if window_data.is_empty():
            logger.debug("No data for window ending %s", time_point)
            return None

        temp_cost_basis = self._calculate_cost_basis_from_dataframe(window_data)
        _, product_cost = self.calculate_ingredient_costs(product_ingredients, temp_cost_basis)

        return product_cost

    def _generate_monthly_time_points(self, start_date: datetime, end_date: datetime) -> list[datetime]:
        """Generate monthly time points between start and end dates."""
        if start_date is None or end_date is None:
            return []

        time_points: list[datetime] = []
        current = start_date.replace(day=1)

        while current <= end_date:
            time_points.append(current)
            current += relativedelta(months=1)

        return time_points

    def _calculate_cost_basis_from_dataframe(self, dataframe: pl.DataFrame) -> dict[str, dict[str, float]]:
        """Calculate cost basis from any Polars DataFrame with purchase data."""
        if dataframe is None or dataframe.is_empty():
            logger.warning("No data available for cost basis calculation")
            return {}

        logger.debug("Cost basis start: %d rows with columns %s", dataframe.height, sorted(dataframe.columns))

        try:
            normalized = normalize_material_purchase_dataframe(dataframe.clone(), self._schema)
        except KeyError:
            logger.exception("Unable to resolve Grist schema columns")
            return {}
        except Exception:  # noqa: BLE001
            logger.exception("Failed to normalize material purchase dataframe")
            return {}

        filtered = normalized.with_columns(
            [
                pl.col("material").fill_null("").alias("material"),
                pl.col("unit").fill_null("").alias("unit"),
                pl.col("units_purchased").fill_null(0.0).alias("units_purchased"),
                pl.col("total_cost").fill_null(0.0).alias("total_cost"),
            ]
        ).filter(
            (pl.col("material").str.len_chars() > 0)
            & (pl.col("unit").str.len_chars() > 0)
            & (pl.col("units_purchased") > 0)
        )

        logger.debug(
            "Cost basis rows after filtering: %d (dropped %d)",
            filtered.height,
            normalized.height - filtered.height,
        )

        if filtered.is_empty():
            logger.warning("No valid rows available for cost basis calculation after filtering")
            return {}

        grouped = (
            filtered.group_by(["material", "unit"])
            .agg(
                [
                    pl.col("units_purchased").sum().alias("total_amount_bought"),
                    pl.col("total_cost").sum().alias("total_cost"),
                ]
            )
            .with_columns(
                pl.when(pl.col("total_amount_bought") > 0)
                .then(pl.col("total_cost") / pl.col("total_amount_bought"))
                .otherwise(None)
                .alias("cost_per_unit")
            )
        )

        cost_per_unit_series = grouped.get_column("cost_per_unit")
        if bool(cost_per_unit_series.is_null().any()):
            problematic = grouped.filter(pl.col("cost_per_unit").is_null()).select(
                ["material", "unit", "total_cost", "total_amount_bought"]
            )
            logger.warning("NaN cost_per_unit detected for rows: %s", problematic.to_dicts())
            grouped = grouped.filter(pl.col("cost_per_unit").is_not_null())

        cost_basis: dict[str, dict[str, float]] = {}
        for row in grouped.iter_rows(named=True):
            material = row["material"]
            unit = row["unit"]
            cost_per_unit = float(row["cost_per_unit"])
            cost_basis.setdefault(material, {})[unit] = cost_per_unit

        return cost_basis

    def calculate_cost_basis_for_window_at_date(
        self, selected_date: datetime, trailing_months: int
    ) -> dict[str, dict[str, float]]:
        """Calculate cost basis for a specific date using trailing window."""
        if self.data_manager is None or self.data_manager.grist_dataframe is None:
            return {}

        df = self.data_manager.grist_dataframe
        resolved = self._schema.resolve(df)
        purchase_date_col = resolved.get("purchase_date", "Purchase_Date")
        if purchase_date_col not in df.columns:
            logger.warning("%s column not found when calculating window cost basis", purchase_date_col)
            return {}

        window_start = selected_date - relativedelta(months=trailing_months)
        window_data = df.filter(
            (pl.col(purchase_date_col) >= window_start) & (pl.col(purchase_date_col) <= selected_date)
        )

        if window_data.is_empty():
            logger.warning("No data available for time point %s", selected_date)
            return {}

        return self._calculate_cost_basis_from_dataframe(window_data)

    def _register_with_dependency_manager(self) -> None:
        """Register this calculator's cache with the dependency manager."""
        try:
            dependency_manager = get_cache_dependency_manager()
            dependency_manager.register_cache("cost_calculation", self._cache)
            dependency_manager.add_dependency("recipe", "cost_calculation")
            dependency_manager.add_dependency("material_purchases", "cost_calculation")
            logger.info("Registered cost calculation cache with dependency manager")
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to register with dependency manager: %s", exc)
