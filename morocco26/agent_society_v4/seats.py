from __future__ import annotations

import dataclasses
import math
import random
from collections import Counter, defaultdict
from typing import Any, Mapping, Sequence

from .contracts import ContractError


class SeatError(ContractError):
    pass


@dataclasses.dataclass(frozen=True)
class SeatRuleConfig:
    local_method: str
    regional_method: str
    local_seats_by_territory: Mapping[str, int]
    regional_seats_by_region: Mapping[str, int]
    territory_to_region: Mapping[str, str]
    local_threshold: float = 0.0
    regional_threshold: float = 0.0
    expected_local_total: int = 305
    expected_regional_total: int = 90
    official_rule_source: str | None = None

    def validate(self) -> None:
        if self.local_method not in {"DHONDT", "LARGEST_REMAINDER"} or self.regional_method not in {"DHONDT", "LARGEST_REMAINDER"}:
            raise SeatError("unsupported seat method")
        if sum(self.local_seats_by_territory.values()) != self.expected_local_total or sum(self.regional_seats_by_region.values()) != self.expected_regional_total:
            raise SeatError("seat maps do not match expected totals")
        if not self.official_rule_source:
            raise SeatError("official rule source is required")


def _allocate(votes: Mapping[str, float], seats: int, method: str, threshold: float) -> dict[str, int]:
    total = sum(votes.values()); norm = {p: v / total for p, v in votes.items() if total and v / total >= threshold}
    if not norm: raise SeatError("no eligible party")
    if method == "DHONDT":
        result = {p: 0 for p in norm}; q = []
        for p, v in norm.items():
            q.extend((v / d, p) for d in range(1, seats + 1))
        for _, p in sorted(q, key=lambda x: (-x[0], x[1]))[:seats]: result[p] += 1
        return result
    quotas = {p: v / sum(norm.values()) * seats for p, v in norm.items()}; result = {p: int(math.floor(q)) for p, q in quotas.items()}
    for p in sorted(norm, key=lambda p: (-(quotas[p] - result[p]), -norm[p], p))[: seats - sum(result.values())]: result[p] += 1
    return result


def decode(forecast: Sequence[Mapping[str, Any]], config: SeatRuleConfig) -> dict[str, Any]:
    config.validate(); by_tid = {str(r["territory_id"]): r for r in forecast if r.get("territory_id")}
    local_total: dict[str, int] = defaultdict(int); region_votes: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for tid, n in config.local_seats_by_territory.items():
        if tid not in by_tid: raise SeatError(f"missing territory {tid}")
        row = by_tid[tid]; alloc = _allocate(row["party_probabilities"], n, config.local_method, config.local_threshold)
        for p, s in alloc.items(): local_total[p] += s
        region = config.territory_to_region[tid]; w = float(row.get("registered_electorate") or 1)
        regional = next((x for x in forecast if x.get("ballot") == "REGIONAL" and x.get("region_id") == region), None)
        if regional:
            for p, share in regional["party_probabilities"].items(): region_votes[region][p] += w * share
    regional_total: dict[str, int] = defaultdict(int)
    for region, n in config.regional_seats_by_region.items():
        alloc = _allocate(region_votes[region], n, config.regional_method, config.regional_threshold)
        for p, s in alloc.items(): regional_total[p] += s
    parties = set(local_total) | set(regional_total)
    return {"schema_version": "AGENT_SOCIETY_SEAT_DECODER_V4", "local_total": dict(local_total), "regional_total": dict(regional_total), "total_seats": {p: local_total.get(p, 0) + regional_total.get(p, 0) for p in parties}, "seat_total": sum(local_total.values()) + sum(regional_total.values())}


def monte_carlo(forecast: Sequence[Mapping[str, Any]], config: SeatRuleConfig, *, draws: int, seed: int) -> dict[str, Any]:
    config.validate(); rng = random.Random(seed); parties = sorted({p for r in forecast for p in r["party_probabilities"]}); samples = {p: [] for p in parties}; plurality = Counter()
    for _ in range(draws):
        national = {p: rng.gauss(0, .05) for p in parties}; perturbed = []
        for r in forecast:
            logits = {p: math.log(max(1e-12, share)) + national[p] + rng.gauss(0, .06) for p, share in r["party_probabilities"].items()}; mx = max(logits.values()); exp = {p: math.exp(v-mx) for p,v in logits.items()}; total = sum(exp.values())
            perturbed.append({**r, "party_probabilities": {p:v/total for p,v in exp.items()}})
        seats = decode(perturbed, config)["total_seats"]
        for p in parties: samples[p].append(seats.get(p,0))
        plurality[max(parties, key=lambda p:(seats.get(p,0),p))] += 1
    return {"schema_version":"AGENT_SOCIETY_CORRELATED_MONTE_CARLO_V4","draws":draws,"seed":seed,"parties":{p:{"mean_seats":sum(samples[p])/draws,"p05":sorted(samples[p])[max(0,int(.05*draws)-1)],"p95":sorted(samples[p])[min(draws-1,int(.95*draws))],"plurality_probability":plurality[p]/draws} for p in parties},"correlated_model_uncertainty":True}
