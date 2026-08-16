#!/usr/bin/env python3
"""Probe TAFRA 2002/2007 workbooks for safe national-level calibration use.

The older elections are NOT assumed geographically comparable to 2011-2021.
This probe only asks whether their schemas support transparent national party-vote
aggregates and turnout facts. Raw bytes are retained and hashed. No older data
enters B* until a later machine gate explicitly accepts it.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goal100" / "older_history_probe"
RAW = OUT / "raw"
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

DATASETS = {
    2002: {
        "url": "https://open.africa/dataset/863697f2-bffa-4607-afe7-2c38d6b78adf/resource/19018416-2921-4abf-87a2-463160892f07/download/parlement-elections-2002-1-0.xlsx",
        "filename": "parlement-elections-2002-1-0.xlsx",
        "source_quality_note": "TAFRA warns that primary coverage is incomplete, the secondary source has errors, and small-party results are unavailable.",
    },
    2007: {
        "url": "https://open.africa/dataset/1f48eeec-ff94-46a2-ae8e-ed56b66dd529/resource/0ec47fad-4f8a-4753-b107-82b0cc76d94c/download/parlement-elections-2007-1-0.xlsx",
        "filename": "parlement-elections-2007-1-0.xlsx",
        "source_quality_note": "TAFRA archived copy of the official elections2007.gov.ma results.",
    },
}


def main():
    s = requests.Session()
    s.headers.update({"User-Agent": "MOROCCO26-research/2.0 (aggregate election research)"})
    report = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-OLDER-HISTORY-PROBE-V1",
        "scope": "probe only; no forecast/model input authorization",
        "datasets": [],
    }
    for year, spec in DATASETS.items():
        r = s.get(spec["url"], timeout=45, allow_redirects=True)
        if r.status_code != 200 or len(r.content) < 4096 or r.content[:2] != b"PK":
            raise RuntimeError({"year": year, "status": r.status_code, "bytes": len(r.content), "final_url": r.url, "content_type": r.headers.get("content-type")})
        raw_path = RAW / spec["filename"]
        raw_path.write_bytes(r.content)
        book = pd.ExcelFile(io.BytesIO(r.content))
        sheets = []
        for name in book.sheet_names:
            df = pd.read_excel(io.BytesIO(r.content), sheet_name=name)
            sheets.append({
                "sheet": name,
                "rows": int(len(df)),
                "columns": [str(c) for c in df.columns],
                "nonempty_by_column": {str(c): int(df[c].notna().sum()) for c in df.columns},
                "head": df.head(3).where(pd.notna(df.head(3)), None).to_dict(orient="records"),
            })
        report["datasets"].append({
            "year": year,
            "source_url": spec["url"],
            "source_quality_note": spec["source_quality_note"],
            "raw_path": str(raw_path.relative_to(ROOT)),
            "raw_sha256": hashlib.sha256(r.content).hexdigest(),
            "raw_bytes": len(r.content),
            "sheets": sheets,
        })
    path = OUT / "older_history_schema_probe.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
