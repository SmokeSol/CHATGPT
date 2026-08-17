#!/usr/bin/env python3
"""Discover 2016 Medias24 election-map addresses without contaminating E_reason.

The live/current Medias24 CMS is used only as an address-discovery oracle. No
candidate fact from a current response is admissible evidence. A discovered
map becomes historical evidence only when a Wayback snapshot exists at or
before the preregistered 2016 cutoff.
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
ARTICLE_SLUG = "legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes"
ARTICLE = f"https://medias24.com/2016/10/03/{ARTICLE_SLUG}/"
S = requests.Session()
S.headers.update({
    "User-Agent": "Mozilla/5.0 Atlas395-EReason-AddressDiscovery/2.0",
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


def archive_current(body: bytes, suffix: str = ".bin") -> str:
    digest = sha(body)
    path = RAW_CURRENT / f"{digest}{suffix}"
    if not path.exists():
        path.write_bytes(body)
    return str(path.relative_to(ROOT))


def normalize_asset(value: str, base: str) -> str | None:
    value = value.replace("\\/", "/").replace("&amp;", "&").strip().rstrip(")],.;\\")
    if value.startswith("//"):
        value = "https:" + value
    value = urljoin(base, value)
    parsed = urlparse(value)
    host = (parsed.hostname or "").lower()
    if host != "assets.medias24.com":
        return None
    # Fragments are irrelevant to archived object identity.
    return urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, parsed.params, parsed.query, ""))


def extract_assets(text: str, base: str) -> set[str]:
    text = text.replace("\\/", "/")
    found: set[str] = set()
    try:
        soup = BeautifulSoup(text, "html.parser")
        for node in soup.find_all(["iframe", "script", "link", "a"]):
            for attr in ("src", "data-src", "data-lazy-src", "href"):
                value = node.get(attr)
                if value:
                    asset = normalize_asset(str(value), base)
                    if asset:
                        found.add(asset)
    except Exception:
        pass
    patterns = [
        r"https?://assets\.medias24\.com/[^\s\"'<>]+",
        r"//assets\.medias24\.com/[^\s\"'<>]+",
        r"(?:src|data-src|data-lazy-src)=[\"']([^\"']+)[\"']",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, flags=re.I):
            value = match.group(1) if match.lastindex else match.group(0)
            asset = normalize_asset(value, base)
            if asset:
                found.add(asset)
    return found


def current_discovery() -> tuple[set[str], list[dict[str, Any]]]:
    """Use current CMS only to recover historical-looking asset addresses."""
    assets: set[str] = set()
    rows: list[dict[str, Any]] = []
    queue: list[tuple[str, str]] = [
        (ARTICLE, "LIVE_ARTICLE_ADDRESS_ONLY"),
        (f"https://medias24.com/wp-json/wp/v2/posts?slug={ARTICLE_SLUG}&per_page=10", "WP_EXACT_SLUG"),
        (f"https://medias24.com/?rest_route=/wp/v2/posts&slug={ARTICLE_SLUG}&per_page=10", "WP_EXACT_SLUG_ROUTE"),
        ("https://medias24.com/wp-json/wp/v2/search?search=legislatives%20principaux%20candidats%2017%20cartes&per_page=100", "WP_SEARCH"),
        ("https://medias24.com/wp-json/wp/v2/search?search=legislatives%20carte%20interactive&per_page=100", "WP_SEARCH"),
        ("https://medias24.com/?rest_route=/wp/v2/search&search=legislatives%20carte%20interactive&per_page=100", "WP_SEARCH_ROUTE"),
    ]
    seen: set[str] = set()
    post_ids: set[int] = set()
    while queue:
        url, origin = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        rec: dict[str, Any] = {"url": url, "origin": origin, "status": None, "bytes": 0, "sha256": None, "archive_path": None, "assets": [], "post_ids": [], "error": None, "admissible_candidate_evidence": False}
        try:
            r = get_retry(url, timeout=(8, 35), attempts=3)
            body = r.content
            rec.update(status=r.status_code, bytes=len(body), sha256=sha(body) if body else None)
            if body:
                suffix = ".json" if "json" in (r.headers.get("content-type") or "").lower() else ".html"
                rec["archive_path"] = archive_current(body, suffix)
            text = body.decode("utf-8", errors="replace")
            discovered = extract_assets(text, str(r.url))
            assets.update(discovered)
            rec["assets"] = sorted(discovered)
            if r.ok:
                try:
                    payload = r.json()
                    objects = payload if isinstance(payload, list) else [payload]
                    for obj in objects:
                        if isinstance(obj, dict) and isinstance(obj.get("id"), int):
                            pid = int(obj["id"])
                            post_ids.add(pid)
                            rec["post_ids"].append(pid)
                except Exception:
                    pass
        except Exception as exc:
            rec["error"] = f"{type(exc).__name__}: {exc}"
        rows.append(rec)
    for pid in sorted(post_ids):
        for url, origin in [
            (f"https://medias24.com/wp-json/wp/v2/posts/{pid}?context=view", "WP_POST_BY_ID"),
            (f"https://medias24.com/?rest_route=/wp/v2/posts/{pid}&context=view", "WP_POST_BY_ID_ROUTE"),
        ]:
            rec = {"url": url, "origin": origin, "status": None, "bytes": 0, "sha256": None, "archive_path": None, "assets": [], "post_ids": [pid], "error": None, "admissible_candidate_evidence": False}
            try:
                r = get_retry(url, timeout=(8, 35), attempts=3)
                body = r.content
                rec.update(status=r.status_code, bytes=len(body), sha256=sha(body) if body else None)
                if body:
                    rec["archive_path"] = archive_current(body, ".json")
                discovered = extract_assets(body.decode("utf-8", errors="replace"), str(r.url))
                assets.update(discovered)
                rec["assets"] = sorted(discovered)
            except Exception as exc:
                rec["error"] = f"{type(exc).__name__}: {exc}"
            rows.append(rec)
    return assets, rows


def cdx_exact(url: str) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    variants = []
    parsed = urlparse(url)
    clean = urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, parsed.params, parsed.query, ""))
    noquery = urlunparse((parsed.scheme or "https", parsed.netloc, parsed.path, parsed.params, "", ""))
    for candidate in (clean, noquery, clean.replace("https://", "http://", 1), noquery.replace("https://", "http://", 1)):
        if candidate not in variants:
            variants.append(candidate)
    diagnostics: list[dict[str, Any]] = []
    collected: dict[tuple[str, str], dict[str, str]] = {}
    for candidate in variants:
        params = {"url": candidate, "output": "json", "fl": "timestamp,original,statuscode,mimetype,digest", "filter": "statuscode:200", "to": "20161006", "limit": "200", "collapse": "digest"}
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


def main() -> int:
    assets, current_rows = current_discovery()
    archive_rows: list[dict[str, Any]] = []
    for asset in sorted(assets):
        # Prioritize plausible election-map objects; still retain all addresses in diagnostics.
        low = asset.lower()
        plausible = any(token in low for token in ("carte", "election", "legisl", "candidat", "map"))
        rec: dict[str, Any] = {"asset_url": asset, "plausible_map": plausible, "cdx_rows": [], "cdx_diagnostics": [], "selected_snapshot": None, "snapshot_status": None, "snapshot_bytes": 0, "snapshot_sha256": None, "snapshot_path": None, "error": None, "admissible_candidate_evidence": False}
        if plausible:
            rows, diagnostics = cdx_exact(asset)
            rec["cdx_rows"] = rows
            rec["cdx_diagnostics"] = diagnostics
            if rows:
                snap = rows[0]
                rec["selected_snapshot"] = snap
                archive_url = f"https://web.archive.org/web/{snap['timestamp']}id_/{snap['original']}"
                try:
                    r = get_retry(archive_url, timeout=(10, 70), attempts=4)
                    body = r.content
                    rec.update(snapshot_status=r.status_code, snapshot_bytes=len(body), snapshot_sha256=sha(body) if body else None)
                    if r.ok and body:
                        suffix = Path(urlparse(snap["original"]).path).suffix.lower()
                        if suffix not in {".html", ".htm", ".json", ".js", ".css", ".csv", ".txt"}:
                            suffix = ".html"
                        path = RAW_ARCHIVE / f"{sha(body)}{suffix}"
                        path.write_bytes(body)
                        rec["snapshot_path"] = str(path.relative_to(ROOT))
                        rec["admissible_candidate_evidence"] = snap["timestamp"] <= CUTOFF
                except Exception as exc:
                    rec["error"] = f"{type(exc).__name__}: {exc}"
        archive_rows.append(rec)

    admissible = [x for x in archive_rows if x["admissible_candidate_evidence"]]
    manifest = {
        "schema_version": "2.0",
        "run_id": RUN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cutoff_utc": CUTOFF,
        "method": "CURRENT_CMS_FOR_ADDRESS_DISCOVERY_ONLY_THEN_PRE_CUTOFF_WAYBACK",
        "current_sources_are_candidate_evidence": False,
        "current_discovery_rows": current_rows,
        "discovered_asset_urls": sorted(assets),
        "archive_rows": archive_rows,
        "admissible_precutoff_snapshot_count": len(admissible),
        "admissible_precutoff_assets": [x["asset_url"] for x in admissible],
        "predictive_judgments_generated": False,
        "forecast_delta_generated": False,
        "F1_created": False,
    }
    (OUT / "discovery.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ER / "iframe_discovery_latest.json").write_text(json.dumps({"latest_run_id": RUN_ID, "latest_manifest": str((OUT / "discovery.json").relative_to(ROOT))}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"run_id": RUN_ID, "discovered_assets": len(assets), "plausible_maps": sum(x["plausible_map"] for x in archive_rows), "admissible_precutoff_snapshots": len(admissible), "admissible_assets": [x["asset_url"] for x in admissible]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
