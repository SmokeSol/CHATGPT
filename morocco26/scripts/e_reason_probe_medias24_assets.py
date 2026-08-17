#!/usr/bin/env python3
"""Targeted probe of Médias24 2016/2021 election iframe assets.

Discovery/provenance only. No predictive judgment, output delta or Atlas write.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26" / "data" / "goal100" / "e_reason"
RUN_ID = os.environ.get("E_REASON_ASSET_RUN_ID") or "medias24_asset_probe_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
RUN_DIR = ER / "evidence" / "asset_probes" / RUN_ID
RAW = RUN_DIR / "raw"
MAX_FETCHES = int(os.environ.get("E_REASON_ASSET_MAX_FETCHES", "240"))
MAX_BYTES = 8_000_000
TIMEOUT = (8, 22)
UA = "Mozilla/5.0 Atlas395-EReasonAssetProbe/1.0"

CUTOFF_UTC = {2016: datetime(2016, 10, 6, 22, 59, 59, tzinfo=timezone.utc), 2021: datetime(2021, 9, 7, 22, 59, 59, tzinfo=timezone.utc)}

CITY = ["casa", "fes", "marrakech", "sale", "rabat"]
REGION = [
    "rabat-sale-kenitra", "Beni-Mellal-Khenifra", "Casablanca-Settat",
    "dakhla-oued-ed-dahab", "draa-tafilalet", "fes-meknes",
    "laayoune-sakia-hamra", "Marrakech-Safi", "guelmim-oued-noun",
    "oriental", "Souss-Massa", "tanger-tetouan-houceima",
]

# Exact 2021 URLs extracted from the pre-election Médias24 article.
SEEDS: list[tuple[int, str, str]] = []
for city in CITY:
    SEEDS.append((2021, f"https://assets.medias24.com/js/carte/election2021/villes/{city}/index.html", "EXACT_ARTICLE_IFRAME"))
for region in REGION:
    SEEDS.append((2021, f"https://assets.medias24.com/js/carte/election2021/region/{region}/index.html", "EXACT_ARTICLE_IFRAME"))

# 2016 page states the same 17-map layout. Probe several deterministic path variants;
# candidates become evidence only after a successful response and provenance audit.
for city in CITY:
    for root in ("election2016", "elections2016", "legislatives2016", "election"):
        SEEDS.append((2016, f"https://assets.medias24.com/js/carte/{root}/villes/{city}/index.html", "PATH_PROBE"))
for region in REGION:
    for root in ("election2016", "elections2016", "legislatives2016", "election"):
        SEEDS.append((2016, f"https://assets.medias24.com/js/carte/{root}/region/{region}/index.html", "PATH_PROBE"))

# WordPress/API discovery probes can expose the historical iframe src attributes.
SLUGS = {
    2016: "legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes",
    2021: "legislatives-voici-la-liste-des-principaux-candidats-circonscription-par-circonscription",
}
for year, slug in SLUGS.items():
    SEEDS.extend([
        (year, f"https://medias24.com/wp-json/wp/v2/posts?slug={slug}", "WP_API_PROBE"),
        (year, f"https://medias24.com/wp-json/wp/v2/search?search={slug}", "WP_API_PROBE"),
        (year, f"https://medias24.com/?rest_route=/wp/v2/posts&slug={slug}", "WP_API_PROBE"),
    ])

ALLOWED = {"assets.medias24.com", "medias24.com", "www.medias24.com"}
STATIC_SUFFIXES = {".html", ".htm", ".js", ".css", ".json", ".csv", ".xml", ".txt", ".db", ".sqlite", ".geojson"}


@dataclass
class Row:
    year: int
    url: str
    final_url: str | None
    parent: str | None
    origin: str
    depth: int
    status: int | None
    content_type: str | None
    size: int
    sha256: str | None
    etag: str | None
    last_modified: str | None
    last_modified_before_cutoff: bool | None
    archive_path: str | None
    discovered: list[str]
    error: str | None


def canonical(url: str, base: str | None = None) -> str:
    if base:
        url = urljoin(base, url)
    return urldefrag(url)[0].strip()


def content_suffix(url: str, ctype: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in STATIC_SUFFIXES:
        return suffix
    c = (ctype or "").lower()
    if "html" in c: return ".html"
    if "javascript" in c: return ".js"
    if "json" in c: return ".json"
    if "css" in c: return ".css"
    return ".bin"


def extract_urls(body: bytes, url: str, ctype: str | None) -> list[str]:
    c = (ctype or "").lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    if not ("text" in c or "json" in c or "javascript" in c or suffix in STATIC_SUFFIXES):
        return []
    text = body.decode("utf-8", errors="replace")
    found: set[str] = set()
    if "html" in c or suffix in {".html", ".htm", ""}:
        soup = BeautifulSoup(text, "html.parser")
        for tag, attr in (("script", "src"), ("link", "href"), ("iframe", "src"), ("a", "href")):
            for node in soup.find_all(tag):
                value = node.get(attr)
                if value:
                    found.add(canonical(value, url))
    for pattern in (
        r"[\"']([^\"']+\.(?:js|css|json|csv|xml|txt|db|sqlite|geojson)(?:\?[^\"']*)?)[\"']",
        r"(?:fetch|open)\s*\(\s*[\"']([^\"']+)[\"']",
        r"https?://[^\s\"'<>]+",
    ):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            candidate = match.group(1) if match.lastindex else match.group(0)
            found.add(canonical(candidate.rstrip(")],.;"), url))
    out = []
    for child in sorted(found):
        if not child.startswith(("http://", "https://")):
            continue
        if (urlparse(child).hostname or "").lower() not in ALLOWED:
            continue
        if (urlparse(child).hostname or "").lower() == "assets.medias24.com" or "wp-json" in child or "rest_route" in child:
            out.append(child)
    return out


def read_body(response: requests.Response) -> bytes:
    parts = []
    total = 0
    for chunk in response.iter_content(65536):
        if not chunk: continue
        parts.append(chunk)
        total += len(chunk)
        if total > MAX_BYTES: break
    return b"".join(parts)


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    RAW.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept": "*/*", "Accept-Language": "fr,ar;q=0.9,en;q=0.6"})
    queue = deque((year, url, None, origin, 0) for year, url, origin in SEEDS)
    seen: set[tuple[int, str]] = set()
    rows: list[Row] = []
    while queue and len(rows) < MAX_FETCHES:
        year, url, parent, origin, depth = queue.popleft()
        url = canonical(url)
        if (year, url) in seen:
            continue
        seen.add((year, url))
        try:
            response = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
            body = read_body(response)
            ctype = response.headers.get("content-type", "").split(";")[0].strip()
            digest = hashlib.sha256(body).hexdigest() if body else None
            archive_path = None
            if response.ok and body:
                suffix = content_suffix(str(response.url), ctype)
                path = RAW / f"{digest}{suffix}"
                path.write_bytes(body)
                archive_path = str(path.relative_to(ROOT))
            children = extract_urls(body, str(response.url), ctype) if response.ok and body else []
            if depth < 2:
                for child in children:
                    if (year, child) not in seen:
                        queue.append((year, child, url, "DISCOVERED_ASSET", depth + 1))
            lm = response.headers.get("last-modified")
            before = None
            if lm:
                try:
                    before = parsedate_to_datetime(lm).astimezone(timezone.utc) <= CUTOFF_UTC[year]
                except Exception:
                    before = None
            rows.append(Row(year, url, str(response.url), parent, origin, depth, response.status_code, ctype, len(body), digest, response.headers.get("etag"), lm, before, archive_path, children, None))
        except Exception as exc:
            rows.append(Row(year, url, None, parent, origin, depth, None, None, 0, None, None, None, None, None, [], f"{type(exc).__name__}: {exc}"))

    payload = [asdict(x) for x in rows]
    (RUN_DIR / "asset_probe.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    success = [x for x in payload if x["status"] is not None and x["status"] < 400 and x["size"] > 0]
    exact_2021 = [x for x in success if x["year"] == 2021 and x["origin"] == "EXACT_ARTICLE_IFRAME"]
    found_2016_roots = sorted({x["url"] for x in success if x["year"] == 2016 and x["origin"] == "PATH_PROBE"})
    static_assets = [x for x in success if x["origin"] == "DISCOVERED_ASSET"]
    summary = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "fetch_rows": len(payload),
        "successful_rows": len(success),
        "exact_2021_iframes_successful": len(exact_2021),
        "found_2016_root_count": len(found_2016_roots),
        "found_2016_roots": found_2016_roots,
        "discovered_static_assets_successful": len(static_assets),
        "last_modified_pre_cutoff_assets": sum(x["last_modified_before_cutoff"] is True for x in success),
        "predictive_judgments_generated": False,
        "forecast_delta_generated": False,
        "F1_created": False,
        "Atlas_UI_modified": False,
    }
    (RUN_DIR / "run_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (ER / "medias24_asset_probe_latest.json").write_text(json.dumps({
        "schema_version": "1.0",
        "latest_run_id": RUN_ID,
        "latest_run_manifest": str((RUN_DIR / "run_manifest.json").relative_to(ROOT)),
        "latest_probe": str((RUN_DIR / "asset_probe.json").relative_to(ROOT)),
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
