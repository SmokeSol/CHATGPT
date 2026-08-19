from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np


class ForecastV3Error(ValueError):
    """Fail-closed validation error for the v3 forecast centre/calibration layer."""


@dataclass(frozen=True)
class CenterDiagnostics:
    lambda_: float
    iterations: int
    converged: bool
    max_national_abs_error: float
    max_row_sum_abs_error: float
    floor: float
    correction_required: bool
    pre_rake_max_national_abs_error: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "lambda": self.lambda_,
            "iterations": self.iterations,
            "converged": self.converged,
            "max_national_abs_error": self.max_national_abs_error,
            "max_row_sum_abs_error": self.max_row_sum_abs_error,
            "floor": self.floor,
            "correction_required": self.correction_required,
            "pre_rake_max_national_abs_error": self.pre_rake_max_national_abs_error,
        }


def _as_2d(name: str, values: np.ndarray | list[list[float]]) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 2 or array.shape[0] < 1 or array.shape[1] < 2:
        raise ForecastV3Error(f"{name} must be a non-empty 2D matrix with >=2 parties")
    if not np.all(np.isfinite(array)):
        raise ForecastV3Error(f"{name} contains non-finite values")
    return array


def normalize_vector(values: np.ndarray | list[float], *, floor: float = 0.0) -> np.ndarray:
    array = np.asarray(values, dtype=float)
    if array.ndim != 1 or array.size < 2:
        raise ForecastV3Error("share vector must be one-dimensional with >=2 parties")
    if not np.all(np.isfinite(array)):
        raise ForecastV3Error("share vector contains non-finite values")
    if np.any(array < 0):
        raise ForecastV3Error("share vector contains negative values")
    if floor < 0:
        raise ForecastV3Error("floor must be >=0")
    if floor:
        array = np.maximum(array, floor)
    total = float(array.sum())
    if total <= 0:
        raise ForecastV3Error("share vector has zero mass")
    return array / total


def normalize_rows(values: np.ndarray | list[list[float]], *, floor: float = 0.0) -> np.ndarray:
    array = _as_2d("share matrix", values).copy()
    if np.any(array < 0):
        raise ForecastV3Error("share matrix contains negative values")
    if floor < 0:
        raise ForecastV3Error("floor must be >=0")
    if floor:
        array = np.maximum(array, floor)
    totals = array.sum(axis=1, keepdims=True)
    if np.any(totals <= 0):
        raise ForecastV3Error("share matrix contains zero-mass rows")
    return array / totals


def normalize_weights(weights: np.ndarray | list[float], n_rows: int) -> np.ndarray:
    array = np.asarray(weights, dtype=float)
    if array.ndim != 1 or len(array) != n_rows:
        raise ForecastV3Error("weights must be one-dimensional and match territory count")
    if not np.all(np.isfinite(array)) or np.any(array <= 0):
        raise ForecastV3Error("weights must be finite and strictly positive")
    return array / array.sum()


def weighted_national(shares: np.ndarray, weights: np.ndarray | list[float]) -> np.ndarray:
    matrix = normalize_rows(shares)
    w = normalize_weights(weights, len(matrix))
    result = (matrix * w[:, None]).sum(axis=0)
    return normalize_vector(result)


