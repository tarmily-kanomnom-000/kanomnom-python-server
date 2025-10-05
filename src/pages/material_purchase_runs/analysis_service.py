"""Analytical services for material purchase runs."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import groupby
from typing import Iterable, Sequence

import polars as pl

from shared.grist_material_transformer import normalize_material_purchase_dataframe
from shared.grist_schema import MaterialPurchaseSchema

from .usage_estimation import (
    MaterialUsageEstimator,
    UsageInterval,
    create_default_kalman_estimator,
)


@dataclass(slots=True)
class AdaptiveUsageConfig:
    """Configuration for adaptive usage calculations."""

    decay_factor: float = 0.6
    max_intervals: int = 6
    minimum_interval_days: float = 1.0
    maximum_interval_days: float = 120.0
    infrequent_threshold_days: float = 120.0


@dataclass(slots=True)
class SupplyRunConfig:
    """Configuration for supply run forecasting."""

    grouping_window_days: int = 7
    upcoming_horizon_days: int = 60
    low_supply_threshold_days: int = 7
    minimum_purchase_count: int = 3


@dataclass(slots=True)
class MaterialPurchaseProjection:
    """Derived metrics for a material's purchase cadence and usage."""

    material: str
    unit: str | None
    total_purchases: int
    last_purchase_date: datetime | None
    average_units_per_purchase: float | None
    units_last_purchase: float | None
    purchase_frequency_days: float | None
    usage_per_day: float | None
    days_since_last_purchase: float | None
    days_until_runout: float | None
    estimated_runout_date: datetime | None
    best_source: str | None
    best_unit_cost: float | None
    units_remaining_estimate: float | None
    usage_confidence: float


@dataclass(slots=True)
class SupplyRunGroup:
    """Grouping of materials that should share a supply run."""

    label: str
    target_date: datetime
    materials: list[MaterialPurchaseProjection]


@dataclass(slots=True)
class MaterialPurchaseAnalyticsResult:
    """Full analytics payload for the UI layer."""

    generated_at: datetime
    projections: list[MaterialPurchaseProjection]
    low_supply: list[MaterialPurchaseProjection]
    supply_run_groups: list[SupplyRunGroup]


