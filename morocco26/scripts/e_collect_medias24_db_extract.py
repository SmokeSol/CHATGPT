#!/usr/bin/env python3
"""Acquire and normalize the public Médias24 2026 election SQLite database.

Outputs are a versioned E_collect evidence package plus an Atlas V1-ready JSON
snapshot. The script is append-only and explicitly has no authority to modify
F-1, F0, B2, coefficients or forecast probabilities.
"""
from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
M26 = REPO_ROOT / "morocco26"
G100 = M26 / "data" / "goal100"
E_ROOT = G100 / "e_collect"
ATLAS_ROOT = M26 / "data" / "atlas_v1"
RUN_ID = os.environ.get("E_COLLECT_RUN_ID") or (
    "medias24_db_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
)
RUN_DIR = E_ROOT / "runs" / RUN_ID
RAW_DIR = RUN_DIR / "raw"

ROOT_URL = "https://assets.medias24.com/elections/"
DB_URL = "https://assets.medias24.com/elections/data/elections.db"
EXPECTED_F0_SHA256 = "fbe5197999f20d0612bc0c66e1954b5c611b11208e43a72eb5494a03b1e40d3f"
EXPECTED_B2_ROSTER_SHA256 = "b206ad303869c744d8ade5e3dc09442611d2a59cc15c87aedb19265aae171b86"
USER_AGENT = "Atlas395-ECollect/1.1 (+https://github.com/SmokeSol/CHATGPT)"

