#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
HIST = G100 / "historical"
LAB = G100 / "forecast_lab"
SRC = ROOT / "src"
SCRIPTS = ROOT / "scripts"
OUT = LAB / "uncertainty_calibration_v3_conditional.json"
SCORES = LAB / "baseline_scores_v2.json"
LAMBDA = 0.5
FLOOR = 1e-10

sys.path.insert(0, str(SRC))
sys.path.insert(0, str(SCRIPTS))

from morocco26.forecast_v3 import (  # noqa: E402
    ForecastV3Error,
    build_territorial_centers,
    conditional_territorial_residuals,
    normalize_rows,
    residual_summary,
    weighted_national,
)
import goal100_run_fminus1 as legacy  # noqa: E402

PARTIES = tuple(legacy.BUCKETS)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: object) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def modern_year(year: int) -> tuple[list[dict], np.ndarray, np.ndarray]:
    rows = legacy.load_year(year)
    mapping = legacy.build_mapping(rows)
    ordered = sorted(rows, key=lambda historical_id: mapping[historical_id]["constituency_id"])
    metadata: list[dict] = []
    raw: list[np.ndarray] = []
    for historical_id in ordered:
        repo = mapping[historical_id]
        counts = legacy.bucket_counts(rows[historical_id])
        raw.append(counts)
        metadata.append(
            {
                "historical_id": int(historical_id),
                "constituency_id": repo["constituency_id"],
                "name": repo["name"],
                "region": repo["region"],
            }
        )
    raw_matrix = np.stack(raw)
    weights = raw_matrix.sum(axis=1)
    shares = raw_matrix / weights[:, None]
    if len(metadata) != 92:
        raise ForecastV3Error(f"{year} expected 92 local territories, found {len(metadata)}")
    return metadata, shares, weights


def fold_direct(origin_year: int, target_year: int) -> dict:
    origin_meta, origin_share, origin_weight = modern_year(origin_year)
    target_meta, actual, target_weight = modern_year(target_year)
    origin_ids = [row["constituency_id"] for row in origin_meta]
    target_ids = [row["constituency_id"] for row in target_meta]
    if origin_ids != target_ids:
        raise ForecastV3Error(f"{origin_year}->{target_year} territory order mismatch")

    target_national = weighted_national(actual, target_weight)
    center, diagnostics = build_territorial_centers(
        origin_share,
        origin_weight,
        target_national,
        lambda_=LAMBDA,
        floor=FLOOR,
    )
    residual = conditional_territorial_residuals(actual, center, floor=FLOOR)
    observations = []
    for index, meta in enumerate(target_meta):
        observations.append(
            {
                "origin_year": origin_year,
                "target_year": target_year,
                "territory_id": meta["constituency_id"],
                "support_policy": "FULL_NATIVE_IDENTITY_92",
                "residual_clr": {
                    party: float(residual[index, pidx]) for pidx, party in enumerate(PARTIES)
                },
            }
        )
    return {
        "origin_year": origin_year,
        "target_year": target_year,
        "support_policy": "FULL_NATIVE_IDENTITY_92",
        "mapped_territories": 92,
        "conditioning": "REALIZED_TARGET_NATIONAL_USED_ONLY_TO_ISOLATE_TERRITORIAL_ERROR",
        "target_national_share": {
            party: float(target_national[i]) for i, party in enumerate(PARTIES)
        },
        "center_diagnostics": diagnostics.as_dict(),
        "summary": residual_summary(actual, center, floor=FLOOR),
        "actual": actual,
        "center": center,
        "observations": observations,
    }


