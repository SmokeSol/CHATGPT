#!/usr/bin/env python3
"""Inventory Médias24 election assets for the E_collect V1.1 pipeline.

The script is deliberately provenance-first:
- it starts from a bounded set of human seeds;
- it records every HTTP response with URL, timestamp, status, type, size and SHA-256;
- it recursively follows only Médias24 election-related iframe/static assets;
- it archives small structured/static assets, not full news articles;
- it produces an append-only run directory suitable for independent review.

It does not modify F-1, F0, B2, coefficients or forecast probabilities.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import time
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

REPO_ROOT = Path(__file__).resolve().parents[2]
ECOLLECT_ROOT = REPO_ROOT / "morocco26" / "data" / "goal100" / "e_collect"

RUN_ID = os.environ.get("E_COLLECT_RUN_ID") or (
    "medias24_inventory_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
RUN_DIR = ECOLLECT_ROOT / "runs" / RUN_ID
RAW_DIR = RUN_DIR / "raw"

USER_AGENT = (
    "Atlas395-ECollect/1.1 (+https://github.com/SmokeSol/CHATGPT; "
    "scientific electoral evidence inventory)"
)
TIMEOUT = (12, 35)
MAX_FETCHES = int(os.environ.get("E_COLLECT_MAX_FETCHES", "500"))
MAX_ARCHIVE_BYTES = int(os.environ.get("E_COLLECT_MAX_ARCHIVE_BYTES", "2500000"))
MAX_TOTAL_ARCHIVE_BYTES = int(
    os.environ.get("E_COLLECT_MAX_TOTAL_ARCHIVE_BYTES", "30000000")
)
MAX_DEPTH = int(os.environ.get("E_COLLECT_MAX_DEPTH", "4"))

SEEDS = [
    {
        "url": "https://assets.medias24.com/elections/",
        "origin": "HUMAN_SEED",
        "purpose": "root election asset discovery",
    },
    {
        "url": "https://medias24.com/2021/09/05/legislatives-voici-la-liste-des-principaux-candidats-circonscription-par-circonscription/",
        "origin": "HUMAN_SEED",
        "purpose": "2021 pre-election candidate maps",
    },
    {
        "url": "https://medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/",
        "origin": "HUMAN_SEED",
        "purpose": "2016 pre-election candidate maps",
    },
    {
        "url": "https://medias24.com/2021/09/17/legislatives-2021-qui-a-ete-elu-dans-votre-circonscription-17-cartes-interactives/",
        "origin": "HUMAN_SEED",
        "purpose": "2021 elected-member maps",
    },
    {
        "url": "https://medias24.com/2021/09/27/legislatives-2021-voici-le-nombre-de-voix-par-candidat-circonscription-et-parti/",
        "origin": "HUMAN_SEED",
        "purpose": "2021 detailed results",
    },
    {
        "url": "https://medias24.com/categorie/elections-2021/",
        "origin": "HUMAN_SEED",
        "purpose": "2021 election dashboard",
    },
    {
        "url": "https://medias24.com/2021/08/14/voici-les-profils-des-candidats-du-pjd-pour-les-prochaines-legislatives/",
        "origin": "HUMAN_SEED",
        "purpose": "2021 PJD profiles and structured features",
    },
    {
        "url": "https://medias24.com/2026/06/05/legislatives-2026-le-rni-devoile-une-liste-de-89-candidats-1693575/",
        "origin": "HUMAN_SEED",
        "purpose": "2026 RNI roster",
    },
    {
        "url": "https://medias24.com/2026/04/20/legislatives-2026-le-pjd-sort-ses-poids-lourds-benkirane-valide-une-premiere-vague-de-40-candidats-1662703/",
        "origin": "HUMAN_SEED",
        "purpose": "2026 PJD roster wave",
    },
    {
        "url": "https://medias24.com/2026/06/15/legislatives-2026-lusfp-devoile-une-liste-de-plus-de-70-candidats-1700435/",
        "origin": "HUMAN_SEED",
        "purpose": "2026 USFP roster",
    },
    {
        "url": "https://medias24.com/2026/07/24/legislatives-2026-ce-que-revele-la-liste-des-candidats-du-pps-1729547/",
        "origin": "HUMAN_SEED",
        "purpose": "2026 PPS roster and candidate features",
    },
]

ALLOWED_HOSTS = {
    "medias24.com",
    "www.medias24.com",
    "assets.medias24.com",
}
STRUCTURED_EXTENSIONS = {
    ".json",
    ".geojson",
    ".topojson",
    ".csv",
    ".tsv",
    ".xml",
    ".txt",
}
STATIC_EXTENSIONS = STRUCTURED_EXTENSIONS | {
    ".html",
    ".htm",
    ".js",
    ".css",
    ".map",
}
ELECTION_MARKERS = (
    "election",
    "elections",
    "election2021",
    "election2016",
    "legislative",
    "candidat",
    "elu",
    "resultat",
    "circonscription",
    "carte",
)

URL_RE = re.compile(
    r"""(?P<url>
        https?://[^\s\"'<>\\)]+
        |
        (?:\"|')(?P<rel>[^\"']+\.(?:json|geojson|topojson|csv|tsv|xml|txt|js|css|html?|pdf)(?:\?[^\"']*)?)(?:\"|')
    )""",
    re.IGNORECASE | re.VERBOSE,
)


@dataclass
class FetchRecord:
    url: str
    final_url: str
    parent_url: str | None
    depth: int
    discovery_origin: str
    discovery_purpose: str
    retrieved_at: str
    status_code: int | None
    content_type: str | None
    content_length: int
    sha256: str | None
    archived_path: str | None
    asset_role: str
    error: str | None
    discovered_urls: list[str]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def canonicalize(url: str, base: str | None = None) -> str:
    if base:
        url = urljoin(base, url)
    url, _fragment = urldefrag(url)
    return url.strip()


def host_allowed(url: str) -> bool:
    return (urlparse(url).hostname or "").lower() in ALLOWED_HOSTS


def election_relevant(url: str, parent: str | None = None) -> bool:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = (parsed.path or "").lower()
    if host == "assets.medias24.com":
        return any(marker in path for marker in ELECTION_MARKERS)
    if host in {"medias24.com", "www.medias24.com"}:
        if parent and (urlparse(parent).hostname or "").lower() == "assets.medias24.com":
            return False
        return any(marker in path for marker in ELECTION_MARKERS)
    return False


def extension_for(url: str, content_type: str | None) -> str:
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix and len(suffix) <= 10:
        return suffix
    ctype = (content_type or "").lower()
    if "json" in ctype:
        return ".json"
    if "javascript" in ctype:
        return ".js"
    if "css" in ctype:
        return ".css"
    if "html" in ctype:
        return ".html"
    if "csv" in ctype:
        return ".csv"
    if "xml" in ctype:
        return ".xml"
    if "pdf" in ctype:
        return ".pdf"
    return ".bin"


def classify_asset(url: str, content_type: str | None) -> str:
    lower = url.lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    if suffix in STRUCTURED_EXTENSIONS or "json" in (content_type or "").lower():
        return "STRUCTURED_DATA"
    if lower.endswith(".pdf") or "pdf" in (content_type or "").lower():
        return "PDF"
    if suffix in {".js", ".css", ".map"}:
        return "STATIC_CODE"
    if suffix in {".html", ".htm"} or "html" in (content_type or "").lower():
        if (urlparse(url).hostname or "").lower() == "assets.medias24.com":
            return "INTERACTIVE_ASSET_HTML"
        return "MEDIAS24_ARTICLE_OR_DASHBOARD"
    return "OTHER"


def should_archive(url: str, content_type: str | None, size: int) -> bool:
    if size <= 0 or size > MAX_ARCHIVE_BYTES:
        return False
    host = (urlparse(url).hostname or "").lower()
    suffix = Path(urlparse(url).path).suffix.lower()
    ctype = (content_type or "").lower()
    if host != "assets.medias24.com":
        return False
    return (
        suffix in STATIC_EXTENSIONS
        or "text/" in ctype
        or "json" in ctype
        or "javascript" in ctype
    )


def extract_metadata(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    title = None
    if soup.title:
        title = soup.title.get_text(" ", strip=True)
    for selector in (
        'meta[property="og:title"]',
        'meta[name="twitter:title"]',
    ):
        node = soup.select_one(selector)
        if node and node.get("content"):
            title = node["content"].strip()
            break
    published = None
    modified = None
    for selector in (
        'meta[property="article:published_time"]',
        'meta[name="date"]',
        "time[datetime]",
    ):
        node = soup.select_one(selector)
        value = node.get("content") if node and node.name == "meta" else (
            node.get("datetime") if node else None
        )
        if value:
            published = value
            break
    node = soup.select_one('meta[property="article:modified_time"]')
    if node and node.get("content"):
        modified = node["content"].strip()
    h1 = soup.find("h1")
    headline = h1.get_text(" ", strip=True) if h1 else title
    return {
        "url": url,
        "title": title,
        "headline": headline,
        "published_at": published,
        "modified_at": modified,
        "iframe_urls": [
            canonicalize(tag.get("src", ""), url)
            for tag in soup.find_all("iframe")
            if tag.get("src")
        ],
    }


def discover_urls(text: str, base_url: str, content_type: str | None) -> list[str]:
    discovered: set[str] = set()
    ctype = (content_type or "").lower()
    if "html" in ctype or base_url.lower().endswith((".html", ".htm", "/")):
        soup = BeautifulSoup(text, "html.parser")
        for tag, attr in (
            ("iframe", "src"),
            ("script", "src"),
            ("link", "href"),
            ("a", "href"),
            ("source", "src"),
        ):
            for node in soup.find_all(tag):
                value = node.get(attr)
                if value:
                    discovered.add(canonicalize(value, base_url))
        for node in soup.find_all(attrs={"data-src": True}):
            discovered.add(canonicalize(node.get("data-src"), base_url))

    for match in URL_RE.finditer(text):
        raw = match.group("url")
        rel = match.group("rel")
        candidate = rel or raw
        if candidate:
            candidate = candidate.strip("\"'")
            discovered.add(canonicalize(candidate, base_url))

    cleaned = []
    for url in sorted(discovered):
        if not url.startswith(("http://", "https://")):
            continue
        if not host_allowed(url):
            continue
        if election_relevant(url, base_url):
            cleaned.append(url)
    return cleaned


def add_common_candidates(url: str) -> Iterable[str]:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host != "assets.medias24.com":
        return []
    path = parsed.path
    if not path.endswith(("/", "/index.html", "/index.htm")):
        return []
    base = url if path.endswith("/") else url.rsplit("/", 1)[0] + "/"
    names = (
        "data.json",
        "datas.json",
        "candidats.json",
        "candidates.json",
        "resultats.json",
        "results.json",
        "elections.json",
        "config.json",
        "data.csv",
        "candidats.csv",
        "script.js",
        "scripts.js",
        "main.js",
        "app.js",
        "map.js",
        "data.js",
        "style.css",
        "styles.css",
    )
    return [urljoin(base, name) for name in names]


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "fr,ar;q=0.9,en;q=0.6",
        }
    )

    queue: deque[tuple[str, str | None, int, str, str]] = deque()
    for seed in SEEDS:
        queue.append(
            (
                canonicalize(seed["url"]),
                None,
                0,
                seed["origin"],
                seed["purpose"],
            )
        )

    seen: set[str] = set()
    records: list[FetchRecord] = []
    article_index: list[dict] = []
    archived_total = 0

    search_log_path = RUN_DIR / "search_log.jsonl"
    with search_log_path.open("w", encoding="utf-8") as search_log:
        while queue and len(records) < MAX_FETCHES:
            url, parent_url, depth, origin, purpose = queue.popleft()
            url = canonicalize(url)
            if not url or url in seen:
                continue
            seen.add(url)
            if not host_allowed(url):
                continue
            if depth > 0 and not election_relevant(url, parent_url):
                continue

            retrieved_at = now_iso()
            status_code = None
            content_type = None
            body = b""
            final_url = url
            error = None
            discovered_urls: list[str] = []
            archived_path = None
            role = "UNKNOWN"

            search_log.write(
                json.dumps(
                    {
                        "timestamp": retrieved_at,
                        "event": "FETCH_START",
                        "url": url,
                        "parent_url": parent_url,
                        "depth": depth,
                        "discovery_origin": origin,
                        "purpose": purpose,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            search_log.flush()

            try:
                response = session.get(
                    url,
                    timeout=TIMEOUT,
                    allow_redirects=True,
                    stream=True,
                )
                status_code = response.status_code
                final_url = canonicalize(response.url)
                content_type = response.headers.get("content-type", "").split(";")[0].strip()
                chunks = []
                total = 0
                hard_cap = max(MAX_ARCHIVE_BYTES, 8_000_000)
                for chunk in response.iter_content(chunk_size=65536):
                    if not chunk:
                        continue
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > hard_cap:
                        break
                body = b"".join(chunks)
                role = classify_asset(final_url, content_type)

                if response.ok and body:
                    sha256 = hashlib.sha256(body).hexdigest()
                    text = None
                    if (
                        "text/" in (content_type or "").lower()
                        or "json" in (content_type or "").lower()
                        or "javascript" in (content_type or "").lower()
                        or Path(urlparse(final_url).path).suffix.lower()
                        in STATIC_EXTENSIONS
                        or final_url.endswith("/")
                    ):
                        encoding = response.encoding or "utf-8"
                        try:
                            text = body.decode(encoding, errors="replace")
                        except LookupError:
                            text = body.decode("utf-8", errors="replace")

                    if text is not None:
                        discovered_urls = discover_urls(text, final_url, content_type)
                        if role == "MEDIAS24_ARTICLE_OR_DASHBOARD":
                            meta = extract_metadata(text, final_url)
                            meta.update(
                                {
                                    "sha256": sha256,
                                    "content_length": len(body),
                                    "discovery_origin": origin,
                                    "purpose": purpose,
                                }
                            )
                            article_index.append(meta)

                    for candidate in add_common_candidates(final_url):
                        if candidate not in seen:
                            discovered_urls.append(candidate)

                    if (
                        should_archive(final_url, content_type, len(body))
                        and archived_total + len(body) <= MAX_TOTAL_ARCHIVE_BYTES
                    ):
                        ext = extension_for(final_url, content_type)
                        raw_path = RAW_DIR / f"{sha256}{ext}"
                        if not raw_path.exists():
                            raw_path.write_bytes(body)
                            archived_total += len(body)
                        archived_path = str(raw_path.relative_to(REPO_ROOT))
                else:
                    sha256 = hashlib.sha256(body).hexdigest() if body else None

            except Exception as exc:
                sha256 = None
                error = f"{type(exc).__name__}: {exc}"
                role = "FETCH_ERROR"

            deduped_discovered = []
            seen_discovered = set()
            for child in discovered_urls:
                child = canonicalize(child, final_url)
                if (
                    child
                    and child not in seen_discovered
                    and host_allowed(child)
                    and election_relevant(child, final_url)
                ):
                    seen_discovered.add(child)
                    deduped_discovered.append(child)
                    if depth < MAX_DEPTH and child not in seen:
                        queue.append(
                            (
                                child,
                                final_url,
                                depth + 1,
                                origin,
                                f"discovered from {final_url}",
                            )
                        )

            record = FetchRecord(
                url=url,
                final_url=final_url,
                parent_url=parent_url,
                depth=depth,
                discovery_origin=origin,
                discovery_purpose=purpose,
                retrieved_at=retrieved_at,
                status_code=status_code,
                content_type=content_type,
                content_length=len(body),
                sha256=sha256,
                archived_path=archived_path,
                asset_role=role,
                error=error,
                discovered_urls=deduped_discovered,
            )
            records.append(record)

            search_log.write(
                json.dumps(
                    {
                        "timestamp": now_iso(),
                        "event": "FETCH_END",
                        "url": url,
                        "final_url": final_url,
                        "status_code": status_code,
                        "content_type": content_type,
                        "content_length": len(body),
                        "sha256": sha256,
                        "asset_role": role,
                        "error": error,
                        "discovered_count": len(deduped_discovered),
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            search_log.flush()
            time.sleep(0.08)

    record_dicts = [asdict(record) for record in records]
    (RUN_DIR / "asset_inventory.json").write_text(
        json.dumps(record_dicts, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (RUN_DIR / "article_index.json").write_text(
        json.dumps(article_index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    status_counts: dict[str, int] = {}
    role_counts: dict[str, int] = {}
    for record in records:
        status_key = str(record.status_code) if record.status_code is not None else "ERROR"
        status_counts[status_key] = status_counts.get(status_key, 0) + 1
        role_counts[record.asset_role] = role_counts.get(record.asset_role, 0) + 1

    structured = [
        r for r in record_dicts
        if r["asset_role"] == "STRUCTURED_DATA" and r["status_code"] == 200
    ]
    interactive = [
        r for r in record_dicts
        if r["asset_role"] == "INTERACTIVE_ASSET_HTML" and r["status_code"] == 200
    ]
    manifest = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "collector": "CHATGPT_GITHUB_ACTIONS_MEDIAS24_INVENTORY_V1",
        "started_from_branch": os.environ.get("GITHUB_REF_NAME", "unknown"),
        "started_from_sha": os.environ.get("GITHUB_SHA"),
        "created_at": now_iso(),
        "human_seed_amendment": (
            "morocco26/data/goal100/e_collect/"
            "e_collect_v1_1_human_seed_amendment.json"
        ),
        "execution_scope": "MEDIAS24_ELECTION_ASSET_INVENTORY",
        "forecast_effect_authorized": False,
        "frozen_artifacts_modified": False,
        "seed_count": len(SEEDS),
        "fetch_count": len(records),
        "seen_url_count": len(seen),
        "queue_remaining_at_stop": len(queue),
        "max_fetches": MAX_FETCHES,
        "max_depth": MAX_DEPTH,
        "archived_bytes": archived_total,
        "status_counts": status_counts,
        "role_counts": role_counts,
        "structured_asset_count": len(structured),
        "interactive_asset_html_count": len(interactive),
        "source_policy": {
            "allowed_hosts": sorted(ALLOWED_HOSTS),
            "discovery_origin": "HUMAN_SEED",
            "root_seed": "https://assets.medias24.com/elections/",
        },
        "outputs": {
            "asset_inventory": str(
                (RUN_DIR / "asset_inventory.json").relative_to(REPO_ROOT)
            ),
            "article_index": str(
                (RUN_DIR / "article_index.json").relative_to(REPO_ROOT)
            ),
            "search_log": str(search_log_path.relative_to(REPO_ROOT)),
            "raw_dir": str(RAW_DIR.relative_to(REPO_ROOT)),
        },
    }
    (RUN_DIR / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report_lines = [
        f"# Médias24 election asset inventory — {RUN_ID}",
        "",
        "## Result",
        "",
        f"- Fetches: **{len(records)}** / cap {MAX_FETCHES}",
        f"- HTTP status counts: `{json.dumps(status_counts, sort_keys=True)}`",
        f"- Asset roles: `{json.dumps(role_counts, sort_keys=True)}`",
        f"- Interactive HTML assets fetched: **{len(interactive)}**",
        f"- Structured data assets fetched: **{len(structured)}**",
        f"- Archived static/structured bytes: **{archived_total}**",
        f"- Queue remaining at stop: **{len(queue)}**",
        "",
        "## Structured assets",
        "",
    ]
    if structured:
        for item in structured:
            report_lines.append(
                f"- `{item['final_url']}` — {item['content_type']} — "
                f"{item['content_length']} bytes — `{item['sha256']}`"
            )
    else:
        report_lines.append("- None identified in this pass.")
    report_lines.extend(
        [
            "",
            "## Integrity",
            "",
            "- F-1, F0, B2 and coefficients were not read-write targets.",
            "- Full news articles were not archived; article metadata and response hashes were recorded.",
            "- Human seeds are provenance hints only. This run makes no forecast claim.",
            "",
        ]
    )
    (RUN_DIR / "collector_report.md").write_text(
        "\n".join(report_lines),
        encoding="utf-8",
    )

    latest = {
        "schema_version": "1.0",
        "latest_run_id": RUN_ID,
        "latest_run_manifest": str(
            (RUN_DIR / "run_manifest.json").relative_to(REPO_ROOT)
        ),
        "updated_at": now_iso(),
    }
    (ECOLLECT_ROOT / "medias24_inventory_latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FileExistsError:
        print(
            f"E_COLLECT_INVENTORY_FAIL: run directory already exists: {RUN_DIR}",
            file=sys.stderr,
        )
        raise SystemExit(2)
