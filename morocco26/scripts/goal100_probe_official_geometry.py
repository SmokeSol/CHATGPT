#!/usr/bin/env python3
"""Probe authoritative Moroccan sources for the current electoral geometry.

This is an evidence-acquisition step, not a geometry certificate. It records raw
source hashes, links and extractability so the row-by-row legal diff can be built
without silently treating a secondary table as current law.
"""
from __future__ import annotations

import hashlib
import io
import json
import re
import unicodedata
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "data" / "goal100" / "geometry_sources"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = ROOT / "data" / "goal100" / "geometry_official_probe.json"

PAGES = [
    {
        "role": "current_election_law_index",
        "url": "https://www.chambredesrepresentants.ma/ar/%D8%A7%D9%84%D9%82%D9%88%D8%A7%D9%86%D9%8A%D9%86-%D8%A7%D9%84%D9%85%D8%AA%D8%B9%D9%84%D9%82%D8%A9-%D8%A8%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D8%A7%D8%AA",
    },
    {
        "role": "consolidated_organic_law_27_11",
        "url": "https://www.sgg.gov.ma/Portals/1/textesconsolides/27_11.pdf",
    },
    {
        "role": "organic_law_53_25",
        "url": "https://www.sgg.gov.ma/Portals/1/lois/Loi_organique_53.25_ar.pdf",
    },
]

NEEDLES = [
    "2.11.603",
    "211603",
    "circonscription",
    "circonscriptions",
    "دوائر",
    "الدائرة",
    "الدوائر",
    "الانتخابية",
]


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pdf_text(data: bytes) -> dict:
    try:
        reader = PdfReader(io.BytesIO(data))
        pages = []
        for i, page in enumerate(reader.pages):
            try:
                text = page.extract_text() or ""
            except Exception as exc:  # preserve extraction failures per page
                text = f"[EXTRACTION_ERROR {exc!r}]"
            pages.append(text)
        joined = "\n\n".join(pages)
        return {
            "pages": len(reader.pages),
            "extracted_chars": len(joined),
            "text_sha256": sha(joined.encode("utf-8")),
            "contains_decree_number": "2.11.603" in joined or "211603" in norm(joined),
            "head": joined[:5000],
        }
    except Exception as exc:
        return {"error": repr(exc), "pages": None, "extracted_chars": 0}


def main() -> None:
    session = requests.Session()
    session.headers.update({"User-Agent": "MOROCCO26-research/3.0 (aggregate election research)"})
    report = {
        "schema_version": "1.0",
        "probe_id": "M26-GOAL100-GEOMETRY-OFFICIAL-PROBE-V1",
        "purpose": "locate and hash authoritative current-law geometry sources before row-by-row certification",
        "pages": [],
        "candidate_documents": [],
        "gate": "PROBE_ONLY_NOT_GEOMETRY_CERTIFICATE",
    }
    seen_candidates = set()

    for spec in PAGES:
        url = spec["url"]
        item = {"role": spec["role"], "url": url}
        try:
            r = session.get(url, timeout=45, allow_redirects=True)
            item.update({
                "status": r.status_code,
                "final_url": r.url,
                "content_type": r.headers.get("content-type"),
                "bytes": len(r.content),
                "sha256": sha(r.content),
            })
            if r.status_code != 200:
                item["error"] = f"HTTP {r.status_code}"
                report["pages"].append(item)
                continue
            ctype = (r.headers.get("content-type") or "").lower()
            if r.content[:4] == b"%PDF" or "pdf" in ctype:
                filename = f"{spec['role']}.pdf"
                (OUT_DIR / filename).write_bytes(r.content)
                item["saved_path"] = str((OUT_DIR / filename).relative_to(ROOT))
                item["pdf"] = pdf_text(r.content)
            else:
                text = r.text
                item["html_chars"] = len(text)
                item["contains_decree_number"] = "2.11.603" in text or "211603" in norm(text)
                soup = BeautifulSoup(text, "html.parser")
                links = []
                for a in soup.find_all("a", href=True):
                    href = urljoin(r.url, a.get("href"))
                    label = " ".join(a.get_text(" ", strip=True).split())
                    links.append({"label": label, "url": href})
                    haystack = f"{label} {href}".lower()
                    if any(n.lower() in haystack for n in NEEDLES):
                        if href not in seen_candidates:
                            seen_candidates.add(href)
                            report["candidate_documents"].append({
                                "discovered_from": r.url,
                                "label": label,
                                "url": href,
                            })
                item["link_count"] = len(links)
                item["candidate_link_count"] = sum(1 for x in report["candidate_documents"] if x["discovered_from"] == r.url)
                item["matching_text_fragments"] = [
                    s.strip()[:500]
                    for s in soup.stripped_strings
                    if any(n.lower() in s.lower() for n in NEEDLES)
                ][:50]
            report["pages"].append(item)
        except Exception as exc:
            item["error"] = repr(exc)
            report["pages"].append(item)

    # Fetch every discovered official candidate and retain immutable bytes.
    for i, candidate in enumerate(report["candidate_documents"]):
        try:
            r = session.get(candidate["url"], timeout=45, allow_redirects=True)
            candidate.update({
                "status": r.status_code,
                "final_url": r.url,
                "content_type": r.headers.get("content-type"),
                "bytes": len(r.content),
                "sha256": sha(r.content),
            })
            if r.status_code == 200:
                ext = ".pdf" if r.content[:4] == b"%PDF" or "pdf" in (r.headers.get("content-type") or "").lower() else ".bin"
                path = OUT_DIR / f"candidate_{i:02d}{ext}"
                path.write_bytes(r.content)
                candidate["saved_path"] = str(path.relative_to(ROOT))
                if ext == ".pdf":
                    candidate["pdf"] = pdf_text(r.content)
        except Exception as exc:
            candidate["error"] = repr(exc)

    report["summary"] = {
        "source_pages_ok": sum(p.get("status") == 200 for p in report["pages"]),
        "source_pages_total": len(report["pages"]),
        "candidate_documents": len(report["candidate_documents"]),
        "downloaded_candidates": sum(c.get("status") == 200 for c in report["candidate_documents"]),
        "candidates_with_extractable_pdf_text": sum((c.get("pdf") or {}).get("extracted_chars", 0) > 100 for c in report["candidate_documents"]),
        "decree_number_found_in_index_or_candidate": any(
            p.get("contains_decree_number") or (p.get("pdf") or {}).get("contains_decree_number")
            for p in report["pages"]
        ) or any((c.get("pdf") or {}).get("contains_decree_number") for c in report["candidate_documents"]),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
