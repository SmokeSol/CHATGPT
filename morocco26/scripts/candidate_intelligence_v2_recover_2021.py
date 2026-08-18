#!/usr/bin/env python3
"""Recover a denser pre-election 2021 candidate-intelligence panel.

Scientific role
---------------
This is an evidence-recovery/power-audit tool only. It MUST NOT change F0,
E_reason V1 outputs, coefficients, or forecast probabilities.

Inputs:
- pre-election Medias24 candidate-profile pages (published before 2021-09-08)
- frozen TAFRA historical elected-member artifact already in the repository
- canonical 92-constituency geometry

Outputs:
- raw archived Medias24 pages + hashes
- candidate profile records with text-derived feature leads
- independently cross-checked prior-cycle incumbency / party / territory facts
- a recoverability/power-audit summary

Text-derived political attributes are labelled M24_SUPPORTED until an allowed
second source/T0 corroborates them. Prior-cycle incumbency facts can be promoted
to CROSS_SOURCE_VERIFIED only when the Medias24 candidate identity safely
matches the frozen TAFRA prior-cycle elected-member artifact.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]
M26 = REPO_ROOT / "morocco26"
G100 = M26 / "data" / "goal100"
OUT = G100 / "e_collect" / "candidate_intelligence_v2" / "2021"
RAW = OUT / "raw"
RUN_ID = os.environ.get("CANDIDATE_INTEL_RUN_ID") or datetime.now(timezone.utc).strftime("ci2021_%Y%m%dT%H%M%SZ")

SOURCES = {
    "PJD": "https://medias24.com/2021/08/14/voici-les-profils-des-candidats-du-pjd-pour-les-prochaines-legislatives/",
    "RNI": "https://medias24.com/2021/07/25/entrepreneurs-promoteurs-recrues-voici-les-candidats-du-rni-pour-les-prochaines-legislatives/",
    "PAM": "https://medias24.com/2021/08/25/elections-2021-voici-les-candidats-du-pam-pour-les-legislatives/",
    "PI": "https://medias24.com/2021/08/23/elections-2021-voici-les-profils-des-candidats-de-listiqlal-pour-les-legislatives/",
}
ELECTION_DATE = "2021-09-08"

# Conservative aliases. The canonical geometry remains authoritative.
ALIASES = {
    "anfa": "casablanca-anfa",
    "casablanca anfa": "casablanca-anfa",
    "ain chok": "ain-chock",
    "ain chock": "ain-chock",
    "ain sbaa hay mohammadi": "ain-sebaa-hay-mohammadi",
    "ain sebaa hay mohammadi": "ain-sebaa-hay-mohammadi",
    "ben msik": "ben-m-sick",
    "ben msik sidi othmane": "ben-m-sick",
    "sidi moumen sidi bernoussi": "sidi-bernoussi",
    "bernoussi": "sidi-bernoussi",
    "el fida": "al-fida-mers-sultan",
    "el fida mers sultan": "al-fida-mers-sultan",
    "fahs anjra": "fahs-anjra",
    "mdiq fnideq": "mdiq-fnideq",
    "m diq fnideq": "mdiq-fnideq",
    "ouazzane": "ouezzane",
    "fes nord": "fes-nord",
    "fes sud": "fes-sud",
    "karia ghafsai": "karia-ghafsay",
    "sefrou": "sefrou",
    "moulay yaacoub": "moulay-yaacoub",
    "marrakech medina": "marrakech-medina",
    "marrakech menara": "marrakech-menara",
    "marrakech guiliz": "marrakech-gueliz",
    "guiliz": "marrakech-gueliz",
    "kelaa sraghna": "el-kelaa-des-sraghna",
    "kelaat seraghna": "el-kelaa-des-sraghna",
    "el haouz": "al-haouz",
    "tiflet romani": "tiflet-rommani",
    "tifelt romani": "tiflet-rommani",
    "khemisset oulmes": "khemisset-oulmes",
    "sale medina": "sale-medina",
    "sala al jadida": "sale-el-jadida",
    "sale al jadida": "sale-el-jadida",
    "skhirat temara": "skhirat-temara",
    "ghar b": "el-gharb",
    "el gharb": "el-gharb",
    "agadir ida outanane": "agadir-ida-outanane",
    "inzegane ait melloul": "inezgane-ait-melloul",
    "chtouka ait baha": "chtouka-ait-baha",
    "taroudant nord": "taroudant-nord",
    "taroudant sud": "taroudant-sud",
    "oujda angad": "oujda-angad",
    "beni mellal": "beni-mellal",
    "fqih ben salah": "fquih-ben-salah",
    "fquih ben salah": "fquih-ben-salah",
    "azilal demnat": "azilal-demnate",
    "demnat": "azilal-demnate",
    "azilal bzou ouaouizeght": "bzou-ouaouizeght",
    "bzou ouaouizeght": "bzou-ouaouizeght",
    "oued eddahab": "oued-eddahab",
    "oued ed dahab": "oued-eddahab",
    "dakhla": "oued-eddahab",
    "laayoune": "laayoune",
    "tant tan": "tan-tan",
    "assa zag": "assa-zag",
}

FEATURE_PATTERNS = {
    "LOCAL_EXECUTIVE_OFFICE": [
        r"\bmaire\b", r"président(?:e)? du conseil (?:de la )?commune", r"président(?:e)? de la commune",
        r"vice-président(?:e)? du conseil communal", r"vice-président(?:e)? de la commune",
        r"président(?:e)? de l[’']arrondissement", r"vice-président(?:e)? du conseil de l[’']arrondissement",
    ],
    "LOCAL_OR_PROVINCIAL_OFFICE": [
        r"conseil communal", r"conseiller communal", r"conseillère communale", r"conseil provincial", r"conseil préfectoral",
    ],
    "REGIONAL_OFFICE": [
        r"conseil régional", r"conseil de la région", r"président(?:e)? de la région", r"président(?:e)? du conseil régional",
        r"vice-président(?:e)? du conseil régional",
    ],
    "PARTY_OFFICE": [
        r"secrétariat (?:général|régional|provincial|local)", r"secrétaire (?:général|régional|provincial)",
        r"coordinateur(?:rice)? (?:régional|provincial)", r"bureau (?:national|régional|provincial|local) du parti",
        r"commission exécutive du parti", r"conseil national du parti",
    ],
    "FORMER_MINISTER_OR_NATIONAL_OFFICE": [r"\bministre\b", r"ex-ministre", r"président du groupe parlementaire", r"vice-président de la chambre des représentants"],
    "FORMER_MP_MENTION": [r"ex-déput", r"ancien député", r"député .*\(20\d\d-20\d\d\)"],
}

SWITCH_HINT = re.compile(r"(?:sortant|élu|élue|député|députée|conseiller|président).*?\((PAM|RNI|PI|PJD|USFP|MP|PPS|UC)\)|ex-député\s+(PAM|RNI|PI|PJD|USFP|MP|PPS|UC)|sous les couleurs du\s+(PAM|RNI|PI|PJD|USFP|MP|PPS|UC)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def norm(value: Any) -> str:
    s = "" if value is None else str(value)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace("’", "'")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return re.sub(r"\s+", " ", s)


def load_geometry() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    path = M26 / "data" / "constituencies_goal75.csv"
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    by_id = {r["constituency_id"]: r for r in rows}
    by_name = {norm(r["name"]): r["constituency_id"] for r in rows}
    for k, v in ALIASES.items():
        if v in by_id:
            by_name[norm(k)] = v
    return by_id, by_name


def load_prior_members() -> list[dict[str, Any]]:
    payload = json.loads((G100 / "historical" / "b2_historical_elected_members.json").read_text(encoding="utf-8"))
    # 2016 election members are the prior-cycle incumbency observable for 2021.
    return payload["years"]["2016"]["rows"]


def member_index(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    idx: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        idx[norm(r.get("canonical_name_source"))].append(r)
    return idx


def fetch(url: str, session: requests.Session) -> tuple[bytes, dict[str, Any]]:
    r = session.get(url, timeout=(15, 60), headers={"User-Agent": "M26-CandidateIntelV2/1.0"})
    r.raise_for_status()
    b = r.content
    return b, {"url": url, "retrieved_at": now_iso(), "status_code": r.status_code, "sha256": sha256_bytes(b), "bytes": len(b)}


def extract_candidate_lines(html: bytes) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    # Remove obvious non-article noise while preserving list-like paragraphs.
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()
    lines: list[str] = []
    seen: set[str] = set()
    for el in soup.find_all(["li", "p"]):
        txt = " ".join(el.stripped_strings)
        txt = re.sub(r"\s+", " ", txt).strip(" -\u2022\t")
        if not txt or len(txt) < 8 or ":" not in txt:
            continue
        n = norm(txt)
        if n in seen:
            continue
        seen.add(n)
        lines.append(txt)
    return lines


def resolve_territory(label: str, by_name: dict[str, str]) -> str | None:
    n = norm(label)
    if n in by_name:
        return by_name[n]
    # Strip region/list qualifiers and try again.
    n = re.sub(r"^(circonscription|liste locale)\s+", "", n)
    if n in by_name:
        return by_name[n]
    # conservative containment only when unique
    hits = {cid for key, cid in by_name.items() if len(key) >= 5 and (key in n or n in key)}
    return next(iter(hits)) if len(hits) == 1 else None


def parse_line(line: str, current_party: str, by_name: dict[str, str]) -> dict[str, Any] | None:
    left, right = line.split(":", 1)
    if norm(left).startswith("liste regionale") or norm(left) in {"casablanca settat", "rabat sale kenitra", "fes meknes", "marrakech safi", "souss massa", "oriental", "draa tafilalet", "dakhla oued ed dahab", "laayoune sakia el hamra", "guelmim oued noun", "beni mellal khenifra", "tanger tetouan al hoceima"}:
        return None
    territory_id = resolve_territory(left, by_name)
    if not territory_id:
        return None
    profile = right.strip()
    # Candidate name is the leading phrase before the first descriptive comma.
    name = profile.split(",", 1)[0].strip()
    if len(name.split()) < 2 or len(name) > 120:
        return None
    features: dict[str, bool] = {}
    for fid, patterns in FEATURE_PATTERNS.items():
        features[fid] = any(re.search(p, profile, re.I) for p in patterns)
    prior_party_hints = [g for m in SWITCH_HINT.finditer(profile) for g in m.groups() if g]
    prior_party_hint = prior_party_hints[0].upper() if prior_party_hints else None
    if prior_party_hint == current_party:
        prior_party_hint = None
    return {
        "year": 2021,
        "election_date": ELECTION_DATE,
        "current_party": current_party,
        "territory_label_source": left.strip(),
        "territory_id": territory_id,
        "candidate_name_source": name,
        "candidate_name_norm": norm(name),
        "profile_text": profile,
        "m24_feature_leads": features,
        "prior_party_hint": prior_party_hint,
    }


def safe_match_prior(candidate: dict[str, Any], idx: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    key = candidate["candidate_name_norm"]
    matches = idx.get(key, [])
    if len(matches) != 1:
        # Conservative token fallback: exact token set after removing honorific noise.
        ctoks = set(key.split())
        scored = []
        for k, rows in idx.items():
            ktoks = set(k.split())
            if len(ctoks) >= 2 and ctoks == ktoks:
                scored.extend(rows)
        matches = scored
    if len(matches) != 1:
        return {"status": "UNRESOLVED", "match_count": len(matches)}
    r = matches[0]
    same_party = r.get("party_code") == candidate["current_party"]
    same_territory = r.get("territory_id") == candidate["territory_id"]
    return {
        "status": "CROSS_SOURCE_VERIFIED",
        "prior_person_id": r.get("person_id"),
        "prior_party": r.get("party_code"),
        "prior_territory_id": r.get("territory_id"),
        "prior_scope": r.get("scope"),
        "prior_source_name": r.get("canonical_name_source"),
        "incumbent_same_party_same_district": bool(same_party and same_territory),
        "incumbent_same_party_moved_district": bool(same_party and not same_territory),
        "incumbent_party_switch_in": bool((not same_party) and r.get("party_code") and candidate["current_party"]),
    }


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    RAW.mkdir(parents=True, exist_ok=True)
    by_id, by_name = load_geometry()
    prior_rows = load_prior_members()
    pidx = member_index(prior_rows)
    session = requests.Session()

    records: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    parsing_rejects: list[dict[str, Any]] = []

    for party, url in SOURCES.items():
        body, meta = fetch(url, session)
        raw_path = RAW / f"{party.lower()}_{meta['sha256']}.html"
        raw_path.write_bytes(body)
        meta["archived_path"] = str(raw_path.relative_to(REPO_ROOT))
        meta["party"] = party
        sources.append(meta)
        for line in extract_candidate_lines(body):
            rec = parse_line(line, party, by_name)
            if not rec:
                parsing_rejects.append({"party": party, "line": line})
                continue
            rec["source_url"] = url
            rec["source_sha256"] = meta["sha256"]
            rec["source_status"] = "M24_SUPPORTED_PRE_ELECTION"
            rec["prior_cycle_crosscheck"] = safe_match_prior(rec, pidx)
            records.append(rec)

    # Deterministic dedupe by (party, territory, normalized candidate name).
    dedup: dict[tuple[str, str, str], dict[str, Any]] = {}
    for r in records:
        dedup[(r["current_party"], r["territory_id"], r["candidate_name_norm"])] = r
    records = list(dedup.values())

    feature_counts = Counter()
    cross_counts = Counter()
    territory_set = set()
    party_counts = Counter()
    nonzero_candidates = 0
    for r in records:
        territory_set.add(r["territory_id"])
        party_counts[r["current_party"]] += 1
        any_feature = False
        for fid, val in r["m24_feature_leads"].items():
            if val:
                feature_counts[fid] += 1
                any_feature = True
        cc = r["prior_cycle_crosscheck"]
        cross_counts[cc["status"]] += 1
        for fid in ["incumbent_same_party_same_district", "incumbent_same_party_moved_district", "incumbent_party_switch_in"]:
            if cc.get(fid):
                cross_counts[fid] += 1
                any_feature = True
        if r.get("prior_party_hint"):
            feature_counts["PARTY_SWITCH_TEXT_HINT"] += 1
            any_feature = True
        if any_feature:
            nonzero_candidates += 1

    candidate_panel_path = OUT / "candidate_panel_first_pass.jsonl"
    candidate_panel_path.write_text("\n".join(json.dumps(r, ensure_ascii=False, sort_keys=True) for r in sorted(records, key=lambda x: (x["territory_id"], x["current_party"], x["candidate_name_norm"]))) + "\n", encoding="utf-8")
    (OUT / "parsing_rejects.json").write_text(json.dumps(parsing_rejects, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    audit = {
        "schema_version": "1.0",
        "audit_id": "M26-CANDIDATE-INTEL-V2-2021-FIRST-PASS",
        "run_id": RUN_ID,
        "generated_at": now_iso(),
        "status": "RECOVERY_FIRST_PASS_COMPLETE",
        "sources": sources,
        "panel": {
            "candidate_records": len(records),
            "local_territories_covered": len(territory_set),
            "party_counts": dict(sorted(party_counts.items())),
            "candidate_records_with_any_recovered_feature": nonzero_candidates,
            "candidate_feature_density": nonzero_candidates / len(records) if records else 0.0,
        },
        "m24_feature_lead_counts": dict(sorted(feature_counts.items())),
        "prior_cycle_crosscheck_counts": dict(sorted(cross_counts.items())),
        "comparison_to_e_reason_v1": {
            "e_reason_2021_party_cells": 828,
            "e_reason_2021_nonzero_directional_cells": 59,
            "e_reason_2021_directional_density": 59 / 828,
            "note": "Candidate-level density is not directly comparable to party-cell density, but materially higher recoverability indicates the old bundle gate discarded candidate information that was publicly available pre-election."
        },
        "epistemic_status": {
            "m24_text_features": "M24_SUPPORTED_NOT_YET_FINAL_VERIFIED",
            "prior_cycle_incumbency_crosschecks": "CROSS_SOURCE_VERIFIED_WHEN_UNIQUE_NAME_MATCH",
            "forecast_effect": "NONE",
            "f0_modified": false,
            "e_reason_v1_modified": false,
        },
        "next_gate": "Independent corroboration/adjudication plus support/missingness audit before any coefficient fitting or E_reason V2."
    }
    (OUT / "power_audit_first_pass.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
