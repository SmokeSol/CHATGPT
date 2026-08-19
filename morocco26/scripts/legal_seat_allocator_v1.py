#!/usr/bin/env python3
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping


class SeatAllocationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Regime:
    year: int
    threshold: float
    quotient_basis: str  # QUALIFIED_VOTES or REGISTERED_VOTERS


REGIMES: dict[int, Regime] = {
    2007: Regime(2007, 0.06, "QUALIFIED_VOTES"),
    2011: Regime(2011, 0.06, "QUALIFIED_VOTES"),
    2016: Regime(2016, 0.03, "QUALIFIED_VOTES"),
    2021: Regime(2021, 0.00, "REGISTERED_VOTERS"),
    2026: Regime(2026, 0.00, "REGISTERED_VOTERS"),
}


def _clean_votes(votes: Mapping[str, Any]) -> dict[str, float]:
    out: dict[str, float] = {}
    for party, raw in votes.items():
        if raw is None or raw == "":
            continue
        v = float(raw)
        if not math.isfinite(v) or v < 0:
            raise SeatAllocationError(f"INVALID_VOTE:{party}:{raw}")
        if v > 0:
            out[str(party)] = v
    if not out:
        raise SeatAllocationError("NO_POSITIVE_LIST_VOTES")
    return out


def allocate(
    *,
    year: int,
    votes: Mapping[str, Any],
    seats: int,
    registered_voters: int | float | None = None,
    tie_tolerance: float = 1e-12,
) -> dict[str, Any]:
    """Apply the frozen legal seat-count rule for one constituency.

    This function does not choose candidates within a list. If an exact
    largest-remainder tie crosses the last available seat, it returns an
    explicit unresolved status instead of inventing an alphabetical/random
    tie break.
    """
    if year not in REGIMES:
        raise SeatAllocationError(f"UNSUPPORTED_REGIME:{year}")
    if int(seats) != seats or int(seats) <= 0:
        raise SeatAllocationError(f"INVALID_SEAT_COUNT:{seats}")
    seats = int(seats)
    regime = REGIMES[year]
    vals = _clean_votes(votes)
    expressed = float(sum(vals.values()))

    if regime.threshold > 0:
        eligible = {
            p: v for p, v in vals.items()
            if (v / expressed) + 1e-15 >= regime.threshold
        }
    else:
        eligible = dict(vals)
    if not eligible:
        raise SeatAllocationError("NO_ELIGIBLE_LISTS")

    if regime.quotient_basis == "QUALIFIED_VOTES":
        quotient_numerator = float(sum(eligible.values()))
    elif regime.quotient_basis == "REGISTERED_VOTERS":
        if registered_voters is None or registered_voters == "":
            return {
                "status": "BLOCKED_REGISTERED_VOTERS_REQUIRED",
                "year": year,
                "seats": seats,
                "threshold": regime.threshold,
                "quotient_basis": regime.quotient_basis,
                "expressed_list_votes": expressed,
            }
        rv = float(registered_voters)
        if not math.isfinite(rv) or rv <= 0 or rv + 1e-9 < expressed:
            raise SeatAllocationError(
                f"INVALID_REGISTERED_VOTERS:{registered_voters}:EXPRESSED={expressed}"
            )
        quotient_numerator = rv
    else:
        raise SeatAllocationError(f"BAD_REGIME_BASIS:{regime.quotient_basis}")

    quotient = quotient_numerator / seats
    if quotient <= 0:
        raise SeatAllocationError("NONPOSITIVE_QUOTIENT")

    allocation = {p: int(math.floor(v / quotient + 1e-14)) for p, v in eligible.items()}
    initially_allocated = int(sum(allocation.values()))
    if initially_allocated > seats:
        raise SeatAllocationError(
            f"INITIAL_ALLOCATION_EXCEEDS_MAGNITUDE:{initially_allocated}>{seats}"
        )
    remaining = seats - initially_allocated
    remainders = {p: float(v - allocation[p] * quotient) for p, v in eligible.items()}

    if remaining > 0:
        if remaining > len(eligible):
            return {
                "status": "BLOCKED_SPECIAL_CASE_INSUFFICIENT_LISTS_FOR_REMAINDERS",
                "year": year,
                "seats": seats,
                "threshold": regime.threshold,
                "quotient_basis": regime.quotient_basis,
                "quotient": quotient,
                "initial_allocation": allocation,
                "remaining_seats": remaining,
            }
        ordered = sorted(eligible, key=lambda p: (-remainders[p], -eligible[p], p))
        if remaining < len(ordered):
            boundary_hi = remainders[ordered[remaining - 1]]
            boundary_lo = remainders[ordered[remaining]]
            if math.isclose(boundary_hi, boundary_lo, rel_tol=0.0, abs_tol=tie_tolerance):
                tied = sorted(
                    p for p in ordered
                    if math.isclose(remainders[p], boundary_hi, rel_tol=0.0, abs_tol=tie_tolerance)
                )
                return {
                    "status": "UNRESOLVED_LEGAL_TIE",
                    "year": year,
                    "seats": seats,
                    "threshold": regime.threshold,
                    "quotient_basis": regime.quotient_basis,
                    "quotient": quotient,
                    "initial_allocation": allocation,
                    "remaining_seats": remaining,
                    "tied_lists": tied,
                    "tied_remainder": boundary_hi,
                }
        for p in ordered[:remaining]:
            allocation[p] += 1

    if sum(allocation.values()) != seats:
        raise SeatAllocationError("FINAL_SEAT_SUM_MISMATCH")

    return {
        "status": "ALLOCATED",
        "year": year,
        "seats": seats,
        "threshold": regime.threshold,
        "quotient_basis": regime.quotient_basis,
        "expressed_list_votes": expressed,
        "qualified_list_votes": float(sum(eligible.values())),
        "registered_voters": None if registered_voters is None else float(registered_voters),
        "quotient": float(quotient),
        "excluded_below_threshold": sorted(set(vals) - set(eligible)),
        "remainders": remainders,
        "allocation": allocation,
    }


__all__ = ["REGIMES", "Regime", "SeatAllocationError", "allocate"]
