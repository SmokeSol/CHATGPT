#!/usr/bin/env python3
"""Runtime V4 for the frozen F-1 protocol V1.1.

This module is intentionally separate from the rejected V1 runtime. It provides:
- robust V2 simplex projection;
- contest-active list projection;
- one structural support vote per observed eligible list;
- exact quotient/remainder allocation;
- exchangeable-age marginalization only at a binding statutory tie.

No forecast is registered by this module. The caller runs the frozen engine, then
re-hashes every generated manifest before a separate registration transition.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

import goal100_run_fminus1 as engine
from goal100_fminus1_vector_allocator_v2 import vectorized_allocate

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
PROTOCOL_PATH = G100 / "fminus1_protocol_v1_1.json"
UNCERTAINTY_PATH = G100 / "uncertainty_calibration_v2.json"

PROTOCOL = json.loads(PROTOCOL_PATH.read_text(encoding="utf-8"))
UNCERTAINTY = json.loads(UNCERTAINTY_PATH.read_text(encoding="utf-8"))
FLOOR = float(PROTOCOL["uncertainty"]["robust_projection"]["bucket_floor"])
CAP = float(PROTOCOL["uncertainty"]["robust_projection"]["max_bucket_share_cap"])
AGE_PRIOR_SEED = int(PROTOCOL["monte_carlo"]["seed_manifest"]["statutory_age_prior"])
AGE_RNG = np.random.default_rng(AGE_PRIOR_SEED)
RAW_INV_CLR = engine.inv_clr
ORIGINAL_LOAD_JSON = engine.load_json


def robust_project(probabilities: np.ndarray) -> np.ndarray:
    values = np.asarray(probabilities, dtype=float)
    if values.ndim != 2 or values.shape[1] < 2:
        raise ValueError("robust projection requires a 2D multi-list probability matrix")
    if values.shape[1] * FLOOR >= 1:
        raise ValueError("active-list floor is infeasible")
    if np.any(~np.isfinite(values)) or np.any(values < 0):
        raise ValueError("invalid active-list probabilities")
    totals = values.sum(axis=1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError("active-list probability row sums to zero")
    values = values / totals
    values = FLOOR + (1.0 - values.shape[1] * FLOOR) * values

    affected = values.max(axis=1) > CAP
    if np.any(affected):
        subset = values[affected]
        low = np.zeros(len(subset), dtype=float)
        high = np.ones(len(subset), dtype=float)
        for _ in range(60):
            tau = (low + high) / 2.0
            powered = subset ** tau[:, None]
            projected = powered / powered.sum(axis=1, keepdims=True)
            above = projected.max(axis=1) > CAP
            high[above] = tau[above]
            low[~above] = tau[~above]
        tau = (low + high) / 2.0
        powered = subset ** tau[:, None]
        values[affected] = powered / powered.sum(axis=1, keepdims=True)

    values /= values.sum(axis=1, keepdims=True)
    engine.require(float(values.min()) >= FLOOR - 1e-12, "active-list robust floor violated")
    engine.require(float(values.max()) <= CAP + 1e-10, "active-list concentration cap violated")
    engine.require(float(np.max(np.abs(values.sum(axis=1) - 1))) < 1e-10, "active-list probabilities not normalized")
    return values


def robust_inv_clr(latent: np.ndarray) -> np.ndarray:
    return robust_project(RAW_INV_CLR(latent))


def build_actual_probabilities(
    shares: np.ndarray,
    raw_votes: dict[str, int],
) -> tuple[np.ndarray, list[str], dict]:
    positive = {str(party): int(value) for party, value in raw_votes.items() if int(value or 0) > 0}
    active_core = [party for party in engine.CORE if positive.get(party, 0) > 0]
    minor = sorted(party for party in positive if party not in engine.CORE)
    category_names = [*active_core]
    category_columns = [shares[:, engine.CORE.index(party)] for party in active_core]
    if minor:
        category_names.append("OTHER")
        category_columns.append(shares[:, -1])
    engine.require(len(category_names) >= 2, "F-1 active bucket set has fewer than two categories")

    category_matrix = np.column_stack(category_columns)
    projected_categories = robust_project(category_matrix)

    # Mutate the caller's 9-bucket array so published vote distributions obey
    # contest list availability rather than retaining mass on an absent list.
    shares[:, :] = 0.0
    for index, party in enumerate(active_core):
        shares[:, engine.CORE.index(party)] = projected_categories[:, index]
    if minor:
        other_index = len(active_core)
        shares[:, -1] = projected_categories[:, other_index]
        minor_votes = np.asarray([positive[party] for party in minor], dtype=float)
        minor_weights = minor_votes / minor_votes.sum()
        actual = np.column_stack(
            [
                *[projected_categories[:, index] for index in range(len(active_core))],
                *[
                    projected_categories[:, other_index] * minor_weights[index]
                    for index in range(len(minor))
                ],
            ]
        )
        parties = [*active_core, *minor]
    else:
        actual = projected_categories
        parties = [*active_core]

    engine.require(len(parties) == actual.shape[1], "active party/probability shape mismatch")
    engine.require(float(np.max(np.abs(actual.sum(axis=1) - 1))) < 1e-10, "actual active-list probabilities not normalized")
    engine.require(float(np.max(np.abs(shares.sum(axis=1) - 1))) < 1e-10, "published active-bucket shares not normalized")
    return actual, parties, {
        "active_core_parties": active_core,
        "minor_parties": minor,
        "active_list_count": len(parties),
        "inactive_core_parties": [party for party in engine.CORE if party not in active_core],
        "other_absent_and_dropped": not bool(minor),
        "other_folded_into_core": False,
        "active_bucket_min_share": float(projected_categories.min()),
        "active_bucket_max_share": float(projected_categories.max()),
        "active_bucket_floor": FLOOR,
        "active_bucket_cap": CAP,
    }


def support_vote_round(
    probabilities: np.ndarray,
    valid_votes: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    active_lists = probabilities.shape[1]
    engine.require(np.all(valid_votes >= active_lists), "valid votes below active-list support requirement")
    remaining = valid_votes.astype(np.int64) - active_lists
    expected_remaining = probabilities * remaining[:, None]
    counts = engine.balanced_round(expected_remaining, remaining, rng)
    counts += 1
    engine.require(np.all(counts > 0), "support-vote rounding produced a zero-vote eligible list")
    engine.require(np.all(counts.sum(axis=1) == valid_votes), "support-vote rounding failed exact total")
    return counts


def resolve_binding_tie_by_exchangeable_age(
    votes: np.ndarray,
    registered: int,
    magnitude: int,
) -> tuple[np.ndarray, dict]:
    values = np.asarray(votes, dtype=np.int64)
    engine.require(np.all(values > 0), "age-prior allocator received an inactive list")
    allocation = (values * int(magnitude)) // int(registered)
    remainders = values * int(magnitude) - allocation * int(registered)
    seats_left = int(magnitude - int(allocation.sum()))
    engine.require(0 <= seats_left <= magnitude, "invalid quotient allocation before age prior")
    groups: dict[int, list[int]] = {}
    for index, remainder in enumerate(remainders.tolist()):
        groups.setdefault(int(remainder), []).append(index)

    prior_used = False
    binding_group_size = 0
    seats_marginalized = 0
    for remainder in sorted(groups, reverse=True):
        if seats_left <= 0:
            break
        group = groups[remainder]
        if len(group) <= seats_left:
            allocation[group] += 1
            seats_left -= len(group)
            continue
        prior_used = True
        binding_group_size = len(group)
        seats_marginalized = seats_left
        chosen = AGE_RNG.choice(np.asarray(group, dtype=int), size=seats_left, replace=False)
        allocation[chosen] += 1
        seats_left = 0
        break

    engine.require(seats_left == 0, "exchangeable-age prior did not fill the district")
    engine.require(int(allocation.sum()) == magnitude, "exchangeable-age allocation magnitude mismatch")
    return allocation, {
        "prior_used": prior_used,
        "binding_group_size": binding_group_size,
        "seats_marginalized": seats_marginalized,
    }


def simulate_contest(
    shares: np.ndarray,
    valid_votes: np.ndarray,
    registered: np.ndarray,
    magnitude: int,
    raw_votes: dict[str, int],
    rng: np.random.Generator,
    max_attempts: int,
) -> tuple[np.ndarray, list[str], dict]:
    del max_attempts  # V1.1 uses no rerounding loop.
    probabilities, parties, diagnostics = build_actual_probabilities(shares, raw_votes)
    active_lists = len(parties)
    engine.require(active_lists >= magnitude, "observed eligible lists fewer than district seats")
    counts = support_vote_round(probabilities, valid_votes, rng)

    seats, binding = vectorized_allocate(counts, registered, magnitude)
    binding_rows = np.flatnonzero(binding)
    age_prior_group_sizes: list[int] = []
    age_prior_seats: list[int] = []
    for row_index in binding_rows.tolist():
        allocation, event = resolve_binding_tie_by_exchangeable_age(
            counts[row_index],
            int(registered[row_index]),
            int(magnitude),
        )
        engine.require(event["prior_used"], "vector allocator flagged a non-binding/non-age state")
        seats[row_index] = allocation
        age_prior_group_sizes.append(int(event["binding_group_size"]))
        age_prior_seats.append(int(event["seats_marginalized"]))

    engine.require(np.all(seats.sum(axis=1) == magnitude), "contest does not allocate exact magnitude")

    scalar_complete_checks = 0
    scalar_tie_checks = 0
    non_binding_rows = np.flatnonzero(~binding)
    for row_index in non_binding_rows[np.linspace(0, len(non_binding_rows) - 1, min(5, len(non_binding_rows)), dtype=int)] if len(non_binding_rows) else []:
        vote_dict = {party: int(counts[row_index, index]) for index, party in enumerate(parties)}
        scalar = engine.allocate_2026(vote_dict, int(registered[row_index]), int(magnitude))
        engine.require(scalar.complete, f"scalar non-tie check failed: {scalar.status}")
        expected = {party: int(seats[row_index, index]) for index, party in enumerate(parties) if seats[row_index, index] > 0}
        engine.require(scalar.seats_by_list == expected, "vector/scalar non-tie allocation disagreement")
        scalar_complete_checks += 1

    for row_index in binding_rows[: min(5, len(binding_rows))]:
        vote_dict = {party: int(counts[row_index, index]) for index, party in enumerate(parties)}
        scalar = engine.allocate_2026(vote_dict, int(registered[row_index]), int(magnitude))
        engine.require(
            scalar.status == "UNRESOLVED_STATUTORY_TIE",
            f"binding row did not reach scalar statutory tie: {scalar.status}",
        )
        engine.require(any(event.get("kind") == "equal_remainder_binding" for event in scalar.tie_events), "scalar tie event missing binding group")
        scalar_tie_checks += 1

    diagnostics.update(
        {
            "support_vote_per_active_list": 1,
            "zero_vote_eligible_lists": 0,
            "unique_list_threshold_failures": 0,
            "unfilled_seat_exceptions": 0,
            "statutory_age_prior_draws": int(len(binding_rows)),
            "statutory_age_prior_rate": float(len(binding_rows) / len(counts)),
            "statutory_age_prior_max_group_size": max(age_prior_group_sizes, default=0),
            "statutory_age_prior_seats_marginalized": int(sum(age_prior_seats)),
            "statutory_age_prior_seed": AGE_PRIOR_SEED,
            "scalar_complete_spot_checks": scalar_complete_checks,
            "scalar_binding_tie_spot_checks": scalar_tie_checks,
            "rerounded_draws": 0,
            "maximum_attempts_used": 0,
            "unresolved_after_retries": 0,
            "unresolved_after_age_prior": 0,
        }
    )
    return seats, parties, diagnostics


def patched_load_json(path: Path):
    path = Path(path)
    if path.name == "fminus1_protocol_v1.json":
        compatibility = copy.deepcopy(PROTOCOL)
        compatibility["integer_vote_model"]["maximum_rerounding_attempts"] = 0
        return compatibility
    if path.name == "uncertainty_calibration.json":
        return copy.deepcopy(UNCERTAINTY)
    return ORIGINAL_LOAD_JSON(path)


def install() -> None:
    engine.load_json = patched_load_json
    engine.inv_clr = robust_inv_clr
    engine.build_actual_probabilities = build_actual_probabilities
    engine.simulate_contest = simulate_contest
