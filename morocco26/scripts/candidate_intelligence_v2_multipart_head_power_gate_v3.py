#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("mpv1", HERE / "candidate_intelligence_v2_multipart_head_power_gate.py")
mp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mp)

mp.OUT = mp.CI / "candidate_intelligence_v2_multipart_head_power_gate_v3.json"
mp.DETAIL16 = mp.CI / "multipart" / "2016_head_prior_mp_features_v3.jsonl"
mp.DETAIL21 = mp.CI / "multipart" / "2021_head_prior_mp_features_v3.jsonl"
DEDUP = mp.CI / "multipart" / "2021_head_roster_dedup_v3.json"

def _quality(row):
    exact = 1 if row.get("territory_resolution") == "EXACT_NORMALIZED" else 0
    score = float(row.get("territory_match_score") or 0.0)
    not_old = 0 if " old" in str(row.get("district_source") or "").casefold() else 1
    return (exact, score, not_old)

def load_candidates21_deduped():
    rows = json.loads(mp.HEAD21.read_text(encoding="utf-8"))
    chosen = {}
    unresolved = []
    duplicate_drops = []
    for r in rows:
        if r.get("party_bucket") not in {"PJD", "RNI"}:
            continue
        if int(r.get("CANDIDATE_REGISTERED_RANK") or 0) != 1:
            continue
        if r.get("rank_evidence_status") != "EXPLICIT_CANDIDATS_TETES_DE_LISTE":
            continue
        if not r.get("territory_id"):
            unresolved.append({"party": r.get("party_bucket"), "candidate_name": r.get("candidate_name_source"), "district_source": r.get("district_source"), "reason": "UNRESOLVED_TERRITORY_NOT_A_PARTY_X_TERRITORY_CELL"})
            continue
        key = (r["party_bucket"], r["territory_id"])
        normalized = r.get("candidate_name_normalized") or mp.nlat(r.get("candidate_name_source"))
        if key not in chosen:
            chosen[key] = r
            continue
        prev = chosen[key]
        prev_norm = prev.get("candidate_name_normalized") or mp.nlat(prev.get("candidate_name_source"))
        if normalized != prev_norm:
            raise RuntimeError(f"conflicting certified heads for {key}: {prev.get('candidate_name_source')} vs {r.get('candidate_name_source')}")
        keep, drop = (r, prev) if _quality(r) > _quality(prev) else (prev, r)
        chosen[key] = keep
        duplicate_drops.append({"party": key[0], "territory_id": key[1], "candidate_name": keep.get("candidate_name_source"), "kept_district_source": keep.get("district_source"), "kept_territory_resolution": keep.get("territory_resolution"), "kept_territory_match_score": keep.get("territory_match_score"), "dropped_district_source": drop.get("district_source"), "dropped_territory_resolution": drop.get("territory_resolution"), "dropped_territory_match_score": drop.get("territory_match_score"), "rule": "SAME_CANDIDATE_DUPLICATE_KEEP_BEST_TERRITORY_RESOLUTION"})
    out = []
    for key in sorted(chosen):
        r = chosen[key]
        out.append({"transition": "2016_TO_2021", "year": 2021, "party": r["party_bucket"], "territory_id": r["territory_id"], "candidate_name_lat": r["candidate_name_source"], "candidate_name_ar": None, "source_class": "CERTIFIED_EXPLICIT_HEAD_ROSTER_DEDUPED", "prior_link_corroborated": bool(r.get("prior_elected_person_id")), "existing_same_party_same_district": bool(r.get("INCUMBENT_SAME_PARTY_SAME_DISTRICT")), "existing_switch_in": bool(r.get("PARTY_SWITCH_IN")), "incumbent_match_score": r.get("incumbent_match_score")})
    DEDUP.parent.mkdir(parents=True, exist_ok=True)
    DEDUP.write_text(json.dumps({"schema_version": "1.0", "rule": "Within a party×territory cell, duplicate rows are collapsed only when candidate identity is identical; exact territory resolution dominates fuzzy/legacy duplicates. Conflicting candidate identities fail closed.", "unresolved_territory_rows_excluded": unresolved, "same_candidate_duplicate_rows_dropped": duplicate_drops, "final_rows": len(out), "party_counts": {p: sum(x["party"] == p for x in out) for p in ("PJD", "RNI")}}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return out

mp.load_candidates21 = load_candidates21_deduped

def main():
    mp.main()
    result = json.loads(mp.OUT.read_text(encoding="utf-8"))
    result["schema_version"] = "1.3"
    result["result_id"] = "M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-HEAD-POWER-GATE-V3"
    result["dedupe_artifact"] = str(DEDUP.relative_to(mp.ROOT))
    result["dedupe_policy"] = "Same candidate duplicated by legacy/fuzzy and exact map labels is counted once, preferring exact territory resolution; conflicting identities fail closed."
    mp.OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": result["status"], "eligible_features": result["eligible_features"], "known_2016": result["2011_TO_2016"]["fully_known_all_features"], "known_2021": result["2016_TO_2021"]["fully_known_all_features"], "party_2016": result["2011_TO_2016"]["parties"], "party_2021": result["2016_TO_2021"]["parties"], "positive_2016": {k: v["positive"] for k, v in result["2011_TO_2016"]["features"].items()}, "positive_2021": {k: v["positive"] for k, v in result["2016_TO_2021"]["features"].items()}}, ensure_ascii=False, sort_keys=True))

if __name__ == "__main__":
    main()
