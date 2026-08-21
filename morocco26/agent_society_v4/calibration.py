from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from .contracts import ContractError, LambdaCalibration, simplex
from .forecast import blend, log_ratio_delta


class CalibrationError(ContractError):
    pass


def log_loss(actual: Mapping[str, float], predicted: Mapping[str, float]) -> float:
    a = simplex(actual, "actual")
    p = simplex(predicted, "predicted")
    return -sum(a.get(k, 0) * math.log(max(1e-12, p.get(k, 1e-12))) for k in set(a) | set(p))


def _grid() -> list[float]:
    return [i / 20 for i in range(31)]


def fit_2016(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise CalibrationError("empty 2016 development set")
    if any(str(r.get("development_split")) != "2016_DEVELOPMENT_ONLY" or r.get("holdout_2021_visible") is True for r in rows):
        raise CalibrationError("lambda may use 2016 development only; 2021 must remain sealed")
    def fit(prefix: str) -> float:
        scored = []
        for lam in _grid():
            losses = []
            for r in rows:
                base, agent, actual = r[f"{prefix}_baseline"], r[f"{prefix}_society"], r[f"{prefix}_actual"]
                losses.append(log_loss(actual, blend(base, log_ratio_delta(base, agent), lam)))
            scored.append((sum(losses) / len(losses), lam))
        return min(scored)[1]
    local, regional = fit("local"), fit("regional")
    turnout_scores = []
    for lam in _grid():
        loss = 0.0
        for r in rows:
            b, a, y = float(r["turnout_baseline"]), float(r["turnout_society"]), float(r["turnout_actual"])
            def logit(p: float) -> float:
                p = min(1 - 1e-9, max(1e-9, p)); return math.log(p / (1 - p))
            pred = 1 / (1 + math.exp(-(logit(b) + lam * (logit(a) - logit(b)))))
            loss += (pred - y) ** 2
        turnout_scores.append((loss / len(rows), lam))
    calibration = LambdaCalibration(local, regional, min(turnout_scores)[1], "2016_DEVELOPMENT_ONLY", True)
    calibration.validate()
    return {"schema_version": "AGENT_SOCIETY_LAMBDA_FREEZE_V4", "status": "PASS_LAMBDA_FROZEN_BEFORE_2021_HOLDOUT", "calibration": {"local_choice": calibration.local_choice, "regional_choice": calibration.regional_choice, "turnout": calibration.turnout, "fitted_on": calibration.fitted_on, "frozen_before_2021_holdout": calibration.frozen_before_2021_holdout}, "post_holdout_tuning_allowed": False}


def score_2021(rows: Sequence[Mapping[str, Any]], freeze: Mapping[str, Any]) -> dict[str, Any]:
    if freeze.get("status") != "PASS_LAMBDA_FROZEN_BEFORE_2021_HOLDOUT":
        raise CalibrationError("pre-holdout freeze required")
    if any(str(r.get("holdout_split")) != "2021_HOLDOUT_ONLY" for r in rows):
        raise CalibrationError("2021 holdout rows only")
    c = LambdaCalibration(**freeze["calibration"])
    c.validate()
    metrics = {"local_log_loss": [], "regional_log_loss": []}
    for r in rows:
        for prefix, lam in (("local", c.local_choice), ("regional", c.regional_choice)):
            pred = blend(r[f"{prefix}_baseline"], log_ratio_delta(r[f"{prefix}_baseline"], r[f"{prefix}_society"]), lam)
            metrics[f"{prefix}_log_loss"].append(log_loss(r[f"{prefix}_actual"], pred))
    return {"schema_version": "AGENT_SOCIETY_2021_HOLDOUT_SCORE_V4", "status": "PASS_2021_HOLDOUT_SCORED_NO_RETUNING", "metrics": {k: sum(v) / len(v) for k, v in metrics.items()}, "post_holdout_tuning_allowed": False}
