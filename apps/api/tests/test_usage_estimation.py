from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Sequence

import matplotlib.pyplot as plt
import optuna
import polars as pl
import pytest

from pages.material_purchase_runs.analysis_service import (
    AdaptiveUsageConfig,
    MaterialPurchaseAnalyticsService,
    SupplyRunConfig,
)
from pages.material_purchase_runs.usage_estimation import (
    KalmanFilterConfig,
    KalmanUsageEstimator,
    MaterialUsageEstimator,
    UsageEstimate,
    UsageInterval,
    load_kalman_parameters,
)
from shared.grist_schema import MaterialPurchaseSchema
from shared.grist_service import DataFilterManager

KALMAN_CONFIG_PATH = Path("src/pages/material_purchase_runs/kalman_parameters.json")
OPTUNA_TRIALS = 100
OPTUNA_SEED = 42


def _build_constant_usage_intervals(units_per_purchase: float, interval_days: int, count: int) -> list[UsageInterval]:
    start = datetime(2024, 1, 1)
    intervals: list[UsageInterval] = []
    for index in range(count):
        interval_start = start + timedelta(days=interval_days * index)
        interval_end = start + timedelta(days=interval_days * (index + 1))
        interval = UsageInterval.from_purchases(
            interval_start,
            interval_end,
            units_per_purchase,
            minimum_duration=1.0,
        )
        assert interval is not None
        intervals.append(interval)
    return intervals


class _StubEstimator(MaterialUsageEstimator):
    def estimate(self, intervals: Sequence[UsageInterval]) -> UsageEstimate:
        return UsageEstimate(
            usage_per_day=None,
            usage_variance=None,
            confidence=0.0,
            samples=len(intervals),
            process_variance=None,
            measurement_variance=None,
        )


def test_usage_interval_builder_merges_same_day_purchases() -> None:
    service = MaterialPurchaseAnalyticsService(
        AdaptiveUsageConfig(),
        SupplyRunConfig(),
        usage_estimator=_StubEstimator(),
    )

    purchase_day = datetime(2025, 1, 1)
    records = [
        {
            "purchase_date": purchase_day,
            "units_purchased": 10.0,
        },
        {
            "purchase_date": purchase_day,
            "units_purchased": 5.0,
        },
        {
            "purchase_date": purchase_day + timedelta(days=10),
            "units_purchased": 8.0,
        },
    ]

    intervals = service._build_usage_intervals(records)

    assert len(intervals) == 1
    interval = intervals[0]
    assert interval.units == 15.0
    assert interval.duration_days >= service._usage_config.minimum_interval_days


def test_analysis_produces_probabilistic_supply_window() -> None:
    rows = _generate_purchase_rows(purchase_count=6, interval_days=10)
    history_rows = rows[:-1]
    dataframe = pl.DataFrame(history_rows)

    estimator = KalmanUsageEstimator(config=load_kalman_parameters(KALMAN_CONFIG_PATH))
    service = MaterialPurchaseAnalyticsService(AdaptiveUsageConfig(), SupplyRunConfig(), usage_estimator=estimator)

    reference_date = history_rows[-1]["Purchase_Date"]
    result = service.analyze(
        dataframe,
        min_purchases=3,
        reference_date=reference_date,
    )

    projection = next((item for item in result.projections if item.material == "Test Material"), None)
    assert projection is not None

    window = projection.remaining_supply_window
    assert window is not None
    assert window.lower_days is not None
    assert window.upper_days is not None
    assert window.lower_days < window.upper_days
    assert window.confidence == pytest.approx(0.8, rel=1e-6)
    assert window.lower_date is not None
    assert window.upper_date is not None

    assert result.cadence_schedule
    assert result.run_interval_days == 14
    assert any(run.assignments for run in result.cadence_schedule)
    today_run = result.cadence_schedule[0]
    assignment = next(item for item in today_run.assignments if item.projection.material == "Test Material")
    assert assignment.recommended_purchase_units is not None
    assert assignment.recommended_purchase_units > 0
    assert assignment.recommended_purchase_cost is not None


