#!/usr/bin/env python3
"""Offline cross-source audit of a pre-election 2016 candidate seed vs TAFRA 2011."""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
M26 = ROOT / "morocco26"
G100 = M26 / "data" / "goal100"
SEED = G100 / "e_collect" / "candidate_intelligence_v2" / "2016" / "cross_source_seed_v1.jsonl"
HISTORY = G100 / "historical" / "b2_historical_elected_members.json"
OUT = G100 / "e_collect" / "candidate_intelligence_v2" / "2016" / "cross_source_seed_audit_v1.json"
DETAIL = G100 / "e_collect" / "candidate_intelligence_v2" / "2016" / "cross_source_seed_verified_v1.jsonl"
PARTIES = {"RNI", "PAM", "PI", "PJD", "USFP", "MP", "PPS", "UC", "MDS", "FGD", "AL_AHD"}


def norm(value: Any) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'")
    s = re.sub(r"\b(mohamed|mohammed)\b", "mohamed", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def tokens(s: str) -> set[str]:
    return {x for x in norm(s).split() if len(x) > 1}


def feature_leads(profile: str) -> list[str]:
    p = profile.lower()
    out = []
    if re.search(r"déput|deput|parlement sortant", p):
        out.append("PARLIAMENTARY_MANDATE_MENTION")
    if re.search(r"maire|conseil communal|conseil régional|conseil regional|conseil provincial|élu régional|elu regional|président|president", p):
        out.append("LOCAL_OR_REGIONAL_OFFICE_MENTION")
    if re.search(r"secrétaire général|secretaire general|responsable du pôle|responsable du pole|conseil national|ténor|tenor", p):
        out.append("PARTY_OR_NATIONAL_OFFICE_MENTION")
    if re.search(r"ministre", p):
        out.append("MINISTER_OR_FORMER_MINISTER_MENTION")
    if re.search(r"démissionné du|demissionne du|secrétaire général du parti al ahd|secretaire general du parti al ahd|de l.?uc", p):
        out.append("PARTY_SWITCH_OR_OTHER_PARTY_MENTION")
    return sorted(set(out))


def best_fuzzy(name: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = norm(name)
    nt = tokens(name)
    ranked = []
    for row in rows:
        rn = norm(row.get("canonical_name_source"))
        rt = tokens(rn)
        seq = SequenceMatcher(None, n, rn).ratio()
        jac = len(nt & rt) / len(nt | rt) if (nt | rt) else 0.0
        score = 0.7 * seq + 0.3 * jac
        ranked.append((score, seq, jac, row))
    ranked.sort(key=lambda x: x[0], reverse=True)
    if not ranked:
        return {"status": "NO_CANDIDATES"}
    best = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    return {
        "status": "FUZZY_DIAGNOSTIC_ONLY",
        "score": round(best[0], 6),
        "sequence": round(best[1], 6),
        "jaccard": round(best[2], 6),
        "gap": round(best[0] - (second[0] if second else 0), 6),
        "suggested_name": best[3].get("canonical_name_source"),
        "suggested_party": best[3].get("party_code"),
        "suggested_territory": best[3].get("territory_id"),
    }


def variant_class(seed: dict[str, Any], f: dict[str, Any]) -> str | None:
    seq = float(f.get("sequence") or 0)
    score = float(f.get("score") or 0)
    gap = float(f.get("gap") or 0)
    context = f.get("suggested_party") == seed.get("party") or f.get("suggested_territory") == seed.get("territory_id")
    if seq >= 0.97 and score >= 0.75 and context:
        return "VERY_HIGH_NAME_VARIANT_DIAGNOSTIC"
    if seq >= 0.93 and score >= 0.72 and gap >= 0.03 and context:
        return "HIGH_NAME_VARIANT_DIAGNOSTIC"
    return None


def main() -> int:
    seeds = [json.loads(x) for x in SEED.read_text(encoding="utf-8").splitlines() if x.strip()]
    hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    prior = [r for r in hist["years"]["2011"]["rows"] if r.get("scope") == "local"]
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in prior:
        by_name[norm(r.get("canonical_name_source"))].append(r)

    details = []
    derived = Counter()
    match_modes = Counter()
    variant_counts = Counter()
    party_verified = Counter()
    objective_leads = Counter()

    for seed in seeds:
        leads = feature_leads(seed.get("profile", ""))
        for f in leads:
            objective_leads[f] += 1
        matches = by_name.get(norm(seed["candidate"]), [])
        row = None
        mode = "NO_EXACT_MATCH"
        if len(matches) == 1:
            row = matches[0]
            mode = "EXACT_UNIQUE"
        elif len(matches) > 1:
            same_t = [r for r in matches if r.get("territory_id") == seed.get("territory_id")]
            if len(same_t) == 1:
                row = same_t[0]
                mode = "EXACT_TERRITORY_DISAMBIGUATED"
            else:
                mode = "EXACT_AMBIGUOUS"
        match_modes[mode] += 1
        item = {**seed, "m24_objective_feature_leads": leads, "cross_source_match_mode": mode}
        if row is not None:
            pp = row.get("party_code")
            pt = row.get("territory_id")
            same_p = pp == seed.get("party")
            same_t = pt == seed.get("territory_id")
            item["cross_source_status"] = "CROSS_SOURCE_VERIFIED"
            item["tafra_prior"] = {
                "person_id": row.get("person_id"),
                "canonical_name_source": row.get("canonical_name_source"),
                "party_code": pp,
                "territory_id": pt,
                "seat_id": row.get("seat_id"),
            }
            item["derived_features"] = {
                "INCUMBENT_SAME_PARTY_SAME_DISTRICT": bool(same_p and same_t),
                "INCUMBENT_SAME_PARTY_MOVED_DISTRICT": bool(same_p and not same_t),
                "INCUMBENT_PARTY_SWITCH_IN": bool((not same_p) and pp is not None),
                "PRIOR_CYCLE_MP": True,
            }
            for k, v in item["derived_features"].items():
                if v:
                    derived[k] += 1
            party_verified[seed["party"]] += 1
        else:
            item["cross_source_status"] = "UNRESOLVED"
            f = best_fuzzy(seed["candidate"], prior)
            item["fuzzy_diagnostic"] = f
            item["name_variant_diagnostic"] = variant_class(seed, f)
            if item["name_variant_diagnostic"]:
                variant_counts[item["name_variant_diagnostic"]] += 1
        details.append(item)

    DETAIL.parent.mkdir(parents=True, exist_ok=True)
    DETAIL.write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in details) + "\n", encoding="utf-8")
    verified = sum(x["cross_source_status"] == "CROSS_SOURCE_VERIFIED" for x in details)
    variants = sum(variant_counts.values())
    audit = {
        "schema_version": "1.0",
        "audit_id": "M26-CANDIDATE-INTEL-V2-2016-CROSS-SOURCE-SEED-V1",
        "status": "OFFLINE_CROSS_SOURCE_AUDIT_COMPLETE",
        "seed_rows": len(seeds),
        "seed_parties": dict(sorted(Counter(x["party"] for x in seeds).items())),
        "seed_territories": len({x["territory_id"] for x in seeds}),
        "cross_source_verified_rows": verified,
        "cross_source_verified_rate": verified / len(seeds) if seeds else 0,
        "cross_source_verified_parties": dict(sorted(party_verified.items())),
        "cross_source_derived_feature_counts": dict(sorted(derived.items())),
        "match_modes": dict(sorted(match_modes.items())),
        "m24_objective_feature_lead_counts": dict(sorted(objective_leads.items())),
        "name_variant_diagnostic": {
            "rows": variants,
            "by_class": dict(sorted(variant_counts.items())),
            "exact_plus_variant_rows": verified + variants,
            "exact_plus_variant_rate": (verified + variants) / len(seeds) if seeds else 0,
            "warning": "Variant rows remain unresolved and do not count as verified."
        },
        "verification_rule": "Only unique exact normalized matches against the frozen TAFRA 2011 local elected-member panel count as cross-source verified.",
        "scientific_interpretation": "This is a recoverability/identity audit for the 2011→2016 transition, not a predictive backtest and not authority to change F0.",
        "next_gate": "Use verified 2011→2016 and 2016→2021 candidate facts to build party×constituency features, then test coverage/support and predictive value before fitting any effect."
    }
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
