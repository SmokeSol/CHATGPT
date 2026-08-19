#!/usr/bin/env python3
"""Discover pre-election web evidence for unresolved 2007 native-map cells.

RESEARCH-ONLY CONTRACT
----------------------
* The 2007 outcome transcription may be used only to name checklist targets.
* No value (including magnitude) is copied from the outcome.
* Search/fetch results are never auto-promoted to VERIFIED.
* Pages with an extracted publication date after 2007-09-06 are rejected.
* Pages without a defensible exact date remain AMBIGUOUS_DATE.
* The output is candidate evidence for later human/model review, not a snapshot input.
"""
from __future__ import annotations

import datetime as dt
import html
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "goal100" / "historical" / "2007"
GATE = D / "pre_election_map_recovery_v2_gate.json"
CHECKLIST = D / "historical_native_map_outcome_transcription.json"
OUT = D / "pre_election_map_recovery_v2_machine_candidates.json"
CUTOFF = dt.date(2007, 9, 6)
ALLOWED_HOSTS = (
    "aujourdhui.ma", "www.aujourdhui.ma",
    "lematin.ma", "www.lematin.ma",
    "assahraa.ma", "www.assahraa.ma",
    "oujdacity.net", "www.oujdacity.net",
    "aljazeera.net", "www.aljazeera.net",
)
SEARCH_ENGINES = (
    "https://www.bing.com/search?q={q}&count=8",
    "https://html.duckduckgo.com/html/?q={q}",
)
MONTHS = {
    "janvier": 1, "fevrier": 2, "février": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "aout": 8, "août": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "decembre": 12, "décembre": 12,
}

SESSION = requests.Session()
SESSION.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; MOROCCO26 historical research; +https://github.com/SmokeSol/CHATGPT)"
})


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def get_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fetch(url: str, timeout: int = 20) -> tuple[int | None, str, str]:
    try:
        r = SESSION.get(url, timeout=timeout, allow_redirects=True)
        ctype = (r.headers.get("content-type") or "").lower()
        if r.status_code != 200 or "html" not in ctype:
            return r.status_code, r.url, ""
        return r.status_code, r.url, r.text
    except Exception:
        return None, url, ""


def unwrap_search_url(href: str) -> str | None:
    if not href:
        return None
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    p = urlparse(href)
    if "duckduckgo.com" in p.netloc:
        qs = parse_qs(p.query)
        if "uddg" in qs:
            href = unquote(qs["uddg"][0])
            p = urlparse(href)
    if p.scheme not in {"http", "https"}:
        return None
    if p.netloc.lower() not in ALLOWED_HOSTS:
        return None
    return href.split("#", 1)[0]


def search(query: str) -> list[str]:
    urls: list[str] = []
    for template in SEARCH_ENGINES:
        status, _, text = fetch(template.format(q=quote_plus(query)))
        if status != 200 or not text:
            continue
        soup = BeautifulSoup(text, "html.parser")
        for a in soup.find_all("a", href=True):
            u = unwrap_search_url(a.get("href", ""))
            if u and u not in urls:
                urls.append(u)
            if len(urls) >= 8:
                break
        if len(urls) >= 8:
            break
    return urls[:8]


def parse_date(soup: BeautifulSoup, text: str) -> tuple[str | None, str]:
    for attr, value in (("property", "article:published_time"), ("name", "date"), ("itemprop", "datePublished")):
        tag = soup.find("meta", attrs={attr: value})
        if tag and tag.get("content"):
            raw = str(tag["content"]).strip()
            m = re.match(r"(20\d\d)-(\d\d)-(\d\d)", raw)
            if m:
                return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", f"meta:{value}"
    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = script.string or script.get_text(" ")
        m = re.search(r'"datePublished"\s*:\s*"(20\d\d)-(\d\d)-(\d\d)', raw)
        if m:
            return f"{m.group(1)}-{m.group(2)}-{m.group(3)}", "jsonld:datePublished"
    compact = re.sub(r"\s+", " ", text[:12000]).lower()
    pat = r"\b([0-3]?\d)\s+(janvier|f[eé]vrier|mars|avril|mai|juin|juillet|ao[uû]t|septembre|octobre|novembre|d[eé]cembre)\s+2007\b"
    m = re.search(pat, compact)
    if m:
        month_key = m.group(2)
        month = MONTHS.get(month_key) or MONTHS.get(unicodedata.normalize("NFKD", month_key).encode("ascii", "ignore").decode())
        if month:
            return f"2007-{month:02d}-{int(m.group(1)):02d}", "visible_text"
    return None, "missing"


