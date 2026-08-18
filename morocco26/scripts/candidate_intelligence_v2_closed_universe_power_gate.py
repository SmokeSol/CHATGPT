#!/usr/bin/env python3
"""Candidate Intelligence V2 closed-universe power gate.

Offline only. Uses:
- official PJD 2016 Arabic closed roster (74 local heads)
- Medias24 2021 Latin closed roster (91 local heads)
- already archived multi-year Chamber-members parquet files in this repository

No forecast is modified. This script measures whether a NEW V2 candidate-head
feature, HEAD_PRIOR_CYCLE_MP, has enough CLOSED-UNIVERSE TRUE/FALSE coverage and
positive support to justify a later preregistered model specification.

Important: HEAD_PRIOR_CYCLE_MP is not silently substituted for frozen B2_P01,
which counted all registered candidates. It is a narrower V2 candidate-head
feature and receives no coefficient here.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
M26 = ROOT / "morocco26"
G100 = M26 / "data" / "goal100"
CI = G100 / "e_collect" / "candidate_intelligence_v2"
R16 = CI / "2016" / "pjd_closed_roster_v1.json"
R21 = CI / "2021" / "pjd_closed_roster_v1.json"
RAW = G100 / "b2_raw_acquisition" / "HF_CHAMBER_MEMBERS_MULTIYEAR" / "data"
OUT = CI / "candidate_intelligence_v2_closed_universe_power_gate_v1.json"
DETAIL16 = CI / "2016" / "pjd_closed_universe_incumbency_v1.jsonl"
DETAIL21 = CI / "2021" / "pjd_closed_universe_incumbency_v1.jsonl"

MIN_COVERAGE = 0.80
MIN_POSITIVE = 30
FUZZY_UNKNOWN_GUARD = 0.86

AR_DIACRITICS = re.compile(r"[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]")


def norm_ar(value: Any) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("ـ", "")
    s = AR_DIACRITICS.sub("", s)
    s = re.sub(r"[إأآٱ]", "ا", s)
    s = s.replace("ى", "ي")
    s = s.replace("ؤ", "و").replace("ئ", "ي")
    s = s.replace("هللا", "الله")
    s = re.sub(r"\bامل", "الم", s)
    s = re.sub(r"\bاإل", "ال", s)
    s = re.sub(r"\s+ي\b", "ي", s)
    s = re.sub(r"[^\u0621-\u063a\u0641-\u064a0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def norm_lat(value: Any) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'")
    s = re.sub(r"\bmohamm?ed\b|\bmohamad\b", "mohamed", s)
    s = re.sub(r"\babdellah\b|\babdallah\b|\babdullah\b", "abdallah", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def load_raw() -> pd.DataFrame:
    files = sorted(RAW.glob("*.parquet"))
    if not files:
        raise RuntimeError(f"no archived Chamber parquet files under {RAW}")
    frames = [pd.read_parquet(p) for p in files]
    return pd.concat(frames, ignore_index=True)


def first_col(df: pd.DataFrame, *names: str) -> str:
    by_lower = {str(c).lower(): str(c) for c in df.columns}
    for n in names:
        if n.lower() in by_lower:
            return by_lower[n.lower()]
    raise KeyError(f"none of {names!r} found; columns={list(df.columns)!r}")


def elected_universe(df: pd.DataFrame, parliament: str) -> tuple[pd.DataFrame, dict[str, str]]:
    cols = {
        "parliament": first_col(df, "parlement"),
        "entry_reason": first_col(df, "motifentree", "motif_entree"),
        "name_lat": first_col(df, "prenomnom", "prenom_nom"),
        "name_ar": first_col(df, "prenomnomar", "prenom_nom_ar"),
        "territory": first_col(df, "circonscription"),
    }
    party_col = None
    for cand in ("parti", "partipolitique", "appartenancepolitique", "formationpolitique"):
        try:
            party_col = first_col(df, cand)
            break
        except KeyError:
            pass
    if party_col:
        cols["party"] = party_col

    p = df[df[cols["parliament"]].astype(str).str.strip().eq(parliament)].copy()
    p = p[p[cols["entry_reason"]].astype(str).str.casefold().str.strip().eq("elu")].copy()
    if len(p) != 395:
        raise RuntimeError(f"closed elected universe {parliament} must contain 395 rows, got {len(p)}")
    return p, cols


def best_similarity(name: str, universe: pd.DataFrame, name_col: str, normalizer) -> tuple[float, str | None]:
    n = normalizer(name)
    best_score = -1.0
    best_raw = None
    for raw in universe[name_col].fillna("").astype(str):
        r = normalizer(raw)
        if not r:
            continue
        score = SequenceMatcher(None, n, r).ratio()
        if score > best_score:
            best_score, best_raw = score, raw
    return best_score, best_raw


def classify_roster(rows: list[dict[str, Any]], universe: pd.DataFrame, cols: dict[str, str], *, arabic: bool) -> list[dict[str, Any]]:
    name_col = cols["name_ar"] if arabic else cols["name_lat"]
    source_name_key = "candidate_name_ar" if arabic else "candidate_name_fr"
    norm = norm_ar if arabic else norm_lat
    idx: dict[str, list[int]] = defaultdict(list)
    for ix, raw in universe[name_col].fillna("").astype(str).items():
        n = norm(raw)
        if n:
            idx[n].append(ix)

    out = []
    for row in rows:
        raw_name = row[source_name_key]
        n = norm(raw_name)
        hits = idx.get(n, [])
        item = {**row, "feature_id": "V2_HEAD_PRIOR_CYCLE_MP", "candidate_name_normalized": n, "closed_universe_size": 395}
        if len(hits) == 1:
            m = universe.loc[hits[0]]
            item.update({
                "feature_state": "VERIFIED_TRUE",
                "identity_method": "EXACT_NORMALIZED_SAME_SCRIPT_CLOSED_UNIVERSE",
                "prior_member_name_lat": None if pd.isna(m[cols["name_lat"]]) else str(m[cols["name_lat"]]),
                "prior_member_name_ar": None if pd.isna(m[cols["name_ar"]]) else str(m[cols["name_ar"]]),
                "prior_member_territory_source": None if pd.isna(m[cols["territory"]]) else str(m[cols["territory"]]),
                "prior_member_party_source": (None if "party" not in cols or pd.isna(m[cols["party"]]) else str(m[cols["party"]])),
            })
        elif len(hits) > 1:
            item.update({"feature_state": "UNKNOWN", "identity_method": "EXACT_NORMALIZED_COLLISION", "collision_count": len(hits)})
        else:
            score, best = best_similarity(raw_name, universe, name_col, norm)
            item["nearest_prior_name"] = best
            item["nearest_name_similarity"] = round(score, 6)
            if score >= FUZZY_UNKNOWN_GUARD:
                item.update({"feature_state": "UNKNOWN", "identity_method": "NO_EXACT_MATCH_HIGH_SIMILARITY_GUARD"})
            else:
                item.update({"feature_state": "VERIFIED_FALSE", "identity_method": "NO_MATCH_IN_COMPLETE_395_MEMBER_UNIVERSE_WITH_LOW_SIMILARITY_GUARD"})
        out.append(item)
    return out


def summary(rows: list[dict[str, Any]], roster_total: int) -> dict[str, Any]:
    states = Counter(r["feature_state"] for r in rows)
    known = states["VERIFIED_TRUE"] + states["VERIFIED_FALSE"]
    return {
        "roster_rows": roster_total,
        "states": dict(sorted(states.items())),
        "known_true_false": known,
        "known_coverage": known / roster_total if roster_total else 0.0,
        "positive_instances": states["VERIFIED_TRUE"],
        "coverage_gate": known / roster_total >= MIN_COVERAGE if roster_total else False,
        "support_gate": states["VERIFIED_TRUE"] >= MIN_POSITIVE,
    }


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in rows) + "\n", encoding="utf-8")


def main() -> int:
    roster16 = json.loads(R16.read_text(encoding="utf-8"))
    roster21 = json.loads(R21.read_text(encoding="utf-8"))
    df = load_raw()
    u11, c11 = elected_universe(df, "2011-2016")
    u16, c16 = elected_universe(df, "2016-2021")
    rows16 = classify_roster(roster16["rows"], u11, c11, arabic=True)
    rows21 = classify_roster(roster21["rows"], u16, c16, arabic=False)
    write_jsonl(DETAIL16, rows16)
    write_jsonl(DETAIL21, rows21)
    s16 = summary(rows16, len(roster16["rows"]))
    s21 = summary(rows21, len(roster21["rows"]))
    model_gate = s16["coverage_gate"] and s21["coverage_gate"] and s16["support_gate"] and s21["support_gate"]
    result = {
        "schema_version": "1.0",
        "gate_id": "M26-CANDIDATE-INTELLIGENCE-V2-CLOSED-UNIVERSE-POWER-GATE-V1",
        "status": "PASS_HEAD_INCUMBENCY_DATA_POWER" if model_gate else "FAIL_HEAD_INCUMBENCY_DATA_POWER",
        "feature": {
            "feature_id": "V2_HEAD_PRIOR_CYCLE_MP",
            "entity": "PARTY_X_LOCAL_CONTEST_HEAD",
            "definition": "Whether the focal party's pre-election local head of list is present in the complete elected-member universe of the immediately prior House legislature.",
            "relationship_to_B2": "NEW_NARROWER_V2_FEATURE; it does not replace or rewrite B2_P01, which counted all registered candidates.",
            "coefficient_authorized": False,
        },
        "thresholds": {
            "minimum_known_coverage_each_transition": MIN_COVERAGE,
            "minimum_positive_instances_each_transition": MIN_POSITIVE,
            "fuzzy_unknown_guard": FUZZY_UNKNOWN_GUARD,
            "unknown_is_false": False,
        },
        "2011_TO_2016": s16,
        "2016_TO_2021": s21,
        "data_integrity": {
            "prior_universe_2011_2016_rows": len(u11),
            "prior_universe_2016_2021_rows": len(u16),
            "parquet_files": [p.name for p in sorted(RAW.glob("*.parquet"))],
            "network_used": False,
            "forecast_modified": False,
        },
        "reasoner_gate": {
            "status": "NOT_EVALUATED_BY_THIS_SINGLE_FEATURE_GATE",
            "rule": "A data-power PASS on one binary feature does not establish C1-vs-C2 reasoner identifiability; at least one additional independently varying feature family must be recovered and the prospective contrast surface audited before any LLM run."
        },
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
