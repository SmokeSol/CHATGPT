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
CONTRACT = G / "f1_baseline_rebuild_contract_v2.json"
OUT = G / "f1_full_support_uncertainty_dev_v2.json"

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


def robust_project(s: np.ndarray, cap: float) -> np.ndarray:
    a = np.asarray(s, float)
    a = FLOOR + (1.0 - K * FLOOR) * a
    a = a / a.sum(axis=-1, keepdims=True)
    flat = a.reshape(-1, K)
    bad = np.max(flat, axis=1) > cap + 1e-12
    if np.any(bad):
        b = flat[bad]
        lo = np.zeros(len(b))
        hi = np.ones(len(b))
        for _ in range(36):
            mid = (lo + hi) / 2.0
            p = np.power(b, mid[:, None])
            p /= p.sum(axis=1, keepdims=True)
            mx = p.max(axis=1)
            hi = np.where(mx > cap, mid, hi)
            lo = np.where(mx <= cap, mid, lo)
        p = np.power(b, lo[:, None])
        p /= p.sum(axis=1, keepdims=True)
        flat[bad] = p
    return flat.reshape(a.shape)


def transition(consts, prev_rows, next_rows):
    mp = hb.match_rows(consts, prev_rows)
    mn = hb.match_rows(consts, next_rows)
    cids = [c["constituency_id"] for c in consts]
    zp = np.stack([cclr(mp[c]) for c in cids])
    zn = np.stack([cclr(mn[c]) for c in cids])
    residual = hb.centre_clr(zn - zp)
    national = hb.centre_clr(residual.mean(axis=0))
    territorial = hb.centre_clr(residual - national[None, :])
    actual = np.stack([share(mn[c]) for c in cids])
    return {
        "cids": cids,
        "prior_z": zp,
        "actual": actual,
        "national": national,
        "territorial": territorial,
    }


def energy_sqrt(samples, y):
    xs = np.sqrt(samples)
    yy = np.sqrt(y)
    first = np.linalg.norm(xs - yy[None, :], axis=1).mean()
    second = np.linalg.norm(xs - np.roll(xs, 1, axis=0), axis=1).mean()
    return float(first - 0.5 * second)


def pooled_territorial(train_territorial: np.ndarray, pool_fraction: float) -> np.ndarray:
    terr = np.asarray(train_territorial, float)
    sd = terr.std(axis=0, ddof=1)
    pooled_var = float(np.mean(sd ** 2))
    target_sd = np.sqrt((1.0 - pool_fraction) * (sd ** 2) + pool_fraction * pooled_var)
    ratio = target_sd / np.maximum(sd, 1e-8)
    adjusted = terr * ratio[None, :]
    return hb.centre_clr(adjusted)


def evaluate(train, held, national_scale, iso_fraction, territorial_scale, pool_fraction, cap, draws, seed, cov80_floor, cov95_floor):
    rng = np.random.default_rng(seed)
    z_rank = rng.standard_normal(draws)
    iso = rng.standard_normal((draws, K))
    iso = hb.centre_clr(iso)
    iso /= math.sqrt(1.0 - 1.0 / K)
    idx = rng.integers(0, len(train["territorial"]), size=(len(held["cids"]), draws))

    nat = np.asarray(train["national"], float)
    nat_rms = float(np.sqrt(np.mean(nat ** 2)))
    rank_draw = z_rank[:, None] * nat[None, :]
    iso_draw = nat_rms * iso
    national_draw = national_scale * (
        math.sqrt(max(0.0, 1.0 - iso_fraction)) * rank_draw
        + math.sqrt(iso_fraction) * iso_draw
    )
    national_draw = hb.centre_clr(national_draw)

    terr = pooled_territorial(train["territorial"], pool_fraction)
    covered80 = np.zeros((len(held["cids"]), K), bool)
    covered95 = np.zeros_like(covered80)
    widths80, widths95, energies, means = [], [], [], []

    for i in range(len(held["cids"])):
        shock = national_draw + territorial_scale * terr[idx[i]]
        z = hb.centre_clr(held["prior_z"][i][None, :] + shock)
        s = robust_project(hb.inv_clr(z), cap)
        y = held["actual"][i]
        q10, q90 = np.quantile(s, [0.10, 0.90], axis=0)
        q025, q975 = np.quantile(s, [0.025, 0.975], axis=0)
        covered80[i] = (y >= q10) & (y <= q90)
        covered95[i] = (y >= q025) & (y <= q975)
        widths80.append(q90 - q10)
        widths95.append(q975 - q025)
        energies.append(energy_sqrt(s, y))
        means.append(s.mean(axis=0))

    cov80 = covered80.mean(axis=0)
    cov95 = covered95.mean(axis=0)
    means = np.stack(means)
    actual = held["actual"]
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
        "national_training_rms": nat_rms,
    }


