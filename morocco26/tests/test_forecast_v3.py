from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco26.forecast_v3 import (  # noqa: E402
    ForecastV3Error,
    build_territorial_centers,
    conditional_territorial_residuals,
    weighted_national,
)


class ForecastV3CenterTests(unittest.TestCase):
    def test_target_national_is_exact_after_centering(self) -> None:
        prior = np.asarray(
            [
                [0.60, 0.30, 0.10],
                [0.20, 0.50, 0.30],
                [0.30, 0.20, 0.50],
            ],
            dtype=float,
        )
        weights = np.asarray([1.0, 2.0, 1.0])
        target = np.asarray([0.25, 0.45, 0.30])
        center, diagnostics = build_territorial_centers(prior, weights, target, lambda_=0.5)
        np.testing.assert_allclose(center.sum(axis=1), 1.0, atol=1e-12)
        np.testing.assert_allclose(weighted_national(center, weights), target, atol=1e-10)
        self.assertTrue(diagnostics.converged)

    def test_validated_identity_is_preserved_when_target_equals_origin_national(self) -> None:
        prior = np.asarray(
            [
                [0.60, 0.30, 0.10],
                [0.20, 0.50, 0.30],
                [0.30, 0.20, 0.50],
            ],
            dtype=float,
        )
        weights = np.asarray([1.0, 2.0, 1.0])
        origin_national = weighted_national(prior, weights)
        expected = 0.5 * prior + 0.5 * origin_national[None, :]
        center, diagnostics = build_territorial_centers(
            prior, weights, origin_national, lambda_=0.5
        )
        np.testing.assert_allclose(center, expected, atol=1e-12)
        self.assertFalse(diagnostics.correction_required)

    def test_large_national_swing_stays_positive_and_rakes_back_to_target(self) -> None:
        prior = np.asarray(
            [
                [0.90, 0.09, 0.01],
                [0.05, 0.90, 0.05],
                [0.05, 0.01, 0.94],
            ],
            dtype=float,
        )
        target = np.asarray([0.02, 0.49, 0.49])
        weights = np.ones(3)
        center, diagnostics = build_territorial_centers(prior, weights, target, lambda_=0.5)
        self.assertTrue(np.all(center > 0))
        self.assertTrue(diagnostics.correction_required)
        np.testing.assert_allclose(weighted_national(center, weights), target, atol=1e-9)

    def test_invalid_lambda_fails_closed(self) -> None:
        with self.assertRaises(ForecastV3Error):
            build_territorial_centers(
                [[0.5, 0.5], [0.4, 0.6]], [1, 1], [0.5, 0.5], lambda_=1.1
            )

    def test_clr_residuals_are_zero_sum_per_observation(self) -> None:
        actual = np.asarray([[0.50, 0.30, 0.20], [0.20, 0.30, 0.50]])
        center = np.asarray([[0.45, 0.35, 0.20], [0.25, 0.25, 0.50]])
        residual = conditional_territorial_residuals(actual, center)
        np.testing.assert_allclose(residual.sum(axis=1), 0.0, atol=1e-12)


if __name__ == "__main__":
    unittest.main()
