from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence


class SeatMarginError(ValueError):
    """Raised when a vote-rank seat-margin diagnostic cannot be computed."""


@dataclass(frozen=True, slots=True)
class RankedList:
    party: str
    votes: int
    rank: int
    elected_by_rank: bool


@dataclass(frozen=True, slots=True)
class SeatMarginResult:
    seats: int
    ranked_lists: tuple[RankedList, ...]
    rank_winners: tuple[str, ...]
    last_rank_winner: str
    first_rank_nonwinner: str | None
    margin_votes: int | None
    margin_valid_vote_pp: float | None
    expected_winners: tuple[str, ...] | None
    winner_set_match: bool | None
    evidence_tier: str = "VOTE_RANK_DIAGNOSTIC_NOT_LEGAL_ALLOCATION"

    def as_dict(self) -> dict[str, object]:
        return {
            "seats": self.seats,
            "ranked_lists": [
                {
                    "party": row.party,
                    "votes": row.votes,
                    "rank": row.rank,
                    "elected_by_rank": row.elected_by_rank,
                }
                for row in self.ranked_lists
            ],
            "rank_winners": list(self.rank_winners),
            "last_rank_winner": self.last_rank_winner,
            "first_rank_nonwinner": self.first_rank_nonwinner,
            "margin_votes": self.margin_votes,
            "margin_valid_vote_pp": self.margin_valid_vote_pp,
            "expected_winners": list(self.expected_winners) if self.expected_winners is not None else None,
            "winner_set_match": self.winner_set_match,
            "evidence_tier": self.evidence_tier,
        }


def analyze_vote_rank_margin(
    votes: Mapping[str, int],
    seats: int,
    *,
    valid_votes: int | None = None,
    expected_winners: Sequence[str] | None = None,
) -> SeatMarginResult:
    """Compute an empirical top-N seat-cutoff diagnostic from list votes.

    This is deliberately *not* the legal Moroccan allocator. It answers a
    narrower empirical question: if each list can occupy at most one local seat,
    what is the raw-vote gap between the Nth and (N+1)th lists, and does that
    ranking reproduce an independently supplied elected-list set?

    ``registered`` is therefore not required here. Legal quota replay remains a
    separate gate and must use :func:`morocco26.electoral.allocate_seats` with a
    registered-voter denominator.
    """
    if seats <= 0:
        raise SeatMarginError("seats must be positive")
    clean: dict[str, int] = {}
    for party, value in votes.items():
        ivalue = int(value)
        if ivalue < 0:
            raise SeatMarginError("votes cannot be negative")
        if ivalue > 0:
            clean[str(party)] = ivalue
    if len(clean) < seats:
        raise SeatMarginError("fewer positive-vote lists than seats")

    ranked_pairs = sorted(clean.items(), key=lambda item: (-item[1], item[0]))
    ranked = tuple(
        RankedList(party=party, votes=value, rank=index, elected_by_rank=index <= seats)
        for index, (party, value) in enumerate(ranked_pairs, 1)
    )
    winners = tuple(row.party for row in ranked[:seats])
    last = ranked[seats - 1]
    first_nonwinner = ranked[seats] if len(ranked) > seats else None
    margin_votes = last.votes - first_nonwinner.votes if first_nonwinner else None

    denominator = int(valid_votes) if valid_votes is not None else sum(clean.values())
    if denominator <= 0:
        raise SeatMarginError("valid_votes must be positive")
    if denominator < sum(clean.values()):
        raise SeatMarginError("valid_votes cannot be smaller than supplied party votes")
    margin_pp = (margin_votes / denominator * 100.0) if margin_votes is not None else None

    expected = tuple(str(x) for x in expected_winners) if expected_winners is not None else None
    match = set(winners) == set(expected) if expected is not None else None

    return SeatMarginResult(
        seats=seats,
        ranked_lists=ranked,
        rank_winners=winners,
        last_rank_winner=last.party,
        first_rank_nonwinner=first_nonwinner.party if first_nonwinner else None,
        margin_votes=margin_votes,
        margin_valid_vote_pp=margin_pp,
        expected_winners=expected,
        winner_set_match=match,
    )
