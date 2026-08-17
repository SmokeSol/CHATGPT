#!/usr/bin/env python3
"""Deterministic historical acquisition under the frozen V1.1 source surface.

Enumeration only. Every route comes from `historical_source_surface_v1_1.json`,
which was frozen and hashed before this script was allowed to run. Retention is
by exact substring match on fixed terms; nothing is ranked, judged or read for
meaning.

Two honesty rules carry most of the weight here:

  * A result set whose length equals the requested limit is TRUNCATED, and a
    truncated scan can never support a claim of exhaustion.
  * A 403, challenge, timeout or empty capture list is BLOCKED_SOURCE or
    NO_CAPTURES, never absence of the underlying document.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SURFACE_PATH = G100 / "historical_source_surface_v1_1.json"
CERTIFICATE_PATH = G100 / "historical_source_surface_certificate.json"
VAULT_DIR = G100 / "b2_raw_acquisition"
MANIFEST_PATH = G100 / "b2_historical_v1_1_acquisition_manifest.json"

USER_AGENT = "Mozilla/5.0 (compatible; MOROCCO26-B2-acquirer/1.1)"
TIMEOUT_SECONDS = 45
CDX_TIMEOUT_SECONDS = 25
MAX_BYTES = 64 * 1024 * 1024
CHALLENGE_MARKERS = ("just a moment", "one moment, please", "cf-chl", "captcha")
BLOCKED_STATUSES = {401, 403, 429, 451}


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_V1_1_ACQUIRE_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def environment() -> dict:
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "runner": "GITHUB_ACTIONS" if os.environ.get("GITHUB_ACTIONS") else "LOCAL",
        "user_agent": USER_AGENT,
    }


def fetch(url: str, timeout: int = TIMEOUT_SECONDS) -> dict:
    record = {
        "url": url, "retrieved_at": now_local(), "http_status": None, "final_url": None,
        "content_type": None, "content_length": None, "sha256": None,
        "state": None, "error": None, "body": None,
    }
    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                record.update(state="BLOCKED_SOURCE", error="RESPONSE_EXCEEDS_MAX_BYTES")
                return record
            record.update(
                http_status=response.status, final_url=response.url,
                content_type=response.headers.get("Content-Type"),
                content_length=len(body), sha256=hashlib.sha256(body).hexdigest(), body=body,
            )
            head = body[:4096].decode("utf-8", "ignore").casefold()
            if any(marker in head for marker in CHALLENGE_MARKERS):
                record.update(state="BLOCKED_SOURCE", error="CHALLENGE_MARKER_PRESENT", body=None)
            else:
                record["state"] = "ACQUIRED"
    except urllib.error.HTTPError as exc:
        record.update(http_status=exc.code, error=f"HTTPError {exc.code}",
                      state="BLOCKED_SOURCE" if exc.code in BLOCKED_STATUSES else "FETCH_ERROR")
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        record.update(state="BLOCKED_SOURCE", error=f"{type(exc).__name__}: {str(exc)[:200]}")
    return record


def store(record: dict, source_id: str, bucket: str, filename: str) -> str | None:
    if record.get("body") is None:
        return None
    target = VAULT_DIR / source_id / bucket / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(record["body"])
    dump(target.with_suffix(target.suffix + ".meta.json"), {
        "source_id": source_id, "bucket": bucket, "original_url": record["url"],
        "final_url": record["final_url"], "retrieved_at": record["retrieved_at"],
        "http_status": record["http_status"], "content_type": record["content_type"],
        "content_length": record["content_length"], "sha256": record["sha256"],
        "environment": environment(),
        "immutability": "RAW_BYTES_NEVER_REPLACED_BY_PARSER_OUTPUT",
    })
    return target.relative_to(REPO).as_posix()


def strip_body(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "body"}


def acquire_openafrica(source: dict) -> list[dict]:
    method = source["deterministic_enumeration_method"]
    rows_per_page = int(method["rows_per_page"])
    max_pages = int(method["max_pages_per_term"])
    entries, packages = [], {}

    for term in sorted(method["fixed_terms"]):
        for page in range(max_pages):
            start = page * rows_per_page
            url = (
                f"https://{source['root']}/api/3/action/package_search"
                f"?q={urllib.parse.quote(term)}&rows={rows_per_page}&start={start}"
            )
            got = fetch(url)
            entry = {
                **strip_body(got), "source_id": source["source_id"],
                "purpose": "CKAN_PACKAGE_SEARCH", "term": term, "page": page,
                "stored_path": store(got, source["source_id"], "catalog",
                                     f"search_{term}_{page}.json"),
            }
            if got["state"] == "ACQUIRED":
                try:
                    payload = json.loads(got["body"]).get("result", {})
                    results = payload.get("results", [])
                    entry["result_count"] = len(results)
                    entry["reported_total"] = payload.get("count")
                    entry["truncated"] = len(results) == rows_per_page
                    for package in results:
                        packages[package.get("name", "")] = {
                            "name": package.get("name"),
                            "title": package.get("title"),
                            "organization": (package.get("organization") or {}).get("name"),
                            "resource_formats": sorted(
                                {str(r.get("format") or "").upper() for r in package.get("resources", [])}
                            ),
                        }
                except (json.JSONDecodeError, TypeError, AttributeError):
                    entry["error"] = "SEARCH_PAYLOAD_NOT_JSON"
            entries.append(entry)
            if entry.get("result_count", 0) < rows_per_page:
                break

    entries.append({
        "source_id": source["source_id"], "purpose": "CATALOG_INVENTORY",
        "retrieved_at": now_local(), "state": "INVENTORY",
        "distinct_packages": len(packages),
        "packages": [packages[key] for key in sorted(packages)],
        "url": None, "sha256": None, "stored_path": None,
    })
    return entries


def acquire_huggingface(source: dict) -> list[dict]:
    method = source["deterministic_enumeration_method"]
    limit = int(method["limit"])
    entries, datasets = [], {}

    for term in sorted(method["fixed_terms"]):
        url = (
            f"https://{source['root']}/api/datasets"
            f"?author={urllib.parse.quote(source['organization'])}"
            f"&search={urllib.parse.quote(term)}&limit={limit}"
        )
        got = fetch(url)
        entry = {
            **strip_body(got), "source_id": source["source_id"],
            "purpose": "HF_ORG_DATASET_SEARCH", "term": term,
            "stored_path": store(got, source["source_id"], "catalog", f"search_{term}.json"),
        }
        if got["state"] == "ACQUIRED":
            try:
                results = json.loads(got["body"])
                entry["result_count"] = len(results)
                # A full page is indistinguishable from a truncated one.
                entry["truncated"] = len(results) >= limit
                for item in results:
                    datasets[item["id"]] = {"id": item["id"]}
            except (json.JSONDecodeError, TypeError, KeyError):
                entry["error"] = "SEARCH_PAYLOAD_NOT_JSON"
        entries.append(entry)

    entries.append({
        "source_id": source["source_id"], "purpose": "CATALOG_INVENTORY",
        "retrieved_at": now_local(), "state": "INVENTORY",
        "distinct_datasets": len(datasets),
        "datasets": sorted(datasets),
        "url": None, "sha256": None, "stored_path": None,
    })
    return entries


def acquire_web_archive(source: dict, cutoffs: dict) -> list[dict]:
    method = source["deterministic_enumeration_method"]
    limit = int(method["limit"])
    entries = []

    for domain in sorted(source["mirrored_domains"]):
        for year in sorted(int(y) for y in cutoffs):
            cutoff = cutoffs[str(year)]
            to_ts = cutoff[:10].replace("-", "")
            from_ts = f"{year}0101"
            url = (
                f"https://{source['root']}/cdx/search/cdx"
                f"?url={urllib.parse.quote(domain)}%2F*&output=json"
                f"&from={from_ts}&to={to_ts}&limit={limit}"
            )
            got = fetch(url, timeout=CDX_TIMEOUT_SECONDS)
            entry = {
                **strip_body(got), "source_id": source["source_id"],
                "purpose": "WAYBACK_CDX_PRECUTOFF_ENUMERATION",
                "domain": domain, "election_year": year,
                "window_from": from_ts, "window_to": to_ts,
                "stored_path": store(got, source["source_id"], f"cdx/{year}",
                                     f"{domain.replace('.', '_')}.json"),
            }
            if got["state"] == "ACQUIRED":
                try:
                    rows = json.loads(got["body"])
                    captures = max(0, len(rows) - 1)  # first row is the header
                    entry["capture_count"] = captures
                    entry["truncated"] = captures >= limit
                    if captures == 0:
                        entry["state"] = "NO_CAPTURES"
                        entry["error"] = "NO_PRE_CUTOFF_CAPTURE_IN_WINDOW"
                except (json.JSONDecodeError, TypeError):
                    entry["capture_count"] = 0
                    entry["error"] = "CDX_PAYLOAD_NOT_JSON"
            entries.append(entry)
    return entries


def write_manifest(entries: list[dict], surface: dict, certificate: dict, complete: bool) -> dict:
    truncated = [
        {"source_id": row["source_id"], "term": row.get("term"), "purpose": row["purpose"]}
        for row in entries if row.get("truncated")
    ]
    manifest = {
        "schema_version": "1.1",
        "manifest_id": "M26-GOAL100-B2-HISTORICAL-V1-1-ACQUISITION",
        "run_at": now_local(),
        "run_complete": complete,
        "append_only": True,
        "source_surface_sha256": surface["canonical_surface_sha256"],
        "certificate_sha256": certificate["canonical_certificate_sha256"],
        "environment": environment(),
        "determinism": {"llm_used": False, "semantic_selection": False, "ranking_used": False},
        "absence_rule": (
            "BLOCKED_SOURCE, FETCH_ERROR and NO_CAPTURES describe access, never absence. A truncated "
            "or incomplete enumeration can never support a claim of exhaustion."
        ),
        "counts": {
            "entries": len(entries),
            "acquired": sum(row.get("state") == "ACQUIRED" for row in entries),
            "blocked": sum(row.get("state") == "BLOCKED_SOURCE" for row in entries),
            "errors": sum(row.get("state") == "FETCH_ERROR" for row in entries),
            "no_captures": sum(row.get("state") == "NO_CAPTURES" for row in entries),
            "truncated_enumerations": len(truncated),
        },
        "truncated_enumerations": truncated,
        "entries": entries,
    }
    manifest["canonical_manifest_sha256"] = canonical_sha256(
        {k: v for k, v in manifest.items() if k != "canonical_manifest_sha256"}
    )
    dump(MANIFEST_PATH, manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.parse_args()

    surface = load(SURFACE_PATH)
    certificate = load(CERTIFICATE_PATH)
    if surface["status"] != "FROZEN_PRE_ACQUISITION":
        raise SystemExit("B2_V1_1_ACQUIRE_FAIL: source surface is not frozen")
    if certificate["gate"] != "PASS":
        raise SystemExit("B2_V1_1_ACQUIRE_FAIL: source-surface certificate is not PASS")
    if certificate["source_surface_sha256"] != surface["canonical_surface_sha256"]:
        raise SystemExit("B2_V1_1_ACQUIRE_FAIL: certificate does not match the frozen surface")

    cutoffs = surface["time_contract"]["election_cutoffs"]
    handlers = {
        "H1_OPENAFRICA_CATALOG": acquire_openafrica,
        "H2_HUGGINGFACE_ELECTRICSHEEPAFRICA": acquire_huggingface,
    }

    entries = []
    for source in surface["sources"]:
        if source["source_id"] in handlers:
            entries += handlers[source["source_id"]](source)
        elif source["source_id"] == "H3_WEB_ARCHIVE_OF_REGISTERED_DOMAINS":
            entries += acquire_web_archive(source, cutoffs)
        # Checkpoint: a killed run must never discard the work already done.
        write_manifest(entries, surface, certificate, complete=False)

    manifest = write_manifest(entries, surface, certificate, complete=True)

    print("B2_V1_1_HISTORICAL_ACQUISITION_COMPLETE")
    for key, value in manifest["counts"].items():
        print(f"  {key:<24} {value}")


if __name__ == "__main__":
    main()
