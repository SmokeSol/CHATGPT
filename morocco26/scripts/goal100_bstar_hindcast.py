#!/usr/bin/env python3
"""Execute the frozen Goal100 structural-baseline hindcast.

Development transition: 2011 -> 2016.
Temporal validation:  2016 -> 2021.

No 2021 outcome is used to fit shifts, residual distributions, or kappa.  The
finite model family and scores are frozen in forecast_protocol_v1.json before
this script's result exists.
"""
from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "goal100" / "historical"
OUT = ROOT / "data" / "goal100" / "bstar_hindcast_v1.json"
PROTOCOL = ROOT / "data" / "goal100" / "forecast_protocol_v1.json"
CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
BUCKETS = (*CORE, "OTHER")
KAPPA = 5.0
N_SAMPLES = 4096
N_BOOT = 5000
SEED = 260816
EPS_VOTES = 0.5


def load(year: int):
    data = json.loads((HIST / f"tafra_legislative_{year}_canonical.json").read_text(encoding="utf-8"))
    rows = [r for r in data["rows"] if str(r.get("list_type", "")).lower() in {"locale", "local"}]
    return {str(r["id_constituency"]): r for r in rows}


def bucket_counts(row):
    raw = row.get("votes", {})
    vals = [float(raw.get(p, 0) or 0) for p in CORE]
    other = sum(float(v or 0) for p, v in raw.items() if p not in CORE)
    vals.append(other)
    arr = np.asarray(vals, dtype=float)
    if np.any(arr < 0) or arr.sum() <= 0:
        raise ValueError(f"invalid vote vector {row.get('id_constituency')}: {arr}")
    return arr


def raw_share(row):
    x = bucket_counts(row)
    return x / x.sum()


def clr(row):
    # Fixed half-vote smoothing exists ONLY to map boundary compositions into CLR.
    # Scoring uses unsmoothed observed shares and therefore does not hide zeros.
    x = bucket_counts(row) + EPS_VOTES
    s = x / x.sum()
    z = np.log(s)
    return z - z.mean()


def inv_clr(z):
    z = np.asarray(z, dtype=float)
    z = z - np.max(z, axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def centre_clr(x):
    a = np.asarray(x, dtype=float)
    return a - a.mean(axis=-1, keepdims=True)


def logit(x):
    x = min(max(float(x), 1e-6), 1 - 1e-6)
    return math.log(x / (1 - x))


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-np.asarray(x, dtype=float)))


def energy_score(samples, observed, pair_samples):
    a = np.sqrt(np.clip(samples, 0, 1))
    b = np.sqrt(np.clip(pair_samples, 0, 1))
    y = np.sqrt(np.clip(observed, 0, 1))
    return float(np.linalg.norm(a - y, axis=1).mean() - 0.5 * np.linalg.norm(a - b, axis=1).mean())


def crps(samples, observed, pair_samples):
    return float(np.abs(samples - observed).mean() - 0.5 * np.abs(samples - pair_samples).mean())


def q(a, p):
    return float(np.quantile(np.asarray(a, dtype=float), p))


def paired_bootstrap(delta, rng):
    d = np.asarray(delta, dtype=float)
    idx = rng.integers(0, len(d), size=(N_BOOT, len(d)))
    means = d[idx].mean(axis=1)
    return {
        "mean_delta_model_minus_persist": float(d.mean()),
        "ci95": [q(means, 0.025), q(means, 0.975)],
        "p_bootstrap_model_better_than_persist": float(np.mean(means < 0)),
    }


