#!/usr/bin/env python3
"""Deterministic acquisition against the frozen surface, into an immutable raw vault.

Every fetch is driven by a locator that already exists in
`b2_deterministic_acquisition_surface.json`. There is no search, no ranking and
no semantic selection: the enumerator walks recorded routes in lexicographic
order and records exactly what came back.

Failure is never absence. A 403, a WAF challenge, a timeout or a DNS error is
recorded as BLOCKED_SOURCE together with the environment that observed it, so a
local network restriction can never be mistaken for a missing document.

Usage:
    goal100_b2_acquire.py --historical
    goal100_b2_acquire.py --wave1
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
import urllib.request
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"
VAULT_DIR = G100 / "b2_raw_acquisition"
MANIFEST_PATH = G100 / "b2_raw_acquisition_manifest.json"

USER_AGENT = "Mozilla/5.0 (compatible; MOROCCO26-B2-acquirer/1.0)"
TIMEOUT_SECONDS = 45
MAX_BYTES = 64 * 1024 * 1024

# Frozen smoke-test vocabulary, restated so a challenge page is never archived
# as if it were content.
CHALLENGE_MARKERS = ("just a moment", "one moment, please", "cf-chl", "captcha")
BLOCKED_STATUSES = {401, 403, 429, 451}


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_ACQUIRE_FAIL: missing {path.relative_to(REPO)}")
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
    """Recorded with every run so a local block is never read as absence."""
    return {
        "platform": platform.system(),
        "python": platform.python_version(),
        "runner": "GITHUB_ACTIONS" if os.environ.get("GITHUB_ACTIONS") else "LOCAL",
        "github_run_id": os.environ.get("GITHUB_RUN_ID"),
        "user_agent": USER_AGENT,
    }


class RedirectRecorder(urllib.request.HTTPRedirectHandler):
    def __init__(self) -> None:
        self.chain: list[str] = []

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        self.chain.append(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch(url: str) -> dict:
    """One deterministic GET. Returns a record; never raises for network failure."""
    recorder = RedirectRecorder()
    opener = urllib.request.build_opener(recorder)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    record = {
        "url": url,
        "retrieved_at": now_local(),
        "http_status": None,
        "redirect_chain": [],
        "final_url": None,
        "content_type": None,
        "content_length": None,
        "etag": None,
        "last_modified": None,
        "sha256": None,
        "state": None,
        "error": None,
        "body": None,
    }
    try:
        with opener.open(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                record.update(state="BLOCKED_SOURCE", error="RESPONSE_EXCEEDS_MAX_BYTES")
                return record
            record.update(
                http_status=response.status,
                redirect_chain=list(recorder.chain),
                final_url=response.url,
                content_type=response.headers.get("Content-Type"),
                content_length=len(body),
                etag=response.headers.get("ETag"),
                last_modified=response.headers.get("Last-Modified"),
                sha256=hashlib.sha256(body).hexdigest(),
                body=body,
            )
            lowered = body[:4096].decode("utf-8", "ignore").casefold()
            if any(marker in lowered for marker in CHALLENGE_MARKERS):
                record.update(state="BLOCKED_SOURCE", error="CHALLENGE_MARKER_PRESENT", body=None)
            else:
                record["state"] = "ACQUIRED"
    except urllib.error.HTTPError as exc:
        record.update(
            http_status=exc.code,
            state="BLOCKED_SOURCE" if exc.code in BLOCKED_STATUSES else "FETCH_ERROR",
            error=f"HTTPError {exc.code}",
        )
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, OSError) as exc:
        record.update(state="BLOCKED_SOURCE", error=f"{type(exc).__name__}: {str(exc)[:200]}")
    return record


def store(record: dict, source_id: str, bucket: str, filename: str) -> str | None:
    """Write raw bytes into the immutable vault. Parser output never lands here."""
    if record.get("body") is None:
        return None
    target = VAULT_DIR / source_id / bucket / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(record["body"])
    sidecar = target.with_suffix(target.suffix + ".meta.json")
    dump(sidecar, {
        "source_id": source_id,
        "bucket": bucket,
        "original_url": record["url"],
        "final_url": record["final_url"],
        "retrieved_at": record["retrieved_at"],
        "http_status": record["http_status"],
        "content_type": record["content_type"],
        "content_length": record["content_length"],
        "etag": record["etag"],
        "last_modified": record["last_modified"],
        "sha256": record["sha256"],
        "environment": environment(),
        "immutability": "RAW_BYTES_NEVER_REPLACED_BY_PARSER_OUTPUT",
    })
    return target.relative_to(REPO).as_posix()


def strip_body(record: dict) -> dict:
    return {key: value for key, value in record.items() if key != "body"}


def acquire_historical(surface: dict) -> list[dict]:
    """Read the recorded member dataset partitions that were never extracted."""
    entries = []
    rows = [
        row for row in surface["surfaces"]
        if row["surface_family"] == "HISTORICAL_INGEST_PROVENANCE"
        and row.get("loader") == "HUGGINGFACE_DATASETS"
    ]
    for row in rows:
        source_id = row["source_id"]
        dataset = row["dataset_name"]
        listing_url = f"https://huggingface.co/api/datasets/{dataset}"
        listing = fetch(listing_url)
        entries.append({
            **strip_body(listing),
            "source_id": source_id,
            "purpose": "ENUMERATE_DATASET_FILES",
            "stored_path": store(listing, source_id, "index", "dataset_index.json"),
        })
        if listing["state"] != "ACQUIRED":
            continue

        try:
            siblings = json.loads(listing["body"]).get("siblings", [])
        except (json.JSONDecodeError, TypeError):
            entries[-1]["error"] = "DATASET_INDEX_NOT_JSON"
            continue

        # Lexicographic order; only the data payloads, no repo metadata files.
        names = sorted(
            item["rfilename"] for item in siblings
            if str(item.get("rfilename", "")).endswith((".parquet", ".csv", ".json"))
            and not str(item.get("rfilename", "")).startswith(".")
        )
        for name in names:
            file_url = f"https://huggingface.co/datasets/{dataset}/resolve/main/{name}"
            got = fetch(file_url)
            entries.append({
                **strip_body(got),
                "source_id": source_id,
                "purpose": "ACQUIRE_DATASET_FILE",
                "dataset_file": name,
                "stored_path": store(got, source_id, "data", name.replace("/", "__")),
            })
    return entries


def acquire_wave1(surface: dict) -> list[dict]:
    """Bounded enumeration of ACTIVE 2026 registry routes under the frozen templates."""
    entries = []
    rows = sorted(
        (row for row in surface["surfaces"]
         if row["surface_family"] == "B2_SOURCE_REGISTRY_V1"),
        key=lambda row: row["source_id"],
    )
    for row in rows:
        source_id = row["source_id"]
        if not row.get("claim_eligible"):
            entries.append({
                "source_id": source_id,
                "url": (row.get("seed_urls") or [None])[0],
                "retrieved_at": now_local(),
                "state": "BLOCKED_SOURCE",
                "error": f"OPERATIONAL_STATE_{row.get('access_status')}",
                "purpose": "NOT_CLAIM_ELIGIBLE_UNDER_FROZEN_REGISTRY",
                "http_status": None,
                "sha256": None,
                "stored_path": None,
            })
            continue

        allowed = set(row.get("root_domains") or [])
        for seed in sorted(row.get("seed_urls") or []):
            got = fetch(seed)
            digest = (got.get("sha256") or "nohash")[:16]
            entries.append({
                **strip_body(got),
                "source_id": source_id,
                "purpose": "Q01_FIXED_SEED",
                "stored_path": store(got, source_id, "2026", f"seed_{digest}.bin"),
            })

        # Q02: sitemap probe at the frozen candidate paths only.
        for domain in sorted(allowed):
            for candidate in ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml"):
                url = urljoin(f"https://{domain}", candidate)
                got = fetch(url)
                if got["state"] == "ACQUIRED" and urlparse(got["final_url"]).netloc not in allowed:
                    got.update(state="BLOCKED_SOURCE", error="REDIRECT_LEFT_ALLOWED_DOMAIN", body=None)
                entries.append({
                    **strip_body(got),
                    "source_id": source_id,
                    "purpose": "Q02_SITEMAP_PROBE",
                    "stored_path": store(
                        got, source_id, "2026", f"sitemap_{domain}_{candidate.strip('/')}"
                    ),
                })
            break  # one canonical domain per source is enough for a bounded probe
    return entries


def merge_append_only(existing: list[dict], new: list[dict]) -> list[dict]:
    """Append-only: an earlier observation is never rewritten by a later one."""
    seen = {
        (row.get("source_id"), row.get("url"), row.get("retrieved_at"))
        for row in existing
    }
    merged = list(existing)
    for row in new:
        key = (row.get("source_id"), row.get("url"), row.get("retrieved_at"))
        if key not in seen:
            merged.append(row)
            seen.add(key)
    merged.sort(key=lambda row: (row.get("source_id") or "", row.get("url") or "", row.get("retrieved_at") or ""))
    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--historical", action="store_true")
    parser.add_argument("--wave1", action="store_true")
    args = parser.parse_args()
    if not (args.historical or args.wave1):
        parser.error("choose --historical and/or --wave1")

    surface = load(SURFACE_PATH)
    entries = []
    if args.historical:
        entries += acquire_historical(surface)
    if args.wave1:
        entries += acquire_wave1(surface)

    previous = load(MANIFEST_PATH) if MANIFEST_PATH.exists() else {"entries": [], "runs": []}
    merged = merge_append_only(previous.get("entries", []), entries)

    run = {
        "run_at": now_local(),
        "modes": [name for name, on in (("historical", args.historical), ("wave1", args.wave1)) if on],
        "surface_sha256": surface["canonical_surface_sha256"],
        "environment": environment(),
        "entries_added": len(merged) - len(previous.get("entries", [])),
        "acquired": sum(row.get("state") == "ACQUIRED" for row in entries),
        "blocked": sum(row.get("state") == "BLOCKED_SOURCE" for row in entries),
        "errors": sum(row.get("state") == "FETCH_ERROR" for row in entries),
    }

    manifest = {
        "schema_version": "1.0",
        "manifest_id": "M26-GOAL100-B2-RAW-ACQUISITION-V1",
        "append_only": True,
        "determinism": {"llm_used": False, "source_discovery": False, "semantic_selection": False},
        "absence_rule": "BLOCKED_SOURCE and FETCH_ERROR describe access, never absence of the document.",
        "vault_dir": VAULT_DIR.relative_to(REPO).as_posix(),
        "runs": previous.get("runs", []) + [run],
        "entry_count": len(merged),
        "entries": merged,
    }
    manifest["canonical_manifest_sha256"] = canonical_sha256(
        {key: value for key, value in manifest.items() if key != "canonical_manifest_sha256"}
    )
    dump(MANIFEST_PATH, manifest)

    print("B2_ACQUISITION_RUN_COMPLETE")
    print(f"modes={run['modes']} acquired={run['acquired']} blocked={run['blocked']} errors={run['errors']}")
    print(f"manifest_entries={len(merged)} environment={run['environment']['runner']}")


if __name__ == "__main__":
    main()
