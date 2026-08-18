#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import math
import zipfile
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

EXPECTED = {
    2016: "1ab8a01626244a094e97f874791576cc40270f21d135183d2e4b25ab41fa5a8d",
    2021: "5e0c8c70bb9e8488eb51866ca225a0babd5fcbf33bc0441238f8688e01a265f3",
}
COLS = {
    2016: ["URBRUR","Q1","Q97","Q95","Q101","Q4A","Q4B","Q8A","Q8B","Q8E","Q14","Q30","Q41","Q52B","Q52E","Q53B","Q53D","Q66A","Q66B","Q66K","Q59B","Q92B"],
    2021: ["URBRUR","Q1","Q97","Q95A","Q101","Q4A","Q4B","Q7A","Q7B","Q7E","Q9","Q21","Q37","Q41B","Q41D","Q42B","Q42D","Q50A","Q50B","Q50J","Q38B","Q92I"],
}
MAP = {
    2016: {
        "economic_condition": ("Q4A",1,5), "living_conditions": ("Q4B",1,5),
        "food_deprivation": ("Q8A",0,4), "water_deprivation": ("Q8B",0,4), "cash_deprivation": ("Q8E",0,4),
        "political_discussion": ("Q14",0,2), "democracy_support": ("Q30",1,3), "democracy_satisfaction": ("Q41",0,4),
        "trust_parliament": ("Q52B",0,3), "trust_local_government": ("Q52E",0,3),
        "perceived_mp_corruption": ("Q53B",0,3), "perceived_local_corruption": ("Q53D",0,3),
        "government_economic_performance": ("Q66A",1,4), "government_poverty_performance": ("Q66B",1,4),
        "government_anticorruption_performance": ("Q66K",1,4), "local_responsiveness": ("Q59B",0,3),
        "internet_use": ("Q92B",0,4),
    },
    2021: {
        "economic_condition": ("Q4A",1,5), "living_conditions": ("Q4B",1,5),
        "food_deprivation": ("Q7A",0,4), "water_deprivation": ("Q7B",0,4), "cash_deprivation": ("Q7E",0,4),
        "political_discussion": ("Q9",0,2), "democracy_support": ("Q21",1,3), "democracy_satisfaction": ("Q37",0,4),
        "trust_parliament": ("Q41B",0,3), "trust_local_government": ("Q41D",0,3),
        "perceived_mp_corruption": ("Q42B",0,3), "perceived_local_corruption": ("Q42D",0,3),
        "government_economic_performance": ("Q50A",1,4), "government_poverty_performance": ("Q50B",1,4),
        "government_anticorruption_performance": ("Q50J",1,4), "local_responsiveness": ("Q38B",0,3),
        "internet_use": ("Q92I",0,4),
    },
}
MIN_STRATUM_N = 15

def sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()

def num(x):
    try:
        v = float(x)
        return v if math.isfinite(v) else np.nan
    except Exception:
        return np.nan

def scale(x, lo, hi):
    x = num(x)
    if not math.isfinite(x) or x < lo or x > hi:
        return np.nan
    return max(0.0, min(1.0, (x - lo) / (hi - lo)))

def age_band(age):
    age = num(age)
    if not math.isfinite(age) or age < 18 or age > 110:
        return "MISSING"
    if age < 25: return "18_24"
    if age < 35: return "25_34"
    if age < 45: return "35_44"
    if age < 60: return "45_59"
    return "60_PLUS"

def donor_edu(x):
    x = num(x)
    if not math.isfinite(x) or x < 0 or x > 9: return "MISSING"
    if x <= 1: return "NONE"
    if x <= 3: return "PRIMARY"
    if x <= 5: return "SECONDARY"
    return "HIGHER"

def synthetic_edu(text):
    s = str(text).lower()
    if "sup" in s: return "HIGHER"
    if "second" in s or "coll" in s or "qualif" in s: return "SECONDARY"
    if "prim" in s: return "PRIMARY"
    if "aucun" in s or "préscol" in s or "prescol" in s: return "NONE"
    return "MISSING"

def donor_emp(x):
    x = num(x)
    if not math.isfinite(x) or x < 0 or x > 3: return "MISSING"
    if x == 0: return "INACTIVE"
    if x == 1: return "UNEMPLOYED"
    return "EMPLOYED"

def synthetic_emp(text):
    s = str(text)
    if s == "ACTIVE_EMPLOYED": return "EMPLOYED"
    if s == "UNEMPLOYED": return "UNEMPLOYED"
    if s == "INACTIVE": return "INACTIVE"
    return "MISSING"

def donor_frame(path, year):
    df, _ = pyreadstat.read_sav(path, usecols=COLS[year], apply_value_formats=False)
    emp = "Q95" if year == 2016 else "Q95A"
    out = pd.DataFrame({
        "urban_rural": df["URBRUR"].map(lambda x: "URBAN" if num(x) == 1 else ("RURAL" if num(x) == 2 else "MISSING")),
        "sex": df["Q101"].map(lambda x: "M" if num(x) == 1 else ("F" if num(x) == 2 else "MISSING")),
        "age_band": df["Q1"].map(age_band),
        "education_band": df["Q97"].map(donor_edu),
        "employment_band": df[emp].map(donor_emp),
    })
    for name, (col, lo, hi) in MAP[year].items():
        out[name] = df[col].map(lambda x: scale(x, lo, hi))
    return out

