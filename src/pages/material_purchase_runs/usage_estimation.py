"""Usage estimation strategies for material purchase analytics."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

_EPS = 1e-9

_PARAM_KEYS = {
    "initial_process_variance",
    "initial_measurement_variance",
    "max_em_iterations",
    "target_sample_size",
    "min_intervals",
    "convergence_tolerance",
    "minimum_process_variance",
    "minimum_measurement_variance",
}

DEFAULT_KALMAN_PARAMS: dict[str, float | int | None] = {
    "initial_process_variance": 0.05,
    "initial_measurement_variance": 0.1,
    "max_em_iterations": 12,
    "target_sample_size": 6,
}

_CONFIG_PATH = Path(__file__).with_name("kalman_parameters.json")


def load_kalman_parameters(config_path: Path | None = None) -> dict[str, float | int | None]:
    """Load Kalman estimator parameters from JSON if available."""

    target_path = config_path or _CONFIG_PATH
    if target_path.exists():
        try:
            data = json.loads(target_path.read_text())
            if isinstance(data, dict):
                filtered: dict[str, float | int | None] = {}
                for key, value in data.items():
                    if key not in _PARAM_KEYS:
                        continue
                    if key == "max_em_iterations" and value is None:
                        filtered[key] = None
                    elif isinstance(value, (int, float)):
                        filtered[key] = value
                if filtered:
                    params = DEFAULT_KALMAN_PARAMS.copy()
                    params.update(filtered)
                    return params
        except Exception:  # noqa: BLE001 - fallback to defaults
            pass
    return DEFAULT_KALMAN_PARAMS.copy()


def create_default_kalman_estimator(config_path: Path | None = None) -> "KalmanUsageEstimator":
    """Instantiate a Kalman usage estimator using configured parameters."""

    params = load_kalman_parameters(config_path)
    return KalmanUsageEstimator(**params)


@dataclass(slots=True)
class UsageInterval:
    """Represents the consumption window between two purchases."""

    start: datetime
    end: datetime
    units: float
    duration_days: float
    usage_per_day: float | None

    @classmethod
    def from_purchases(
        cls,
        start: datetime,
        end: datetime,
        units: float | None,
        *,
        minimum_duration: float,
    ) -> "UsageInterval" | None:
        if units is None:
            return None
        if end <= start:
            duration = minimum_duration
        else:
            duration = max((end - start).total_seconds() / 86400.0, minimum_duration)
        if duration <= 0:
            return None
        try:
            units_value = float(units)
        except (TypeError, ValueError):
            return None
        if units_value < 0:
            return None
        usage = units_value / duration if units_value > 0 else None
        return cls(start=start, end=end, units=units_value, duration_days=duration, usage_per_day=usage)


@dataclass(slots=True)
class UsageEstimate:
    """Result of a usage estimation strategy."""

    usage_per_day: float | None
    confidence: float
    samples: int
    process_variance: float | None
    measurement_variance: float | None
    bias_days: float | None = None


class MaterialUsageEstimator:
    """Interface for material usage estimators."""

    def estimate(self, intervals: Sequence[UsageInterval]) -> UsageEstimate:  # noqa: D401
        """Estimate daily usage from purchase intervals."""
        raise NotImplementedError


class KalmanUsageEstimator(MaterialUsageEstimator):
    """Kalman filter with EM variance updates for usage estimation."""

    def __init__(
        self,
        *,
        min_intervals: int = 2,
        max_em_iterations: int = 12,
        convergence_tolerance: float = 1e-4,
        initial_process_variance: float = 0.05,
        initial_measurement_variance: float = 0.1,
        minimum_process_variance: float = 1e-5,
        minimum_measurement_variance: float = 1e-4,
        target_sample_size: int = 6,
    ) -> None:
        self._min_intervals = min_intervals
        self._max_em_iterations = max_em_iterations
        self._tolerance = convergence_tolerance
        self._initial_process_variance = max(initial_process_variance, minimum_process_variance)
        self._initial_measurement_variance = max(initial_measurement_variance, minimum_measurement_variance)
        self._minimum_process_variance = minimum_process_variance
        self._minimum_measurement_variance = minimum_measurement_variance
        self._target_sample_size = max(1, target_sample_size)

    def estimate(self, intervals: Sequence[UsageInterval]) -> UsageEstimate:
        valid_intervals = [interval for interval in intervals if interval.usage_per_day is not None]
        sample_count = len(valid_intervals)

        if sample_count == 0:
            fallback = intervals[-1].usage_per_day if intervals else None
            return UsageEstimate(
                usage_per_day=fallback,
                confidence=0.0,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
                bias_days=None,
            )

        if sample_count == 1:
            usage = valid_intervals[0].usage_per_day
            confidence = 0.15 if usage is not None else 0.0
            return UsageEstimate(
                usage_per_day=usage,
                confidence=confidence,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
                bias_days=None,
            )

        if sample_count < self._min_intervals:
            usage = valid_intervals[-1].usage_per_day
            confidence = 0.2 if usage is not None else 0.0
            return UsageEstimate(
                usage_per_day=usage,
                confidence=confidence,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
            )

        observations = [interval.usage_per_day or 0.0 for interval in valid_intervals]
        durations = [max(interval.duration_days, 1.0) for interval in valid_intervals]

        process_var = self._initial_process_variance
        measurement_var = self._initial_measurement_variance

        previous_log_likelihood = None
        kalman_result = None

        for _ in range(self._max_em_iterations):
            kalman_result = self._run_kalman_smoother(observations, durations, process_var, measurement_var)
            if kalman_result is None:
                break

            process_var_new, measurement_var_new, log_likelihood = self._em_update(
                observations, durations, kalman_result, process_var, measurement_var
            )

            if measurement_var_new is not None:
                measurement_var = max(self._minimum_measurement_variance, measurement_var_new)
            if process_var_new is not None:
                process_var = max(self._minimum_process_variance, process_var_new)

            if previous_log_likelihood is not None and log_likelihood is not None:
                if abs(log_likelihood - previous_log_likelihood) < self._tolerance:
                    break
            previous_log_likelihood = log_likelihood

        if kalman_result is None:
            usage = observations[-1]
            return UsageEstimate(
                usage_per_day=usage,
                confidence=0.2,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
                bias_days=None,
            )

        usage = kalman_result.smoothed_means[-1]
        variance = max(kalman_result.smoothed_variances[-1], 0.0)
        usage = usage if usage > 0 else None

        if usage is None:
            return UsageEstimate(
                usage_per_day=None,
                confidence=0.0,
                samples=sample_count,
                process_variance=process_var,
                measurement_variance=measurement_var,
                bias_days=None,
            )

        confidence = self._derive_confidence(usage, variance, measurement_var, sample_count)

        return UsageEstimate(
            usage_per_day=usage,
            confidence=confidence,
            samples=sample_count,
            process_variance=process_var,
            measurement_variance=measurement_var,
            bias_days=None,
        )

    @dataclass(slots=True)
    class _KalmanResult:
        filtered_means: list[float]
        filtered_variances: list[float]
        predicted_means: list[float]
        predicted_variances: list[float]
        smoothed_means: list[float]
        smoothed_variances: list[float]
        cross_covariances: list[float]
        log_likelihood: float

    def _run_kalman_smoother(
        self,
        observations: Sequence[float],
        durations: Sequence[float],
        process_var: float,
        measurement_var: float,
    ) -> "KalmanUsageEstimator._KalmanResult" | None:
        n = len(observations)
        if n == 0:
            return None

        filtered_means: list[float] = [0.0] * n
        filtered_variances: list[float] = [0.0] * n
        predicted_means: list[float] = [0.0] * n
        predicted_variances: list[float] = [0.0] * n
        log_likelihood = 0.0

        prior_mean = observations[0]
        prior_variance = max(measurement_var, self._minimum_process_variance)

        for index, observation in enumerate(observations):
            if index == 0:
                pred_mean = prior_mean
                pred_variance = prior_variance
            else:
                q = process_var * max(durations[index], 1.0)
                pred_mean = filtered_means[index - 1]
                pred_variance = filtered_variances[index - 1] + q

            predicted_means[index] = pred_mean
            predicted_variances[index] = pred_variance

            innovation_variance = pred_variance + measurement_var
            if innovation_variance <= _EPS:
                return None
            kalman_gain = pred_variance / innovation_variance
            resid = observation - pred_mean
            filtered_mean = pred_mean + kalman_gain * resid
            filtered_variance = (1 - kalman_gain) * pred_variance

            filtered_means[index] = filtered_mean
            filtered_variances[index] = max(filtered_variance, _EPS)

            log_likelihood += -0.5 * (math.log(2 * math.pi * innovation_variance) + (resid**2) / innovation_variance)

        smoothed_means = filtered_means[:]
        smoothed_variances = filtered_variances[:]
        cross_covariances: list[float] = [0.0] * (n - 1 if n > 1 else 0)

        for index in reversed(range(n - 1)):
            pred_variance_next = predicted_variances[index + 1]
            if pred_variance_next <= _EPS:
                continue
            smoothing_gain = filtered_variances[index] / pred_variance_next
            diff = smoothed_means[index + 1] - predicted_means[index + 1]
            smoothed_means[index] = filtered_means[index] + smoothing_gain * diff
            smoothed_variances[index] = filtered_variances[index] + (
                smoothing_gain**2 * (smoothed_variances[index + 1] - pred_variance_next)
            )
            smoothed_variances[index] = max(smoothed_variances[index], _EPS)
            cross_covariances[index] = smoothed_variances[index + 1] * smoothing_gain

        return KalmanUsageEstimator._KalmanResult(
            filtered_means=filtered_means,
            filtered_variances=filtered_variances,
            predicted_means=predicted_means,
            predicted_variances=predicted_variances,
            smoothed_means=smoothed_means,
            smoothed_variances=smoothed_variances,
            cross_covariances=cross_covariances,
            log_likelihood=log_likelihood,
        )

    def _em_update(
        self,
        observations: Sequence[float],
        durations: Sequence[float],
        result: "KalmanUsageEstimator._KalmanResult",
        process_var: float,
        measurement_var: float,
    ) -> tuple[float | None, float | None, float | None]:
        n = len(observations)
        if n == 0:
            return (None, None, None)

        measurement_terms = [
            (observations[i] - result.smoothed_means[i]) ** 2 + result.smoothed_variances[i] for i in range(n)
        ]
        measurement_var_new = sum(measurement_terms) / n

        process_terms: list[float] = []
        for index in range(1, n):
            delta = max(durations[index], 1.0)
            diff = result.smoothed_means[index] - result.smoothed_means[index - 1]
            var_sum = (
                result.smoothed_variances[index]
                + result.smoothed_variances[index - 1]
                - 2 * result.cross_covariances[index - 1]
            )
            process_terms.append((diff**2 + var_sum) / delta)
        process_var_new = sum(process_terms) / (len(process_terms) or 1)

        return (process_var_new, measurement_var_new, result.log_likelihood)

    def _derive_confidence(
        self,
        usage: float,
        variance: float,
        measurement_var: float,
        sample_count: int,
    ) -> float:
        posterior_std = math.sqrt(max(variance, _EPS))
        measurement_std = math.sqrt(max(measurement_var, _EPS))
        signal = abs(usage)
        denom = signal + posterior_std + measurement_std
        base_conf = signal / denom if denom > 0 else 0.0
        sample_factor = min(1.0, sample_count / self._target_sample_size)
        confidence = max(0.0, min(1.0, 0.6 * base_conf + 0.4 * sample_factor))
        return round(confidence, 3)
