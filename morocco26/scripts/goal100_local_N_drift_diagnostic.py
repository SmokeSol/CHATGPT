#!/usr/bin/env python3
"""Measure historical drift in local registered-voter shares for the 2026 N prior.

Only exact normalized constituency-name matches between 2007 and 2011 are used.
This is a variance diagnostic, not permission to pretend that 2007 boundaries are
identical to 2011.  The 2026 posterior remains constrained to the official
15,801,162 national total.
"""
from __future__ import annotations

import json
import math
import re
import unicodedata
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW07 = ROOT / "data" / "goal100" / "older_history_probe" / "raw" / "parlement-elections-2007-1-0.xlsx"
CAN11 = ROOT / "data" / "goal100" / "historical" / "tafra_legislative_2011_canonical.json"
OUT = ROOT / "data" / "goal100" / "local_N_drift_diagnostic.json"
N2026 = 15_801_162


def norm(value):
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def q(x, p):
    return float(np.quantile(np.asarray(x, dtype=float), p))


def main():
    if not RAW07.exists() or not CAN11.exists():
        raise RuntimeError("required canonical/raw inputs missing")
    d07 = pd.read_excel(RAW07, sheet_name="données")
    d07 = d07[d07["typeListe"].astype(str).str.lower().isin(["locale", "local"])].copy()
    if d07["nInscrits"].isna().any():
        raise RuntimeError("2007 local N unexpectedly missing")
    j11 = json.loads(CAN11.read_text(encoding="utf-8"))
    r11 = [r for r in j11["rows"] if str(r.get("list_type", "")).lower() in {"locale", "local"}]
    if len(r11) != 92 or any(r.get("registered_reported") is None for r in r11):
        raise RuntimeError("2011 canonical local N gate failed")

    total07 = float(d07["nInscrits"].sum())
    total11 = float(sum(float(r["registered_reported"]) for r in r11))

    m07 = {}
    duplicates07 = []
    for _, row in d07.iterrows():
        key = norm(row["circonscription"])
        item = {"name": str(row["circonscription"]), "N": int(row["nInscrits"]), "seats": int(row["nSieges"])}
        if key in m07:
            duplicates07.append(key)
        else:
            m07[key] = item
    m11 = {}
    duplicates11 = []
    for row in r11:
        key = norm(row["constituency"])
        item = {"name": row["constituency"], "N": int(row["registered_reported"]), "seats": int(row["seats"]), "id": row["id_constituency"]}
        if key in m11:
            duplicates11.append(key)
        else:
            m11[key] = item

    common = sorted(set(m07) & set(m11))
    rows = []
    log_share_drift = []
    relative_N_change = []
    stable_magnitude = []
    for key in common:
        a, b = m07[key], m11[key]
        s07, s11 = a["N"] / total07, b["N"] / total11
        ld = math.log(s11 / s07)
        rc = b["N"] / a["N"] - 1.0
        same = a["seats"] == b["seats"]
        rows.append({
            "key": key,
            "name_2007": a["name"],
            "name_2011": b["name"],
            "id_2011": b["id"],
            "seats_2007": a["seats"],
            "seats_2011": b["seats"],
            "same_seat_magnitude": same,
            "N_2007": a["N"],
            "N_2011": b["N"],
            "national_share_2007": s07,
            "national_share_2011": s11,
            "log_national_share_drift": ld,
            "relative_N_change": rc,
        })
        log_share_drift.append(ld)
        relative_N_change.append(rc)
        if same:
            stable_magnitude.append(ld)

    absd = np.abs(np.asarray(log_share_drift))
    absstable = np.abs(np.asarray(stable_magnitude)) if stable_magnitude else np.asarray([])

    # Deterministic centre only; not a claim that 2011 shares are exact in 2026.
    # Largest-remainder integer rounding makes the centre sum exactly to N2026.
    shares11 = np.asarray([float(r["registered_reported"]) for r in r11], dtype=float)
    shares11 /= shares11.sum()
    raw = shares11 * N2026
    base = np.floor(raw).astype(int)
    remainder = N2026 - int(base.sum())
    order = np.argsort(-(raw - base))
    base[order[:remainder]] += 1
    centre = []
    for r, n in zip(r11, base):
        centre.append({"id": r["id_constituency"], "name": r["constituency"], "N_center_scaled_2011_share": int(n)})
    assert sum(x["N_center_scaled_2011_share"] for x in centre) == N2026

    report = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-LOCAL-N-DRIFT-V1",
        "official_2026_national_N": N2026,
        "historical": {
            "local_rows_2007": int(len(d07)),
            "local_rows_2011": len(r11),
            "national_sum_local_N_2007": int(total07),
            "national_sum_local_N_2011": int(total11),
            "exact_normalized_name_matches": len(common),
            "exact_match_coverage_of_2011": len(common) / len(r11),
            "same_seat_magnitude_matches": sum(r["same_seat_magnitude"] for r in rows),
            "duplicate_normalized_names_2007": duplicates07,
            "duplicate_normalized_names_2011": duplicates11,
        },
        "drift": {
            "metric": "log of constituency share of national registered voters, 2011 minus 2007",
            "n": len(log_share_drift),
            "median": float(np.median(log_share_drift)),
            "sd": float(np.std(log_share_drift, ddof=1)),
            "median_abs": float(np.median(absd)),
            "p80_abs": q(absd, 0.80),
            "p90_abs": q(absd, 0.90),
            "p95_abs": q(absd, 0.95),
            "stable_magnitude_n": len(stable_magnitude),
            "stable_magnitude_sd": float(np.std(stable_magnitude, ddof=1)) if len(stable_magnitude) > 1 else None,
            "stable_magnitude_p90_abs": q(absstable, 0.90) if len(absstable) else None,
            "warning": "This is a four-year historical drift diagnostic, not a stationary-law claim for 2011->2026. It can set a variance floor; it cannot by itself identify the 2026 local N vector."
        },
        "point_centre": {
            "method": "2011 local registered-voter shares scaled to official 2026 national total",
            "epistemic_status": "PRIOR_CENTRE_NOT_OFFICIAL_LOCAL_COUNTS",
            "rows": centre
        },
        "matches": rows,
        "posterior_design_implication": "Use the scaled-2011 vector only as a centre. Perturb local log-shares jointly with a heavy-tailed/shrunk prior no tighter than observed historical share drift, then renormalize and integer-round to exactly 15,801,162. Update centre with HCP/RGPH demographic growth or official local roll data when available.",
        "status": "EMPIRICAL_VARIANCE_FLOOR_ESTIMATED_IF_MATCH_COVERAGE_IS_SUFFICIENT"
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "matches": len(common),
        "coverage": len(common)/len(r11),
        "same_magnitude": report["historical"]["same_seat_magnitude_matches"],
        "drift_sd": report["drift"]["sd"],
        "p90_abs": report["drift"]["p90_abs"],
        "stable_magnitude_p90_abs": report["drift"]["stable_magnitude_p90_abs"],
    }, indent=2))


if __name__ == "__main__":
    main()