def test_kalman_estimator_tracks_constant_usage() -> None:
    config = load_kalman_parameters(KALMAN_CONFIG_PATH)
    estimator = KalmanUsageEstimator(config=config)
    intervals = _build_constant_usage_intervals(units_per_purchase=50.0, interval_days=10, count=6)

    estimate = estimator.estimate(intervals)

    assert estimate.usage_per_day is not None
    assert abs(estimate.usage_per_day - 5.0) < 0.2
    assert estimate.confidence > 0.6


def test_cadence_schedule_highlights_short_lived_materials() -> None:
    rows = _generate_purchase_rows(purchase_count=6, interval_days=5)
    history_rows = rows[:-1]
    dataframe = pl.DataFrame(history_rows)

    config = load_kalman_parameters(KALMAN_CONFIG_PATH)
    estimator = KalmanUsageEstimator(config=config)
    run_config = SupplyRunConfig(target_run_interval_days=14)
    service = MaterialPurchaseAnalyticsService(AdaptiveUsageConfig(), run_config, usage_estimator=estimator)

    reference_date = history_rows[-1]["Purchase_Date"]
    result = service.analyze(
        dataframe,
        min_purchases=3,
        reference_date=reference_date,
    )

    assert result.cadence_schedule
    warnings = [
        assignment for assignment in result.cadence_warnings if assignment.projection.material == "Test Material"
    ]
    assert warnings
    assert warnings[0].violates_cadence
    assert warnings[0].lower_days_available is not None
    assert warnings[0].lower_days_available < run_config.target_run_interval_days
    assert warnings[0].recommended_purchase_units is not None
    assert warnings[0].recommended_purchase_units > 0


def _generate_purchase_rows(purchase_count: int, interval_days: int) -> list[dict[str, object]]:
    """Create synthetic purchase history with an additional future purchase for evaluation."""

    anchor = datetime.now().replace(microsecond=0)
    start_offset = interval_days * purchase_count - interval_days / 2
    first_purchase = anchor - timedelta(days=start_offset)

    rows: list[dict[str, object]] = []
    for index in range(purchase_count + 1):
        purchase_date = first_purchase + timedelta(days=interval_days * index)
        rows.append(
            {
                "material": "Test Material",
                "Purchase_Date": purchase_date,
                "package_size": 10.0,
                "quantity_purchased": 5.0,
                "unit": "kg",
                "total_cost_USD": 100.0,
                "total_unit_cost_USD": 2.0,
                "purchase_source": "SupplierA",
            }
        )
    return rows


def _evaluate_prediction_accuracy(
    purchase_rows: Sequence[dict[str, object]],
    usage_config: AdaptiveUsageConfig,
    run_config: SupplyRunConfig,
    *,
    min_purchases: int,
) -> pl.DataFrame:
    metrics: list[dict[str, object]] = []

    minimum_history = min_purchases
    total_rows = len(purchase_rows)
    config = load_kalman_parameters(KALMAN_CONFIG_PATH)

    for history_size in range(minimum_history, total_rows):
        history_rows = purchase_rows[:history_size]
        actual_next_purchase = purchase_rows[history_size]["Purchase_Date"]

        dataframe = pl.DataFrame(history_rows)
        estimator = KalmanUsageEstimator(config=config)
        service = MaterialPurchaseAnalyticsService(usage_config, run_config, usage_estimator=estimator)

        reference_date = history_rows[-1]["Purchase_Date"]
        if not isinstance(reference_date, datetime):
            continue

        result = service.analyze(
            dataframe,
            min_purchases=minimum_history,
            reference_date=reference_date,
        )
        projection = next((proj for proj in result.projections if proj.material == "Test Material"), None)

        predicted_runout = projection.estimated_runout_date if projection else None
        confidence = projection.usage_confidence if projection else None
        usage = projection.usage_per_day if projection else None

        abs_error_days = None
        if predicted_runout is not None:
            abs_error_days = abs((predicted_runout - actual_next_purchase).total_seconds()) / 86400.0

        metrics.append(
            {
                "history_size": history_size,
                "predicted_next_purchase": predicted_runout,
                "actual_next_purchase": actual_next_purchase,
                "abs_error_days": abs_error_days,
                "usage_per_day": usage,
                "usage_confidence": confidence,
            }
        )

    return pl.DataFrame(metrics)


