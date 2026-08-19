#!/usr/bin/env python3
"""Select the 2026 national party-strength model under the frozen V1 contract.

No 2026-specific political signal is consumed here.  The only input class is prior
legislative national local-ballot party shares.  Model formulae were frozen in
``national_model_formulas_v1.json`` before scoring.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence

PARTIES = ["RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS", "OTHER"]
MODELS = [
    "PREVIOUS_NATIONAL_PERSISTENCE",
    "POOLED_SHRUNK_NATIONAL_SWING",
    "PARTY_SHRUNK_NATIONAL_SWING",
    "SHRUNK_MEAN_REVERSION",
]
YEARS = [1997, 2002, 2007, 2011, 2016, 2021]
FOLDS = [(2002, 2007), (2007, 2011), (2011, 2016), (2016, 2021)]

ROOT = Path(__file__).resolve().parents[1]
LAB = ROOT / "data" / "goal100" / "forecast_lab"
HIST = ROOT / "data" / "goal100" / "historical"


def _load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _normalize(v: Sequence[float]) -> List[float]:
    s = float(sum(v))
    if not math.isfinite(s) or s <= 0:
        raise ValueError("non-positive vector sum")
    out = [float(x) / s for x in v]
    if any((not math.isfinite(x)) or x < -1e-15 for x in out):
        raise ValueError("invalid probability vector")
    return out


def project_simplex(v: Sequence[float]) -> List[float]:
    """Deterministic Euclidean projection onto the non-negative unit simplex."""
    x = [float(z) for z in v]
    if not x or any(not math.isfinite(z) for z in x):
        raise ValueError("invalid projection input")
    u = sorted(x, reverse=True)
    cssv = 0.0
    rho = -1
    theta = 0.0
    for i, z in enumerate(u):
        cssv += z
        t = (cssv - 1.0) / (i + 1)
        if z - t > 0:
            rho = i
            theta = t
    if rho < 0:
        raise ValueError("simplex projection failed")
    out = [max(z - theta, 0.0) for z in x]
    return _normalize(out)


def _bucket_votes(votes: Mapping[str, object]) -> List[float]:
    acc = {p: 0.0 for p in PARTIES}
    for code, raw in votes.items():
        if raw is None:
            continue
        value = float(raw)
        if value < 0 or not math.isfinite(value):
            raise ValueError(f"invalid vote count {code}={raw}")
        acc[code if code in acc and code != "OTHER" else "OTHER"] += value
    return [acc[p] for p in PARTIES]


def _national_from_rows(rows: Iterable[Mapping[str, object]]) -> List[float]:
    total = [0.0] * len(PARTIES)
    n_local = 0
    for row in rows:
        if row.get("list_type") != "locale":
            continue
        n_local += 1
        b = _bucket_votes(row["votes"])
        total = [a + z for a, z in zip(total, b)]
    if n_local == 0:
        raise ValueError("no local-ballot rows")
    return _normalize(total)


def load_history() -> Dict[int, List[float]]:
    early = _load_json(LAB / "national_history_1997_2002_v1.json")
    if early.get("status") != "PASS_FOR_NATIONAL_ROLLING_ORIGIN_ONLY":
        raise RuntimeError("early national history not certified")
    out: Dict[int, List[float]] = {}
    for year in (1997, 2002):
        block = early["years"][str(year)]
        out[year] = [float(block["bucket_share"][p]) for p in PARTIES]
        if abs(sum(out[year]) - 1.0) > 1e-10:
            raise RuntimeError(f"{year} national shares do not sum to one")

    p2007 = _load_json(HIST / "2007" / "legislative_2007_outcome_canonical.json")
    out[2007] = _national_from_rows(p2007["local_rows"])
    for year in (2011, 2016, 2021):
        payload = _load_json(HIST / f"tafra_legislative_{year}_canonical.json")
        out[year] = _national_from_rows(payload["rows"])
    return out


def _sub(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [x - y for x, y in zip(a, b)]


def _add(a: Sequence[float], b: Sequence[float]) -> List[float]:
    return [x + y for x, y in zip(a, b)]


def _scale(a: Sequence[float], c: float) -> List[float]:
    return [c * x for x in a]


def _mean(vectors: Sequence[Sequence[float]]) -> List[float]:
    if not vectors:
        raise ValueError("empty mean")
    return [sum(v[j] for v in vectors) / len(vectors) for j in range(len(vectors[0]))]


def _deltas(history: Mapping[int, Sequence[float]], origin: int) -> List[List[float]]:
    ys = [y for y in YEARS if y <= origin and y in history]
    return [_sub(history[b], history[a]) for a, b in zip(ys[:-1], ys[1:])]


def forecast_model(name: str, history: Mapping[int, Sequence[float]], origin: int) -> List[float]:
    p0 = list(history[origin])
    ds = _deltas(history, origin)
    k = len(ds)
    if name == "PREVIOUS_NATIONAL_PERSISTENCE":
        return list(p0)
    if name == "POOLED_SHRUNK_NATIONAL_SWING":
        if k == 0:
            return list(p0)
        mu = _mean(ds)
        return project_simplex(_add(p0, _scale(mu, k / (k + 1.0))))
    if name == "PARTY_SHRUNK_NATIONAL_SWING":
        if k == 0:
            return list(p0)
        mu = _mean(ds)
        q = sum(z * z for d in ds for z in d) / (k * len(PARTIES))
        if q <= 0:
            return list(p0)
        r = [(k * m * m) / (k * m * m + q) for m in mu]
        return project_simplex([p + rr * m for p, rr, m in zip(p0, r, mu)])
    if name == "SHRUNK_MEAN_REVERSION":
        ys = [y for y in YEARS if y <= origin and y in history]
        predictors: List[List[float]] = []
        outcomes: List[List[float]] = []
        # A transition at index i->i+1 is eligible only if the origin at i has
        # at least two elections available (i >= 1), exactly as frozen.
        for i in range(1, len(ys) - 1):
            y0, y1 = ys[i], ys[i + 1]
            prior_mean = _mean([history[y] for y in ys[: i + 1]])
            predictors.append(_sub(prior_mean, history[y0]))
            outcomes.append(_sub(history[y1], history[y0]))
        denom = sum(sum(z * z for z in d) for d in predictors)
        if denom <= 0 or not predictors:
            beta = 0.0
        else:
            numer = sum(sum(a * b for a, b in zip(d, e)) for d, e in zip(predictors, outcomes))
            beta = min(1.0, max(0.0, numer / (2.0 * denom)))
        current_mean = _mean([history[y] for y in ys])
        d = _sub(current_mean, p0)
        return project_simplex(_add(p0, _scale(d, beta)))
    raise KeyError(name)


def rmse(pred: Sequence[float], actual: Sequence[float], idx: Sequence[int] | None = None, conditional=False) -> float:
    ix = list(range(len(pred))) if idx is None else list(idx)
    p = [pred[i] for i in ix]
    a = [actual[i] for i in ix]
    if conditional:
        p, a = _normalize(p), _normalize(a)
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(p, a)) / len(ix))


def mae(pred: Sequence[float], actual: Sequence[float]) -> float:
    return sum(abs(x - y) for x, y in zip(pred, actual)) / len(pred)


def top_hit(pred: Sequence[float], actual: Sequence[float]) -> int:
    mp, ma = max(pred), max(actual)
    pp = {i for i, z in enumerate(pred) if abs(z - mp) < 1e-12}
    aa = {i for i, z in enumerate(actual) if abs(z - ma) < 1e-12}
    return int(bool(pp & aa))


def run() -> dict:
    history = load_history()
    fold_results = {}
    model_agg = {m: {"rmse": [], "mae": [], "top_hit": []} for m in MODELS}
    for origin, target in FOLDS:
        fold = {"origin_year": origin, "target_year": target, "models": {}}
        for model in MODELS:
            pred = forecast_model(model, history, origin)
            actual = history[target]
            metrics = {"rmse": rmse(pred, actual), "mae": mae(pred, actual), "top_party_hit": top_hit(pred, actual)}
            fold["models"][model] = {
                "prediction": dict(zip(PARTIES, pred)),
                "actual": dict(zip(PARTIES, actual)),
                **metrics,
            }
            for k in model_agg[model]:
                model_agg[model][k].append(metrics["top_party_hit" if k == "top_hit" else k])
        fold_results[f"{origin}_TO_{target}"] = fold

    scores = {}
    for model in MODELS:
        scores[model] = {
            "mean_fold_rmse": sum(model_agg[model]["rmse"]) / len(FOLDS),
            "mean_fold_mae": sum(model_agg[model]["mae"]) / len(FOLDS),
            "worst_fold_rmse": max(model_agg[model]["rmse"]),
            "top_party_accuracy": sum(model_agg[model]["top_hit"]) / len(FOLDS),
        }
    fixed_order = {m: i for i, m in enumerate(MODELS)}
    ranking = sorted(
        MODELS,
        key=lambda m: (
            scores[m]["mean_fold_rmse"],
            scores[m]["mean_fold_mae"],
            scores[m]["worst_fold_rmse"],
            -scores[m]["top_party_accuracy"],
            fixed_order[m],
        ),
    )
    winner = ranking[0]

    diagnostics = {}
    for label, excluded in {
        "EXCLUDE_PAM": {"PAM"},
        "EXCLUDE_OTHER": {"OTHER"},
        "EXCLUDE_PAM_AND_OTHER": {"PAM", "OTHER"},
    }.items():
        idx = [i for i, p in enumerate(PARTIES) if p not in excluded]
        vals = {}
        for model in MODELS:
            raw, conditional = [], []
            for origin, target in FOLDS:
                pred = forecast_model(model, history, origin)
                actual = history[target]
                raw.append(rmse(pred, actual, idx=idx, conditional=False))
                conditional.append(rmse(pred, actual, idx=idx, conditional=True))
            vals[model] = {
                "mean_raw_component_rmse": sum(raw) / len(raw),
                "mean_conditional_composition_rmse": sum(conditional) / len(conditional),
            }
        diagnostics[label] = {
            "excluded": sorted(excluded),
            "scores": vals,
            "winner_raw": min(MODELS, key=lambda m: (vals[m]["mean_raw_component_rmse"], fixed_order[m])),
            "winner_conditional": min(MODELS, key=lambda m: (vals[m]["mean_conditional_composition_rmse"], fixed_order[m])),
            "selection_role": "DIAGNOSTIC_ONLY_NO_POST_HOC_MODEL_CHANGE",
        }

    p2026 = forecast_model(winner, history, 2021)
    # The downstream V3 structural centre requires strictly positive shares.
    p2026 = _normalize([max(x, 1e-8) for x in p2026])
    history_json = {str(y): dict(zip(PARTIES, history[y])) for y in YEARS}
    return {
        "schema_version": "1.0",
        "artifact_id": "M26-NATIONAL-MODEL-SELECTION-2026-V1",
        "selection_contract": "morocco26/data/goal100/forecast_lab/national_model_selection_contract_v1.json",
        "formula_contract": "morocco26/data/goal100/forecast_lab/national_model_formulas_v1.json",
        "data_class": "PRIOR_LEGISLATIVE_NATIONAL_LOCAL_BALLOT_SHARES_ONLY",
        "target_outcome_used": False,
        "scored_folds": [f"{a}_TO_{b}" for a, b in FOLDS],
        "history": history_json,
        "fold_results": fold_results,
        "scores": scores,
        "ranking": ranking,
        "winner": winner,
        "diagnostic_sensitivities": diagnostics,
        "forecast_2026": {
            "forecast_id": "M26-NATIONAL-2026-POINT-V1",
            "target_year": 2026,
            "as_of": "2026-08-19T00:00:00+01:00",
            "status": "READY_FOR_STRUCTURAL_CENTER",
            "data_class": "CURRENT_PRE_ELECTION_NATIONAL_FORECAST",
            "target_outcome_used": False,
            "party_order": PARTIES,
            "point_share": dict(zip(PARTIES, p2026)),
            "model": winner,
            "evidence": [
                "Frozen national model family selected by four strict rolling-origin folds using only prior legislative national local-ballot shares.",
                "No 2026-only political signal, poll, candidate judgement, partial election, press narrative or prediction market is used in this numeric point forecast."
            ],
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    result = run()
    text = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print("NATIONAL_MODEL_SELECTION=" + json.dumps({
        "winner": result["winner"],
        "ranking": result["ranking"],
        "scores": result["scores"],
        "diagnostic_winners": {
            k: {"raw": v["winner_raw"], "conditional": v["winner_conditional"]}
            for k, v in result["diagnostic_sensitivities"].items()
        },
        "point_share_2026": result["forecast_2026"]["point_share"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
