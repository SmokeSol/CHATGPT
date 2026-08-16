#!/usr/bin/env python3
"""Deterministic statutory smoke tests for legal_allocator_2026."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from morocco26.legal_allocator_2026 import (  # noqa: E402
    STATUS_LOTTERY_REQUIRED,
    STATUS_OK,
    STATUS_OK_AGE_TIEBREAK,
    STATUS_OK_UNIQUE,
    STATUS_TIE_UNRESOLVED,
    STATUS_UNIQUE_FAIL,
    allocate_2026,
)


def check(name, condition):
    if not condition:
        raise AssertionError(name)
    print(f"PASS {name}")


def main():
    r = allocate_2026({"A": 300, "B": 250, "C": 200, "D": 100}, 1000, 4)
    check("largest_remainder", r.status == STATUS_OK and r.seats_by_list == {"A": 1, "B": 1, "C": 1, "D": 1})

    # N/m = 100. A crosses the quotient twice; B once; last seat is C's remainder.
    r = allocate_2026({"A": 230, "B": 145, "C": 90, "D": 35}, 500, 5)
    check("quotient_plus_remainder", r.complete and r.seats_by_list == {"A": 2, "B": 1, "C": 1, "D": 1})

    r = allocate_2026({"A": 199}, 1000, 3)
    check("unique_list_one_fifth_fail", r.status == STATUS_UNIQUE_FAIL and r.allocated_seats == 0)

    r = allocate_2026({"A": 200}, 1000, 3)
    check("unique_list_one_fifth_exact", r.status == STATUS_OK_UNIQUE and r.seats_by_list == {"A": 3})

    r = allocate_2026({"A": 200, "B": 200, "C": 100}, 1000, 1)
    check("single_member_tie_fails_closed", r.status == STATUS_TIE_UNRESOLVED and r.unallocated_seats == 1)

    r = allocate_2026(
        {"A": 200, "B": 200, "C": 100}, 1000, 1,
        {"A": ["1980-01-01"], "B": ["1990-01-01"], "C": ["1970-01-01"]},
    )
    check("single_member_youngest", r.status == STATUS_OK_AGE_TIEBREAK and r.seats_by_list == {"B": 1})

    # Four zero-base lists tie on the same remainder for only 3 seats.
    r = allocate_2026({"A": 100, "B": 100, "C": 100, "D": 100}, 1000, 3)
    check("remainder_tie_fails_closed", r.status == STATUS_TIE_UNRESOLVED and r.unallocated_seats == 3)

    r = allocate_2026(
        {"A": 100, "B": 100, "C": 100, "D": 100}, 1000, 3,
        {
            "A": ["1970-01-01"],
            "B": ["1980-01-01"],
            "C": ["1990-01-01"],
            "D": ["2000-01-01"],
        },
    )
    check("remainder_tie_youngest", r.status == STATUS_OK_AGE_TIEBREAK and r.seats_by_list == {"B": 1, "C": 1, "D": 1})

    r = allocate_2026(
        {"A": 100, "B": 100, "C": 100, "D": 100}, 1000, 3,
        {
            "A": ["2000-01-01"],
            "B": ["2000-01-01"],
            "C": ["1990-01-01"],
            "D": ["1980-01-01"],
        },
    )
    check("equal_age_requires_lottery", r.status == STATUS_LOTTERY_REQUIRED and r.unallocated_seats == 3)

    try:
        allocate_2026({"A": 1001}, 1000, 3)
    except ValueError:
        print("PASS impossible_votes_rejected")
    else:
        raise AssertionError("impossible_votes_rejected")

    print("ALL LEGAL ALLOCATOR SELFTESTS PASS")


if __name__ == "__main__":
    main()