class MaterialPurchaseAnalyticsService:
    """Service that analyses material purchase history and forecasts supply runs."""

    def __init__(
        self,
        usage_config: AdaptiveUsageConfig,
        run_config: SupplyRunConfig,
        usage_estimator: MaterialUsageEstimator | None = None,
    ) -> None:
        self._usage_config = usage_config
        self._run_config = run_config
        self._schema = MaterialPurchaseSchema.default()
        self._usage_estimator = usage_estimator or create_default_kalman_estimator()

    def analyze(self, dataframe: pl.DataFrame, min_purchases: int | None) -> MaterialPurchaseAnalyticsResult:
        """Analyze purchase history and return projections."""

        if dataframe.is_empty():
            now = datetime.now()
            return MaterialPurchaseAnalyticsResult(now, [], [], [])

        threshold = self._resolve_min_purchases(min_purchases)

        normalized = self._normalize_dataframe(dataframe)
        records = normalized.sort(["material", "purchase_date"]).to_dicts()
        if not records:
            now = datetime.now()
            return MaterialPurchaseAnalyticsResult(now, [], [], [])

        best_source_map = self._derive_best_sources(records)
        projections = self._build_projections(records, best_source_map, threshold)

        low_supply = [
            projection
            for projection in projections
            if projection.days_until_runout is not None
            and projection.days_until_runout <= self._run_config.low_supply_threshold_days
        ]

        supply_run_groups = self._group_supply_runs(projections)
        return MaterialPurchaseAnalyticsResult(datetime.now(), projections, low_supply, supply_run_groups)

    def _normalize_dataframe(self, dataframe: pl.DataFrame) -> pl.DataFrame:
        normalized = normalize_material_purchase_dataframe(dataframe, self._schema)

        required_columns = ["material", "purchase_date", "package_size", "quantity", "unit"]
        missing = [column for column in required_columns if column not in normalized.columns]
        if missing:
            raise KeyError(f"Missing required normalized columns: {', '.join(sorted(missing))}")

        selected_order = [
            "material",
            "purchase_date",
            "package_size",
            "quantity",
            "unit",
            "units_purchased",
            "total_cost",
            "unit_cost",
            "purchase_source",
        ]
        existing = [column for column in selected_order if column in normalized.columns]
        return normalized.select(existing)

    def _derive_best_sources(self, records: Sequence[dict[str, object]]) -> dict[str, tuple[str | None, float | None]]:
        best_sources: dict[str, tuple[str | None, float | None]] = {}
        for record in records:
            material = record.get("material")
            source = record.get("purchase_source")
            unit_cost = record.get("unit_cost")
            if not isinstance(material, str):
                continue
            if not isinstance(source, str):
                continue
            if unit_cost is None:
                continue
            try:
                cost_value = float(unit_cost)
            except (TypeError, ValueError):
                continue

            current_best = best_sources.get(material)
            if current_best is None or current_best[1] is None or cost_value < current_best[1]:
                best_sources[material] = (source, cost_value)
        return best_sources

    def _build_projections(
        self,
        records: Sequence[dict[str, object]],
        best_sources: dict[str, tuple[str | None, float | None]],
        min_purchases: int,
    ) -> list[MaterialPurchaseProjection]:
        projections: list[MaterialPurchaseProjection] = []

        def _material_key(row: dict[str, object]) -> object:
            return row.get("material")

        for material, group_iter in groupby(records, key=_material_key):
            if not isinstance(material, str):
                continue
            group_records = list(group_iter)
            if not group_records:
                continue
            projection = self._analyze_material(material, group_records, best_sources.get(material))
            if projection and projection.total_purchases >= max(1, min_purchases):
                projections.append(projection)
        projections.sort(key=lambda item: (item.days_until_runout is None, item.days_until_runout or 0.0))
        return projections

    def _analyze_material(
        self,
        material: str,
        records: list[dict[str, object]],
        best_source: tuple[str | None, float | None] | None,
    ) -> MaterialPurchaseProjection | None:
        records_sorted = sorted(records, key=lambda row: row.get("purchase_date") or datetime.min)
        total_purchases = len(records_sorted)
        last_record = records_sorted[-1]

        last_purchase_date = (
            last_record.get("purchase_date") if isinstance(last_record.get("purchase_date"), datetime) else None
        )
        unit_counts = Counter()
        for record in records_sorted:
            unit_value = record.get("unit")
            if isinstance(unit_value, str) and unit_value.strip():
                unit_counts[unit_value.strip()] += 1
        unit = None
        if unit_counts:
            unit = unit_counts.most_common(1)[0][0]
        elif isinstance(last_record.get("unit"), str):
            unit = last_record.get("unit")
        units_last_purchase = self._to_float(last_record.get("units_purchased"))
        avg_units = self._compute_average_units(records_sorted)

        intervals = self._build_usage_intervals(records_sorted)

        frequency_samples = [interval.duration_days for interval in intervals]
        purchase_frequency_days = self._weighted_average(list(reversed(frequency_samples)))

        infrequent_material = (
            purchase_frequency_days is not None
            and self._usage_config.infrequent_threshold_days > 0
            and purchase_frequency_days > self._usage_config.infrequent_threshold_days
        )

        usage_per_day: float | None = None
        usage_confidence = 0.0

        bias_days = self._estimate_reorder_bias(records_sorted)

        if not infrequent_material and intervals:
            usage_estimate = self._usage_estimator.estimate(intervals)
            usage_per_day = usage_estimate.usage_per_day
            usage_confidence = usage_estimate.confidence

        now = (
            datetime.now(tz=last_purchase_date.tzinfo)
            if last_purchase_date and last_purchase_date.tzinfo
            else datetime.now()
        )
        days_since_last_purchase = self._calculate_days_between(last_purchase_date, now)

        if (
            not infrequent_material
            and usage_per_day is None
            and units_last_purchase is not None
            and days_since_last_purchase is not None
        ):
            if days_since_last_purchase > 0:
                usage_per_day = units_last_purchase / max(
                    days_since_last_purchase, self._usage_config.minimum_interval_days
                )
                usage_confidence = max(usage_confidence, 0.3)

        units_remaining_estimate = None
        days_until_runout = None
        estimated_runout_date = None

        if (
            not infrequent_material
            and usage_per_day is not None
            and usage_per_day > 0
            and units_last_purchase is not None
        ):
            if days_since_last_purchase is None:
                days_since_last_purchase = 0.0
            units_consumed = usage_per_day * days_since_last_purchase
            units_remaining_estimate = max(units_last_purchase - units_consumed, 0.0)
            if usage_per_day > 0:
                days_until_runout = units_remaining_estimate / usage_per_day
                if bias_days is not None and days_until_runout is not None:
                    adjusted_days = max(days_until_runout - bias_days, 0.0)
                    units_remaining_estimate = usage_per_day * adjusted_days
                    days_until_runout = adjusted_days
                estimated_runout_date = now + timedelta(days=days_until_runout)
        elif (
            not infrequent_material
            and units_last_purchase is not None
            and units_last_purchase > 0
            and purchase_frequency_days is not None
        ):
            adjusted_frequency = purchase_frequency_days
            if bias_days is not None:
                adjusted_frequency = max(purchase_frequency_days - bias_days, 0.0)
            days_until_runout = adjusted_frequency
            estimated_runout_date = now + timedelta(days=adjusted_frequency)

        best_source_name, best_unit_cost = best_source if best_source else (None, None)

        if infrequent_material:
            usage_confidence = 0.0

        if usage_confidence < 0.2:
            days_until_runout = None
            estimated_runout_date = None

        return MaterialPurchaseProjection(
            material=material,
            unit=unit,
            total_purchases=total_purchases,
            last_purchase_date=last_purchase_date,
            average_units_per_purchase=avg_units,
            units_last_purchase=units_last_purchase,
            purchase_frequency_days=purchase_frequency_days,
            usage_per_day=usage_per_day,
            days_since_last_purchase=days_since_last_purchase,
            days_until_runout=days_until_runout,
            estimated_runout_date=estimated_runout_date,
            best_source=best_source_name,
            best_unit_cost=best_unit_cost,
            units_remaining_estimate=units_remaining_estimate,
            usage_confidence=usage_confidence,
        )

    def _build_usage_intervals(self, records: Sequence[dict[str, object]]) -> list[UsageInterval]:
        intervals: list[UsageInterval] = []
        for index in range(len(records) - 1):
            current = records[index]
            nxt = records[index + 1]
            start = current.get("purchase_date")
            end = nxt.get("purchase_date")
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue
            delta_days = self._calculate_days_between(start, end)
            if delta_days is None:
                continue
            if self._usage_config.maximum_interval_days > 0 and delta_days > self._usage_config.maximum_interval_days:
                continue

            units = self._to_float(current.get("units_purchased"))
            interval = UsageInterval.from_purchases(
                start,
                end,
                units,
                minimum_duration=self._usage_config.minimum_interval_days,
            )
            if interval is None:
                continue
            intervals.append(interval)

        if self._usage_config.max_intervals > 0 and len(intervals) > self._usage_config.max_intervals:
            intervals = intervals[-self._usage_config.max_intervals :]
        return intervals

    def _estimate_reorder_bias(self, records: Sequence[dict[str, object]]) -> float | None:
        if len(records) < 3:
            return None

        biases: list[float] = []
        for pivot in range(2, len(records) - 1):
            history_records = records[: pivot + 1]
            history_intervals = self._build_usage_intervals(history_records)
            if not history_intervals:
                continue

            usage_estimate = self._usage_estimator.estimate(history_intervals)
            usage = usage_estimate.usage_per_day
            if usage is None or usage <= 0:
                continue

            last_record = history_records[-1]
            units_last = self._to_float(last_record.get("units_purchased"))
            if units_last is None or units_last <= 0:
                continue

            last_purchase = last_record.get("purchase_date")
            next_purchase = records[pivot + 1].get("purchase_date")
            if not isinstance(last_purchase, datetime) or not isinstance(next_purchase, datetime):
                continue

            actual_days = self._calculate_days_between(last_purchase, next_purchase)
            if actual_days is None or actual_days <= 0:
                continue

            predicted_days = units_last / usage
            biases.append(predicted_days - actual_days)

        if not biases:
            return None

        biases.sort()
        return biases[len(biases) // 2]

    def _resolve_min_purchases(self, min_purchases: int | None) -> int:
        configured_default = max(1, self._run_config.minimum_purchase_count)
        if min_purchases is None:
            return configured_default
        return max(1, min_purchases)

    def _compute_average_units(self, records: Sequence[dict[str, object]]) -> float | None:
        units: list[float] = []
        for record in records:
            value = self._to_float(record.get("units_purchased"))
            if value is not None and value > 0:
                units.append(value)
        if not units:
            return None
        return sum(units) / len(units)

    def _weighted_average(self, values: Iterable[float | None]) -> float | None:
        filtered_values: list[float] = [value for value in values if value is not None]
        if not filtered_values:
            return None
        weights: list[float] = []
        weighted_values: list[float] = []
        for index, value in enumerate(filtered_values):
            weight = self._usage_config.decay_factor**index
            weights.append(weight)
            weighted_values.append(value * weight)
        total_weight = sum(weights)
        if total_weight == 0:
            return None
        return sum(weighted_values) / total_weight

    def _calculate_days_between(self, earlier: datetime | None, later: datetime | None) -> float | None:
        if earlier is None or later is None:
            return None
        delta = later - earlier
        return delta.total_seconds() / 86400.0

    def _to_float(self, value: object) -> float | None:
        if value is None:
            return None
        try:
            numeric = float(value)  # type: ignore[arg-type]
            return numeric
        except (TypeError, ValueError):
            return None

    def _group_supply_runs(self, projections: Sequence[MaterialPurchaseProjection]) -> list[SupplyRunGroup]:
        groups: dict[datetime, list[MaterialPurchaseProjection]] = {}
        now = datetime.now()
        horizon_limit = now + timedelta(days=self._run_config.upcoming_horizon_days)

        for projection in projections:
            if projection.estimated_runout_date is None:
                continue
            if projection.days_until_runout is None:
                continue
            if projection.days_until_runout < 0:
                continue
            if projection.estimated_runout_date > horizon_limit:
                continue
            bucket_start = self._bucket_start(projection.estimated_runout_date)
            groups.setdefault(bucket_start, []).append(projection)

        supply_groups: list[SupplyRunGroup] = []
        for bucket, materials in sorted(groups.items(), key=lambda item: item[0]):
            label = self._format_group_label(bucket)
            supply_groups.append(SupplyRunGroup(label=label, target_date=bucket, materials=materials))

        return supply_groups

    def _bucket_start(self, date: datetime) -> datetime:
        window = max(self._run_config.grouping_window_days, 1)
        anchor = datetime(date.year, date.month, date.day)
        ordinal = anchor.toordinal()
        offset = ordinal % window
        bucket_day = ordinal - offset
        if bucket_day < 1:
            bucket_day = 1
        bucket_date = datetime.fromordinal(bucket_day)
        return bucket_date

    def _format_group_label(self, bucket_start: datetime) -> str:
        if self._run_config.grouping_window_days == 7:
            return f"Week of {bucket_start.strftime('%Y-%m-%d')}"
        return f"Run window starting {bucket_start.strftime('%Y-%m-%d')}"
