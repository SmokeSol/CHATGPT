#!/usr/bin/env python3
"""Recover and parse pre-election Médias24 candidate maps for 2016/2021.

Outputs a provenance-addressed roster and an objective preregistered data-gate
report. It generates no predictive judgments and no forecast delta.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import unicodedata
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
G100 = ROOT / "morocco26" / "data" / "goal100"
ER = G100 / "e_reason"
HIST = G100 / "historical"
RUN_ID = os.environ.get("E_REASON_ROSTER_RUN_ID") or "historical_rosters_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
OUT = ER / "evidence" / "historical_rosters" / RUN_ID
RAW = OUT / "raw"
OUT.mkdir(parents=True, exist_ok=False)
RAW.mkdir(parents=True, exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Atlas395-EReason-RosterRecovery/1.0", "Accept": "*/*"})
TIMEOUT = (6, 25)
CUTOFF = {2016: "20161006225959", 2021: "20210907225959"}

CITY = ["casa", "fes", "marrakech", "sale", "rabat"]
REGION = [
    "rabat-sale-kenitra", "Beni-Mellal-Khenifra", "Casablanca-Settat",
    "dakhla-oued-ed-dahab", "draa-tafilalet", "fes-meknes",
    "laayoune-sakia-hamra", "Marrakech-Safi", "guelmim-oued-noun",
    "oriental", "Souss-Massa", "tanger-tetouan-houceima",
]
URLS_2021 = [f"https://assets.medias24.com/js/carte/election2021/villes/{x}/index.html" for x in CITY] + [f"https://assets.medias24.com/js/carte/election2021/region/{x}/index.html" for x in REGION]

PARTY_ALIASES = {
    "RNI":"RNI", "PAM":"PAM", "PI":"PI", "ISTIQLAL":"PI", "PJD":"PJD",
    "USFP":"USFP", "MP":"MP", "MOUVEMENT POPULAIRE":"MP", "UC":"UC",
    "PPS":"PPS", "PSU":"OTHER", "FGD":"OTHER", "AFG":"OTHER", "FFD":"OTHER",
    "MDS":"OTHER", "PEDD":"OTHER", "PUD":"OTHER", "PARTI DE L AVENIR":"OTHER",
}


def norm(value: str | None) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value)
    value = "".join(c for c in value if not unicodedata.combining(c)).casefold()
    value = value.replace("’", " ").replace("'", " ").replace("-", " ")
    value = re.sub(r"\b(circonscription|province|prefecture|préfecture|region|région|locale|electorale|électorale)\b", " ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def norm_person(value: str | None) -> str:
    x = norm(value)
    substitutions = {
        "mohammed":"mohamed", "mohammad":"mohamed", "mohamad":"mohamed",
        "abdellah":"abdallah", "abdelilah":"abdellah", "mustapha":"mostafa",
        "youssef":"youssef", "yousef":"youssef",
    }
    return " ".join(substitutions.get(t, t) for t in x.split())


def norm_party(value: str) -> str:
    x = norm(value).upper()
    compact = re.sub(r"[^A-Z0-9]", "", x)
    for alias, canonical in PARTY_ALIASES.items():
        if compact == re.sub(r"[^A-Z0-9]", "", alias):
            return canonical
    return "OTHER"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cdx_exact(url: str, year: int) -> list[dict[str, str]]:
    params = {
        "url": url, "output": "json", "fl": "timestamp,original,statuscode,mimetype,digest",
        "filter": "statuscode:200", "to": CUTOFF[year][:8], "limit": "100", "collapse": "digest",
    }
    response = SESSION.get("https://web.archive.org/cdx/search/cdx", params=params, timeout=TIMEOUT)
    response.raise_for_status()
    payload = response.json()
    if not payload or len(payload) < 2:
        return []
    header = payload[0]
    rows = [dict(zip(header, r)) for r in payload[1:] if r[0] <= CUTOFF[year]]
    rows.sort(key=lambda x: x["timestamp"], reverse=True)
    return rows


def cdx_2016_catalog() -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    attempts = [
        {"url":"assets.medias24.com/js/carte/", "matchType":"prefix"},
        {"url":"https://assets.medias24.com/js/carte/*"},
        {"url":"assets.medias24.com/js/carte/*"},
    ]
    diagnostics = []
    collected: dict[str, dict[str, str]] = {}
    for spec in attempts:
        params = {
            **spec, "output":"json", "fl":"timestamp,original,statuscode,mimetype,digest",
            "filter":"statuscode:200", "from":"2016", "to":"2016", "limit":"5000", "collapse":"urlkey",
        }
        try:
            response = SESSION.get("https://web.archive.org/cdx/search/cdx", params=params, timeout=(8, 45))
            diagnostics.append({"params":params,"status":response.status_code,"bytes":len(response.content),"error":None})
            response.raise_for_status()
            payload = response.json()
            if payload and len(payload) > 1:
                header = payload[0]
                for row in payload[1:]:
                    item = dict(zip(header, row))
                    if item.get("timestamp", "") <= CUTOFF[2016]:
                        old = collected.get(item["original"])
                        if old is None or item["timestamp"] > old["timestamp"]:
                            collected[item["original"]] = item
        except Exception as exc:
            diagnostics.append({"params":params,"status":None,"bytes":0,"error":f"{type(exc).__name__}: {exc}"})
    rows = list(collected.values())
    rows.sort(key=lambda x: x["original"])
    return rows, diagnostics


def fetch_snapshot(url: str, timestamp: str) -> tuple[bytes, str, int]:
    archive_url = f"https://web.archive.org/web/{timestamp}id_/{url}"
    response = SESSION.get(archive_url, timeout=TIMEOUT, allow_redirects=True)
    response.raise_for_status()
    return response.content, str(response.url), response.status_code


def candidate_rows_from_html(body: bytes) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    soup = BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
    districts: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    containers = soup.select(".modal") or soup.find_all(["section", "article"])
    if not containers:
        containers = [soup]
    for container in containers:
        heading = container.select_one("h3.modal-title") or container.find(["h2", "h3"])
        if not heading:
            continue
        district = " ".join(heading.get_text(" ", strip=True).split())
        if len(district) < 2:
            continue
        seats = None
        text = container.get_text(" ", strip=True)
        for pattern in (r"(?:Nombre\s+de\s+si[eè]ges|Si[eè]ges?)\s*[:：]?\s*(\d+)", r"(\d+)\s+si[eè]ges"):
            m = re.search(pattern, text, flags=re.I)
            if m:
                seats = int(m.group(1)); break
        start = None
        for h in container.find_all(["h4", "h5", "strong"]):
            if "candidat" in norm(h.get_text(" ", strip=True)):
                start = h
                break
        table = start.find_next("table") if start else container.find("table")
        local = []
        if table:
            for tr in table.find_all("tr"):
                cells = [" ".join(x.get_text(" ", strip=True).split()) for x in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                name, party = cells[0], cells[1]
                if not name or not party or "candidat" in norm(name) or "parti" in norm(party):
                    continue
                if len(norm_person(name).split()) < 2:
                    continue
                row = {"district_source":district,"candidate_name_source":name,"candidate_name_normalized":norm_person(name),"party_source":party,"party_bucket":norm_party(party),"seats_source":seats}
                local.append(row)
        if local:
            districts.append({"district_source":district,"seats_source":seats,"candidate_count":len(local)})
            candidates.extend(local)
    # fallback: tables preceded by a district h3
    if not candidates:
        for h in soup.find_all(["h2", "h3"]):
            district = " ".join(h.get_text(" ", strip=True).split())
            table = h.find_next("table")
            if not table: continue
            local = []
            for tr in table.find_all("tr"):
                cells = [" ".join(x.get_text(" ", strip=True).split()) for x in tr.find_all("td")]
                if len(cells) >= 2 and len(norm_person(cells[0]).split()) >= 2:
                    local.append({"district_source":district,"candidate_name_source":cells[0],"candidate_name_normalized":norm_person(cells[0]),"party_source":cells[1],"party_bucket":norm_party(cells[1]),"seats_source":None})
            if local:
                districts.append({"district_source":district,"seats_source":None,"candidate_count":len(local)})
                candidates.extend(local)
    return districts, candidates


def load_canonical(year: int) -> list[dict[str, Any]]:
    payload = json.loads((HIST / f"tafra_legislative_{year}_canonical.json").read_text(encoding="utf-8"))
    return [r for r in payload["rows"] if r.get("list_type") == "locale"]


def territory_match(source: str, canonical: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, str]:
    s = norm(source)
    exact = []
    for row in canonical:
        labels = [row.get("constituency"), row.get("prefprov")]
        for label in labels:
            if s and s == norm(label):
                exact.append(row)
    unique = {x["id_constituency"]:x for x in exact}
    if len(unique) == 1:
        return next(iter(unique.values())), 1.0, "EXACT_NORMALIZED"
    best = None; best_score = 0.0; second = 0.0
    for row in canonical:
        score = max(SequenceMatcher(None, s, norm(row.get("constituency"))).ratio(), SequenceMatcher(None, s, norm(row.get("prefprov"))).ratio())
        if score > best_score:
            second = best_score; best_score = score; best = row
        elif score > second:
            second = score
    if best and best_score >= 0.82 and best_score - second >= 0.05:
        return best, best_score, "FUZZY_CONSERVATIVE"
    return None, best_score, "UNRESOLVED"


def incumbent_index(year: int) -> dict[str, list[dict[str, Any]]]:
    payload = json.loads((HIST / "b2_historical_elected_members.json").read_text(encoding="utf-8"))
    rows = payload["years"][str(year)]["rows"]
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if row.get("scope") == "local" and row.get("territory_id"):
            out[row["territory_id"]].append(row)
    return out


def match_incumbent(candidate: dict[str, Any], prior: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float]:
    name = candidate["candidate_name_normalized"]
    best = None; score = 0.0
    for row in prior:
        s = SequenceMatcher(None, name, norm_person(row.get("canonical_name_source"))).ratio()
        if s > score:
            score = s; best = row
    if best and (score >= 0.94 or (score >= 0.88 and len(name.split()) >= 3)):
        return best, score
    return None, score


def main() -> int:
    fetched: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    all_districts: list[dict[str, Any]] = []
    catalog, catalog_diag = cdx_2016_catalog()
    (OUT / "cdx_2016_catalog.json").write_text(json.dumps(catalog, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    (OUT / "cdx_2016_diagnostics.json").write_text(json.dumps(catalog_diag, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")

    targets: list[tuple[int,str,dict[str,str]]] = []
    for url in URLS_2021:
        try:
            snaps = cdx_exact(url, 2021)
            if snaps: targets.append((2021,url,snaps[0]))
        except Exception as exc:
            fetched.append({"year":2021,"original_url":url,"error":f"CDX {type(exc).__name__}: {exc}"})
    for item in catalog:
        url = item["original"]
        path = urlparse(url).path.lower()
        if path.endswith(("index.html", ".htm", ".html")) and ("carte" in path or "election" in path or "legisl" in path):
            targets.append((2016,url,item))

    # If broad catalogue is sparse, probe likely 2016 roots discovered from 2021 shape.
    if not any(y == 2016 for y,_,_ in targets):
        roots = ["election2016", "elections2016", "legislatives2016", "election"]
        likely = [f"https://assets.medias24.com/js/carte/{r}/villes/{x}/index.html" for r in roots for x in CITY] + [f"https://assets.medias24.com/js/carte/{r}/region/{x}/index.html" for r in roots for x in REGION]
        for url in likely:
            try:
                snaps = cdx_exact(url, 2016)
                if snaps: targets.append((2016,url,snaps[0]))
            except Exception:
                pass

    seen = set()
    for year, url, snap in targets:
        key = (year,url,snap["timestamp"])
        if key in seen: continue
        seen.add(key)
        try:
            body, final_url, status = fetch_snapshot(url, snap["timestamp"])
            file_sha = digest(body)
            path = RAW / f"{file_sha}.html"
            path.write_bytes(body)
            districts, candidates = candidate_rows_from_html(body)
            for d in districts:
                d.update({"year":year,"original_url":url,"archive_timestamp":snap["timestamp"],"content_sha256":file_sha})
                all_districts.append(d)
            for c in candidates:
                c.update({"year":year,"original_url":url,"archive_timestamp":snap["timestamp"],"content_sha256":file_sha})
                all_candidates.append(c)
            fetched.append({"year":year,"original_url":url,"archive_timestamp":snap["timestamp"],"final_url":final_url,"status":status,"bytes":len(body),"sha256":file_sha,"districts_parsed":len(districts),"candidates_parsed":len(candidates),"error":None})
        except Exception as exc:
            fetched.append({"year":year,"original_url":url,"archive_timestamp":snap.get("timestamp"),"error":f"{type(exc).__name__}: {exc}"})
        time.sleep(0.1)

    enriched = []
    coverage = {}
    for year in (2016,2021):
        canonical = load_canonical(year)
        prior_index = incumbent_index(2011 if year == 2016 else 2016)
        rows = [c for c in all_candidates if c["year"] == year]
        for c in rows:
            territory, score, method = territory_match(c["district_source"], canonical)
            c["territory_match_score"] = round(score,6)
            c["territory_resolution"] = method
            if territory:
                c["id_constituency"] = territory["id_constituency"]
                c["territory_id"] = norm(territory["constituency"]).replace(" ","-")
                c["constituency_canonical"] = territory["constituency"]
                c["region_canonical"] = territory["region"]
                prior = prior_index.get(c["territory_id"], [])
                incumbent, identity_score = match_incumbent(c, prior)
                c["incumbent_match_score"] = round(identity_score,6)
                c["INCUMBENT_SAME_PARTY_SAME_DISTRICT"] = bool(incumbent and incumbent.get("party_code") == c["party_bucket"])
                c["PARTY_SWITCH_IN"] = bool(incumbent and incumbent.get("party_code") != c["party_bucket"] and c["party_bucket"] != "OTHER")
                c["prior_elected_person_id"] = incumbent.get("person_id") if incumbent else None
                if incumbent:
                    enriched.append({"year":year,"territory_id":c["territory_id"],"candidate_name_source":c["candidate_name_source"],"party_bucket":c["party_bucket"],"prior_party":incumbent.get("party_code"),"identity_score":round(identity_score,6),"feature":"INCUMBENT_OR_PARTY_SWITCH"})
            else:
                c["id_constituency"] = None; c["territory_id"] = None; c["constituency_canonical"] = None; c["region_canonical"] = None
                c["INCUMBENT_SAME_PARTY_SAME_DISTRICT"] = False; c["PARTY_SWITCH_IN"] = False; c["prior_elected_person_id"] = None
        by_territory: dict[str,list[dict[str,Any]]] = defaultdict(list)
        for c in rows:
            if c.get("territory_id"):
                by_territory[c["territory_id"]].append(c)
        identity_districts = sum(len({x["candidate_name_normalized"] for x in xs}) >= 3 for xs in by_territory.values())
        enriched_districts = len({x["territory_id"] for x in enriched if x["year"] == year})
        coverage[str(year)] = {
            "candidate_rows":len(rows),
            "source_district_labels":len({x["district_source"] for x in rows}),
            "resolved_canonical_districts":len(by_territory),
            "districts_with_at_least_three_verified_candidate_identities":identity_districts,
            "districts_with_at_least_one_enriched_candidate_fact":enriched_districts,
            "required_identity_districts":70,
            "required_enriched_districts":50,
            "gate_pass":identity_districts >= 70 and enriched_districts >= 50,
        }

    gate_pass = all(coverage[str(y)]["gate_pass"] for y in (2016,2021))
    terminal_if_closed = "E_REASON_COLLECTION_GATE_PASS" if gate_pass else "E_REASON_DATA_INSUFFICIENT_CURRENT_CORPUS"
    (OUT / "fetch_manifest.json").write_text(json.dumps(fetched,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT / "district_records.json").write_text(json.dumps(all_districts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT / "candidate_roster.json").write_text(json.dumps(all_candidates,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (OUT / "enriched_candidate_facts.json").write_text(json.dumps(enriched,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    manifest = {
        "schema_version":"1.0","run_id":RUN_ID,"created_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "cdx_2016_catalog_rows":len(catalog),"target_snapshots":len(targets),"fetched_snapshots":sum(x.get("status")==200 for x in fetched),
        "coverage":coverage,"data_sufficiency_gate_pass":gate_pass,"status":terminal_if_closed,
        "predictive_judgments_generated":False,"forecast_delta_generated":False,"outcomes_unsealed":False,"F1_created":False,"Atlas_UI_modified":False,
    }
    (OUT / "run_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ER / "historical_rosters_latest.json").write_text(json.dumps({"schema_version":"1.0","latest_run_id":RUN_ID,"latest_manifest":str((OUT/"run_manifest.json").relative_to(ROOT)),"latest_roster":str((OUT/"candidate_roster.json").relative_to(ROOT))},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
