"""Usage estimation strategies for material purchase analytics."""

from __future__ import annotations

import inspect
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Sequence

import numpy as np
from numpy.linalg import LinAlgError
from statsmodels.tsa.statespace.kalman_filter import (
    KalmanFilter as StatsmodelsKalmanFilter,
)

from .kalman_em import run_local_level_em, smooth_local_level

_EPS = 1e-9

_CONFIG_PATH = Path(__file__).with_name("kalman_parameters.json")
_REQUIRED_CONFIG_KEYS = {
    "initial_process_variance",
    "initial_measurement_variance",
    "max_em_iterations",
    "target_sample_size",
    "min_intervals",
    "convergence_tolerance",
    "minimum_process_variance",
    "minimum_measurement_variance",
    "measurement_volume_floor",
    "measurement_volume_exponent",
    "process_volume_floor",
    "process_volume_alpha",
    "process_scale_ceiling",
    "process_gap_alpha",
    "process_gap_reference",
    "confidence_volume_weight",
    "confidence_volume_floor",
    "confidence_volume_sensitivity",
}


@dataclass(slots=True)
class KalmanFilterConfig:
    """Configuration payload for the statsmodels-based Kalman estimator."""

    min_intervals: int
    max_em_iterations: int
    convergence_tolerance: float
    initial_process_variance: float
    initial_measurement_variance: float
    minimum_process_variance: float
    minimum_measurement_variance: float
    target_sample_size: int
    measurement_volume_floor: float
    measurement_volume_exponent: float
    process_volume_floor: float
    process_volume_alpha: float
    process_scale_ceiling: float
    process_gap_alpha: float
    process_gap_reference: float
    confidence_volume_weight: float
    confidence_volume_floor: float
    confidence_volume_sensitivity: float

    @classmethod
    def from_mapping(cls, data: dict[str, object]) -> "KalmanFilterConfig":
        missing = _REQUIRED_CONFIG_KEYS.difference(data.keys())
        if missing:
            joined = ", ".join(sorted(missing))
            raise KeyError(f"Missing Kalman configuration keys: {joined}")

        def _require_float(name: str) -> float:
            value = data.get(name)
            if isinstance(value, bool):  # bool is subclass of int; reject explicitly
                raise TypeError(f"Configuration value '{name}' must be numeric, received bool")
            if not isinstance(value, (int, float)):
                raise TypeError(f"Configuration value '{name}' must be numeric, received {type(value).__name__}")
            return float(value)

        def _require_int(name: str) -> int:
            numeric = data.get(name)
            if isinstance(numeric, bool):
                raise TypeError(f"Configuration value '{name}' must be integer, received bool")
            if isinstance(numeric, int):
                return numeric
            if isinstance(numeric, float) and numeric.is_integer():
                return int(numeric)
            raise TypeError(f"Configuration value '{name}' must be integer, received {type(numeric).__name__}")

        minimum_process_variance = max(_require_float("minimum_process_variance"), _EPS)
        minimum_measurement_variance = max(_require_float("minimum_measurement_variance"), _EPS)

        process_scale_ceiling = max(_require_float("process_scale_ceiling"), 1.0)
        measurement_volume_floor = max(_require_float("measurement_volume_floor"), _EPS)
        measurement_volume_exponent = max(_require_float("measurement_volume_exponent"), 0.0)
        process_volume_floor = max(_require_float("process_volume_floor"), _EPS)
        process_volume_alpha = max(_require_float("process_volume_alpha"), 0.0)
        process_gap_alpha = max(_require_float("process_gap_alpha"), 0.0)
        process_gap_reference = max(_require_float("process_gap_reference"), _EPS)
        confidence_volume_weight = max(0.0, min(1.0, _require_float("confidence_volume_weight")))
        confidence_volume_floor = max(_require_float("confidence_volume_floor"), _EPS)
        confidence_volume_sensitivity = max(_require_float("confidence_volume_sensitivity"), 0.0)

        return cls(
            min_intervals=max(1, _require_int("min_intervals")),
            max_em_iterations=max(0, _require_int("max_em_iterations")),
            convergence_tolerance=max(_EPS, _require_float("convergence_tolerance")),
            initial_process_variance=max(_require_float("initial_process_variance"), minimum_process_variance),
            initial_measurement_variance=max(
                _require_float("initial_measurement_variance"), minimum_measurement_variance
            ),
            minimum_process_variance=minimum_process_variance,
            minimum_measurement_variance=minimum_measurement_variance,
            target_sample_size=max(1, _require_int("target_sample_size")),
            measurement_volume_floor=measurement_volume_floor,
            measurement_volume_exponent=measurement_volume_exponent,
            process_volume_floor=process_volume_floor,
            process_volume_alpha=process_volume_alpha,
            process_scale_ceiling=process_scale_ceiling,
            process_gap_alpha=process_gap_alpha,
            process_gap_reference=process_gap_reference,
            confidence_volume_weight=confidence_volume_weight,
            confidence_volume_floor=confidence_volume_floor,
            confidence_volume_sensitivity=confidence_volume_sensitivity,
        )

    def to_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable dictionary of the configuration values."""

        return asdict(self)


def load_kalman_parameters(config_path: Path | None = None) -> KalmanFilterConfig:
    """Load the Kalman configuration from JSON."""

    target_path = config_path or _CONFIG_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Kalman configuration file not found at {target_path}")

    try:
        raw = json.loads(target_path.read_text())
    except json.JSONDecodeError as error:
        raise ValueError(f"Kalman configuration at {target_path} is not valid JSON") from error

    if not isinstance(raw, dict):
        raise TypeError(f"Kalman configuration at {target_path} must be a JSON object")

    return KalmanFilterConfig.from_mapping(raw)


def create_default_kalman_estimator(config_path: Path | None = None) -> "KalmanUsageEstimator":
    """Instantiate a Kalman usage estimator using configured parameters."""

    config = load_kalman_parameters(config_path)
    return KalmanUsageEstimator(config=config)


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
    usage_variance: float | None
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
    """Material usage estimator backed by statsmodels' KalmanFilter."""

    def __init__(self, *, config: KalmanFilterConfig) -> None:
        self._config = config

    def estimate(self, intervals: Sequence[UsageInterval]) -> UsageEstimate:
        valid_intervals = [interval for interval in intervals if interval.usage_per_day is not None]
        sample_count = len(valid_intervals)

        if sample_count == 0:
            fallback = intervals[-1].usage_per_day if intervals else None
            return UsageEstimate(
                usage_per_day=fallback,
                usage_variance=None,
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
                usage_variance=None,
                confidence=confidence,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
                bias_days=None,
            )

        if sample_count < self._config.min_intervals:
            usage = valid_intervals[-1].usage_per_day
            confidence = 0.2 if usage is not None else 0.0
            return UsageEstimate(
                usage_per_day=usage,
                usage_variance=None,
                confidence=confidence,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
            )

        observations = np.array([interval.usage_per_day or 0.0 for interval in valid_intervals], dtype=float)
        units = np.array([interval.units for interval in valid_intervals], dtype=float)
        durations = np.array([interval.duration_days for interval in valid_intervals], dtype=float)

        result = self._smooth_usage(observations, units, durations)
        if result is None:
            usage = float(observations[-1])
            return UsageEstimate(
                usage_per_day=usage,
                usage_variance=None,
                confidence=0.2,
                samples=sample_count,
                process_variance=None,
                measurement_variance=None,
                bias_days=None,
            )

        (
            usage,
            variance,
            base_process_variance,
            base_measurement_variance,
            final_measurement_variance,
        ) = result
        usage = usage if usage > 0 else None

        if usage is None:
            return UsageEstimate(
                usage_per_day=None,
                usage_variance=None,
                confidence=0.0,
                samples=sample_count,
                process_variance=base_process_variance,
                measurement_variance=base_measurement_variance,
                bias_days=None,
            )

        confidence = self._derive_confidence(
            usage,
            variance,
            final_measurement_variance,
            sample_count,
            units,
        )

        return UsageEstimate(
            usage_per_day=usage,
            usage_variance=max(variance, _EPS),
            confidence=confidence,
            samples=sample_count,
            process_variance=base_process_variance,
            measurement_variance=base_measurement_variance,
            bias_days=None,
        )

    def _smooth_usage(
        self,
        observations: np.ndarray,
        units: np.ndarray,
        durations: np.ndarray,
    ) -> tuple[float, float, float, float, float] | None:
        if observations.size == 0:
            return None

        if observations.size == 0 or units.size != observations.size or durations.size != observations.size:
            return None

        config = self._config
        kf = StatsmodelsKalmanFilter(
            k_endog=1,
            k_states=1,
            nobs=int(observations.size),
            time_varying_obs_cov=True,
            time_varying_state_cov=True,
        )
        kf.bind(observations)

        # Set up a simple local-level model.
        kf.design[:] = 1.0
        kf.transition[:] = 1.0
        kf.selection[:] = 1.0
        kf.state_cov[:] = config.initial_process_variance
        kf.obs_cov[:] = config.initial_measurement_variance

        initial_covariance = max(config.initial_measurement_variance, config.minimum_process_variance)
        initial_state = np.array([np.squeeze(observations[0])], dtype=float)
        kf.initialize_known(initial_state, np.array([[initial_covariance]], dtype=float))

        base_process_variance = config.initial_process_variance
        base_measurement_variance = config.initial_measurement_variance

        if config.max_em_iterations > 0:
            if hasattr(kf, "em"):
                try:
                    em_kwargs = self._build_em_kwargs(kf)
                    kf.em(observations, **em_kwargs)
                    base_process_variance = float(np.squeeze(kf.state_cov))
                    base_measurement_variance = float(np.squeeze(kf.obs_cov))
                except (LinAlgError, ValueError, RuntimeError):
                    return None
            else:
                base_process_variance, base_measurement_variance = run_local_level_em(
                    observations,
                    durations,
                    base_process_variance,
                    base_measurement_variance,
                    min_process_variance=self._config.minimum_process_variance,
                    min_measurement_variance=self._config.minimum_measurement_variance,
                    max_iterations=self._config.max_em_iterations,
                    tolerance=self._config.convergence_tolerance,
                )

        kf.state_cov[:] = base_process_variance
        kf.obs_cov[:] = base_measurement_variance

        measurement_multipliers = self._measurement_multipliers(units)
        process_multipliers = self._process_multipliers(units, durations)

        measurement_cov = (base_measurement_variance * measurement_multipliers).reshape(1, 1, -1)
        process_cov = (base_process_variance * process_multipliers).reshape(1, 1, -1)

        kf.obs_cov = measurement_cov
        kf.state_cov = process_cov

        measurement_vars = measurement_cov[0, 0, :]
        process_vars = process_cov[0, 0, :]

        if hasattr(kf, "smooth"):
            try:
                smoother = kf.smooth(observations)
                smoothed_state = float(smoother.smoothed_state[0, -1])
                smoothed_variance = float(smoother.smoothed_state_cov[0, 0, -1])
            except (LinAlgError, ValueError, RuntimeError):
                return None
        else:
            smoother_result = smooth_local_level(
                observations,
                process_vars,
                measurement_vars,
                min_process_variance=config.minimum_process_variance,
            )
            if smoother_result is None:
                return None
            smoothed_means, smoothed_variances = smoother_result
            smoothed_state = float(smoothed_means[-1])
            smoothed_variance = float(smoothed_variances[-1])

        process_var = max(float(base_process_variance), config.minimum_process_variance)
        measurement_var = max(float(base_measurement_variance), config.minimum_measurement_variance)

        final_measurement_variance = max(float(measurement_vars[-1]), config.minimum_measurement_variance)

        return (
            smoothed_state,
            max(smoothed_variance, _EPS),
            process_var,
            measurement_var,
            final_measurement_variance,
        )

    def _build_em_kwargs(self, filter_instance: StatsmodelsKalmanFilter) -> dict[str, object]:
        """Construct EM keyword arguments compatible with the runtime statsmodels version."""

        if not hasattr(filter_instance, "em"):
            raise RuntimeError(
                "statsmodels.KalmanFilter.em is unavailable; upgrade statsmodels to support EM variance fitting."
            )

        parameters = inspect.signature(filter_instance.em).parameters
        kwargs: dict[str, object] = {}

        if "em_vars" in parameters:
            kwargs["em_vars"] = ["state_cov", "obs_cov"]

        iteration_keys = ("maxiter", "em_iter", "n_iter", "niter")
        for key in iteration_keys:
            if key in parameters:
                kwargs[key] = self._config.max_em_iterations
                break

        tolerance_keys = ("tol", "em_tol")
        for key in tolerance_keys:
            if key in parameters:
                kwargs[key] = self._config.convergence_tolerance
                break

        return kwargs

    def _measurement_multipliers(self, units: np.ndarray) -> np.ndarray:
        floor = self._config.measurement_volume_floor
        exponent = self._config.measurement_volume_exponent
        if exponent <= 0.0:
            return np.ones_like(units, dtype=float)

        safe_units = np.where(np.isfinite(units), units, floor)
        safe_units = np.maximum(safe_units, floor)
        positive_units = safe_units[safe_units > 0]
        if positive_units.size > 0:
            dynamic_floor = float(np.median(positive_units))
            floor = max(floor, dynamic_floor)

        safe_units = np.maximum(safe_units, floor)
        normalized = safe_units / floor
        multipliers = np.power(normalized, -exponent, dtype=float)
        return np.clip(multipliers, 0.1, 10.0)

    def _process_multipliers(self, units: np.ndarray, durations: np.ndarray) -> np.ndarray:
        alpha = self._config.process_volume_alpha
        gap_alpha = self._config.process_gap_alpha
        if units.size == 0:
            return np.ones_like(units, dtype=float)

        safe_units = np.where(np.isfinite(units), units, self._config.process_volume_floor)
        safe_units = np.maximum(safe_units, self._config.process_volume_floor)
        multipliers = np.ones_like(safe_units, dtype=float)

        if alpha > 0.0 and safe_units.size > 1:
            prev = safe_units[:-1]
            delta = np.abs(safe_units[1:] - prev)
            denom = np.maximum(prev, self._config.process_volume_floor)
            relative_change = delta / denom
            ceiling = max(self._config.process_scale_ceiling, 1.0)
            multipliers[1:] = np.clip(1.0 + alpha * relative_change, 1.0, ceiling)

        if gap_alpha > 0.0 and durations.size == multipliers.size:
            reference = max(self._config.process_gap_reference, _EPS)
            safe_durations = np.where(np.isfinite(durations), durations, reference)
            safe_durations = np.maximum(safe_durations, _EPS)
            ratios = safe_durations / reference
            gap_adjustment = 1.0 + gap_alpha * np.maximum(0.0, ratios - 1.0)
            ceiling = max(self._config.process_scale_ceiling, 1.0)
            multipliers = np.clip(multipliers * gap_adjustment, 1.0, ceiling)

        return multipliers

    def _volume_consistency(self, units: np.ndarray) -> float:
        if units.size <= 1:
            return 0.5

        safe_units = np.where(np.isfinite(units), units, 0.0)
        mean_units = float(np.mean(safe_units))
        if mean_units <= 0.0:
            return 0.5

        std_units = float(np.std(safe_units))
        cv = std_units / max(mean_units, self._config.confidence_volume_floor)
        sensitivity = self._config.confidence_volume_sensitivity
        factor = 1.0 / (1.0 + sensitivity * cv)
        return max(0.0, min(1.0, factor))

    def _derive_confidence(
        self,
        usage: float,
        variance: float,
        measurement_var: float,
        sample_count: int,
        units: np.ndarray,
    ) -> float:
        posterior_std = math.sqrt(max(variance, _EPS))
        measurement_std = math.sqrt(max(measurement_var, _EPS))
        signal = abs(usage)
        denom = signal + posterior_std + measurement_std
        base_conf = signal / denom if denom > 0 else 0.0
        sample_factor = min(1.0, sample_count / self._config.target_sample_size)
        combined = 0.6 * base_conf + 0.4 * sample_factor
        volume_weight = self._config.confidence_volume_weight
        volume_factor = self._volume_consistency(units)
        confidence = (1.0 - volume_weight) * combined + volume_weight * volume_factor
        confidence = max(0.0, min(1.0, confidence))
        return round(confidence, 3)
