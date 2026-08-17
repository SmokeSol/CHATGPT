#!/usr/bin/env python3
"""Collect pre-election 2016/2021 evidence for E_reason V1.

This stage performs no predictive judgment and computes no forecast delta.
It prefers pre-cutoff Internet Archive captures, treats live pages as discovery
only unless an immutable pre-cutoff version is established, and records full
provenance and content hashes.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, quote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26" / "data" / "goal100" / "e_reason"
RUN_ID = os.environ.get("E_REASON_RUN_ID") or (
    "historical_collection_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
RUN_DIR = ER / "evidence" / "runs" / RUN_ID
RAW_DIR = RUN_DIR / "raw"
TEXT_DIR = RUN_DIR / "text"

TIMEOUT = (15, 55)
MAX_FETCHES = int(os.environ.get("E_REASON_MAX_FETCHES", "350"))
MAX_DEPTH = int(os.environ.get("E_REASON_MAX_DEPTH", "3"))
MAX_BYTES = int(os.environ.get("E_REASON_MAX_BYTES", "6000000"))
REQUEST_DELAY = float(os.environ.get("E_REASON_REQUEST_DELAY", "0.20"))
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 Atlas395-EReason/1.0"
)

ALLOWED_ORIGINAL_HOSTS = {
    "medias24.com",
    "www.medias24.com",
    "assets.medias24.com",
    "pjd.ma",
    "www.pjd.ma",
    "rni.ma",
    "www.rni.ma",
    "pam.ma",
    "www.pam.ma",
    "istiqlal.info",
    "www.istiqlal.info",
    "usfp.ma",
    "www.usfp.ma",
    "haraka.ma",
    "www.haraka.ma",
    "uc.ma",
    "www.uc.ma",
    "pps.ma",
    "www.pps.ma",
    "elections.ma",
    "www.elections.ma",
    "interieur.gov.ma",
    "www.interieur.gov.ma",
    "chambredesrepresentants.ma",
    "www.chambredesrepresentants.ma",
}
ARCHIVE_HOSTS = {"web.archive.org", "web.archive.org"}
ELECTION_MARKERS = (
    "election", "legislative", "candidat", "circonscription", "liste", "scrutin",
    "election2016", "election2021", "carte", "depute", "parlement",
)
ASSET_EXTENSIONS = {
    ".html", ".htm", ".json", ".geojson", ".csv", ".tsv", ".xml", ".txt",
    ".js", ".css", ".db", ".sqlite", ".pdf", ".jpg", ".jpeg", ".png", ".webp",
}

CUTOFFS = {
    2016: "20161006225959",  # 23:59:59 Morocco / 22:59:59 UTC
    2021: "20210907225959",
}


@dataclass
class Record:
    election: int
    original_url: str
    retrieval_url: str | None
    parent_url: str | None
    depth: int
    transport: str
    retrieved_at: str
    status_code: int | None
    content_type: str | None
    bytes: int
    sha256: str | None
    archive_timestamp: str | None
    archived_path: str | None
    text_path: str | None
    published_at: str | None
    modified_at: str | None
    admissibility: str
    source_class: str
    error: str | None
    discovered_urls: list[str]


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(url: str, base: str | None = None) -> str:
    if base:
        url = urljoin(base, url)
    url, _ = urldefrag(url)
    return url.strip()


def original_from_wayback(url: str) -> str:
    parsed = urlparse(url)
    if parsed.hostname != "web.archive.org":
        return url
    match = re.search(r"/web/\d+(?:[a-z_]+)?/(https?://.+)$", parsed.path + ("?" + parsed.query if parsed.query else ""))
    return match.group(1) if match else url


def allowed_original(url: str) -> bool:
    return (urlparse(original_from_wayback(url)).hostname or "").lower() in ALLOWED_ORIGINAL_HOSTS


def source_class(url: str) -> str:
    host = (urlparse(original_from_wayback(url)).hostname or "").lower()
    if host in {"medias24.com", "www.medias24.com", "assets.medias24.com"}:
        return "M24_MEDIAS24"
    if host.endswith(".gov.ma") or host in {"elections.ma", "www.elections.ma", "chambredesrepresentants.ma", "www.chambredesrepresentants.ma"}:
        return "T0_OFFICIAL_INSTITUTIONAL"
    return "T1_OFFICIAL_PARTY"


def relevant(url: str, election: int) -> bool:
    original = original_from_wayback(url)
    parsed = urlparse(original)
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_ORIGINAL_HOSTS:
        return False
    path = (parsed.path or "").lower()
    suffix = Path(path).suffix.lower()
    if host == "assets.medias24.com":
        return suffix in ASSET_EXTENSIONS or any(x in path for x in ELECTION_MARKERS)
    if str(election) in path:
        return True
    return any(x in path for x in ELECTION_MARKERS)


def metadata_and_text(body: bytes, url: str, ctype: str | None) -> tuple[dict[str, Any], str, list[str]]:
    lower = (ctype or "").lower()
    suffix = Path(urlparse(original_from_wayback(url)).path).suffix.lower()
    if not ("html" in lower or suffix in {".html", ".htm", ""}):
        return ({"title": None, "published_at": None, "modified_at": None}, "", [])
    text = body.decode("utf-8", errors="replace")
    soup = BeautifulSoup(text, "html.parser")
    for node in soup.select("#wm-ipp, script, style, noscript, svg"):
        node.decompose()
    title = None
    if soup.title:
        title = soup.title.get_text(" ", strip=True)
    og = soup.select_one('meta[property="og:title"]')
    if og and og.get("content"):
        title = og["content"].strip()
    published = None
    modified = None
    for selector in (
        'meta[property="article:published_time"]', 'meta[name="date"]',
        'meta[itemprop="datePublished"]', 'time[datetime]',
    ):
        node = soup.select_one(selector)
        if node:
            published = node.get("content") or node.get("datetime")
            if published:
                break
    for selector in ('meta[property="article:modified_time"]', 'meta[itemprop="dateModified"]'):
        node = soup.select_one(selector)
        if node and node.get("content"):
            modified = node["content"]
            break
    container = None
    for selector in (
        "article", ".article-content", ".entry-content", ".post-content", ".content-article",
        "main", "body",
    ):
        container = soup.select_one(selector)
        if container:
            break
    clean = container.get_text("\n", strip=True) if container else soup.get_text("\n", strip=True)
    clean = re.sub(r"\n{3,}", "\n\n", clean)

    discovered: set[str] = set()
    raw_soup = BeautifulSoup(text, "html.parser")
    for tag, attr in (("iframe", "src"), ("script", "src"), ("a", "href"), ("link", "href"), ("img", "src")):
        for node in raw_soup.find_all(tag):
            value = node.get(attr)
            if not value:
                continue
            child = canonical(value, original_from_wayback(url))
            child = original_from_wayback(child)
            if child.startswith(("http://", "https://")):
                discovered.add(child)
    for match in re.finditer(r"https?://[^\s\"'<>]+", text):
        discovered.add(match.group(0).rstrip(")],.;"))
    return ({"title": title, "published_at": published, "modified_at": modified}, clean, sorted(discovered))


def cdx_snapshots(session: requests.Session, original_url: str, election: int) -> list[dict[str, str]]:
    endpoint = "https://web.archive.org/cdx/search/cdx"
    params = {
        "url": original_url,
        "output": "json",
        "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200",
        "from": str(election - 1),
        "to": str(election),
        "collapse": "digest",
        "limit": "100",
    }
    response = session.get(endpoint, params=params, timeout=TIMEOUT)
    response.raise_for_status()
    rows = response.json()
    if not rows or len(rows) < 2:
        return []
    header = rows[0]
    cutoff = CUTOFFS[election]
    out = []
    for row in rows[1:]:
        item = dict(zip(header, row))
        if item.get("timestamp", "") <= cutoff:
            out.append(item)
    out.sort(key=lambda x: x["timestamp"], reverse=True)
    return out


def fetch_bytes(session: requests.Session, url: str) -> tuple[requests.Response, bytes]:
    response = session.get(url, timeout=TIMEOUT, allow_redirects=True, stream=True)
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_content(65536):
        if not chunk:
            continue
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_BYTES:
            break
    return response, b"".join(chunks)


def save_body(body: bytes, original_url: str, ctype: str | None) -> str:
    digest = sha256(body)
    suffix = Path(urlparse(original_url).path).suffix.lower()
    if suffix not in ASSET_EXTENSIONS:
        if "html" in (ctype or "").lower():
            suffix = ".html"
        elif "json" in (ctype or "").lower():
            suffix = ".json"
        elif "pdf" in (ctype or "").lower():
            suffix = ".pdf"
        else:
            suffix = ".bin"
    path = RAW_DIR / f"{digest}{suffix}"
    path.write_bytes(body)
    return str(path.relative_to(ROOT))


def load_seeds() -> list[tuple[int, str, str | None, int]]:
    manifest = json.loads((ER / "e_reason_source_seed_manifest_v1.json").read_text(encoding="utf-8"))
    return [(int(x["election"]), canonical(x["url"]), None, 0) for x in manifest["seeds"]]


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    TEXT_DIR.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fr,ar;q=0.9,en;q=0.6"})

    queue = deque(load_seeds())
    seen: set[tuple[int, str]] = set()
    records: list[Record] = []
    admissible_articles: list[dict[str, Any]] = []

    while queue and len(records) < MAX_FETCHES:
        election, original_url, parent_url, depth = queue.popleft()
        original_url = canonical(original_url)
        key = (election, original_url)
        if key in seen or not allowed_original(original_url) or depth > MAX_DEPTH:
            continue
        seen.add(key)
        retrieved = now()
        snapshot = None
        cdx_error = None
        try:
            snapshots = cdx_snapshots(session, original_url, election)
            snapshot = snapshots[0] if snapshots else None
        except Exception as exc:
            cdx_error = f"{type(exc).__name__}: {exc}"

        attempts: list[tuple[str, str, str | None]] = []
        if snapshot:
            ts = snapshot["timestamp"]
            attempts.append((f"https://web.archive.org/web/{ts}id_/{original_url}", "WAYBACK_PRE_CUTOFF", ts))
        attempts.append((original_url, "DIRECT_DISCOVERY_ONLY", None))

        success = False
        for retrieval_url, transport, archive_ts in attempts:
            try:
                response, body = fetch_bytes(session, retrieval_url)
                ctype = response.headers.get("content-type", "").split(";")[0].strip()
                meta, clean_text, discovered = metadata_and_text(body, retrieval_url, ctype)
                admissibility = "PRE_CUTOFF_ARCHIVE_ADMISSIBLE" if transport == "WAYBACK_PRE_CUTOFF" and response.ok else "DISCOVERY_ONLY_NOT_EVIDENCE"
                archived_path = save_body(body, original_url, ctype) if response.ok and body else None
                text_path = None
                if clean_text:
                    text_file = TEXT_DIR / f"{sha256(clean_text.encode('utf-8'))}.txt"
                    text_file.write_text(clean_text, encoding="utf-8")
                    text_path = str(text_file.relative_to(ROOT))
                kept_children = []
                for child in discovered:
                    child = canonical(child)
                    if allowed_original(child) and relevant(child, election):
                        kept_children.append(child)
                        if depth < MAX_DEPTH and (election, child) not in seen:
                            queue.append((election, child, original_url, depth + 1))
                records.append(Record(
                    election=election,
                    original_url=original_url,
                    retrieval_url=str(response.url),
                    parent_url=parent_url,
                    depth=depth,
                    transport=transport,
                    retrieved_at=retrieved,
                    status_code=response.status_code,
                    content_type=ctype,
                    bytes=len(body),
                    sha256=sha256(body) if body else None,
                    archive_timestamp=archive_ts,
                    archived_path=archived_path,
                    text_path=text_path,
                    published_at=meta.get("published_at"),
                    modified_at=meta.get("modified_at"),
                    admissibility=admissibility,
                    source_class=source_class(original_url),
                    error=cdx_error,
                    discovered_urls=sorted(set(kept_children)),
                ))
                if admissibility == "PRE_CUTOFF_ARCHIVE_ADMISSIBLE" and clean_text:
                    admissible_articles.append({
                        "election": election,
                        "original_url": original_url,
                        "archive_timestamp": archive_ts,
                        "source_class": source_class(original_url),
                        "published_at": meta.get("published_at"),
                        "modified_at": meta.get("modified_at"),
                        "title": meta.get("title"),
                        "content_sha256": sha256(body),
                        "text_sha256": sha256(clean_text.encode("utf-8")),
                        "text_path": text_path,
                    })
                success = response.ok and bool(body)
                if success:
                    break
            except Exception as exc:
                records.append(Record(
                    election=election,
                    original_url=original_url,
                    retrieval_url=retrieval_url,
                    parent_url=parent_url,
                    depth=depth,
                    transport=transport,
                    retrieved_at=retrieved,
                    status_code=None,
                    content_type=None,
                    bytes=0,
                    sha256=None,
                    archive_timestamp=archive_ts,
                    archived_path=None,
                    text_path=None,
                    published_at=None,
                    modified_at=None,
                    admissibility="FETCH_FAILED",
                    source_class=source_class(original_url),
                    error=f"{type(exc).__name__}: {exc}; cdx={cdx_error}",
                    discovered_urls=[],
                ))
            time.sleep(REQUEST_DELAY)

    record_dicts = [asdict(x) for x in records]
    (RUN_DIR / "fetch_manifest.json").write_text(json.dumps(record_dicts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (RUN_DIR / "admissible_article_index.json").write_text(json.dumps(admissible_articles, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    by_election: dict[str, dict[str, int]] = {}
    for year in (2016, 2021):
        rows = [x for x in record_dicts if x["election"] == year]
        by_election[str(year)] = {
            "records": len(rows),
            "unique_original_urls": len({x["original_url"] for x in rows}),
            "admissible_archived": sum(x["admissibility"] == "PRE_CUTOFF_ARCHIVE_ADMISSIBLE" for x in rows),
            "direct_discovery_success": sum(x["transport"] == "DIRECT_DISCOVERY_ONLY" and (x["status_code"] or 0) < 400 for x in rows),
            "fetch_failures": sum(x["status_code"] is None for x in rows),
        }
    summary = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "created_at": now(),
        "record_count": len(record_dicts),
        "admissible_article_count": len(admissible_articles),
        "queue_remaining": len(queue),
        "by_election": by_election,
        "predictive_judgments_generated": False,
        "forecast_delta_generated": False,
        "F1_created": False,
        "immutable_artifacts_modified": False,
    }
    (RUN_DIR / "run_manifest.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = [
        f"# E_reason historical evidence collection — {RUN_ID}", "",
        f"- Records: **{len(record_dicts)}**", f"- Admissible pre-cutoff archived documents: **{len(admissible_articles)}**",
        f"- Queue remaining: **{len(queue)}**", "",
    ]
    for year in (2016, 2021):
        stats = by_election[str(year)]
        report += [f"## {year}", "", *[f"- {k}: **{v}**" for k, v in stats.items()], ""]
    report += ["## Scientific guardrails", "", "- No predictive judgment generated.", "- No forecast delta computed.", "- F-1, B2, F0, E_collect and Atlas/UI were not write targets.", ""]
    (RUN_DIR / "collector_report.md").write_text("\n".join(report), encoding="utf-8")
    latest = {
        "schema_version": "1.0",
        "latest_run_id": RUN_ID,
        "latest_run_manifest": str((RUN_DIR / "run_manifest.json").relative_to(ROOT)),
        "updated_at": now(),
    }
    (ER / "historical_collection_latest.json").write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