def fold_2007_2011() -> dict:
    gate = read_json(HIST / "2007" / "acceptance_gate_v2.json")
    if gate.get("scientific_status") != "PASS_FOR_ROLLING_ORIGIN_BACKTEST":
        raise ForecastV3Error("2007 acceptance gate is not PASS")

    source_rows = read_json(HIST / "2007" / "legislative_2007_outcome_canonical.json")[
        "local_rows"
    ]
    by_native = {row["native_id"]: row for row in source_rows}
    source_raw_all = np.stack([legacy.bucket_counts(row) for row in source_rows])
    origin_national = source_raw_all.sum(axis=0)
    origin_national /= origin_national.sum()

    crosswalk = read_json(HIST / "2007" / "crosswalk_to_modern.json")["rows"]
    candidates: dict[str, list[object]] = defaultdict(list)
    for row in crosswalk:
        targets = row.get("modern_targets") or []
        native_id = row.get("native_id")
        if (
            row.get("mapping_type") != "UNRESOLVED"
            and len(targets) == 1
            and native_id in by_native
        ):
            candidates[targets[0]["constituency_id"]].append(native_id)

    target_meta, target_share_all, target_weight_all = modern_year(2011)
    target_pos = {row["constituency_id"]: index for index, row in enumerate(target_meta)}
    mapped = [
        row["constituency_id"]
        for row in target_meta
        if row["constituency_id"] in candidates and len(candidates[row["constituency_id"]]) == 1
    ]
    if not mapped:
        raise ForecastV3Error("2007->2011 has no conservative one-to-one support")

    prior_raw = np.stack(
        [legacy.bucket_counts(by_native[candidates[territory_id][0]]) for territory_id in mapped]
    )
    prior = prior_raw / prior_raw.sum(axis=1, keepdims=True)
    actual = np.stack([target_share_all[target_pos[territory_id]] for territory_id in mapped])
    target_national = weighted_national(target_share_all, target_weight_all)

    # The 2007 fold covers only the explicit 1:1 common support. Do not rake this
    # non-national subset to the full 2011 national aggregate; condition on that
    # aggregate, retain the validated 2007 deviation, and normalize each row only.
    raw_center = target_national[None, :] + LAMBDA * (
        prior - origin_national[None, :]
    )
    correction_required = bool(np.any(raw_center <= FLOOR))
    center = normalize_rows(np.maximum(raw_center, FLOOR), floor=FLOOR)
    residual = conditional_territorial_residuals(actual, center, floor=FLOOR)

    observations = []
    for index, territory_id in enumerate(mapped):
        observations.append(
            {
                "origin_year": 2007,
                "target_year": 2011,
                "territory_id": territory_id,
                "support_policy": "COMMON_EXPLICIT_1_TO_1_CROSSWALK_ONLY",
                "residual_clr": {
                    party: float(residual[index, pidx]) for pidx, party in enumerate(PARTIES)
                },
            }
        )
    return {
        "origin_year": 2007,
        "target_year": 2011,
        "support_policy": "COMMON_EXPLICIT_1_TO_1_CROSSWALK_ONLY",
        "mapped_territories": len(mapped),
        "conditioning": "REALIZED_TARGET_NATIONAL_USED_ONLY_TO_ISOLATE_TERRITORIAL_ERROR",
        "target_national_share": {
            party: float(target_national[i]) for i, party in enumerate(PARTIES)
        },
        "center_diagnostics": {
            "raking": "DISABLED_INCOMPLETE_57_OF_92_SUPPORT",
            "correction_required": correction_required,
            "row_sum_max_abs_error": float(np.max(np.abs(center.sum(axis=1) - 1.0))),
        },
        "summary": residual_summary(actual, center, floor=FLOOR),
        "actual": actual,
        "center": center,
        "observations": observations,
    }


def serializable_fold(fold: dict) -> dict:
    return {
        key: value
        for key, value in fold.items()
        if key not in {"actual", "center", "observations"}
    }


