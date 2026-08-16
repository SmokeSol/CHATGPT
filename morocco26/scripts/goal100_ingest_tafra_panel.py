#!/usr/bin/env python3
"""Acquire and canonicalize the TAFRA legislative history for Goal100.

Scientific contract:
- raw bytes are hashed before parsing;
- HTML/login/redirect shells are rejected as data;
- original geographic IDs are preserved;
- missing registered-voter counts remain missing;
- no 2016 N is inferred in this ingestion step;
- no historical seat law is used to create 2026 outcomes.

This script is intentionally fail-closed: a dead mirror or changed schema stops the
pipeline rather than silently falling back to a scraped secondary table.
"""
from __future__ import annotations

import hashlib
import io
import json
import math
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "goal100" / "historical"
RAW = OUT / "raw"
OUT.mkdir(parents=True, exist_ok=True)
RAW.mkdir(parents=True, exist_ok=True)

DATASETS = {
    2011: {
        "primary": "https://openafrica.net/dataset/cb7a294b-9569-4647-b35e-3b1cb6c8028e/resource/59229632-d062-4e1a-afff-b344b6afdae7/download/parlement-elections-2011-1-0.xlsx",
        "filename": "parlement-elections-2011-1-0.xlsx",
    },
    2016: {
        "primary": "https://openafrica.net/dataset/6bf3208e-7e01-456f-9ed8-ff8977e49585/resource/6c4000e1-5359-43fd-b941-399af34ee54a/download/parlement-elections-2016-1-1.xlsx",
        "mirrors": ["https://server.rferrali.net/media/parlement-elections-2016-1-1.xlsx"],
        "filename": "parlement-elections-2016-1-1.xlsx",
    },
    2021: {
        "primary": "https://openafrica.net/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx",
        "filename": "parlement-elections-2021-1-0.xlsx",
    },
}

META_COLUMNS = {
    "idregion", "idwilaya", "idprefprov", "idsouspref", "idcirconscription",
    "region", "wilaya", "prefprov", "souspref", "circonscription", "typeliste",
    "nsieges", "ninscrits", "txparticipation", "invalide",
}
META_PREFIXES = ("rep",)


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_xlsx(data: bytes) -> bool:
    # XLSX is a ZIP container. Reject HTML challenge/login pages and empty bodies.
    return len(data) > 4096 and data[:2] == b"PK"


def download(year: int, spec: dict) -> tuple[bytes, str]:
    urls = [spec["primary"], *spec.get("mirrors", [])]
    errors = []
    session = requests.Session()
    session.headers.update({"User-Agent": "MOROCCO26-research/2.0 (aggregate election research)"})
    for url in urls:
        try:
            r = session.get(url, timeout=45, allow_redirects=True)
            if r.status_code == 200 and is_xlsx(r.content):
                return r.content, url
            errors.append({
                "url": url,
                "status": r.status_code,
                "content_type": r.headers.get("content-type"),
                "final_url": r.url,
                "bytes": len(r.content),
            })
        except Exception as exc:
            errors.append({"url": url, "error": repr(exc)})
    raise RuntimeError(f"TAFRA {year} acquisition failed closed: {errors}")


def canonical_colmap(columns) -> dict[str, object]:
    out = {}
    for c in columns:
        key = norm(c)
        if key and key not in out:
            out[key] = c
    return out


