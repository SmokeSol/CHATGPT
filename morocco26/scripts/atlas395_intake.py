#!/usr/bin/env python3
"""Atlas 395 daily public-source intake.

Product-side watch only. It NEVER writes MOROCCO//26 scientific artifacts and
NEVER changes a forecast. It uses the certified B2 acquisition surface as a
whitelist, discovers recent pages only inside those domains, and stores compact,
auditable detections for Atlas' public watch layer.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import ssl
import socket
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Casablanca")
UA = "Mozilla/5.0 (compatible; Atlas395-DailyWatch/0.5; +public-election-monitoring)"
TIMEOUT = 18
MAX_BYTES = 5 * 1024 * 1024
DISCOVERY_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/feed", "/feed.xml", "/rss", "/rss.xml")

KEYWORDS = (
    "election", "élection", "elections", "élections", "legislative", "législative",
    "legislatives", "législatives", "candidat", "candidate", "candidature", "candidats",
    "liste", "listes", "investiture", "circonscription", "ralliement", "alliance",
    "defection", "défection", "transhumance", "tete de liste", "tête de liste",
    "23 septembre", "2026", "chambre des representants", "chambre des représentants",
)
PARTY_TERMS = ("rni", "pam", "pjd", "usfp", "pps", "istiqlal", "mouvement populaire", "union constitutionnelle")


def now_local() -> datetime:
    return datetime.now(TZ)


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def norm_url(url: str) -> str:
    p = urlparse(url)
    path = re.sub(r"/+", "/", p.path or "/")
    return p._replace(fragment="", path=path).geturl()


def host_allowed(url: str, domains: set[str]) -> bool:
    h = (urlparse(url).hostname or "").lower()
    return h in domains


def fetch(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,application/rss+xml,application/atom+xml,application/pdf;q=0.6,*/*;q=0.2"})
    out = {"url": url, "status": None, "content_type": None, "body": None, "error": None, "final_url": None}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as r:
            b = r.read(MAX_BYTES + 1)
            if len(b) > MAX_BYTES:
                out["error"] = "TOO_LARGE"
                return out
            out.update(status=getattr(r, "status", 200), content_type=(r.headers.get("Content-Type") or "").split(";")[0].lower(), body=b, final_url=r.geturl())
    except urllib.error.HTTPError as e:
        out.update(status=e.code, error=f"HTTP_{e.code}")
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as e:
        out["error"] = f"{type(e).__name__}:{str(e)[:120]}"
    return out


def decode(body: bytes | None) -> str:
    if not body:
        return ""
    for enc in ("utf-8", "windows-1252", "iso-8859-1"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            pass
    return body.decode("utf-8", "ignore")


def strip_html(text: str) -> str:
    text = re.sub(r"(?is)<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def title_from_html(text: str) -> str:
    for pat in (r"(?is)<h1[^>]*>(.*?)</h1>", r"(?is)<title[^>]*>(.*?)</title>"):
        m = re.search(pat, text)
        if m:
            return strip_html(m.group(1))[:240]
    return ""


def links_from_html(base: str, text: str, domains: set[str]) -> list[str]:
    links = []
    for raw in re.findall(r"(?is)href=[\"']([^\"'#]+)", text):
        u = norm_url(urljoin(base, html.unescape(raw.strip())))
        if host_allowed(u, domains) and any(k in u.casefold() for k in KEYWORDS):
            links.append(u)
    return links


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    s = value.strip()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return parsedate_to_datetime(s)
        except Exception:
            return None


def xml_links(base: str, body: bytes, domains: set[str], cutoff: datetime) -> tuple[list[str], list[str]]:
    pages, child_maps = [], []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return pages, child_maps
    tag = root.tag.casefold()
    if tag.endswith("sitemapindex"):
        for node in root:
            loc = next((c.text for c in node if c.tag.casefold().endswith("loc")), None)
            last = next((c.text for c in node if c.tag.casefold().endswith("lastmod")), None)
            if loc:
                u = norm_url(urljoin(base, loc.strip()))
                d = parse_date(last)
                if host_allowed(u, domains) and (d is None or d >= cutoff - timedelta(days=30) or any(k in u.casefold() for k in ("post", "news", "actual", "article"))):
                    child_maps.append(u)
    elif tag.endswith("urlset"):
        for node in root:
            loc = next((c.text for c in node if c.tag.casefold().endswith("loc")), None)
            last = next((c.text for c in node if c.tag.casefold().endswith("lastmod")), None)
            if not loc:
                continue
            u = norm_url(urljoin(base, loc.strip()))
            d = parse_date(last)
            if host_allowed(u, domains) and ((d and d >= cutoff) or any(k in u.casefold() for k in KEYWORDS)):
                pages.append(u)
    else:  # RSS / Atom
        for item in root.iter():
            t = item.tag.casefold()
            if t.endswith("item") or t.endswith("entry"):
                loc = None; date = None
                for c in item:
                    ct = c.tag.casefold()
                    if ct.endswith("link"):
                        loc = c.attrib.get("href") or c.text
                    elif ct.endswith("pubdate") or ct.endswith("published") or ct.endswith("updated"):
                        date = c.text
                if loc:
                    u = norm_url(urljoin(base, loc.strip()))
                    d = parse_date(date)
                    if host_allowed(u, domains) and (d is None or d >= cutoff):
                        pages.append(u)
    return pages, child_maps


def relevant(title: str, text: str, url: str) -> tuple[bool, int]:
    hay = f"{title} {text[:18000]} {url}".casefold()
    hits = sum(1 for k in KEYWORDS if k in hay)
    party = sum(1 for k in PARTY_TERMS if k in hay)
    hard = any(k in hay for k in ("élection", "election", "législative", "legislative", "candidat", "candidature", "circonscription"))
    return (hard and hits >= 2) or ("2026" in hay and hits >= 3) or (party >= 1 and hits >= 3), hits + party


def collect(surface: dict, out_dir: Path, days_back: int, max_per_source: int) -> dict:
    now = now_local(); cutoff = now - timedelta(days=days_back)
    observations, probes = [], []
    rows = [x for x in surface.get("surfaces", []) if x.get("surface_family") == "B2_SOURCE_REGISTRY_V1" and x.get("claim_eligible") and x.get("access_status") == "ACTIVE"]
    for row in sorted(rows, key=lambda x: x.get("source_id", "")):
        sid = row["source_id"]; domains = {d.lower() for d in row.get("root_domains", [])}
        candidates = []
        seeds = [norm_url(u) for u in row.get("seed_urls", [])]
        candidates.extend(seeds)
        for seed in seeds[:3]:
            got = fetch(seed); probes.append({"source":sid,"url":seed,"status":got["status"],"error":got["error"]})
            if got["body"] and "html" in (got["content_type"] or ""):
                candidates.extend(links_from_html(got["final_url"] or seed, decode(got["body"]), domains))
        canonical = sorted(domains)[0] if domains else None
        if canonical:
            for p in DISCOVERY_PATHS:
                u = f"https://{canonical}{p}"
                got = fetch(u); probes.append({"source":sid,"url":u,"status":got["status"],"error":got["error"]})
                if got["body"] and ("xml" in (got["content_type"] or "") or p.endswith(("xml","feed","rss"))):
                    pages, maps = xml_links(got["final_url"] or u, got["body"], domains, cutoff)
                    candidates.extend(pages)
                    for child in maps[:5]:
                        cg = fetch(child); probes.append({"source":sid,"url":child,"status":cg["status"],"error":cg["error"]})
                        if cg["body"]:
                            ps, _ = xml_links(cg["final_url"] or child, cg["body"], domains, cutoff)
                            candidates.extend(ps)
        seen = set(); ordered = []
        for u in candidates:
            u = norm_url(u)
            if u not in seen and host_allowed(u, domains):
                seen.add(u); ordered.append(u)
        for u in ordered[:max_per_source]:
            got = fetch(u); probes.append({"source":sid,"url":u,"status":got["status"],"error":got["error"]})
            if not got["body"]:
                continue
            ctype = got["content_type"] or ""
            if "html" not in ctype and "text" not in ctype and "xml" not in ctype:
                continue
            raw = decode(got["body"]); text = strip_html(raw); title = title_from_html(raw)
            ok, score = relevant(title, text, u)
            if not ok:
                continue
            digest = hashlib.sha256(got["body"]).hexdigest()
            observations.append({
                "id": f"INTAKE-{digest[:16]}", "source_id": sid, "publisher": row.get("publisher"),
                "url": got["final_url"] or u, "retrieved_at": now.isoformat(timespec="seconds"),
                "content_sha256": digest, "title": title or (text[:120] + ("…" if len(text)>120 else "")),
                "snippet": text[:600], "relevance_score": score,
                "status": "DETECTED_UNVERIFIED", "forecast_impact": "NONE",
            })
    uniq = {}
    for o in observations:
        uniq[(o["source_id"], o["content_sha256"])] = o
    observations = sorted(uniq.values(), key=lambda x:(-x["relevance_score"], x["source_id"], x["url"]))
    payload = {
        "schema_version":"0.5", "run_at":now.isoformat(timespec="seconds"),
        "source_surface_id":surface.get("surface_id"), "active_sources_scanned":len(rows),
        "detections":observations, "detection_count":len(observations),
        "probe_count":len(probes), "probe_failures":sum(1 for p in probes if p["error"]),
        "contract":{"product_watch_only":True,"writes_science":False,"may_change_forecast":False,"validation_required_before_forecast_effect":True},
    }
    day = now.date().isoformat()
    day_path = out_dir / "runs" / f"{day}.json"
    if not day_path.exists():
        dump(day_path, payload)
    dump(out_dir / "latest.json", payload)
    index_path = out_dir / "index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {"runs":[]}
    if not any(x.get("date") == day for x in index["runs"]):
        index["runs"].append({"date":day,"run_at":payload["run_at"],"detections":payload["detection_count"],"active_sources":payload["active_sources_scanned"]})
        index["runs"].sort(key=lambda x:x["date"])
    dump(index_path, index)
    return payload


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--surface", required=True)
    ap.add_argument("--out", default="morocco26/atlas395/intake")
    ap.add_argument("--days-back", type=int, default=4)
    ap.add_argument("--max-per-source", type=int, default=30)
    args = ap.parse_args()
    surface = json.loads(Path(args.surface).read_text(encoding="utf-8"))
    result = collect(surface, Path(args.out), args.days_back, args.max_per_source)
    print(f"ATLAS395_INTAKE_OK sources={result['active_sources_scanned']} detections={result['detection_count']} probes={result['probe_count']} failures={result['probe_failures']}")

if __name__ == "__main__":
    main()