def main() -> None:
    scores = read_json(SCORES)
    if scores.get("skill_floor_winner") != "HALF_SHRINK":
        raise SystemExit("UNCERTAINTY_V3_FAIL: HALF_SHRINK is not the frozen rolling-origin winner")
    if float(scores.get("lambda_selected_for_2026")) != LAMBDA:
        raise SystemExit("UNCERTAINTY_V3_FAIL: lambda drifted from 0.5")

    try:
        folds = [fold_2007_2011(), fold_direct(2011, 2016), fold_direct(2016, 2021)]
    except ForecastV3Error as exc:
        raise SystemExit(f"UNCERTAINTY_V3_FAIL: {exc}") from exc

    expected_mapped = int(scores["folds"]["2011"]["mapped_territories"])
    if folds[0]["mapped_territories"] != expected_mapped:
        raise SystemExit(
            "UNCERTAINTY_V3_FAIL: 2007 common-support count disagrees with rolling-origin selection"
        )

    actual = np.vstack([fold["actual"] for fold in folds])
    center = np.vstack([fold["center"] for fold in folds])
    observations = [obs for fold in folds for obs in fold["observations"]]
    pooled = residual_summary(actual, center, floor=FLOOR)
    abs_error = np.abs(center - actual)
    territory_l1 = np.sum(abs_error, axis=1)

    output = {
        "schema_version": "3.0",
        "calibration_id": "M26-UNCERTAINTY-V3-CONDITIONAL-TERRITORIAL",
        "target_model": "CURRENT_NATIONAL_2026_PLUS_LAMBDA_0_5_TERRITORIAL_DEVIATION",
        "lambda": LAMBDA,
        "party_order": list(PARTIES),
        "component": "TERRITORIAL_RESIDUAL_CONDITIONAL_ON_NATIONAL",
        "status": "CONDITIONAL_TERRITORIAL_RESIDUAL_LIBRARY_BUILT",
        "probabilistic_forecast_status": "NOT_PROMOTED",
        "national_uncertainty_status": "BLOCKED_PENDING_COMPARABLE_NATIONAL_MODEL_BACKTEST_OR_EXPLICIT_CALIBRATED_NATIONAL_DISTRIBUTION",
        "method": {
            "residual_space": "CLR(actual_target_territory)-CLR(v3_center_conditional_on_realized_target_national)",
            "why_condition_on_realized_national": "This intentionally removes national-shock error so territorial dispersion is calibrated around the new architecture instead of recycling the old F-1 national/regional/local shock library.",
            "anti_leakage": "Realized target national shares are used only inside retrospective error decomposition. They are never admissible prospective 2026 inputs.",
            "sampling_policy_next": "Empirical residual rows may be resampled only after the national 2026 uncertainty component and cross-fold coverage test are frozen.",
        },
        "folds": [serializable_fold(fold) for fold in folds],
        "pooled_summary": pooled,
        "empirical_error_quantiles": {
            "territory_l1": {
                "q50": float(np.quantile(territory_l1, 0.50)),
                "q80": float(np.quantile(territory_l1, 0.80)),
                "q90": float(np.quantile(territory_l1, 0.90)),
                "q95": float(np.quantile(territory_l1, 0.95)),
            },
            "absolute_party_share_error_q95": {
                party: float(np.quantile(abs_error[:, pidx], 0.95))
                for pidx, party in enumerate(PARTIES)
            },
        },
        "empirical_residual_library": {
            "observations": observations,
            "n_observations": len(observations),
            "cluster_fields": ["origin_year", "target_year", "territory_id"],
        },
        "promotion_requirements_remaining": [
            "Freeze a current pre-election national 2026 point forecast with source lineage.",
            "Calibrate or otherwise explicitly justify the national 2026 uncertainty distribution using a comparable historical/prospective protocol.",
            "Freeze the residual resampling/correlation rule and validate interval coverage by rolling-origin replay.",
            "Run >=50000 coherent elections through the existing fail-closed legal allocator and verify exactly 395 seats per draw.",
            "Only then publish party-first and seat-interval probabilities as calibrated forecast outputs.",
        ],
    }
    write_json(OUT, output)
    print(
        "UNCERTAINTY_V3_CONDITIONAL_READY="
        + json.dumps(
            {
                "output": str(OUT),
                "n_observations": len(observations),
                "fold_support": [fold["mapped_territories"] for fold in folds],
                "pooled_share_rmse": pooled["share_rmse"],
                "probabilistic_forecast_status": "NOT_PROMOTED",
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
