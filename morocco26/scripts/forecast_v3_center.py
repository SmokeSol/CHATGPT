#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
LAB = G100 / "forecast_lab"
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPTS))

from morocco26.forecast_v3 import (  # noqa: E402
    ForecastV3Error,
    build_territorial_centers,
    normalize_vector,
    weighted_national,
)
import goal100_run_fminus1 as legacy  # noqa: E402

LAMBDA = 0.5
PARTIES = tuple(legacy.BUCKETS)
DEFAULT_OUT = LAB / "territorial_center_2026_v3.json"
SCORES = LAB / "baseline_scores_v2.json"


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_selection() -> dict:
    scores = read_json(SCORES)
    if scores.get("skill_floor_winner") != "HALF_SHRINK":
        raise ForecastV3Error("rolling-origin winner is not HALF_SHRINK")
    if float(scores.get("lambda_selected_for_2026")) != LAMBDA:
        raise ForecastV3Error("rolling-origin lambda is not frozen at 0.5")
    folds = scores.get("folds", {})
    if set(folds) != {"2011", "2016", "2021"}:
        raise ForecastV3Error("three-fold rolling-origin evidence is incomplete")
    return scores


def validate_national_forecast(payload: dict) -> np.ndarray:
    if payload.get("target_year") != 2026:
        raise ForecastV3Error("national forecast target_year must equal 2026")
    if payload.get("status") != "READY_FOR_STRUCTURAL_CENTER":
        raise ForecastV3Error("national forecast is not promoted for structural centering")
    if payload.get("data_class") != "CURRENT_PRE_ELECTION_NATIONAL_FORECAST":
        raise ForecastV3Error("national forecast must be current pre-election evidence")
    if payload.get("target_outcome_used") is not False:
        raise ForecastV3Error("target_outcome_used must be false")
    if tuple(payload.get("party_order", [])) != PARTIES:
        raise ForecastV3Error(f"party_order must be exactly {PARTIES}")
    if not payload.get("as_of"):
        raise ForecastV3Error("national forecast must declare an as_of cutoff")
    evidence = payload.get("evidence", [])
    if not isinstance(evidence, list) or not evidence:
        raise ForecastV3Error("national forecast must contain non-empty evidence lineage")
    shares = payload.get("point_share")
    if not isinstance(shares, dict) or set(shares) != set(PARTIES):
        raise ForecastV3Error("point_share must contain exactly the v3 party buckets")
    vector = normalize_vector([float(shares[p]) for p in PARTIES])
    if float(np.max(np.abs(vector - np.asarray([shares[p] for p in PARTIES], dtype=float)))) > 1e-8:
        raise ForecastV3Error("point_share must already sum to one; implicit normalization is forbidden")
    if np.any(vector <= 1e-10):
        raise ForecastV3Error("all national point shares must be strictly positive")
    return vector


def load_2021_prior() -> tuple[list[dict], np.ndarray, np.ndarray]:
    y21 = legacy.load_year(2021)
    mapping = legacy.build_mapping(y21)
    ordered = sorted(y21, key=lambda historical_id: mapping[historical_id]["constituency_id"])
    rows = []
    raw = []
    for historical_id in ordered:
        repo = mapping[historical_id]
        counts = legacy.bucket_counts(y21[historical_id])
        raw.append(counts)
        rows.append(
            {
                "historical_id": int(historical_id),
                "constituency_id": repo["constituency_id"],
                "name": repo["name"],
                "region": repo["region"],
                "magnitude": int(repo["seats"]),
            }
        )
    matrix = np.stack(raw)
    weights = matrix.sum(axis=1)
    prior = matrix / weights[:, None]
    if len(rows) != 92:
        raise ForecastV3Error(f"expected 92 local constituencies, found {len(rows)}")
    return rows, prior, weights


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build the v3 92-territory structural center from a current national 2026 forecast."
    )
    parser.add_argument("national_forecast", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.national_forecast.exists():
        raise SystemExit(f"FORECAST_V3_FAIL: missing {args.national_forecast}")
    try:
        selection = validate_selection()
        national_payload = read_json(args.national_forecast)
        national_target = validate_national_forecast(national_payload)
        territory_meta, prior, weights = load_2021_prior()
        prior_national = weighted_national(prior, weights)
        center, diagnostics = build_territorial_centers(
            prior,
            weights,
            national_target,
            lambda_=LAMBDA,
        )
    except ForecastV3Error as exc:
        raise SystemExit(f"FORECAST_V3_FAIL: {exc}") from exc

    aggregate = weighted_national(center, weights)
    out_rows = []
    for index, meta in enumerate(territory_meta):
        out_rows.append(
            {
                **meta,
                "2021_valid_vote_weight": float(weights[index]),
                "prior_2021_share": {
                    party: float(prior[index, pidx]) for pidx, party in enumerate(PARTIES)
                },
                "center_2026_share": {
                    party: float(center[index, pidx]) for pidx, party in enumerate(PARTIES)
                },
            }
        )

    output = {
        "schema_version": "3.0",
        "forecast_id": "M26-2026-TERRITORIAL-CENTER-V3",
        "target_year": 2026,
        "territories": 92,
        "status": "STRUCTURAL_CENTER_READY_POINT_ONLY",
        "probabilistic_forecast_status": "NOT_PROMOTED_UNCERTAINTY_RECALIBRATION_REQUIRED",
        "target_outcome_used": False,
        "party_order": list(PARTIES),
        "model": {
            "lambda": LAMBDA,
            "identity": "national_2026 + lambda*(territory_2021-national_2021), then positive raking to national_2026",
            "why": "This reduces exactly to the validated HALF_SHRINK model when national_2026 equals national_2021 while allowing a separate current national swing.",
            "selection_evidence": str(SCORES.relative_to(ROOT)),
            "selection_sha256": sha256_path(SCORES),
            "selection_rule": selection["selection_rule"],
        },
        "national_forecast": {
            "forecast_id": national_payload.get("forecast_id"),
            "as_of": national_payload["as_of"],
            "sha256": sha256_path(args.national_forecast),
            "point_share": {party: float(national_target[i]) for i, party in enumerate(PARTIES)},
        },
        "origin_2021_national_share": {
            party: float(prior_national[i]) for i, party in enumerate(PARTIES)
        },
        "center_weighted_national_share": {
            party: float(aggregate[i]) for i, party in enumerate(PARTIES)
        },
        "raking_diagnostics": diagnostics.as_dict(),
        "weighting_note": "Raking uses 2021 local valid-vote mass solely as a centering constraint. 2026 N/turnout remain stochastic downstream.",
        "rows": out_rows,
    }
    write_json(args.output, output)
    print(
        "FORECAST_V3_CENTER_READY="
        + json.dumps(
            {
                "output": str(args.output),
                "territories": 92,
                "lambda": LAMBDA,
                "max_national_abs_error": diagnostics.max_national_abs_error,
                "probabilistic_forecast_status": output["probabilistic_forecast_status"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
