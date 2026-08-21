from __future__ import annotations

import dataclasses
import datetime as dt
import enum
import math
from typing import Any, Mapping


class ContractError(ValueError):
    pass


class CandidateState(str, enum.Enum):
    OFFICIAL = "OFFICIAL"
    DECLARED = "DECLARED"
    REPORTED = "REPORTED"
    UNKNOWN = "UNKNOWN"
    NO_LIST = "NO_LIST"


class BallotType(str, enum.Enum):
    LOCAL = "LOCAL"
    REGIONAL = "REGIONAL"


class Regime(str, enum.Enum):
    NAMED_REALISTIC_2026 = "NAMED_REALISTIC_2026"
    RICH_SEMI_BLIND_BACKTEST = "RICH_SEMI_BLIND_BACKTEST"
    TOTAL_BLIND_CONTROL = "TOTAL_BLIND_CONTROL"


def parse_date(value: str) -> dt.date:
    try:
        return dt.date.fromisoformat(value)
    except ValueError as exc:
        raise ContractError(f"invalid ISO date {value!r}") from exc


def probability(value: Any, label: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ContractError(f"{label} must be numeric") from exc
    if not math.isfinite(number) or not 0.0 <= number <= 1.0:
        raise ContractError(f"{label} must be in [0,1]")
    return number


def simplex(values: Mapping[str, Any], label: str = "simplex") -> dict[str, float]:
    if len(values) < 2:
        raise ContractError(f"{label} requires at least two options")
    parsed = {str(k): probability(v, f"{label}.{k}") for k, v in values.items()}
    total = sum(parsed.values())
    if abs(total - 1.0) > 1e-6:
        raise ContractError(f"{label} sums to {total}, not 1")
    return parsed


@dataclasses.dataclass(frozen=True)
class CandidateRecord:
    territory_id: str
    party_id: str
    ballot: BallotType
    state: CandidateState
    candidate_name: str | None
    known_at: str | None
    sources: tuple[Mapping[str, Any], ...] = ()
    attributes: Mapping[str, Any] = dataclasses.field(default_factory=dict)

    def validate(self, *, as_of: str) -> None:
        cutoff = parse_date(as_of)
        if not self.territory_id or not self.party_id:
            raise ContractError("candidate requires territory_id and party_id")
        named = self.state in {CandidateState.OFFICIAL, CandidateState.DECLARED, CandidateState.REPORTED}
        if named and not self.candidate_name:
            raise ContractError(f"{self.state.value} requires candidate_name")
        if self.state in {CandidateState.UNKNOWN, CandidateState.NO_LIST} and self.candidate_name:
            raise ContractError(f"{self.state.value} cannot carry a candidate name")
        if named and not self.sources:
            raise ContractError(f"{self.state.value} requires provenance")
        if self.state is CandidateState.NO_LIST and not self.sources:
            raise ContractError("NO_LIST requires positive evidence")
        if self.known_at and parse_date(self.known_at[:10]) > cutoff:
            raise ContractError("candidate knowledge is newer than vintage")
        for source in self.sources:
            source_date = str(source.get("known_at") or "")[:10]
            if not source_date:
                raise ContractError("candidate source requires known_at")
            if parse_date(source_date) > cutoff:
                raise ContractError("candidate source is newer than vintage")


@dataclasses.dataclass(frozen=True)
class LambdaCalibration:
    local_choice: float = 0.0
    regional_choice: float = 0.0
    turnout: float = 0.0
    fitted_on: str = "LOCKED_ZERO_PRE_VALIDATION"
    frozen_before_2021_holdout: bool = False

    def validate(self) -> None:
        for label, value in (("local_choice", self.local_choice), ("regional_choice", self.regional_choice), ("turnout", self.turnout)):
            if not 0.0 <= float(value) <= 1.5:
                raise ContractError(f"{label} lambda must be in [0,1.5]")
        if self.fitted_on == "LOCKED_ZERO_PRE_VALIDATION" and any(float(v) != 0.0 for v in (self.local_choice, self.regional_choice, self.turnout)):
            raise ContractError("pre-validation lambdas must be zero")
