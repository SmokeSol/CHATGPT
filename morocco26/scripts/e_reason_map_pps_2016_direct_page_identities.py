#!/usr/bin/env python3
"""Map PPS-2016 pages to constituencies using direct title evidence only.

Unlike the regional bijection diagnostic, this mapper never assigns a page by
remainder. It accepts only an exact canonical/observed Arabic title form found
in a spatial top-area group, an exact logical PDF line, or (for page 1) the PDF
metadata title. Short official poster forms such as اشتوكة and وجدة are frozen
as identity aliases. Duplicate direct titles are reported rather than forced
onto missing districts. No candidate or outcome fact is generated here.
"""
from __future__ import annotations

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
CROSS = ER / "evidence/arabic_2016_crosswalk/crosswalk.json"
PTR = ER / "pps_2016_regional_pdf_probe_latest.json"
OUT = ER / "evidence/pps_2016_direct_page_identity"

REGION_MATCH = {
    "casablanca-settat": "casablanca settat", "souss-massa": "souss massa", "oriental": "oriental",
    "beni-mellal-khenifra": "beni mellal khenifra", "rabat-sale-kenitra": "rabat sale kenitra",
    "marrakech-safi": "marrakech safi", "fes-meknes": "fes meknes",
    "tanger-tetouan-al-hoceima": "tanger tetouan al hoceima", "draa-tafilalet": "draa tafilalet",
    "guelmim-oued-noun": "guelmim oued noun", "laayoune-sakia-el-hamra": "laayoune sakia el hamra",
    "dakhla-oued-ed-dahab": "dakhla oued ed dahab",
}

# Observed first-party poster title spellings/abbreviations. These are identity
# normalizations only; they contain no candidate, seat or outcome information.
DIRECT_ALIASES = {
    "chtouka-ait-baha": ["اشتوكة", "شتوكة ايت باها"],
    "oujda-angad": ["وجدة", "وجدة انجاد"],
    "agadir-ida-outanane": ["اكادير اداوتنان", "باكادير اداوتنان"],
    "khemisset-oulmes": ["الخميسات", "الخميسات اولماس"],
    "khouribga": ["خريبكة"],
    "beni-mellal": ["بني ملال", "بني م"],
    "sidi-ifni": ["سيدي افني", "سيدي"],
    "inezgane-ait-melloul": ["انزكان ايت ملول", "انزكان"],
    "moulay-rachid": ["مولاي رشيد"],
    "sale-el-jadida": ["سلا الجديدة", "سال الجديدة"],
    "ouezzane": ["وزان"],
    "ifrane": ["افران", "إفران"],
    "moulay-yaacoub": ["مولاي يعقوب"],
    "casablanca-anfa": ["الدار البيضاء انفا", "انفا"],
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


def logical_word(value: object) -> str:
    return unicodedata.normalize("NFKC", clean(value))[::-1]


def spatial_top_groups(page) -> list[dict[str, Any]]:
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False, x_tolerance=1, y_tolerance=1, extra_attrs=["size"]) or []
    words = [w for w in words if re.search(r"[\u0600-\u06FF]", unicodedata.normalize("NFKC", str(w.get("text") or ""))) and float(w["top"]) <= 0.40 * float(page.height)]
    lines: list[dict[str, Any]] = []
    for word in sorted(words, key=lambda w: (float(w["top"]), float(w["x0"]))):
        line = next((x for x in lines if abs(x["top"] - float(word["top"])) <= 2.8), None)
        if line is None:
            line = {"top": float(word["top"]), "words": []}
            lines.append(line)
        line["words"].append(word)
    groups = []
    for line in lines:
        ordered = sorted(line["words"], key=lambda w: float(w["x0"]))
        split: list[list[dict[str, Any]]] = []
        for word in ordered:
            if not split or float(word["x0"]) - float(split[-1][-1]["x1"]) > 20.0:
                split.append([word])
            else:
                split[-1].append(word)
        for group in split:
            rtl = sorted(group, key=lambda w: -float(w["x0"]))
            groups.append({"source": "PDFPLUMBER_TOP_GROUP", "top": round(line["top"], 2), "top_fraction": round(line["top"] / float(page.height), 4), "text": norm_ar(" ".join(logical_word(w["text"]) for w in rtl)), "raw_words_rtl": [w["text"] for w in rtl], "max_font_size": max(round(float(w.get("size") or 0), 2) for w in group)})
    return groups


def candidate_records(records: list[dict], region_slug: str) -> list[dict]:
    result = [r for r in records if norm_latin(r.get("historical_region")) == REGION_MATCH[region_slug]]
    # Ouezzane is duplicated in the official Fès and Tanger bundles; direct
    # mapping reports both occurrences and never substitutes Fahs-Anjra.
    if region_slug == "fes-meknes":
        result += [r for r in records if r["source_2026_constituency_id"] == "ouezzane"]
    return result


