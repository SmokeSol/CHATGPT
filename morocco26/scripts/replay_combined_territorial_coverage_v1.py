#!/usr/bin/env python3
"""Prequential combined national + lambda=.5 geography coverage replay.

This script implements the already-frozen M26-COMBINED-TERRITORIAL-COVERAGE-V1
contract.  It deliberately resamples *share-space* conditional geography error,
not CLR residuals, then rakes the simulated territories back to the exact same
national draw so national uncertainty is counted exactly once.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


sel = _load_module("m26_nat_sel", SCRIPTS / "select_national_model_2026_v1.py")
natunc = _load_module("m26_nat_unc", SCRIPTS / "calibrate_national_uncertainty_2026_v1.py")
geo = _load_module("m26_geo_unc", SCRIPTS / "calibrate_uncertainty_v3.py")

PARTIES = tuple(sel.PARTIES)
LAMBDA = 0.5
DRAWS = 20_000
BATCH = 500
TARGET_FLOOR = 1e-8
RAKE_FLOOR = 1e-12
TOL = 1e-8
MAX_ITER = 2000
SCORED = [(2011, 2016), (2016, 2021)]
NATIONAL_SEEDS = {(2011, 2016): 26092602, (2016, 2021): 26092603}
GEO_SEEDS = {(2011, 2016): 26092702, (2016, 2021): 26092703}


def normalize_targets(x: np.ndarray) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    x = np.maximum(x, TARGET_FLOOR)
    x /= x.sum(axis=1, keepdims=True)
    return x


def normalize_rows_batch(x: np.ndarray, floor: float = RAKE_FLOOR) -> np.ndarray:
    x = np.asarray(x, dtype=float)
    if x.ndim != 3 or x.shape[2] != len(PARTIES):
        raise ValueError("expected batch x territory x party array")
    if not np.all(np.isfinite(x)):
        raise ValueError("non-finite simulated shares")
    x = np.maximum(x, floor)
    x /= x.sum(axis=2, keepdims=True)
    return x


def rake_batch(x: np.ndarray, weights: np.ndarray, targets: np.ndarray) -> tuple[np.ndarray, int, float]:
    """Rake BxTxP rows to BxP targets using one prospectively known T-vector."""
    x = normalize_rows_batch(x)
    w = np.asarray(weights, dtype=float)
    if w.ndim != 1 or len(w) != x.shape[1] or np.any(w <= 0) or not np.all(np.isfinite(w)):
        raise ValueError("invalid origin weights")
    w = w / w.sum()
    targets = normalize_targets(targets)
    iterations = 0
    max_error = math.inf
    for iterations in range(1, MAX_ITER + 1):
        agg = np.einsum("t,btp->bp", w, x, optimize=True)
        max_error = float(np.max(np.abs(agg - targets)))
        if max_error <= TOL:
            break
        factors = targets / np.maximum(agg, RAKE_FLOOR)
        x = normalize_rows_batch(np.maximum(x * factors[:, None, :], RAKE_FLOOR))
    if max_error > TOL:
        agg = np.einsum("t,btp->bp", w, x, optimize=True)
        max_error = float(np.max(np.abs(agg - targets)))
    if max_error > TOL:
        raise RuntimeError(f"batch raking failed: max national error={max_error:.3e}")
    return x, iterations, max_error


def centers_for_targets(origin_share: np.ndarray, origin_weight: np.ndarray, targets: np.ndarray) -> tuple[np.ndarray, int, float]:
    w = np.asarray(origin_weight, dtype=float)
    w /= w.sum()
    origin_national = np.einsum("t,tp->p", w, origin_share, optimize=True)
    raw = targets[:, None, :] + LAMBDA * (origin_share[None, :, :] - origin_national[None, None, :])
    raw = normalize_rows_batch(np.maximum(raw, RAKE_FLOOR))
    return rake_batch(raw, w, targets)


def national_scale_for_origin(history: dict[int, list[float]], origin: int) -> tuple[float, list[str]]:
    energies = []
    labels = []
    for a, b in natunc.TRANSITIONS:
        if b <= origin:
            e = np.asarray(history[b], dtype=float) - np.asarray(history[a], dtype=float)
            energies.append(float(np.sqrt(np.mean(e * e))))
            labels.append(f"{a}_TO_{b}")
    if not energies:
        raise RuntimeError(f"no prior national residual support for origin {origin}")
    return max(energies), labels


def geography_pools() -> dict[tuple[int, int], np.ndarray]:
    # These functions reconstruct the already-validated conditional geography
    # centres using realized target national shares solely for retrospective
    # decomposition.  Only *prior* fold residuals are admitted below.
    g0711 = geo.fold_2007_2011()
    g1116 = geo.fold_direct(2011, 2016)
    r0711 = np.asarray(g0711["actual"], dtype=float) - np.asarray(g0711["center"], dtype=float)
    r1116 = np.asarray(g1116["actual"], dtype=float) - np.asarray(g1116["center"], dtype=float)
    for name, r in [("2007_TO_2011", r0711), ("2011_TO_2016", r1116)]:
        if np.max(np.abs(r.sum(axis=1))) > 1e-9:
            raise RuntimeError(f"share residual rows do not sum to zero: {name}")
        if not np.all(np.isfinite(r)):
            raise RuntimeError(f"non-finite share residuals: {name}")
    return {
        (2011, 2016): r0711,
        (2016, 2021): np.vstack([r0711, r1116]),
    }


def replay_fold(origin: int, target: int, pool: np.ndarray, draws: int, batch_size: int) -> dict:
    origin_meta, origin_share, origin_weight = geo.modern_year(origin)
    target_meta, actual, _target_weight = geo.modern_year(target)
    if [x["constituency_id"] for x in origin_meta] != [x["constituency_id"] for x in target_meta]:
        raise RuntimeError(f"territory order drift {origin}->{target}")

    history = sel.load_history()
    scale, available_national = national_scale_for_origin(history, origin)
    national_center = np.asarray(history[origin], dtype=float)
    national_draws = natunc.draw_national(
        national_center,
        scale,
        draws,
        NATIONAL_SEEDS[(origin, target)],
        prospective_floor=False,
    )
    national_draws = normalize_targets(national_draws)

    rng = np.random.default_rng(GEO_SEEDS[(origin, target)])
    simulations = np.empty((draws, 92, len(PARTIES)), dtype=np.float32)
    max_rake_error = 0.0
    max_rake_iterations = 0

    for start in range(0, draws, batch_size):
        stop = min(draws, start + batch_size)
        targets = national_draws[start:stop]
        centers, it1, err1 = centers_for_targets(origin_share, origin_weight, targets)
        sample_index = rng.integers(0, len(pool), size=(stop - start, 92))
        residual = pool[sample_index]
        candidate = normalize_rows_batch(np.maximum(centers + residual, RAKE_FLOOR))
        final, it2, err2 = rake_batch(candidate, origin_weight, targets)
        simulations[start:stop] = final.astype(np.float32)
        max_rake_error = max(max_rake_error, err1, err2)
        max_rake_iterations = max(max_rake_iterations, it1, it2)

    q025, q10, q90, q975 = np.quantile(simulations, [0.025, 0.10, 0.90, 0.975], axis=0)
    c80 = (actual >= q10 - 1e-12) & (actual <= q90 + 1e-12)
    c95 = (actual >= q025 - 1e-12) & (actual <= q975 + 1e-12)
    width80 = q90 - q10
    width95 = q975 - q025

    party = {}
    for j, p in enumerate(PARTIES):
        party[p] = {
            "coverage80": float(c80[:, j].mean()),
            "coverage95": float(c95[:, j].mean()),
            "mean_width80": float(width80[:, j].mean()),
            "mean_width95": float(width95[:, j].mean()),
            "miss_count80": int((~c80[:, j]).sum()),
            "miss_count95": int((~c95[:, j]).sum()),
        }

    return {
        "origin_year": origin,
        "target_year": target,
        "territories": 92,
        "party_count": len(PARTIES),
        "draws": draws,
        "national_scale": scale,
        "national_prior_residual_support": available_national,
        "geography_residual_rows": int(len(pool)),
        "geography_residual_sampling": "WHOLE_NINE_PARTY_SHARE_ERROR_ROW_WITH_REPLACEMENT",
        "coverage80": float(c80.mean()),
        "coverage95": float(c95.mean()),
        "covered_cells80": int(c80.sum()),
        "covered_cells95": int(c95.sum()),
        "total_cells": int(c80.size),
        "party": party,
        "mean_interval_width80": float(width80.mean()),
        "mean_interval_width95": float(width95.mean()),
        "max_rake_error": max_rake_error,
        "max_rake_iterations": max_rake_iterations,
        "coverage80_mask": c80,
        "coverage95_mask": c95,
    }


def run(draws: int = DRAWS, batch_size: int = BATCH) -> dict:
    if draws < 1000:
        raise ValueError("draws must be >=1000")
    pools = geography_pools()
    folds = [replay_fold(a, b, pools[(a, b)], draws, batch_size) for a, b in SCORED]
    pooled80 = sum(f["covered_cells80"] for f in folds) / sum(f["total_cells"] for f in folds)
    pooled95 = sum(f["covered_cells95"] for f in folds) / sum(f["total_cells"] for f in folds)
    total_cells = sum(f["total_cells"] for f in folds)
    status = "PASS" if pooled80 >= 0.80 and pooled95 >= 0.95 else "FAIL"

    party_pooled = {}
    for p in PARTIES:
        covered80 = sum((f["party"][p]["coverage80"] * 92) for f in folds)
        covered95 = sum((f["party"][p]["coverage95"] * 92) for f in folds)
        party_pooled[p] = {
            "coverage80": float(covered80 / (92 * len(folds))),
            "coverage95": float(covered95 / (92 * len(folds))),
        }

    serial_folds = []
    for f in folds:
        serial_folds.append({k: v for k, v in f.items() if k not in {"coverage80_mask", "coverage95_mask"}})
    return {
        "schema_version": "1.0",
        "artifact_id": "M26-COMBINED-TERRITORIAL-COVERAGE-V1",
        "contract": "morocco26/data/goal100/forecast_lab/combined_territorial_coverage_contract_v1.json",
        "point_model": "PREVIOUS_NATIONAL_PERSISTENCE",
        "national_uncertainty": "M26-NATIONAL-UNCERTAINTY-V1",
        "territorial_lambda": LAMBDA,
        "geography_residual_space": "RAW_SHARE_ERROR_ACTUAL_MINUS_CONDITIONAL_CENTER",
        "scored_folds": serial_folds,
        "pooled": {
            "total_cells": total_cells,
            "coverage80": float(pooled80),
            "coverage95": float(pooled95),
            "required_coverage80": 0.80,
            "required_coverage95": 0.95,
            "party": party_pooled,
            "status": status,
        },
        "promotion_effect": "READY_FOR_FINAL_2026_LEGAL_SIMULATION" if status == "PASS" else "FINAL_PROBABILITIES_BLOCKED",
        "limitations": [
            "Only 2011_TO_2016 and 2016_TO_2021 have genuinely prior conditional geography residual support and are scored.",
            "The residual library is exchangeable across territories and preserves within-row party dependence but not territory-specific variance.",
            "Marginal cell coverage does not establish full joint 92-territory calibration."
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--batch-size", type=int, default=BATCH)
    args = ap.parse_args()
    result = run(args.draws, args.batch_size)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("COMBINED_TERRITORIAL_COVERAGE=" + json.dumps({
        "status": result["pooled"]["status"],
        "coverage80": result["pooled"]["coverage80"],
        "coverage95": result["pooled"]["coverage95"],
        "total_cells": result["pooled"]["total_cells"],
        "folds": {f"{f['origin_year']}_TO_{f['target_year']}": {"coverage80": f["coverage80"], "coverage95": f["coverage95"], "geography_residual_rows": f["geography_residual_rows"], "max_rake_error": f["max_rake_error"]} for f in result["scored_folds"]},
        "party": result["pooled"]["party"],
    }, sort_keys=True))
    if result["pooled"]["status"] != "PASS":
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