def build_territorial_centers(
    prior_territorial: np.ndarray | list[list[float]],
    weights: np.ndarray | list[float],
    national_target: np.ndarray | list[float],
    *,
    lambda_: float = 0.5,
    floor: float = 1e-10,
    tolerance: float = 1e-10,
    max_iter: int = 10_000,
) -> tuple[np.ndarray, CenterDiagnostics]:
    """Build positive territorial centres around an exogenous target national share.

    The historically validated model is::

        national_origin + lambda * (territory_origin - national_origin)

    v3 preserves that exact identity when the target national share equals the
    origin national share, then substitutes the current national target::

        national_target + lambda * (territory_origin - national_origin)

    A large national swing can make the additive expression leave the simplex.
    The matrix is therefore floored and iteratively raked so that every row sums
    to one and its weighted aggregate equals ``national_target``. Raking restores
    constraints; it is not a fitted parameter.
    """
    prior = normalize_rows(prior_territorial)
    w = normalize_weights(weights, len(prior))
    target = normalize_vector(national_target)
    if prior.shape[1] != len(target):
        raise ForecastV3Error("national target party dimension does not match territories")
    if not (0.0 <= float(lambda_) <= 1.0):
        raise ForecastV3Error("lambda must lie in [0,1]")
    if floor <= 0:
        raise ForecastV3Error("floor must be strictly positive")
    if tolerance <= 0 or max_iter < 1:
        raise ForecastV3Error("invalid convergence controls")
    if np.any(target <= floor):
        raise ForecastV3Error("national target must be strictly above the numerical floor")

    origin_national = weighted_national(prior, w)
    raw = target[None, :] + float(lambda_) * (prior - origin_national[None, :])
    correction_required = bool(np.any(raw <= floor))
    center = normalize_rows(np.maximum(raw, floor), floor=floor)

    pre_error = float(np.max(np.abs(weighted_national(center, w) - target)))
    converged = False
    iterations = 0

    for iterations in range(1, max_iter + 1):
        aggregate = weighted_national(center, w)
        error = float(np.max(np.abs(aggregate - target)))
        if error <= tolerance:
            converged = True
            break
        factors = target / np.maximum(aggregate, floor)
        center = normalize_rows(np.maximum(center * factors[None, :], floor), floor=floor)

    aggregate = weighted_national(center, w)
    final_error = float(np.max(np.abs(aggregate - target)))
    row_error = float(np.max(np.abs(center.sum(axis=1) - 1.0)))
    if not converged and final_error <= tolerance:
        converged = True
    if not converged:
        raise ForecastV3Error(
            f"territorial raking did not converge: max national error={final_error:.3e}"
        )

    diagnostics = CenterDiagnostics(
        lambda_=float(lambda_),
        iterations=iterations,
        converged=converged,
        max_national_abs_error=final_error,
        max_row_sum_abs_error=row_error,
        floor=float(floor),
        correction_required=correction_required,
        pre_rake_max_national_abs_error=pre_error,
    )
    return center, diagnostics


def clr_rows(values: np.ndarray | list[list[float]], *, floor: float = 1e-10) -> np.ndarray:
    matrix = normalize_rows(values, floor=floor)
    logs = np.log(matrix)
    return logs - logs.mean(axis=1, keepdims=True)


def conditional_territorial_residuals(
    actual: np.ndarray | list[list[float]],
    center: np.ndarray | list[list[float]],
    *,
    floor: float = 1e-10,
) -> np.ndarray:
    actual_matrix = normalize_rows(actual, floor=floor)
    center_matrix = normalize_rows(center, floor=floor)
    if actual_matrix.shape != center_matrix.shape:
        raise ForecastV3Error("actual and center matrices must have identical shapes")
    residuals = clr_rows(actual_matrix, floor=floor) - clr_rows(center_matrix, floor=floor)
    residuals -= residuals.mean(axis=1, keepdims=True)
    return residuals


def residual_summary(
    actual: np.ndarray | list[list[float]],
    center: np.ndarray | list[list[float]],
    *,
    floor: float = 1e-10,
) -> dict[str, Any]:
    actual_matrix = normalize_rows(actual, floor=floor)
    center_matrix = normalize_rows(center, floor=floor)
    residual_clr = conditional_territorial_residuals(actual_matrix, center_matrix, floor=floor)
    share_error = center_matrix - actual_matrix
    covariance = np.cov(residual_clr, rowvar=False, ddof=1)
    return {
        "n_observations": int(len(actual_matrix)),
        "party_count": int(actual_matrix.shape[1]),
        "share_rmse": float(np.sqrt(np.mean(share_error**2))),
        "share_mae": float(np.mean(np.abs(share_error))),
        "mean_territory_l1": float(np.mean(np.sum(np.abs(share_error), axis=1))),
        "clr_residual_mean": residual_clr.mean(axis=0).tolist(),
        "clr_residual_sd": residual_clr.std(axis=0, ddof=1).tolist(),
        "clr_residual_covariance": np.asarray(covariance, dtype=float).tolist(),
    }