def main() -> int:
    cross = json.loads(CROSS.read_text(encoding="utf-8"))
    pointer = json.loads(PTR.read_text(encoding="utf-8"))
    probe = json.loads((ROOT / pointer["latest_probe"]).read_text(encoding="utf-8"))
    records = cross["records"]
    variants: dict[str, set[str]] = {}
    for record in records:
        cid = record["source_2026_constituency_id"]
        variants[cid] = {norm_ar(record.get("name_ar")), norm_ar(record.get("name_ar_source_form")), norm_ar(record.get("name_ar_match_key"))} - {""}
        variants[cid].update(norm_ar(x) for x in DIRECT_ALIASES.get(cid, []))

    pages = []
    for doc in sorted(probe["pdf_hits"], key=lambda x: x["region_slug"]):
        region = doc["region_slug"]
        reader = PdfReader(str(ROOT / doc["pdf"]["raw_path"]))
        metadata_title = norm_ar((reader.metadata or {}).get("/Title"))
        candidates = candidate_records(records, region)
        with pdfplumber.open(str(ROOT / doc["pdf"]["raw_path"])) as pdf:
            for page_no, (pypage, plpage) in enumerate(zip(reader.pages, pdf.pages), 1):
                logical_lines = [norm_ar(x) for x in (pypage.extract_text() or "").splitlines() if norm_ar(x)]
                sources = [{"source": "PYPDF_LINE", "line_index": i, "text": line} for i, line in enumerate(logical_lines)]
                sources += spatial_top_groups(plpage)
                if page_no == 1 and metadata_title:
                    sources.append({"source": "PDF_METADATA_TITLE_PAGE1", "text": metadata_title})
                hits = []
                for record in candidates:
                    cid = record["source_2026_constituency_id"]
                    for source in sources:
                        sc = compact(source.get("text"))
                        for variant in variants[cid]:
                            vc = compact(variant)
                            if not sc or not vc:
                                continue
                            exact = sc == vc
                            contained = vc in sc or sc in vc
                            # Short forms are accepted only when explicitly listed
                            # for that CID; generic canonical partials are not.
                            explicit_alias = variant in {norm_ar(x) for x in DIRECT_ALIASES.get(cid, [])}
                            if exact or (explicit_alias and contained and min(len(sc), len(vc)) >= 4):
                                hits.append({"constituency_id": cid, "historical_constituency": record["historical_constituency"], "historical_seats_2016": int(record["historical_seats_2016"]), "variant": variant, "exact": exact, "source": source})
                by_cid: dict[str, list[dict]] = defaultdict(list)
                for hit in hits:
                    by_cid[hit["constituency_id"]].append(hit)
                if len(by_cid) == 1:
                    cid = next(iter(by_cid))
                    best = sorted(by_cid[cid], key=lambda h: (not h["exact"], h["source"].get("source") != "PDFPLUMBER_TOP_GROUP", len(h["variant"])), reverse=False)[0]
                    status = "DIRECT_EXACT_PAGE_IDENTITY"
                    assignment = {"constituency_id": cid, "historical_constituency": best["historical_constituency"], "historical_seats_2016": best["historical_seats_2016"], "method": status, "evidence": best}
                else:
                    assignment = None
                    status = "UNRESOLVED_NO_DIRECT_TITLE" if not by_cid else "AMBIGUOUS_MULTIPLE_DIRECT_TITLES"
                pages.append({"region": region, "page": page_no, "pdf_sha256": doc["sha256"], "status": status, "assignment": assignment, "direct_hits_by_constituency": by_cid, "pypdf_lines": logical_lines[:24], "spatial_top_groups": [x for x in sources if x["source"] == "PDFPLUMBER_TOP_GROUP"], "metadata_title_page1": metadata_title if page_no == 1 else None})

    resolved = [p for p in pages if p["assignment"]]
    counts_by_cid = defaultdict(int)
    for page in resolved:
        counts_by_cid[page["assignment"]["constituency_id"]] += 1
    duplicates = [{"constituency_id": cid, "direct_page_count": n, "pages": [{"region": p["region"], "page": p["page"]} for p in resolved if p["assignment"]["constituency_id"] == cid]} for cid, n in counts_by_cid.items() if n > 1]
    payload = {"schema_version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "status": "PASS_PARTIAL_DIRECT_PAGE_IDENTITY", "counts": {"pdf_pages": len(pages), "directly_resolved_pages": len(resolved), "unique_direct_constituency_ids": len(counts_by_cid), "unresolved_pages": sum(not p["assignment"] for p in pages), "duplicate_direct_constituency_ids": len(duplicates)}, "duplicate_direct_titles": duplicates, "pages": pages, "invariants": {"remainder_bijection_used": False, "candidate_facts_generated": False, "outcomes_unsealed": False, "predictive_judgments_generated": False, "F1_created": False}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "direct_map.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "duplicates": duplicates, "new_alias_resolutions": [{"region": p["region"], "page": p["page"], "cid": p["assignment"]["constituency_id"], "source": p["assignment"]["evidence"]["source"]} for p in resolved if p["assignment"]["evidence"]["variant"] in {norm_ar(x) for xs in DIRECT_ALIASES.values() for x in xs}]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