def main():
    contract = rj(CONTRACT)
    if contract.get("status") != "FROZEN_BEFORE_F1_FULL_SUPPORT_UNCERTAINTY_EXECUTION":
        raise RuntimeError("F1 V2 contract not frozen")
    u = contract["uncertainty_family"]
    g = contract["gates"]
    draws = int(u["draws_per_territory"])
    cov80_floor = float(g["party_coverage80_floor"])
    cov95_floor = float(g["party_coverage95_floor"])

    consts = hb.load_constituencies()
    r11, r16, r21 = load_local(2011), load_local(2016), load_local(2021)
    t16 = transition(consts, r11, r16)
    t21 = transition(consts, r16, r21)

    allshares = []
    for rows in (r11, r16, r21):
        m = hb.match_rows(consts, rows)
        allshares.extend(share(m[c["constituency_id"]]) for c in consts)
    histmax = float(np.max(np.stack(allshares)))
    cap = float(min(0.85, histmax + 0.05))

    candidates = []
    for ns in u["national_scale_grid"]:
        for iso in u["national_isotropic_fraction_grid"]:
            for ts in u["territorial_scale_grid"]:
                for pool in u["territorial_pool_fraction_grid"]:
                    f16 = evaluate(t21, t16, float(ns), float(iso), float(ts), float(pool), cap, draws, int(u["seed_fold_2011_to_2016"]), cov80_floor, cov95_floor)
                    f21 = evaluate(t16, t21, float(ns), float(iso), float(ts), float(pool), cap, draws, int(u["seed_fold_2016_to_2021"]), cov80_floor, cov95_floor)
                    eligible = bool(f16["party_coverage_gate"] and f21["party_coverage_gate"])
                    candidates.append({
                        "national_scale": float(ns),
                        "national_isotropic_fraction": float(iso),
                        "territorial_scale": float(ts),
                        "territorial_pool_fraction": float(pool),
                        "heldout_2011_TO_2016": f16,
                        "heldout_2016_TO_2021": f21,
                        "eligible": eligible,
                        "selection_coverage_shortfall": float(f16["coverage_shortfall"] + f21["coverage_shortfall"]),
                        "selection_calibration_error": float((f16["calibration_abs_error"] + f21["calibration_abs_error"]) / 2.0),
                        "selection_energy": float((f16["mean_energy_score"] + f21["mean_energy_score"]) / 2.0),
                        "selection_width95": float((f16["mean_interval_width95"] + f21["mean_interval_width95"]) / 2.0),
                    })

    eligible = [c for c in candidates if c["eligible"]]
    selected = None
    if eligible:
        selected = sorted(eligible, key=lambda c: (c["selection_calibration_error"], c["selection_energy"], c["selection_width95"]))[0]
        sharp = selected["selection_width95"] < F0_WIDTH95
        status = "F1_FULL_SUPPORT_UNCERTAINTY_READY_FOR_REFIT" if sharp else "F1_FULL_SUPPORT_UNCERTAINTY_FAIL_SHARPNESS"
    else:
        sharp = False
        status = "F1_FULL_SUPPORT_UNCERTAINTY_NOT_READY_PARTY_CALIBRATION"

    best_near_miss = sorted(candidates, key=lambda c: (c["selection_coverage_shortfall"], c["selection_calibration_error"], c["selection_energy"], c["selection_width95"]))[0]
    result = {
        "schema_version": "2.0",
        "result_id": "M26-GOAL100-F1-FULL-SUPPORT-UNCERTAINTY-DEV-V2",
        "contract_id": contract["contract_id"],
        "scientific_status": "POST_2021_DEVELOPMENT_2026_UNTOUCHED",
        "historical_max_bucket_share": histmax,
        "robust_simplex_cap": cap,
        "coverage_floors": {"80": cov80_floor, "95": cov95_floor},
        "candidate_count": len(candidates),
        "eligible_candidate_count": len(eligible),
        "selected_candidate": selected,
        "best_near_miss": best_near_miss,
        "sharpness_improves_over_F0_v2": sharp,
        "F0_modified": False,
        "E_reason_reopened": False,
        "status": status,
        "next_action": (
            "Refit this exact full-support family on both historical transitions, freeze its 2026 parameterization, then update list support only with admissible 2026 roster evidence before legal seat simulation."
            if status == "F1_FULL_SUPPORT_UNCERTAINTY_READY_FOR_REFIT"
            else "Do not relax gates. If calibration still fails, the next conventional family must explicitly model party-specific temporal regime uncertainty rather than adding global width."
        ),
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    compact_source = selected if selected is not None else best_near_miss
    compact = {
        "status": status,
        "eligible": len(eligible),
        "candidate_count": len(candidates),
        "reported": "selected" if selected is not None else "best_near_miss",
        "params": {
            "national_scale": compact_source["national_scale"],
            "national_isotropic_fraction": compact_source["national_isotropic_fraction"],
            "territorial_scale": compact_source["territorial_scale"],
            "territorial_pool_fraction": compact_source["territorial_pool_fraction"],
        },
        "coverage_shortfall": compact_source["selection_coverage_shortfall"],
        "calibration_error": compact_source["selection_calibration_error"],
        "energy": compact_source["selection_energy"],
        "width95": compact_source["selection_width95"],
        "fold16_min80": compact_source["heldout_2011_TO_2016"]["min_party_coverage80"],
        "fold16_min95": compact_source["heldout_2011_TO_2016"]["min_party_coverage95"],
        "fold21_min80": compact_source["heldout_2016_TO_2021"]["min_party_coverage80"],
        "fold21_min95": compact_source["heldout_2016_TO_2021"]["min_party_coverage95"],
    }
    print(json.dumps(compact, sort_keys=True))


if __name__ == "__main__":
    main()
