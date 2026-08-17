#!/usr/bin/env python3
"""Recover 2016 Medias24 election-map addresses without contaminating E_reason.

Current WordPress responses are discovery metadata only. They may reveal legacy
GUIDs/hostnames but NEVER supply candidate facts. Candidate/map content becomes
admissible only after an independently timestamped Wayback capture at or before
the preregistered 2016 cutoff.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
RUN_ID = os.environ.get("E_REASON_IFRAME_RUN_ID") or "iframe_discovery_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ER / "evidence/iframe_discovery" / RUN_ID
RAW_CURRENT = OUT / "current_discovery_only"
RAW_ARCHIVE = OUT / "precutoff_archive"
OUT.mkdir(parents=True, exist_ok=False)
RAW_CURRENT.mkdir(parents=True, exist_ok=True)
RAW_ARCHIVE.mkdir(parents=True, exist_ok=True)

CUTOFF = "20161006225959"
CUTOFF_ISO = "2016-10-06T22:59:59"
ARTICLE_SLUG = "legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes"
ARTICLE = f"https://medias24.com/2016/10/03/{ARTICLE_SLUG}/"
S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 Atlas395-EReason-LegacyGUIDRecovery/3.0",
    "Accept": "*/*",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.5",
})


def get_retry(url: str, *, params: dict[str, Any] | None = None, timeout=(8, 40), attempts: int = 4) -> requests.Response:
    last: Exception | None = None
    for attempt in range(attempts):
        try:
            r = S.get(url, params=params, timeout=timeout, allow_redirects=True)
            if r.status_code not in {429, 500, 502, 503, 504}:
                return r
            last = requests.HTTPError(f"retryable HTTP {r.status_code}")
        except (requests.ConnectTimeout, requests.ReadTimeout, requests.ConnectionError) as exc:
            last = exc
        if attempt + 1 < attempts:
            time.sleep(min(8, 2 ** attempt))
    if last:
        raise last
    raise RuntimeError("request failed without response")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def archive_bytes(body: bytes, directory: Path, suffix: str) -> str:
    digest = sha(body)
    path = directory / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(body)
    return str(path.relative_to(ROOT))


def clean_url(value: str, base: str | None = None) -> str | None:
    value = html.unescape(value.replace("\\/", "/")).strip().rstrip(")],.;\\")
    if value.startswith("//"):
        value = "https:" + value
    if base:
        value = urljoin(base, value)
    if not value.startswith(("http://", "https://")):
        return None
    p = urlparse(value)
    if not p.hostname:
        return None
    return urlunparse((p.scheme, p.netloc, p.path, p.params, p.query, ""))


def extract_iframe_urls(text: str, base: str) -> set[str]:
    """Extract iframe-like targets regardless of hosting provider."""
    text = html.unescape(text.replace("\\/", "/"))
    found: set[str] = set()
    try:
        soup = BeautifulSoup(text, "html.parser")
        for node in soup.find_all("iframe"):
            for attr in ("src", "data-src", "data-lazy-src"):
                value = node.get(attr)
                if value:
                    u = clean_url(str(value), base)
                    if u:
                        found.add(u)
    except Exception:
        pass
    for pattern in (
        r"(?:iframe[^>]+?(?:src|data-src|data-lazy-src)|(?:src|data-src|data-lazy-src))\s*=\s*[\"']([^\"']+)[\"']",
        r"https?://[^\s\"'<>]+",
        r"//[^\s\"'<>]+",
    ):
        for m in re.finditer(pattern, text, flags=re.I):
            raw = m.group(1) if m.lastindex else m.group(0)
            u = clean_url(raw, base)
            if not u:
                continue
            low = u.lower()
            # For free URLs, keep only strong map/embed signals. Actual iframe-tag
            # URLs above are retained unconditionally.
            if m.lastindex or any(t in low for t in ("carte", "map", "election", "legisl", "candidat", "embed", "iframe")):
                found.add(u)
    return found


def cdx_exact(url: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    p = urlparse(url)
    clean = urlunparse((p.scheme or "https", p.netloc, p.path, p.params, p.query, ""))
    noquery = urlunparse((p.scheme or "https", p.netloc, p.path, p.params, "", ""))
    variants: list[str] = []
    for candidate in (clean, noquery, clean.replace("https://", "http://", 1), noquery.replace("https://", "http://", 1)):
        if candidate not in variants:
            variants.append(candidate)
    diagnostics: list[dict[str, Any]] = []
    collected: dict[tuple[str, str], dict[str, str]] = {}
    for candidate in variants:
        params = {
            "url": candidate, "output": "json",
            "fl": "timestamp,original,statuscode,mimetype,digest",
            "filter": "statuscode:200", "to": "20161006", "limit": "200",
            "collapse": "digest",
        }
        diag = {"query_url": candidate, "status": None, "bytes": 0, "rows": 0, "error": None}
        try:
            r = get_retry("https://web.archive.org/cdx/search/cdx", params=params, timeout=(10, 65), attempts=4)
            diag.update(status=r.status_code, bytes=len(r.content))
            r.raise_for_status()
            payload = r.json()
            if payload and len(payload) > 1:
                header = payload[0]
                for raw in payload[1:]:
                    item = dict(zip(header, raw))
                    if item.get("timestamp", "") <= CUTOFF:
                        collected[(item.get("original", ""), item.get("timestamp", ""))] = item
                diag["rows"] = len(payload) - 1
        except Exception as exc:
            diag["error"] = f"{type(exc).__name__}: {exc}"
        diagnostics.append(diag)
    rows = sorted(collected.values(), key=lambda x: x.get("timestamp", ""), reverse=True)
    return rows, diagnostics


def fetch_precutoff(url: str, origin: str) -> dict[str, Any]:
    rows, diagnostics = cdx_exact(url)
    rec: dict[str, Any] = {
        "url": url, "origin": origin, "cdx_rows": rows,
        "cdx_diagnostics": diagnostics, "selected_snapshot": None,
        "snapshot_status": None, "snapshot_bytes": 0, "snapshot_sha256": None,
        "snapshot_path": None, "embedded_urls": [], "error": None,
        "admissible_candidate_evidence": False,
    }
    if not rows:
        return rec
    snap = rows[0]
    rec["selected_snapshot"] = snap
    archive_url = f"https://web.archive.org/web/{snap['timestamp']}id_/{snap['original']}"
    try:
        r = get_retry(archive_url, timeout=(10, 70), attempts=4)
        body = r.content
        rec.update(snapshot_status=r.status_code, snapshot_bytes=len(body), snapshot_sha256=sha(body) if body else None)
        if r.ok and body:
            suffix = Path(urlparse(snap["original"]).path).suffix.lower()
            if suffix not in {".html", ".htm", ".json", ".js", ".css", ".csv", ".txt", ".xml"}:
                suffix = ".html"
            rec["snapshot_path"] = archive_bytes(body, RAW_ARCHIVE, suffix)
            rec["admissible_candidate_evidence"] = snap["timestamp"] <= CUTOFF
            rec["embedded_urls"] = sorted(extract_iframe_urls(body.decode("utf-8", errors="replace"), snap["original"]))
    except Exception as exc:
        rec["error"] = f"{type(exc).__name__}: {exc}"
    return rec


def current_discovery() -> tuple[set[str], list[dict[str, Any]]]:
    """Use current CMS strictly as an address/legacy-host discovery oracle."""
    legacy_pages: set[str] = set()
    rows: list[dict[str, Any]] = []
    queue: list[tuple[str, str]] = [
        (ARTICLE, "LIVE_ARTICLE_ADDRESS_ONLY"),
        (f"https://medias24.com/wp-json/wp/v2/posts?slug={ARTICLE_SLUG}&per_page=10", "WP_EXACT_SLUG"),
        ("https://medias24.com/wp-json/wp/v2/search?search=legislatives%20carte%20interactive&per_page=100", "WP_SEARCH"),
        ("https://medias24.com/wp-json/wp/v2/search?search=legislatives%20candidats%20rabat%20sale%20marrakech&per_page=100", "WP_SEARCH"),
    ]
    seen: set[str] = set()
    post_ids: set[int] = set()

    def consume_payload(payload: Any, rec: dict[str, Any]) -> None:
        objects = payload if isinstance(payload, list) else [payload]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            if isinstance(obj.get("id"), int):
                post_ids.add(int(obj["id"]))
                rec.setdefault("post_ids", []).append(int(obj["id"]))
            date_gmt = str(obj.get("date_gmt") or obj.get("date") or "")
            guid = obj.get("guid")
            guid_url = guid.get("rendered") if isinstance(guid, dict) else None
            if guid_url and (not date_gmt or date_gmt <= CUTOFF_ISO):
                u = clean_url(str(guid_url))
                if u:
                    legacy_pages.add(u)
                    rec.setdefault("legacy_guids", []).append(u)

    while queue:
        url, origin = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        rec: dict[str, Any] = {"url": url, "origin": origin, "status": None, "bytes": 0, "sha256": None, "archive_path": None, "post_ids": [], "legacy_guids": [], "error": None, "admissible_candidate_evidence": False}
        try:
            r = get_retry(url, timeout=(8, 40), attempts=3)
            body = r.content
            rec.update(status=r.status_code, bytes=len(body), sha256=sha(body) if body else None)
            if body:
                suffix = ".json" if "json" in (r.headers.get("content-type") or "").lower() else ".html"
                rec["archive_path"] = archive_bytes(body, RAW_CURRENT, suffix)
            if r.ok:
                try:
                    consume_payload(r.json(), rec)
                except Exception:
                    pass
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(rec)

    for pid in sorted(post_ids):
        url = f"https://medias24.com/wp-json/wp/v2/posts/{pid}?context=view"
        rec = {"url": url, "origin": "WP_POST_BY_ID", "status": None, "bytes": 0, "sha256": None, "archive_path": None, "post_ids": [pid], "legacy_guids": [], "error": None, "admissible_candidate_evidence": False}
        try:
            r = get_retry(url, timeout=(8, 40), attempts=3)
            body = r.content
            rec.update(status=r.status_code, bytes=len(body), sha256=sha(body) if body else None)
            if body:
                rec["archive_path"] = archive_bytes(body, RAW_CURRENT, ".json")
            if r.ok:
                consume_payload(r.json(), rec)
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(rec)
    return legacy_pages, rows


def main() -> int:
    legacy_pages, current_rows = current_discovery()
    # The known aggregate article's legacy GUID is valuable even if current CMS
    # search fails; this is address metadata observed in the archived diagnostic.
    legacy_pages.add(f"https://prod.medias24.push.ma/2016/10/03/{ARTICLE_SLUG}/")

    page_rows: list[dict[str, Any]] = []
    embedded: set[str] = set()
    for url in sorted(legacy_pages):
        rec = fetch_precutoff(url, "LEGACY_CMS_GUID")
        page_rows.append(rec)
        if rec["admissible_candidate_evidence"]:
            embedded.update(rec["embedded_urls"])

    embed_rows: list[dict[str, Any]] = []
    # Bounded: only addresses physically present in a pre-cutoff archived page.
    for url in sorted(embedded)[:200]:
        embed_rows.append(fetch_precutoff(url, "EMBED_FROM_PRE_CUTOFF_PAGE"))

    admissible_pages = [x for x in page_rows if x["admissible_candidate_evidence"]]
    admissible_embeds = [x for x in embed_rows if x["admissible_candidate_evidence"]]
    manifest = {
        "schema_version": "3.0",
        "run_id": RUN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff_utc": CUTOFF,
        "method": "CURRENT_CMS_LEGACY_GUID_DISCOVERY_THEN_PRE_CUTOFF_WAYBACK_RECURSION",
        "current_sources_are_candidate_evidence": False,
        "current_discovery_rows": current_rows,
        "legacy_page_urls": sorted(legacy_pages),
        "legacy_page_rows": page_rows,
        "embedded_urls_from_admissible_pages": sorted(embedded),
        "embedded_rows": embed_rows,
        "admissible_precutoff_page_count": len(admissible_pages),
        "admissible_precutoff_embed_count": len(admissible_embeds),
        "admissible_precutoff_pages": [x["url"] for x in admissible_pages],
        "admissible_precutoff_embeds": [x["url"] for x in admissible_embeds],
        "predictive_judgments_generated": False,
        "forecast_delta_generated": False,
        "F1_created": False,
    }
    (OUT / "discovery.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ER / "iframe_discovery_latest.json").write_text(json.dumps({"latest_run_id": RUN_ID, "latest_manifest": str((OUT / "discovery.json").relative_to(ROOT))}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "run_id": RUN_ID,
        "legacy_pages_discovered": len(legacy_pages),
        "admissible_precutoff_pages": len(admissible_pages),
        "embedded_urls_from_admissible_pages": len(embedded),
        "admissible_precutoff_embeds": len(admissible_embeds),
        "admissible_pages": [x["url"] for x in admissible_pages],
        "admissible_embeds": [x["url"] for x in admissible_embeds],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
