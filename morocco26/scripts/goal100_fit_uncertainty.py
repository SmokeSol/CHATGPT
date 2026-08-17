#!/usr/bin/env python3
"""Fit and calibrate the Goal100 hierarchical uncertainty layer.

The mean model is the frozen persistence-first B*. This script calibrates only the
predictive innovation distribution under the already-frozen uncertainty protocol.
It publishes the untouched scale-1 temporal hindcast, every fixed scale candidate,
the deterministic scale selection, and the final all-pre-2026 empirical component
libraries. It never estimates a free 92x92 territorial covariance matrix.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "goal100" / "historical"
G75 = ROOT / "data" / "goal75"
G100 = ROOT / "data" / "goal100"
PROTOCOL = G100 / "uncertainty_protocol_v1.json"
OUT = G100 / "uncertainty_calibration.json"

CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
BUCKETS = (*CORE, "OTHER")
EPS_VOTES = 0.5
KAPPA = 5.0
N_DRAWS = 8192
SEED = 26092341
SCALE_GRID = (0.75, 1.0, 1.25, 1.5, 2.0, 2.5)
COVERAGE_LEVELS = (0.50, 0.80, 0.95)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"UNCERTAINTY_CALIBRATION_FAIL: {message}")


def canonical_json_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_year(year: int) -> dict[str, dict]:
    data = load_json(HIST / f"tafra_legislative_{year}_canonical.json")
    rows = [row for row in data["rows"] if norm(row.get("list_type")) == "locale"]
    result = {str(row["id_constituency"]): row for row in rows}
    require(len(result) == 92, f"{year} local row count {len(result)} != 92")
    return result


def build_repo_mapping(rows: dict[str, dict]) -> dict[str, dict]:
    closure = load_json(G75 / "local_92_closure_v3.json")["rows"]
    by_name = {norm(row["tafra_name"]): row for row in closure}
    require(len(by_name) == 92, "closure TAFRA names are not unique")
    mapping = {}
    used = set()
    for historical_id, row in rows.items():
        key = norm(row["constituency"])
        target = by_name.get(key)
        if target is None:
            compact = key.replace(" ", "")
            candidates = [candidate for name, candidate in by_name.items() if name.replace(" ", "") == compact]
            require(len(candidates) == 1, f"cannot map historical constituency {row['constituency']}")
            target = candidates[0]
        require(target["constituency_id"] not in used, f"repo row reused: {target['constituency_id']}")
        used.add(target["constituency_id"])
        mapping[historical_id] = target
    require(len(mapping) == 92 and len(used) == 92, "historical/repo mapping coverage != 92")
    return mapping


def bucket_counts(row: dict) -> np.ndarray:
    raw = row.get("votes", {})
    values = [float(raw.get(party, 0) or 0) for party in CORE]
    values.append(sum(float(value or 0) for party, value in raw.items() if party not in CORE))
    array = np.asarray(values, dtype=float)
    require(np.all(array >= 0) and array.sum() > 0, f"invalid vote vector {row.get('id_constituency')}")
    return array


def raw_share(row: dict) -> np.ndarray:
    values = bucket_counts(row)
    return values / values.sum()


def clr(row: dict) -> np.ndarray:
    values = bucket_counts(row) + EPS_VOTES
    share = values / values.sum()
    log_share = np.log(share)
    return log_share - log_share.mean()


def centre_clr(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    return array - array.mean(axis=-1, keepdims=True)


def inv_clr(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    array = array - array.max(axis=-1, keepdims=True)
    exp = np.exp(array)
    return exp / exp.sum(axis=-1, keepdims=True)


def logit(value: float) -> float:
    clipped = min(max(float(value), 1e-6), 1 - 1e-6)
    return math.log(clipped / (1 - clipped))


def sigmoid(value: np.ndarray) -> np.ndarray:
    array = np.asarray(value, dtype=float)
    return 1.0 / (1.0 + np.exp(-array))


def energy_score(samples: np.ndarray, observed: np.ndarray, pairs: np.ndarray) -> float:
    sample_root = np.sqrt(np.clip(samples, 0, 1))
    pair_root = np.sqrt(np.clip(pairs, 0, 1))
    observed_root = np.sqrt(np.clip(observed, 0, 1))
    return float(
        np.linalg.norm(sample_root - observed_root, axis=1).mean()
        - 0.5 * np.linalg.norm(sample_root - pair_root, axis=1).mean()
    )


def crps(samples: np.ndarray, observed: float, pairs: np.ndarray) -> float:
    return float(np.abs(samples - observed).mean() - 0.5 * np.abs(samples - pairs).mean())


def interval_hit(samples: np.ndarray, observed: np.ndarray | float, level: float) -> np.ndarray:
    alpha = (1 - level) / 2
    lower = np.quantile(samples, alpha, axis=0)
    upper = np.quantile(samples, 1 - alpha, axis=0)
    return (np.asarray(observed) >= lower) & (np.asarray(observed) <= upper)


def interval_width(samples: np.ndarray, level: float) -> np.ndarray:
    alpha = (1 - level) / 2
    return np.quantile(samples, 1 - alpha, axis=0) - np.quantile(samples, alpha, axis=0)


def decompose_transition(
    source: dict[str, dict],
    target: dict[str, dict],
    mapping: dict[str, dict],
    ids: list[str],
) -> dict:
    vote_delta = np.stack([centre_clr(clr(target[historical_id]) - clr(source[historical_id])) for historical_id in ids])
    turnout_delta = np.asarray(
        [
            logit(target[historical_id]["turnout_rate_reported"])
            - logit(source[historical_id]["turnout_rate_reported"])
            for historical_id in ids
        ],
        dtype=float,
    )
    national_vote = centre_clr(vote_delta.mean(axis=0))
    national_turnout = float(turnout_delta.mean())

    regions = [mapping[historical_id]["region"] for historical_id in ids]
    unique_regions = sorted(set(regions))
    require(len(unique_regions) == 12, "transition does not map to 12 current regions")

    regional_vote = {}
    regional_turnout = {}
    region_meta = {}
    for region in unique_regions:
        indices = [index for index, value in enumerate(regions) if value == region]
        weight = len(indices) / (len(indices) + KAPPA)
        raw_vote = centre_clr((vote_delta[indices] - national_vote).mean(axis=0))
        raw_turnout = float((turnout_delta[indices] - national_turnout).mean())
        regional_vote[region] = centre_clr(weight * raw_vote)
        regional_turnout[region] = weight * raw_turnout
        region_meta[region] = {
            "territories": len(indices),
            "shrinkage_weight": weight,
        }

    local_vote = np.stack(
        [
            centre_clr(vote_delta[index] - national_vote - regional_vote[regions[index]])
            for index in range(len(ids))
        ]
    )
    local_turnout = np.asarray(
        [
            turnout_delta[index] - national_turnout - regional_turnout[regions[index]]
            for index in range(len(ids))
        ],
        dtype=float,
    )
    reconstructed_vote = np.stack(
        [national_vote + regional_vote[regions[index]] + local_vote[index] for index in range(len(ids))]
    )
    reconstructed_turnout = np.asarray(
        [national_turnout + regional_turnout[regions[index]] + local_turnout[index] for index in range(len(ids))]
    )
    require(float(np.max(np.abs(reconstructed_vote - vote_delta))) < 1e-10, "vote hierarchy reconstruction failed")
    require(float(np.max(np.abs(reconstructed_turnout - turnout_delta))) < 1e-10, "turnout hierarchy reconstruction failed")

    return {
        "national_vote": national_vote,
        "national_turnout": national_turnout,
        "regional_vote": regional_vote,
        "regional_turnout": regional_turnout,
        "local_vote": local_vote,
        "local_turnout": local_turnout,
        "regions": regions,
        "region_meta": region_meta,
        "vote_delta": vote_delta,
        "turnout_delta": turnout_delta,
    }


def make_random_plan(n_territories: int, n_regions: int, seed: int) -> dict:
    rng = np.random.default_rng(seed)
    return {
        "national_sign": rng.choice(np.array([-1.0, 1.0]), size=N_DRAWS),
        "regional_sign": rng.choice(np.array([-1.0, 1.0]), size=(N_DRAWS, n_regions)),
        "local_index": rng.integers(0, n_territories, size=(N_DRAWS, n_territories), dtype=np.int16),
        "local_sign": rng.choice(np.array([-1.0, 1.0]), size=(N_DRAWS, n_territories)),
    }


def evaluate_vote_scale(
    scale: float,
    decomposition: dict,
    z_source: dict[str, np.ndarray],
    observed: dict[str, np.ndarray],
    ids: list[str],
    region_index: dict[str, int],
    plan_a: dict,
    plan_b: dict,
    keep_territories: bool = False,
) -> dict:
    national = decomposition["national_vote"]
    regional = decomposition["regional_vote"]
    local = decomposition["local_vote"]
    regions = decomposition["regions"]
    scores = []
    rmse = []
    coverage = {level: [] for level in COVERAGE_LEVELS}
    widths = {level: [] for level in COVERAGE_LEVELS}
    party_hits = {level: {bucket: [] for bucket in BUCKETS} for level in COVERAGE_LEVELS}
    territory_rows = []
    max_probability_error = 0.0

    for territory_index, historical_id in enumerate(ids):
        region = regions[territory_index]
        ridx = region_index[region]
        base_a = (
            plan_a["national_sign"][:, None] * national[None, :]
            + plan_a["regional_sign"][:, ridx, None] * regional[region][None, :]
            + plan_a["local_sign"][:, territory_index, None]
            * local[plan_a["local_index"][:, territory_index]]
        )
        base_b = (
            plan_b["national_sign"][:, None] * national[None, :]
            + plan_b["regional_sign"][:, ridx, None] * regional[region][None, :]
            + plan_b["local_sign"][:, territory_index, None]
            * local[plan_b["local_index"][:, territory_index]]
        )
        samples = inv_clr(z_source[historical_id][None, :] + scale * base_a)
        pairs = inv_clr(z_source[historical_id][None, :] + scale * base_b)
        obs = observed[historical_id]
        max_probability_error = max(
            max_probability_error,
            float(np.max(np.abs(samples.sum(axis=1) - 1))),
            float(np.max(np.abs(pairs.sum(axis=1) - 1))),
        )
        score = energy_score(samples, obs, pairs)
        mean_prediction = samples.mean(axis=0)
        territory_rmse = float(np.sqrt(np.mean((mean_prediction - obs) ** 2)))
        scores.append(score)
        rmse.append(territory_rmse)
        row_coverage = {}
        for level in COVERAGE_LEVELS:
            hits = interval_hit(samples, obs, level)
            coverage[level].extend(bool(value) for value in hits)
            width = interval_width(samples, level)
            widths[level].extend(float(value) for value in width)
            row_coverage[str(level)] = float(np.mean(hits))
            for bucket_index, bucket in enumerate(BUCKETS):
                party_hits[level][bucket].append(bool(hits[bucket_index]))
        if keep_territories:
            territory_rows.append(
                {
                    "historical_id": historical_id,
                    "region": region,
                    "energy_score": score,
                    "mean_share_rmse": territory_rmse,
                    "coverage": row_coverage,
                }
            )

    result = {
        "scale": scale,
        "mean_energy_score": float(np.mean(scores)),
        "median_energy_score": float(np.median(scores)),
        "mean_share_rmse": float(np.mean(rmse)),
        "coverage": {str(level): float(np.mean(coverage[level])) for level in COVERAGE_LEVELS},
        "mean_interval_width": {str(level): float(np.mean(widths[level])) for level in COVERAGE_LEVELS},
        "coverage_by_party": {
            str(level): {bucket: float(np.mean(values)) for bucket, values in party_hits[level].items()}
            for level in COVERAGE_LEVELS
        },
        "max_probability_normalization_error": max_probability_error,
    }
    if keep_territories:
        result["territories"] = territory_rows
    return result


def evaluate_turnout_scale(
    scale: float,
    decomposition: dict,
    source_logit: dict[str, float],
    observed: dict[str, float],
    ids: list[str],
    region_index: dict[str, int],
    plan_a: dict,
    plan_b: dict,
    keep_territories: bool = False,
) -> dict:
    national = decomposition["national_turnout"]
    regional = decomposition["regional_turnout"]
    local = decomposition["local_turnout"]
    regions = decomposition["regions"]
    scores = []
    errors = []
    squared = []
    coverage = {level: [] for level in COVERAGE_LEVELS}
    widths = {level: [] for level in COVERAGE_LEVELS}
    territory_rows = []

    for territory_index, historical_id in enumerate(ids):
        region = regions[territory_index]
        ridx = region_index[region]
        base_a = (
            plan_a["national_sign"] * national
            + plan_a["regional_sign"][:, ridx] * regional[region]
            + plan_a["local_sign"][:, territory_index]
            * local[plan_a["local_index"][:, territory_index]]
        )
        base_b = (
            plan_b["national_sign"] * national
            + plan_b["regional_sign"][:, ridx] * regional[region]
            + plan_b["local_sign"][:, territory_index]
            * local[plan_b["local_index"][:, territory_index]]
        )
        samples = sigmoid(source_logit[historical_id] + scale * base_a)
        pairs = sigmoid(source_logit[historical_id] + scale * base_b)
        obs = observed[historical_id]
        score = crps(samples, obs, pairs)
        mean_prediction = float(samples.mean())
        error = abs(mean_prediction - obs)
        scores.append(score)
        errors.append(error)
        squared.append((mean_prediction - obs) ** 2)
        row_coverage = {}
        for level in COVERAGE_LEVELS:
            hit = bool(interval_hit(samples, obs, level))
            coverage[level].append(hit)
            widths[level].append(float(interval_width(samples, level)))
            row_coverage[str(level)] = hit
        if keep_territories:
            territory_rows.append(
                {
                    "historical_id": historical_id,
                    "region": region,
                    "crps": score,
                    "absolute_error": error,
                    "coverage": row_coverage,
                }
            )

    result = {
        "scale": scale,
        "mean_crps": float(np.mean(scores)),
        "median_crps": float(np.median(scores)),
        "mae": float(np.mean(errors)),
        "rmse": float(math.sqrt(np.mean(squared))),
        "coverage": {str(level): float(np.mean(coverage[level])) for level in COVERAGE_LEVELS},
        "mean_interval_width": {str(level): float(np.mean(widths[level])) for level in COVERAGE_LEVELS},
    }
    if keep_territories:
        result["territories"] = territory_rows
    return result


def choose_scale(candidates: list[dict], score_field: str) -> tuple[dict, dict]:
    qualifying = [
        candidate
        for candidate in candidates
        if candidate["coverage"]["0.8"] >= 0.75 and candidate["coverage"]["0.95"] >= 0.90
    ]
    if qualifying:
        selected = min(qualifying, key=lambda candidate: (candidate[score_field], candidate["scale"]))
        return selected, {
            "mode": "QUALIFYING_COVERAGE_THEN_PROPER_SCORE",
            "qualifying_scales": [candidate["scale"] for candidate in qualifying],
        }
    for candidate in candidates:
        candidate["coverage_deficit"] = (
            max(0.0, 0.75 - candidate["coverage"]["0.8"])
            + max(0.0, 0.90 - candidate["coverage"]["0.95"])
        )
    selected = min(candidates, key=lambda candidate: (candidate["coverage_deficit"], candidate[score_field], candidate["scale"]))
    return selected, {
        "mode": "MINIMUM_COVERAGE_DEFICIT_FALLBACK",
        "qualifying_scales": [],
    }


def symmetrized_vectors(vectors: list[np.ndarray]) -> list[list[float]]:
    support = []
    for vector in vectors:
        centred = centre_clr(np.asarray(vector, dtype=float))
        support.append([float(value) for value in centred])
        support.append([float(value) for value in -centred])
    return support


def symmetrized_scalars(values: list[float]) -> list[float]:
    support = []
    for value in values:
        support.extend([float(value), float(-value)])
    return support


def matrix_rank(support: list[list[float]]) -> int:
    return int(np.linalg.matrix_rank(np.asarray(support, dtype=float), tol=1e-10))


def main() -> None:
    protocol = load_json(PROTOCOL)
    require(protocol["protocol_id"] == "M26-GOAL100-UNCERTAINTY-PROTOCOL-V1", "unexpected protocol ID")
    require(tuple(protocol["party_buckets"]) == BUCKETS, "party bucket protocol drift")
    require(tuple(float(value) for value in protocol["temporal_calibration"]["fixed_scale_grid"]) == SCALE_GRID, "scale grid protocol drift")
    require(int(protocol["temporal_calibration"]["draws_per_candidate"]) == N_DRAWS, "draw count protocol drift")
    require(int(protocol["temporal_calibration"]["seed"]) == SEED, "seed protocol drift")

    y11, y16, y21 = load_year(2011), load_year(2016), load_year(2021)
    ids = sorted(set(y11) & set(y16) & set(y21), key=int)
    require(len(ids) == 92, "modern common ID count != 92")
    mapping = build_repo_mapping(y21)
    regions = sorted({mapping[historical_id]["region"] for historical_id in ids})
    require(len(regions) == 12, "current region count != 12")
    region_index = {region: index for index, region in enumerate(regions)}

    train = decompose_transition(y11, y16, mapping, ids)
    validation_transition = decompose_transition(y16, y21, mapping, ids)

    z16 = {historical_id: clr(y16[historical_id]) for historical_id in ids}
    observed_share21 = {historical_id: raw_share(y21[historical_id]) for historical_id in ids}
    logit16 = {historical_id: logit(y16[historical_id]["turnout_rate_reported"]) for historical_id in ids}
    observed_turnout21 = {historical_id: float(y21[historical_id]["turnout_rate_reported"]) for historical_id in ids}

    vote_plan_a = make_random_plan(len(ids), len(regions), SEED)
    vote_plan_b = make_random_plan(len(ids), len(regions), SEED + 1)
    turnout_plan_a = make_random_plan(len(ids), len(regions), SEED + 2)
    turnout_plan_b = make_random_plan(len(ids), len(regions), SEED + 3)

    vote_candidates = [
        evaluate_vote_scale(
            scale,
            train,
            z16,
            observed_share21,
            ids,
            region_index,
            vote_plan_a,
            vote_plan_b,
        )
        for scale in SCALE_GRID
    ]
    turnout_candidates = [
        evaluate_turnout_scale(
            scale,
            train,
            logit16,
            observed_turnout21,
            ids,
            region_index,
            turnout_plan_a,
            turnout_plan_b,
        )
        for scale in SCALE_GRID
    ]
    selected_vote, vote_selection = choose_scale(vote_candidates, "mean_energy_score")
    selected_turnout, turnout_selection = choose_scale(turnout_candidates, "mean_crps")

    # Re-evaluate selected scales with territory-level diagnostics retained.
    selected_vote_detail = evaluate_vote_scale(
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
    selected_turnout_detail = evaluate_turnout_scale(
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

    # Final libraries use all pre-2026 modern transitions after the fixed calibration rule.
    decompositions = [train, validation_transition]
    national_vote_support = symmetrized_vectors([decomposition["national_vote"] for decomposition in decompositions])
    national_turnout_support = symmetrized_scalars([decomposition["national_turnout"] for decomposition in decompositions])
    regional_vote_support = {
        region: symmetrized_vectors([decomposition["regional_vote"][region] for decomposition in decompositions])
        for region in regions
    }
    regional_turnout_support = {
        region: symmetrized_scalars([decomposition["regional_turnout"][region] for decomposition in decompositions])
        for region in regions
    }
    local_vote_support = symmetrized_vectors(
        [decomposition["local_vote"][index] for decomposition in decompositions for index in range(len(ids))]
    )
    local_turnout_support = symmetrized_scalars(
        [float(decomposition["local_turnout"][index]) for decomposition in decompositions for index in range(len(ids))]
    )

    support_payload = {
        "vote_scale": float(selected_vote["scale"]),
        "turnout_scale": float(selected_turnout["scale"]),
        "national_vote": national_vote_support,
        "national_turnout": national_turnout_support,
        "regional_vote": regional_vote_support,
        "regional_turnout": regional_turnout_support,
        "local_vote": local_vote_support,
        "local_turnout": local_turnout_support,
    }
    support_hash = canonical_json_hash(support_payload)

    all_vote_values = np.asarray(local_vote_support, dtype=float)
    all_turnout_values = np.asarray(local_turnout_support, dtype=float)
    require(np.all(np.isfinite(all_vote_values)), "final local vote support contains non-finite values")
    require(np.all(np.isfinite(all_turnout_values)), "final local turnout support contains non-finite values")
    require(float(np.max(np.abs(all_vote_values.sum(axis=1)))) < 1e-10, "final vote support is not CLR-centred")
    require(abs(float(all_vote_values.mean(axis=0).max())) < 1e-10, "symmetrized local vote support mean is not zero")
    require(abs(float(all_turnout_values.mean())) < 1e-12, "symmetrized local turnout support mean is not zero")

    vote_threshold_pass = selected_vote["coverage"]["0.8"] >= 0.75 and selected_vote["coverage"]["0.95"] >= 0.90
    turnout_threshold_pass = selected_turnout["coverage"]["0.8"] >= 0.75 and selected_turnout["coverage"]["0.95"] >= 0.90
    gate_pass = vote_threshold_pass and turnout_threshold_pass

    bstar = load_json(G100 / "bstar_hindcast_v1.json")
    result = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-UNCERTAINTY-CALIBRATION-V1",
        "protocol_id": protocol["protocol_id"],
        "as_of": "2026-08-16",
        "gate": "PASS" if gate_pass else "FAIL_COVERAGE_THRESHOLD",
        "calibration_status": "CALIBRATED_ON_PRE2026_HISTORY_2026_UNTOUCHED" if gate_pass else "NOT_CALIBRATED",
        "epistemic_boundary": protocol["epistemic_statement"],
        "temporal_hindcast": {
            "fit": "2011_TO_2016_ONLY",
            "validation": "2016_TO_2021",
            "draws_per_candidate": N_DRAWS,
            "seed_manifest": {
                "vote_A": SEED,
                "vote_B": SEED + 1,
                "turnout_A": SEED + 2,
                "turnout_B": SEED + 3,
            },
            "vote_candidates": vote_candidates,
            "turnout_candidates": turnout_candidates,
            "scale_1_retained": {
                "vote": next(candidate for candidate in vote_candidates if candidate["scale"] == 1.0),
                "turnout": next(candidate for candidate in turnout_candidates if candidate["scale"] == 1.0),
            },
            "selected_vote": selected_vote_detail,
            "selected_turnout": selected_turnout_detail,
            "vote_selection": vote_selection,
            "turnout_selection": turnout_selection,
            "coverage_thresholds": {"coverage80": 0.75, "coverage95": 0.90},
            "vote_threshold_pass": vote_threshold_pass,
            "turnout_threshold_pass": turnout_threshold_pass,
            "Bstar_flat_residual_context": {
                "vote_energy_score": bstar["vote_models"]["V0_PERSIST"]["mean_energy_score"],
                "turnout_crps": bstar["turnout_models"]["T0_PERSIST"]["mean_crps"],
                "role": "historical non-hierarchical context only; the frozen hierarchical calibration rule governs F-1 coherence",
            },
        },
        "hierarchical_decomposition": {
            "region_kappa": KAPPA,
            "training_region_meta": train["region_meta"],
            "validation_transition_region_meta": validation_transition["region_meta"],
            "free_territorial_covariance_parameters": 0,
            "turnout_vote_cross_correlation": 0.0,
            "national_vote_component_norms": [
                float(np.linalg.norm(decomposition["national_vote"])) for decomposition in decompositions
            ],
            "national_turnout_component_abs": [
                abs(float(decomposition["national_turnout"])) for decomposition in decompositions
            ],
            "local_vote_residual_component_sd": [
                float(value)
                for value in np.vstack([decomposition["local_vote"] for decomposition in decompositions]).std(axis=0, ddof=1)
            ],
            "local_turnout_residual_sd": float(
                np.concatenate([decomposition["local_turnout"] for decomposition in decompositions]).std(ddof=1)
            ),
        },
        "final_all_pre2026_component_library": {
            "selected_vote_scale": float(selected_vote["scale"]),
            "selected_turnout_scale": float(selected_turnout["scale"]),
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
                "national": matrix_rank(national_vote_support),
                "local": matrix_rank(local_vote_support),
            },
            "territory_order": [mapping[historical_id]["constituency_id"] for historical_id in ids],
            "historical_id_order": ids,
            "region_order": regions,
            "region_by_territory": [mapping[historical_id]["region"] for historical_id in ids],
        },
        "F_minus_1_rules": {
            "regional_ballot_bridge": protocol["regional_ballot_bridge_for_F_minus_1"],
            "minor_party_legal_disaggregation": protocol["minor_party_legal_disaggregation"],
        },
        "limitations": [
            "Only two modern territorial transitions exist, so the national support is deliberately low-rank and symmetrized rather than presented as a well-estimated full covariance.",
            "The selected scale is calibrated on 2016->2021 under a rule frozen before this execution; it is not an independent validation after selection.",
            "The 2021 regional ballot is bridged structurally because no earlier current-system regional-list ballot exists in the canonical panel.",
            "2026 is the first untouched prospective test of the post-selection calibrated uncertainty layer.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "vote_scale": selected_vote["scale"],
                "vote_energy": selected_vote["mean_energy_score"],
                "vote_coverage80": selected_vote["coverage"]["0.8"],
                "vote_coverage95": selected_vote["coverage"]["0.95"],
                "turnout_scale": selected_turnout["scale"],
                "turnout_crps": selected_turnout["mean_crps"],
                "turnout_coverage80": selected_turnout["coverage"]["0.8"],
                "turnout_coverage95": selected_turnout["coverage"]["0.95"],
                "support_hash": support_hash,
                "free_92x92_covariance": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0 if gate_pass else 3)


if __name__ == "__main__":
    main()
