#!/usr/bin/env python3
"""Run the final V1 calibrated 2026 forecast through 50,000 legal elections.

Vote uncertainty is the new validated architecture (national model + national
uncertainty + lambda=.5 + conditional geography residuals).  Only structural
N/turnout/valid-vote/list/legal mechanics are reused from certified F-1 V1.1;
its old vote uncertainty is never reused.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
SRC = ROOT / "src"
G100 = ROOT / "data" / "goal100"
LAB = G100 / "forecast_lab"
HIST = G100 / "historical"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(SRC))

import goal100_run_fminus1 as engine  # noqa: E402
import goal100_fminus1_runtime_v4 as runtime  # noqa: E402
import calibrate_uncertainty_v3 as geo  # noqa: E402


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


natunc = _load_module("m26_nat_unc_final", SCRIPTS / "calibrate_national_uncertainty_2026_v1.py")
combined = _load_module("m26_combined_final", SCRIPTS / "replay_combined_territorial_coverage_v1.py")

BUCKETS = tuple(engine.BUCKETS)
CORE = tuple(engine.CORE)
N_DRAWS = 50_000
HOUSE = 395
MAJORITY = 198
GEO_SEED = 26092854
BATCH = 500


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError("FINAL2026_FAIL: " + message)


def quantile_record(values: np.ndarray) -> dict:
    a = np.asarray(values, dtype=float)
    q = np.quantile(a, [0.025, 0.10, 0.50, 0.90, 0.975])
    return {
        "mean": float(a.mean()),
        "sd": float(a.std(ddof=1)),
        "q025": float(q[0]),
        "q10": float(q[1]),
        "median": float(q[2]),
        "q90": float(q[3]),
        "q975": float(q[4]),
    }


def geography_pool() -> np.ndarray:
    folds = [geo.fold_2007_2011(), geo.fold_direct(2011, 2016), geo.fold_direct(2016, 2021)]
    pieces = [np.asarray(f["actual"], dtype=float) - np.asarray(f["center"], dtype=float) for f in folds]
    pool = np.vstack(pieces)
    require(pool.shape == (241, 9), f"geography pool shape {pool.shape} != (241,9)")
    require(np.all(np.isfinite(pool)), "non-finite geography residual")
    require(float(np.max(np.abs(pool.sum(axis=1)))) < 1e-9, "geography share residual does not sum to zero")
    return pool


def ordered_2021(library: dict) -> tuple[list[str], list[str], np.ndarray, np.ndarray, dict[str, dict], dict[str, dict]]:
    y21 = engine.load_year(2021)
    y11 = engine.load_year(2011)
    mapping = engine.build_mapping(y21)
    ids = [str(x) for x in library["historical_id_order"]]
    cids = [mapping[hid]["constituency_id"] for hid in ids]
    territory_order = list(library["territory_order"])
    require(cids == territory_order, "F-1 historical-id order != territory order")
    counts = np.stack([engine.bucket_counts(y21[hid]) for hid in ids])
    weights = counts.sum(axis=1)
    shares = counts / weights[:, None]
    require(shares.shape == (92, 9), "2021 local share matrix shape drift")
    return ids, territory_order, shares, weights, y21, y11


def generate_vote_draws(origin_share: np.ndarray, origin_weight: np.ndarray) -> tuple[np.ndarray, np.ndarray, dict]:
    selection = load_json(LAB / "national_forecast_2026_v1.json")
    require(selection["model"] == "PREVIOUS_NATIONAL_PERSISTENCE", "national point model drift")
    center = np.asarray([selection["point_share"][p] for p in BUCKETS], dtype=float)
    national_cal = natunc.run(coverage_draws=20_000, prospective_draws=1_000)
    require(national_cal["prequential"]["status"] == "PASS", "national uncertainty no longer passes")
    scale = float(national_cal["prospective_2026"]["scale"])
    national = natunc.draw_national(center, scale, N_DRAWS, 26092352, prospective_floor=True)
    require(national.shape == (N_DRAWS, 9), "national draw shape drift")
    require(float(np.max(np.abs(national.sum(axis=1) - 1.0))) < 1e-10, "national draws not normalized")
    require(float(national.min()) > 0, "national draw numerical floor failed")

    pool = geography_pool()
    rng = np.random.default_rng(GEO_SEED)
    local = np.empty((N_DRAWS, 92, 9), dtype=np.float32)
    max_error = 0.0
    max_iterations = 0
    for start in range(0, N_DRAWS, BATCH):
        stop = min(N_DRAWS, start + BATCH)
        targets = national[start:stop]
        centers, it1, e1 = combined.centers_for_targets(origin_share, origin_weight, targets)
        idx = rng.integers(0, len(pool), size=(stop - start, 92))
        candidate = combined.normalize_rows_batch(np.maximum(centers + pool[idx], combined.RAKE_FLOOR))
        final, it2, e2 = combined.rake_batch(candidate, origin_weight, targets)
        local[start:stop] = final.astype(np.float32)
        max_error = max(max_error, float(e1), float(e2))
        max_iterations = max(max_iterations, int(it1), int(it2))
    check = np.einsum("t,btp->bp", origin_weight / origin_weight.sum(), local.astype(np.float64), optimize=True)
    aggregate_error = float(np.max(np.abs(check - national)))
    require(aggregate_error <= 2e-8, f"stored local draws drift from national target: {aggregate_error}")
    return national, local, {
        "national_scale": scale,
        "national_seed": 26092352,
        "geography_seed": GEO_SEED,
        "geography_residual_rows": int(len(pool)),
        "max_rake_error_runtime": max_error,
        "max_rake_iterations": max_iterations,
        "max_stored_weighted_aggregate_error": aggregate_error,
    }


def regional_rows_2021(region_order: list[str]) -> dict[str, dict]:
    canonical = load_json(HIST / "tafra_legislative_2021_canonical.json")
    rows = [r for r in canonical["rows"] if engine.norm(r.get("list_type")) == "regionale"]
    require(len(rows) == 12, "regional 2021 rows != 12")
    out = {}
    for row in rows:
        region = engine.match_region(row.get("region") or row.get("constituency"), region_order)
        require(region not in out, f"duplicate regional row {region}")
        out[region] = row
    require(set(out) == set(region_order), "regional row coverage drift")
    return out


def regional_vote_bridge(
    local_draws: np.ndarray,
    origin_share: np.ndarray,
    origin_weight: np.ndarray,
    region_by_territory: list[str],
    region_order: list[str],
    regional_rows: dict[str, dict],
) -> tuple[dict[str, np.ndarray], dict]:
    result = {}
    diagnostics = {}
    for region in region_order:
        idx = np.asarray([i for i, r in enumerate(region_by_territory) if r == region], dtype=int)
        require(len(idx) > 0, f"no local territories in {region}")
        w = origin_weight[idx].astype(float)
        w /= w.sum()
        local_base = np.einsum("t,tp->p", w, origin_share[idx], optimize=True)
        local_sim = np.einsum("t,btp->bp", w, local_draws[:, idx, :].astype(np.float64), optimize=True)
        regional_counts = engine.bucket_counts(regional_rows[region])
        regional_base = regional_counts / regional_counts.sum()
        raw = regional_base[None, :] * (local_sim / np.maximum(local_base[None, :], 1e-8))
        raw = np.maximum(raw, 1e-12)
        shares = raw / raw.sum(axis=1, keepdims=True)
        require(np.all(np.isfinite(shares)) and float(np.max(np.abs(shares.sum(axis=1) - 1))) < 1e-10, f"regional bridge invalid {region}")
        result[region] = shares
        diagnostics[region] = {
            "territories": int(len(idx)),
            "local_2021": {p: float(local_base[j]) for j, p in enumerate(BUCKETS)},
            "regional_2021": {p: float(regional_base[j]) for j, p in enumerate(BUCKETS)},
        }
    return result, diagnostics


def aggregate_legal(diagnostics: list[dict]) -> dict:
    return {
        "contest_count": len(diagnostics),
        "contest_draws": len(diagnostics) * N_DRAWS,
        "statutory_age_prior_contest_draws": sum(int(d["statutory_age_prior_draws"]) for d in diagnostics),
        "statutory_age_prior_seats_marginalized": sum(int(d["statutory_age_prior_seats_marginalized"]) for d in diagnostics),
        "statutory_age_prior_max_group_size": max(int(d["statutory_age_prior_max_group_size"]) for d in diagnostics),
        "unique_list_threshold_failures": sum(int(d["unique_list_threshold_failures"]) for d in diagnostics),
        "unfilled_seat_exceptions": sum(int(d["unfilled_seat_exceptions"]) for d in diagnostics),
        "unresolved_after_age_prior": sum(int(d["unresolved_after_age_prior"]) for d in diagnostics),
        "zero_vote_eligible_lists": sum(int(d["zero_vote_eligible_lists"]) for d in diagnostics),
        "scalar_complete_spot_checks": sum(int(d["scalar_complete_spot_checks"]) for d in diagnostics),
        "scalar_binding_tie_spot_checks": sum(int(d["scalar_binding_tie_spot_checks"]) for d in diagnostics),
        "active_bucket_min_share": min(float(d["active_bucket_min_share"]) for d in diagnostics),
        "active_bucket_max_share": max(float(d["active_bucket_max_share"]) for d in diagnostics),
        "active_list_count_min": min(int(d["active_list_count"]) for d in diagnostics),
        "active_list_count_max": max(int(d["active_list_count"]) for d in diagnostics),
    }


def run() -> dict:
    contract = load_json(LAB / "final_probabilistic_forecast_2026_contract_v1.json")
    require(contract["freeze_status"] == "FROZEN_BEFORE_FINAL_50000_SEAT_SIMULATION", "final contract not frozen")
    protocol = load_json(G100 / "fminus1_protocol_v1_1.json")
    uncertainty_v2 = load_json(G100 / "uncertainty_calibration_v2.json")
    local_n = load_json(G100 / "local_N_posterior.json")
    require(protocol["protocol_id"] == "M26-GOAL100-FMINUS1-PROTOCOL-V1.1", "F-1 legal protocol drift")
    require(uncertainty_v2["gate"] == "PASS", "F-1 V2 structural uncertainty artifact no longer PASS")
    require(local_n["gate"] == "PASS", "N92 posterior no longer PASS")
    library = uncertainty_v2["final_all_pre2026_component_library"]
    require(library["support_sha256"] == protocol["uncertainty"]["support_sha256"], "F-1 structural support hash drift")

    runtime.AGE_RNG = np.random.default_rng(int(protocol["monte_carlo"]["seed_manifest"]["statutory_age_prior"]))
    ids, territory_order, origin_share, origin_weight, y21, y11 = ordered_2021(library)
    mapping = engine.build_mapping(y21)
    region_order = list(library["region_order"])
    region_by_territory = list(library["region_by_territory"])
    require(len(region_order) == 12 and len(region_by_territory) == 92, "region support shape drift")
    require([mapping[hid]["region"] for hid in ids] == region_by_territory, "region assignment drift")

    national_vote_draws, local_share_draws, vote_diag = generate_vote_draws(origin_share, origin_weight)
    regional_rows = regional_rows_2021(region_order)
    regional_share_draws, regional_bridge_diag = regional_vote_bridge(
        local_share_draws, origin_share, origin_weight, region_by_territory, region_order, regional_rows
    )

    N_draws, N_diag = engine.generate_N_draws(protocol, local_n, territory_order, region_by_territory, region_order)
    require(N_draws.shape == (N_DRAWS, 92), "N92 draw shape drift")
    require(np.all(N_draws > 0) and np.all(N_draws.sum(axis=1) == 15_801_162), "N92 exact-total invariant failed")

    seeds = {k: int(v) for k, v in protocol["monte_carlo"]["seed_manifest"].items()}
    turnout_scale = float(library["selected_turnout_scale"])
    national_turnout_support = np.asarray(library["national_turnout_support"], dtype=float)
    regional_turnout_support = {r: np.asarray(v, dtype=float) for r, v in library["regional_turnout_support"].items()}
    local_turnout_support = np.asarray(library["local_turnout_support"], dtype=float)
    rng_nt = np.random.default_rng(seeds["national_turnout"])
    rng_rt = np.random.default_rng(seeds["regional_turnout"])
    rng_lt = np.random.default_rng(seeds["local_turnout"])
    rng_round = np.random.default_rng(seeds["vote_rounding"])
    nt = national_turnout_support[rng_nt.integers(0, len(national_turnout_support), size=N_DRAWS)]
    rt = np.empty((N_DRAWS, len(region_order)), dtype=float)
    for ridx, region in enumerate(region_order):
        support = regional_turnout_support[region]
        rt[:, ridx] = support[rng_rt.integers(0, len(support), size=N_DRAWS)]
    lt_idx = rng_lt.integers(0, len(local_turnout_support), size=(N_DRAWS, 92), dtype=np.int16)

    valid_fraction, valid_fraction_diag = engine.valid_fraction_model(y11, ids)
    region_index = {r: i for i, r in enumerate(region_order)}
    region_local_valid = np.zeros((N_DRAWS, len(region_order)), dtype=np.int64)
    national_seats = np.zeros((N_DRAWS, len(BUCKETS)), dtype=np.int16)
    local_outputs = []
    legal_diagnostics = []

    for tidx, hid in enumerate(ids):
        repo = mapping[hid]
        ridx = region_index[region_by_territory[tidx]]
        turnout_latent = turnout_scale * (nt + rt[:, ridx] + local_turnout_support[lt_idx[:, tidx]])
        turnout = engine.sigmoid(engine.logit(y21[hid]["turnout_rate_reported"]) + turnout_latent)
        registered = N_draws[:, tidx]
        valid = np.floor(registered * turnout * valid_fraction[hid]).astype(np.int64)
        valid = np.clip(valid, 1, registered)
        region_local_valid[:, ridx] += valid
        shares = local_share_draws[:, tidx, :].astype(np.float64, copy=True)
        actual_seats, parties, diag = runtime.simulate_contest(
            shares, valid, registered, int(repo["seats"]),
            {str(p): int(v) for p, v in y21[hid]["votes"].items()}, rng_round, 0
        )
        bucket_seats = engine.bucket_seats_from_actual(actual_seats, parties)
        national_seats += bucket_seats
        legal_diagnostics.append(diag)
        local_outputs.append({
            "constituency_id": repo["constituency_id"],
            "name": repo["name"],
            "region": repo["region"],
            "magnitude": int(repo["seats"]),
            "expected_bucket_seats": {p: float(bucket_seats[:, j].mean()) for j, p in enumerate(BUCKETS)},
            "turnout": quantile_record(turnout),
            "registered_N": quantile_record(registered),
            "valid_votes": quantile_record(valid),
            "statutory_age_prior_draws": int(diag["statutory_age_prior_draws"]),
        })

    local_observed_valid_by_region = defaultdict(int)
    for hid in ids:
        local_observed_valid_by_region[mapping[hid]["region"]] += sum(int(v) for v in y21[hid]["votes"].values())
    raw_ratio = np.asarray([
        sum(int(v) for v in regional_rows[r]["votes"].values()) / local_observed_valid_by_region[r]
        for r in region_order
    ], dtype=float)
    p05, p95 = np.quantile(raw_ratio, [0.05, 0.95])
    regional_ratio = 0.5 * np.clip(raw_ratio, p05, p95) + 0.5

    regional_outputs = []
    for ridx, region in enumerate(region_order):
        row = regional_rows[region]
        tids = np.asarray([i for i, r in enumerate(region_by_territory) if r == region], dtype=int)
        registered = N_draws[:, tids].sum(axis=1)
        valid = np.rint(region_local_valid[:, ridx] * regional_ratio[ridx]).astype(np.int64)
        valid = np.clip(valid, 1, registered)
        shares = regional_share_draws[region].astype(np.float64, copy=True)
        actual_seats, parties, diag = runtime.simulate_contest(
            shares, valid, registered, int(row["seats"]),
            {str(p): int(v) for p, v in row["votes"].items()}, rng_round, 0
        )
        bucket_seats = engine.bucket_seats_from_actual(actual_seats, parties)
        national_seats += bucket_seats
        legal_diagnostics.append(diag)
        regional_outputs.append({
            "region": region,
            "magnitude": int(row["seats"]),
            "expected_bucket_seats": {p: float(bucket_seats[:, j].mean()) for j, p in enumerate(BUCKETS)},
            "regional_to_local_valid_vote_ratio_raw_2021": float(raw_ratio[ridx]),
            "regional_to_local_valid_vote_ratio_used": float(regional_ratio[ridx]),
            "statutory_age_prior_draws": int(diag["statutory_age_prior_draws"]),
        })

    seat_totals = national_seats.sum(axis=1)
    require(np.all(seat_totals == HOUSE), "not every election allocates exactly 395 seats")
    legal = aggregate_legal(legal_diagnostics)
    require(legal["contest_count"] == 104, "contest count !=104")
    require(legal["unique_list_threshold_failures"] == 0, "unique-list threshold failure")
    require(legal["unfilled_seat_exceptions"] == 0, "unfilled-seat exceptional allocation")
    require(legal["unresolved_after_age_prior"] == 0, "tie remains after age prior")
    require(legal["zero_vote_eligible_lists"] == 0, "eligible list received zero votes")
    legal["statutory_age_prior_rate_per_contest_draw"] = legal["statutory_age_prior_contest_draws"] / legal["contest_draws"]

    maximum = national_seats.max(axis=1)
    seat_summary = {}
    for j, p in enumerate(BUCKETS):
        values = national_seats[:, j].astype(float)
        s = quantile_record(values)
        s.update({
            "P_first_or_tied": float(np.mean(national_seats[:, j] == maximum)),
            "P_unique_first": float(np.mean((national_seats[:, j] == maximum) & ((national_seats == maximum[:, None]).sum(axis=1) == 1))),
            "P_majority_198": float(np.mean(national_seats[:, j] >= MAJORITY)),
            "mc_se_expected_seats": float(values.std(ddof=1) / math.sqrt(N_DRAWS)),
        })
        seat_summary[p] = s

    vote_summary = {p: quantile_record(national_vote_draws[:, j]) for j, p in enumerate(BUCKETS)}
    stream_hash = hashlib.sha256(np.ascontiguousarray(national_seats, dtype="<i2").tobytes()).hexdigest()
    expected_total = sum(seat_summary[p]["mean"] for p in BUCKETS)
    require(abs(expected_total - HOUSE) < 1e-10, "expected seat means do not sum to 395")

    return {
        "schema_version": "1.0",
        "forecast_id": "M26-PROBABILISTIC-FORECAST-2026-V1",
        "target_year": 2026,
        "status": "PROMOTED",
        "contract": "morocco26/data/goal100/forecast_lab/final_probabilistic_forecast_2026_contract_v1.json",
        "draws": N_DRAWS,
        "house_seats": HOUSE,
        "majority_threshold": MAJORITY,
        "party_order": list(BUCKETS),
        "national_vote_share": vote_summary,
        "national_395": {
            "bucket_seat_distribution": seat_summary,
            "seat_total_every_draw": HOUSE,
            "joint_bucket_seat_stream_sha256": stream_hash,
            "expected_seat_sum": float(expected_total),
        },
        "local_92": local_outputs,
        "regional_12": regional_outputs,
        "diagnostics": {
            "vote_generator": vote_diag,
            "registered_N": N_diag,
            "turnout_scale_reused_from_Fminus1_V1_1": turnout_scale,
            "valid_fraction_model": valid_fraction_diag,
            "regional_bridge": regional_bridge_diag,
            "regional_valid_vote_ratio_winsor_p05": float(p05),
            "regional_valid_vote_ratio_winsor_p95": float(p95),
            "legal": legal,
        },
        "upstream_validation": {
            "national_model": "PASS",
            "national_uncertainty": "PASS",
            "lambda_0_5": "PASS",
            "conditional_geography": "PASS",
            "combined_territorial_coverage": "PASS",
            "legal_current_law": "PASS"
        },
        "known_limitations": contract["mandatory_limitations"],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    result = run()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    national = result["national_395"]["bucket_seat_distribution"]
    print("FINAL_2026_FORECAST=" + json.dumps({
        "status": result["status"],
        "draws": result["draws"],
        "seat_total_every_draw": result["national_395"]["seat_total_every_draw"],
        "seat_stream_sha256": result["national_395"]["joint_bucket_seat_stream_sha256"],
        "legal": result["diagnostics"]["legal"],
        "seats": {p: {k: national[p][k] for k in ("mean", "median", "q025", "q975", "P_first_or_tied", "P_majority_198")} for p in BUCKETS},
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
