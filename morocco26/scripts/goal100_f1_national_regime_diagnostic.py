#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
OUT = G / "f1_national_regime_diagnostic.json"

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)
PARTIES = hb.PARTIES


def rj(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_local(year: int):
    d = rj(HIST / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in d["rows"] if str(r.get("list_type", "")).lower() in {"local", "locale"}]
    if len(rows) != 92:
        raise RuntimeError(f"{year}: expected 92 local rows")
    return rows


def shares(row):
    x = hb.bucket_counts(row)
    return x / x.sum()


def zrow(row):
    return hb.centre_clr(hb.clr(row))


def panel(consts, rows):
    m = hb.match_rows(consts, rows)
    cids = [c["constituency_id"] for c in consts]
    z = np.stack([zrow(m[c]) for c in cids])
    s = np.stack([shares(m[c]) for c in cids])
    return z, s


def rmse(a, b):
    return float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))


def transition(prev_z, prev_s, next_z, next_s):
    national = hb.centre_clr(next_z.mean(axis=0) - prev_z.mean(axis=0))
    oracle_s = hb.inv_clr(hb.centre_clr(prev_z + national[None, :]))
    persistence_rmse = rmse(prev_s, next_s)
    oracle_rmse = rmse(oracle_s, next_s)
    residual = hb.centre_clr((next_z - prev_z) - national[None, :])
    territorial_sd = residual.std(axis=0, ddof=1)
    ratio = np.abs(national) / np.maximum(territorial_sd, 1e-12)
    return {
        "national_clr_swing": {p: float(national[i]) for i, p in enumerate(PARTIES)},
        "national_clr_rms": float(np.sqrt(np.mean(national ** 2))),
        "territorial_residual_sd": {p: float(territorial_sd[i]) for i, p in enumerate(PARTIES)},
        "abs_national_to_territorial_sd": {p: float(ratio[i]) for i, p in enumerate(PARTIES)},
        "persistence_share_rmse": persistence_rmse,
        "oracle_true_national_swing_share_rmse": oracle_rmse,
        "oracle_relative_rmse_improvement": float((persistence_rmse - oracle_rmse) / persistence_rmse),
        "territory_equal_mean_share_prev": {p: float(prev_s[:, i].mean()) for i, p in enumerate(PARTIES)},
        "territory_equal_mean_share_next": {p: float(next_s[:, i].mean()) for i, p in enumerate(PARTIES)},
        "territory_equal_mean_share_delta": {p: float(next_s[:, i].mean() - prev_s[:, i].mean()) for i, p in enumerate(PARTIES)},
    }


def main():
    consts = hb.load_constituencies()
    z11, s11 = panel(consts, load_local(2011))
    z16, s16 = panel(consts, load_local(2016))
    z21, s21 = panel(consts, load_local(2021))
    a = transition(z11, s11, z16, s16)
    b = transition(z16, s16, z21, s21)
    v1 = np.array([a["national_clr_swing"][p] for p in PARTIES])
    v2 = np.array([b["national_clr_swing"][p] for p in PARTIES])
    corr = float(np.corrcoef(v1, v2)[0, 1])
    cosine = float(v1 @ v2 / (np.linalg.norm(v1) * np.linalg.norm(v2)))
    signs = np.sign(v1) == np.sign(v2)
    result = {
        "schema_version": "1.0",
        "diagnostic_id": "M26-GOAL100-F1-NATIONAL-REGIME-DIAGNOSTIC",
        "status": "DIAGNOSTIC_ONLY_OUTCOME_AWARE_NOT_A_FORECAST_MODEL",
        "scientific_boundary": "The true held-out national swing is deliberately used as an oracle to decompose historical forecast error. These quantities may diagnose model structure but may not be used as a prospective coefficient or claim of blind prediction.",
        "transition_2011_TO_2016": a,
        "transition_2016_TO_2021": b,
        "cross_transition_national_swing": {
            "pearson_correlation": corr,
            "cosine_similarity": cosine,
            "same_sign_party_fraction": float(signs.mean()),
            "same_sign_parties": [p for i, p in enumerate(PARTIES) if signs[i]],
            "sign_flip_parties": [p for i, p in enumerate(PARTIES) if not signs[i]],
        },
        "interpretation_rule": "If oracle national swing materially reduces RMSE while national swing direction is unstable across transitions, the conventional bottleneck is prospective estimation of party-level national state, not further global uncertainty inflation or candidate micro-residuals."
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "rmse_improvement_2016": a["oracle_relative_rmse_improvement"],
        "rmse_improvement_2021": b["oracle_relative_rmse_improvement"],
        "national_swing_corr": corr,
        "national_swing_cosine": cosine,
        "same_sign_fraction": float(signs.mean()),
        "sign_flip_parties": result["cross_transition_national_swing"]["sign_flip_parties"]
    }, sort_keys=True))


if __name__ == "__main__":
    main()
