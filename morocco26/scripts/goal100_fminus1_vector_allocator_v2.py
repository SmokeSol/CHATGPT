#!/usr/bin/env python3
"""Vectorized exact-equivalent implementation of the Goal100 2026 allocator.

Correction V2: zero-vote lists are excluded from quotient/remainder groups, exactly
as in ``legal_allocator_2026.allocate_2026``. V1 incorrectly left zero-vote lists
in the vectorized remainder ranking, creating artificial binding ties.
"""
from __future__ import annotations

import numpy as np


def vectorized_allocate(
    votes: np.ndarray,
    registered: np.ndarray,
    magnitude: int,
) -> tuple[np.ndarray, np.ndarray]:
    registered = np.asarray(registered, dtype=np.int64)
    votes = np.asarray(votes, dtype=np.int64)
    if votes.ndim != 2 or registered.ndim != 1 or len(votes) != len(registered):
        raise ValueError("invalid vote/registered shapes")
    if magnitude <= 0 or np.any(registered <= 0):
        raise ValueError("magnitude and registered must be positive")
    if np.any(votes < 0):
        raise ValueError("negative simulated votes")
    if np.any(votes.sum(axis=1) > registered):
        raise ValueError("simulated votes exceed registered N")

    n_rows, n_parties = votes.shape
    positive = votes > 0
    positive_count = positive.sum(axis=1)
    seats = np.zeros_like(votes, dtype=np.int64)
    unresolved = np.zeros(n_rows, dtype=bool)

    # No valid-list votes: scalar allocator returns NO_VALID_VOTES.
    unresolved[positive_count == 0] = True

    # Unique positive list: exact Article 84/91 one-fifth gate.
    unique_rows = np.flatnonzero(positive_count == 1)
    if len(unique_rows):
        unique_party = np.argmax(positive[unique_rows], axis=1)
        unique_votes = votes[unique_rows, unique_party]
        threshold_met = 5 * unique_votes >= registered[unique_rows]
        passed_rows = unique_rows[threshold_met]
        passed_party = unique_party[threshold_met]
        seats[passed_rows, passed_party] = int(magnitude)
        unresolved[unique_rows[~threshold_met]] = True

    # Normal multi-list quotient + largest-remainder branch.
    multi_rows = np.flatnonzero(positive_count >= 2)
    if len(multi_rows):
        v = votes[multi_rows]
        reg = registered[multi_rows]
        pos = positive[multi_rows]
        base = ((v * int(magnitude)) // reg[:, None]) * pos
        remainder = v * int(magnitude) - base * reg[:, None]
        # Lists with zero votes do not exist in the scalar positive-list map.
        remainder = np.where(pos, remainder, -1)
        left = int(magnitude) - base.sum(axis=1)
        if np.any(left < 0) or np.any(left > int(magnitude)):
            raise AssertionError("invalid remaining-seat count")

        local_unresolved = np.zeros(len(multi_rows), dtype=bool)
        # If there are more remaining seats than positive lists, the scalar
        # allocator ends UNFILLED_SEATS_EXCEPTIONAL after exhausting all lists.
        local_unresolved[left > pos.sum(axis=1)] = True
        order = np.argsort(-remainder, axis=1, kind="stable")

        for local_index in np.flatnonzero((left > 0) & ~local_unresolved):
            need = int(left[local_index])
            cutoff = remainder[local_index, order[local_index, need - 1]]
            greater = int(np.sum(pos[local_index] & (remainder[local_index] > cutoff)))
            equal = int(np.sum(pos[local_index] & (remainder[local_index] == cutoff)))
            if greater < need < greater + equal:
                local_unresolved[local_index] = True

        resolved = ~local_unresolved
        multi_seats = base.copy()
        for rank in range(int(left.max(initial=0))):
            local_indices = np.flatnonzero((left > rank) & resolved)
            if len(local_indices):
                multi_seats[local_indices, order[local_indices, rank]] += 1
        seats[multi_rows] = multi_seats
        unresolved[multi_rows] = local_unresolved

    return seats, unresolved