def summarize_groups(df, year):
    features = list(MAP[year])
    levels = [
        ("U_S_A_E_W", ["urban_rural","sex","age_band","education_band","employment_band"]),
        ("U_S_A_E", ["urban_rural","sex","age_band","education_band"]),
        ("U_S_A", ["urban_rural","sex","age_band"]),
        ("U_S", ["urban_rural","sex"]),
        ("U", ["urban_rural"]),
        ("ALL", []),
    ]
    tables = []
    for level_name, keys in levels:
        groups = {}
        iterator = [((), df)] if not keys else df.groupby(keys, dropna=False, sort=True)
        for key, g in iterator:
            if not isinstance(key, tuple):
                key = (key,)
            vals = {}
            for f in features:
                x = pd.to_numeric(g[f], errors="coerce").dropna().to_numpy(float)
                vals[f] = {
                    "mean": float(np.mean(x)) if len(x) else None,
                    "sd": float(np.std(x, ddof=1)) if len(x) > 1 else 0.0 if len(x) == 1 else None,
                    "valid_n": int(len(x)),
                }
            groups[tuple(map(str, key))] = {"n": int(len(g)), "values": vals}
        tables.append((level_name, keys, groups))
    return tables

def find_summary(record, tables):
    key_values = {
        "urban_rural": str(record.get("urban_rural", "MISSING")),
        "sex": str(record.get("sex", "MISSING")),
        "age_band": str(record.get("age_band", "MISSING")),
        "education_band": synthetic_edu(record.get("education_level")),
        "employment_band": synthetic_emp(record.get("activity_status")),
    }
    for level_name, keys, groups in tables:
        key = tuple(key_values[k] for k in keys)
        g = groups.get(key)
        if g and g["n"] >= MIN_STRATUM_N:
            return level_name, g
    raise RuntimeError("global attitude stratum unexpectedly unavailable")

def write_overlay(pop_path, donor_path, year, out_path):
    pop = json.loads(Path(pop_path).read_text(encoding="utf-8"))
    donors = donor_frame(donor_path, year)
    tables = summarize_groups(donors, year)
    counts = defaultdict(int)
    rows = 0
    with open(out_path, "w", encoding="utf-8") as f:
        for territory in pop["territories"]:
            for a in territory["archetypes"]:
                level, g = find_summary(a, tables)
                row = {
                    "year": year,
                    "constituency_id": territory["constituency_id"],
                    "archetype_id": a["archetype_id"],
                    "attitude_posterior_match_level": level,
                    "attitude_posterior_stratum_n": g["n"],
                    "attitude_source": f"AFROBAROMETER_MOROCCO_R{6 if year == 2016 else 8}",
                }
                for name, stats in g["values"].items():
                    row[f"latent_attitude_{name}_mean"] = stats["mean"]
                    row[f"latent_attitude_{name}_sd"] = stats["sd"]
                f.write(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",",":")) + "\n")
                counts[level] += 1
                rows += 1
    return {
        "year": year, "rows": rows, "territories": len(pop["territories"]),
        "donor_rows": len(donors), "match_levels": dict(sorted(counts.items())),
        "min_stratum_n": MIN_STRATUM_N,
    }

def main():
    ap = argparse.ArgumentParser()
    for name in ["pop2016","pop2021","af6","af8","outdir"]:
        ap.add_argument("--" + name, required=True)
    args = ap.parse_args()
    if sha256(args.af6) != EXPECTED[2016]: raise RuntimeError("Afrobarometer R6 SHA mismatch")
    if sha256(args.af8) != EXPECTED[2021]: raise RuntimeError("Afrobarometer R8 SHA mismatch")
    out = Path(args.outdir); out.mkdir(parents=True, exist_ok=True)
    audits = {
        2016: write_overlay(args.pop2016, args.af6, 2016, out/"2016_attitude_overlay_v1.jsonl"),
        2021: write_overlay(args.pop2021, args.af8, 2021, out/"2021_attitude_overlay_v1.jsonl"),
    }
    cert = {
        "schema_version": "1.0",
        "certificate_id": "M26-ASV2-RICH-ATTITUDE-OVERLAY-CERTIFICATE-V1",
        "experiment_id": "M26-AGENT-SOCIETY-V2-001",
        "status": "ASV2_RICH_ATTITUDE_OVERLAY_PASS",
        "target_outcomes_used": False,
        "real_llm_outputs_used": False,
        "person_level_attitudes_asserted_as_observed": False,
        "method": "Pre-election Afrobarometer conditional posterior means and standard deviations, matched hierarchically on broad demographic strata. No real respondent is copied into a synthetic voter.",
        "direct_party_vote_intention_used": False,
        "party_closeness_used": False,
        "sensitive_identity_variables_used": False,
        "attitude_dimensions": len(MAP[2016]),
        "posterior_fields_per_archetype": len(MAP[2016]) * 2,
        "not_counted_toward_R2_x10_gate": True,
        "audits": audits,
        "source_sha256": {"2016": EXPECTED[2016], "2021": EXPECTED[2021]},
    }
    Path(out/"rich_attitude_overlay_certificate_v1.json").write_text(json.dumps(cert,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    with zipfile.ZipFile(out/"asv2-rich-attitude-overlay-v1.zip","w",zipfile.ZIP_DEFLATED) as z:
        for fn in ["2016_attitude_overlay_v1.jsonl","2021_attitude_overlay_v1.jsonl","rich_attitude_overlay_certificate_v1.json"]:
            z.write(out/fn,fn)
    print(json.dumps(cert, indent=2))

if __name__ == "__main__":
    main()
