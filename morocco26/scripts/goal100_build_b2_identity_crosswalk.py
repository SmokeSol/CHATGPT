#!/usr/bin/env python3
"""Build and certify the deterministic B2 identity/territory crosswalk.

This gate certifies keys and mappings, not the 2026 ballot. Legacy candidate
coverage is retained as lead-only metadata and contributes zero admitted B2
records. No fuzzy matching, transliteration model or LLM resolution is used.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G75 = ROOT / "data" / "goal75"
G100 = ROOT / "data" / "goal100"
DATA = ROOT / "data"
TZ = ZoneInfo("Africa/Casablanca")

PROTOCOL_PATH = G100 / "b2_identity_protocol_v1.json"
LOCAL_CLOSURE_PATH = G75 / "local_92_closure_v3.json"
GEOMETRY_CERTIFICATE_PATH = G100 / "geometry_2026_certificate.json"
REGIONAL_CSV_PATH = G100 / "geometry_authoritative_regional_rows_fr.csv"
HISTORICAL_PATHS = {
    2011: G100 / "historical" / "tafra_legislative_2011_canonical.json",
    2016: G100 / "historical" / "tafra_legislative_2016_canonical.json",
    2021: G100 / "historical" / "tafra_legislative_2021_canonical.json",
}
ELECTED_PATH = G75 / "observed_elected_2021.json"
LEGACY_CANDIDATE_PATH = DATA / "candidate_coverage_2026.json"
SOURCE_REGISTRY_PATH = G100 / "b2_source_registry.json"
GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"
EVIDENCE_DIR = G100 / "b2_evidence"
CROSSWALK_PATH = G100 / "b2_identity_crosswalk.json"
CERTIFICATE_PATH = G100 / "b2_identity_territory_certificate.json"
EVENT_DIR = G100 / "fil_ariane_events"
JOURNAL = ROOT / "FIL_ARIANE.md"

CORE_PARTIES = {
    "RNI": {
        "full_name_fr": "Rassemblement National des Indépendants",
        "full_name_ar": "التجمع الوطني للأحرار",
    },
    "PAM": {
        "full_name_fr": "Parti Authenticité et Modernité",
        "full_name_ar": "حزب الأصالة والمعاصرة",
    },
    "PI": {
        "full_name_fr": "Parti de l'Istiqlal",
        "full_name_ar": "حزب الاستقلال",
    },
    "PJD": {
        "full_name_fr": "Parti de la Justice et du Développement",
        "full_name_ar": "حزب العدالة والتنمية",
    },
    "USFP": {
        "full_name_fr": "Union Socialiste des Forces Populaires",
        "full_name_ar": "الاتحاد الاشتراكي للقوات الشعبية",
    },
    "MP": {
        "full_name_fr": "Mouvement Populaire",
        "full_name_ar": "الحركة الشعبية",
    },
    "UC": {
        "full_name_fr": "Union Constitutionnelle",
        "full_name_ar": "الاتحاد الدستوري",
    },
    "PPS": {
        "full_name_fr": "Parti du Progrès et du Socialisme",
        "full_name_ar": "حزب التقدم والاشتراكية",
    },
}

ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ؤ": "و", "ئ": "ي",
    "ـ": "",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
    "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4",
    "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9",
})
APOSTROPHES = "'’ʼ`´ʻʹ"
DASHES = "‐‑‒–—―−"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_IDENTITY_FAIL: {message}")


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).translate(ARABIC_TRANSLATION)
    for char in APOSTROPHES:
        text = text.replace(char, " ")
    for char in DASHES:
        text = text.replace(char, " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    cleaned = []
    for char in text.casefold():
        category = unicodedata.category(char)
        cleaned.append(char if char.isalnum() or category.startswith("L") else " ")
    return " ".join("".join(cleaned).split())


def slug(value: object) -> str:
    normalized = normalize_text(value)
    ascii_text = unicodedata.normalize("NFKD", normalized).encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    require(bool(ascii_text), f"cannot slugify {value!r}")
    return ascii_text


def party_code(value: object) -> str:
    code = re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")
    require(bool(code), f"empty party code from {value!r}")
    return code


def count_claim_records() -> int:
    if not EVIDENCE_DIR.exists():
        return 0
    return sum(1 for path in EVIDENCE_DIR.rglob("*.json") if path.is_file())


def add_alias(alias_map: dict[str, str], alias_sets: dict[str, set[str]], raw: object, target_id: str, failures: list[dict], kind: str) -> None:
    normalized = normalize_text(raw)
    if not normalized:
        return
    previous = alias_map.get(normalized)
    if previous is not None and previous != target_id:
        failures.append({
            "kind": f"{kind}_ALIAS_COLLISION",
            "alias": str(raw),
            "normalized_alias": normalized,
            "target_a": previous,
            "target_b": target_id,
        })
        return
    alias_map[normalized] = target_id
    alias_sets[target_id].add(str(raw))


def resolve_alias(alias_map: dict[str, str], raw: object, failures: list[dict], kind: str, context: str) -> str | None:
    normalized = normalize_text(raw)
    target = alias_map.get(normalized)
    if target is None:
        failures.append({
            "kind": f"UNRESOLVED_{kind}",
            "raw": str(raw),
            "normalized": normalized,
            "context": context,
        })
    return target


def read_regional_csv() -> list[dict]:
    with REGIONAL_CSV_PATH.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def discover_historical_rows() -> dict[int, list[dict]]:
    result = {}
    for year, path in HISTORICAL_PATHS.items():
        data = load(path)
        require(int(data["year"]) == year, f"historical year mismatch in {path.name}")
        result[year] = data["rows"]
    return result


def build_crosswalk() -> tuple[dict, dict]:
    protocol = load(PROTOCOL_PATH)
    closure = load(LOCAL_CLOSURE_PATH)
    geometry = load(GEOMETRY_CERTIFICATE_PATH)
    historical = discover_historical_rows()
    elected = load(ELECTED_PATH)
    legacy = load(LEGACY_CANDIDATE_PATH)
    sources = load(SOURCE_REGISTRY_PATH)

    require(protocol["status"] == "FROZEN_PRE_EXECUTION", "identity protocol is not frozen pre-execution")
    require(sources["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED", "B2 source universe is not frozen/enabled")
    require(sources["collection_allowed"] is True, "B2 source universe collection flag is false")
    claim_count = count_claim_records()

    failures: list[dict] = []
    local_alias_map: dict[str, str] = {}
    local_alias_sets: dict[str, set[str]] = defaultdict(set)
    region_alias_map: dict[str, str] = {}
    region_alias_sets: dict[str, set[str]] = defaultdict(set)

    # Authoritative regional identities first.
    regions: dict[str, dict] = {}
    for row in read_regional_csv():
        name = row["official_name_fr"]
        region_id = f"reg-{slug(name)}"
        require(region_id not in regions, f"duplicate regional ID {region_id}")
        regions[region_id] = {
            "region_id": region_id,
            "canonical_name": name,
            "seats": int(row["seats"]),
            "aliases": [],
            "identity_basis": "AUTHORITATIVE_REGIONAL_ROW",
        }
        add_alias(region_alias_map, region_alias_sets, name, region_id, failures, "REGION")
    reviewed_regions = protocol["reviewed_aliases"]["regional"]
    for raw, region_id in reviewed_regions.items():
        if region_id not in regions:
            failures.append({"kind": "REVIEWED_REGION_ALIAS_UNKNOWN_TARGET", "alias": raw, "target": region_id})
        else:
            add_alias(region_alias_map, region_alias_sets, raw, region_id, failures, "REGION")

    # Certified local identities and their already-paired TAFRA names.
    locals_by_id: dict[str, dict] = {}
    for row in closure["rows"]:
        constituency_id = row["constituency_id"]
        require(constituency_id not in locals_by_id, f"duplicate local ID {constituency_id}")
        region_id = resolve_alias(region_alias_map, row["region"], failures, "REGION", f"closure:{constituency_id}")
        if region_id:
            add_alias(region_alias_map, region_alias_sets, row["region"], region_id, failures, "REGION")
        locals_by_id[constituency_id] = {
            "constituency_id": constituency_id,
            "canonical_name": row["name"],
            "region_id": region_id,
            "seats": int(row["seats"]),
            "tafra_name": row["tafra_name"],
            "aliases": [],
            "identity_basis": "CERTIFIED_LOCAL_92_CLOSURE",
        }
        add_alias(local_alias_map, local_alias_sets, row["name"], constituency_id, failures, "LOCAL")
        add_alias(local_alias_map, local_alias_sets, row["tafra_name"], constituency_id, failures, "LOCAL")

    # Historical parties and list identities.
    party_contexts: dict[str, set[str]] = defaultdict(set)
    party_years: dict[str, set[int]] = defaultdict(set)
    list_registry: dict[str, dict] = {}
    historical_summary: dict[str, dict] = {}
    local_row_mappings = 0
    regional_row_mappings = 0
    ignored_row_types = Counter()

    for year, rows in sorted(historical.items()):
        year_local = 0
        year_regional = 0
        year_lists = 0
        for row_index, row in enumerate(rows):
            list_type = normalize_text(row.get("list_type"))
            votes = row.get("votes") or {}
            positive_codes = []
            for raw_code, raw_votes in votes.items():
                if int(raw_votes or 0) <= 0:
                    continue
                code = party_code(raw_code)
                positive_codes.append(code)
                party_contexts[code].add(f"HISTORICAL_{year}")
                party_years[code].add(year)

            if list_type == "locale":
                territory_id = resolve_alias(
                    local_alias_map,
                    row.get("constituency"),
                    failures,
                    "LOCAL",
                    f"historical:{year}:{row_index}",
                )
                if territory_id:
                    add_alias(local_alias_map, local_alias_sets, row.get("constituency"), territory_id, failures, "LOCAL")
                scope = "local"
                year_local += 1
                local_row_mappings += int(territory_id is not None)
            elif list_type == "regionale":
                region_raw = row.get("region") or row.get("constituency")
                territory_id = resolve_alias(
                    region_alias_map,
                    region_raw,
                    failures,
                    "REGION",
                    f"historical:{year}:{row_index}",
                )
                if territory_id:
                    add_alias(region_alias_map, region_alias_sets, region_raw, territory_id, failures, "REGION")
                scope = "regional"
                year_regional += 1
                regional_row_mappings += int(territory_id is not None)
            else:
                ignored_row_types[list_type or "missing"] += 1
                continue

            if territory_id is None:
                continue
            for code in sorted(set(positive_codes)):
                list_id = f"list:{year}:{scope}:{territory_id}:{code}"
                if list_id in list_registry:
                    failures.append({
                        "kind": "DUPLICATE_LIST_ID",
                        "list_id": list_id,
                        "year": year,
                        "scope": scope,
                        "territory_id": territory_id,
                        "party_code": code,
                    })
                    continue
                list_registry[list_id] = {
                    "list_id": list_id,
                    "year": year,
                    "scope": scope,
                    "territory_id": territory_id,
                    "party_code": code,
                    "presence_semantics": "POSITIVE_VOTE_LIST_OBSERVED_IN_CANONICAL_RESULT",
                    "source_row_id": row.get("id_constituency") or row.get("id_region"),
                }
                year_lists += 1
        historical_summary[str(year)] = {
            "rows_total": len(rows),
            "local_rows": year_local,
            "regional_rows": year_regional,
            "positive_vote_lists": year_lists,
        }

    # 2021 elected members: stable TAFRA person and seat IDs.
    member_rows = elected["rows"]
    people: list[dict] = []
    person_id_names: dict[int, set[str]] = defaultdict(set)
    normalized_name_person_ids: dict[str, set[int]] = defaultdict(set)
    seat_ids: set[int] = set()
    local_members = 0
    regional_members = 0
    for index, row in enumerate(member_rows):
        idperson = int(row["idperson"])
        idsiege = int(row["idsiege"])
        raw_name = str(row["name"]).strip()
        normalized_name = normalize_text(raw_name)
        code = party_code(row["party"])
        party_contexts[code].add("ELECTED_2021")
        party_years[code].add(2021)
        person_id_names[idperson].add(normalized_name)
        normalized_name_person_ids[normalized_name].add(idperson)
        if idsiege in seat_ids:
            failures.append({"kind": "DUPLICATE_SEAT_ID", "idsiege": idsiege, "row_index": index})
        seat_ids.add(idsiege)

        circonscription = row.get("circonscription") or ""
        if normalize_text(circonscription).startswith(normalize_text("Circonscription régionale")):
            scope = "regional"
            territory_id = resolve_alias(region_alias_map, row.get("region"), failures, "REGION", f"elected:{idsiege}")
            if territory_id:
                add_alias(region_alias_map, region_alias_sets, row.get("region"), territory_id, failures, "REGION")
            regional_members += 1
        else:
            scope = "local"
            territory_id = resolve_alias(local_alias_map, circonscription, failures, "LOCAL", f"elected:{idsiege}")
            if territory_id:
                add_alias(local_alias_map, local_alias_sets, circonscription, territory_id, failures, "LOCAL")
            local_members += 1

        people.append({
            "person_id": f"tafra-person:{idperson}",
            "tafra_idperson": idperson,
            "seat_id": f"tafra-seat:{idsiege}",
            "tafra_idsiege": idsiege,
            "canonical_name_source": raw_name,
            "normalized_name": normalized_name,
            "party_code_2021": code,
            "scope": scope,
            "territory_id": territory_id,
            "region_source": row.get("region"),
            "constituency_source": circonscription,
            "entry_date": row.get("dateentree"),
            "entry_reason": row.get("motifentree"),
            "identity_basis": "TAFRA_STABLE_PERSON_ID",
        })

    for idperson, names in sorted(person_id_names.items()):
        if len(names) > 1:
            failures.append({
                "kind": "CONFLICTING_NAMES_FOR_STABLE_PERSON_ID",
                "idperson": idperson,
                "normalized_names": sorted(names),
            })

    name_collision_groups = [
        {
            "normalized_name": name,
            "person_ids": [f"tafra-person:{value}" for value in sorted(person_ids)],
            "resolution": "RETAIN_SEPARATE_STABLE_IDS_NO_NAME_MERGE",
        }
        for name, person_ids in sorted(normalized_name_person_ids.items())
        if len(person_ids) > 1
    ]

    # Legacy 2026 summary creates only lead codes and no candidate identity.
    for row in legacy.get("parties", []):
        code = party_code(row["party"])
        party_contexts[code].add("LEGACY_2026_AGGREGATE_LEAD_ONLY")

    # Final party registry and alias collision audit.
    party_alias_map: dict[str, str] = {}
    party_alias_sets: dict[str, set[str]] = defaultdict(set)
    party_registry = []
    for code in sorted(party_contexts):
        core = CORE_PARTIES.get(code)
        aliases = [code]
        if core:
            aliases.extend([core["full_name_fr"], core["full_name_ar"]])
        for alias in aliases:
            normalized = normalize_text(alias)
            previous = party_alias_map.get(normalized)
            if previous is not None and previous != code:
                failures.append({
                    "kind": "PARTY_ALIAS_COLLISION",
                    "alias": alias,
                    "normalized_alias": normalized,
                    "party_a": previous,
                    "party_b": code,
                })
            else:
                party_alias_map[normalized] = code
                party_alias_sets[code].add(alias)
        party_registry.append({
            "party_code": code,
            "full_name_fr": core["full_name_fr"] if core else None,
            "full_name_ar": core["full_name_ar"] if core else None,
            "reporting_bucket": code if code in CORE_PARTIES else "OTHER",
            "identity_status": "CORE_OFFICIAL_NAME_FROZEN" if core else "OBSERVED_CODE_FULL_LABEL_UNRESOLVED",
            "aliases": sorted(party_alias_sets[code]),
            "observed_contexts": sorted(party_contexts[code]),
            "observed_years": sorted(party_years[code]),
        })

    # Attach aliases and deterministic region IDs to output rows.
    local_rows = []
    for constituency_id in sorted(locals_by_id):
        row = dict(locals_by_id[constituency_id])
        row["aliases"] = sorted(local_alias_sets[constituency_id])
        row["normalized_aliases"] = sorted({normalize_text(value) for value in row["aliases"]})
        local_rows.append(row)
    regional_rows = []
    for region_id in sorted(regions):
        row = dict(regions[region_id])
        row["aliases"] = sorted(region_alias_sets[region_id])
        row["normalized_aliases"] = sorted({normalize_text(value) for value in row["aliases"]})
        regional_rows.append(row)

    # Gate expectations and explicit failures.
    if len(local_rows) != 92:
        failures.append({"kind": "LOCAL_ID_COUNT", "actual": len(local_rows), "expected": 92})
    if sum(row["seats"] for row in local_rows) != 305:
        failures.append({"kind": "LOCAL_SEAT_SUM", "actual": sum(row["seats"] for row in local_rows), "expected": 305})
    if len(regional_rows) != 12:
        failures.append({"kind": "REGIONAL_ID_COUNT", "actual": len(regional_rows), "expected": 12})
    if sum(row["seats"] for row in regional_rows) != 90:
        failures.append({"kind": "REGIONAL_SEAT_SUM", "actual": sum(row["seats"] for row in regional_rows), "expected": 90})
    expected_local_historical = 92 * len(HISTORICAL_PATHS)
    actual_local_historical = sum(value["local_rows"] for value in historical_summary.values())
    if actual_local_historical != expected_local_historical or local_row_mappings != expected_local_historical:
        failures.append({
            "kind": "HISTORICAL_LOCAL_MAPPING_COVERAGE",
            "rows": actual_local_historical,
            "mapped": local_row_mappings,
            "expected": expected_local_historical,
        })
    expected_regional_historical = sum(value["regional_rows"] for value in historical_summary.values())
    if regional_row_mappings != expected_regional_historical:
        failures.append({
            "kind": "HISTORICAL_REGIONAL_MAPPING_COVERAGE",
            "rows": expected_regional_historical,
            "mapped": regional_row_mappings,
        })
    if len(member_rows) != 395 or len(seat_ids) != 395:
        failures.append({"kind": "ELECTED_MEMBER_SEAT_COVERAGE", "rows": len(member_rows), "unique_seats": len(seat_ids), "expected": 395})
    if local_members != 305 or regional_members != 90:
        failures.append({"kind": "ELECTED_MEMBER_SCOPE_COUNTS", "local": local_members, "regional": regional_members, "expected_local": 305, "expected_regional": 90})
    if any(row["territory_id"] is None for row in people):
        failures.append({"kind": "ELECTED_MEMBER_UNRESOLVED_TERRITORY", "count": sum(row["territory_id"] is None for row in people)})
    if claim_count != 0:
        failures.append({"kind": "B2_CLAIMS_EXIST_BEFORE_IDENTITY_CERTIFICATE", "count": claim_count})
    if geometry["gate"] != "PASS" or int(geometry["house_seats"]) != 395:
        failures.append({"kind": "GEOMETRY_PARENT_NOT_CERTIFIED", "gate": geometry.get("gate"), "house_seats": geometry.get("house_seats")})

    generated_at = now_local()
    input_paths = {
        "protocol": PROTOCOL_PATH,
        "local_closure": LOCAL_CLOSURE_PATH,
        "geometry_certificate": GEOMETRY_CERTIFICATE_PATH,
        "regional_rows": REGIONAL_CSV_PATH,
        "historical_2011": HISTORICAL_PATHS[2011],
        "historical_2016": HISTORICAL_PATHS[2016],
        "historical_2021": HISTORICAL_PATHS[2021],
        "elected_2021": ELECTED_PATH,
        "legacy_candidate_coverage_2026": LEGACY_CANDIDATE_PATH,
        "source_registry": SOURCE_REGISTRY_PATH,
    }
    crosswalk = {
        "schema_version": "1.0",
        "crosswalk_id": "M26-GOAL100-B2-IDENTITY-CROSSWALK-V1",
        "protocol_id": protocol["protocol_id"],
        "generated_at": generated_at,
        "gate": "PASS" if not failures else "FAIL",
        "normalizer": protocol["normalization"],
        "territories": {
            "local": local_rows,
            "regional": regional_rows,
            "local_alias_count": len(local_alias_map),
            "regional_alias_count": len(region_alias_map),
            "unreviewed_fuzzy_matches": 0,
        },
        "parties": party_registry,
        "lists": [list_registry[key] for key in sorted(list_registry)],
        "people_2021": people,
        "identity_collisions": {
            "normalized_name_collision_groups": name_collision_groups,
            "policy": "Collision groups remain separate because stable TAFRA IDs are primary. Name-only resolution into these groups is UNRESOLVED_COLLISION.",
        },
        "historical_mapping": {
            "by_year": historical_summary,
            "local_rows_mapped": local_row_mappings,
            "regional_rows_mapped": regional_row_mappings,
            "ignored_row_types": dict(sorted(ignored_row_types.items())),
        },
        "legacy_2026_candidate_leads": {
            "source_path": str(LEGACY_CANDIDATE_PATH.relative_to(REPO)),
            "source_sha256": sha256(LEGACY_CANDIDATE_PATH),
            "as_of": legacy.get("as_of"),
            "reported_total_candidate_records": legacy.get("total_candidate_records"),
            "reported_active_local_records": legacy.get("active_local_records"),
            "party_coverage_summary": legacy.get("parties", []),
            "status": "LEAD_ONLY_REVALIDATION_REQUIRED",
            "admitted_B2_candidate_records": 0,
            "mechanical_effect": "NONE",
            "predictive_effect": 0.0,
            "reason": "Aggregate file has no B2 record-level source locator, publication timestamp, first-observed timestamp, content hash, claim hash, verification state or critical double-entry fields.",
        },
        "input_hashes": {
            name: {
                "path": str(path.relative_to(REPO)),
                "sha256": sha256(path),
            }
            for name, path in input_paths.items()
        },
        "failures": failures,
    }
    crosswalk_hash = canonical_sha256(crosswalk)
    crosswalk["canonical_crosswalk_sha256"] = crosswalk_hash

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-IDENTITY-TERRITORY-CERTIFICATE-V1",
        "protocol_id": protocol["protocol_id"],
        "certified_at": generated_at,
        "gate": "PASS" if not failures else "FAIL",
        "crosswalk_path": str(CROSSWALK_PATH.relative_to(REPO)),
        "crosswalk_sha256": crosswalk_hash,
        "local_territories": len(local_rows),
        "local_seats": sum(row["seats"] for row in local_rows),
        "regional_territories": len(regional_rows),
        "regional_seats": sum(row["seats"] for row in regional_rows),
        "historical_local_rows_mapped": local_row_mappings,
        "historical_regional_rows_mapped": regional_row_mappings,
        "party_codes": len(party_registry),
        "core_party_codes": len([row for row in party_registry if row["party_code"] in CORE_PARTIES]),
        "historical_list_ids": len(list_registry),
        "elected_member_rows": len(people),
        "elected_local_rows": local_members,
        "elected_regional_rows": regional_members,
        "unique_stable_person_ids": len(person_id_names),
        "unique_seat_ids": len(seat_ids),
        "normalized_name_collision_groups": len(name_collision_groups),
        "territory_alias_collisions": sum(failure["kind"] in {"LOCAL_ALIAS_COLLISION", "REGION_ALIAS_COLLISION"} for failure in failures),
        "party_alias_collisions": sum(failure["kind"] == "PARTY_ALIAS_COLLISION" for failure in failures),
        "unreviewed_fuzzy_matches": 0,
        "B2_claim_records_before_certificate": claim_count,
        "legacy_2026_candidate_records_reported": legacy.get("total_candidate_records"),
        "legacy_2026_candidate_records_admitted": 0,
        "failures": failures,
        "scientific_boundary": "PASS certifies deterministic identifiers and exact territorial mappings only. It does not certify any 2026 candidacy, ballot presence, party switch, endorsement or predictive effect.",
    }
    return crosswalk, certificate


def append_event_and_transition(certificate: dict) -> None:
    if certificate["gate"] != "PASS":
        run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
        event_id = f"A021F{run_id}"
        event = {
            "event_id": event_id,
            "date": certificate["certified_at"],
            "title": "Échec du certificat identité-territoire B2",
            "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
            "gate": "B2-2-IDENTITY-TERRITORY-CROSSWALK",
            "status": "FAIL",
            "machine_result": certificate,
            "scientific_decision": "B2-2 remains OPEN; no fuzzy fallback and no candidate/list fact is admitted.",
            "next_action_exact": "Resolve only the published failure classes through a versioned reviewed alias or corrected stable source input, then rerun without weakening the gate."
        }
        dump(EVENT_DIR / f"{event_id}.json", event)
        return

    gates = load(GATES_PATH)
    gate = next(row for row in gates["gates"] if row["id"] == "B2-2-IDENTITY-TERRITORY-CROSSWALK")
    gate["status"] = "CLOSED"
    gate["required_artifact"] = "morocco26/data/goal100/b2_identity_territory_certificate.json"
    gate["resolved_claim"] = "The certified 92 local and 12 regional territorial IDs, all observed historical party/list codes and all 395 elected-member rows resolve deterministically without fuzzy matching; legacy 2026 candidate aggregates admit zero B2 records."
    gates["as_of"] = certificate["certified_at"]
    gates["next_gate"] = "B2-3-HISTORICAL-FEATURE-PANEL"
    dump(GATES_PATH, gates)

    state = load(STATE_PATH)
    state["as_of"] = certificate["certified_at"]
    state["phase"] = "B2_IDENTITY_TERRITORY_CERTIFIED_HISTORICAL_PANEL_PENDING"
    state["identity_crosswalk"] = {
        "status": "CERTIFIED",
        "certificate": "morocco26/data/goal100/b2_identity_territory_certificate.json",
        "crosswalk": "morocco26/data/goal100/b2_identity_crosswalk.json",
        "crosswalk_sha256": certificate["crosswalk_sha256"],
        "local_territories": certificate["local_territories"],
        "regional_territories": certificate["regional_territories"],
        "party_codes": certificate["party_codes"],
        "historical_list_ids": certificate["historical_list_ids"],
        "elected_member_rows": certificate["elected_member_rows"],
        "normalized_name_collision_groups": certificate["normalized_name_collision_groups"],
        "unreviewed_fuzzy_matches": 0,
        "legacy_2026_candidate_records_admitted": 0,
    }
    closed = state["gates"]["closed"]
    if "B2-2-IDENTITY-TERRITORY-CROSSWALK" not in closed:
        closed.append("B2-2-IDENTITY-TERRITORY-CROSSWALK")
    state["gates"]["open"] = [value for value in state["gates"]["open"] if value != "B2-2-IDENTITY-TERRITORY-CROSSWALK"]
    state["next_action_exact"] = "Freeze and build the same-cutoff historical candidate/list feature panel for 2011->2016 and 2016->2021; no 2026 predictive coefficient may move before B2-3 and B2-6 pass."
    dump(STATE_PATH, state)

    event = {
        "event_id": "A021",
        "date": certificate["certified_at"],
        "title": "Certification du crosswalk identité-parti-liste-territoire B2",
        "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
        "gate": "B2-2-IDENTITY-TERRITORY-CROSSWALK",
        "status": "PASS",
        "question": "Les clés nécessaires à B2 peuvent-elles être certifiées sans fuzzy matching ni admission prématurée des candidatures 2026 ?",
        "pre_test_hypothesis": "PASS si les 92+12 territoires, toutes les listes historiques et les 395 élus 2021 sont résolus par IDs exacts/aliases revus, avec collisions de noms publiées mais jamais fusionnées.",
        "machine_result": certificate,
        "scientific_decision": "The identity infrastructure is certified. Legacy 2026 aggregates remain lead-only and have zero mechanical or predictive effect.",
        "next_action_exact": "Construct B2-3 historical feature coverage and support at historical information cutoffs before fitting any B2 coefficient."
    }
    dump(EVENT_DIR / "A021.json", event)

    marker = "Entrée A021 — Certification du crosswalk identité-parti-liste-territoire B2"
    text = JOURNAL.read_text(encoding="utf-8")
    if marker not in text:
        text += f"""