def territory_terms(name: str) -> list[str]:
    toks = [t for t in norm(name).split() if len(t) >= 3 and t not in {"nord", "sud", "al", "el"}]
    return toks[:5]


def evidence_snippets(text: str, constituency: str) -> list[dict]:
    clean = re.sub(r"\s+", " ", text)
    nclean = norm(clean)
    terms = territory_terms(constituency)
    if terms and not all(t in nclean for t in terms[: min(2, len(terms))]):
        return []
    chunks = re.split(r"(?<=[.!?])\s+|\n+", clean)
    hits: list[dict] = []
    seat_re = re.compile(r"\b(\d{1,2})\s+si[eè]ges?\b", re.I)
    for i, chunk in enumerate(chunks):
        nchunk = norm(chunk)
        if not any(t in nchunk for t in terms):
            continue
        context = " ".join(chunks[max(0, i-1): min(len(chunks), i+2)])[:1400]
        nums = sorted({int(x) for x in seat_re.findall(context) if 1 <= int(x) <= 10})
        if nums:
            hits.append({"seat_numbers_detected": nums, "context": context})
    return hits[:5]


def main() -> None:
    gate = get_json(GATE)
    if gate.get("same_year_outcome_loaded") is not False:
        raise SystemExit("research gate contract broken")
    missing_ids = set(gate.get("remaining_native_ids", []))
    checklist = get_json(CHECKLIST)
    # CHECKLIST USE IS DISCOVERY ONLY. We copy only names into search queries; no magnitude.
    targets = [
        {"native_id": r["native_id"], "query_name": r["constituency"]}
        for r in checklist.get("rows", []) if r.get("native_id") in missing_ids
    ]
    report = {
        "schema_version": "1.0",
        "research_id": "M26-HIST-2007-MISSING-WEB-DISCOVERY-V1",
        "generated_at": dt.date.today().isoformat(),
        "cutoff": CUTOFF.isoformat(),
        "status": "MACHINE_CANDIDATES_NOT_SNAPSHOT_INPUT",
        "outcome_use": "CHECKLIST_NAMES_FOR_DISCOVERY_ONLY_NO_VALUES_COPIED",
        "targets": [],
    }
    for idx, target in enumerate(targets, 1):
        name = target["query_name"]
        query = f'"{name}" 2007 legislatives sieges Maroc'
        urls = search(query)
        entry = {"native_id": target["native_id"], "query_name": name, "query": query, "candidates": []}
        for url in urls:
            status, final_url, raw = fetch(url)
            if status != 200 or not raw:
                continue
            soup = BeautifulSoup(raw, "html.parser")
            page_text = soup.get_text("\n", strip=True)
            published, date_method = parse_date(soup, page_text)
            date_status = "AMBIGUOUS_DATE"
            if published:
                d = dt.date.fromisoformat(published)
                date_status = "ELIGIBLE_PRE_CUTOFF" if d <= CUTOFF else "REJECT_POST_CUTOFF"
            snippets = evidence_snippets(page_text, name)
            if snippets:
                entry["candidates"].append({
                    "url": final_url,
                    "publication_date": published,
                    "date_extraction": date_method,
                    "date_status": date_status,
                    "source_class": "T2_DISCOVERY",
                    "status": "MACHINE_CANDIDATE_NOT_VERIFIED",
                    "snippets": snippets,
                })
        report["targets"].append(entry)
        print(f"[{idx}/{len(targets)}] {target['native_id']} {name}: {len(entry['candidates'])} candidate pages", flush=True)
        time.sleep(0.15)
    report["summary"] = {
        "targets": len(targets),
        "targets_with_candidate_pages": sum(bool(t["candidates"]) for t in report["targets"]),
        "eligible_pre_cutoff_candidate_pages": sum(
            c["date_status"] == "ELIGIBLE_PRE_CUTOFF"
            for t in report["targets"] for c in t["candidates"]
        ),
        "post_cutoff_rejected_pages": sum(
            c["date_status"] == "REJECT_POST_CUTOFF"
            for t in report["targets"] for c in t["candidates"]
        ),
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], sort_keys=True))


if __name__ == "__main__":
    main()
