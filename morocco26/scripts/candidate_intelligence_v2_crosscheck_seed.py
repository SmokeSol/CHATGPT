#!/usr/bin/env python3
"""Offline cross-source audit of the 2021 candidate-intelligence seed.

No web access is used. Medias24-derived candidate/profile rows already captured
in cross_source_seed_v1.jsonl are matched conservatively against the frozen
TAFRA 2016 elected-member artifact. Only unambiguous exact normalized name
matches count as CROSS_SOURCE_VERIFIED. Fuzzy suggestions are diagnostic only.
"""
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
SEED = G100 / "e_collect" / "candidate_intelligence_v2" / "2021" / "cross_source_seed_v1.jsonl"
HISTORY = G100 / "historical" / "b2_historical_elected_members.json"
OUT = G100 / "e_collect" / "candidate_intelligence_v2" / "2021" / "cross_source_seed_audit_v1.json"
DETAIL = G100 / "e_collect" / "candidate_intelligence_v2" / "2021" / "cross_source_seed_verified_v1.jsonl"

PARTIES = {"RNI", "PAM", "PI", "PJD", "USFP", "MP", "PPS", "UC", "MDS", "FGD"}


def norm(value: Any) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'")
    s = re.sub(r"\b(mohamed|mohammed)\b", "mohamed", s)
    s = re.sub(r"\b(abdel|abd el)\b", "abdel", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def tokens(s: str) -> set[str]:
    return {x for x in norm(s).split() if len(x) > 1}


def feature_leads(profile: str) -> list[str]:
    p = profile.lower()
    out = []
    if re.search(r"\bdéput|\bdeput|chambre des représentants|chambre des representants", p):
        out.append("PARLIAMENTARY_MANDATE_MENTION")
    if re.search(r"président|president|vice-président|vice president|conseil communal|conseil provincial|conseil régional|conseil regional|maire|arrondissement", p):
        out.append("LOCAL_OR_REGIONAL_OFFICE_MENTION")
    if re.search(r"secrétariat|secretariat|secrétaire|secretaire|coordinateur|bureau .*parti|commission exécutive|commission executive|groupe parlementaire", p):
        out.append("PARTY_OR_PARLIAMENTARY_OFFICE_MENTION")
    if re.search(r"\bministre\b|ex-ministre|président du gouvernement|president du gouvernement", p):
        out.append("FORMER_MINISTER_OR_NATIONAL_OFFICE_MENTION")
    for party in sorted(PARTIES):
        if party != "PI" and re.search(rf"\b{re.escape(party.lower())}\b", p):
            out.append("PRIOR_OR_OTHER_PARTY_MENTION")
            break
    return sorted(set(out))


def best_fuzzy(name: str, candidates: list[dict[str, Any]]) -> dict[str, Any]:
    n = norm(name)
    nt = tokens(name)
    ranked = []
    for row in candidates:
        rn = norm(row.get("canonical_name_source"))
        rt = tokens(rn)
        seq = SequenceMatcher(None, n, rn).ratio()
        jac = len(nt & rt) / len(nt | rt) if (nt | rt) else 0.0
        score = 0.7 * seq + 0.3 * jac
        ranked.append((score, seq, jac, row))
    ranked.sort(key=lambda x: x[0], reverse=True)
    best = ranked[0] if ranked else None
    second = ranked[1] if len(ranked) > 1 else None
    if not best:
        return {"status": "NO_CANDIDATES"}
    return {
        "status": "FUZZY_DIAGNOSTIC_ONLY",
        "score": round(best[0], 6),
        "sequence": round(best[1], 6),
        "jaccard": round(best[2], 6),
        "gap": round(best[0] - (second[0] if second else 0.0), 6),
        "suggested_name": best[3].get("canonical_name_source"),
        "suggested_party": best[3].get("party_code"),
        "suggested_territory": best[3].get("territory_id"),
    }


def resolve_exact(seed: dict[str, Any], by_name: dict[str, list[dict[str, Any]]]) -> tuple[str, dict[str, Any] | None]:
    matches = by_name.get(norm(seed["candidate"]), [])
    if len(matches) == 1:
        return "EXACT_UNIQUE", matches[0]
    if len(matches) > 1:
        same_t = [r for r in matches if r.get("territory_id") == seed.get("territory_id")]
        if len(same_t) == 1:
            return "EXACT_TERRITORY_DISAMBIGUATED", same_t[0]
        same_p = [r for r in matches if r.get("party_code") == seed.get("party")]
        if len(same_p) == 1:
            return "EXACT_PARTY_DISAMBIGUATED", same_p[0]
        return "EXACT_AMBIGUOUS", None
    return "NO_EXACT_MATCH", None


def variant_diagnostic(item: dict[str, Any]) -> str | None:
    """Classify close-name unresolved rows without promoting them to verified."""
    f = item.get("fuzzy_diagnostic") or {}
    seq = float(f.get("sequence") or 0.0)
    score = float(f.get("score") or 0.0)
    gap = float(f.get("gap") or 0.0)
    same_party = f.get("suggested_party") == item.get("party")
    same_territory = f.get("suggested_territory") == item.get("territory_id")
    context = same_party or same_territory
    if seq >= 0.97 and score >= 0.75 and context:
        return "VERY_HIGH_NAME_VARIANT_DIAGNOSTIC"
    if seq >= 0.93 and score >= 0.72 and gap >= 0.03 and context:
        return "HIGH_NAME_VARIANT_DIAGNOSTIC"
    return None


def main() -> int:
    seeds = [json.loads(x) for x in SEED.read_text(encoding="utf-8").splitlines() if x.strip()]
    hist = json.loads(HISTORY.read_text(encoding="utf-8"))
    prior = [r for r in hist["years"]["2016"]["rows"] if r.get("scope") == "local"]
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in prior:
        by_name[norm(row.get("canonical_name_source"))].append(row)

    details = []
    match_counts = Counter()
    feature_counts = Counter()
    derived = Counter()
    verified_parties = Counter()
    verified_territories = set()

    for seed in seeds:
        mode, row = resolve_exact(seed, by_name)
        match_counts[mode] += 1
        leads = feature_leads(seed.get("profile", ""))
        for f in leads:
            feature_counts[f] += 1
        item = {**seed, "m24_objective_feature_leads": leads, "cross_source_match_mode": mode}
        if row is not None:
            prior_party = row.get("party_code")
            prior_territory = row.get("territory_id")
            same_party = prior_party == seed.get("party")
            same_territory = prior_territory == seed.get("territory_id")
            item["cross_source_status"] = "CROSS_SOURCE_VERIFIED"
            item["tafra_prior"] = {
                "person_id": row.get("person_id"),
                "canonical_name_source": row.get("canonical_name_source"),
                "party_code": prior_party,
                "territory_id": prior_territory,
                "seat_id": row.get("seat_id"),
            }
            item["derived_features"] = {
                "INCUMBENT_SAME_PARTY_SAME_DISTRICT": bool(same_party and same_territory),
                "INCUMBENT_SAME_PARTY_MOVED_DISTRICT": bool(same_party and not same_territory),
                "INCUMBENT_PARTY_SWITCH_IN": bool((not same_party) and prior_party is not None),
                "PRIOR_CYCLE_MP": True,
            }
            for k, v in item["derived_features"].items():
                if v:
                    derived[k] += 1
            verified_parties[seed["party"]] += 1
            verified_territories.add(seed["territory_id"])
        else:
            item["cross_source_status"] = "UNRESOLVED"
            item["fuzzy_diagnostic"] = best_fuzzy(seed["candidate"], prior)
            item["name_variant_diagnostic"] = variant_diagnostic(item)
        details.append(item)

    DETAIL.parent.mkdir(parents=True, exist_ok=True)
    DETAIL.write_text("\n".join(json.dumps(x, ensure_ascii=False, sort_keys=True) for x in details) + "\n", encoding="utf-8")

    verified = sum(1 for x in details if x["cross_source_status"] == "CROSS_SOURCE_VERIFIED")
    objective = sum(1 for x in details if x["m24_objective_feature_leads"])
    variant_counts = Counter(x.get("name_variant_diagnostic") for x in details if x.get("name_variant_diagnostic"))
    variant_rows = sum(variant_counts.values())
    examples = [
        {
            "candidate": x["candidate"],
            "party": x["party"],
            "territory_id": x["territory_id"],
            "diagnostic": x.get("name_variant_diagnostic"),
            "suggested_name": x.get("fuzzy_diagnostic", {}).get("suggested_name"),
            "sequence": x.get("fuzzy_diagnostic", {}).get("sequence"),
            "suggested_party": x.get("fuzzy_diagnostic", {}).get("suggested_party"),
            "suggested_territory": x.get("fuzzy_diagnostic", {}).get("suggested_territory"),
        }
        for x in details if x.get("name_variant_diagnostic")
    ]
    audit = {
        "schema_version": "1.1",
        "audit_id": "M26-CANDIDATE-INTEL-V2-2021-CROSS-SOURCE-SEED-V1",
        "status": "OFFLINE_CROSS_SOURCE_AUDIT_COMPLETE",
        "seed_rows": len(seeds),
        "seed_parties": dict(Counter(x["party"] for x in seeds)),
        "seed_territories": len({x["territory_id"] for x in seeds}),
        "medias24_rows_with_objective_feature_lead": objective,
        "medias24_objective_feature_rate": objective / len(seeds) if seeds else 0.0,
        "cross_source_verified_rows": verified,
        "cross_source_verified_rate": verified / len(seeds) if seeds else 0.0,
        "cross_source_verified_parties": dict(sorted(verified_parties.items())),
        "cross_source_verified_territories": len(verified_territories),
        "match_modes": dict(sorted(match_counts.items())),
        "m24_feature_lead_counts": dict(sorted(feature_counts.items())),
        "cross_source_derived_feature_counts": dict(sorted(derived.items())),
        "unresolved_name_variant_diagnostic": {
            "rows": variant_rows,
            "by_class": dict(sorted(variant_counts.items())),
            "exact_plus_variant_diagnostic_rows": verified + variant_rows,
            "exact_plus_variant_diagnostic_rate": (verified + variant_rows) / len(seeds) if seeds else 0.0,
            "examples": examples,
            "warning": "These rows remain UNRESOLVED and are not counted as CROSS_SOURCE_VERIFIED. The diagnostic estimates how much of exact-match loss is plausibly orthographic/transliteration noise."
        },
        "verification_rule": "Only unique exact normalized TAFRA 2016 member-name matches (or exact matches safely disambiguated by territory/party) receive CROSS_SOURCE_VERIFIED. Fuzzy/name-variant diagnostics never count as verified.",
        "scientific_interpretation": "This sample measures recoverability and independent cross-source verifiability, not predictive effect. It cannot update F0 and does not validate a coefficient.",
        "comparison_anchor": {"e_reason_v1_2021_directional_nonzero_cells": 59, "e_reason_v1_2021_party_cells": 828},
        "next_gate": "Scale extraction across full pre-election 2021/2016 source surfaces, then aggregate candidate facts to party x constituency and run support/missingness/predictive backtest before E_reason V2."
    }
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
