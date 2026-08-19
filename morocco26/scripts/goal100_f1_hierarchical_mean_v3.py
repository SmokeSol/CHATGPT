#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
CONTRACT = G / "f1_baseline_rebuild_contract_v3.json"
OUT = G / "f1_hierarchical_mean_dev_v3.json"

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)
PARTIES = hb.PARTIES
K = len(PARTIES)
FLOOR = 0.0005
F0_WIDTH95 = 0.5445930074002108


def rj(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_local(year: int):
    d = rj(HIST / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in d["rows"] if str(r.get("list_type", "")).lower() in {"local", "locale"}]
    if len(rows) != 92:
        raise RuntimeError(f"{year}: expected 92 local rows, got {len(rows)}")
    return rows


def share(row):
    x = hb.bucket_counts(row)
    return x / x.sum()


def cclr(row):
    return hb.centre_clr(hb.clr(row))


def transition(consts, prev_rows, next_rows):
    mp = hb.match_rows(consts, prev_rows)
    mn = hb.match_rows(consts, next_rows)
    cids = [c["constituency_id"] for c in consts]
    zp = np.stack([cclr(mp[c]) for c in cids])
    zn = np.stack([cclr(mn[c]) for c in cids])
    actual = np.stack([share(mn[c]) for c in cids])
    return {"cids": cids, "prior_z": zp, "next_z": zn, "actual": actual}


def robust_project(s: np.ndarray, cap: float) -> np.ndarray:
    a = np.asarray(s, float)
    a = FLOOR + (1.0 - K * FLOOR) * a
    a = a / a.sum(axis=-1, keepdims=True)
    flat = a.reshape(-1, K)
    bad = np.max(flat, axis=1) > cap + 1e-12
    if np.any(bad):
        b = flat[bad]
        lo = np.zeros(len(b)); hi = np.ones(len(b))
        for _ in range(36):
            mid = (lo + hi) / 2.0
            p = np.power(b, mid[:, None]); p /= p.sum(axis=1, keepdims=True)
            mx = p.max(axis=1)
            hi = np.where(mx > cap, mid, hi)
            lo = np.where(mx <= cap, mid, lo)
        p = np.power(b, lo[:, None]); p /= p.sum(axis=1, keepdims=True)
        flat[bad] = p
    return flat.reshape(a.shape)


def fit_mean_and_residual(train, slope_pool_fraction: float, clip_low: float, clip_high: float):
    zp = np.asarray(train["prior_z"], float)
    zn = np.asarray(train["next_z"], float)
    mu_prev = zp.mean(axis=0)
    mu_next = zn.mean(axis=0)
    x = zp - mu_prev[None, :]
    y = zn - mu_next[None, :]
    denom = np.sum(x * x, axis=0)
    party = np.sum(x * y, axis=0) / np.maximum(denom, 1e-12)
    pooled = float(np.sum(x * y) / max(float(np.sum(x * x)), 1e-12))
    party = np.clip(party, clip_low, clip_high)
    pooled = float(np.clip(pooled, clip_low, clip_high))
    slopes = (1.0 - slope_pool_fraction) * party + slope_pool_fraction * pooled
    pred = hb.centre_clr(mu_prev[None, :] + x * slopes[None, :])
    residual = hb.centre_clr(zn - pred)
    national = hb.centre_clr(residual.mean(axis=0))
    territorial = hb.centre_clr(residual - national[None, :])
    return {
        "slopes": slopes,
        "party_raw_slopes": party,
        "pooled_slope": pooled,
        "national_residual": national,
        "territorial_residual": territorial,
    }


def predict_mean(held, slopes):
    zp = np.asarray(held["prior_z"], float)
    mu = zp.mean(axis=0)
    x = zp - mu[None, :]
    return hb.centre_clr(mu[None, :] + x * slopes[None, :])


def pooled_territorial(terr: np.ndarray, pool_fraction: float):
    terr = np.asarray(terr, float)
    sd = terr.std(axis=0, ddof=1)
    pooled_var = float(np.mean(sd ** 2))
    target_sd = np.sqrt((1.0 - pool_fraction) * (sd ** 2) + pool_fraction * pooled_var)
    ratio = target_sd / np.maximum(sd, 1e-8)
    return hb.centre_clr(terr * ratio[None, :])


def energy_sqrt(samples, y):
    xs = np.sqrt(samples); yy = np.sqrt(y)
    return float(np.linalg.norm(xs - yy[None, :], axis=1).mean() - 0.5 * np.linalg.norm(xs - np.roll(xs, 1, axis=0), axis=1).mean())


def evaluate(train, held, slope_pool_fraction, national_scale, territorial_scale, territorial_pool_fraction, cap, draws, seed, cov80_floor, cov95_floor, clip_low, clip_high):
    fitted = fit_mean_and_residual(train, slope_pool_fraction, clip_low, clip_high)
    pred_z = predict_mean(held, fitted["slopes"])
    nat = fitted["national_residual"]
    nat_rms = float(np.sqrt(np.mean(nat ** 2)))
    terr = pooled_territorial(fitted["territorial_residual"], territorial_pool_fraction)

    rng = np.random.default_rng(seed)
    iso = rng.standard_normal((draws, K))
    iso = hb.centre_clr(iso) / math.sqrt(1.0 - 1.0 / K)
    national_draw = hb.centre_clr(national_scale * nat_rms * iso)
    idx = rng.integers(0, len(terr), size=(len(held["cids"]), draws))

    covered80 = np.zeros((len(held["cids"]), K), bool)
    covered95 = np.zeros_like(covered80)
    widths80, widths95, energies, means = [], [], [], []
    for i in range(len(held["cids"])):
        shock = national_draw + territorial_scale * terr[idx[i]]
        z = hb.centre_clr(pred_z[i][None, :] + shock)
        s = robust_project(hb.inv_clr(z), cap)
        y = held["actual"][i]
        q10, q90 = np.quantile(s, [0.10, 0.90], axis=0)
        q025, q975 = np.quantile(s, [0.025, 0.975], axis=0)
        covered80[i] = (y >= q10) & (y <= q90)
        covered95[i] = (y >= q025) & (y <= q975)
        widths80.append(q90 - q10); widths95.append(q975 - q025)
        energies.append(energy_sqrt(s, y)); means.append(s.mean(axis=0))

    cov80 = covered80.mean(axis=0); cov95 = covered95.mean(axis=0)
    means = np.stack(means); actual = held["actual"]
    shortfall = float(np.maximum(0.0, cov80_floor - cov80).sum() + np.maximum(0.0, cov95_floor - cov95).sum())
    return {
        "coverage80_by_party": {p: float(cov80[j]) for j, p in enumerate(PARTIES)},
        "coverage95_by_party": {p: float(cov95[j]) for j, p in enumerate(PARTIES)},
        "min_party_coverage80": float(cov80.min()),
        "min_party_coverage95": float(cov95.min()),
        "party_coverage_gate": bool(np.all(cov80 >= cov80_floor) and np.all(cov95 >= cov95_floor)),
        "coverage_shortfall": shortfall,
        "calibration_abs_error": float(np.mean(np.abs(cov80 - 0.80)) + np.mean(np.abs(cov95 - 0.95))),
        "mean_energy_score": float(np.mean(energies)),
        "mean_interval_width80": float(np.mean(np.stack(widths80))),
        "mean_interval_width95": float(np.mean(np.stack(widths95))),
        "mean_share_rmse": float(np.sqrt(np.mean((means - actual) ** 2))),
        "trained_slopes": {p: float(fitted["slopes"][j]) for j, p in enumerate(PARTIES)},
        "raw_party_slopes": {p: float(fitted["party_raw_slopes"][j]) for j, p in enumerate(PARTIES)},
        "pooled_slope": float(fitted["pooled_slope"]),
        "national_training_rms": nat_rms,
    }


def main():
    contract = rj(CONTRACT)
    if contract.get("status") != "FROZEN_BEFORE_F1_HIERARCHICAL_MEAN_EXECUTION":
        raise RuntimeError("F1 V3 contract not frozen")
    m = contract["mean_family"]; u = contract["uncertainty_family"]; g = contract["gates"]
    clip_low, clip_high = map(float, m["slope_clip"])
    cov80_floor = float(g["party_coverage80_floor"]); cov95_floor = float(g["party_coverage95_floor"])
    draws = int(u["draws_per_territory"])

    consts = hb.load_constituencies()
    r11, r16, r21 = load_local(2011), load_local(2016), load_local(2021)
    t16 = transition(consts, r11, r16); t21 = transition(consts, r16, r21)
    allshares = []
    for rows in (r11, r16, r21):
        mm = hb.match_rows(consts, rows)
        allshares.extend(share(mm[c["constituency_id"]]) for c in consts)
    histmax = float(np.max(np.stack(allshares))); cap = float(min(0.85, histmax + 0.05))

    candidates = []
    for sp in m["party_slope_pool_fraction_grid"]:
        for ns in u["national_scale_grid"]:
            for ts in u["territorial_scale_grid"]:
                f16 = evaluate(t21, t16, float(sp), float(ns), float(ts), float(u["territorial_pool_fraction"]), cap, draws, int(u["seed_fold_2011_to_2016"]), cov80_floor, cov95_floor, clip_low, clip_high)
                f21 = evaluate(t16, t21, float(sp), float(ns), float(ts), float(u["territorial_pool_fraction"]), cap, draws, int(u["seed_fold_2016_to_2021"]), cov80_floor, cov95_floor, clip_low, clip_high)
                eligible = bool(f16["party_coverage_gate"] and f21["party_coverage_gate"])
                candidates.append({
                    "party_slope_pool_fraction": float(sp),
                    "national_scale": float(ns),
                    "territorial_scale": float(ts),
                    "territorial_pool_fraction": float(u["territorial_pool_fraction"]),
                    "heldout_2011_TO_2016": f16,
                    "heldout_2016_TO_2021": f21,
                    "eligible": eligible,
                    "selection_coverage_shortfall": float(f16["coverage_shortfall"] + f21["coverage_shortfall"]),
                    "selection_calibration_error": float((f16["calibration_abs_error"] + f21["calibration_abs_error"]) / 2.0),
                    "selection_energy": float((f16["mean_energy_score"] + f21["mean_energy_score"]) / 2.0),
                    "selection_width95": float((f16["mean_interval_width95"] + f21["mean_interval_width95"]) / 2.0),
                    "selection_rmse": float((f16["mean_share_rmse"] + f21["mean_share_rmse"]) / 2.0),
                })

    elig = [c for c in candidates if c["eligible"]]
    if elig:
        selected = sorted(elig, key=lambda c: (c["selection_calibration_error"], c["selection_energy"], c["selection_width95"]))[0]
        sharp = selected["selection_width95"] < F0_WIDTH95
        status = "F1_HIERARCHICAL_MEAN_READY_FOR_REFIT" if sharp else "F1_HIERARCHICAL_MEAN_FAIL_SHARPNESS"
    else:
        selected = None; sharp = False; status = "F1_HIERARCHICAL_MEAN_NOT_READY_PARTY_CALIBRATION"

    best = sorted(candidates, key=lambda c: (c["selection_coverage_shortfall"], c["selection_calibration_error"], c["selection_energy"], c["selection_width95"]))[0]
    result = {
        "schema_version": "3.0",
        "result_id": "M26-GOAL100-F1-HIERARCHICAL-MEAN-DEV-V3",
        "contract_id": contract["contract_id"],
        "scientific_status": "POST_2021_DEVELOPMENT_2026_UNTOUCHED",
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(elig),
        "selected_candidate": selected,
        "best_near_miss": best,
        "coverage_floors": {"80": cov80_floor, "95": cov95_floor},
        "robust_simplex_cap": cap,
        "sharpness_improves_over_F0_v2": sharp,
        "F0_modified": False,
        "E_reason_reopened": False,
        "status": status,
        "next_action": (
            "Refit this exact hierarchical mean and residual family on both historical transitions and freeze the conventional 2026 F1 parameterization before any agentic layer."
            if status == "F1_HIERARCHICAL_MEAN_READY_FOR_REFIT"
            else "Do not widen uncertainty or reopen E_reason. If this family fails, persistence is not conditionally adequate and the next conventional model must introduce explicit national party-regime state rather than local candidate reasoning."
        ),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    x = selected or best
    print(json.dumps({
        "status": status,
        "eligible": len(elig),
        "candidate_count": len(candidates),
        "reported": "selected" if selected else "best_near_miss",
        "params": {"party_slope_pool_fraction": x["party_slope_pool_fraction"], "national_scale": x["national_scale"], "territorial_scale": x["territorial_scale"]},
        "coverage_shortfall": x["selection_coverage_shortfall"],
        "calibration_error": x["selection_calibration_error"],
        "energy": x["selection_energy"],
        "width95": x["selection_width95"],
        "rmse": x["selection_rmse"],
        "fold16_min80": x["heldout_2011_TO_2016"]["min_party_coverage80"],
        "fold16_min95": x["heldout_2011_TO_2016"]["min_party_coverage95"],
        "fold21_min80": x["heldout_2016_TO_2021"]["min_party_coverage80"],
        "fold21_min95": x["heldout_2016_TO_2021"]["min_party_coverage95"]
    }, sort_keys=True))


if __name__ == "__main__":
    main()
