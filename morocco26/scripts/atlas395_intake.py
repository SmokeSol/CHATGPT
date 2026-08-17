#!/usr/bin/env python3
"""Atlas 395 daily public-source intake.

Product-side watch only. It never writes MOROCCO//26 scientific artifacts and
never changes a forecast. The scientific B2 surface supplies locators; the
product source policy applies a stricter, fail-closed reader allowlist.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import socket
import ssl
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
TIMEOUT = 12
MAX_BYTES = 5 * 1024 * 1024
ACTIVE_DISCOVERY_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml", "/feed", "/rss.xml")
LIMITED_DISCOVERY_PATHS = ("/sitemap.xml", "/feed")

KEYWORDS = (
    "election", "élection", "elections", "élections", "legislative", "législative",
    "legislatives", "législatives", "candidat", "candidate", "candidature", "candidats",
    "liste", "listes", "investiture", "circonscription", "ralliement", "alliance",
    "defection", "défection", "transhumance", "tete de liste", "tête de liste",
    "23 septembre", "2026", "chambre des representants", "chambre des représentants",
)
PARTY_TERMS = (
    "rni", "pam", "pjd", "usfp", "pps", "istiqlal", "mouvement populaire",
    "union constitutionnelle",
)


def now_local() -> datetime:
    return datetime.now(TZ)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_policy(surface: dict, policy: dict) -> tuple[set[str], str]:
    if policy.get("default_decision") != "DENY":
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: default decision must be DENY")
    allowed = {str(x) for x in policy.get("authorized_source_ids") or []}
    media = {str(x) for x in policy.get("authorized_media_source_ids") or []}
    if media != {"T2_MEDIAS24"}:
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: Médias24 must be the sole authorized media source")
    if any(x.startswith("T2_") and x not in media for x in allowed):
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: unauthorized media present in allowlist")
    if any(not (x.startswith("T0_") or x.startswith("T1_") or x == "T2_MEDIAS24") for x in allowed):
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: allowlist contains a non-official/non-authorized source")
    registry_ids = {
        str(x.get("source_id"))
        for x in surface.get("surfaces", [])
        if x.get("surface_family") == "B2_SOURCE_REGISTRY_V1"
    }
    missing = sorted(allowed - registry_ids)
    if missing:
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: source ids absent from certified surface: " + ", ".join(missing))
    forbidden = set(policy.get("explicitly_forbidden_media_source_ids") or [])
    if allowed & forbidden:
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: source is both authorized and forbidden")
    return allowed, canonical_sha256(policy)


def source_role(source_id: str) -> str:
    if source_id.startswith("T0_"):
        return "INSTITUTIONAL_OFFICIAL_WITHIN_COMPETENCE"
    if source_id.startswith("T1_"):
        return "OFFICIAL_PARTY_PRIMARY_BUT_INTERESTED"
    if source_id == "T2_MEDIAS24":
        return "MEDIA_MONITORING_AND_CORROBORATION_ONLY"
    raise SystemExit(f"ATLAS395_SOURCE_POLICY_FAIL: unexpected source {source_id}")


def norm_url(url: str) -> str:
    p = urlparse(url)
    path = re.sub(r"/+", "/", p.path or "/")
    return p._replace(fragment="", path=path).geturl()


def host_allowed(url: str, domains: set[str]) -> bool:
    return (urlparse(url).hostname or "").lower() in domains


def fetch(url: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": UA,
            "Accept": "text/html,application/xhtml+xml,application/xml,text/xml,application/rss+xml,application/atom+xml,application/pdf;q=0.6,*/*;q=0.2",
        },
    )
    out = {"url": url, "status": None, "content_type": None, "body": None, "error": None, "final_url": None}
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT, context=ssl.create_default_context()) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                out["error"] = "TOO_LARGE"
                return out
            out.update(
                status=getattr(response, "status", 200),
                content_type=(response.headers.get("Content-Type") or "").split(";")[0].lower(),
                body=body,
                final_url=response.geturl(),
            )
    except urllib.error.HTTPError as exc:
        out.update(status=exc.code, error=f"HTTP_{exc.code}")
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        out["error"] = f"{type(exc).__name__}:{str(exc)[:120]}"
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
    for pattern in (r"(?is)<h1[^>]*>(.*?)</h1>", r"(?is)<title[^>]*>(.*?)</title>"):
        match = re.search(pattern, text)
        if match:
            return strip_html(match.group(1))[:240]
    return ""


def links_from_html(base: str, text: str, domains: set[str]) -> list[str]:
    links = []
    for raw in re.findall(r"(?is)href=[\"']([^\"'#]+)", text):
        url = norm_url(urljoin(base, html.unescape(raw.strip())))
        if host_allowed(url, domains) and any(keyword in url.casefold() for keyword in KEYWORDS):
            links.append(url)
    return links


def parse_date(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return parsedate_to_datetime(value.strip())
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
            loc = next((child.text for child in node if child.tag.casefold().endswith("loc")), None)
            last = next((child.text for child in node if child.tag.casefold().endswith("lastmod")), None)
            if not loc:
                continue
            url = norm_url(urljoin(base, loc.strip()))
            date = parse_date(last)
            if host_allowed(url, domains) and (
                date is None or date >= cutoff - timedelta(days=30) or any(x in url.casefold() for x in ("post", "news", "actual", "article"))
            ):
                child_maps.append(url)
    elif tag.endswith("urlset"):
        for node in root:
            loc = next((child.text for child in node if child.tag.casefold().endswith("loc")), None)
            last = next((child.text for child in node if child.tag.casefold().endswith("lastmod")), None)
            if not loc:
                continue
            url = norm_url(urljoin(base, loc.strip()))
            date = parse_date(last)
            if host_allowed(url, domains) and ((date and date >= cutoff) or any(k in url.casefold() for k in KEYWORDS)):
                pages.append(url)
    else:
        for item in root.iter():
            if not (item.tag.casefold().endswith("item") or item.tag.casefold().endswith("entry")):
                continue
            loc = None
            date = None
            for child in item:
                child_tag = child.tag.casefold()
                if child_tag.endswith("link"):
                    loc = child.attrib.get("href") or child.text
                elif child_tag.endswith("pubdate") or child_tag.endswith("published") or child_tag.endswith("updated"):
                    date = child.text
            if loc:
                url = norm_url(urljoin(base, loc.strip()))
                parsed = parse_date(date)
                if host_allowed(url, domains) and (parsed is None or parsed >= cutoff):
                    pages.append(url)
    return pages, child_maps


def relevant(title: str, text: str, url: str) -> tuple[bool, int]:
    haystack = f"{title} {text[:18000]} {url}".casefold()
    hits = sum(1 for keyword in KEYWORDS if keyword in haystack)
    party_hits = sum(1 for term in PARTY_TERMS if term in haystack)
    hard = any(term in haystack for term in ("élection", "election", "législative", "legislative", "candidat", "candidature", "circonscription"))
    return (hard and hits >= 2) or ("2026" in haystack and hits >= 3) or (party_hits >= 1 and hits >= 3), hits + party_hits


def collect(surface: dict, policy: dict, out_dir: Path, days_back: int, max_per_source: int) -> dict:
    allowed, policy_sha = validate_policy(surface, policy)
    now = now_local()
    day = now.date().isoformat()
    run_id = f"{day}--{policy_sha[:12]}"
    run_path = out_dir / "runs" / f"{run_id}.json"
    if run_path.exists():
        existing = load(run_path)
        dump(out_dir / "latest.json", existing)
        print(f"ATLAS395_INTAKE_REUSE run={run_id} detections={existing.get('detection_count', 0)}")
        return existing

    cutoff = now - timedelta(days=days_back)
    registry_rows = [
        row for row in surface.get("surfaces", [])
        if row.get("surface_family") == "B2_SOURCE_REGISTRY_V1"
    ]
    rows = [row for row in registry_rows if row.get("source_id") in allowed]
    observations: list[dict] = []
    probes: list[dict] = []
    per_source: list[dict] = []

    for row in sorted(rows, key=lambda item: item.get("source_id", "")):
        source_id = str(row["source_id"])
        domains = {str(domain).lower() for domain in row.get("root_domains", [])}
        candidates: list[str] = []
        seeds = [norm_url(url) for url in row.get("seed_urls", [])]
        candidates.extend(seeds)
        source_probe_start = len(probes)
        source_detection_start = len(observations)

        for seed in seeds[:3]:
            got = fetch(seed)
            probes.append({"source": source_id, "url": seed, "status": got["status"], "error": got["error"]})
            if got["body"] and "html" in (got["content_type"] or ""):
                candidates.extend(links_from_html(got["final_url"] or seed, decode(got["body"]), domains))

        canonical = sorted(domains)[0] if domains else None
        registry_active = row.get("access_status") == "ACTIVE" and bool(row.get("claim_eligible"))
        discovery_paths = ACTIVE_DISCOVERY_PATHS if registry_active else LIMITED_DISCOVERY_PATHS
        if canonical:
            for path in discovery_paths:
                url = f"https://{canonical}{path}"
                got = fetch(url)
                probes.append({"source": source_id, "url": url, "status": got["status"], "error": got["error"]})
                if got["body"] and ("xml" in (got["content_type"] or "") or path.endswith(("xml", "feed", "rss"))):
                    pages, maps = xml_links(got["final_url"] or url, got["body"], domains, cutoff)
                    candidates.extend(pages)
                    for child in maps[: (5 if registry_active else 1)]:
                        child_got = fetch(child)
                        probes.append({"source": source_id, "url": child, "status": child_got["status"], "error": child_got["error"]})
                        if child_got["body"]:
                            child_pages, _ = xml_links(child_got["final_url"] or child, child_got["body"], domains, cutoff)
                            candidates.extend(child_pages)

        seen: set[str] = set()
        ordered: list[str] = []
        for url in candidates:
            normalized = norm_url(url)
            if normalized not in seen and host_allowed(normalized, domains):
                seen.add(normalized)
                ordered.append(normalized)

        fetch_limit = max_per_source if registry_active else min(max_per_source, 8)
        for url in ordered[:fetch_limit]:
            got = fetch(url)
            probes.append({"source": source_id, "url": url, "status": got["status"], "error": got["error"]})
            if not got["body"]:
                continue
            content_type = got["content_type"] or ""
            if "html" not in content_type and "text" not in content_type and "xml" not in content_type:
                continue
            raw = decode(got["body"])
            text = strip_html(raw)
            title = title_from_html(raw)
            is_relevant, score = relevant(title, text, url)
            if not is_relevant:
                continue
            digest = hashlib.sha256(got["body"]).hexdigest()
            observations.append({
                "id": f"INTAKE-{digest[:16]}",
                "source_id": source_id,
                "publisher": row.get("publisher"),
                "source_role": source_role(source_id),
                "url": got["final_url"] or url,
                "retrieved_at": now.isoformat(timespec="seconds"),
                "content_sha256": digest,
                "title": title or (text[:120] + ("…" if len(text) > 120 else "")),
                "snippet": text[:600],
                "relevance_score": score,
                "status": "DETECTED_UNVERIFIED",
                "verification_state": "PENDING_PRIMARY_OR_INDEPENDENT_CORROBORATION",
                "forecast_impact": "NONE",
            })

        source_probes = probes[source_probe_start:]
        per_source.append({
            "source_id": source_id,
            "publisher": row.get("publisher"),
            "source_role": source_role(source_id),
            "registry_access_status": row.get("access_status"),
            "registry_claim_eligible": bool(row.get("claim_eligible")),
            "probe_count": len(source_probes),
            "probe_failures": sum(1 for probe in source_probes if probe.get("error")),
            "detections": len(observations) - source_detection_start,
        })

    unique: dict[tuple[str, str], dict] = {}
    for observation in observations:
        if observation["source_id"] not in allowed:
            raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: disallowed detection escaped intake")
        unique[(observation["source_id"], observation["content_sha256"])] = observation
    observations = sorted(unique.values(), key=lambda item: (-item["relevance_score"], item["source_id"], item["url"]))

    payload = {
        "schema_version": "0.5",
        "run_id": run_id,
        "run_at": now.isoformat(timespec="seconds"),
        "source_surface_id": surface.get("surface_id"),
        "source_policy_id": policy.get("policy_id"),
        "source_policy_sha256": policy_sha,
        "authorized_source_ids": sorted(allowed),
        "authorized_media_source_ids": sorted(policy.get("authorized_media_source_ids") or []),
        "authorized_sources_scanned": len(rows),
        "active_sources_scanned": len(rows),
        "disallowed_registry_sources_ignored": len(registry_rows) - len(rows),
        "per_source": per_source,
        "detections": observations,
        "detection_count": len(observations),
        "probe_count": len(probes),
        "probe_failures": sum(1 for probe in probes if probe.get("error")),
        "contract": {
            "product_watch_only": True,
            "writes_science": False,
            "may_change_forecast": False,
            "validation_required_before_forecast_effect": True,
            "sole_authorized_media": "T2_MEDIAS24",
            "default_source_decision": "DENY",
        },
    }
    dump(run_path, payload)
    dump(out_dir / "latest.json", payload)
    index_path = out_dir / "index.json"
    index = load(index_path) if index_path.exists() else {"schema_version": "1.0", "runs": []}
    if not any(row.get("run_id") == run_id for row in index.get("runs", [])):
        index.setdefault("runs", []).append({
            "run_id": run_id,
            "date": day,
            "run_at": payload["run_at"],
            "source_policy_id": payload["source_policy_id"],
            "detections": payload["detection_count"],
            "authorized_sources": payload["authorized_sources_scanned"],
        })
        index["runs"].sort(key=lambda row: (row.get("date", ""), row.get("run_at", ""), row.get("run_id", "")))
    dump(index_path, index)
    return payload


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--out", default="morocco26/atlas395/intake")
    parser.add_argument("--days-back", type=int, default=4)
    parser.add_argument("--max-per-source", type=int, default=30)
    args = parser.parse_args()
    result = collect(load(Path(args.surface)), load(Path(args.policy)), Path(args.out), args.days_back, args.max_per_source)
    print(
        "ATLAS395_INTAKE_OK "
        f"policy={result['source_policy_id']} sources={result['authorized_sources_scanned']} "
        f"detections={result['detection_count']} probes={result['probe_count']} failures={result['probe_failures']}"
    )


if __name__ == "__main__":
    main()
