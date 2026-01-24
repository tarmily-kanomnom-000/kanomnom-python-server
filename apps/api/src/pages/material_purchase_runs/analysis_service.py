"""Analytical services for material purchase runs."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import groupby
from statistics import NormalDist
from typing import Iterable, Sequence

import polars as pl
from shared.grist_material_transformer import normalize_material_purchase_dataframe
from shared.grist_schema import MaterialPurchaseSchema

from .usage_estimation import (
    MaterialUsageEstimator,
    UsageInterval,
    create_default_kalman_estimator,
)

PROBABILITY_INTERVAL = (0.1, 0.9)


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
    target_run_interval_days: int = 14


@dataclass(slots=True)
class RemainingSupplyWindow:
    """Probabilistic bounds for remaining supply days."""

    lower_days: float | None
    upper_days: float | None
    lower_date: datetime | None
    upper_date: datetime | None
    confidence: float


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
    remaining_supply_window: RemainingSupplyWindow | None


@dataclass(slots=True)
class SupplyRunAssignment:
    """Assignment details for a material within a scheduled supply run."""

    projection: MaterialPurchaseProjection
    run_offset_days: float
    lower_days_available: float | None
    expected_days_available: float | None
    buffer_days: float | None
    violates_cadence: bool
    is_unreliable: bool
    projected_units_on_run_date: float | None
    recommended_purchase_units: float | None
    recommended_purchase_cost: float | None


@dataclass(slots=True)
class ScheduledSupplyRun:
    """Scheduled supply run adhering to the configured cadence."""

    label: str
    scheduled_date: datetime
    offset_days: float
    assignments: list[SupplyRunAssignment]


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
    cadence_schedule: list[ScheduledSupplyRun]
    cadence_warnings: list[SupplyRunAssignment]
    run_interval_days: int


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

    def analyze(
        self,
        dataframe: pl.DataFrame,
        min_purchases: int | None,
        *,
        reference_date: datetime | None = None,
    ) -> MaterialPurchaseAnalyticsResult:
        """Analyze purchase history and return projections."""

        analysis_time = reference_date or datetime.now()

        if dataframe.is_empty():
            return MaterialPurchaseAnalyticsResult(
                generated_at=analysis_time,
                projections=[],
                low_supply=[],
                cadence_schedule=[],
                cadence_warnings=[],
                run_interval_days=max(1, self._run_config.target_run_interval_days),
            )

        threshold = self._resolve_min_purchases(min_purchases)

        normalized = self._normalize_dataframe(dataframe)
        records = normalized.sort(["material", "purchase_date"]).to_dicts()
        if not records:
            return MaterialPurchaseAnalyticsResult(
                generated_at=analysis_time,
                projections=[],
                low_supply=[],
                cadence_schedule=[],
                cadence_warnings=[],
                run_interval_days=max(1, self._run_config.target_run_interval_days),
            )

        best_source_map = self._derive_best_sources(records)
        projections = self._build_projections(
            records, best_source_map, threshold, analysis_time
        )

        low_supply = [
            projection
            for projection in projections
            if projection.days_until_runout is not None
            and projection.days_until_runout
            <= self._run_config.low_supply_threshold_days
        ]

        cadence_schedule, cadence_warnings = self._build_cadence_schedule(
            projections, analysis_time
        )

        return MaterialPurchaseAnalyticsResult(
            generated_at=analysis_time,
            projections=projections,
            low_supply=low_supply,
            cadence_schedule=cadence_schedule,
            cadence_warnings=cadence_warnings,
            run_interval_days=max(1, self._run_config.target_run_interval_days),
        )

    def _normalize_dataframe(self, dataframe: pl.DataFrame) -> pl.DataFrame:
        normalized = normalize_material_purchase_dataframe(dataframe, self._schema)

        required_columns = [
            "material",
            "purchase_date",
            "package_size",
            "quantity",
            "unit",
        ]
        missing = [
            column for column in required_columns if column not in normalized.columns
        ]
        if missing:
            raise KeyError(
                f"Missing required normalized columns: {', '.join(sorted(missing))}"
            )

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

    def _derive_best_sources(
        self, records: Sequence[dict[str, object]]
    ) -> dict[str, tuple[str | None, float | None]]:
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
            if (
                current_best is None
                or current_best[1] is None
                or cost_value < current_best[1]
            ):
                best_sources[material] = (source, cost_value)
        return best_sources

    def _build_projections(
        self,
        records: Sequence[dict[str, object]],
        best_sources: dict[str, tuple[str | None, float | None]],
        min_purchases: int,
        analysis_time: datetime,
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
            projection = self._analyze_material(
                material,
                group_records,
                best_sources.get(material),
                analysis_time,
            )
            if projection and projection.total_purchases >= max(1, min_purchases):
                projections.append(projection)
        projections.sort(
            key=lambda item: (
                item.days_until_runout is None,
                item.days_until_runout or 0.0,
            )
        )
        return projections

    def _analyze_material(
        self,
        material: str,
        records: list[dict[str, object]],
        best_source: tuple[str | None, float | None] | None,
        analysis_time: datetime,
    ) -> MaterialPurchaseProjection | None:
        records_sorted = sorted(
            records, key=lambda row: row.get("purchase_date") or datetime.min
        )
        total_purchases = len(records_sorted)
        last_record = records_sorted[-1]

        last_purchase_date = (
            last_record.get("purchase_date")
            if isinstance(last_record.get("purchase_date"), datetime)
            else None
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
        purchase_frequency_days = self._weighted_average(
            list(reversed(frequency_samples))
        )

        infrequent_material = (
            purchase_frequency_days is not None
            and self._usage_config.infrequent_threshold_days > 0
            and purchase_frequency_days > self._usage_config.infrequent_threshold_days
        )

        usage_per_day: float | None = None
        usage_confidence = 0.0
        usage_variance: float | None = None

        bias_days = self._estimate_reorder_bias(records_sorted)

        if not infrequent_material and intervals:
            usage_estimate = self._usage_estimator.estimate(intervals)
            usage_per_day = usage_estimate.usage_per_day
            usage_confidence = usage_estimate.confidence
            usage_variance = usage_estimate.usage_variance

        if (
            last_purchase_date
            and last_purchase_date.tzinfo
            and analysis_time.tzinfo is None
        ):
            now = analysis_time.replace(tzinfo=last_purchase_date.tzinfo)
        else:
            now = analysis_time

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
        remaining_supply_window: RemainingSupplyWindow | None = None

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
                total_units = units_last_purchase
                if isinstance(last_purchase_date, datetime):
                    aggregated_units = self._aggregate_same_day_units(
                        records_sorted, last_purchase_date
                    )
                    if aggregated_units is not None:
                        total_units = aggregated_units
                remaining_supply_window = self._probabilistic_remaining_supply_window(
                    units_purchased=total_units,
                    usage_mean=usage_per_day,
                    usage_variance=usage_variance,
                    days_since_last_purchase=(
                        days_since_last_purchase
                        if days_since_last_purchase is not None
                        else 0.0
                    ),
                    bias_days=bias_days,
                    now=now,
                )
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
            remaining_supply_window = None

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
            remaining_supply_window=remaining_supply_window,
        )

    def _build_usage_intervals(
        self, records: Sequence[dict[str, object]]
    ) -> list[UsageInterval]:
        merged_records = self._merge_same_day_records(records)
        intervals: list[UsageInterval] = []
        for index in range(len(merged_records) - 1):
            current = merged_records[index]
            nxt = merged_records[index + 1]
            start = current.get("purchase_date")
            end = nxt.get("purchase_date")
            if not isinstance(start, datetime) or not isinstance(end, datetime):
                continue
            delta_days = self._calculate_days_between(start, end)
            if delta_days is None:
                continue
            if (
                self._usage_config.maximum_interval_days > 0
                and delta_days > self._usage_config.maximum_interval_days
            ):
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

        if (
            self._usage_config.max_intervals > 0
            and len(intervals) > self._usage_config.max_intervals
        ):
            intervals = intervals[-self._usage_config.max_intervals :]
        return intervals

    def _merge_same_day_records(
        self, records: Sequence[dict[str, object]]
    ) -> list[dict[str, object]]:
        merged: list[dict[str, object]] = []
        for record in records:
            purchase_date = record.get("purchase_date")
            if merged:
                last_record = merged[-1]
                last_date = last_record.get("purchase_date")
                if (
                    isinstance(purchase_date, datetime)
                    and isinstance(last_date, datetime)
                    and purchase_date == last_date
                ):
                    merged[-1] = self._combine_same_day_record(last_record, record)
                    continue
            merged.append(record.copy())
        return merged

    def _combine_same_day_record(
        self,
        base: dict[str, object],
        extra: dict[str, object],
    ) -> dict[str, object]:
        combined = base.copy()
        combined["units_purchased"] = self._sum_numeric(
            base.get("units_purchased"), extra.get("units_purchased")
        )
        combined["quantity"] = self._sum_numeric(
            base.get("quantity"), extra.get("quantity")
        )
        combined["total_cost"] = self._sum_numeric(
            base.get("total_cost"), extra.get("total_cost")
        )
        combined["total_cost_USD"] = self._sum_numeric(
            base.get("total_cost_USD"), extra.get("total_cost_USD")
        )
        return combined

    def _aggregate_same_day_units(
        self,
        records: Sequence[dict[str, object]],
        purchase_date: datetime,
    ) -> float | None:
        total = 0.0
        found = False
        for record in records:
            candidate_date = record.get("purchase_date")
            if isinstance(candidate_date, datetime) and candidate_date == purchase_date:
                units_value = self._to_float(record.get("units_purchased"))
                if units_value is None:
                    continue
                total += units_value
                found = True
        return total if found else None

    def _estimate_reorder_bias(
        self, records: Sequence[dict[str, object]]
    ) -> float | None:
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
            last_purchase = last_record.get("purchase_date")
            if not isinstance(last_purchase, datetime):
                continue

            units_last = self._aggregate_same_day_units(history_records, last_purchase)
            if units_last is None or units_last <= 0:
                continue

            next_purchase = records[pivot + 1].get("purchase_date")
            if not isinstance(last_purchase, datetime) or not isinstance(
                next_purchase, datetime
            ):
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

    def _probabilistic_remaining_supply_window(
        self,
        *,
        units_purchased: float | None,
        usage_mean: float | None,
        usage_variance: float | None,
        days_since_last_purchase: float,
        bias_days: float | None,
        now: datetime,
    ) -> RemainingSupplyWindow | None:
        if units_purchased is None or units_purchased <= 0:
            return None
        if usage_mean is None or usage_mean <= 0:
            return None
        if usage_variance is None or usage_variance <= 0:
            return None

        log_params = self._lognormal_parameters(usage_mean, usage_variance)
        if log_params is None:
            return None

        usage_log_mu, usage_log_sigma = log_params
        if not math.isfinite(usage_log_mu) or not math.isfinite(usage_log_sigma):
            return None

        total_log_mu = math.log(units_purchased) - usage_log_mu
        total_log_sigma = usage_log_sigma

        if not math.isfinite(total_log_mu) or not math.isfinite(total_log_sigma):
            return None

        normal = NormalDist()
        offset = days_since_last_purchase + (bias_days or 0.0)

        sampled_days: list[float] = []
        for quantile in PROBABILITY_INTERVAL:
            z_score = normal.inv_cdf(quantile)
            total_days = math.exp(total_log_mu + total_log_sigma * z_score)
            remaining = max(total_days - offset, 0.0)
            sampled_days.append(remaining)

        lower, upper = sorted(sampled_days)
        if upper <= 0.0:
            return None

        lower_date = now + timedelta(days=lower)
        upper_date = now + timedelta(days=upper)

        return RemainingSupplyWindow(
            lower_days=lower,
            upper_days=upper,
            lower_date=lower_date,
            upper_date=upper_date,
            confidence=PROBABILITY_INTERVAL[1] - PROBABILITY_INTERVAL[0],
        )

    def _lognormal_parameters(
        self, mean: float, variance: float
    ) -> tuple[float, float] | None:
        if mean <= 0:
            return None
        if variance <= 0:
            return None

        try:
            ratio = variance / (mean * mean)
            if ratio <= 0:
                return None
            sigma_squared = math.log1p(ratio)
        except (ValueError, OverflowError):
            return None

        if sigma_squared < 0:
            return None

        sigma = math.sqrt(sigma_squared)
        mu = math.log(mean) - sigma_squared / 2
        return mu, sigma

    def _build_cadence_schedule(
        self,
        projections: Sequence[MaterialPurchaseProjection],
        analysis_time: datetime,
    ) -> tuple[list[ScheduledSupplyRun], list[SupplyRunAssignment]]:
        interval = max(1, self._run_config.target_run_interval_days)
        horizon = max(interval, self._run_config.upcoming_horizon_days)
        run_count = max(1, math.ceil(horizon / interval) + 1)

        runs: list[ScheduledSupplyRun] = []
        for index in range(run_count):
            offset_days = float(index * interval)
            scheduled_date = analysis_time + timedelta(days=offset_days)
            label = "Today" if index == 0 else f"Run {index + 1}"
            runs.append(
                ScheduledSupplyRun(
                    label=label,
                    scheduled_date=scheduled_date,
                    offset_days=offset_days,
                    assignments=[],
                )
            )

        cadence_warnings: list[SupplyRunAssignment] = []

        for projection in projections:
            lower_bound = self._lower_runout_bound(projection)
            expected = projection.days_until_runout

            safe_lower = lower_bound if lower_bound is not None else expected
            if safe_lower is not None:
                safe_lower = max(0.0, safe_lower)

            chosen_index = 0
            if safe_lower is not None:
                candidates = [
                    idx for idx, run in enumerate(runs) if run.offset_days <= safe_lower
                ]
                if candidates:
                    chosen_index = max(candidates)
            assignment_run = runs[chosen_index]

            buffer_days = None
            if lower_bound is not None:
                buffer_days = lower_bound - assignment_run.offset_days

            violates_cadence = False
            if lower_bound is not None:
                violates_cadence = lower_bound < interval

            is_unreliable = lower_bound is None or projection.usage_confidence < 0.2

            assignment = SupplyRunAssignment(
                projection=projection,
                run_offset_days=assignment_run.offset_days,
                lower_days_available=lower_bound,
                expected_days_available=expected,
                buffer_days=buffer_days,
                violates_cadence=violates_cadence,
                is_unreliable=is_unreliable,
                projected_units_on_run_date=None,
                recommended_purchase_units=None,
                recommended_purchase_cost=None,
            )
            self._populate_purchase_plan(assignment, interval)
            assignment_run.assignments.append(assignment)

            if violates_cadence or is_unreliable:
                cadence_warnings.append(assignment)

        scheduled_runs = [run for run in runs if run.assignments]
        if not scheduled_runs and runs:
            scheduled_runs = [runs[0]]

        return scheduled_runs, cadence_warnings

    def _lower_runout_bound(
        self, projection: MaterialPurchaseProjection
    ) -> float | None:
        window = projection.remaining_supply_window
        if window and window.lower_days is not None:
            return window.lower_days
        return projection.days_until_runout

    def _populate_purchase_plan(
        self, assignment: SupplyRunAssignment, interval_days: int
    ) -> None:
        projection = assignment.projection
        usage = projection.usage_per_day
        if usage is None or usage <= 0:
            return

        projected_units = self._project_units_on_run_date(
            projection, assignment.run_offset_days
        )
        assignment.projected_units_on_run_date = projected_units

        required_units = usage * interval_days
        available_units = projected_units if projected_units is not None else 0.0
        recommended_units = max(required_units - available_units, 0.0)
        assignment.recommended_purchase_units = recommended_units

        if projection.best_unit_cost is not None:
            assignment.recommended_purchase_cost = (
                recommended_units * projection.best_unit_cost
            )

    def _project_units_on_run_date(
        self,
        projection: MaterialPurchaseProjection,
        run_offset_days: float,
    ) -> float | None:
        usage = projection.usage_per_day
        if usage is None or usage <= 0:
            return None

        days_since_last = projection.days_since_last_purchase or 0.0
        base_units = projection.units_last_purchase
        total_days_since_last = days_since_last + run_offset_days

        if base_units is not None:
            projected = base_units - usage * total_days_since_last
        elif projection.units_remaining_estimate is not None:
            projected = projection.units_remaining_estimate - usage * run_offset_days
        else:
            return None

        if not math.isfinite(projected):
            return None

        return max(projected, 0.0)

    def _resolve_min_purchases(self, min_purchases: int | None) -> int:
        configured_default = max(1, self._run_config.minimum_purchase_count)
        if min_purchases is None:
            return configured_default
        return max(1, min_purchases)

    def _compute_average_units(
        self, records: Sequence[dict[str, object]]
    ) -> float | None:
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

    def _calculate_days_between(
        self, earlier: datetime | None, later: datetime | None
    ) -> float | None:
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

    def _sum_numeric(self, first: object | None, second: object | None) -> float | None:
        first_value = self._to_float(first)
        second_value = self._to_float(second)
        if first_value is None and second_value is None:
            return None
        return (first_value or 0.0) + (second_value or 0.0)

    def _group_supply_runs(
        self,
        projections: Sequence[MaterialPurchaseProjection],
        analysis_time: datetime,
    ) -> list[SupplyRunGroup]:
        groups: dict[datetime, list[MaterialPurchaseProjection]] = {}
        horizon_limit = analysis_time + timedelta(
            days=self._run_config.upcoming_horizon_days
        )

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
            supply_groups.append(
                SupplyRunGroup(label=label, target_date=bucket, materials=materials)
            )

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
