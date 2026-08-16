#!/usr/bin/env python3
"""Quantify what the canonical TAFRA history can and cannot identify.

This is a diagnostic, not a forecasting model.  It freezes the empirical support
for P0-4/P0-5/P0-6 before model fitting starts.
"""
from __future__ import annotations

import json
import math
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HIST = ROOT / "data" / "goal100" / "historical"
OUT = ROOT / "data" / "goal100" / "historical_panel_diagnostic.json"
YEARS = (2011, 2016, 2021)
CORE = ("RNI", "PAM", "PJD", "PI", "MP", "USFP", "PPS", "UC")


def norm(s):
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in t if ch.isalnum())


def load(year):
    p = HIST / f"tafra_legislative_{year}_canonical.json"
    return json.loads(p.read_text(encoding="utf-8"))


def is_local(row):
    return norm(row.get("list_type")) in {"locale", "local"}


def share(row, party):
    denom = row.get("party_vote_sum") or 0
    return (row.get("votes", {}).get(party, 0) / denom) if denom > 0 else None


def pct(x):
    return round(100.0 * x, 6)


def q(values, p):
    if not values:
        return None
    xs = sorted(values)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - k) + xs[hi] * (k - lo)


def main():
    books = {y: load(y) for y in YEARS}
    local = {y: [r for r in books[y]["rows"] if is_local(r)] for y in YEARS}
    byid = {y: {str(r["id_constituency"]): r for r in local[y]} for y in YEARS}

    diag = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-HISTORICAL-PANEL-DIAGNOSTIC-V1",
        "purpose": "empirical support audit for temporal calibration and hierarchical uncertainty",
        "years": {},
        "continuity": {},
        "transitions": {},
        "identifiability": {},
    }

    for y in YEARS:
        rows = local[y]
        list_types = Counter(str(r.get("list_type")) for r in books[y]["rows"])
        parties = sorted({p for r in rows for p in r.get("votes", {})})
        diag["years"][str(y)] = {
            "all_rows": len(books[y]["rows"]),
            "local_rows": len(rows),
            "nonlocal_rows": len(books[y]["rows"]) - len(rows),
            "list_types": dict(sorted(list_types.items())),
            "unique_local_ids": len(byid[y]),
            "local_seats_sum": sum(int(r["seats"]) for r in rows),
            "registered_nonnull_local": sum(r.get("registered_reported") is not None for r in rows),
            "turnout_nonnull_local": sum(r.get("turnout_rate_reported") is not None for r in rows),
            "party_count": len(parties),
            "parties": parties,
        }

    pairs = ((2011, 2016), (2016, 2021), (2011, 2021))
    for a, b in pairs:
        common = sorted(set(byid[a]) & set(byid[b]))
        same_name = sum(norm(byid[a][i]["constituency"]) == norm(byid[b][i]["constituency"]) for i in common)
        same_seats = sum(int(byid[a][i]["seats"]) == int(byid[b][i]["seats"]) for i in common)
        diag["continuity"][f"{a}_{b}"] = {
            "common_local_ids": len(common),
            "coverage_of_later_local_ids": round(len(common) / max(1, len(byid[b])), 6),
            "same_normalized_name": same_name,
            "same_seat_magnitude": same_seats,
            "ids_only_in_earlier": sorted(set(byid[a]) - set(byid[b])),
            "ids_only_in_later": sorted(set(byid[b]) - set(byid[a])),
        }

        trans = {
            "n_common_territories": len(common),
            "turnout_delta_pp": None,
            "core_party_share_delta_pp": {},
        }
        td = []
        for i in common:
            ta, tb = byid[a][i].get("turnout_rate_reported"), byid[b][i].get("turnout_rate_reported")
            if ta is not None and tb is not None:
                td.append(100.0 * (float(tb) - float(ta)))
        if td:
            trans["turnout_delta_pp"] = {
                "n": len(td),
                "median": round(statistics.median(td), 6),
                "p10": round(q(td, .10), 6),
                "p90": round(q(td, .90), 6),
                "mae": round(statistics.mean(abs(x) for x in td), 6),
                "rmse": round(math.sqrt(statistics.mean(x*x for x in td)), 6),
            }

        for party in CORE:
            ds = []
            for i in common:
                sa, sb = share(byid[a][i], party), share(byid[b][i], party)
                if sa is not None and sb is not None:
                    ds.append(100.0 * (sb - sa))
            if ds:
                trans["core_party_share_delta_pp"][party] = {
                    "n": len(ds),
                    "median": round(statistics.median(ds), 6),
                    "p10": round(q(ds, .10), 6),
                    "p90": round(q(ds, .90), 6),
                    "mae": round(statistics.mean(abs(x) for x in ds), 6),
                    "rmse": round(math.sqrt(statistics.mean(x*x for x in ds)), 6),
                }
        diag["transitions"][f"{a}_{b}"] = trans

    triple = sorted(set(byid[2011]) & set(byid[2016]) & set(byid[2021]))
    diag["continuity"]["2011_2016_2021"] = {
        "common_local_ids_all_three": len(triple),
        "coverage_of_2021_local_ids": round(len(triple) / max(1, len(byid[2021])), 6),
    }

    c16_21 = diag["continuity"]["2016_2021"]["common_local_ids"]
    c11_16 = diag["continuity"]["2011_2016"]["common_local_ids"]
    diag["identifiability"] = {
        "vote_transition_calibration": "PASS" if c16_21 >= 90 and c11_16 >= 80 else "PARTIAL",
        "turnout_transition_calibration": "PASS_WITH_REPORTED_RATES" if all(
            diag["years"][str(y)]["turnout_nonnull_local"] >= 80 for y in YEARS
        ) else "PARTIAL",
        "exact_registered_panel": "FAIL_EXPECTED",
        "reason_exact_registered_panel_fails": "2016 and 2021 canonical TAFRA local rows do not report N; missingness is preserved rather than imputed",
        "full_92x92_covariance": "NOT_IDENTIFIABLE",
        "hierarchical_low_rank_covariance": "SUPPORTED",
        "regional_effects": "STRONGEST_ON_2016_2021_CURRENT_REGION_SYSTEM",
        "selection_protocol": "Use prequential 2011->2016 and 2016->2021 predictions; do not reuse the consumed Goal75 territorial holdout as untouched tuning data",
        "gate_Bstar_fit": "OPEN" if c16_21 >= 90 and c11_16 >= 80 else "BLOCKED_BY_CROSSWALK",
    }

    OUT.write_text(json.dumps(diag, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(diag, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
