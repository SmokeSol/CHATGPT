"""Fail-closed House of Representatives seat allocator for Morocco 2026.

Legal basis (current consolidated Organic Law 27.11, last modified 2026-01-29):
- Art. 84: quotient = registered voters / seats; largest remainders.
- Art. 84: equal remainder -> youngest eligible next candidate; equal age -> lottery.
- Art. 84: single-member election -> plurality, same tie rule.
- Art. 84/91: a unique list/candidate needs at least one fifth of registered voters.
- Art. 85: regional allocation uses the Art. 84 method.

This module deliberately fails closed when the statute requires candidate-age or
lottery information that has not been supplied. It never substitutes party name,
raw vote count, or insertion order for the statutory tie-break.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Mapping, Sequence


STATUS_OK = "OK"
STATUS_OK_UNIQUE = "OK_UNIQUE_LIST_THRESHOLD_MET"
STATUS_OK_AGE_TIEBREAK = "OK_TIE_BY_AGE"
STATUS_NO_VALID_VOTES = "NO_VALID_VOTES"
STATUS_UNIQUE_FAIL = "UNIQUE_LIST_THRESHOLD_NOT_MET"
STATUS_TIE_UNRESOLVED = "UNRESOLVED_STATUTORY_TIE"
STATUS_LOTTERY_REQUIRED = "LOTTERY_REQUIRED"
STATUS_UNFILLED_EXCEPTIONAL = "UNFILLED_SEATS_EXCEPTIONAL"


@dataclass(frozen=True)
class AllocationResult:
    seats_by_list: dict[str, int]
    allocated_seats: int
    unallocated_seats: int
    status: str
    registered: int
    district_seats: int
    quotient_numerator: int
    quotient_denominator: int
    tie_events: tuple[dict, ...] = ()

    @property
    def complete(self) -> bool:
        return self.unallocated_seats == 0 and self.status in {
            STATUS_OK,
            STATUS_OK_UNIQUE,
            STATUS_OK_AGE_TIEBREAK,
        }


def _as_birthdate(value: str | date) -> date:
    return value if isinstance(value, date) else date.fromisoformat(value)


def _next_birthdate(
    party: str,
    already_allocated: int,
    candidate_birthdates: Mapping[str, Sequence[str | date] | str | date] | None,
) -> date | None:
    if candidate_birthdates is None or party not in candidate_birthdates:
        return None
    value = candidate_birthdates[party]
    if isinstance(value, (str, date)):
        return _as_birthdate(value) if already_allocated == 0 else None
    if already_allocated >= len(value):
        return None
    return _as_birthdate(value[already_allocated])


def _result(
    alloc: Mapping[str, int],
    registered: int,
    district_seats: int,
    unallocated: int,
    status: str,
    tie_events: list[dict] | None = None,
) -> AllocationResult:
    cleaned = {p: int(n) for p, n in alloc.items() if int(n) > 0}
    return AllocationResult(
        seats_by_list=cleaned,
        allocated_seats=sum(cleaned.values()),
        unallocated_seats=int(unallocated),
        status=status,
        registered=int(registered),
        district_seats=int(district_seats),
        quotient_numerator=int(registered),
        quotient_denominator=int(district_seats),
        tie_events=tuple(tie_events or ()),
    )


def allocate_2026(
    votes: Mapping[str, int],
    registered: int,
    district_seats: int,
    candidate_birthdates: Mapping[str, Sequence[str | date] | str | date] | None = None,
) -> AllocationResult:
    """Allocate seats under the 2026 Art. 84 rule.

    ``candidate_birthdates`` is ordered by list rank for each party/list. A later
    birth date means a younger candidate. It is consulted only when an exact
    statutory tie affects who receives a seat.

    Arithmetic is integer-exact. For list ``p`` the initial seat count is
    floor(v_p * m / N). Its remainder can be compared using the integer
    numerator ``v_p * m - floor(v_p*m/N) * N`` because every list has the same
    denominator ``m``. This avoids floating-point tie artefacts.
    """
    if registered <= 0:
        raise ValueError("registered must be positive")
    if district_seats <= 0:
        raise ValueError("district_seats must be positive")

    clean: dict[str, int] = {}
    for party, value in votes.items():
        ivalue = int(value)
        if ivalue < 0:
            raise ValueError(f"negative votes for {party}")
        clean[str(party)] = ivalue
    if sum(clean.values()) > registered:
        raise ValueError("valid-list votes cannot exceed registered voters")

    positive = {p: v for p, v in clean.items() if v > 0}
    if not positive:
        return _result({}, registered, district_seats, district_seats, STATUS_NO_VALID_VOTES)

    # Art. 84/91 unique-list gate. Once the unique list reaches the one-fifth
    # threshold, its candidates are the only candidates who can fill the district.
    if len(positive) == 1:
        party, value = next(iter(positive.items()))
        if 5 * value < registered:
            return _result({}, registered, district_seats, district_seats, STATUS_UNIQUE_FAIL)
        return _result({party: district_seats}, registered, district_seats, 0, STATUS_OK_UNIQUE)

    # Partial/single-member election branch.
    if district_seats == 1:
        max_votes = max(positive.values())
        tied = sorted(p for p, value in positive.items() if value == max_votes)
        if len(tied) == 1:
            return _result({tied[0]: 1}, registered, 1, 0, STATUS_OK)
        dates = {p: _next_birthdate(p, 0, candidate_birthdates) for p in tied}
        missing = sorted(p for p, d in dates.items() if d is None)
        event = {"kind": "single_member_vote_tie", "parties": tied}
        if missing:
            event["missing_birthdates"] = missing
            return _result({}, registered, 1, 1, STATUS_TIE_UNRESOLVED, [event])
        youngest_date = max(d for d in dates.values() if d is not None)
        youngest = sorted(p for p, d in dates.items() if d == youngest_date)
        if len(youngest) > 1:
            event["lottery_parties"] = youngest
            return _result({}, registered, 1, 1, STATUS_LOTTERY_REQUIRED, [event])
        event["winner"] = youngest[0]
        event["resolution"] = "youngest_candidate"
        return _result({youngest[0]: 1}, registered, 1, 0, STATUS_OK_AGE_TIEBREAK, [event])

    # Exact quotient/remainder arithmetic for multi-member districts.
    allocation = {p: (value * district_seats) // registered for p, value in positive.items()}
    remainder_num = {
        p: value * district_seats - allocation[p] * registered
        for p, value in positive.items()
    }
    seats_left = district_seats - sum(allocation.values())
    if seats_left < 0:
        raise AssertionError("initial quotient allocation exceeded district magnitude")

    events: list[dict] = []
    groups: dict[int, list[str]] = {}
    for party, rem in remainder_num.items():
        groups.setdefault(rem, []).append(party)

    for rem in sorted(groups, reverse=True):
        if seats_left <= 0:
            break
        group = sorted(groups[rem])

        # If every tied list fits above the cutoff, seat counts are unambiguous;
        # statutory age ordering does not change the allocation vector.
        if len(group) <= seats_left:
            for party in group:
                allocation[party] += 1
            if len(group) > 1:
                events.append({
                    "kind": "equal_remainder_nonbinding",
                    "remainder_numerator": rem,
                    "parties": group,
                    "resolution": "all_tied_lists_receive_one_remainder_seat",
                })
            seats_left -= len(group)
            continue

        # The allocation cutoff falls inside an exact remainder tie. The law
        # requires the youngest eligible next candidate, then lottery on equal age.
        dates: dict[str, date] = {}
        missing: list[str] = []
        next_ranks: dict[str, int] = {}
        for party in group:
            next_ranks[party] = allocation[party] + 1
            birth = _next_birthdate(party, allocation[party], candidate_birthdates)
            if birth is None:
                missing.append(party)
            else:
                dates[party] = birth

        event = {
            "kind": "equal_remainder_binding",
            "remainder_numerator": rem,
            "parties": group,
            "seats_available": seats_left,
            "next_candidate_rank": next_ranks,
        }
        if missing:
            event["missing_birthdates"] = sorted(missing)
            events.append(event)
            return _result(
                allocation, registered, district_seats, seats_left,
                STATUS_TIE_UNRESOLVED, events,
            )

        ordered = sorted(group, key=lambda p: (dates[p], p), reverse=True)
        cutoff_date = dates[ordered[seats_left - 1]]
        strictly_younger = [p for p in group if dates[p] > cutoff_date]
        boundary = sorted(p for p in group if dates[p] == cutoff_date)
        boundary_needed = seats_left - len(strictly_younger)
        if len(boundary) > boundary_needed:
            event["lottery_parties"] = boundary
            events.append(event)
            return _result(
                allocation, registered, district_seats, seats_left,
                STATUS_LOTTERY_REQUIRED, events,
            )

        winners = strictly_younger + boundary
        winners = winners[:seats_left]
        for party in winners:
            allocation[party] += 1
        event["resolution"] = "youngest_candidate"
        event["winners"] = sorted(winners)
        events.append(event)
        seats_left = 0

    if seats_left:
        return _result(
            allocation, registered, district_seats, seats_left,
            STATUS_UNFILLED_EXCEPTIONAL, events,
        )
    status = STATUS_OK_AGE_TIEBREAK if any(
        e.get("resolution") == "youngest_candidate" for e in events
    ) else STATUS_OK
    return _result(allocation, registered, district_seats, 0, status, events)