# Canonical corrections between the public Médias24 UI vocabulary and Atlas.
# These are identity aliases only; they do not encode any electoral effect.
EXPLICIT_ALIASES = {
    "Salé Nouvelle": "Salé-El Jadida",
    "Salé Médina": "Salé-Médina",
    "Kénitra - El Gharb": "El Gharb",
    "Sidi Othmane-Moulay Rachid": "Moulay Rachid",
    "Ben M'sik": "Ben M'sick",
    "Ben Slimane": "Benslimane",
    "Mohammedia": "Mohammédia",
    "Moulay Yacoub": "Moulay Yaâcoub",
    "Sefrou": "Séfrou",
    "El Karia-Ghafsai": "Karia-Ghafsay",
    "Gueliz": "Guéliz-Nakhil",
    "Ménara": "Menara",
    "Sidi Youssef Ben Ali": "Medina-Sidi Youssef",
    "El Kelâa Des-Sraghna": "El Kelâa des Sraghna",
    "Taroudant Sud": "Taroudant-Sud",
    "Taroudant Nord": "Taroudant-Nord",
    "Agadir-Ida-Ou-Tanane": "Agadir Ida-Outanane",
    "Oued Ed-Dahab": "Oued Eddahab",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def norm(value: Any) -> str:
    text = "" if value is None else str(value)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("’", "'")
    return "".join(ch for ch in text if ch.isalnum())


def json_safe(value: Any) -> Any:
    if isinstance(value, bytes):
        return {"base64": base64.b64encode(value).decode("ascii")}
    return value


def fetch(session: requests.Session, url: str) -> tuple[bytes, dict[str, Any]]:
    response = session.get(url, timeout=(12, 50), allow_redirects=True)
    body = response.content
    meta = {
        "requested_url": url,
        "final_url": response.url,
        "retrieved_at": now_iso(),
        "status_code": response.status_code,
        "content_type": response.headers.get("content-type", "").split(";")[0],
        "content_length": len(body),
        "sha256": sha256_bytes(body),
    }
    if response.status_code != 200:
        raise RuntimeError(f"HTTP {response.status_code} for {url}")
    return body, meta


def extract_js_aliases(html: str) -> dict[str, str]:
    match = re.search(r"const\s+provinceAliases\s*=\s*(\{.*?\})\s*;", html, re.S)
    if not match:
        return {}
    try:
        parsed = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return {str(k): str(v) for k, v in parsed.items()}


def load_canonical_constituencies() -> list[dict[str, Any]]:
    path = M26 / "data" / "constituencies_goal75.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["seats"] = int(row["seats"])
    if len(rows) != 92:
        raise RuntimeError(f"canonical local geometry must contain 92 rows, got {len(rows)}")
    return rows


def resolve_constituency(
    name: str | None,
    canonical: list[dict[str, Any]],
    aliases: dict[str, str],
) -> dict[str, Any]:
    if not name:
        return {
            "input": name,
            "status": "REGIONAL_OR_MISSING",
            "constituency_id": None,
            "canonical_name": None,
            "method": None,
            "score": None,
        }

    by_norm = {norm(row["name"]): row for row in canonical}
    input_norm = norm(name)
    if input_norm in by_norm:
        row = by_norm[input_norm]
        return {
            "input": name,
            "status": "RESOLVED",
            "constituency_id": row["constituency_id"],
            "canonical_name": row["name"],
            "canonical_region": row["region"],
            "seats": row["seats"],
            "method": "EXACT_NORMALIZED",
            "score": 1.0,
        }

    alias_target = aliases.get(name) or EXPLICIT_ALIASES.get(name)
    if alias_target and norm(alias_target) in by_norm:
        row = by_norm[norm(alias_target)]
        return {
            "input": name,
            "status": "RESOLVED",
            "constituency_id": row["constituency_id"],
            "canonical_name": row["name"],
            "canonical_region": row["region"],
            "seats": row["seats"],
            "method": "MEDIAS24_OR_ATLAS_ALIAS",
            "score": 1.0,
        }

    ranked = sorted(
        (
            (SequenceMatcher(None, input_norm, norm(row["name"])).ratio(), row)
            for row in canonical
        ),
        key=lambda item: item[0],
        reverse=True,
    )
    best_score, best = ranked[0]
    second_score = ranked[1][0]
    if best_score >= 0.93 and best_score - second_score >= 0.04:
        return {
            "input": name,
            "status": "PROPOSED_FUZZY_REVIEW_REQUIRED",
            "constituency_id": best["constituency_id"],
            "canonical_name": best["name"],
            "canonical_region": best["region"],
            "seats": best["seats"],
            "method": "UNIQUE_HIGH_SIMILARITY_PROPOSAL",
            "score": round(best_score, 6),
            "runner_up_score": round(second_score, 6),
        }
    return {
        "input": name,
        "status": "UNRESOLVED",
        "constituency_id": None,
        "canonical_name": None,
        "method": "NO_SAFE_MATCH",
        "score": round(best_score, 6),
        "best_candidate": best["name"],
        "runner_up_score": round(second_score, 6),
    }


def sqlite_export(db_path: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    connection = sqlite3.connect(str(db_path))
    connection.row_factory = sqlite3.Row
    try:
        table_rows = connection.execute(
            "SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        schema: dict[str, Any] = {}
        exports: dict[str, list[dict[str, Any]]] = {}
        for item in table_rows:
            table = item["name"]
            columns = [dict(row) for row in connection.execute(f'PRAGMA table_info("{table}")')]
            count = connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            rows = [
                {key: json_safe(row[key]) for key in row.keys()}
                for row in connection.execute(f'SELECT * FROM "{table}"')
            ]
            schema[table] = {
                "create_sql": item["sql"],
                "columns": columns,
                "row_count": count,
            }
            exports[table] = rows
        return schema, exports
    finally:
        connection.close()


def table(exports: dict[str, list[dict[str, Any]]], *names: str) -> list[dict[str, Any]]:
    lowered = {key.lower(): value for key, value in exports.items()}
    for name in names:
        if name.lower() in lowered:
            return lowered[name.lower()]
    return []


def main() -> int:
    RUN_DIR.mkdir(parents=True, exist_ok=False)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    ATLAS_ROOT.mkdir(parents=True, exist_ok=True)

    protected_before = {
        "F0": sha256_file(G100 / "forecasts" / "F0" / "forecast.json"),
        "B2_ROSTER": sha256_file(G100 / "b2_2026_ballot_roster.json"),
    }
    if protected_before["F0"] != EXPECTED_F0_SHA256:
        raise RuntimeError("F0 integrity check failed before acquisition")
    if protected_before["B2_ROSTER"] != EXPECTED_B2_ROSTER_SHA256:
        raise RuntimeError("B2 roster integrity check failed before acquisition")

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Language": "fr,ar;q=0.9,en;q=0.5",
        }
    )
    html_bytes, html_meta = fetch(session, ROOT_URL)
    db_bytes, db_meta = fetch(session, DB_URL)

    html_path = RAW_DIR / f"{html_meta['sha256']}.html"
    db_path = RAW_DIR / f"{db_meta['sha256']}.db"
    html_path.write_bytes(html_bytes)
    db_path.write_bytes(db_bytes)

    # Refuse non-SQLite content even if the server returned 200.
    if not db_bytes.startswith(b"SQLite format 3\x00"):
        raise RuntimeError("downloaded elections.db is not a SQLite database")

    html = html_bytes.decode("utf-8", errors="replace")
    js_aliases = extract_js_aliases(html)
    canonical = load_canonical_constituencies()
    schema, exports = sqlite_export(db_path)

    parties = table(exports, "partis", "parties")
    circonscriptions = table(exports, "circonscriptions", "constituencies")
    candidates = table(exports, "candidats", "candidates")

    crosswalk: list[dict[str, Any]] = []
    mapping_by_input: dict[str, dict[str, Any]] = {}
    for row in circonscriptions:
        name = row.get("circonscription") or row.get("name")
        resolved = resolve_constituency(name, canonical, js_aliases)
        resolved.update(
            {
                "medias24_region_key": row.get("regionKey") or row.get("region_key"),
                "medias24_region": row.get("region"),
                "source_ref": DB_URL,
                "source_sha256": db_meta["sha256"],
            }
        )
        crosswalk.append(resolved)
        if name:
            mapping_by_input[norm(name)] = resolved

    candidate_ledger: list[dict[str, Any]] = []
    for row in candidates:
        circ = row.get("circonscription") or row.get("constituency")
        resolution = mapping_by_input.get(norm(circ)) if circ else None
        if circ and resolution is None:
            resolution = resolve_constituency(circ, canonical, js_aliases)
        candidate_ledger.append(
            {
                "record_id": f"M24-2026-{row.get('id')}",
                "source_class": "MEDIAS24",
                "discovery_origin": "HUMAN_SEED",
                "source_url": row.get("source") or ROOT_URL,
                "source_database_url": DB_URL,
                "source_database_sha256": db_meta["sha256"],
                "retrieved_at": db_meta["retrieved_at"],
                "name_source_form": row.get("name"),
                "party": row.get("party"),
                "region_source_form": row.get("region"),
                "region_key_source": row.get("regionKey") or row.get("region_key"),
                "constituency_source_form": circ,
                "constituency_id": resolution.get("constituency_id") if resolution else None,
                "constituency_canonical_name": resolution.get("canonical_name") if resolution else None,
                "territory_resolution_status": resolution.get("status") if resolution else "REGIONAL_OR_MISSING",
                "territory_resolution_method": resolution.get("method") if resolution else None,
                "role": row.get("role"),
                "source_status": row.get("status"),
                "image": row.get("image"),
                "source_updated_at": row.get("updatedAt") or row.get("updated_at"),
                "atlas_evidence_status": "PARTY_ANNOUNCED_OR_MEDIAS24_REPORTED",
                "forecast_impact_status": "NOT_CALIBRATED",
                "raw_database_row": row,
            }
        )

    resolved = [item for item in crosswalk if item["status"] == "RESOLVED"]
    review = [item for item in crosswalk if item["status"] == "PROPOSED_FUZZY_REVIEW_REQUIRED"]
    unresolved = [item for item in crosswalk if item["status"] == "UNRESOLVED"]
    territory_ids = {item["constituency_id"] for item in candidate_ledger if item["constituency_id"]}

    for filename, payload in {
        "database_schema.json": schema,
        "database_tables.json": exports,
        "parties.json": parties,
        "circonscriptions_raw.json": circonscriptions,
        "territory_crosswalk.json": crosswalk,
        "candidates_raw.json": candidates,
        "candidate_ledger.json": candidate_ledger,
    }.items():
        (RUN_DIR / filename).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    source_manifest = {
        "schema_version": "1.0",
        "run_id": RUN_ID,
        "collector": "CHATGPT_MEDIAS24_SQLITE_EXTRACTOR_V1",
        "created_at": now_iso(),
        "sources": [
            {**html_meta, "archived_path": str(html_path.relative_to(REPO_ROOT))},
            {**db_meta, "archived_path": str(db_path.relative_to(REPO_ROOT))},
        ],
        "sqlite_tables": {key: value["row_count"] for key, value in schema.items()},
        "counts": {
            "parties": len(parties),
            "circonscriptions": len(circonscriptions),
            "candidates": len(candidates),
            "crosswalk_resolved": len(resolved),
            "crosswalk_review_required": len(review),
            "crosswalk_unresolved": len(unresolved),
            "candidate_territories_with_records": len(territory_ids),
        },
        "integrity": {
            "F0_sha256_before": protected_before["F0"],
            "B2_roster_sha256_before": protected_before["B2_ROSTER"],
            "forecast_effect_authorized": False,
            "coefficients_modified": False,
        },
    }
    (RUN_DIR / "run_manifest.json").write_text(
        json.dumps(source_manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    atlas_snapshot = {
        "schema_version": "1.0",
        "snapshot_id": f"ATLAS-V1-MEDIAS24-{RUN_ID}",
        "generated_at": now_iso(),
        "status": "EVIDENCE_LAYER_PREVIEW",
        "forecast": {
            "snapshot_id": "F0",
            "immutable": True,
            "artifact_sha256": EXPECTED_F0_SHA256,
            "candidate_signal_impact": "NOT_CALIBRATED",
        },
        "source": {
            "class": "MEDIAS24",
            "root_url": ROOT_URL,
            "database_url": DB_URL,
            "database_sha256": db_meta["sha256"],
            "retrieved_at": db_meta["retrieved_at"],
        },
        "coverage": source_manifest["counts"],
        "parties": parties,
        "territory_crosswalk": crosswalk,
        "candidates": candidate_ledger,
        "display_policy": {
            "Arabic_is_first_class": True,
            "missing_or_ambiguous_not_silently_filled": True,
            "forecast_and_live_evidence_separate": True,
        },
    }
    atlas_path = ATLAS_ROOT / "medias24_2026_snapshot.json"
    atlas_path.write_text(
        json.dumps(atlas_snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    protected_after = {
        "F0": sha256_file(G100 / "forecasts" / "F0" / "forecast.json"),
        "B2_ROSTER": sha256_file(G100 / "b2_2026_ballot_roster.json"),
    }
    if protected_after != protected_before:
        raise RuntimeError("protected artifacts changed during extraction")

    latest = {
        "schema_version": "1.0",
        "latest_run_id": RUN_ID,
        "latest_run_manifest": str((RUN_DIR / "run_manifest.json").relative_to(REPO_ROOT)),
        "atlas_snapshot": str(atlas_path.relative_to(REPO_ROOT)),
        "updated_at": now_iso(),
    }
    (E_ROOT / "medias24_db_latest.json").write_text(
        json.dumps(latest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = f"""# Médias24 2026 SQLite extraction — {RUN_ID}

- Tables: {json.dumps(source_manifest['sqlite_tables'], ensure_ascii=False, sort_keys=True)}
- Parties: **{len(parties)}**
- Constituency rows: **{len(circonscriptions)}**
- Candidate rows: **{len(candidates)}**
- Territory crosswalk resolved exactly/alias: **{len(resolved)}**
- Territory mappings requiring review: **{len(review)}**
- Territory mappings unresolved: **{len(unresolved)}**
- Local territories with at least one candidate record: **{len(territory_ids)}**
- Database SHA-256: `{db_meta['sha256']}`
- F0 unchanged: **yes** (`{protected_after['F0']}`)
- B2 roster unchanged: **yes** (`{protected_after['B2_ROSTER']}`)
- Forecast impact: **NOT CALIBRATED / NOT APPLIED**
"""
    (RUN_DIR / "collector_report.md").write_text(report, encoding="utf-8")

    print(json.dumps(source_manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
