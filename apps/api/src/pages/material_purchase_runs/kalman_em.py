"""Fallback EM routines for the local-level Kalman model."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

_EPS = 1e-9


@dataclass(slots=True)
class _SmootherResult:
    filtered_means: np.ndarray
    filtered_variances: np.ndarray
    predicted_means: np.ndarray
    predicted_variances: np.ndarray
    smoothed_means: np.ndarray
    smoothed_variances: np.ndarray
    cross_covariances: np.ndarray
    log_likelihood: float


def run_local_level_em(
    observations: np.ndarray,
    durations: np.ndarray,
    initial_process: float,
    initial_measurement: float,
    *,
    min_process_variance: float,
    min_measurement_variance: float,
    max_iterations: int,
    tolerance: float,
) -> tuple[float, float]:
    """Estimate process and measurement variances via EM for a local-level model."""

    obs = np.asarray(observations, dtype=float)
    dur = np.asarray(durations, dtype=float)
    if obs.size == 0:
        return (initial_process, initial_measurement)

    process_var = max(initial_process, min_process_variance)
    measurement_var = max(initial_measurement, min_measurement_variance)
    previous_log_likelihood: float | None = None

    iterations = max(1, max_iterations)
    for _ in range(iterations):
        result = _run_kalman_smoother(obs, dur, process_var, measurement_var, min_process_variance)
        if result is None:
            break

        process_new, measurement_new, log_likelihood = _em_update(
            obs, dur, result, min_process_variance, min_measurement_variance
        )

        if measurement_new is not None:
            measurement_var = max(min_measurement_variance, measurement_new)
        if process_new is not None:
            process_var = max(min_process_variance, process_new)

        if previous_log_likelihood is not None and log_likelihood is not None:
            if abs(log_likelihood - previous_log_likelihood) < tolerance:
                break
        previous_log_likelihood = log_likelihood

    return (process_var, measurement_var)


def smooth_local_level(
    observations: np.ndarray,
    process_variances: np.ndarray,
    measurement_variances: np.ndarray,
    *,
    min_process_variance: float,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Run a Kalman smoother for a time-varying local-level model."""

    obs = np.asarray(observations, dtype=float)
    proc = np.asarray(process_variances, dtype=float)
    meas = np.asarray(measurement_variances, dtype=float)

    n = obs.size
    if n == 0 or proc.size != n or meas.size != n:
        return None

    filtered_means = np.zeros(n, dtype=float)
    filtered_variances = np.zeros(n, dtype=float)
    predicted_means = np.zeros(n, dtype=float)
    predicted_variances = np.zeros(n, dtype=float)

    prior_mean = float(obs[0])
    prior_variance = max(float(meas[0]), min_process_variance)

    for index in range(n):
        observation = float(obs[index])
        if index == 0:
            pred_mean = prior_mean
            pred_variance = prior_variance
        else:
            q = float(proc[index])
            pred_mean = filtered_means[index - 1]
            pred_variance = filtered_variances[index - 1] + q

        predicted_means[index] = pred_mean
        predicted_variances[index] = pred_variance

        innovation_variance = pred_variance + float(meas[index])
        if innovation_variance <= _EPS:
            return None

        kalman_gain = pred_variance / innovation_variance
        resid = observation - pred_mean
        filtered_mean = pred_mean + kalman_gain * resid
        filtered_variance = (1 - kalman_gain) * pred_variance

        filtered_means[index] = filtered_mean
        filtered_variances[index] = max(filtered_variance, _EPS)

    smoothed_means = filtered_means.copy()
    smoothed_variances = filtered_variances.copy()

    for index in range(n - 2, -1, -1):
        pred_var_next = predicted_variances[index + 1]
        if pred_var_next <= _EPS:
            continue
        smoothing_gain = filtered_variances[index] / pred_var_next
        diff = smoothed_means[index + 1] - predicted_means[index + 1]
        smoothed_means[index] = filtered_means[index] + smoothing_gain * diff
        smoothed_variances[index] = filtered_variances[index] + (
            smoothing_gain**2 * (smoothed_variances[index + 1] - pred_var_next)
        )
        smoothed_variances[index] = max(smoothed_variances[index], _EPS)

    return (smoothed_means, smoothed_variances)


def _run_kalman_smoother(
    observations: np.ndarray,
    durations: np.ndarray,
    process_var: float,
    measurement_var: float,
    min_process_variance: float,
) -> _SmootherResult | None:
    n = observations.size
    if n == 0:
        return None

    filtered_means = np.zeros(n, dtype=float)
    filtered_variances = np.zeros(n, dtype=float)
    predicted_means = np.zeros(n, dtype=float)
    predicted_variances = np.zeros(n, dtype=float)
    log_likelihood = 0.0

    prior_mean = float(observations[0])
    prior_variance = max(measurement_var, min_process_variance)

    for index in range(n):
        observation = observations[index]
        if index == 0:
            pred_mean = prior_mean
            pred_variance = prior_variance
        else:
            q = process_var * max(float(durations[index]), 1.0)
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

    smoothed_means = filtered_means.copy()
    smoothed_variances = filtered_variances.copy()
    cross_covariances = np.zeros(max(0, n - 1), dtype=float)

    for index in range(n - 2, -1, -1):
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

    return _SmootherResult(
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
    observations: np.ndarray,
    durations: np.ndarray,
    result: _SmootherResult,
    min_process_variance: float,
    min_measurement_variance: float,
) -> tuple[float | None, float | None, float | None]:
    n = observations.size
    if n == 0:
        return (None, None, None)

    measurement_terms = (observations - result.smoothed_means) ** 2 + result.smoothed_variances
    measurement_var_new = float(np.mean(measurement_terms))
    measurement_var_new = max(measurement_var_new, min_measurement_variance)

    if n == 1:
        return (None, measurement_var_new, result.log_likelihood)

    diffs = result.smoothed_means[1:] - result.smoothed_means[:-1]
    var_sum = result.smoothed_variances[1:] + result.smoothed_variances[:-1] - 2 * result.cross_covariances
    safe_durations = np.maximum(durations[1:], 1.0)
    process_terms = (diffs**2 + var_sum) / safe_durations
    process_var_new = float(np.mean(process_terms))
    process_var_new = max(process_var_new, min_process_variance)

    return (process_var_new, measurement_var_new, result.log_likelihood)
