#!/usr/bin/env python3
"""Parse candidate identities on safe direct-title PPS pages not yet covered.

The existing typographic parser remains authoritative for its 65 exact/high
header pages. This extension consumes only pages marked `direct_identity_safe`
by the stricter full-title equality mapper and excludes pages already present in
the base typographic artifact. Candidate-group extraction is the exact same
frozen function imported from the base parser. No layout rank or outcome is used.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
PTR = ER / "pps_2016_regional_pdf_probe_latest.json"
AUD = ER / "evidence/pps_2016_pdf_provenance_audit/audit.json"
DIRECT = ER / "evidence/pps_2016_direct_page_identity/direct_map.json"
BASE = ER / "evidence/pps_2016_typographic_identities/parsed_identities.json"
BASE_SCRIPT = ROOT / "morocco26/scripts/e_reason_parse_pps_2016_typographic_identities.py"
OUT = ER / "evidence/pps_2016_direct_typographic_extension"


def load_base_module():
    spec = importlib.util.spec_from_file_location("e_reason_pps_typographic_base", BASE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot import base typographic parser")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    base_module = load_base_module()
    pointer = json.loads(PTR.read_text(encoding="utf-8"))
    probe = json.loads((ROOT / pointer["latest_probe"]).read_text(encoding="utf-8"))
    audit = json.loads(AUD.read_text(encoding="utf-8"))
    direct = json.loads(DIRECT.read_text(encoding="utf-8"))
    base = json.loads(BASE.read_text(encoding="utf-8"))
    if direct.get("schema_version") != "1.1" or not direct.get("invariants", {}).get("full_exact_title_equality_required"):
        raise RuntimeError("direct map is not strict schema 1.1")
    if audit.get("counts", {}).get("mechanically_admissible_pdfs") != 12:
        raise RuntimeError("PPS provenance is not 12/12")

    docs = {row["region_slug"]: row for row in probe["pdf_hits"]}
    region_by_sha = {row["sha256"]: row["region_slug"] for row in probe["pdf_hits"]}
    provenance_by_sha = {row["probe_sha256"]: row for row in audit["relationships"] if row["mechanical_pass"]}
    base_page_keys = {
        (region_by_sha[row["pdf_sha256"]], int(row["evidence_excerpt"]["page"]))
        for row in base.get("territory_rows", [])
        if row.get("pdf_sha256") in region_by_sha and row.get("evidence_excerpt", {}).get("page")
    }
    page_map = {
        (row["region"], int(row["page"])): row
        for row in direct["pages"]
        if row.get("direct_identity_safe") is True and row.get("assignment") and (row["region"], int(row["page"])) not in base_page_keys
    }

    territory_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for region, doc in sorted(docs.items()):
        relevant = {page: mapping for (r, page), mapping in page_map.items() if r == region}
        if not relevant:
            continue
        path = ROOT / doc["pdf"]["raw_path"]
        provenance = provenance_by_sha.get(doc["sha256"])
        if not provenance:
            raise RuntimeError(f"missing provenance for {doc['sha256']}")
        reader = PdfReader(str(path))
        with pdfplumber.open(str(path)) as pdf:
            for page_no, mapping_row in sorted(relevant.items()):
                page = pdf.pages[page_no - 1]
                pypage = reader.pages[page_no - 1]
                assignment = mapping_row["assignment"]
                seats = int(assignment["historical_seats_2016"])
                pypdf_lines = [base_module.clean(x) for x in (pypage.extract_text() or "").splitlines() if base_module.clean(x)]
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=1, y_tolerance=1, extra_attrs=["size", "fontname"]) or []
                arabic_words = [word for word in words if base_module.has_arabic(word.get("text"))]
                groups = []
                for line in base_module.cluster_lines(arabic_words):
                    for group in base_module.split_x(line["words"]):
                        groups.append(base_module.group_record(group, float(page.width), float(page.height), pypdf_lines))
                eligible = [group for group in groups if group["name_like"]]
                eligible.sort(key=lambda group: (-group["selection_score"], group["top_fraction"], -group["center_x_fraction"]))
                selected = eligible[:seats]
                errors = []
                if len(selected) != seats:
                    errors.append(f"SELECTED_{len(selected)}_NE_SEATS_{seats}")
                identity_keys = []
                for group in selected:
                    material = json.dumps({"pdf_sha256": doc["sha256"], "page": page_no, "bbox": group["bbox"], "raw_words_rtl": group["raw_words_rtl"]}, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    identity_keys.append(hashlib.sha256(material).hexdigest())
                if len(set(identity_keys)) != len(identity_keys):
                    errors.append("DUPLICATE_RAW_IDENTITY_KEY")
                diagnostic = {"region": region, "page": page_no, "constituency_id": assignment["constituency_id"], "historical_constituency": assignment["historical_constituency"], "territory_assignment_method": "DIRECT_EXACT_PAGE_IDENTITY", "direct_title_evidence": assignment["evidence"], "seats": seats, "eligible_group_count": len(eligible), "selected_groups": selected, "errors": errors}
                diagnostics.append(diagnostic)
                if errors:
                    failures.append(diagnostic)
                    continue
                excerpt = {"page": page_no, "direct_title_evidence": assignment["evidence"], "selected_typographic_groups": selected}
                territory_rows.append({"year": 2016, "party": "PPS", "constituency_id": assignment["constituency_id"], "historical_constituency": assignment["historical_constituency"], "seats": seats, "candidate_count": seats, "FORMAL_ENDORSEMENT": True, "source_class": "T1_OFFICIAL_PARTY", "pdf_sha256": doc["sha256"], "parent_page_url": provenance["page_url"], "parent_page_timestamps": provenance["page_timestamps"], "territory_assignment_method": "DIRECT_EXACT_PAGE_IDENTITY", "evidence_excerpt": excerpt})
                for display_order, (group, identity_key) in enumerate(zip(selected, identity_keys), 1):
                    readable = group["candidate_name_ar_normalized"]
                    candidate_rows.append({"year": 2016, "party": "PPS", "constituency_id": assignment["constituency_id"], "historical_constituency": assignment["historical_constituency"], "candidate_name_ar": readable, "candidate_name_ar_normalized": readable, "candidate_identity_key": identity_key, "candidate_text_status": "HUMAN_READABLE" if readable else "RAW_GLYPH_IDENTITY_FONTMAP_LOSS", "identity_verification": "ADMISSIBLE_T1_TYPOGRAPHIC_NAME_GROUP_ON_DIRECT_TITLE_PAGE", "candidate_rank": None, "CANDIDATE_REGISTERED_RANK": None, "rank_evidence_status": "MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT", "FORMAL_ENDORSEMENT": True, "party_fact_status": "PARTY_ANNOUNCED", "poster_display_order_only": display_order, "evidence": {"publication_time": provenance["page_timestamps"][0] if provenance["page_timestamps"] else None, "retrieval_time": audit["created_at"], "source_class": "T1_OFFICIAL_PARTY", "content_sha256": doc["sha256"], "parent_page_url": provenance["page_url"], "page": page_no, "archived_excerpt": {"direct_title_evidence": assignment["evidence"], "bbox": group["bbox"], "raw_words_rtl": group["raw_words_rtl"], "logical_raw_text": group["logical_raw_text"], "font_sizes": group["font_sizes"]}}})

    by_territory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_territory[row["constituency_id"]].append(row)
    ge3 = sum(len({row["candidate_name_ar_normalized"] or row["candidate_identity_key"] for row in rows}) >= 3 for rows in by_territory.values())
    payload = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PARTIAL_VALID", "base_typographic_pages_excluded": len(base_page_keys), "safe_direct_extension_pages": len(page_map), "territory_rows": territory_rows, "candidate_rows": candidate_rows, "failures": failures, "page_diagnostics": diagnostics, "counts": {"safe_direct_extension_pages": len(page_map), "territories_parsed": len(territory_rows), "candidate_rows": len(candidate_rows), "districts_with_at_least_three_verified_candidate_identities": ge3, "failure_pages": len(failures)}, "invariants": {"same_page_not_reparsed_from_base_typographic_artifact": True, "direct_identity_safe_required": True, "full_exact_title_equality_required": True, "candidate_rank_inferred_from_layout": False, "failed_pages_promoted": False, "outcomes_unsealed": False, "predictive_judgments_generated": False, "forecast_delta_generated": False, "F1_created": False}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "extension.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "territories": [row["historical_constituency"] for row in territory_rows], "failure_sample": [{"district": row["historical_constituency"], "seats": row["seats"], "eligible": row["eligible_group_count"], "errors": row["errors"]} for row in failures]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
