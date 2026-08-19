#!/usr/bin/env python3
"""Calibrate national 2026 uncertainty under M26-NATIONAL-UNCERTAINTY-V1."""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SEL_PATH = ROOT / "scripts" / "select_national_model_2026_v1.py"
spec = importlib.util.spec_from_file_location("m26_national_selection", SEL_PATH)
sel = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(sel)

PARTIES = sel.PARTIES
TRANSITIONS = [(1997, 2002), (2002, 2007), (2007, 2011), (2011, 2016), (2016, 2021)]
SCORED = TRANSITIONS[1:]
DF = 3
COVERAGE_DRAWS = 100_000
PROSPECTIVE_DRAWS = 50_000


def project_simplex_batch(v: np.ndarray) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    if v.ndim != 2 or v.shape[1] != len(PARTIES) or not np.isfinite(v).all():
        raise ValueError("invalid batch for simplex projection")
    u = np.sort(v, axis=1)[:, ::-1]
    cssv = np.cumsum(u, axis=1) - 1.0
    ind = np.arange(1, v.shape[1] + 1, dtype=float)
    cond = u - cssv / ind > 0
    rho = cond.sum(axis=1) - 1
    if np.any(rho < 0):
        raise RuntimeError("simplex projection failed")
    theta = cssv[np.arange(len(v)), rho] / (rho + 1)
    out = np.maximum(v - theta[:, None], 0.0)
    sums = out.sum(axis=1)
    if np.any(sums <= 0):
        raise RuntimeError("empty projected simplex row")
    out /= sums[:, None]
    return out


def draw_national(center: np.ndarray, scale: float, n: int, seed: int, prospective_floor: bool = False) -> np.ndarray:
    if scale <= 0 or not math.isfinite(scale):
        raise ValueError("scale must be finite and positive")
    rng = np.random.default_rng(seed)
    z = rng.normal(size=(n, len(PARTIES)))
    z -= z.mean(axis=1, keepdims=True)
    # After demeaning iid N(0,1), each component variance is (p-1)/p = 8/9.
    z /= math.sqrt((len(PARTIES) - 1) / len(PARTIES))
    chi = rng.chisquare(DF, size=n)
    innovation = scale * z / np.sqrt(chi[:, None] / DF)
    out = project_simplex_batch(center[None, :] + innovation)
    if prospective_floor:
        out = np.maximum(out, 1e-8)
        out /= out.sum(axis=1, keepdims=True)
    return out


def _vector(history: dict[int, list[float]], year: int) -> np.ndarray:
    return np.asarray(history[year], dtype=float)


