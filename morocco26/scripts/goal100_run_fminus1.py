#!/usr/bin/env python3
"""Run and freeze the first MOROCCO//26 structural probabilistic forecast (F-1).

This execution is deliberately non-agentic and uses only the frozen persistence
mean, calibrated hierarchical uncertainty, latent constrained N92 posterior,
current-law allocator, and 2021 contest/list structure. It creates immutable
forecast artifacts but does not mutate the append-only registry; registration is
a separate fail-closed transition.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G75 = DATA / "goal75"
G100 = DATA / "goal100"
HIST = G100 / "historical"
FORECAST_DIR = G100 / "forecasts" / "F-1"
FORECAST_PATH = FORECAST_DIR / "forecast.json"
DATA_MANIFEST_PATH = FORECAST_DIR / "data_manifest.json"
PARAMETER_MANIFEST_PATH = FORECAST_DIR / "parameter_manifest.json"
RNG_MANIFEST_PATH = FORECAST_DIR / "rng_seed_manifest.json"
SNAPSHOT_MANIFEST_PATH = FORECAST_DIR / "snapshot_manifest.json"
SIMULATION_CERTIFICATE_PATH = G100 / "simulation_certificate.json"

sys.path.insert(0, str(ROOT / "src"))
from morocco26.legal_allocator_2026 import allocate_2026  # noqa: E402

CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
BUCKETS = (*CORE, "OTHER")
EPS_VOTES = 0.5
N_DRAWS = 50_000
NATIONAL_N = 15_801_162
QUANTILES = (0.025, 0.10, 0.25, 0.50, 0.75, 0.90, 0.975)
QUANTILE_NAMES = ("q025", "q10", "q25", "q50", "q75", "q90", "q975")


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def compact(value: object) -> str:
    key = norm(value).replace(" ", "")
    if key == "loriental":
        return "oriental"
    return key


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FMINUS1_FAIL: {message}")


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_hash(value: object) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_year(year: int) -> dict[str, dict]:
    data = load_json(HIST / f"tafra_legislative_{year}_canonical.json")
    return {
        str(row["id_constituency"]): row
        for row in data["rows"]
        if norm(row.get("list_type")) == "locale"
    }


def build_mapping(rows: dict[str, dict]) -> dict[str, dict]:
    closure = load_json(G75 / "local_92_closure_v3.json")["rows"]
    by_name = {norm(row["tafra_name"]): row for row in closure}
    require(len(by_name) == 92, "closure names are not unique")
    mapping = {}
    used = set()
    for historical_id, row in rows.items():
        key = norm(row["constituency"])
        target = by_name.get(key)
        if target is None:
            candidates = [candidate for name, candidate in by_name.items() if name.replace(" ", "") == key.replace(" ", "")]
            require(len(candidates) == 1, f"cannot map {row['constituency']}")
            target = candidates[0]
        require(target["constituency_id"] not in used, f"mapping reused {target['constituency_id']}")
        used.add(target["constituency_id"])
        mapping[historical_id] = target
    require(len(mapping) == 92 and len(used) == 92, "mapping coverage != 92")
    return mapping


def match_region(value: object, regions: list[str]) -> str:
    key = compact(value)
    direct = {compact(region): region for region in regions}
    require(key in direct, f"cannot map region {value!r}")
    return direct[key]


def bucket_counts(row: dict) -> np.ndarray:
    raw = row.get("votes", {})
    values = [float(raw.get(party, 0) or 0) for party in CORE]
    values.append(sum(float(value or 0) for party, value in raw.items() if party not in CORE))
    array = np.asarray(values, dtype=float)
    require(np.all(array >= 0) and array.sum() > 0, f"invalid vote vector {row.get('id_constituency')}")
    return array


def clr(row: dict) -> np.ndarray:
    values = bucket_counts(row) + EPS_VOTES
    share = values / values.sum()
    logs = np.log(share)
    return logs - logs.mean()


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


def integerize_probability_rows(total: int, probabilities: np.ndarray) -> np.ndarray:
    raw = probabilities * int(total)
    base = np.floor(raw).astype(np.int64)
    deficit = int(total) - base.sum(axis=1)
    require(np.all(deficit >= 0) and np.all(deficit < probabilities.shape[1]), "invalid integerization deficit")
    order = np.argsort(-(raw - base), axis=1, kind="stable")
    for rank in range(int(deficit.max(initial=0))):
        rows = np.flatnonzero(deficit > rank)
        if len(rows):
            base[rows, order[rows, rank]] += 1
    require(np.all(base.sum(axis=1) == int(total)), "row integerization exact-sum failure")
    return base


def generate_N_draws(protocol: dict, local_n: dict, territory_order: list[str], region_by_territory: list[str], region_order: list[str]) -> tuple[np.ndarray, dict]:
    rows = {row["constituency_id"]: row for row in local_n["local"]["rows_detail"]}
    require(set(rows) == set(territory_order), "N92 territory order coverage mismatch")
    floors = np.asarray([rows[territory]["posterior_floor_after_regional_constraint"] for territory in territory_order], dtype=np.int64)
    centers = np.asarray([rows[territory]["posterior"]["center"] for territory in territory_order], dtype=np.int64)
    slack_total = int(NATIONAL_N - floors.sum())
    require(slack_total > 0, "N92 floors exhaust national total")
    slack_weights = np.maximum(centers - floors, 1).astype(float)
    slack_weights /= slack_weights.sum()
    variance = local_n["variance_model"]
    sigma_region = float(variance["posterior_sigma_region"])
    sigma_local = float(variance["posterior_sigma_local"])
    seed = int(protocol["monte_carlo"]["seed_manifest"]["N92"])
    rng = np.random.default_rng(seed)
    region_index = {region: index for index, region in enumerate(region_order)}
    region_lookup = np.asarray([region_index[region] for region in region_by_territory], dtype=int)
    region_shock = rng.normal(0.0, sigma_region, size=(N_DRAWS, len(region_order)))
    local_shock = rng.normal(0.0, sigma_local, size=(N_DRAWS, len(territory_order)))
    logits = np.log(slack_weights)[None, :] + region_shock[:, region_lookup] + local_shock
    logits -= logits.max(axis=1, keepdims=True)
    probability = np.exp(logits)
    probability /= probability.sum(axis=1, keepdims=True)
    slack = integerize_probability_rows(slack_total, probability)
    draws = slack + floors[None, :]
    require(np.all(draws > 0), "N92 draw contains non-positive N")
    require(np.all(draws.sum(axis=1) == NATIONAL_N), "N92 draw does not sum to national total")
    return draws, {
        "seed": seed,
        "sigma_region": sigma_region,
        "sigma_local": sigma_local,
        "slack_total": slack_total,
        "stream_sha256": hashlib.sha256(np.ascontiguousarray(draws, dtype="<i8").tobytes()).hexdigest(),
        "minimum": int(draws.min()),
        "maximum": int(draws.max()),
    }


def quantile_summary(values: np.ndarray) -> dict:
    array = np.asarray(values, dtype=float)
    q = np.quantile(array, QUANTILES, axis=0)
    result = {
        "mean": np.mean(array, axis=0).tolist() if array.ndim > 1 else float(np.mean(array)),
        "sd": np.std(array, axis=0, ddof=1).tolist() if array.ndim > 1 else float(np.std(array, ddof=1)),
    }
    for name, value in zip(QUANTILE_NAMES, q):
        result[name] = value.tolist() if np.ndim(value) else float(value)
    return result


def bucket_share_summary(shares: np.ndarray) -> dict:
    summary = quantile_summary(shares)
    output = {}
    for index, bucket in enumerate(BUCKETS):
        output[bucket] = {
            key: float(value[index]) if isinstance(value, list) else value
            for key, value in summary.items()
        }
    return output


def seats_summary(bucket_seats: np.ndarray, magnitude: int) -> dict:
    output = {}
    for index, bucket in enumerate(BUCKETS):
        values = bucket_seats[:, index].astype(int)
        probability = [float(np.mean(values == count)) for count in range(magnitude + 1)]
        expected = float(values.mean())
        output[bucket] = {
            "P_seats_k": probability,
            "expected_seats": expected,
            "mc_standard_error_expected": float(values.std(ddof=1) / math.sqrt(len(values))),
            "max_probability_mc_se": float(max(math.sqrt(p * (1 - p) / len(values)) for p in probability)),
        }
    return output


def build_actual_probabilities(shares: np.ndarray, raw_votes: dict[str, int]) -> tuple[np.ndarray, list[str], dict]:
    minor = sorted(party for party, value in raw_votes.items() if party not in CORE and int(value or 0) > 0)
    diagnostics = {"minor_parties": minor, "other_folded_into_core": False}
    if minor:
        minor_values = np.asarray([float(raw_votes[party]) for party in minor], dtype=float)
        minor_weights = minor_values / minor_values.sum()
        probabilities = np.concatenate(
            [shares[:, : len(CORE)], shares[:, -1, None] * minor_weights[None, :]],
            axis=1,
        )
        parties = [*CORE, *minor]
    else:
        core = shares[:, : len(CORE)]
        probabilities = core / core.sum(axis=1, keepdims=True)
        parties = list(CORE)
        diagnostics["other_folded_into_core"] = True
    require(float(np.max(np.abs(probabilities.sum(axis=1) - 1))) < 1e-10, "actual party probabilities do not sum to one")
    return probabilities, parties, diagnostics


def balanced_round(expected: np.ndarray, totals: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    base = np.floor(expected).astype(np.int64)
    deficit = totals.astype(np.int64) - base.sum(axis=1)
    require(np.all(deficit >= 0) and np.all(deficit < expected.shape[1]), "balanced-round deficit invalid")
    fraction = expected - base
    gumbel = rng.gumbel(size=expected.shape)
    score = np.log(np.maximum(fraction, 1e-300)) + gumbel
    order = np.argsort(-score, axis=1, kind="stable")
    for rank in range(int(deficit.max(initial=0))):
        rows = np.flatnonzero(deficit > rank)
        if len(rows):
            base[rows, order[rows, rank]] += 1
    require(np.all(base.sum(axis=1) == totals), "balanced rounding does not preserve totals")
    return base


def vectorized_allocate(votes: np.ndarray, registered: np.ndarray, magnitude: int) -> tuple[np.ndarray, np.ndarray]:
    registered = registered.astype(np.int64)
    votes = votes.astype(np.int64)
    require(np.all(votes >= 0), "negative simulated votes")
    require(np.all(votes.sum(axis=1) <= registered), "simulated votes exceed registered N")
    base = (votes * int(magnitude)) // registered[:, None]
    remainders = votes * int(magnitude) - base * registered[:, None]
    left = int(magnitude) - base.sum(axis=1)
    require(np.all(left >= 0) and np.all(left <= magnitude), "invalid remaining-seat count")
    order = np.argsort(-remainders, axis=1, kind="stable")
    unresolved = np.zeros(len(votes), dtype=bool)
    for row_index in np.flatnonzero(left > 0):
        need = int(left[row_index])
        cutoff = remainders[row_index, order[row_index, need - 1]]
        greater = int(np.sum(remainders[row_index] > cutoff))
        equal = int(np.sum(remainders[row_index] == cutoff))
        if greater < need < greater + equal:
            unresolved[row_index] = True
    seats = base.copy()
    for rank in range(int(left.max(initial=0))):
        rows = np.flatnonzero((left > rank) & ~unresolved)
        if len(rows):
            seats[rows, order[rows, rank]] += 1
    return seats, unresolved


def simulate_contest(
    shares: np.ndarray,
    valid_votes: np.ndarray,
    registered: np.ndarray,
    magnitude: int,
    raw_votes: dict[str, int],
    rng: np.random.Generator,
    max_attempts: int,
) -> tuple[np.ndarray, list[str], dict]:
    probabilities, parties, diagnostics = build_actual_probabilities(shares, raw_votes)
    expected = probabilities * valid_votes[:, None]
    counts = balanced_round(expected, valid_votes, rng)
    seats, unresolved = vectorized_allocate(counts, registered, magnitude)
    rerounded_draws = int(unresolved.sum())
    attempts_used = 0
    while unresolved.any() and attempts_used < max_attempts:
        attempts_used += 1
        rows = np.flatnonzero(unresolved)
        replacement = balanced_round(expected[rows], valid_votes[rows], rng)
        counts[rows] = replacement
        replacement_seats, replacement_unresolved = vectorized_allocate(
            replacement,
            registered[rows],
            magnitude,
        )
        seats[rows] = replacement_seats
        unresolved[rows] = replacement_unresolved
    require(not unresolved.any(), f"unresolved statutory ties remain after {max_attempts} rerounding attempts")
    require(np.all(seats.sum(axis=1) == magnitude), "contest does not allocate exact magnitude")

    # Exact spot-check against the fail-closed scalar allocator.
    for row_index in np.linspace(0, len(counts) - 1, 5, dtype=int):
        vote_dict = {party: int(counts[row_index, index]) for index, party in enumerate(parties) if counts[row_index, index] > 0}
        scalar = allocate_2026(vote_dict, int(registered[row_index]), int(magnitude))
        require(scalar.complete, f"scalar legal spot-check failed: {scalar.status}")
        expected_key = {party: int(seats[row_index, index]) for index, party in enumerate(parties) if seats[row_index, index] > 0}
        require(scalar.seats_by_list == expected_key, "vectorized/scalar allocator disagreement")

    diagnostics.update(
        {
            "rerounded_draws": rerounded_draws,
            "maximum_attempts_used": attempts_used,
            "unresolved_after_retries": 0,
        }
    )
    return seats, parties, diagnostics


def bucket_seats_from_actual(actual_seats: np.ndarray, parties: list[str]) -> np.ndarray:
    output = np.zeros((len(actual_seats), len(BUCKETS)), dtype=np.int16)
    bucket_index = {bucket: index for index, bucket in enumerate(BUCKETS)}
    for party_index, party in enumerate(parties):
        target = party if party in CORE else "OTHER"
        output[:, bucket_index[target]] += actual_seats[:, party_index].astype(np.int16)
    return output


def add_actual_totals(store: dict[str, np.ndarray], actual_seats: np.ndarray, parties: list[str]) -> None:
    for index, party in enumerate(parties):
        if party not in store:
            store[party] = np.zeros(len(actual_seats), dtype=np.int16)
        store[party] += actual_seats[:, index].astype(np.int16)


def valid_fraction_model(y11: dict[str, dict], ids: list[str]) -> tuple[dict[str, float], dict]:
    raw = []
    for historical_id in ids:
        row = y11[historical_id]
        registered = int(row["registered_reported"])
        turnout = float(row["turnout_rate_reported"])
        ratio = sum(int(value) for value in row["votes"].values()) / (registered * turnout)
        raw.append(ratio)
    array = np.asarray(raw, dtype=float)
    p05, p95 = np.quantile(array, [0.05, 0.95])
    median = float(np.median(array))
    winsor = np.clip(array, p05, p95)
    shrunk = 0.5 * winsor + 0.5 * median
    shrunk = np.clip(shrunk, 1e-6, 1.0)
    return {historical_id: float(shrunk[index]) for index, historical_id in enumerate(ids)}, {
        "raw_min": float(array.min()),
        "raw_max": float(array.max()),
        "raw_median": median,
        "winsor_p05": float(p05),
        "winsor_p95": float(p95),
        "final_min": float(shrunk.min()),
        "final_max": float(shrunk.max()),
        "shrinkage_to_median": 0.5,
    }


def summarize_actual_national(actual_totals: dict[str, np.ndarray]) -> dict:
    output = {}
    for party, values in sorted(actual_totals.items()):
        summary = quantile_summary(values)
        output[party] = {key: float(value) for key, value in summary.items()}
    return output


def main() -> None:
    require(not FORECAST_DIR.exists(), "F-1 forecast directory already exists; immutable snapshot cannot be overwritten")
    protocol_path = G100 / "fminus1_protocol_v1.json"
    uncertainty_path = G100 / "uncertainty_calibration.json"
    local_n_path = G100 / "local_N_posterior.json"
    geometry_path = G100 / "geometry_2026_certificate.json"
    legal_path = ROOT / "src" / "morocco26" / "legal_allocator_2026.py"
    closure_path = G75 / "local_92_closure_v3.json"
    canonical2011_path = HIST / "tafra_legislative_2011_canonical.json"
    canonical2021_path = HIST / "tafra_legislative_2021_canonical.json"
    input_paths = {
        "protocol": protocol_path,
        "uncertainty": uncertainty_path,
        "local_N": local_n_path,
        "geometry": geometry_path,
        "legal_allocator": legal_path,
        "closure_92": closure_path,
        "canonical_2011": canonical2011_path,
        "canonical_2021": canonical2021_path,
    }
    for path in input_paths.values():
        require(path.exists(), f"missing input {path.relative_to(ROOT)}")

    protocol = load_json(protocol_path)
    uncertainty = load_json(uncertainty_path)
    local_n = load_json(local_n_path)
    geometry = load_json(geometry_path)
    require(protocol["snapshot_id"] == "F-1" and protocol["monte_carlo"]["draws"] == N_DRAWS, "F-1 protocol drift")
    require(uncertainty["gate"] == "PASS", "uncertainty calibration gate not PASS")
    require(local_n["gate"] == "PASS", "N92 posterior gate not PASS")
    require(geometry["gate"] == "PASS" and geometry["house_seats"] == 395, "geometry gate not PASS")

    library = uncertainty["final_all_pre2026_component_library"]
    require(library["support_sha256"] == protocol["uncertainty"]["support_sha256"], "uncertainty support hash/protocol mismatch")
    require(float(library["selected_vote_scale"]) == float(protocol["uncertainty"]["vote_scale"]), "vote scale mismatch")
    require(float(library["selected_turnout_scale"]) == float(protocol["uncertainty"]["turnout_scale"]), "turnout scale mismatch")

    y11 = load_year(2011)
    y21 = load_year(2021)
    ids = list(library["historical_id_order"])
    territory_order = list(library["territory_order"])
    region_order = list(library["region_order"])
    region_by_territory = list(library["region_by_territory"])
    require(len(ids) == len(territory_order) == len(region_by_territory) == 92, "uncertainty territory order invalid")
    mapping = build_mapping(y21)
    require([mapping[historical_id]["constituency_id"] for historical_id in ids] == territory_order, "mapping disagrees with uncertainty order")
    region_index = {region: index for index, region in enumerate(region_order)}
    territory_region_index = np.asarray([region_index[region] for region in region_by_territory], dtype=int)

    N_draws, N_diagnostics = generate_N_draws(protocol, local_n, territory_order, region_by_territory, region_order)

    vote_scale = float(library["selected_vote_scale"])
    turnout_scale = float(library["selected_turnout_scale"])
    national_vote_support = np.asarray(library["national_vote_support"], dtype=float)
    national_turnout_support = np.asarray(library["national_turnout_support"], dtype=float)
    regional_vote_support = {region: np.asarray(values, dtype=float) for region, values in library["regional_vote_support"].items()}
    regional_turnout_support = {region: np.asarray(values, dtype=float) for region, values in library["regional_turnout_support"].items()}
    local_vote_support = np.asarray(library["local_vote_support"], dtype=float)
    local_turnout_support = np.asarray(library["local_turnout_support"], dtype=float)

    seeds = {key: int(value) for key, value in protocol["monte_carlo"]["seed_manifest"].items()}
    rng_national_vote = np.random.default_rng(seeds["national_vote"])
    rng_regional_vote = np.random.default_rng(seeds["regional_vote"])
    rng_local_vote = np.random.default_rng(seeds["local_vote"])
    rng_national_turnout = np.random.default_rng(seeds["national_turnout"])
    rng_regional_turnout = np.random.default_rng(seeds["regional_turnout"])
    rng_local_turnout = np.random.default_rng(seeds["local_turnout"])
    rng_rounding = np.random.default_rng(seeds["vote_rounding"])

    national_vote_draw = national_vote_support[rng_national_vote.integers(0, len(national_vote_support), size=N_DRAWS)]
    national_turnout_draw = national_turnout_support[rng_national_turnout.integers(0, len(national_turnout_support), size=N_DRAWS)]
    regional_vote_draw = np.empty((N_DRAWS, len(region_order), len(BUCKETS)), dtype=float)
    regional_turnout_draw = np.empty((N_DRAWS, len(region_order)), dtype=float)
    for region, ridx in region_index.items():
        vote_support = regional_vote_support[region]
        turnout_support = regional_turnout_support[region]
        regional_vote_draw[:, ridx, :] = vote_support[rng_regional_vote.integers(0, len(vote_support), size=N_DRAWS)]
        regional_turnout_draw[:, ridx] = turnout_support[rng_regional_turnout.integers(0, len(turnout_support), size=N_DRAWS)]
    local_vote_index = rng_local_vote.integers(0, len(local_vote_support), size=(N_DRAWS, len(ids)), dtype=np.int16)
    local_turnout_index = rng_local_turnout.integers(0, len(local_turnout_support), size=(N_DRAWS, len(ids)), dtype=np.int16)

    valid_fraction, valid_fraction_diagnostics = valid_fraction_model(y11, ids)
    local_outputs = []
    national_bucket_seats = np.zeros((N_DRAWS, len(BUCKETS)), dtype=np.int16)
    national_actual_seats: dict[str, np.ndarray] = {}
    region_local_residual_sum = np.zeros((N_DRAWS, len(region_order), len(BUCKETS)), dtype=float)
    region_local_valid_votes = np.zeros((N_DRAWS, len(region_order)), dtype=np.int64)
    legal_rerounded_total = 0
    legal_max_attempts = 0
    other_folded_contests = []
    maximum_share_error = 0.0

    for territory_index, historical_id in enumerate(ids):
        repo = mapping[historical_id]
        region = region_by_territory[territory_index]
        ridx = territory_region_index[territory_index]
        local_residual = local_vote_support[local_vote_index[:, territory_index]]
        region_local_residual_sum[:, ridx, :] += local_residual
        latent = vote_scale * (
            national_vote_draw
            + regional_vote_draw[:, ridx, :]
            + local_residual
        )
        shares = inv_clr(clr(y21[historical_id])[None, :] + latent)
        maximum_share_error = max(maximum_share_error, float(np.max(np.abs(shares.sum(axis=1) - 1))))
        turnout_latent = turnout_scale * (
            national_turnout_draw
            + regional_turnout_draw[:, ridx]
            + local_turnout_support[local_turnout_index[:, territory_index]]
        )
        turnout = sigmoid(logit(y21[historical_id]["turnout_rate_reported"]) + turnout_latent)
        registered = N_draws[:, territory_index]
        valid_votes = np.floor(registered * turnout * valid_fraction[historical_id]).astype(np.int64)
        valid_votes = np.clip(valid_votes, 1, registered)
        region_local_valid_votes[:, ridx] += valid_votes
        magnitude = int(repo["seats"])
        actual_seats, parties, diagnostics = simulate_contest(
            shares,
            valid_votes,
            registered,
            magnitude,
            {str(party): int(value) for party, value in y21[historical_id]["votes"].items()},
            rng_rounding,
            int(protocol["integer_vote_model"]["maximum_rerounding_attempts"]),
        )
        bucket_seats = bucket_seats_from_actual(actual_seats, parties)
        national_bucket_seats += bucket_seats
        add_actual_totals(national_actual_seats, actual_seats, parties)
        legal_rerounded_total += diagnostics["rerounded_draws"]
        legal_max_attempts = max(legal_max_attempts, diagnostics["maximum_attempts_used"])
        if diagnostics["other_folded_into_core"]:
            other_folded_contests.append(repo["constituency_id"])
        local_outputs.append(
            {
                "constituency_id": repo["constituency_id"],
                "historical_id": int(historical_id),
                "name": repo["name"],
                "region": region,
                "magnitude": magnitude,
                "vote_share_distribution": bucket_share_summary(shares),
                "turnout_distribution": quantile_summary(turnout),
                "registered_N_distribution": quantile_summary(registered),
                "valid_vote_distribution": quantile_summary(valid_votes),
                "seat_distribution": seats_summary(bucket_seats, magnitude),
                "legal_diagnostics": diagnostics,
            }
        )

    # Regional 2021 rows and structural local-to-regional bridge.
    canonical2021 = load_json(canonical2021_path)
    regional_rows = [row for row in canonical2021["rows"] if norm(row.get("list_type")) == "regionale"]
    require(len(regional_rows) == 12, "regional 2021 row count != 12")
    regional_by_region = {}
    for row in regional_rows:
        region = match_region(row.get("region") or row.get("constituency"), region_order)
        require(region not in regional_by_region, f"duplicate regional row {region}")
        regional_by_region[region] = row

    local_observed_valid_by_region = defaultdict(int)
    for historical_id in ids:
        local_observed_valid_by_region[mapping[historical_id]["region"]] += sum(int(value) for value in y21[historical_id]["votes"].values())
    raw_regional_ratio = np.asarray(
        [
            sum(int(value) for value in regional_by_region[region]["votes"].values())
            / local_observed_valid_by_region[region]
            for region in region_order
        ],
        dtype=float,
    )
    ratio_p05, ratio_p95 = np.quantile(raw_regional_ratio, [0.05, 0.95])
    regional_ratio = 0.5 * np.clip(raw_regional_ratio, ratio_p05, ratio_p95) + 0.5

    regional_outputs = []
    region_counts = {region: region_by_territory.count(region) for region in region_order}
    for region, ridx in region_index.items():
        row = regional_by_region[region]
        mean_local_residual = region_local_residual_sum[:, ridx, :] / region_counts[region]
        latent = vote_scale * (
            national_vote_draw
            + regional_vote_draw[:, ridx, :]
            + mean_local_residual
        )
        shares = inv_clr(clr(row)[None, :] + latent)
        maximum_share_error = max(maximum_share_error, float(np.max(np.abs(shares.sum(axis=1) - 1))))
        territory_indices = np.flatnonzero(territory_region_index == ridx)
        registered = N_draws[:, territory_indices].sum(axis=1)
        valid_votes = np.rint(region_local_valid_votes[:, ridx] * regional_ratio[ridx]).astype(np.int64)
        valid_votes = np.clip(valid_votes, 1, registered)
        magnitude = int(row["seats"])
        actual_seats, parties, diagnostics = simulate_contest(
            shares,
            valid_votes,
            registered,
            magnitude,
            {str(party): int(value) for party, value in row["votes"].items()},
            rng_rounding,
            int(protocol["integer_vote_model"]["maximum_rerounding_attempts"]),
        )
        bucket_seats = bucket_seats_from_actual(actual_seats, parties)
        national_bucket_seats += bucket_seats
        add_actual_totals(national_actual_seats, actual_seats, parties)
        legal_rerounded_total += diagnostics["rerounded_draws"]
        legal_max_attempts = max(legal_max_attempts, diagnostics["maximum_attempts_used"])
        if diagnostics["other_folded_into_core"]:
            other_folded_contests.append(f"REGION:{region}")
        regional_outputs.append(
            {
                "region": region,
                "magnitude": magnitude,
                "regional_to_local_valid_vote_ratio_raw_2021": float(raw_regional_ratio[ridx]),
                "regional_to_local_valid_vote_ratio_used": float(regional_ratio[ridx]),
                "vote_share_distribution": bucket_share_summary(shares),
                "registered_N_distribution": quantile_summary(registered),
                "valid_vote_distribution": quantile_summary(valid_votes),
                "seat_distribution": seats_summary(bucket_seats, magnitude),
                "legal_diagnostics": diagnostics,
            }
        )

    national_total = national_bucket_seats.sum(axis=1)
    require(np.all(national_total == 395), "national seat draws do not sum to 395")
    require(maximum_share_error < 1e-10, "share normalization error too large")
    expected_seat_sum = float(national_bucket_seats.mean(axis=0).sum())
    require(abs(expected_seat_sum - 395) < 1e-10, "expected national seats do not sum to 395")

    national_output = {
        "bucket_seat_distribution": {
            bucket: {
                **{key: float(value) for key, value in quantile_summary(national_bucket_seats[:, index]).items()},
                "mc_standard_error_expected": float(national_bucket_seats[:, index].std(ddof=1) / math.sqrt(N_DRAWS)),
            }
            for index, bucket in enumerate(BUCKETS)
        },
        "actual_party_seat_distribution_secondary": summarize_actual_national(national_actual_seats),
        "seat_total_every_draw": 395,
        "joint_bucket_seat_stream_sha256": hashlib.sha256(np.ascontiguousarray(national_bucket_seats, dtype="<i2").tobytes()).hexdigest(),
    }

    model_commit = os.environ.get("GITHUB_SHA", "")
    require(re.fullmatch(r"[0-9a-f]{40}", model_commit or "") is not None, "GITHUB_SHA missing or invalid")
    created_at = protocol["frozen_at"]
    data_manifest = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "data_cutoff": protocol["data_cutoff"],
        "inputs": {
            name: {
                "path": str(path.relative_to(ROOT.parent)),
                "sha256": sha256_path(path),
            }
            for name, path in input_paths.items()
        },
        "candidate_evidence_state": "NONE_STRUCTURAL_ONLY",
        "event_evidence_state": "NONE_STRUCTURAL_ONLY",
    }
    parameter_manifest = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "protocol_id": protocol["protocol_id"],
        "model_code_commit": model_commit,
        "vote_scale": vote_scale,
        "turnout_scale": turnout_scale,
        "uncertainty_support_sha256": library["support_sha256"],
        "N_sampler": N_diagnostics,
        "valid_fraction_model": valid_fraction_diagnostics,
        "regional_valid_ratio_model": {
            "raw": {region: float(raw_regional_ratio[index]) for index, region in enumerate(region_order)},
            "used": {region: float(regional_ratio[index]) for index, region in enumerate(region_order)},
            "winsor_p05": float(ratio_p05),
            "winsor_p95": float(ratio_p95),
            "shrinkage_to_one": 0.5,
        },
        "minor_party_rule": protocol["legal_party_mapping"],
        "integer_vote_model": protocol["integer_vote_model"],
    }
    rng_manifest = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "draws": N_DRAWS,
        "seeds": seeds,
    }

    forecast = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "snapshot_class": protocol["snapshot_class"],
        "created_at": created_at,
        "data_cutoff": protocol["data_cutoff"],
        "protocol_id": protocol["protocol_id"],
        "forecast_label": "STRUCTURAL_ONLY_NO_CANDIDATE_EVENT_OR_AGENTIC_ADJUSTMENT",
        "calibration_status": protocol["uncertainty"]["calibration_label"],
        "draws": N_DRAWS,
        "party_buckets": list(BUCKETS),
        "local_92": local_outputs,
        "regional_12": regional_outputs,
        "national_395": national_output,
        "diagnostics": {
            "maximum_share_normalization_error": maximum_share_error,
            "N92": N_diagnostics,
            "legal_rerounded_contest_draws": legal_rerounded_total,
            "legal_rerounding_rate_per_contest_draw": legal_rerounded_total / (N_DRAWS * 104),
            "legal_maximum_attempts_used": legal_max_attempts,
            "legal_unresolved_after_retries": 0,
            "other_folded_contests": other_folded_contests,
            "other_folded_contest_count": len(other_folded_contests),
            "expected_national_seat_sum": expected_seat_sum,
            "known_regional_data_anomalies": ["Casablanca-Settat", "Marrakech-Safi"],
        },
        "mandatory_calibration_disclosure": protocol["uncertainty"]["mandatory_disclosure"],
        "known_limitations": [
            "F-1 persists the 2021 structural mean and contains no 2026 candidate, defection, endorsement or event adjustment.",
            "Local registered-voter counts are latent constrained draws, not official 2026 local counts.",
            "Vote uncertainty is calibrated to aggregate componentwise coverage; party-level historical coverage is heterogeneous and published in uncertainty_calibration.json.",
            "The selected coherent vote hierarchy had a worse retrospective Energy Score than the non-hierarchical flat residual bootstrap; coherence and coverage were prioritized under the frozen rule.",
            "The invalid-ballot/valid-vote fraction is a shrunk 2011 structural persistence without an additional F-1 shock.",
            "The regional ballot uses a structural bridge from local innovations because only 2021 supplies the current regional-list ballot.",
            "2021 contest/list availability is used; verified 2026 list changes belong to B2/F0 or later snapshots.",
        ],
    }

    FORECAST_DIR.mkdir(parents=True, exist_ok=False)
    DATA_MANIFEST_PATH.write_text(json.dumps(data_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    PARAMETER_MANIFEST_PATH.write_text(json.dumps(parameter_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    RNG_MANIFEST_PATH.write_text(json.dumps(rng_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    FORECAST_PATH.write_text(json.dumps(forecast, ensure_ascii=False, indent=2), encoding="utf-8")

    data_hash = sha256_path(DATA_MANIFEST_PATH)
    parameter_hash = sha256_path(PARAMETER_MANIFEST_PATH)
    rng_hash = sha256_path(RNG_MANIFEST_PATH)
    forecast_hash = sha256_path(FORECAST_PATH)
    geometry_hash = sha256_path(geometry_path)
    legal_hash = sha256_path(legal_path)
    snapshot_manifest = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "snapshot_class": protocol["snapshot_class"],
        "created_at": created_at,
        "data_cutoff": protocol["data_cutoff"],
        "protocol_id": protocol["protocol_id"],
        "model_code_commit": model_commit,
        "data_manifest_hash": data_hash,
        "parameter_manifest_hash": parameter_hash,
        "rng_seed_manifest": {"path": str(RNG_MANIFEST_PATH.relative_to(ROOT.parent)), "sha256": rng_hash},
        "monte_carlo_draws": N_DRAWS,
        "legal_allocator_version": legal_hash,
        "geometry_certificate_hash": geometry_hash,
        "registered_N_state": "LATENT_CONSTRAINED_NOT_OFFICIAL",
        "candidate_evidence_state": "NONE_STRUCTURAL_ONLY",
        "event_evidence_state": "NONE_STRUCTURAL_ONLY",
        "forecast_artifact_hash": forecast_hash,
        "calibration_status": protocol["uncertainty"]["calibration_label"],
        "known_limitations": forecast["known_limitations"],
        "artifact_paths": {
            "forecast": str(FORECAST_PATH.relative_to(ROOT.parent)),
            "data_manifest": str(DATA_MANIFEST_PATH.relative_to(ROOT.parent)),
            "parameter_manifest": str(PARAMETER_MANIFEST_PATH.relative_to(ROOT.parent)),
            "rng_manifest": str(RNG_MANIFEST_PATH.relative_to(ROOT.parent)),
        },
    }
    SNAPSHOT_MANIFEST_PATH.write_text(json.dumps(snapshot_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    simulation_certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-FMINUS1-SIMULATION-CERTIFICATE-V1",
        "snapshot_id": "F-1",
        "gate": "PASS",
        "draws": N_DRAWS,
        "local_contests": 92,
        "regional_contests": 12,
        "local_seats": 305,
        "regional_seats": 90,
        "national_seats_every_draw": 395,
        "maximum_share_normalization_error": maximum_share_error,
        "N92_exact_sum_every_draw": True,
        "N92_stream_sha256": N_diagnostics["stream_sha256"],
        "joint_bucket_seat_stream_sha256": national_output["joint_bucket_seat_stream_sha256"],
        "legal_unresolved_after_retries": 0,
        "legal_rerounded_contest_draws": legal_rerounded_total,
        "legal_rerounding_rate_per_contest_draw": legal_rerounded_total / (N_DRAWS * 104),
        "legal_maximum_attempts_used": legal_max_attempts,
        "vectorized_scalar_legal_spot_checks": 104 * 5,
        "forecast_sha256": forecast_hash,
        "snapshot_manifest_sha256": sha256_path(SNAPSHOT_MANIFEST_PATH),
        "model_code_commit": model_commit,
    }
    SIMULATION_CERTIFICATE_PATH.write_text(json.dumps(simulation_certificate, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        json.dumps(
            {
                "gate": "PASS",
                "snapshot": "F-1",
                "draws": N_DRAWS,
                "local": 92,
                "regional": 12,
                "seats_every_draw": 395,
                "legal_rerounded": legal_rerounded_total,
                "legal_unresolved": 0,
                "forecast_hash": forecast_hash,
                "seat_stream_hash": national_output["joint_bucket_seat_stream_sha256"],
                "expected_bucket_seats": {
                    bucket: national_output["bucket_seat_distribution"][bucket]["mean"]
                    for bucket in BUCKETS
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
