#!/usr/bin/env python3
"""Diagnostic F-1 run that exposes persistent statutory-tie structure."""
from __future__ import annotations

import json

import numpy as np

import goal100_run_fminus1 as engine
from goal100_fminus1_vector_allocator_v2 import vectorized_allocate

engine.vectorized_allocate = vectorized_allocate
CALL_INDEX = 0


def diagnostic_simulate_contest(
    shares: np.ndarray,
    valid_votes: np.ndarray,
    registered: np.ndarray,
    magnitude: int,
    raw_votes: dict[str, int],
    rng: np.random.Generator,
    max_attempts: int,
):
    global CALL_INDEX
    call_index = CALL_INDEX
    CALL_INDEX += 1
    probabilities, parties, diagnostics = engine.build_actual_probabilities(shares, raw_votes)
    expected = probabilities * valid_votes[:, None]
    counts = engine.balanced_round(expected, valid_votes, rng)
    seats, unresolved = vectorized_allocate(counts, registered, magnitude)
    initial_unresolved = int(unresolved.sum())
    attempts_used = 0
    while unresolved.any() and attempts_used < max_attempts:
        attempts_used += 1
        rows = np.flatnonzero(unresolved)
        replacement = engine.balanced_round(expected[rows], valid_votes[rows], rng)
        counts[rows] = replacement
        replacement_seats, replacement_unresolved = vectorized_allocate(
            replacement,
            registered[rows],
            magnitude,
        )
        seats[rows] = replacement_seats
        unresolved[rows] = replacement_unresolved

    if unresolved.any():
        rows = np.flatnonzero(unresolved)
        details = []
        for row_index in rows[:10]:
            vote_dict = {
                party: int(counts[row_index, party_index])
                for party_index, party in enumerate(parties)
                if int(counts[row_index, party_index]) > 0
            }
            scalar = engine.allocate_2026(
                vote_dict,
                int(registered[row_index]),
                int(magnitude),
            )
            details.append(
                {
                    "draw_index": int(row_index),
                    "registered": int(registered[row_index]),
                    "valid_votes": int(valid_votes[row_index]),
                    "magnitude": int(magnitude),
                    "parties": parties,
                    "counts": counts[row_index].astype(int).tolist(),
                    "expected": expected[row_index].astype(float).tolist(),
                    "fractional_parts": (expected[row_index] - np.floor(expected[row_index])).astype(float).tolist(),
                    "positive_parties": vote_dict,
                    "scalar_status": scalar.status,
                    "scalar_allocated": scalar.seats_by_list,
                    "scalar_unallocated": scalar.unallocated_seats,
                    "scalar_tie_events": list(scalar.tie_events),
                }
            )
        report = {
            "diagnostic": "PERSISTENT_STATUTORY_TIE_AFTER_BALANCED_REROUNDING",
            "contest_call_index_zero_based": call_index,
            "contest_scope": "LOCAL" if call_index < 92 else "REGIONAL",
            "contest_position": call_index if call_index < 92 else call_index - 92,
            "initial_unresolved_draws": initial_unresolved,
            "persistent_unresolved_draws": int(unresolved.sum()),
            "attempts": attempts_used,
            "examples": details,
        }
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
        raise SystemExit("FMINUS1_DIAGNOSTIC_STOP_AFTER_PERSISTENT_TIE_REPORT")

    for row_index in np.linspace(0, len(counts) - 1, 5, dtype=int):
        vote_dict = {
            party: int(counts[row_index, index])
            for index, party in enumerate(parties)
            if counts[row_index, index] > 0
        }
        scalar = engine.allocate_2026(vote_dict, int(registered[row_index]), int(magnitude))
        engine.require(scalar.complete, f"scalar legal spot-check failed: {scalar.status}")
        expected_key = {
            party: int(seats[row_index, index])
            for index, party in enumerate(parties)
            if seats[row_index, index] > 0
        }
        engine.require(scalar.seats_by_list == expected_key, "vectorized/scalar allocator disagreement")

    diagnostics.update(
        {
            "rerounded_draws": initial_unresolved,
            "maximum_attempts_used": attempts_used,
            "unresolved_after_retries": 0,
        }
    )
    return seats, parties, diagnostics


engine.simulate_contest = diagnostic_simulate_contest


if __name__ == "__main__":
    engine.main()