def run(coverage_draws: int = COVERAGE_DRAWS, prospective_draws: int = PROSPECTIVE_DRAWS) -> dict:
    selected = sel.run()
    if selected["winner"] != "PREVIOUS_NATIONAL_PERSISTENCE":
        raise RuntimeError("uncertainty V1 is frozen for the selected persistence point model")
    history = sel.load_history()
    residuals: dict[tuple[int, int], np.ndarray] = {}
    energies: dict[tuple[int, int], float] = {}
    for a, b in TRANSITIONS:
        e = _vector(history, b) - _vector(history, a)
        if abs(float(e.sum())) > 1e-10:
            raise RuntimeError(f"residual {a}->{b} does not sum to zero")
        residuals[(a, b)] = e
        energies[(a, b)] = float(np.sqrt(np.mean(e * e)))

    fold_results = {}
    pooled80 = []
    pooled95 = []
    for fold_index, (origin, target) in enumerate(SCORED):
        available = [ab for ab in TRANSITIONS if ab[1] <= origin]
        if not available:
            raise RuntimeError(f"no prior uncertainty history for {origin}->{target}")
        scale = max(energies[ab] for ab in available)
        draws = draw_national(_vector(history, origin), scale, coverage_draws, 26092600 + fold_index)
        actual = _vector(history, target)
        lo80, hi80 = np.quantile(draws, [0.10, 0.90], axis=0)
        lo95, hi95 = np.quantile(draws, [0.025, 0.975], axis=0)
        c80 = (actual >= lo80 - 1e-12) & (actual <= hi80 + 1e-12)
        c95 = (actual >= lo95 - 1e-12) & (actual <= hi95 + 1e-12)
        pooled80.extend(bool(x) for x in c80)
        pooled95.extend(bool(x) for x in c95)
        fold_results[f"{origin}_TO_{target}"] = {
            "origin_year": origin,
            "target_year": target,
            "available_residual_transitions": [f"{a}_TO_{b}" for a, b in available],
            "scale": scale,
            "coverage80": float(c80.mean()),
            "coverage95": float(c95.mean()),
            "misses80": [PARTIES[i] for i, ok in enumerate(c80) if not ok],
            "misses95": [PARTIES[i] for i, ok in enumerate(c95) if not ok],
            "intervals": {
                p: {
                    "actual": float(actual[i]),
                    "q10": float(lo80[i]), "q90": float(hi80[i]),
                    "q025": float(lo95[i]), "q975": float(hi95[i]),
                }
                for i, p in enumerate(PARTIES)
            },
        }

    coverage80 = sum(pooled80) / len(pooled80)
    coverage95 = sum(pooled95) / len(pooled95)
    status = "PASS" if coverage80 >= 0.80 and coverage95 >= 0.95 else "FAIL"

    prospective_scale = max(energies.values())
    center2026 = np.asarray([selected["forecast_2026"]["point_share"][p] for p in PARTIES], dtype=float)
    future = draw_national(center2026, prospective_scale, prospective_draws, 26092352, prospective_floor=True)
    prospective_summary = {}
    for i, p in enumerate(PARTIES):
        q025, q10, q50, q90, q975 = np.quantile(future[:, i], [0.025, 0.10, 0.50, 0.90, 0.975])
        prospective_summary[p] = {
            "point": float(center2026[i]),
            "draw_mean": float(future[:, i].mean()),
            "q025": float(q025), "q10": float(q10), "median": float(q50), "q90": float(q90), "q975": float(q975),
            "floor_mass": float(np.mean(future[:, i] <= 1.0000001e-8)),
        }

    return {
        "schema_version": "1.0",
        "artifact_id": "M26-NATIONAL-UNCERTAINTY-2026-V1",
        "contract": "morocco26/data/goal100/forecast_lab/national_uncertainty_contract_v1.json",
        "selected_point_model": selected["winner"],
        "party_order": PARTIES,
        "residual_history": {
            f"{a}_TO_{b}": {
                "energy_rmse": energies[(a, b)],
                "residual": {p: float(residuals[(a, b)][i]) for i, p in enumerate(PARTIES)},
            }
            for a, b in TRANSITIONS
        },
        "prequential": {
            "draws_per_fold": coverage_draws,
            "folds": fold_results,
            "pooled_component_n": len(pooled80),
            "coverage80": coverage80,
            "coverage95": coverage95,
            "required_coverage80": 0.80,
            "required_coverage95": 0.95,
            "status": status,
        },
        "prospective_2026": {
            "scale": prospective_scale,
            "df": DF,
            "draws_for_diagnostic_summary": prospective_draws,
            "seed": 26092352,
            "summary": prospective_summary,
            "generator_status": "READY_FOR_DOWNSTREAM_SIMULATION" if status == "PASS" else "BLOCKED",
        },
        "probability_status": "NATIONAL_UNCERTAINTY_CALIBRATED" if status == "PASS" else "NOT_PROMOTED",
        "limitations": [
            "Only five prior national transitions exist, so tail probabilities remain low-resolution.",
            "The exchangeable tangent model is intentionally conservative and does not fit party-specific covariance from n<<p.",
            "Simplex projection creates boundary mass for small parties; downstream uses a 1e-8 numerical floor, not substantive zero-probability exclusion."
        ],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None)
    ap.add_argument("--coverage-draws", type=int, default=COVERAGE_DRAWS)
    ap.add_argument("--prospective-draws", type=int, default=PROSPECTIVE_DRAWS)
    args = ap.parse_args()
    result = run(args.coverage_draws, args.prospective_draws)
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print("NATIONAL_UNCERTAINTY=" + json.dumps({
        "status": result["prequential"]["status"],
        "coverage80": result["prequential"]["coverage80"],
        "coverage95": result["prequential"]["coverage95"],
        "prospective_scale": result["prospective_2026"]["scale"],
        "folds": {k: {"scale": v["scale"], "coverage80": v["coverage80"], "coverage95": v["coverage95"], "misses80": v["misses80"], "misses95": v["misses95"]} for k, v in result["prequential"]["folds"].items()},
    }, sort_keys=True))
    if result["prequential"]["status"] != "PASS":
        raise SystemExit(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
