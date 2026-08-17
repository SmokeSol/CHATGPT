#!/usr/bin/env python3
"""Robust V2 calibration after the pre-forecast prior-predictive failure.

V2 preserves the frozen persistence mean, hierarchy, score, validation transition,
scale grid and seeds. It changes only the map from latent CLR draws to the simplex:
a small bucket floor plus deterministic empirical concentration tempering. This
prevents cross-territory transport of structural zeros from creating synthetic
near-monopolies while retaining the direction and dependence of each innovation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

import goal100_fit_uncertainty as base

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
PROTOCOL = G100 / "uncertainty_protocol_v2.json"
OUT = G100 / "uncertainty_calibration_v2.json"
V1 = G100 / "uncertainty_calibration.json"

FLOOR = 0.0005
CAP = None
RAW_INV_CLR = base.inv_clr
ROBUST_MIN = 1.0
ROBUST_MAX = 0.0


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def robust_inv_clr(value: np.ndarray) -> np.ndarray:
    global ROBUST_MIN, ROBUST_MAX
    if CAP is None:
        raise RuntimeError("robust cap not initialized")
    shares = RAW_INV_CLR(value)
    k = shares.shape[-1]
    shares = FLOOR + (1.0 - k * FLOOR) * shares
    max_share = shares.max(axis=-1)
    affected = max_share > CAP
    if np.any(affected):
        subset = shares[affected]
        lo = np.zeros(len(subset), dtype=float)
        hi = np.ones(len(subset), dtype=float)
        for _ in range(60):
            tau = (lo + hi) / 2.0
            powered = subset ** tau[:, None]
            projected = powered / powered.sum(axis=1, keepdims=True)
            above = projected.max(axis=1) > CAP
            hi[above] = tau[above]
            lo[~above] = tau[~above]
        tau = (lo + hi) / 2.0
        powered = subset ** tau[:, None]
        shares[affected] = powered / powered.sum(axis=1, keepdims=True)
    shares /= shares.sum(axis=-1, keepdims=True)
    ROBUST_MIN = min(ROBUST_MIN, float(shares.min()))
    ROBUST_MAX = max(ROBUST_MAX, float(shares.max()))
    return shares


def reset_robust_diagnostics() -> None:
    global ROBUST_MIN, ROBUST_MAX
    ROBUST_MIN = 1.0
    ROBUST_MAX = 0.0


def qualifying(candidates: list[dict], score_field: str) -> tuple[dict | None, list[float]]:
    rows = [
        candidate
        for candidate in candidates
        if candidate["coverage"]["0.8"] >= 0.75
        and candidate["coverage"]["0.95"] >= 0.90
    ]
    if not rows:
        return None, []
    return min(rows, key=lambda candidate: (candidate[score_field], candidate["scale"])), [row["scale"] for row in rows]


def main() -> None:
    global CAP
    protocol = base.load_json(PROTOCOL)
    base.require(protocol["protocol_id"] == "M26-GOAL100-UNCERTAINTY-PROTOCOL-V2", "unexpected V2 protocol ID")
    unchanged = protocol["unchanged_contract"]
    base.require(tuple(unchanged["party_buckets"]) == base.BUCKETS, "party bucket drift")
    base.require(tuple(float(value) for value in unchanged["fixed_scale_grid"]) == base.SCALE_GRID, "scale grid drift")
    base.require(int(unchanged["draws_per_candidate"]) == base.N_DRAWS, "draw count drift")
    base.require(int(unchanged["seed"]) == base.SEED, "seed drift")
    base.require(float(protocol["robust_simplex_projection"]["bucket_floor"]) == FLOOR, "floor drift")

    y11, y16, y21 = base.load_year(2011), base.load_year(2016), base.load_year(2021)
    ids = sorted(set(y11) & set(y16) & set(y21), key=int)
    base.require(len(ids) == 92, "modern common ID count != 92")
    mapping = base.build_repo_mapping(y21)
    regions = sorted({mapping[historical_id]["region"] for historical_id in ids})
    base.require(len(regions) == 12, "current region count != 12")
    region_index = {region: index for index, region in enumerate(regions)}

    observed_max = max(
        float(base.raw_share(year[historical_id]).max())
        for year in (y11, y16, y21)
        for historical_id in ids
    )
    CAP = min(0.85, observed_max + 0.05)
    base.require(CAP > 1 / len(base.BUCKETS) and CAP <= 0.85, "invalid empirical cap")
    base.inv_clr = robust_inv_clr

    train = base.decompose_transition(y11, y16, mapping, ids)
    validation_transition = base.decompose_transition(y16, y21, mapping, ids)
    z16 = {historical_id: base.clr(y16[historical_id]) for historical_id in ids}
    observed_share21 = {historical_id: base.raw_share(y21[historical_id]) for historical_id in ids}
    logit16 = {historical_id: base.logit(y16[historical_id]["turnout_rate_reported"]) for historical_id in ids}
    observed_turnout21 = {historical_id: float(y21[historical_id]["turnout_rate_reported"]) for historical_id in ids}

    vote_plan_a = base.make_random_plan(len(ids), len(regions), base.SEED)
    vote_plan_b = base.make_random_plan(len(ids), len(regions), base.SEED + 1)
    turnout_plan_a = base.make_random_plan(len(ids), len(regions), base.SEED + 2)
    turnout_plan_b = base.make_random_plan(len(ids), len(regions), base.SEED + 3)

    reset_robust_diagnostics()
    vote_candidates = [
        base.evaluate_vote_scale(
            scale,
            train,
            z16,
            observed_share21,
            ids,
            region_index,
            vote_plan_a,
            vote_plan_b,
        )
        for scale in base.SCALE_GRID
    ]
    candidate_projection_diagnostics = {
        "minimum_share_across_all_vote_candidates": ROBUST_MIN,
        "maximum_share_across_all_vote_candidates": ROBUST_MAX,
    }
    turnout_candidates = [
        base.evaluate_turnout_scale(
            scale,
            train,
            logit16,
            observed_turnout21,
            ids,
            region_index,
            turnout_plan_a,
            turnout_plan_b,
        )
        for scale in base.SCALE_GRID
    ]

    selected_vote, vote_qualifying = qualifying(vote_candidates, "mean_energy_score")
    selected_turnout, turnout_qualifying = qualifying(turnout_candidates, "mean_crps")
    coverage_pass = selected_vote is not None and selected_turnout is not None

    selected_vote_detail = None
    selected_projection = None
    if selected_vote is not None:
        reset_robust_diagnostics()
        selected_vote_detail = base.evaluate_vote_scale(
            float(selected_vote["scale"]),
            train,
            z16,
            observed_share21,
            ids,
            region_index,
            vote_plan_a,
            vote_plan_b,
            keep_territories=True,
        )
        selected_projection = {
            "minimum_share": ROBUST_MIN,
            "maximum_share": ROBUST_MAX,
            "normalization_error": selected_vote_detail["max_probability_normalization_error"],
        }
    selected_turnout_detail = None
    if selected_turnout is not None:
        selected_turnout_detail = base.evaluate_turnout_scale(
            float(selected_turnout["scale"]),
            train,
            logit16,
            observed_turnout21,
            ids,
            region_index,
            turnout_plan_a,
            turnout_plan_b,
            keep_territories=True,
        )

    projection_pass = bool(
        selected_projection
        and selected_projection["minimum_share"] >= FLOOR - 1e-12
        and selected_projection["maximum_share"] <= CAP + 1e-10
        and selected_projection["normalization_error"] < 1e-10
    )
    gate_pass = coverage_pass and projection_pass

    decompositions = [train, validation_transition]
    national_vote_support = base.symmetrized_vectors([decomposition["national_vote"] for decomposition in decompositions])
    national_turnout_support = base.symmetrized_scalars([decomposition["national_turnout"] for decomposition in decompositions])
    regional_vote_support = {
        region: base.symmetrized_vectors([decomposition["regional_vote"][region] for decomposition in decompositions])
        for region in regions
    }
    regional_turnout_support = {
        region: base.symmetrized_scalars([decomposition["regional_turnout"][region] for decomposition in decompositions])
        for region in regions
    }
    local_vote_support = base.symmetrized_vectors(
        [decomposition["local_vote"][index] for decomposition in decompositions for index in range(len(ids))]
    )
    local_turnout_support = base.symmetrized_scalars(
        [float(decomposition["local_turnout"][index]) for decomposition in decompositions for index in range(len(ids))]
    )

    support_payload = {
        "vote_scale": float(selected_vote["scale"]) if selected_vote else None,
        "turnout_scale": float(selected_turnout["scale"]) if selected_turnout else None,
        "robust_projection": {"bucket_floor": FLOOR, "max_bucket_share_cap": CAP},
        "national_vote": national_vote_support,
        "national_turnout": national_turnout_support,
        "regional_vote": regional_vote_support,
        "regional_turnout": regional_turnout_support,
        "local_vote": local_vote_support,
        "local_turnout": local_turnout_support,
    }
    support_hash = canonical_hash(support_payload)
    v1 = base.load_json(V1)

    result = {
        "schema_version": "2.0",
        "audit_id": "M26-GOAL100-UNCERTAINTY-CALIBRATION-V2",
        "protocol_id": protocol["protocol_id"],
        "as_of": "2026-08-16",
        "gate": "PASS" if gate_pass else "FAIL",
        "calibration_status": "ROBUST_AGGREGATE_COVERAGE_CALIBRATED_2026_UNTOUCHED" if gate_pass else "NOT_CALIBRATED",
        "revision_trigger": protocol["revision_trigger"],
        "robust_simplex_projection": {
            "bucket_floor": FLOOR,
            "historical_max_bucket_share": observed_max,
            "max_bucket_share_cap": CAP,
            "cap_rule": protocol["robust_simplex_projection"]["max_bucket_share_cap_rule"],
            "candidate_diagnostics": candidate_projection_diagnostics,
            "selected_candidate_diagnostics": selected_projection,
            "pass": projection_pass,
        },
        "temporal_hindcast": {
            "fit": "2011_TO_2016_ONLY",
            "validation": "2016_TO_2021",
            "draws_per_candidate": base.N_DRAWS,
            "seed_manifest": {
                "vote_A": base.SEED,
                "vote_B": base.SEED + 1,
                "turnout_A": base.SEED + 2,
                "turnout_B": base.SEED + 3,
            },
            "vote_candidates": vote_candidates,
            "turnout_candidates": turnout_candidates,
            "selected_vote": selected_vote_detail,
            "selected_turnout": selected_turnout_detail,
            "vote_qualifying_scales": vote_qualifying,
            "turnout_qualifying_scales": turnout_qualifying,
            "coverage_thresholds": {"coverage80": 0.75, "coverage95": 0.90},
            "coverage_pass": coverage_pass,
        },
        "V1_comparison_preserved": {
            "artifact": "morocco26/data/goal100/uncertainty_calibration.json",
            "V1_gate": v1["gate"],
            "V1_vote_scale": v1["final_all_pre2026_component_library"]["selected_vote_scale"],
            "V1_turnout_scale": v1["final_all_pre2026_component_library"]["selected_turnout_scale"],
            "V1_vote_energy": v1["temporal_hindcast"]["selected_vote"]["mean_energy_score"],
            "V1_turnout_crps": v1["temporal_hindcast"]["selected_turnout"]["mean_crps"],
            "V1_prior_predictive_legal_gate": "FAIL",
        },
        "hierarchical_decomposition": {
            "region_kappa": base.KAPPA,
            "free_territorial_covariance_parameters": 0,
            "turnout_vote_cross_correlation": 0.0,
            "training_region_meta": train["region_meta"],
            "validation_transition_region_meta": validation_transition["region_meta"],
        },
        "final_all_pre2026_component_library": {
            "selected_vote_scale": float(selected_vote["scale"]) if selected_vote else None,
            "selected_turnout_scale": float(selected_turnout["scale"]) if selected_turnout else None,
            "robust_projection": {"bucket_floor": FLOOR, "max_bucket_share_cap": CAP},
            "support_sha256": support_hash,
            "national_vote_support": national_vote_support,
            "national_turnout_support": national_turnout_support,
            "regional_vote_support": regional_vote_support,
            "regional_turnout_support": regional_turnout_support,
            "local_vote_support": local_vote_support,
            "local_turnout_support": local_turnout_support,
            "support_sizes": {
                "national_vote": len(national_vote_support),
                "national_turnout": len(national_turnout_support),
                "regional_vote_each": {region: len(values) for region, values in regional_vote_support.items()},
                "regional_turnout_each": {region: len(values) for region, values in regional_turnout_support.items()},
                "local_vote": len(local_vote_support),
                "local_turnout": len(local_turnout_support),
            },
            "effective_vote_support_rank": {
                "national": base.matrix_rank(national_vote_support),
                "local": base.matrix_rank(local_vote_support),
            },
            "territory_order": [mapping[historical_id]["constituency_id"] for historical_id in ids],
            "historical_id_order": ids,
            "region_order": regions,
            "region_by_territory": [mapping[historical_id]["region"] for historical_id in ids],
        },
        "legal_list_availability_boundary": protocol["legal_list_availability_boundary"],
        "limitations": [
            "V2 was introduced after a prior-predictive legal-feasibility failure and before any forecast output; V1 and both failed runs remain preserved.",
            "The robust cap bounds transported latent shocks and therefore changes the predictive family; 2026 remains its first prospective test.",
            "Only aggregate componentwise coverage thresholds govern selection; party-level historical coverage remains published.",
            "The national innovation support remains low-rank because only two modern transitions exist.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "historical_max": observed_max,
                "cap": CAP,
                "floor": FLOOR,
                "vote_scale": selected_vote["scale"] if selected_vote else None,
                "vote_energy": selected_vote["mean_energy_score"] if selected_vote else None,
                "vote_coverage80": selected_vote["coverage"]["0.8"] if selected_vote else None,
                "vote_coverage95": selected_vote["coverage"]["0.95"] if selected_vote else None,
                "turnout_scale": selected_turnout["scale"] if selected_turnout else None,
                "turnout_crps": selected_turnout["mean_crps"] if selected_turnout else None,
                "turnout_coverage80": selected_turnout["coverage"]["0.8"] if selected_turnout else None,
                "turnout_coverage95": selected_turnout["coverage"]["0.95"] if selected_turnout else None,
                "selected_min_share": selected_projection["minimum_share"] if selected_projection else None,
                "selected_max_share": selected_projection["maximum_share"] if selected_projection else None,
                "support_hash": support_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0 if gate_pass else 3)


if __name__ == "__main__":
    main()
