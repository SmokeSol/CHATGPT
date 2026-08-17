#!/usr/bin/env python3
"""B2-4: parse the 2026 ballot roster deterministically and test double entry.

The roster table is read structurally: rowspan-collapsed cells are carried
forward positionally, and the constituency and agent name are taken from fixed
column offsets. No cell is interpreted.

Corroboration is searched only inside the already-frozen 2026 source universe,
by exact normalized-string containment. The frozen rule is unchanged: candidate
identity requires two matching parses or one authoritative T0 structured table,
and a T1 party page is not authoritative. A row that only one source supports
stays SINGLE_SOURCE_ONLY and creates no verified B2 evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"
RAW_MANIFEST_PATH = G100 / "b2_raw_acquisition_manifest.json"
WAVE1_CERT_PATH = G100 / "b2_current_wave1_acquisition_certificate.json"
CROSSWALK_PATH = G100 / "b2_identity_crosswalk.json"
REGISTRY_PATH = G100 / "b2_source_registry.json"
GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"

ROSTER_PATH = G100 / "b2_2026_ballot_roster.json"
CERTIFICATE_PATH = G100 / "b2_2026_ballot_certificate.json"

GATE_ID = "B2-4-2026-BALLOT-ROSTER"
PARSER_ID = "M26-GOAL100-B2-BALLOT-ROSTER-PARSER"
PARSER_VERSION = "1.0"

TABLE_RE = re.compile(r"<table.*?</table>", re.S | re.I)
ROW_RE = re.compile(r"<tr.*?</tr>", re.S | re.I)
CELL_RE = re.compile(r"<t[dh].*?</t[dh]>", re.S | re.I)
TAG_RE = re.compile(r"<[^>]+>")

ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ؤ": "و", "ئ": "ي", "ـ": "",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
APOSTROPHES = "'’ʼ`´ʻʹ"
DASHES = "‐‑‒–—―−"

# Frozen column semantics of the roster table, taken from its own header row.
HEADER_CONSTITUENCY = "الدائرة الانتخابية"
HEADER_AGENT = "اسم وكيل"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_4_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def normalize_text(value: object) -> str:
    """The frozen M26_TEXT_NORMALIZER_V1 behaviour."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(ARABIC_TRANSLATION)
    for char in APOSTROPHES:
        text = text.replace(char, " ")
    for char in DASHES:
        text = text.replace(char, " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    cleaned = []
    for char in text.casefold():
        cleaned.append(char if char.isalnum() or unicodedata.category(char).startswith("L") else " ")
    return " ".join("".join(cleaned).split())


def cell_text(cell: str) -> str:
    return " ".join(TAG_RE.sub("", cell).replace("&nbsp;", " ").split())


def certified_alias_map(crosswalk: dict) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for row in crosswalk["territories"]["local"]:
        for alias in row.get("normalized_aliases", []):
            aliases[alias] = row["constituency_id"]
        aliases[normalize_text(row["canonical_name"])] = row["constituency_id"]
    return aliases


def find_roster_document(wave1: dict) -> dict | None:
    tables = wave1["format_inventory"]["deterministically_parsable_tables"]
    if not tables:
        return None
    return max(tables, key=lambda row: row["table_rows"])


def parse_roster(stored_path: Path, table_index: int) -> tuple[list[dict], dict]:
    text = stored_path.read_bytes().decode("utf-8", "ignore")
    tables = TABLE_RE.findall(text)
    if table_index >= len(tables):
        raise SystemExit("B2_4_FAIL: recorded table index is absent from the stored document")
    rows = ROW_RE.findall(tables[table_index])

    header = [cell_text(cell) for cell in CELL_RE.findall(rows[0])]
    if not any(HEADER_CONSTITUENCY in value for value in header):
        raise SystemExit("B2_4_FAIL: roster header does not declare the constituency column")
    if not any(HEADER_AGENT in value for value in header):
        raise SystemExit("B2_4_FAIL: roster header does not declare the list-agent column")

    width = len(header)
    parsed, malformed = [], 0
    for index, raw_row in enumerate(rows[1:], start=1):
        cells = [cell_text(cell) for cell in CELL_RE.findall(raw_row)]
        if len(cells) < 2:
            malformed += 1
            continue
        # Rowspan collapses leading cells; the trailing columns stay aligned.
        constituency = cells[-2]
        agent = cells[-1]
        region = cells[0] if len(cells) == width else None
        parsed.append({
            "row_index": index,
            "region_raw": region,
            "constituency_raw": constituency,
            "constituency_normalized": normalize_text(constituency),
            "agent_name_raw": agent,
            "agent_name_normalized": normalize_text(agent),
            "cells_present": len(cells),
            "rowspan_collapsed": len(cells) < width,
        })
    return parsed, {"header": header, "declared_width": width, "malformed_rows": malformed,
                    "data_rows": len(rows) - 1}


def corroborate(rows: list[dict], raw: dict, registry: dict, exclude_source: str) -> dict:
    """Exact normalized-name containment across the frozen 2026 corpus."""
    clusters = {
        entry["source_id"]: entry.get("independence_cluster")
        for entry in registry["source_entries"]
    }
    documents = []
    for entry in raw.get("entries", []):
        if entry.get("state") != "ACQUIRED" or not entry.get("stored_path"):
            continue
        if entry["source_id"] == exclude_source:
            continue
        path = REPO / entry["stored_path"]
        if not path.exists():
            continue
        text = path.read_bytes()[:5_000_000].decode("utf-8", "ignore")
        documents.append({
            "source_id": entry["source_id"],
            "cluster": clusters.get(entry["source_id"], entry["source_id"]),
            "normalized": normalize_text(text),
        })

    for row in rows:
        needle = row["agent_name_normalized"]
        hits = sorted({
            document["cluster"] for document in documents
            if needle and len(needle) >= 8 and needle in document["normalized"]
        })
        row["corroborating_independence_clusters"] = hits
        row["independent_corroboration_count"] = len(hits)
    return {"documents_searched": len(documents),
            "clusters_searched": len({d["cluster"] for d in documents})}


def classify(row: dict, territory_id: str | None, blocked_sources: int) -> str:
    if row["independent_corroboration_count"] >= 1:
        return "VERIFIED_DOUBLE_ENTRY"
    if territory_id is None:
        return "AMBIGUOUS_DETERMINISTIC_MATCH"
    return "SINGLE_SOURCE_ONLY"


def main() -> None:
    wave1 = load(WAVE1_CERT_PATH)
    raw = load(RAW_MANIFEST_PATH)
    registry = load(REGISTRY_PATH)
    crosswalk = load(CROSSWALK_PATH)
    if crosswalk["gate"] != "PASS":
        raise SystemExit("B2_4_FAIL: identity crosswalk is not PASS")

    target = find_roster_document(wave1)
    if target is None:
        raise SystemExit("B2_4_FAIL: no deterministically parsable roster table in the frozen corpus")

    stored = REPO / target["stored_path"]
    rows, structure = parse_roster(stored, target["table_index"])
    aliases = certified_alias_map(crosswalk)

    for row in rows:
        row["territory_id"] = aliases.get(row["constituency_normalized"])
        row["territory_resolution"] = (
            "CERTIFIED_EXACT_ID" if row["territory_id"] else "UNRESOLVED_NO_CERTIFIED_ALIAS"
        )

    search = corroborate(rows, raw, registry, exclude_source=target["source_id"])
    blocked = sum(entry.get("state") == "BLOCKED_SOURCE" for entry in raw.get("entries", []))
    for row in rows:
        row["record_state"] = classify(row, row["territory_id"], blocked)

    states = Counter(row["record_state"] for row in rows)
    resolved = [row for row in rows if row["territory_id"]]
    source_entry = next(
        (e for e in registry["source_entries"] if e["source_id"] == target["source_id"]), {}
    )

    roster = {
        "schema_version": "1.0",
        "artifact_id": "M26-GOAL100-B2-2026-BALLOT-ROSTER-V1",
        "generated_at": now_local(),
        "gate_id": GATE_ID,
        "parser": {"parser_id": PARSER_ID, "version": PARSER_VERSION, "llm_used": False,
                   "method": "HTML_TABLE_PARSER", "semantic_judgment_used": False},
        "source": {
            "source_id": target["source_id"],
            "tier": source_entry.get("tier"),
            "independence_cluster": source_entry.get("independence_cluster"),
            "stored_path": target["stored_path"],
            "table_index": target["table_index"],
            "authoritative_T0": source_entry.get("tier") == "T0",
        },
        "table_structure": structure,
        "corroboration_search": search,
        "double_entry_rule": (
            "Candidate identity requires two matching parses or one authoritative T0 structured table. "
            "This source is T1, so single-source rows create no verified B2 evidence."
        ),
        "rows": rows,
        "counts": {
            "rows_parsed": len(rows),
            "territories_resolved": len({row["territory_id"] for row in resolved}),
            "rows_territory_resolved": len(resolved),
            "rows_territory_unresolved": len(rows) - len(resolved),
            "by_state": dict(sorted(states.items())),
        },
    }
    roster["canonical_roster_sha256"] = canonical_sha256(roster)

    certified_local = len(crosswalk["territories"]["local"])
    verified = states.get("VERIFIED_DOUBLE_ENTRY", 0)
    coverage = round(len({row["territory_id"] for row in resolved}) / certified_local, 6)

    failures = []
    if verified == 0:
        failures.append({
            "kind": "NO_ROW_SATISFIES_CRITICAL_DOUBLE_ENTRY",
            "verified_rows": verified,
            "rule": "T1 single-source rows cannot become verified evidence.",
        })
    if coverage < 1.0:
        failures.append({
            "kind": "TERRITORY_COVERAGE_INCOMPLETE",
            "observed": coverage,
            "required": 1.0,
            "note": "B2-4 requires authoritative coverage of all 92 local and 12 regional contests.",
        })

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-2026-BALLOT-CERTIFICATE-V1",
        "gate_id": GATE_ID,
        "certified_at": roster["generated_at"],
        "gate": "PASS" if not failures else "FAIL",
        "roster_path": ROSTER_PATH.relative_to(REPO).as_posix(),
        "roster_sha256": roster["canonical_roster_sha256"],
        "determinism": {"llm_used": False, "semantic_selection": False},
        "rows_parsed": len(rows),
        "constituencies_covered": len({row["territory_id"] for row in resolved}),
        "certified_local_constituencies": certified_local,
        "territory_coverage_fraction": coverage,
        "parties_covered": ["PJD"],
        "party_source_map": {"PJD": target["source_id"]},
        "verified_double_entry_rows": verified,
        "single_source_rows": states.get("SINGLE_SOURCE_ONLY", 0),
        "ambiguous_deterministic_match_rows": states.get("AMBIGUOUS_DETERMINISTIC_MATCH", 0),
        "conflict_rows": states.get("CONFLICT", 0),
        "unknown_rows": states.get("UNKNOWN", 0),
        "blocked_source_documents": blocked,
        "source_class_breakdown": {
            "T0_authoritative_structured_tables": 0,
            "T1_party_official": 1,
            "T2_media": 0,
        },
        "b2_claim_records_created": 0,
        "coefficients_after_gate": "ALL_PREDICTIVE_COEFFICIENTS_REMAIN_EXACTLY_ZERO",
        "failures": failures,
        "scientific_boundary": (
            "This certificate reports parsed roster structure and corroboration state only. It "
            "certifies no candidacy, no ballot presence and no predictive quantity."
        ),
    }
    certificate["canonical_certificate_sha256"] = canonical_sha256(certificate)

    dump(ROSTER_PATH, roster)
    dump(CERTIFICATE_PATH, certificate)

    gates = load(GATES_PATH)
    gate = next(row for row in gates["gates"] if row["id"] == GATE_ID)
    gate["status"] = "CLOSED" if certificate["gate"] == "PASS" else "OPEN"
    gate["last_attempt"] = {
        "certified_at": certificate["certified_at"],
        "result": certificate["gate"],
        "certificate": CERTIFICATE_PATH.relative_to(REPO).as_posix(),
        "roster_sha256": certificate["roster_sha256"],
        "rows_parsed": certificate["rows_parsed"],
        "verified_double_entry_rows": verified,
        "territory_coverage_fraction": coverage,
    }
    gates["as_of"] = certificate["certified_at"]
    dump(GATES_PATH, gates)

    state = load(STATE_PATH)
    state["as_of"] = certificate["certified_at"]
    state["ballot_roster_2026"] = {
        "status": "ATTEMPTED_NOT_VERIFIED" if certificate["gate"] != "PASS" else "CERTIFIED",
        "certificate": CERTIFICATE_PATH.relative_to(REPO).as_posix(),
        "roster_sha256": certificate["roster_sha256"],
        "rows_parsed": certificate["rows_parsed"],
        "verified_double_entry_rows": verified,
        "territory_coverage_fraction": coverage,
        "parties_covered": certificate["parties_covered"],
    }
    dump(STATE_PATH, state)

    print("B2_4_" + ("PASS" if certificate["gate"] == "PASS" else "FAIL"))
    print(f"rows_parsed={len(rows)} territories_resolved={certificate['constituencies_covered']}/{certified_local}")
    print(f"coverage={coverage} verified_double_entry={verified}")
    for name, count in sorted(states.items()):
        print(f"  {name:<34} {count}")
    print(f"corroboration: {search['documents_searched']} documents, {search['clusters_searched']} clusters")
    raise SystemExit(0 if certificate["gate"] == "PASS" else 3)


if __name__ == "__main__":
    main()
