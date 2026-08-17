#!/usr/bin/env python3
"""Randomized equivalence test: vector allocator V2 vs scalar legal oracle."""
from __future__ import annotations

from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco26.legal_allocator_2026 import allocate_2026  # noqa: E402
from goal100_fminus1_vector_allocator_v2 import vectorized_allocate  # noqa: E402

SEED = 26092359
ROWS_PER_MAGNITUDE = 2000
PARTIES = [f"P{index}" for index in range(12)]


def main() -> None:
    rng = np.random.default_rng(SEED)
    tested = 0
    complete = 0
    incomplete = 0
    zero_vote_rows = 0

    for magnitude in range(2, 7):
        registered = rng.integers(100, 500_000, size=ROWS_PER_MAGNITUDE, dtype=np.int64)
        valid_total = np.empty(ROWS_PER_MAGNITUDE, dtype=np.int64)
        # Mix realistic and deliberately pathological low-valid-vote cases.
        low = rng.random(ROWS_PER_MAGNITUDE) < 0.15
        valid_total[low] = rng.integers(0, 25, size=int(low.sum()), dtype=np.int64)
        valid_total[~low] = (
            registered[~low]
            * rng.uniform(0.15, 0.80, size=int((~low).sum()))
        ).astype(np.int64)
        valid_total = np.minimum(valid_total, registered)

        concentration = rng.uniform(0.05, 3.0, size=(ROWS_PER_MAGNITUDE, len(PARTIES)))
        probability = concentration / concentration.sum(axis=1, keepdims=True)
        votes = np.vstack(
            [rng.multinomial(int(valid_total[index]), probability[index]) for index in range(ROWS_PER_MAGNITUDE)]
        ).astype(np.int64)
        zero_vote_rows += int(np.sum(np.any(votes == 0, axis=1)))

        vector_seats, vector_unresolved = vectorized_allocate(votes, registered, magnitude)
        for row_index in range(ROWS_PER_MAGNITUDE):
            vote_dict = {
                party: int(votes[row_index, party_index])
                for party_index, party in enumerate(PARTIES)
                if int(votes[row_index, party_index]) > 0
            }
            scalar = allocate_2026(vote_dict, int(registered[row_index]), magnitude)
            tested += 1
            if scalar.complete:
                complete += 1
                if vector_unresolved[row_index]:
                    raise AssertionError(
                        f"vector unresolved but scalar complete: m={magnitude} row={row_index} "
                        f"status={scalar.status} votes={vote_dict} N={registered[row_index]}"
                    )
                expected = {
                    party: int(vector_seats[row_index, party_index])
                    for party_index, party in enumerate(PARTIES)
                    if int(vector_seats[row_index, party_index]) > 0
                }
                if scalar.seats_by_list != expected:
                    raise AssertionError(
                        f"allocation mismatch: m={magnitude} row={row_index} "
                        f"scalar={scalar.seats_by_list} vector={expected} votes={vote_dict} "
                        f"N={registered[row_index]}"
                    )
            else:
                incomplete += 1
                if not vector_unresolved[row_index]:
                    raise AssertionError(
                        f"vector resolved but scalar incomplete: m={magnitude} row={row_index} "
                        f"status={scalar.status} votes={vote_dict} N={registered[row_index]}"
                    )

    print("VECTOR_ALLOCATOR_EQUIVALENCE_PASS")
    print(f"tested={tested}")
    print(f"complete={complete}")
    print(f"incomplete={incomplete}")
    print(f"rows_with_at_least_one_zero_vote_list={zero_vote_rows}")
    print(f"seed={SEED}")


if __name__ == "__main__":
    main()
