#!/usr/bin/env python3
"""Audit a 92-page to 92-constituency identity bijection for PPS-2016 PDFs.

The twelve official regional PDFs contain exactly one page per local
constituency. This diagnostic compares only page-header Arabic text to the
accepted Arabic identity bridge, then solves the maximum-weight one-to-one
assignment separately inside each region. Low-score assignments remain marked
BIJECTION_ONLY and are not automatically promoted by this script.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
CROSS = ER / "evidence/arabic_2016_crosswalk/crosswalk.json"
PTR = ER / "pps_2016_regional_pdf_probe_latest.json"
OUT = ER / "evidence/pps_2016_region_bijection"

REGION_MATCH = {
    "casablanca-settat": "casablanca settat",
    "souss-massa": "souss massa",
    "oriental": "oriental",
    "beni-mellal-khenifra": "beni mellal khenifra",
    "rabat-sale-kenitra": "rabat sale kenitra",
    "marrakech-safi": "marrakech safi",
    "fes-meknes": "fes meknes",
    "tanger-tetouan-al-hoceima": "tanger tetouan al hoceima",
    "draa-tafilalet": "draa tafilalet",
    "guelmim-oued-noun": "guelmim oued noun",
    "laayoune-sakia-el-hamra": "laayoune sakia el hamra",
    "dakhla-oued-ed-dahab": "dakhla oued ed dahab",
}

ALIASES = {
    "فجيج": "figuig",
    "فيجيج": "figuig",
    "شتوكة ايت باها": "chtouka-ait-baha",
    "شتوكة آيت باها": "chtouka-ait-baha",
    "انفا": "casablanca-anfa",
    "آنفا": "casablanca-anfa",
    "سال المدينة": "sale-medina",
    "سلا المدينة": "sale-medina",
    "سال الجديدة": "sala-al-jadida",
    "سلا الجديدة": "sala-al-jadida",
    "الرباط المحيط": "rabat-ocean",
    "الرباط شالة": "rabat-chellah",
    "ازيالل دمنات": "azilal-demnate",
    "بوملان": "boulemane",
    "الخميسات": "khemisset-ouelmes",
    "الخميسات والماس": "khemisset-ouelmes",
    "تيفلت الرماني": "tiflet-rommani",
    "تيفلت - الرماني": "tiflet-rommani",
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


def norm_latin(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def page_header(page) -> list[str]:
    text = page.extract_text() or ""
    lines = [norm_ar(line) for line in text.splitlines() if norm_ar(line)]
    # Territory appears before candidate biographies. Twelve logical lines is a
    # conservative bound and is recorded for audit.
    return lines[:12]


def score_header(header: list[str], variants: set[str]) -> tuple[float, dict | None]:
    best = 0.0
    pair = None
    for line_index, line in enumerate(header):
        lc = compact(line)
        if not lc:
            continue
        for variant in variants:
            vc = compact(variant)
            if not vc:
                continue
            if vc in lc or lc in vc:
                score = 1.0 if vc == lc else min(len(vc), len(lc)) / max(len(vc), len(lc))
            else:
                score = SequenceMatcher(None, lc, vc).ratio()
            # Earlier header lines are slightly preferred only as a tie-breaker.
            adjusted = score - line_index * 1e-5
            if adjusted > best:
                best = adjusted
                pair = {"line_index": line_index, "header_line": line, "variant": variant, "raw_score": round(score, 6)}
    return best, pair


def max_assignment(weights: list[list[float]]) -> tuple[float, list[int]]:
    """Bitmask dynamic program; regional n <= 16 so this is bounded."""
    n = len(weights)
    if n == 0:
        return 0.0, []
    dp: dict[int, tuple[float, list[int]]] = {0: (0.0, [])}
    for page_index in range(n):
        nxt: dict[int, tuple[float, list[int]]] = {}
        for mask, (value, path) in dp.items():
            for district_index in range(n):
                bit = 1 << district_index
                if mask & bit:
                    continue
                new_mask = mask | bit
                new_value = value + weights[page_index][district_index]
                old = nxt.get(new_mask)
                if old is None or new_value > old[0]:
                    nxt[new_mask] = (new_value, path + [district_index])
        dp = nxt
    return dp[(1 << n) - 1]


def main() -> int:
    cross = json.loads(CROSS.read_text(encoding="utf-8"))
    pointer = json.loads(PTR.read_text(encoding="utf-8"))
    probe = json.loads((ROOT / pointer["latest_probe"]).read_text(encoding="utf-8"))
    records = cross["records"]
    variants_by_cid: dict[str, set[str]] = {}
    for record in records:
        cid = record["source_2026_constituency_id"]
        variants_by_cid[cid] = {
            norm_ar(record.get("name_ar")),
            norm_ar(record.get("name_ar_source_form")),
            norm_ar(record.get("name_ar_match_key")),
        } - {""}
    for alias, cid in ALIASES.items():
        variants_by_cid.setdefault(cid, set()).add(norm_ar(alias))

    region_results = []
    total_pages = 0
    total_districts = 0
    for doc in sorted(probe["pdf_hits"], key=lambda x: x["region_slug"]):
        region_slug = doc["region_slug"]
        canonical = [
            r
            for r in records
            if norm_latin(r.get("historical_region")) == REGION_MATCH[region_slug]
        ]
        canonical.sort(key=lambda r: str(r["source_2026_constituency_id"]))
        reader = PdfReader(str(ROOT / doc["pdf"]["raw_path"]))
        headers = [page_header(page) for page in reader.pages]
        total_pages += len(headers)
        total_districts += len(canonical)
        if len(headers) != len(canonical):
            region_results.append(
                {
                    "region_slug": region_slug,
                    "status": "PAGE_COUNT_MISMATCH",
                    "page_count": len(headers),
                    "canonical_district_count": len(canonical),
                }
            )
            continue
        weights: list[list[float]] = []
        pairs: list[list[dict | None]] = []
        for header in headers:
            row_weights = []
            row_pairs = []
            for district in canonical:
                score, pair = score_header(header, variants_by_cid[district["source_2026_constituency_id"]])
                row_weights.append(score)
                row_pairs.append(pair)
            weights.append(row_weights)
            pairs.append(row_pairs)
        total_score, assignment = max_assignment(weights)
        pages = []
        for page_index, district_index in enumerate(assignment):
            selected_score = weights[page_index][district_index]
            alternatives = sorted(weights[page_index], reverse=True)
            local_second = alternatives[1] if len(alternatives) > 1 else 0.0
            district = canonical[district_index]
            if selected_score >= 0.999:
                method = "EXACT_HEADER"
            elif selected_score >= 0.82 and selected_score - local_second >= 0.06:
                method = "HIGH_CONFIDENCE_HEADER"
            else:
                method = "REGION_BIJECTION_ONLY_REQUIRES_AUDIT"
            pages.append(
                {
                    "page": page_index + 1,
                    "header_lines": headers[page_index],
                    "assigned_constituency_id": district["source_2026_constituency_id"],
                    "historical_constituency": district["historical_constituency"],
                    "historical_seats_2016": int(district["historical_seats_2016"]),
                    "assignment_score": round(selected_score, 6),
                    "page_local_second_score": round(local_second, 6),
                    "page_local_margin": round(selected_score - local_second, 6),
                    "matched_pair": pairs[page_index][district_index],
                    "assignment_method": method,
                }
            )
        region_results.append(
            {
                "region_slug": region_slug,
                "status": "BIJECTION_SOLVED",
                "page_count": len(headers),
                "canonical_district_count": len(canonical),
                "assignment_total_score": round(total_score, 6),
                "exact_or_high_confidence_pages": sum(p["assignment_method"] != "REGION_BIJECTION_ONLY_REQUIRES_AUDIT" for p in pages),
                "bijection_only_pages": sum(p["assignment_method"] == "REGION_BIJECTION_ONLY_REQUIRES_AUDIT" for p in pages),
                "pages": pages,
            }
        )

    solved = all(r.get("status") == "BIJECTION_SOLVED" for r in region_results)
    unique_ids = {
        p["assigned_constituency_id"]
        for r in region_results
        for p in r.get("pages", [])
    }
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status": "PASS_92_TO_92_IDENTITY_BIJECTION_DIAGNOSTIC" if solved and total_pages == 92 and len(unique_ids) == 92 else "FAIL_CLOSED",
        "counts": {
            "regional_pdfs": len(region_results),
            "pdf_pages": total_pages,
            "canonical_districts": total_districts,
            "unique_assigned_constituency_ids": len(unique_ids),
            "exact_or_high_confidence_pages": sum(r.get("exact_or_high_confidence_pages", 0) for r in region_results),
            "bijection_only_pages": sum(r.get("bijection_only_pages", 0) for r in region_results),
        },
        "regions": region_results,
        "invariants": {
            "assignment_scope": "IDENTITY_ONLY_WITHIN_REGION",
            "candidate_facts_generated": False,
            "bijection_only_assignments_promoted": False,
            "outcomes_unsealed": False,
            "predictive_judgments_generated": False,
            "F1_created": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bijection.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "regions": [{"region": r["region_slug"], "status": r["status"], "pages": r.get("page_count"), "bijection_only": r.get("bijection_only_pages")} for r in region_results]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