def scalar(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def parse_workbook(year: int, raw: bytes) -> dict:
    book = pd.ExcelFile(io.BytesIO(raw))
    if not book.sheet_names:
        raise RuntimeError(f"{year}: workbook has no sheets")

    # Prefer the documented data sheet, otherwise find the sheet carrying geography.
    candidates = ["donnees", "données", *book.sheet_names]
    chosen = None
    df = None
    for name in candidates:
        if name not in book.sheet_names:
            continue
        trial = pd.read_excel(io.BytesIO(raw), sheet_name=name)
        cm = canonical_colmap(trial.columns)
        if "idcirconscription" in cm and "circonscription" in cm:
            chosen, df = name, trial
            break
    if df is None:
        raise RuntimeError(f"{year}: no sheet with idCirconscription/circonscription; sheets={book.sheet_names}")

    cm = canonical_colmap(df.columns)
    required = {"idcirconscription", "circonscription", "nsieges"}
    missing_required = sorted(required - set(cm))
    if missing_required:
        raise RuntimeError(f"{year}: missing required columns {missing_required}")

    party_cols = []
    for key, original in cm.items():
        if key in META_COLUMNS or key.startswith(META_PREFIXES):
            continue
        # Party columns in TAFRA are compact acronyms. Preserve unknown acronyms
        # rather than forcing a post-hoc continuity mapping during ingestion.
        if re.fullmatch(r"[a-z][a-z0-9]{1,7}", key):
            party_cols.append((key.upper(), original))

    rows = []
    for _, r in df.iterrows():
        cid = scalar(r[cm["idcirconscription"]])
        cname = scalar(r[cm["circonscription"]])
        if cid is None and cname is None:
            continue

        list_type = scalar(r[cm["typeliste"]]) if "typeliste" in cm else None
        seats = scalar(r[cm["nsieges"]])
        if seats is None:
            continue

        votes = {}
        for party, original in party_cols:
            value = scalar(r[original])
            if value is None:
                continue
            try:
                ivalue = int(round(float(value)))
            except (TypeError, ValueError):
                continue
            if ivalue < 0:
                raise RuntimeError(f"{year}: negative vote count {party} in {cname}")
            if ivalue:
                votes[party] = ivalue

        row = {
            "year": year,
            "id_region": scalar(r[cm["idregion"]]) if "idregion" in cm else None,
            "id_prefprov": scalar(r[cm["idprefprov"]]) if "idprefprov" in cm else None,
            "id_constituency": cid,
            "region": scalar(r[cm["region"]]) if "region" in cm else None,
            "prefprov": scalar(r[cm["prefprov"]]) if "prefprov" in cm else None,
            "constituency": cname,
            "list_type": list_type,
            "seats": int(round(float(seats))),
            "registered_reported": scalar(r[cm["ninscrits"]]) if "ninscrits" in cm else None,
            "turnout_rate_reported": scalar(r[cm["txparticipation"]]) if "txparticipation" in cm else None,
            "invalid_reported": scalar(r[cm["invalide"]]) if "invalide" in cm else None,
            "votes": dict(sorted(votes.items())),
            "party_vote_sum": sum(votes.values()),
        }
        rows.append(row)

    if len(rows) < 80:
        raise RuntimeError(f"{year}: implausibly small legislative table: {len(rows)} rows")
    return {
        "year": year,
        "sheet": chosen,
        "sheets": book.sheet_names,
        "rows": rows,
        "row_count": len(rows),
        "party_columns": sorted(p for p, _ in party_cols),
    }


def main():
    manifest = {
        "schema_version": "1.0",
        "pipeline": "M26-GOAL100-TAFRA-HISTORY-V1",
        "epistemic_rules": [
            "missing registered counts remain null",
            "no 2016 registered-voter inference during ingestion",
            "historical seat rules are not applied to prospective 2026 draws",
            "raw files are hashed and retained",
            "source/schema failure stops the pipeline",
        ],
        "datasets": [],
    }
    all_rows = []

    for year, spec in DATASETS.items():
        raw, used_url = download(year, spec)
        raw_path = RAW / spec["filename"]
        raw_path.write_bytes(raw)
        parsed = parse_workbook(year, raw)
        parsed_path = OUT / f"tafra_legislative_{year}_canonical.json"
        parsed_path.write_text(json.dumps(parsed, ensure_ascii=False, indent=2), encoding="utf-8")
        all_rows.extend(parsed["rows"])
        manifest["datasets"].append({
            "year": year,
            "source_url_used": used_url,
            "raw_path": str(raw_path.relative_to(ROOT)),
            "raw_sha256": sha256(raw),
            "raw_bytes": len(raw),
            "canonical_path": str(parsed_path.relative_to(ROOT)),
            "row_count": parsed["row_count"],
            "sheet": parsed["sheet"],
            "registered_nonnull_rows": sum(r["registered_reported"] is not None for r in parsed["rows"]),
        })
        print(year, manifest["datasets"][-1], flush=True)

    panel_path = OUT / "tafra_legislative_2011_2016_2021_rows.jsonl"
    with panel_path.open("w", encoding="utf-8") as f:
        for row in all_rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    manifest["panel_path"] = str(panel_path.relative_to(ROOT))
    manifest["panel_rows"] = len(all_rows)

    man_path = OUT / "historical_ingest_manifest.json"
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
