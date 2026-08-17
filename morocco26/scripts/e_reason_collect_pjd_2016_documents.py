#!/usr/bin/env python3
"""Recover official PJD 2016 local-candidate slate documents under E_reason policy.

Current pjd.ma pages/static files are discovery/mirror material only. A source
becomes pre-cutoff evidence only through a Wayback capture at or before the
frozen 2016 cutoff. The script is deliberately provenance-first: it archives
raw pages/PDFs and extracted text but does not generate predictive judgments.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
RID = os.environ.get("E_REASON_PJD2016_RUN_ID") or "pjd2016_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ER / "evidence/pjd_2016_documents" / RID
RAW = OUT / "raw"
TEXT = OUT / "text"
RAW.mkdir(parents=True, exist_ok=False)
TEXT.mkdir(parents=True, exist_ok=True)

CUTOFF = "20161006225959"
CDX = "https://web.archive.org/cdx/search/cdx"
S = requests.Session()
S.headers.update({"User-Agent": "Atlas395-EReason-PJD2016/1.0", "Accept": "*/*"})

# All are official PJD pages published before the frozen cutoff. Together the
# attachment names appear to partition the 2016 local-candidate slate corpus.
ARTICLES = [
    {
        "id": "RABAT_FES_MARRAKECH",
        "url": "https://www.pjd.ma/74975-38982.html",
        "published_at_source": "2016-09-15T06:00:00+01:00",
        "expected_attachment": "jht_lrbt_wfs_wmrksh.pdf",
    },
    {
        "id": "SOUTH_SOUSS_ORIENT",
        "url": "https://www.pjd.ma/74215-38568.html",
        "published_at_source": "2016-08-28T00:00:00+01:00",
        "expected_attachment": "mrshhw_jht_ljnwb_wsws_wlshrq.pdf",
    },
    {
        "id": "LIST_3",
        "url": "https://www.pjd.ma/74973-38983.html",
        "published_at_source": "2016-09-15T06:00:00+01:00",
        "expected_attachment": "ldf_3.pdf",
    },
]

REGISTRY = ER / "e_reason_source_registry_v1.json"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_retry(url: str, *, params: dict[str, Any] | None = None, timeout=(8, 45), attempts=5) -> requests.Response:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            r = S.get(url, params=params, timeout=timeout, allow_redirects=True)
            if r.status_code not in {408, 425, 429, 500, 502, 503, 504}:
                return r
            last = requests.HTTPError(f"retryable HTTP {r.status_code}")
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as exc:
            last = exc
        if attempt + 1 < attempts:
            time.sleep(min(10, 2 ** attempt))
    if last:
        raise last
    raise RuntimeError("request failed without response")


def freeze(body: bytes, suffix: str) -> str:
    h = digest(body)
    path = RAW / f"{h}{suffix}"
    if not path.exists():
        path.write_bytes(body)
    return str(path.relative_to(ROOT))


def cdx_query(url_pattern: str) -> tuple[list[dict[str, str]], dict[str, Any]]:
    params = {
        "url": url_pattern,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "from": "2016",
        "to": "20161006",
        "limit": "5000",
        "collapse": "digest",
    }
    diag: dict[str, Any] = {"url_pattern": url_pattern, "status": None, "bytes": 0, "rows": 0, "error": None}
    rows: list[dict[str, str]] = []
    try:
        r = get_retry(CDX, params=params, timeout=(10, 70), attempts=5)
        diag.update(status=r.status_code, bytes=len(r.content))
        r.raise_for_status()
        payload = r.json()
        if payload and len(payload) > 1:
            header = payload[0]
            for raw in payload[1:]:
                item = dict(zip(header, raw))
                if item.get("timestamp", "") <= CUTOFF:
                    rows.append(item)
        rows.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        diag["rows"] = len(rows)
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}: {exc}"
    return rows, diag


def archive_fetch(item: dict[str, str]) -> tuple[bytes, str, int]:
    u = f"https://web.archive.org/web/{item['timestamp']}id_/{item['original']}"
    r = get_retry(u, timeout=(10, 75), attempts=5)
    r.raise_for_status()
    return r.content, str(r.url), r.status_code


def pdf_links(body: bytes, base: str) -> list[str]:
    text = body.decode("utf-8", errors="replace").replace("\\/", "/")
    out: set[str] = set()
    try:
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a"):
            href = a.get("href")
            if href and ".pdf" in href.lower():
                out.add(urljoin(base, href))
    except Exception:
        pass
    for m in re.finditer(r"https?://[^\s\"'<>]+\.pdf(?:\?[^\s\"'<>]*)?", text, re.I):
        out.add(m.group(0).replace("&amp;", "&"))
    return sorted(out)


def extract_pdf_text(body: bytes, stem: str) -> tuple[str, str | None]:
    tmp = OUT / f".{stem}.pdf"
    try:
        tmp.write_bytes(body)
        reader = PdfReader(str(tmp))
        pages = []
        for i, page in enumerate(reader.pages):
            pages.append(f"--- PAGE {i+1} ---\n" + (page.extract_text() or ""))
        text = "\n".join(pages)
        p = TEXT / f"{stem}.txt"
        p.write_text(text, encoding="utf-8")
        return text, str(p.relative_to(ROOT))
    except Exception as exc:
        return "", f"ERROR:{type(exc).__name__}:{exc}"
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def filename_variants(name: str) -> list[str]:
    stem = name[:-4] if name.lower().endswith(".pdf") else name
    return [
        name,
        f"{stem}_0.pdf",
    ]


def current_mirror_candidates(article_url: str, name: str, body: bytes | None) -> list[str]:
    out: set[str] = set()
    if body:
        out.update(pdf_links(body, article_url))
    for n in filename_variants(name):
        for month in ("04", "05", "06"):
            out.add(f"https://www.pjd.ma/static/uploads/2022/{month}/{n}")
            out.add(f"https://pjd.ma/static/uploads/2022/{month}/{n}")
    return sorted(out)


def validate_registry() -> None:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    ok = any(x.get("domain") == "pjd.ma" and x.get("source_class") == "T1_OFFICIAL_PARTY" and x.get("qualification_status") == "QUALIFIED_BEFORE_EXTRACTION" for x in data.get("entries", []))
    if not ok:
        raise RuntimeError("pjd.ma is not pre-qualified in E_reason source registry")


def main() -> int:
    validate_registry()
    article_rows: list[dict[str, Any]] = []
    document_rows: list[dict[str, Any]] = []
    for spec in ARTICLES:
        expected = spec["expected_attachment"]
        row: dict[str, Any] = {
            **spec,
            "source_class": "T1_OFFICIAL_PARTY",
            "current_page": None,
            "cdx_diagnostics": [],
            "precutoff_article_snapshots": [],
            "selected_precutoff_article": None,
            "archived_pdf_links": [],
            "attachment_cdx_candidates": [],
            "current_mirror_candidates": [],
        }
        current_body: bytes | None = None
        try:
            r = get_retry(spec["url"], timeout=(8, 40), attempts=4)
            current_body = r.content
            row["current_page"] = {
                "status": r.status_code,
                "bytes": len(r.content),
                "sha256": digest(r.content) if r.content else None,
                "path": freeze(r.content, ".html") if r.content else None,
                "admissible_candidate_evidence": False,
            }
        except Exception as exc:
            row["current_page"] = {"error": f"{type(exc).__name__}: {exc}", "admissible_candidate_evidence": False}

        patterns = [spec["url"], spec["url"].replace("https://www.", "http://www."), spec["url"].replace("https://www.", "http://")]
        article_hits: dict[tuple[str, str], dict[str, str]] = {}
        for pattern in patterns:
            hits, diag = cdx_query(pattern)
            row["cdx_diagnostics"].append(diag)
            for hit in hits:
                article_hits[(hit.get("original", ""), hit.get("timestamp", ""))] = hit
        ordered = sorted(article_hits.values(), key=lambda x: x.get("timestamp", ""), reverse=True)
        row["precutoff_article_snapshots"] = ordered
        archived_links: set[str] = set()
        if ordered:
            chosen = ordered[0]
            try:
                body, final_url, status = archive_fetch(chosen)
                p = freeze(body, ".html")
                links = pdf_links(body, chosen["original"])
                archived_links.update(links)
                row["selected_precutoff_article"] = {
                    "snapshot": chosen,
                    "status": status,
                    "final_url": final_url,
                    "bytes": len(body),
                    "sha256": digest(body),
                    "path": p,
                    "pdf_links": links,
                    "expected_filename_present": expected.lower() in body.decode("utf-8", errors="replace").lower(),
                    "admissible_candidate_evidence": chosen["timestamp"] <= CUTOFF,
                }
            except Exception as exc:
                row["selected_precutoff_article"] = {"snapshot": chosen, "error": f"{type(exc).__name__}: {exc}"}
        row["archived_pdf_links"] = sorted(archived_links)

        # Search the archive by exact filename regardless of its historical directory.
        attachment_hits: dict[tuple[str, str], dict[str, str]] = {}
        filename_patterns = []
        for host in ("pjd.ma", "www.pjd.ma"):
            filename_patterns.extend([
                f"{host}/*{expected}",
                f"{host}/*{expected.replace('.pdf', '')}*",
            ])
        filename_patterns.extend(sorted(archived_links))
        for pattern in filename_patterns:
            hits, diag = cdx_query(pattern)
            row["cdx_diagnostics"].append(diag)
            for hit in hits:
                if hit.get("timestamp", "") <= CUTOFF:
                    attachment_hits[(hit.get("original", ""), hit.get("timestamp", ""))] = hit
        candidates = sorted(attachment_hits.values(), key=lambda x: x.get("timestamp", ""), reverse=True)
        row["attachment_cdx_candidates"] = candidates

        selected_doc = None
        for hit in candidates:
            try:
                body, final_url, status = archive_fetch(hit)
                if not body.startswith(b"%PDF"):
                    continue
                h = digest(body)
                raw_path = freeze(body, ".pdf")
                text, text_path = extract_pdf_text(body, h)
                selected_doc = {
                    "article_id": spec["id"],
                    "expected_attachment": expected,
                    "transport": "WAYBACK_PRE_CUTOFF",
                    "original_url": hit["original"],
                    "capture_timestamp": hit["timestamp"],
                    "status": status,
                    "final_url": final_url,
                    "bytes": len(body),
                    "sha256": h,
                    "raw_path": raw_path,
                    "text_path": text_path,
                    "text_chars": len(text),
                    "party_fact_status": "PARTY_ANNOUNCED",
                    "admissible_candidate_evidence": hit["timestamp"] <= CUTOFF,
                }
                document_rows.append(selected_doc)
                break
            except Exception:
                continue

        mirrors = current_mirror_candidates(spec["url"], expected, current_body)
        row["current_mirror_candidates"] = mirrors
        if selected_doc is None:
            for u in mirrors:
                try:
                    r = get_retry(u, timeout=(8, 50), attempts=3)
                    body = r.content
                    if not r.ok or not body.startswith(b"%PDF"):
                        continue
                    h = digest(body)
                    raw_path = freeze(body, ".pdf")
                    text, text_path = extract_pdf_text(body, h)
                    mirror = {
                        "article_id": spec["id"],
                        "expected_attachment": expected,
                        "transport": "CURRENT_STATIC_MIRROR_DISCOVERY_ONLY",
                        "url": u,
                        "status": r.status_code,
                        "bytes": len(body),
                        "sha256": h,
                        "raw_path": raw_path,
                        "text_path": text_path,
                        "text_chars": len(text),
                        "party_fact_status": "PARTY_ANNOUNCED_UNVERIFIED_MIRROR",
                        "admissible_candidate_evidence": False,
                    }
                    document_rows.append(mirror)
                    break
                except Exception:
                    continue
        article_rows.append(row)

    admissible = [x for x in document_rows if x.get("admissible_candidate_evidence")]
    mirrors = [x for x in document_rows if x.get("transport") == "CURRENT_STATIC_MIRROR_DISCOVERY_ONLY"]
    manifest = {
        "schema_version": "1.0",
        "run_id": RID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff_utc": CUTOFF,
        "source_class": "T1_OFFICIAL_PARTY",
        "qualified_domain": "pjd.ma",
        "articles": article_rows,
        "documents": document_rows,
        "admissible_precutoff_document_count": len(admissible),
        "mirror_only_document_count": len(mirrors),
        "admissible_article_ids": [x["article_id"] for x in admissible],
        "predictive_judgments_generated": False,
        "forecast_delta_generated": False,
        "outcomes_unsealed": False,
        "F1_created": False,
        "Atlas_UI_modified": False,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ER / "pjd_2016_documents_latest.json").write_text(json.dumps({
        "schema_version": "1.0",
        "latest_run_id": RID,
        "latest_manifest": str((OUT / "run_manifest.json").relative_to(ROOT)),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "run_id": RID,
        "admissible_precutoff_document_count": len(admissible),
        "mirror_only_document_count": len(mirrors),
        "documents": [{k: x.get(k) for k in ("article_id", "transport", "original_url", "url", "capture_timestamp", "bytes", "text_chars", "admissible_candidate_evidence")} for x in document_rows],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
