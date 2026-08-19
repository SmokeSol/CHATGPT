#!/usr/bin/env python3
"""Recover the 2007 Moroccan electoral map from PRE-ELECTION public sources only.

This script is intentionally outcome-blind. It MUST run on a lineage where the 2007
canonical outcome has not yet been ingested. A legacy raw 2007 workbook already
existed in the repository before this mission; it is treated as SEALED/FORBIDDEN and
must never be opened by this recovery process. CI audits file-open syscalls.

The first purpose is source discovery / evidence extraction, not automatic promotion
to a canonical snapshot. Every extracted fact keeps publication date, URL, exact
supporting context and status. Only pages dated <= 2007-09-06 are eligible.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goal100" / "historical" / "2007_v2_research"
OUT.mkdir(parents=True, exist_ok=True)
CUTOFF = "2007-09-06"

# These derived same-year outcome artifacts MUST NOT exist on the clean lineage.
FORBIDDEN_DERIVED = [
    ROOT / "data" / "goal100" / "historical" / "2007" / "legislative_2007_outcome_canonical.json",
    ROOT / "data" / "goal100" / "historical" / "2007" / "historical_native_map_outcome_transcription.json",
]
# This legacy raw file pre-dates the mission and may exist in Git. It is SEALED:
# existence is recorded, but the recovery process must not open it. CI uses strace
# to fail if this pathname is opened.
SEALED_PREEXISTING = ROOT / "data" / "goal100" / "older_history_probe" / "raw" / "parlement-elections-2007-1-0.xlsx"

SEED_URLS = [
    "https://assahraa.ma/journal/2007/46530",
    "https://assahraa.ma/journal/2007/46728",
    "https://lematin.ma/journal/2007/Legislatives-a-travers-les-regions_15-listes-locales-a-Laayoune-et-23-a-Meknes-Tafilelt/76043.html",
    "https://lematin.ma/journal/2007/Scrutin-du-7-septembre_Journal-de-campagne--716-plaintes-pour-violation-du-code-electoral/74300.html",
]

DISCOVERY_QUERIES = [
    'site:lematin.ma/journal/2007 legislatives circonscription sièges "7 septembre" MAP',
    'site:lematin.ma/journal/2007 "circonscriptions" "sièges" "scrutin du 7 septembre"',
    'site:aujourdhui.ma 2007 "tour du maroc des circonscriptions électorales"',
    'site:assahraa.ma/journal/2007 circonscriptions élections sièges septembre 2007',
    'site:lematin.ma/journal/2007 "listes" "candidats" "sièges" "circonscription" élections',
    'site:lematin.ma/journal/2007 "nouveau découpage" circonscription élections 2007',
]

DATE_PATTERNS = [
    re.compile(r"(\d{1,2})\s+(Janvier|Février|Mars|Avril|Mai|Juin|Juillet|Août|Septembre|Octobre|Novembre|Décembre)\s+2007", re.I),
    re.compile(r"2007[-/](\d{1,2})[-/](\d{1,2})"),
]
MONTHS = {"janvier":1,"février":2,"fevrier":2,"mars":3,"avril":4,"mai":5,"juin":6,"juillet":7,"août":8,"aout":8,"septembre":9,"octobre":10,"novembre":11,"décembre":12,"decembre":12}

EXPLICIT_PATTERNS = [
    re.compile(r"(?:circonscription(?:\s+électorale)?(?:\s+de|\s+d['’])?\s*)([A-ZÀ-ÖØ-öø-ÿ0-9][A-Za-zÀ-ÖØ-öø-ÿ0-9'’ .\-]{1,75}?)\s*(?:[,;:()\-]|compte|avec|où|qui|:).*?(\d+)\s+si[eè]ges?", re.I),
    re.compile(r"([A-ZÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’ .\-]{2,70}?)\s*[:,-]\s*(\d+)\s+si[eè]ges?", re.I),
]

S = requests.Session()
S.headers.update({
    "User-Agent": "MOROCCO26-historical-research/2.0 (+noncommercial academic election reconstruction)",
    "Accept-Language": "fr,ar;q=0.9,en;q=0.7",
})


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def clean_text(raw: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(raw or "")).strip()


def parse_date(text: str) -> str | None:
    t = clean_text(text)
    m = DATE_PATTERNS[0].search(t)
    if m:
        day = int(m.group(1)); month = MONTHS[m.group(2).lower()]
        return f"2007-{month:02d}-{day:02d}"
    m = DATE_PATTERNS[1].search(t)
    if m:
        return f"2007-{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    return None


def canonical_result_url(href: str) -> str | None:
    if not href:
        return None
    href = html.unescape(href)
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        q = parse_qs(urlparse(href).query)
        if q.get("uddg"):
            href = unquote(q["uddg"][0])
    if not href.startswith("http"):
        return None
    host = urlparse(href).netloc.lower()
    if any(x in host for x in ("lematin.ma", "aujourdhui.ma", "assahraa.ma", "maghress.com")):
        return href.split("#")[0]
    return None


def search_ddg(query: str) -> list[str]:
    url = "https://html.duckduckgo.com/html/?q=" + quote_plus(query)
    try:
        r = S.get(url, timeout=30)
    except Exception:
        return []
    if r.status_code != 200:
        return []
    soup = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in soup.find_all("a", href=True):
        u = canonical_result_url(a.get("href"))
        if u and u not in out:
            out.append(u)
    return out[:25]


def fetch_article(url: str) -> dict:
    try:
        r = S.get(url, timeout=30, allow_redirects=True)
    except Exception as exc:
        return {"url": url, "status": "FETCH_ERROR", "error": repr(exc)}
    rec = {
        "url": url, "final_url": r.url, "http_status": r.status_code,
        "content_type": r.headers.get("content-type"), "bytes": len(r.content),
        "sha256": sha256(r.content),
    }
    if r.status_code != 200 or not r.text:
        rec["status"] = "FETCH_ERROR"; return rec
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()
    title = clean_text((soup.title.string if soup.title and soup.title.string else ""))
    text = clean_text(soup.get_text(" "))
    date = None
    for key in ("article:published_time", "date", "datePublished", "publish-date"):
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key}) or soup.find("meta", attrs={"itemprop": key})
        if node and node.get("content"):
            date = parse_date(node.get("content")) or date
    date = date or parse_date(text[:5000])
    rec.update({"title": title, "publication_date": date})
    if not date:
        rec["status"] = "AMBIGUOUS_DATE"; rec["text_head"] = text[:800]; return rec
    if date > CUTOFF:
        rec["status"] = "POST_CUTOFF_REJECTED"; return rec
    if date < "2007-01-01":
        rec["status"] = "WRONG_YEAR_REJECTED"; return rec
    rec["status"] = "ELIGIBLE_PRE_ELECTION"; rec["text"] = text
    return rec


def extract_facts(article: dict) -> list[dict]:
    if article.get("status") != "ELIGIBLE_PRE_ELECTION":
        return []
    text = article["text"]
    facts, seen = [], set()
    for pat in EXPLICIT_PATTERNS:
        for m in pat.finditer(text):
            name = clean_text(m.group(1)).strip(" .,:;-–—")
            try: seats = int(m.group(2))
            except Exception: continue
            if not (2 <= seats <= 6) or len(name) > 80: continue
            low = name.lower()
            if any(x in low for x in ("maroc", "chambre", "liste nationale", "parlement", "province compte", "région compte")): continue
            key = (name.lower(), seats, article["url"])
            if key in seen: continue
            seen.add(key)
            lo = max(0, m.start()-240); hi = min(len(text), m.end()+240)
            facts.append({
                "fact_type": "DISTRICT_MAGNITUDE_EXPLICIT", "territory_as_published": name,
                "magnitude": seats, "publication_date": article["publication_date"],
                "url": article["url"], "source_title": article.get("title"),
                "supporting_context": text[lo:hi], "status": "VERIFIED_TEXT_MATCH",
                "provenance": "CONTEMPORARY_PRE_ELECTION_SOURCE",
            })
    return facts


def assert_clean_lineage() -> dict:
    derived_present = [str(p.relative_to(ROOT)) for p in FORBIDDEN_DERIVED if p.exists()]
    if derived_present:
        raise SystemExit(f"LEAKAGE_GUARD_FAIL derived 2007 outcome paths present: {derived_present}")
    head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    base = "2508256551f94ad67c23a39d7263e01202431bfe"
    ok = subprocess.run(["git", "merge-base", "--is-ancestor", base, head], cwd=ROOT).returncode == 0
    if not ok: raise SystemExit("LEAKAGE_GUARD_FAIL clean base is not ancestor")
    return {
        "head_at_run": head, "clean_base": base, "derived_outcome_paths_present": derived_present,
        "base_is_ancestor": True,
        "sealed_legacy_raw_workbook_present": SEALED_PREEXISTING.exists(),
        "sealed_legacy_raw_workbook_policy": "MAY_EXIST_BUT_MUST_NOT_BE_OPENED__CI_SYSCALL_AUDIT",
    }


def main() -> None:
    lineage = assert_clean_lineage()
    discovered = list(SEED_URLS); search_log = []
    for q in DISCOVERY_QUERIES:
        urls = search_ddg(q); search_log.append({"query": q, "urls": urls})
        for u in urls:
            if u not in discovered: discovered.append(u)
        time.sleep(0.4)
    discovered = sorted(set(discovered))[:160]
    articles, facts = [], []
    for i, u in enumerate(discovered):
        rec = fetch_article(u)
        articles.append({k:v for k,v in rec.items() if k != "text"})
        facts.extend(extract_facts(rec))
        if i % 10 == 0: print(f"fetched {i+1}/{len(discovered)} facts={len(facts)}", flush=True)
        time.sleep(0.15)
    facts.sort(key=lambda x: (x["territory_as_published"].lower(), x["magnitude"], x["publication_date"], x["url"]))
    payload = {
        "schema_version": "2.0", "research_id": "M26-HIST-2007-PRE-ELECTION-MAP-RECOVERY-V2",
        "scope": "SOURCE_DISCOVERY_AND_HIGH_PRECISION_EXTRACTION_ONLY__NOT_YET_CANONICAL_SNAPSHOT",
        "cutoff": CUTOFF, "outcome_used": False, "lineage": lineage,
        "search_queries_are_outcome_independent": True, "source_count_discovered": len(discovered),
        "eligible_article_count": sum(a.get("status") == "ELIGIBLE_PRE_ELECTION" for a in articles),
        "explicit_district_magnitude_fact_count": len(facts), "facts": facts,
    }
    (OUT / "pre_election_map_evidence_raw_v2.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    (OUT / "source_fetch_manifest_v2.json").write_text(json.dumps({"schema_version":"2.0","cutoff":CUTOFF,"articles":articles}, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    (OUT / "search_discovery_manifest_v2.json").write_text(json.dumps({"schema_version":"2.0","queries":search_log}, ensure_ascii=False, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    cert = {
        "assertion": "TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_RECOVERY_V2", "cutoff": CUTOFF,
        "derived_same_year_outcome_paths_present": False, "same_year_result_workbook_opened": False,
        "legacy_raw_workbook_is_sealed_not_input": True, "clean_base_commit": lineage["clean_base"],
        "status": "PASS_RECOVERY_RESEARCH_ONLY_PENDING_CI_OPEN_AUDIT",
    }
    (OUT / "anti_leakage_recovery_certificate_v2.json").write_text(json.dumps(cert, indent=2, sort_keys=True)+"\n", encoding="utf-8")
    print(json.dumps({"discovered":len(discovered),"eligible":payload["eligible_article_count"],"facts":len(facts),"out":str(OUT.relative_to(ROOT))}, ensure_ascii=False))

if __name__ == "__main__":
    main()