def main():
    if not PROTOCOL.exists():
        raise RuntimeError("forecast protocol must be frozen before hindcast execution")
    protocol = json.loads(PROTOCOL.read_text(encoding="utf-8"))
    if protocol.get("status") != "FROZEN_PROTOCOL_READY_FOR_HINDCAST_EXECUTION":
        raise RuntimeError("unexpected protocol state")

    y11, y16, y21 = load(2011), load(2016), load(2021)
    ids = sorted(set(y11) & set(y16) & set(y21))
    if len(ids) != 92:
        raise RuntimeError(f"expected 92 common local IDs, got {len(ids)}")

    z11 = {i: clr(y11[i]) for i in ids}
    z16 = {i: clr(y16[i]) for i in ids}
    train_shift = {i: centre_clr(z16[i] - z11[i]) for i in ids}
    train_matrix = np.stack([train_shift[i] for i in ids])
    global_shift = centre_clr(np.median(train_matrix, axis=0))

    by_region = defaultdict(list)
    for i in ids:
        by_region[str(y16[i]["region"])].append(i)
    if len(by_region) != 12:
        raise RuntimeError(f"expected 12 current regions in 2016 map, got {len(by_region)}")

    regional_shift = {}
    region_meta = {}
    for region, rids in sorted(by_region.items()):
        med = centre_clr(np.median(np.stack([train_shift[i] for i in rids]), axis=0))
        w = len(rids) / (len(rids) + KAPPA)
        shrunk = centre_clr(w * med + (1 - w) * global_shift)
        regional_shift[region] = shrunk
        region_meta[region] = {"n": len(rids), "weight_local": w, "weight_global": 1 - w}

    vote_shift = {
        "V0_PERSIST": lambda i: np.zeros(len(BUCKETS)),
        "V1_GLOBAL_CLR": lambda i: global_shift,
        "V2_REGION_SHRUNK_CLR": lambda i: regional_shift[str(y16[i]["region"])],
    }

    rng = np.random.default_rng(SEED)
    draw_idx_1 = rng.integers(0, len(ids), size=N_SAMPLES)
    draw_idx_2 = rng.integers(0, len(ids), size=N_SAMPLES)

    vote_results = {}
    per_model_scores = {}
    for name, shift_fn in vote_shift.items():
        residuals = np.stack([train_shift[i] - shift_fn(i) for i in ids])
        residuals = centre_clr(residuals - residuals.mean(axis=0, keepdims=True))
        scores = []
        rmse_rows = []
        territory = []
        for i in ids:
            pred_z = centre_clr(z16[i] + shift_fn(i))
            s1 = inv_clr(pred_z + residuals[draw_idx_1])
            s2 = inv_clr(pred_z + residuals[draw_idx_2])
            obs = raw_share(y21[i])
            es = energy_score(s1, obs, s2)
            mean_pred = s1.mean(axis=0)
            rmse = float(np.sqrt(np.mean((mean_pred - obs) ** 2)))
            scores.append(es)
            rmse_rows.append(rmse)
            territory.append({
                "id": i,
                "name": y21[i]["constituency"],
                "region": y21[i]["region"],
                "energy_score": es,
                "share_rmse": rmse,
            })
        vote_results[name] = {
            "mean_energy_score": float(np.mean(scores)),
            "median_energy_score": float(np.median(scores)),
            "mean_share_rmse": float(np.mean(rmse_rows)),
            "territories": territory,
            "training_residual_component_sd": [float(x) for x in residuals.std(axis=0, ddof=1)],
        }
        per_model_scores[name] = np.asarray(scores)

    vote_selected = min(vote_results, key=lambda k: vote_results[k]["mean_energy_score"])
    vote_boot = {}
    base = per_model_scores["V0_PERSIST"]
    boot_rng = np.random.default_rng(SEED + 1)
    for name in vote_results:
        if name == "V0_PERSIST":
            continue
        vote_boot[name] = paired_bootstrap(per_model_scores[name] - base, boot_rng)

    # Turnout: same frozen family on the logit scale.
    t11 = {i: logit(y11[i]["turnout_rate_reported"]) for i in ids}
    t16 = {i: logit(y16[i]["turnout_rate_reported"]) for i in ids}
    td = {i: t16[i] - t11[i] for i in ids}
    td_arr = np.asarray([td[i] for i in ids])
    tg = float(np.median(td_arr))
    tr = {}
    for region, rids in by_region.items():
        med = float(np.median([td[i] for i in rids]))
        w = len(rids) / (len(rids) + KAPPA)
        tr[region] = w * med + (1 - w) * tg

    turnout_shift = {
        "T0_PERSIST": lambda i: 0.0,
        "T1_GLOBAL_LOGIT_SHIFT": lambda i: tg,
        "T2_REGION_SHRUNK_LOGIT_SHIFT": lambda i: tr[str(y16[i]["region"])],
    }
    turnout_results = {}
    turnout_scores = {}
    for name, shift_fn in turnout_shift.items():
        residuals = np.asarray([td[i] - shift_fn(i) for i in ids], dtype=float)
        residuals = residuals - residuals.mean()
        scores, ae, sqe, territory = [], [], [], []
        for i in ids:
            pred = t16[i] + shift_fn(i)
            s1 = sigmoid(pred + residuals[draw_idx_1])
            s2 = sigmoid(pred + residuals[draw_idx_2])
            obs = float(y21[i]["turnout_rate_reported"])
            score = crps(s1, obs, s2)
            mean_pred = float(np.mean(s1))
            scores.append(score)
            ae.append(abs(mean_pred - obs))
            sqe.append((mean_pred - obs) ** 2)
            territory.append({
                "id": i,
                "name": y21[i]["constituency"],
                "region": y21[i]["region"],
                "crps": score,
                "abs_error": abs(mean_pred - obs),
            })
        turnout_results[name] = {
            "mean_crps": float(np.mean(scores)),
            "median_crps": float(np.median(scores)),
            "mae": float(np.mean(ae)),
            "rmse": float(math.sqrt(np.mean(sqe))),
            "training_residual_sd_logit": float(np.std(residuals, ddof=1)),
            "territories": territory,
        }
        turnout_scores[name] = np.asarray(scores)

    turnout_selected = min(turnout_results, key=lambda k: turnout_results[k]["mean_crps"])
    turnout_boot = {}
    tbase = turnout_scores["T0_PERSIST"]
    boot_rng2 = np.random.default_rng(SEED + 2)
    for name in turnout_results:
        if name == "T0_PERSIST":
            continue
        turnout_boot[name] = paired_bootstrap(turnout_scores[name] - tbase, boot_rng2)

    result = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-BSTAR-HINDCAST-V1",
        "protocol_id": protocol["protocol_id"],
        "leakage_contract": {
            "fit_transition": "2011_to_2016_only",
            "validation_transition": "2016_to_2021",
            "goal75_holdout_used_for_fit": False,
            "post_validation_hyperparameter_search": False,
            "kappa_frozen_pre_result": KAPPA,
            "party_buckets_frozen_pre_result": list(BUCKETS),
            "monte_carlo_samples": N_SAMPLES,
            "seed": SEED,
        },
        "training": {
            "territories": len(ids),
            "regions_under_2016_partition": len(by_region),
            "global_clr_shift": {BUCKETS[j]: float(global_shift[j]) for j in range(len(BUCKETS))},
            "region_shrinkage": region_meta,
        },
        "vote_models": vote_results,
        "vote_paired_bootstrap_vs_persist": vote_boot,
        "selected_vote_model": vote_selected,
        "turnout_models": turnout_results,
        "turnout_paired_bootstrap_vs_persist": turnout_boot,
        "selected_turnout_model": turnout_selected,
        "Bstar_core": {"vote": vote_selected, "turnout": turnout_selected},
        "status": "CORE_TEMPORAL_DYNAMICS_SELECTED_ON_2016_TO_2021; 2026_UNTOUCHED",
        "caveat": "This selects the core historical dynamics family. Structured 2026 candidate/network/event evidence and full hierarchical joint covariance are separate preregistered layers and cannot be tuned on 2021 after this result.",
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "selected_vote_model": vote_selected,
        "vote_scores": {k: v["mean_energy_score"] for k, v in vote_results.items()},
        "selected_turnout_model": turnout_selected,
        "turnout_scores": {k: v["mean_crps"] for k, v in turnout_results.items()},
    }, indent=2))


if __name__ == "__main__":
    main()