def _persist_accuracy_report(metrics: pl.DataFrame, *, stem: str) -> None:
    artifact_dir = Path("tests/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    csv_frame = metrics.with_columns(
        pl.col("predicted_next_purchase").dt.strftime("%Y-%m-%d %H:%M:%S").alias("predicted_next_purchase"),
        pl.col("actual_next_purchase").dt.strftime("%Y-%m-%d %H:%M:%S").alias("actual_next_purchase"),
        *(
            pl.col(column).dt.strftime("%Y-%m-%d %H:%M:%S").alias(column)
            for column, dtype in zip(metrics.columns, metrics.dtypes)
            if dtype == pl.Datetime and column not in {"predicted_next_purchase", "actual_next_purchase"}
        ),
    )
    csv_path = artifact_dir / f"{stem}.csv"
    csv_frame.write_csv(csv_path)


def _persist_accuracy_plot(metrics: pl.DataFrame, *, stem: str) -> None:
    if plt is None:
        return

    valid = metrics.drop_nulls(subset=["abs_error_days"])
    if valid.is_empty():
        return

    artifact_dir = Path("tests/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)

    history_sizes = valid.get_column("history_size").to_list()
    errors = valid.get_column("abs_error_days").to_list()
    confidences_raw = valid.get_column("usage_confidence").to_list()
    confidences = [value if value is not None else 0.0 for value in confidences_raw]

    plt.figure(figsize=(7, 4))
    scatter = plt.scatter(
        history_sizes,
        errors,
        c=confidences if any(confidences) else None,
        cmap="viridis",
        alpha=0.7,
        edgecolor="none",
    )
    if any(confidences):
        plt.colorbar(scatter, label="Usage confidence")
    plt.axhline(0, color="grey", linewidth=1, linestyle="--")
    plt.xlabel("Number of historical purchases")
    plt.ylabel("Absolute error (days)")
    plt.title("Kalman estimator prediction error")
    plt.tight_layout()
    plot_path = artifact_dir / f"{stem}.png"
    plt.savefig(plot_path, dpi=150)
    plt.close()


def test_material_purchase_service_predicts_next_purchase_window() -> None:
    usage_config = AdaptiveUsageConfig()
    run_config = SupplyRunConfig()
    purchase_rows = _generate_purchase_rows(purchase_count=5, interval_days=10)
    min_purchases = 3
    metrics = _evaluate_prediction_accuracy(
        purchase_rows,
        usage_config,
        run_config,
        min_purchases=min_purchases,
    )

    valid_metrics = metrics.drop_nulls(subset=["abs_error_days"])
    assert not valid_metrics.is_empty()

    mae = valid_metrics.get_column("abs_error_days").mean()
    max_error = valid_metrics.get_column("abs_error_days").max()

    print(
        f"Kalman estimator MAE: {mae:.2f} days; Max error: {max_error:.2f} days; runs={valid_metrics.height}",
    )

    _persist_accuracy_report(metrics, stem="kalman_prediction_accuracy_synthetic")
    _persist_accuracy_plot(metrics, stem="kalman_prediction_error_synthetic")


def _load_grist_dataframe() -> pl.DataFrame | None:
    manager = DataFilterManager()
    try:
        manager.load_grist_data()
    except Exception as exc:  # noqa: BLE001 - integration skip
        pytest.skip(f"Unable to load Grist data: {exc}")

    if manager.grist_dataframe is None or manager.grist_dataframe.is_empty():
        return None
    return manager.grist_dataframe


def _evaluate_real_materials(
    dataframe: pl.DataFrame,
    *,
    min_purchases: int,
    trailing_days: int,
    usage_config: AdaptiveUsageConfig,
    run_config: SupplyRunConfig,
    estimator_factory: Callable[[], KalmanUsageEstimator],
) -> pl.DataFrame:
    schema = MaterialPurchaseSchema.default()
    resolved = schema.resolve(dataframe)
    material_col = resolved["material_name"]
    purchase_col = resolved["purchase_date"]

    materials = dataframe.get_column(material_col).unique().to_list()
    metrics: list[dict[str, object]] = []

    for material in materials:
        material_df = dataframe.filter(pl.col(material_col) == material).sort(purchase_col)
        if material_df.height <= min_purchases:
            continue

        purchase_dates = material_df.get_column(purchase_col).to_list()
        for index in range(min_purchases, len(purchase_dates)):
            actual_next_purchase = purchase_dates[index]
            if not isinstance(actual_next_purchase, datetime):
                continue

            history_df = material_df.slice(0, index)
            if history_df.is_empty():
                continue

            window_start = actual_next_purchase - timedelta(days=trailing_days)
            history_window = history_df.filter(pl.col(purchase_col) >= window_start)
            if history_window.height < min_purchases:
                continue

            history_end = history_window.get_column(purchase_col).max()
            if not isinstance(history_end, datetime):
                continue

            service = MaterialPurchaseAnalyticsService(
                usage_config,
                run_config,
                usage_estimator=estimator_factory(),
            )

            result = service.analyze(
                history_window,
                min_purchases=min_purchases,
                reference_date=history_end,
            )
            if not result.projections:
                continue

            projection = result.projections[0]
            predicted_runout = projection.estimated_runout_date
            abs_error_days = None
            if predicted_runout is not None:
                abs_error_days = abs((predicted_runout - actual_next_purchase).total_seconds()) / 86400.0

            metrics.append(
                {
                    "material": material,
                    "history_size": history_window.height,
                    "history_start": window_start,
                    "history_end": history_end,
                    "predicted_next_purchase": predicted_runout,
                    "actual_next_purchase": actual_next_purchase,
                    "abs_error_days": abs_error_days,
                    "usage_per_day": projection.usage_per_day,
                    "usage_confidence": projection.usage_confidence,
                }
            )

    return pl.DataFrame(metrics) if metrics else pl.DataFrame()


def _run_optuna_parameter_search(
    dataframe: pl.DataFrame,
    *,
    min_purchases: int,
    trailing_days: int,
    usage_config: AdaptiveUsageConfig,
    run_config: SupplyRunConfig,
) -> tuple[pl.DataFrame, dict[str, float | int], dict[str, object]]:
    if optuna is None:
        pytest.skip("Optuna not installed. Install via `pip install optuna` to run the parameter sweep.")

    trial_records: list[dict[str, object]] = []

    base_config = load_kalman_parameters(KALMAN_CONFIG_PATH)

    def objective(trial: optuna.Trial) -> float:
        process_var = trial.suggest_float("initial_process_variance", 0.01, 0.2, log=True)
        measurement_var = trial.suggest_float("initial_measurement_variance", 0.05, 0.2, log=True)
        sample_target = trial.suggest_int("target_sample_size", 3, 10)
        max_em = trial.suggest_int("max_em_iterations", 4, 16)

        overrides: dict[str, float | int] = {
            "initial_process_variance": process_var,
            "initial_measurement_variance": measurement_var,
            "target_sample_size": sample_target,
            "max_em_iterations": max_em,
        }
        config_mapping = {**base_config.to_dict(), **overrides}
        estimator_config = KalmanFilterConfig.from_mapping(config_mapping)

        def estimator_factory(config: KalmanFilterConfig = estimator_config) -> KalmanUsageEstimator:
            return KalmanUsageEstimator(config=config)

        metrics = _evaluate_real_materials(
            dataframe,
            min_purchases=min_purchases,
            trailing_days=trailing_days,
            usage_config=usage_config,
            run_config=run_config,
            estimator_factory=estimator_factory,
        )

        if metrics.is_empty():
            return float("inf")

        valid_metrics = metrics.drop_nulls(subset=["abs_error_days"])
        if valid_metrics.is_empty():
            return float("inf")

        abs_errors = valid_metrics.get_column("abs_error_days")
        mae = abs_errors.mean()
        median_error = abs_errors.median()
        p90_error = valid_metrics.select(pl.col("abs_error_days").quantile(0.9)).item()

        high_conf = valid_metrics.filter(pl.col("usage_confidence") >= 0.6)
        high_conf_mae = high_conf.get_column("abs_error_days").mean() if not high_conf.is_empty() else None

        record = {
            "trial": trial.number,
            "initial_process_variance": process_var,
            "initial_measurement_variance": measurement_var,
            "target_sample_size": sample_target,
            "max_em_iterations": max_em,
            "runs": valid_metrics.height,
            "mae_days": mae if mae is not None else float("nan"),
            "median_days": median_error if median_error is not None else float("nan"),
            "p90_days": p90_error if p90_error is not None else float("nan"),
            "high_conf_mae_days": high_conf_mae if high_conf_mae is not None else float("nan"),
            "high_conf_runs": high_conf.height if not high_conf.is_empty() else 0,
        }
        trial.set_user_attr("record", record)
        trial_records.append(record)

        stem = f"kalman_prediction_accuracy_grist_trial_{trial.number:03d}"
        _persist_accuracy_report(metrics, stem=stem)
        _persist_accuracy_plot(metrics, stem=stem)

        return mae if mae is not None else float("inf")

    sampler = optuna.samplers.TPESampler(seed=OPTUNA_SEED)
    study = optuna.create_study(direction="minimize", sampler=sampler)
    study.optimize(objective, n_trials=OPTUNA_TRIALS, show_progress_bar=False)

    if not trial_records:
        pytest.skip("Optuna sweep did not produce any valid parameter sets")

    summary_frame = pl.DataFrame(trial_records)
    best_trial = study.best_trial
    best_record = best_trial.user_attrs.get("record")
    if best_record is None:
        best_record = summary_frame.sort("mae_days").row(0)

    best_overrides = {
        "initial_process_variance": best_trial.params["initial_process_variance"],
        "initial_measurement_variance": best_trial.params["initial_measurement_variance"],
        "target_sample_size": int(best_trial.params["target_sample_size"]),
        "max_em_iterations": int(best_trial.params["max_em_iterations"]),
    }
    best_config_mapping = {**base_config.to_dict(), **best_overrides}
    best_config = KalmanFilterConfig.from_mapping(best_config_mapping)

    return summary_frame, best_config, best_record


@pytest.mark.integration
def test_kalman_estimator_on_grist_data() -> None:
    min_purchases = 6
    trailing_days = 365

    dataframe = _load_grist_dataframe()
    if dataframe is None or dataframe.is_empty():
        pytest.skip("No Grist data available for evaluation")

    usage_config = AdaptiveUsageConfig()
    run_config = SupplyRunConfig(minimum_purchase_count=min_purchases)

    summary_frame, best_config, best_record = _run_optuna_parameter_search(
        dataframe,
        min_purchases=min_purchases,
        trailing_days=trailing_days,
        usage_config=usage_config,
        run_config=run_config,
    )

    best_row = best_record or summary_frame.sort(["mae_days", "p90_days"]).row(0)
    if isinstance(best_row, tuple):
        column_names = summary_frame.columns
        best_row = {name: value for name, value in zip(column_names, best_row)}
    print(
        "Best configuration by MAE: trial={trial} (MAE={mae:.2f}d, P90={p90:.2f}d, runs={runs})".format(
            trial=best_row.get("trial", "n/a"),
            mae=best_row.get("mae_days", float("nan")),
            p90=best_row.get("p90_days", float("nan")),
            runs=best_row.get("runs", "n/a"),
        )
    )

    artifact_dir = Path("tests/artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    summary_path = artifact_dir / "kalman_parameter_sweep_summary.csv"
    summary_frame.write_csv(summary_path)

    best_params_json = json.dumps(best_config.to_dict(), indent=2, sort_keys=True)
    KALMAN_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    KALMAN_CONFIG_PATH.write_text(best_params_json)
