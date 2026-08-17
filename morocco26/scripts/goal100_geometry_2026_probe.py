#!/usr/bin/env python3
"""Probe authoritative Parliament pages needed for the 2026 geometry certificate.

This is an acquisition diagnostic, not the certificate itself. It records raw-byte
hashes, HTTP metadata and table schemas and fails closed on content interpretation.
No secondary source is silently substituted for an unavailable official page.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goal100" / "geometry_2026_probe.json"

SOURCES = [
    {
        "id": "CURRENT_PARLIAMENT_ELECTORAL_MAP_AR",
        "role": "current official local constituency map",
        "url": "https://www.chambredesrepresentants.ma/ar/%D8%AE%D8%B1%D9%8A%D8%B7%D8%A9-%D8%A7%D9%84%D8%AA%D9%82%D8%B3%D9%8A%D9%85-%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D9%8A",
    },
    {
        "id": "PARLIAMENT_2021_NUMERIC_LIST_FR",
        "role": "official French local/regional names and seat magnitudes",
        "url": "https://www.chambredesrepresentants.ma/fr/actualites/donnees-chiffrees-autour-du-scrutin-legislatif-du-mercredi-8-septembre-2021-conformement",
    },
    {
        "id": "CURRENT_PARLIAMENT_ELECTION_LAWS_AR",
        "role": "current official election-law index and decree 2.11.603 reference",
        "url": "https://www.chambredesrepresentants.ma/ar/%D8%A7%D9%84%D9%82%D9%88%D8%A7%D9%86%D9%8A%D9%86-%D8%A7%D9%84%D9%85%D8%AA%D8%B9%D9%84%D9%82%D8%A9-%D8%A8%D8%A7%D9%84%D8%A7%D9%86%D8%AA%D8%AE%D8%A7%D8%A8%D8%A7%D8%AA",
    },
]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36 MOROCCO26/2.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,ar;q=0.8,en;q=0.6",
    "Cache-Control": "no-cache",
}


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def table_profile(raw: bytes) -> dict:
    try:
        tables = pd.read_html(io.BytesIO(raw))
    except Exception as exc:
        return {"parse_ok": False, "error": repr(exc), "tables": []}

    profiles = []
    for index, frame in enumerate(tables):
        profiles.append(
            {
                "index": index,
                "rows": int(len(frame)),
                "columns": [str(column) for column in frame.columns],
                "head": frame.head(3).astype(object).where(frame.notna(), None).to_dict("records"),
            }
        )
    return {"parse_ok": True, "table_count": len(tables), "tables": profiles}


def main() -> None:
    session = requests.Session()
    session.headers.update(HEADERS)
    report = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-GEOMETRY-2026-PROBE-V1",
        "purpose": "authoritative-source acquisition diagnostic before geometry certification",
        "epistemic_rule": "official-source failure is recorded; it is never bridged by an unlabeled secondary source",
        "sources": [],
    }

    for source in SOURCES:
        row = dict(source)
        try:
            response = session.get(source["url"], timeout=45, allow_redirects=True)
            raw = response.content
            row.update(
                {
                    "status": response.status_code,
                    "final_url": response.url,
                    "content_type": response.headers.get("content-type"),
                    "bytes": len(raw),
                    "sha256": sha256(raw),
                    "looks_like_html": b"<html" in raw[:4096].lower() or b"<!doctype html" in raw[:4096].lower(),
                    "table_profile": table_profile(raw) if response.status_code == 200 else None,
                }
            )
        except Exception as exc:
            row.update({"request_error": repr(exc)})
        report["sources"].append(row)
        print(json.dumps(row, ensure_ascii=False, default=str), flush=True)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


if __name__ == "__main__":
    main()