### {certificate['certified_at'][:10]} — {marker}

**Question/gate traité :** `B2-2-IDENTITY-TERRITORY-CROSSWALK` — certifier les clés avant tout record candidat 2026.

**Hypothèse avant test :** 92 territoires locaux / 305 sièges, 12 régions / 90 sièges, toutes les listes historiques et les 395 élus 2021 doivent être résolus sans fuzzy matching. Les collisions de noms doivent rester séparées par ID stable.

**Résultat machine :** `PASS` — locaux `{certificate['local_territories']}`, régions `{certificate['regional_territories']}`, codes partis/listes `{certificate['party_codes']}`, list IDs historiques `{certificate['historical_list_ids']}`, élus `{certificate['elected_member_rows']}` dont `{certificate['elected_local_rows']}` locaux et `{certificate['elected_regional_rows']}` régionaux ; groupes de collision de nom `{certificate['normalized_name_collision_groups']}` ; fuzzy matches `{certificate['unreviewed_fuzzy_matches']}`.

**Frontière scientifique :** les `{certificate['legacy_2026_candidate_records_reported']}` enregistrements annoncés par l’ancien résumé 2026 sont conservés comme leads agrégés mais admis dans B2 = `{certificate['legacy_2026_candidate_records_admitted']}`. Ils n’ont aucun effet mécanique ni prédictif.

**Décision scientifique :** crosswalk certifié ; aucune homonymie n’est fusionnée et aucun code non-core n’est transformé en parti connu par supposition.

**Prochaine action exacte :** construire `B2-3` — panel historique de features candidat/liste au même cutoff, avec couverture et support publiés, avant tout fit de coefficient.
"""
        JOURNAL.write_text(text, encoding="utf-8")


def main() -> None:
    crosswalk, certificate = build_crosswalk()
    dump(CROSSWALK_PATH, crosswalk)
    dump(CERTIFICATE_PATH, certificate)
    append_event_and_transition(certificate)
    print("B2_IDENTITY_TERRITORY_PASS" if certificate["gate"] == "PASS" else "B2_IDENTITY_TERRITORY_FAIL")
    print(json.dumps(certificate, ensure_ascii=False, indent=2))
    raise SystemExit(0 if certificate["gate"] == "PASS" else 3)


if __name__ == "__main__":
    main()
