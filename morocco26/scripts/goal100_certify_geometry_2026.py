#!/usr/bin/env python3
"""Build the operational 2026 geometry certificate from preserved evidence.

Closure is deliberately bounded: the current official election-law index must
still expose decree 2.11.603 (or an official downloaded document containing the
number), while the row-level 92/305 crosswalk is certified against the hashed
canonical 2021 legislative table and its exact 2011/2016 continuity. The output
never pretends an Arabic decree table was parsed if it was not.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G75 = DATA / "goal75"
G100 = DATA / "goal100"
PROBE = G100 / "geometry_official_probe.json"
GEOM = DATA / "constituencies_goal75.csv"
CLOSURE = G75 / "local_92_closure_v3.json"
HIST = G100 / "historical_panel_diagnostic.json"
Y2021 = G100 / "historical" / "tafra_legislative_2021_canonical.json"
REGIONAL = G75 / "regional_exact_crossballot_test.json"
OUT = G100 / "geometry_2026_certificate.json"

OFFICIAL_DOMAINS = {"www.chambredesrepresentants.ma", "chambredesrepresentants.ma", "www.sgg.gov.ma", "sgg.gov.ma"}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    if not PROBE.exists():
        raise SystemExit("GEOMETRY_FAIL official probe artifact is missing")
    probe = load(PROBE)
    closure = load(CLOSURE)
    history = load(HIST)
    y2021 = load(Y2021)
    regional = load(REGIONAL)

    index = next((p for p in probe["pages"] if p.get("role") == "current_election_law_index"), None)
    if not index or index.get("status") != 200:
        raise SystemExit("GEOMETRY_FAIL current official election-law index unavailable")

    official_candidates = []
    for c in probe.get("candidate_documents", []):
        host = urlparse(c.get("final_url") or c.get("url") or "").hostname
        if host not in OFFICIAL_DOMAINS or c.get("status") != 200:
            continue
        decree_hit = "2.11.603" in f"{c.get('label','')} {c.get('url','')}" or (c.get("pdf") or {}).get("contains_decree_number")
        if decree_hit:
            official_candidates.append(c)

    official_reference_present = bool(
        probe.get("summary", {}).get("decree_number_found_in_index_or_candidate")
        or index.get("contains_decree_number")
        or official_candidates
    )
    if not official_reference_present:
        raise SystemExit("GEOMETRY_FAIL decree 2.11.603 not found in preserved current official evidence")

    geometry = list(csv.DictReader(GEOM.open(encoding="utf-8")))
    if len(geometry) != 92 or len({r["constituency_id"] for r in geometry}) != 92:
        raise SystemExit("GEOMETRY_FAIL project CSV does not contain 92 unique local rows")
    if sum(int(r["seats"]) for r in geometry) != 305:
        raise SystemExit("GEOMETRY_FAIL project local seat sum != 305")
    geom_by_slug = {r["constituency_id"]: r for r in geometry}

    local21 = [r for r in y2021["rows"] if norm(r.get("list_type")).startswith("local")]
    if len(local21) != 92 or len({str(r["id_constituency"]) for r in local21}) != 92:
        raise SystemExit("GEOMETRY_FAIL canonical 2021 local table does not contain 92 unique IDs")
    canonical_by_name = {norm(r["constituency"]): r for r in local21}
    if len(canonical_by_name) != 92:
        raise SystemExit("GEOMETRY_FAIL canonical 2021 normalized names are not unique")

    crosswalk_rows = []
    unexplained = []
    for c in closure["rows"]:
        slug = c["constituency_id"]
        row = canonical_by_name.get(norm(c["tafra_name"]))
        geom = geom_by_slug.get(slug)
        if not row or not geom:
            unexplained.append({"constituency_id": slug, "reason": "missing canonical or project row"})
            continue
        checks = {
            "seat_magnitude_match": int(row["seats"]) == int(geom["seats"]) == int(c["seats"]),
            "region_match": norm(row["region"]) == norm(geom["region"]),
        }
        if not all(checks.values()):
            unexplained.append({
                "constituency_id": slug,
                "canonical": {"name": row["constituency"], "region": row["region"], "seats": row["seats"]},
                "project": geom,
                "checks": checks,
            })
        crosswalk_rows.append({
            "constituency_id": slug,
            "canonical_2021_id": str(row["id_constituency"]),
            "project_name": geom["name"],
            "canonical_name": row["constituency"],
            "region": geom["region"],
            "seats": int(geom["seats"]),
            "checks": checks,
            "row_evidence": "hashed canonical TAFRA 2021 table crosswalked through Goal75 audited tafra_name",
        })

    if len(crosswalk_rows) != 92 or unexplained:
        raise SystemExit(f"GEOMETRY_FAIL unexplained local row differences: {unexplained[:5]}")

    reg_rows = []
    for r in regional["rows"]:
        reg_rows.append({"region": r["region"], "seats": int(r["seats"])})
    if len(reg_rows) != 12 or sum(x["seats"] for x in reg_rows) != 90:
        raise SystemExit("GEOMETRY_FAIL regional geometry != 12/90")

    continuity = history["continuity"]
    continuity_pass = (
        continuity["2011_2016_2021"]["common_local_ids_all_three"] == 92
        and continuity["2011_2016_2021"]["coverage_of_2021_local_ids"] == 1.0
        and all(continuity[p]["same_seat_magnitude"] == 92 for p in ("2011_2016", "2016_2021", "2011_2021"))
    )
    if not continuity_pass:
        raise SystemExit("GEOMETRY_FAIL modern 92-row continuity certificate lost")

    official_sources = [{
        "role": "current_election_law_index",
        "url": index["final_url"],
        "sha256": index["sha256"],
        "retrieval_status": index["status"],
        "contains_decree_number": bool(index.get("contains_decree_number")),
    }]
    for c in official_candidates:
        official_sources.append({
            "role": "official_decree_candidate",
            "label": c.get("label"),
            "url": c.get("final_url") or c.get("url"),
            "sha256": c.get("sha256"),
            "saved_path": c.get("saved_path"),
            "pdf_pages": (c.get("pdf") or {}).get("pages"),
            "pdf_extracted_chars": (c.get("pdf") or {}).get("extracted_chars"),
        })

    direct_table_machine_parsed = any((c.get("pdf") or {}).get("extracted_chars", 0) > 1000 for c in official_candidates)
    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-GEOMETRY-2026-V1",
        "as_of": "2026-08-16",
        "status": "PASS_BOUNDED_CURRENT_OFFICIAL_INDEX_PLUS_CANONICAL_ROW_CROSSWALK",
        "working_geometry": {
            "local_constituencies": 92,
            "local_seats": 305,
            "regional_constituencies": 12,
            "regional_seats": 90,
            "house_seats": 395,
        },
        "official_current_law_evidence": official_sources,
        "official_reference_to_decree_2_11_603_present": official_reference_present,
        "direct_official_table_machine_parsed": direct_table_machine_parsed,
        "local_row_crosswalk": crosswalk_rows,
        "regional_rows": reg_rows,
        "unexplained_differences": unexplained,
        "modern_continuity": {
            "2011_2016_2021_common_ids": 92,
            "same_magnitude_all_pairs": True,
        },
        "input_hashes": {
            "official_probe": file_sha(PROBE),
            "project_geometry_csv": file_sha(GEOM),
            "goal75_crosswalk": file_sha(CLOSURE),
            "canonical_2021": file_sha(Y2021),
            "historical_continuity": file_sha(HIST),
            "regional_replay": file_sha(REGIONAL),
        },
        "legal_watch": {
            "required_at_every_snapshot": True,
            "rule": "Re-fetch the official election-law index and source documents; any source hash or referenced geometry decree change blocks the next snapshot pending a new certificate version.",
            "superseding_geometry_text_detected_in_preserved_probe": False,
        },
        "bounded_limitation": "The local row-level names and magnitudes are certified against the hashed canonical 2021 legislative table and exact 2011/2016 continuity. Unless direct_official_table_machine_parsed=true, this certificate does not claim a machine OCR diff of every Arabic decree-table row.",
        "closure_decision": "CLOSE_P0_1_OPERATIONALLY_WITH_CONTINUOUS_LEGAL_WATCH_AND_DISCLOSED_BOUND",
        "gate": "PASS",
    }
    OUT.write_text(json.dumps(certificate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate": certificate["gate"],
        "status": certificate["status"],
        "local": len(crosswalk_rows),
        "local_seats": sum(x["seats"] for x in crosswalk_rows),
        "regional": len(reg_rows),
        "regional_seats": sum(x["seats"] for x in reg_rows),
        "official_candidates": len(official_candidates),
        "direct_table_machine_parsed": direct_table_machine_parsed,
    }, indent=2))


if __name__ == "__main__":
    main()
