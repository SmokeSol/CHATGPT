#!/usr/bin/env python3
"""Audit the live Atlas 395 Vercel aliases against the current reader contract.

This is a deployment-surface test: it does not mutate science or reader data.
It records HTTP availability, deployed asset hashes, the active methodology
contract, and a headless-browser fatal-error check when Chromium is available.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

M26 = Path(__file__).resolve().parents[1]
WEB = M26 / "web"
OUT = M26 / "atlas395" / "vercel_audit_latest.json"

CANONICAL = "https://atlas-395-maroc-2026.vercel.app/"
CANDIDATES = [
    CANONICAL,
    "https://atlas-395-v1.vercel.app/",
    "https://atlas-395-v1-yannlevy85gmailcoms-projects.vercel.app/",
    "https://atlas395-maroc-2026.vercel.app/",
    "https://atlas-395-rescue-20260817.vercel.app/",
]
REQUIRED_DATA = [
    "current_snapshot.json",
    "national_projection.json",
    "constituency_cards.json",
    "party_cards.json",
    "evidence_index.json",
    "methodology_state.json",
    "public_methodology.json",
]
REQUIRED_ASSETS = ["app.js", "assets/core.js", "assets/daily.js"]
FATAL_TEXT = [
    "Atlas 395 ne peut pas charger",
    "Atlas 395 ne peut pas initialiser",
    "Données indisponibles (404)",
]


def sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fetch(url: str, timeout: int = 30) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "atlas395-vercel-audit/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            data = response.read()
            return {
                "status": int(response.status),
                "bytes": len(data),
                "sha256": sha_bytes(data),
                "content_type": response.headers.get("Content-Type"),
                "body": data,
                "final_url": response.geturl(),
            }
    except urllib.error.HTTPError as exc:
        data = exc.read()
        return {
            "status": int(exc.code),
            "bytes": len(data),
            "sha256": sha_bytes(data),
            "content_type": exc.headers.get("Content-Type") if exc.headers else None,
            "body": data,
            "final_url": exc.geturl(),
        }
    except Exception as exc:
        return {
            "status": 0,
            "bytes": 0,
            "sha256": None,
            "content_type": None,
            "body": b"",
            "final_url": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


def public(record: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in record.items() if k != "body"}


def browser_check(url: str) -> dict[str, Any]:
    chrome = next(
        (p for p in [shutil.which("google-chrome"), shutil.which("chromium"), shutil.which("chromium-browser")] if p),
        None,
    )
    if not chrome:
        return {"available": False, "pass": None, "reason": "chrome_not_available"}
    try:
        run = subprocess.run(
            [chrome, "--headless", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=15000", "--dump-dom", url],
            capture_output=True,
            timeout=40,
            check=False,
        )
        dom = run.stdout.decode("utf-8", errors="replace")
        bad = [text for text in FATAL_TEXT if text in dom]
        return {
            "available": True,
            "pass": not bad and len(dom) > 1000,
            "dom_bytes": len(run.stdout),
            "fatal_strings": bad,
            "returncode": run.returncode,
        }
    except Exception as exc:
        return {"available": True, "pass": False, "reason": f"{type(exc).__name__}: {exc}"}


def audit_url(url: str) -> dict[str, Any]:
    root = fetch(url)
    assets: dict[str, Any] = {}
    asset_bodies: dict[str, bytes] = {}
    for name in REQUIRED_ASSETS:
        result = fetch(url + name)
        assets[name] = public(result)
        asset_bodies[name] = result["body"]
    data: dict[str, Any] = {}
    for name in REQUIRED_DATA:
        data[name] = public(fetch(url + "data/" + name))
    editions_current = public(fetch(url + "editions/current.json"))

    repo_hashes = {
        "index.html": sha_file(WEB / "index.html"),
        "app.js": sha_file(WEB / "app.js"),
        "assets/core.js": sha_file(WEB / "assets" / "core.js"),
        "assets/daily.js": sha_file(WEB / "assets" / "daily.js"),
    }
    live_hashes = {
        "index.html": root.get("sha256"),
        "app.js": assets["app.js"].get("sha256"),
        "assets/core.js": assets["assets/core.js"].get("sha256"),
        "assets/daily.js": assets["assets/daily.js"].get("sha256"),
    }
    hash_match = {name: live_hashes[name] == repo_hashes[name] for name in repo_hashes}

    core_text = asset_bodies["assets/core.js"].decode("utf-8", errors="replace")
    daily_text = asset_bodies["assets/daily.js"].decode("utf-8", errors="replace")
    if "methodologyPromise=load('public_methodology.json').catch(()=>load('methodology_state.json'))" in daily_text:
        methodology_contract = "public_methodology_with_methodology_state_fallback"
    elif "load('public_methodology.json')" in daily_text:
        methodology_contract = "public_methodology_only"
    elif "load('methodology_state.json')" in daily_text or "load('methodology_state.json')" in core_text:
        methodology_contract = "methodology_state"
    else:
        methodology_contract = "unknown"

    http_pass = (
        root.get("status") == 200
        and all(assets[name].get("status") == 200 for name in REQUIRED_ASSETS)
        and all(data[name].get("status") == 200 for name in REQUIRED_DATA)
    )
    browser = browser_check(url) if http_pass else {"available": None, "pass": False, "reason": "http_contract_failed"}
    overall = bool(http_pass and (browser.get("pass") is not False))
    return {
        "url": url,
        "root": public(root),
        "assets": assets,
        "data": data,
        "editions_current": editions_current,
        "repo_hashes": repo_hashes,
        "live_hashes": live_hashes,
        "hash_match": hash_match,
        "methodology_contract": methodology_contract,
        "http_contract_pass": http_pass,
        "browser": browser,
        "overall_pass": overall,
    }


def main() -> None:
    # Vercel can take a short time to attach a fresh deployment to the stable
    # alias. Poll only the canonical URL; audit alternate aliases once after it.
    canonical: dict[str, Any] | None = None
    attempts = 0
    for attempts in range(1, 19):
        canonical = audit_url(CANONICAL)
        print(
            f"ATLAS395_VERCEL_CANONICAL attempt={attempts} "
            f"root={canonical['root'].get('status')} "
            f"public_methodology={canonical['data']['public_methodology.json'].get('status')} "
            f"daily_match={canonical['hash_match']['assets/daily.js']} "
            f"pass={canonical['overall_pass']}"
        )
        if canonical["overall_pass"]:
            break
        time.sleep(10)

    aliases = [canonical]
    for url in CANDIDATES[1:]:
        aliases.append(audit_url(url))

    payload = {
        "schema_version": "1.0",
        "product": "ATLAS 395",
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "canonical_url": CANONICAL,
        "canonical_attempts": attempts,
        "canonical_pass": bool(canonical and canonical.get("overall_pass")),
        "required_data": REQUIRED_DATA,
        "aliases": aliases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"ATLAS395_VERCEL_AUDIT_RESULT canonical_pass={payload['canonical_pass']} output={OUT}")


if __name__ == "__main__":
    main()
