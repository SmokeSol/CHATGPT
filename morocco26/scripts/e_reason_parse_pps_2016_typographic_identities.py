#!/usr/bin/env python3
"""Parse PPS-2016 candidate identities from exact/high-confidence poster pages.

Territory identity is imported only from the audited 92-page bijection when the
page has EXACT_HEADER or HIGH_CONFIDENCE_HEADER status. Candidate identities are
selected from the poster's candidate zone by a frozen typography rule: Arabic
same-line groups split at large horizontal gaps, obvious office/occupation text
excluded, then the historical seat-magnitude highest-scoring name-like groups
retained. A font-map CID loss does not erase identity: the exact raw glyph group,
page and bounding box form a stable evidence-addressed identity key while the
human-readable name remains MISSING. No list rank is inferred from poster layout.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
PTR = ER / "pps_2016_regional_pdf_probe_latest.json"
BIJ = ER / "evidence/pps_2016_region_bijection/bijection.json"
AUD = ER / "evidence/pps_2016_pdf_provenance_audit/audit.json"
OUT = ER / "evidence/pps_2016_typographic_identities"

CID_RE = re.compile(r"\(?cid:\d+\)?|\)?\d+:dic\(?|[ƒŒŽˆ›“£€‡†‹–]", re.I)
AR_RE = re.compile(r"[\u0600-\u06FF]")

# Frozen non-name vocabulary. It blocks role/occupation/biography groups, not
# individual candidate tokens elsewhere on the page.
NON_NAME_TOKENS = {
    "رجل", "اعمال", "أعمال", "تاجر", "تاجرة", "استاذ", "أستاذ", "استاذة", "أستاذة",
    "موظف", "موظفة", "اطار", "إطار", "فاعل", "فاعلة", "جمعوي", "جمعوية", "رئيس", "رئيسة",
    "نائب", "نائبة", "جماعة", "مستشار", "مستشارة", "مقاول", "مقاولة", "طبيب", "طبيبة",
    "دكتور", "دكتورة", "مهندس", "مهندسة", "مدير", "مديرة", "تقني", "تقنية", "فلاح",
    "عامل", "عاملة", "سائق", "طالبة", "طالب", "عدل", "مستخدم", "مستخدمة", "متقاعد",
    "متقاعدة", "ممول", "ناشط", "ناشطة", "عضو", "كاتبة", "كاتب", "مسؤول", "مسؤولة",
    "وكيل", "وكيلة", "اللائحة", "ممرض", "ممرضة", "صحفي", "صحفية", "خبير", "خبيرة",
    "باحث", "باحثة", "مسير", "مسيرة", "موزع", "مستثمر", "مستثمرة", "محامي", "صيدلي",
    "صيدلانية", "منسق", "منسقة", "مساعد", "مساعدة", "مفوض", "قضائي", "إداري", "اداري",
    "شركة", "مؤسسة", "جامعة", "جامعية", "جامعي", "جمعاوي", "سياسي", "سياسية", "حزب",
}
BLOCK_PHRASES = {
    "المعقول", "صوتوا بوضع علامة", "على الكتاب", "علي الكتاب", "وكيل اللائحة", "وكيلة اللائحة",
    "الانتخابات التشريعية", "7 اكتوبر", "7 أكتوبر", "C M J", "CMJ",
}


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def norm_ar(value: object) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(clean(value))).replace("ـ", "")
    text = text.translate(str.maketrans({"ی": "ي", "ى": "ي", "ک": "ك", "ۀ": "ة", "ہ": "ه"}))
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"[^\u0600-\u06FF0-9]+", " ", text)
    return " ".join(text.split())


def compact(value: object) -> str:
    return norm_ar(value).replace(" ", "")


def logical_word(value: object) -> str:
    return unicodedata.normalize("NFKC", clean(value))[::-1]


def has_arabic(value: object) -> bool:
    return bool(AR_RE.search(unicodedata.normalize("NFKC", str(value or ""))))


def cluster_lines(words: list[dict[str, Any]], y_tolerance: float = 2.6) -> list[dict[str, Any]]:
    lines: list[dict[str, Any]] = []
    for word in sorted(words, key=lambda w: (float(w["top"]), float(w["x0"]))):
        target = next((line for line in lines if abs(line["top"] - float(word["top"])) <= y_tolerance), None)
        if target is None:
            target = {"top": float(word["top"]), "words": []}
            lines.append(target)
        target["words"].append(word)
    return sorted(lines, key=lambda x: x["top"])


def split_x(words: list[dict[str, Any]], gap: float = 20.0) -> list[list[dict[str, Any]]]:
    ordered = sorted(words, key=lambda w: float(w["x0"]))
    groups: list[list[dict[str, Any]]] = []
    for word in ordered:
        if not groups or float(word["x0"]) - float(groups[-1][-1]["x1"]) > gap:
            groups.append([word])
        else:
            groups[-1].append(word)
    return groups


def group_record(group: list[dict[str, Any]], page_width: float, page_height: float, page_text_lines: list[str]) -> dict[str, Any]:
    rtl = sorted(group, key=lambda w: -float(w["x0"]))
    raw_words = [str(w["text"]) for w in rtl]
    logical_tokens = [logical_word(x) for x in raw_words]
    raw_text = clean(" ".join(logical_tokens))
    readable = clean(CID_RE.sub(" ", raw_text))
    normalized = norm_ar(readable)
    tokens = normalized.split()
    x0 = min(float(w["x0"]) for w in group)
    x1 = max(float(w["x1"]) for w in group)
    top = min(float(w["top"]) for w in group)
    bottom = max(float(w["bottom"]) for w in group)
    sizes = sorted({round(float(w.get("size") or 0), 2) for w in group}, reverse=True)
    max_size = max(sizes or [0.0])
    raw_has_cid = any(CID_RE.search(x) for x in raw_words)
    phrase_block = any(norm_ar(p) and compact(p) in compact(normalized) for p in BLOCK_PHRASES)
    non_name_hits = [token for token in tokens if token in {norm_ar(x) for x in NON_NAME_TOKENS}]
    first_non_name = bool(tokens and tokens[0] in {norm_ar(x) for x in NON_NAME_TOKENS})
    occupation_block = first_non_name or (tokens and len(non_name_hits) / len(tokens) >= 0.5)
    line_matches = []
    anchors = [token for token in tokens if len(token) >= 3 and token not in {norm_ar(x) for x in NON_NAME_TOKENS}]
    if anchors:
        for line in page_text_lines:
            nl = norm_ar(line)
            if 1 <= len(nl.split()) <= 7 and all(compact(anchor) in compact(nl) for anchor in anchors):
                line_matches.append(nl)
        line_matches = list(dict.fromkeys(line_matches))
    name_like = (
        0.36 <= top / page_height <= 0.79
        and max_size >= 10.0
        and len(raw_words) >= 1
        and not phrase_block
        and not occupation_block
        and (len(tokens) >= 2 or len(raw_words) >= 2)
    )
    token_bonus = 1.5 if 2 <= len(tokens) <= 5 else 0.0
    independent_line_bonus = 1.0 if len(line_matches) == 1 else 0.0
    # Font size is primary; earlier text within the broad candidate zone is only
    # a weak tie-breaker. This prevents smaller biography text from winning.
    score = max_size * 10.0 + token_bonus + independent_line_bonus - abs(top / page_height - 0.61)
    return {
        "raw_words_rtl": raw_words,
        "logical_raw_text": raw_text,
        "readable_text_without_cid": readable,
        "candidate_name_ar_normalized": normalized if not raw_has_cid and len(tokens) >= 2 else None,
        "raw_has_fontmap_loss": raw_has_cid,
        "font_sizes": sizes,
        "max_font_size": max_size,
        "bbox": [round(x0, 2), round(top, 2), round(x1, 2), round(bottom, 2)],
        "center_x_fraction": round(((x0 + x1) / 2.0) / page_width, 4),
        "top_fraction": round(top / page_height, 4),
        "tokens": tokens,
        "non_name_hits": non_name_hits,
        "phrase_block": phrase_block,
        "occupation_block": occupation_block,
        "name_like": name_like,
        "independent_pypdf_line_matches": line_matches,
        "selection_score": round(score, 6),
    }


def main() -> int:
    pointer = json.loads(PTR.read_text(encoding="utf-8"))
    probe = json.loads((ROOT / pointer["latest_probe"]).read_text(encoding="utf-8"))
    bijection = json.loads(BIJ.read_text(encoding="utf-8"))
    audit = json.loads(AUD.read_text(encoding="utf-8"))
    if bijection.get("status") != "PASS_92_TO_92_IDENTITY_BIJECTION_DIAGNOSTIC":
        raise RuntimeError("PPS 92-to-92 identity bijection is not PASS")
    if audit.get("counts", {}).get("mechanically_admissible_pdfs") != 12:
        raise RuntimeError("PPS provenance is not 12/12 admissible")

    doc_by_region = {row["region_slug"]: row for row in probe["pdf_hits"]}
    provenance_by_sha = {row["probe_sha256"]: row for row in audit["relationships"] if row["mechanical_pass"]}
    page_map = {
        (region["region_slug"], int(page["page"])): page
        for region in bijection["regions"]
        for page in region.get("pages", [])
        if page.get("assignment_method") in {"EXACT_HEADER", "HIGH_CONFIDENCE_HEADER"}
    }

    territory_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    for region_slug, doc in sorted(doc_by_region.items()):
        path = ROOT / doc["pdf"]["raw_path"]
        provenance = provenance_by_sha.get(doc["sha256"])
        if not provenance:
            raise RuntimeError(f"missing provenance for {doc['sha256']}")
        reader = PdfReader(str(path))
        with pdfplumber.open(str(path)) as pdf:
            for page_no, (page, pypage) in enumerate(zip(pdf.pages, reader.pages), 1):
                mapping = page_map.get((region_slug, page_no))
                if not mapping:
                    diagnostics.append({"region": region_slug, "page": page_no, "status": "SKIP_NON_EXACT_TERRITORY_MAPPING"})
                    continue
                seats = int(mapping["historical_seats_2016"])
                pypdf_lines = [clean(x) for x in (pypage.extract_text() or "").splitlines() if clean(x)]
                words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=1, y_tolerance=1, extra_attrs=["size", "fontname"]) or []
                arabic_words = [w for w in words if has_arabic(w.get("text"))]
                groups = []
                for line in cluster_lines(arabic_words):
                    for group in split_x(line["words"]):
                        groups.append(group_record(group, float(page.width), float(page.height), pypdf_lines))
                eligible = [g for g in groups if g["name_like"]]
                eligible.sort(key=lambda g: (-g["selection_score"], g["top_fraction"], -g["center_x_fraction"]))
                selected = eligible[:seats]
                errors = []
                if len(selected) != seats:
                    errors.append(f"SELECTED_{len(selected)}_NE_SEATS_{seats}")
                identity_keys = []
                for group in selected:
                    identity_material = json.dumps({"pdf_sha256": doc["sha256"], "page": page_no, "bbox": group["bbox"], "raw_words_rtl": group["raw_words_rtl"]}, ensure_ascii=False, sort_keys=True).encode("utf-8")
                    identity_keys.append(hashlib.sha256(identity_material).hexdigest())
                if len(set(identity_keys)) != len(identity_keys):
                    errors.append("DUPLICATE_RAW_IDENTITY_KEY")
                diagnostic = {"region": region_slug, "page": page_no, "constituency_id": mapping["assigned_constituency_id"], "historical_constituency": mapping["historical_constituency"], "territory_assignment_method": mapping["assignment_method"], "territory_assignment_score": mapping["assignment_score"], "seats": seats, "eligible_group_count": len(eligible), "selected_groups": selected, "errors": errors}
                diagnostics.append(diagnostic)
                if errors:
                    failures.append(diagnostic)
                    continue
                excerpt = {"page": page_no, "territory_header_lines": mapping["header_lines"], "territory_assignment_method": mapping["assignment_method"], "selected_typographic_groups": selected}
                territory_rows.append({"year": 2016, "party": "PPS", "constituency_id": mapping["assigned_constituency_id"], "historical_constituency": mapping["historical_constituency"], "seats": seats, "candidate_count": seats, "FORMAL_ENDORSEMENT": True, "source_class": "T1_OFFICIAL_PARTY", "pdf_sha256": doc["sha256"], "parent_page_url": provenance["page_url"], "parent_page_timestamps": provenance["page_timestamps"], "territory_assignment_method": mapping["assignment_method"], "evidence_excerpt": excerpt})
                for display_order, (group, identity_key) in enumerate(zip(selected, identity_keys), 1):
                    readable_name = group["candidate_name_ar_normalized"]
                    candidate_rows.append({"year": 2016, "party": "PPS", "constituency_id": mapping["assigned_constituency_id"], "historical_constituency": mapping["historical_constituency"], "candidate_name_ar": readable_name, "candidate_name_ar_normalized": readable_name, "candidate_identity_key": identity_key, "candidate_text_status": "HUMAN_READABLE" if readable_name else "RAW_GLYPH_IDENTITY_FONTMAP_LOSS", "identity_verification": "ADMISSIBLE_T1_TYPOGRAPHIC_NAME_GROUP", "candidate_rank": None, "CANDIDATE_REGISTERED_RANK": None, "rank_evidence_status": "MISSING_NOT_INFERRED_FROM_POSTER_LAYOUT", "FORMAL_ENDORSEMENT": True, "party_fact_status": "PARTY_ANNOUNCED", "poster_display_order_only": display_order, "evidence": {"publication_time": provenance["page_timestamps"][0] if provenance["page_timestamps"] else None, "retrieval_time": audit["created_at"], "source_class": "T1_OFFICIAL_PARTY", "content_sha256": doc["sha256"], "parent_page_url": provenance["page_url"], "page": page_no, "archived_excerpt": {"bbox": group["bbox"], "raw_words_rtl": group["raw_words_rtl"], "logical_raw_text": group["logical_raw_text"], "font_sizes": group["font_sizes"], "territory_assignment_method": mapping["assignment_method"]}}})

    by_territory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_territory[row["constituency_id"]].append(row)
    identity_districts = sum(len({x["candidate_name_ar_normalized"] or x["candidate_identity_key"] for x in rows}) >= 3 for rows in by_territory.values())
    payload = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PARTIAL_VALID", "territory_rows": territory_rows, "candidate_rows": candidate_rows, "failures": failures, "page_diagnostics": diagnostics, "counts": {"eligible_exact_or_high_territory_pages": len(page_map), "territories_parsed": len(territory_rows), "candidate_rows": len(candidate_rows), "human_readable_candidate_rows": sum(x["candidate_text_status"] == "HUMAN_READABLE" for x in candidate_rows), "raw_glyph_identity_rows": sum(x["candidate_text_status"] != "HUMAN_READABLE" for x in candidate_rows), "districts_with_at_least_three_verified_candidate_identities": identity_districts, "failure_pages": len(failures)}, "invariants": {"territory_mapping_methods_allowed": ["EXACT_HEADER", "HIGH_CONFIDENCE_HEADER"], "raw_glyph_identity_is_evidence_addressed": True, "candidate_rank_inferred_from_layout": False, "occupation_groups_excluded_by_frozen_vocabulary": True, "failed_pages_promoted": False, "outcomes_unsealed": False, "predictive_judgments_generated": False, "forecast_delta_generated": False, "F1_created": False}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "parsed_identities.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "failure_sample": [{"district": x["historical_constituency"], "seats": x["seats"], "eligible": x["eligible_group_count"], "errors": x["errors"]} for x in failures[:20]]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
