from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping, Sequence

from .contracts import ContractError, LambdaCalibration, simplex


class ForecastError(ContractError):
    pass


def _normalize(values: Mapping[str, float]) -> dict[str, float]:
    total = sum(values.values())
    if total <= 0:
        raise ForecastError("zero probability mass")
    return {k: v / total for k, v in values.items()}


def log_ratio_delta(base: Mapping[str, float], agent: Mapping[str, float]) -> dict[str, float]:
    parties = sorted(set(base) | set(agent))
    b = _normalize({p: max(1e-12, float(base.get(p, 0))) for p in parties})
    a = _normalize({p: max(1e-12, float(agent.get(p, 0))) for p in parties})
    raw = {p: math.log(a[p]) - math.log(b[p]) for p in parties}
    center = sum(raw.values()) / len(raw)
    return {p: raw[p] - center for p in parties}


def blend(base: Mapping[str, float], delta: Mapping[str, float], lambda_value: float) -> dict[str, float]:
    if not 0 <= lambda_value <= 1.5:
        raise ForecastError("lambda outside [0,1.5]")
    b = simplex(base, "base")
    logits = {p: math.log(max(1e-12, b[p])) + lambda_value * float(delta.get(p, 0)) for p in b}
    maximum = max(logits.values())
    exp = {p: math.exp(v - maximum) for p, v in logits.items()}
    return _normalize(exp)


def aggregate_cells(cells: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[Mapping[str, Any]]] = defaultdict(list)
    for row in cells:
        weight = float(row.get("registered_electorate_weight") or 0)
        if weight <= 0:
            raise ForecastError("registered_electorate_weight must be positive")
        grouped[(str(row["contest_id"]), str(row["ballot"]))].append(row)
    contests = []
    for (contest_id, ballot), rows in sorted(grouped.items()):
        total = sum(float(r["registered_electorate_weight"]) for r in rows)
        party_delta: dict[str, float] = defaultdict(float)
        turnout_delta = 0.0
        for row in rows:
            w = float(row["registered_electorate_weight"]) / total
            for p, value in log_ratio_delta(row["structural_party_probabilities"], row["agent_party_probabilities"]).items():
                party_delta[p] += w * value
            turnout_delta += w * (_logit(float(row["agent_turnout_probability"])) - _logit(float(row["structural_turnout_probability"])))
        contests.append({"contest_id": contest_id, "ballot": ballot, "contest_scope_id": rows[0].get("contest_scope_id"), "registered_electorate_weight": total, "party_log_ratio_delta": dict(party_delta), "turnout_logit_delta": turnout_delta, "cell_count": len(rows)})
    return {"schema_version": "AGENT_SOCIETY_BEHAVIORAL_DELTA_V4", "scientific_label": "AGENTIC_DELTA_UNCALIBRATED", "contests": contests, "standalone_forecast": False}


def _logit(p: float) -> float:
    p = min(1 - 1e-9, max(1e-9, p))
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def combine(structural: Mapping[str, Any], delta: Mapping[str, Any], calibration: LambdaCalibration) -> dict[str, Any]:
    calibration.validate()
    d = {(str(r["contest_id"]), str(r["ballot"])): r for r in delta.get("contests") or []}
    output = []
    for base in structural.get("contests") or []:
        key = (str(base["contest_id"]), str(base["ballot"]))
        row = d.get(key, {"party_log_ratio_delta": {}, "turnout_logit_delta": 0.0})
        lam = calibration.local_choice if key[1] == "LOCAL" else calibration.regional_choice
        probabilities = blend(base["party_probabilities"], row["party_log_ratio_delta"], lam)
        turnout = _sigmoid(_logit(float(base["turnout_probability"])) + calibration.turnout * float(row["turnout_logit_delta"]))
        output.append({**{k: base.get(k) for k in ("contest_id", "contest_scope_id", "territory_id", "region_id", "ballot", "registered_electorate")}, "turnout_probability": turnout, "party_probabilities": probabilities, "structural_party_probabilities": base["party_probabilities"], "agentic_delta_applied": any(v != 0 for v in (lam, calibration.turnout))})
    label = "STRUCTURAL_BASELINE" if calibration.fitted_on == "LOCKED_ZERO_PRE_VALIDATION" else "PROSPECTIVE_FORECAST" if calibration.frozen_before_2021_holdout else "HYBRID_FORECAST_RESEARCH_PREVIEW"
    return {"schema_version": "AGENT_SOCIETY_HYBRID_FORECAST_V4", "scientific_label": label, "calibration": {"local_choice": calibration.local_choice, "regional_choice": calibration.regional_choice, "turnout": calibration.turnout, "fitted_on": calibration.fitted_on, "frozen_before_2021_holdout": calibration.frozen_before_2021_holdout}, "contests": output, "agent_society_is_not_a_standalone_forecast": True, "outcomes_opened": False}
