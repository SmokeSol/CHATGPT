#!/usr/bin/env python3
"""Fit the constrained 92-local registered-voter posterior for F-1.

Scientific boundary
-------------------
This script does not claim to recover official 2026 constituency-level registered
counts. It constructs a reproducible latent distribution needed by the current-law
seat allocator while local official counts are unavailable.

The posterior:
- has 92 positive integer entries in every draw;
- sums exactly to the official national total 15,801,162 in every draw;
- is centred on 2011 local registered-voter shares;
- cannot fall below observed 2021 valid-list votes locally or regionally;
- uses the exact-name 2007->2011 electorate-share drift as an empirical variance
  floor and a shrunk region/local decomposition;
- reports allocation sensitivity caused by N alone for all 92 local and 12
  regional contests under fixed 2021 vote vectors;
- stores summaries and a draw-stream hash, not millions of pseudo-official counts.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G75 = DATA / "goal75"
G100 = DATA / "goal100"
HIST = G100 / "historical"
OUT = G100 / "local_N_posterior.json"

sys.path.insert(0, str(ROOT / "src"))
from morocco26.legal_allocator_2026 import allocate_2026  # noqa: E402

NATIONAL_N_2026 = 15_801_162
N_DRAWS = 50_000
SEED = 26092331
REGION_KAPPA = 5.0
QUANTILES = (0.05, 0.10, 0.50, 0.90, 0.95)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact(value: object) -> str:
    key = norm(value).replace(" ", "")
    if key.startswith("l") and key[1:] == "oriental":
        return "oriental"
    return key


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"LOCAL_N_POSTERIOR_FAIL: {message}")


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scalar_int(value) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(round(float(value)))


def exact_integer_allocation(total: int, weights: np.ndarray) -> np.ndarray:
    """Allocate an integer total by largest fractional remainders."""
    require(total >= 0, "integer allocation total is negative")
    weights = np.asarray(weights, dtype=float)
    require(weights.ndim == 1 and len(weights) > 0, "invalid allocation weight vector")
    require(np.all(np.isfinite(weights)) and np.all(weights >= 0), "invalid allocation weights")
    z = float(weights.sum())
    require(z > 0, "allocation weights sum to zero")
    raw = weights / z * int(total)
    base = np.floor(raw).astype(np.int64)
    left = int(total - int(base.sum()))
    if left:
        order = np.argsort(-(raw - base), kind="stable")
        base[order[:left]] += 1
    require(int(base.sum()) == int(total), "integer allocation failed exact-sum invariant")
    return base


def project_center_with_floors(weights: np.ndarray, floors: np.ndarray, total: int) -> np.ndarray:
    """Continuous proportional projection x_i=max(floor_i, alpha*w_i)."""
    weights = np.asarray(weights, dtype=float)
    floors = np.asarray(floors, dtype=float)
    require(int(floors.sum()) <= total, "feasibility floors exceed national N")
    lo, hi = 0.0, float(total) / max(float(weights.min()), 1e-15)
    for _ in range(100):
        alpha = (lo + hi) / 2.0
        value = np.maximum(floors, alpha * weights).sum()
        if value > total:
            hi = alpha
        else:
            lo = alpha
    projected = np.maximum(floors, lo * weights)
    projected *= total / projected.sum()
    # Rescaling can move a binding floor by machine epsilon; restore it and repeat.
    for _ in range(10):
        binding = projected < floors
        if not binding.any():
            break
        projected[binding] = floors[binding]
        free = ~binding
        residual = total - projected[binding].sum()
        require(residual >= 0 and free.any(), "floor projection has no feasible free component")
        projected[free] *= residual / projected[free].sum()
    require(abs(float(projected.sum()) - total) < 1e-5, "continuous center does not sum to national N")
    require(np.all(projected + 1e-7 >= floors), "continuous center violates floors")
    return projected


def integerize_continuous_with_floors(raw: np.ndarray, floors: np.ndarray, total: int) -> np.ndarray:
    base = np.floor(raw).astype(np.int64)
    base = np.maximum(base, floors.astype(np.int64))
    delta = int(total - int(base.sum()))
    frac = raw - np.floor(raw)
    if delta > 0:
        candidates = np.argsort(-frac, kind="stable")
        base[candidates[:delta]] += 1
    elif delta < 0:
        removable = base - floors.astype(np.int64)
        candidates = np.argsort(frac, kind="stable")
        need = -delta
        for idx in candidates:
            take = min(int(removable[idx]), need)
            if take:
                base[idx] -= take
                need -= take
            if need == 0:
                break
        require(need == 0, "could not integerize centre without violating floors")
    require(int(base.sum()) == total, "integer centre does not sum exactly")
    require(np.all(base >= floors), "integer centre violates floors")
    return base


def map_historical_to_closure(historical_rows: list[dict], closure_rows: list[dict]) -> tuple[dict[int, dict], list[dict]]:
    closure_by_tafra: dict[str, dict] = {}
    for row in closure_rows:
        key = norm(row["tafra_name"])
        require(key not in closure_by_tafra, f"duplicate closure tafra_name: {key}")
        closure_by_tafra[key] = row

    aliases = {
        "rabat el mouhit": "rabat el mouhit",
        "rabat challah": "rabat challah",
        "sale al jadida": "sale al jadida",
        "tifelt rommani": "tifelt rommani",
        "agadir ida ou tanan": "agadir ida outanan",
        "medina sidi youssef ben ali": "medina sidi youssef ben ali",
        "moulay yacoub": "moulay yacoub",
    }
    mapped: dict[int, dict] = {}
    audit = []
    used = set()
    for row in historical_rows:
        if norm(row.get("list_type")) != "locale":
            continue
        key = norm(row["constituency"])
        target = aliases.get(key, key)
        closure = closure_by_tafra.get(target)
        mode = "NORMALIZED_EXACT"
        if closure is None:
            # Conservative unique compact match. Any such use is recorded.
            ckey = compact(target)
            candidates = [candidate for name, candidate in closure_by_tafra.items() if compact(name) == ckey]
            if len(candidates) == 1:
                closure = candidates[0]
                mode = "COMPACT_EXACT"
        require(closure is not None, f"no closure mapping for historical constituency {row['constituency']}")
        cid = int(row["id_constituency"])
        require(cid not in mapped, f"duplicate historical constituency ID {cid}")
        repo_id = closure["constituency_id"]
        require(repo_id not in used, f"closure row reused for {repo_id}")
        used.add(repo_id)
        mapped[cid] = closure
        audit.append(
            {
                "historical_id": cid,
                "historical_name": row["constituency"],
                "repo_id": repo_id,
                "repo_name": closure["name"],
                "match_mode": mode,
            }
        )
    require(len(mapped) == 92 and len(used) == 92, f"historical/closure mapping coverage {len(mapped)}/92")
    return mapped, audit


def match_current_region(value: object, current_regions: list[str]) -> str:
    key = compact(value)
    direct = {compact(region): region for region in current_regions}
    if key in direct:
        return direct[key]
    aliases = {
        "dakhlaouededdahab": "dakhlaouededdahab",
        "guelmimouednoun": "guelmimouednoun",
        "laayounesakiaelhamra": "laayounesakiaelhamra",
        "benimellalkhenifra": "benimellalkhenifra",
        "tangertetouanalhoceima": "tangertetouanalhoceima",
    }
    target = aliases.get(key, key)
    candidates = [region for region in current_regions if compact(region) == target]
    require(len(candidates) == 1, f"cannot map current region {value!r}; candidates={candidates}")
    return candidates[0]


def estimate_variance_components(
    rows2011: list[dict],
    map2011: dict[int, dict],
    raw2007: Path,
    drift_diagnostic: dict,
) -> dict:
    frame = pd.read_excel(raw2007, sheet_name="données")
    required_columns = {"circonscription", "nInscrits"}
    require(required_columns.issubset(set(frame.columns)), f"2007 workbook missing {sorted(required_columns-set(frame.columns))}")

    n2007 = {}
    for _, row in frame.iterrows():
        name = row.get("circonscription")
        registered = scalar_int(row.get("nInscrits"))
        if name is None or registered is None or registered <= 0:
            continue
        key = norm(name)
        require(key not in n2007, f"duplicate exact-normalized 2007 name {key}")
        n2007[key] = registered

    local2011 = [row for row in rows2011 if norm(row.get("list_type")) == "locale"]
    sum2007 = sum(n2007.values())
    sum2011 = sum(int(row["registered_reported"]) for row in local2011)
    pairs = []
    for row in local2011:
        key = norm(row["constituency"])
        if key not in n2007:
            continue
        n11 = int(row["registered_reported"])
        n07 = int(n2007[key])
        delta = math.log((n11 / sum2011) / (n07 / sum2007))
        closure = map2011[int(row["id_constituency"])]
        pairs.append(
            {
                "historical_id": int(row["id_constituency"]),
                "name": row["constituency"],
                "region": closure["region"],
                "N2007": n07,
                "N2011": n11,
                "log_share_delta": delta,
                "same_seat_magnitude": int(row["seats"]) == int(frame.loc[frame["circonscription"].map(norm) == key, "nSieges"].iloc[0]),
            }
        )

    expected_matches = int(drift_diagnostic["historical"]["exact_normalized_name_matches"])
    require(len(pairs) == expected_matches == 74, f"2007->2011 exact-match count {len(pairs)} != diagnostic {expected_matches}")
    delta = np.array([row["log_share_delta"] for row in pairs], dtype=float)
    global_mean = float(delta.mean())

    by_region: dict[str, list[float]] = defaultdict(list)
    for row in pairs:
        by_region[row["region"]].append(float(row["log_share_delta"]))

    region_effect = {}
    region_meta = {}
    for region, values in sorted(by_region.items()):
        n = len(values)
        raw_mean = float(np.mean(values))
        weight = n / (n + REGION_KAPPA)
        effect = weight * (raw_mean - global_mean)
        region_effect[region] = effect
        region_meta[region] = {
            "n": n,
            "raw_mean_log_share_delta": raw_mean,
            "shrinkage_weight": weight,
            "shrunk_zero_centred_effect": effect,
        }

    replicated_region = np.array([region_effect[row["region"]] for row in pairs], dtype=float)
    local_residual = np.array(
        [row["log_share_delta"] - global_mean - region_effect[row["region"]] for row in pairs],
        dtype=float,
    )
    sigma_region = float(np.std(replicated_region, ddof=1))
    sigma_local = float(np.std(local_residual, ddof=1))
    combined = math.sqrt(sigma_region**2 + sigma_local**2)
    variance_floor = float(drift_diagnostic["drift"]["sd"])
    require(variance_floor > 0, "historical variance floor is non-positive")
    scale = max(1.0, variance_floor / combined) if combined > 0 else 1.0
    sigma_region *= scale
    sigma_local *= scale

    return {
        "source_transition": "2007_to_2011_exact_normalized_name_matches",
        "matched_territories": len(pairs),
        "same_magnitude_matches": sum(row["same_seat_magnitude"] for row in pairs),
        "national_sum_N2007": sum2007,
        "national_sum_N2011": sum2011,
        "global_mean_log_share_delta_diagnostic_only": global_mean,
        "region_kappa": REGION_KAPPA,
        "region_metadata": region_meta,
        "raw_sigma_region": float(np.std(replicated_region, ddof=1)),
        "raw_sigma_local": float(np.std(local_residual, ddof=1)),
        "raw_combined_sigma": combined,
        "variance_floor": variance_floor,
        "floor_scale_applied": scale,
        "posterior_sigma_region": sigma_region,
        "posterior_sigma_local": sigma_local,
        "posterior_combined_sigma": math.sqrt(sigma_region**2 + sigma_local**2),
        "zero_mean_rule": "Historical mean drift is diagnostic only; posterior innovations are centred at zero around the 2011-share centre.",
        "stationarity_warning": drift_diagnostic["drift"]["warning"],
    }


def integerize_slack_draws(slack_total: int, probabilities: np.ndarray) -> np.ndarray:
    raw = probabilities * int(slack_total)
    base = np.floor(raw).astype(np.int64)
    deficit = int(slack_total) - base.sum(axis=1)
    require(np.all(deficit >= 0) and np.all(deficit < probabilities.shape[1]), "unexpected slack rounding deficit")
    fraction = raw - base
    order = np.argsort(-fraction, axis=1, kind="stable")
    for rank in range(int(deficit.max(initial=0))):
        rows = np.flatnonzero(deficit > rank)
        if len(rows):
            base[rows, order[rows, rank]] += 1
    require(np.all(base.sum(axis=1) == int(slack_total)), "slack draws do not sum exactly")
    return base


def allocation_key(result) -> tuple[tuple[str, int], ...] | None:
    return tuple(sorted(result.seats_by_list.items())) if result.complete else None


def sensitivity_for_vector(
    votes: dict[str, int],
    seats: int,
    center_N: int,
    sampled_N: np.ndarray,
) -> dict:
    center_result = allocate_2026(votes, int(center_N), int(seats))
    center_key = allocation_key(center_result)
    require(center_key is not None, f"centre allocation failed: status={center_result.status}")
    changed = 0
    unresolved = 0
    status_counts: dict[str, int] = defaultdict(int)
    cache: dict[int, tuple[tuple[str, int], ...] | None] = {}
    values, counts = np.unique(sampled_N.astype(np.int64), return_counts=True)
    for value, count in zip(values.tolist(), counts.tolist()):
        result = allocate_2026(votes, int(value), int(seats))
        status_counts[result.status] += int(count)
        key = allocation_key(result)
        cache[int(value)] = key
        if key is None:
            unresolved += int(count)
        elif key != center_key:
            changed += int(count)
    n = int(len(sampled_N))
    return {
        "center_allocation": dict(center_key),
        "allocation_change_probability_resolved": changed / n,
        "unresolved_statutory_probability": unresolved / n,
        "any_change_or_unresolved_probability": (changed + unresolved) / n,
        "unique_N_values_evaluated": len(values),
        "status_counts": dict(sorted(status_counts.items())),
    }


def summarize_draw_column(values: np.ndarray, center: int) -> dict:
    q = np.quantile(values, QUANTILES)
    return {
        "center": int(center),
        "mean": float(values.mean()),
        "sd": float(values.std(ddof=1)),
        "q05": int(round(q[0])),
        "q10": int(round(q[1])),
        "q50": int(round(q[2])),
        "q90": int(round(q[3])),
        "q95": int(round(q[4])),
        "min": int(values.min()),
        "max": int(values.max()),
    }


def main() -> None:
    paths = {
        "canonical_2011": HIST / "tafra_legislative_2011_canonical.json",
        "canonical_2021": HIST / "tafra_legislative_2021_canonical.json",
        "raw_2007": G100 / "older_history_probe" / "raw" / "parlement-elections-2007-1-0.xlsx",
        "closure_92": G75 / "local_92_closure_v3.json",
        "interval_proof": G75 / "local_allocation_interval_proof.json",
        "drift_diagnostic": G100 / "local_N_drift_diagnostic.json",
        "geometry_certificate": G100 / "geometry_2026_certificate.json",
    }
    for path in paths.values():
        require(path.exists(), f"required input missing: {path.relative_to(ROOT)}")

    canonical2011 = load(paths["canonical_2011"])
    canonical2021 = load(paths["canonical_2021"])
    closure = load(paths["closure_92"])
    interval = load(paths["interval_proof"])
    drift = load(paths["drift_diagnostic"])
    geometry = load(paths["geometry_certificate"])
    require(geometry["gate"] == "PASS", "geometry must be certified before N posterior")
    require(int(drift["official_2026_national_N"]) == NATIONAL_N_2026, "official national N disagreement")

    rows2011 = canonical2011["rows"]
    rows2021 = canonical2021["rows"]
    closure_rows = closure["rows"]
    map2011, mapping_audit = map_historical_to_closure(rows2011, closure_rows)
    map2021, mapping_audit_2021 = map_historical_to_closure(rows2021, closure_rows)
    require(
        {cid: row["constituency_id"] for cid, row in map2011.items()}
        == {cid: row["constituency_id"] for cid, row in map2021.items()},
        "2011/2021 mapping disagreement",
    )

    local2011_by_id = {
        int(row["id_constituency"]): row
        for row in rows2011
        if norm(row.get("list_type")) == "locale"
    }
    local2021_by_id = {
        int(row["id_constituency"]): row
        for row in rows2021
        if norm(row.get("list_type")) == "locale"
    }
    require(set(local2011_by_id) == set(local2021_by_id) == set(map2011), "modern local ID sets are not identical")

    ordered_closure = sorted(closure_rows, key=lambda row: row["constituency_id"])
    repo_to_historical = {row["constituency_id"]: cid for cid, row in map2011.items()}
    require(len(repo_to_historical) == 92, "repo/historical reverse mapping is incomplete")
    current_regions = sorted({row["region"] for row in ordered_closure})
    require(len(current_regions) == 12, f"current region count {len(current_regions)} != 12")
    region_index = {region: idx for idx, region in enumerate(current_regions)}

    ids = [row["constituency_id"] for row in ordered_closure]
    names = [row["name"] for row in ordered_closure]
    regions = [row["region"] for row in ordered_closure]
    seats = np.array([int(row["seats"]) for row in ordered_closure], dtype=np.int64)
    hist_ids = [repo_to_historical[repo_id] for repo_id in ids]

    registered2011 = np.array(
        [int(local2011_by_id[cid]["registered_reported"]) for cid in hist_ids],
        dtype=np.int64,
    )
    require(np.all(registered2011 > 0), "2011 registered counts are incomplete")
    weights2011 = registered2011 / registered2011.sum()

    local_votes = [
        {str(party): int(value) for party, value in local2021_by_id[cid]["votes"].items() if int(value) > 0}
        for cid in hist_ids
    ]
    local_valid = np.array([sum(votes.values()) for votes in local_votes], dtype=np.int64)
    require(np.all(local_valid > 0), "a local 2021 vote vector is empty")

    regional2021 = [row for row in rows2021 if norm(row.get("list_type")) == "regionale"]
    require(len(regional2021) == 12, f"2021 regional row count {len(regional2021)} != 12")
    regional_votes: dict[str, dict[str, int]] = {}
    regional_seats: dict[str, int] = {}
    for row in regional2021:
        region = match_current_region(row.get("region") or row.get("constituency"), current_regions)
        require(region not in regional_votes, f"duplicate regional 2021 row for {region}")
        regional_votes[region] = {
            str(party): int(value)
            for party, value in row["votes"].items()
            if int(value) > 0
        }
        regional_seats[region] = int(row["seats"])
    require(set(regional_votes) == set(current_regions), "regional vote coverage is incomplete")

    # Local feasibility floors, then region-level ballot feasibility floors.
    floors = local_valid.copy()
    regional_floor_adjustments = {}
    for region in current_regions:
        indices = np.array([i for i, value in enumerate(regions) if value == region], dtype=int)
        required_region_N = sum(regional_votes[region].values())
        current_floor = int(floors[indices].sum())
        shortfall = max(0, required_region_N - current_floor)
        if shortfall:
            addition = exact_integer_allocation(shortfall, weights2011[indices])
            floors[indices] += addition
        regional_floor_adjustments[region] = {
            "regional_valid_vote_floor": required_region_N,
            "local_valid_vote_floor_sum_before_adjustment": current_floor,
            "additional_floor_reserved": shortfall,
            "floor_sum_after_adjustment": int(floors[indices].sum()),
        }
        require(int(floors[indices].sum()) >= required_region_N, f"regional feasibility floor failed for {region}")
    require(int(floors.sum()) < NATIONAL_N_2026, "feasibility floors leave no posterior slack")

    continuous_center = project_center_with_floors(weights2011, floors, NATIONAL_N_2026)
    center = integerize_continuous_with_floors(continuous_center, floors, NATIONAL_N_2026)
    slack_total = int(NATIONAL_N_2026 - floors.sum())
    slack_center = np.maximum(continuous_center - floors, 1e-9)
    slack_weights = slack_center / slack_center.sum()

    variance = estimate_variance_components(
        rows2011,
        map2011,
        paths["raw_2007"],
        drift,
    )
    sigma_region = float(variance["posterior_sigma_region"])
    sigma_local = float(variance["posterior_sigma_local"])
    require(sigma_region >= 0 and sigma_local > 0, "invalid posterior variance components")

    rng = np.random.default_rng(SEED)
    region_draws = rng.normal(0.0, sigma_region, size=(N_DRAWS, len(current_regions)))
    local_draws = rng.normal(0.0, sigma_local, size=(N_DRAWS, len(ids)))
    region_lookup = np.array([region_index[region] for region in regions], dtype=int)
    logits = np.log(slack_weights)[None, :] + region_draws[:, region_lookup] + local_draws
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    slack_draws = integerize_slack_draws(slack_total, probability)
    draws = slack_draws + floors[None, :]

    sum_error = draws.sum(axis=1) - NATIONAL_N_2026
    positive_failures = int(np.sum(draws <= 0))
    floor_failures = int(np.sum(draws < floors[None, :]))
    require(np.all(sum_error == 0), "posterior draw national sum invariant failed")
    require(positive_failures == 0, "posterior contains non-positive local N")
    require(floor_failures == 0, "posterior violates a feasibility floor")

    proof_by_id = {
        int(row["idCirconscription"]): bool(row["invariant_to_topN_over_full_interval"])
        for row in interval["rows"]
    }
    require(set(proof_by_id) == set(hist_ids), "denominator-invariance proof ID coverage mismatch")
    require(sum(proof_by_id.values()) == 81, "expected 81 denominator-invariant local contests")

    local_output = []
    for idx, repo_id in enumerate(ids):
        cid = hist_ids[idx]
        summary = summarize_draw_column(draws[:, idx], int(center[idx]))
        invariant = proof_by_id[cid]
        center_result = allocate_2026(local_votes[idx], int(center[idx]), int(seats[idx]))
        require(center_result.complete, f"center local allocation failed for {repo_id}: {center_result.status}")
        if invariant:
            sensitivity = {
                "center_allocation": dict(sorted(center_result.seats_by_list.items())),
                "allocation_change_probability_resolved": 0.0,
                "unresolved_statutory_probability": 0.0,
                "any_change_or_unresolved_probability": 0.0,
                "unique_N_values_evaluated": 0,
                "status_counts": {"DENOMINATOR_INVARIANT_EXACT_PROOF": N_DRAWS},
            }
        else:
            sensitivity = sensitivity_for_vector(
                local_votes[idx],
                int(seats[idx]),
                int(center[idx]),
                draws[:, idx],
            )
        local_output.append(
            {
                "constituency_id": repo_id,
                "historical_id": cid,
                "name": names[idx],
                "region": regions[idx],
                "seats": int(seats[idx]),
                "registered_2011": int(registered2011[idx]),
                "weight_2011": float(weights2011[idx]),
                "local_valid_vote_floor_2021": int(local_valid[idx]),
                "posterior_floor_after_regional_constraint": int(floors[idx]),
                "posterior": summary,
                "denominator_invariant_exact_proof": invariant,
                "N_only_seat_sensitivity": sensitivity,
            }
        )

    regional_output = []
    for region in current_regions:
        indices = np.array([i for i, value in enumerate(regions) if value == region], dtype=int)
        sampled = draws[:, indices].sum(axis=1)
        center_region = int(center[indices].sum())
        sensitivity = sensitivity_for_vector(
            regional_votes[region],
            regional_seats[region],
            center_region,
            sampled,
        )
        regional_output.append(
            {
                "region": region,
                "seats": regional_seats[region],
                "constituencies": len(indices),
                "regional_valid_vote_floor_2021": sum(regional_votes[region].values()),
                "posterior": summarize_draw_column(sampled, center_region),
                "N_only_seat_sensitivity": sensitivity,
            }
        )

    local_change = [row["N_only_seat_sensitivity"]["any_change_or_unresolved_probability"] for row in local_output]
    regional_change = [row["N_only_seat_sensitivity"]["any_change_or_unresolved_probability"] for row in regional_output]
    unresolved_mass_local = sum(row["N_only_seat_sensitivity"]["unresolved_statutory_probability"] for row in local_output)
    unresolved_mass_regional = sum(row["N_only_seat_sensitivity"]["unresolved_statutory_probability"] for row in regional_output)

    draw_stream_hash = hashlib.sha256(np.ascontiguousarray(draws, dtype="<i8").tobytes()).hexdigest()
    result = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-LOCAL-N-POSTERIOR-V1",
        "as_of": "2026-08-16",
        "gate": "PASS",
        "epistemic_status": "LATENT_CALIBRATED_PRIOR_NOT_OFFICIAL_LOCAL_COUNTS",
        "national_N_2026": NATIONAL_N_2026,
        "draw_contract": {
            "draws": N_DRAWS,
            "seed": SEED,
            "positive_integer_entries": positive_failures == 0,
            "exact_sum_every_draw": bool(np.all(sum_error == 0)),
            "max_absolute_sum_error": int(np.abs(sum_error).max()),
            "feasibility_floor_violations": floor_failures,
            "minimum_sampled_local_N": int(draws.min()),
            "maximum_sampled_local_N": int(draws.max()),
            "draw_stream_sha256_little_endian_int64": draw_stream_hash,
            "raw_draws_persisted": False,
            "raw_draws_policy": "Summaries and a deterministic stream hash are persisted; the full pseudo-count matrix is regenerated from the frozen seed and parameters.",
        },
        "centre": {
            "base": "2011 local registered-voter shares",
            "projection": "proportional water-filling above local and regional 2021 valid-vote feasibility floors",
            "national_sum": int(center.sum()),
            "slack_after_floors": slack_total,
            "official_status": "NOT_OFFICIAL_LOCAL_COUNTS",
        },
        "variance_model": variance,
        "regional_floor_adjustments": regional_floor_adjustments,
        "mapping_audit": {
            "2011": mapping_audit,
            "2021": mapping_audit_2021,
            "coverage": 92,
        },
        "local": {
            "rows": 92,
            "denominator_invariant_exact": sum(proof_by_id.values()),
            "denominator_sensitive": 92 - sum(proof_by_id.values()),
            "territories_with_any_N_only_change_mass": sum(value > 0 for value in local_change),
            "maximum_any_change_or_unresolved_probability": max(local_change),
            "aggregate_unresolved_statutory_probability_sum": unresolved_mass_local,
            "rows_detail": local_output,
        },
        "regional": {
            "rows": 12,
            "regions_with_any_N_only_change_mass": sum(value > 0 for value in regional_change),
            "maximum_any_change_or_unresolved_probability": max(regional_change),
            "aggregate_unresolved_statutory_probability_sum": unresolved_mass_regional,
            "rows_detail": regional_output,
        },
        "source_hashes": {name: sha256_path(path) for name, path in paths.items()},
        "limitations": [
            "The local centre is based on 2011 electorate shares, not official 2026 local counts.",
            "The variance floor is informed by one exact-name 2007->2011 transition and is not asserted stationary.",
            "N-only seat sensitivity holds the 2021 vote vectors fixed; full F-1 sensitivity will jointly vary votes, turnout and N.",
            "A later authoritative local-N table requires a new immutable forecast snapshot and does not overwrite this posterior or prior forecasts.",
        ],
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": result["gate"],
                "draws": N_DRAWS,
                "sum_exact": result["draw_contract"]["exact_sum_every_draw"],
                "local_rows": result["local"]["rows"],
                "local_invariant": result["local"]["denominator_invariant_exact"],
                "local_sensitive": result["local"]["denominator_sensitive"],
                "local_with_change_mass": result["local"]["territories_with_any_N_only_change_mass"],
                "regional_rows": result["regional"]["rows"],
                "regional_with_change_mass": result["regional"]["regions_with_any_N_only_change_mass"],
                "unresolved_mass_local_sum": unresolved_mass_local,
                "unresolved_mass_regional_sum": unresolved_mass_regional,
                "draw_hash": draw_stream_hash,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
