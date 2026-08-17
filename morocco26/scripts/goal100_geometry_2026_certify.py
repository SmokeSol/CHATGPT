#!/usr/bin/env python3
"""Certify the MOROCCO//26 working 2026 electoral geometry.

The certificate is fail-closed and separates three facts:
1. the current project local geometry matches the authoritative Parliament rows;
2. the regional magnitudes match Article 1 of Organic Law 27.11;
3. direct CI acquisition is WAF-blocked, so an active legal watch remains mandatory.

A future superseding decree creates a new certificate version and never rewrites a
published forecast.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G100 = DATA / "goal100"

REPO_LOCAL = DATA / "constituencies_goal75.csv"
OFFICIAL_LOCAL = G100 / "geometry_authoritative_local_rows_fr.csv"
OFFICIAL_REGIONAL = G100 / "geometry_authoritative_regional_rows_fr.csv"
WITNESS = G100 / "geometry_authoritative_witness_v1.json"
PROBE = G100 / "geometry_2026_probe.json"
OUT = G100 / "geometry_2026_certificate.json"

CANONICAL_REGIONAL = {
    "tanger tetouan al hoceima": 8,
    "oriental": 7,
    "fes meknes": 10,
    "rabat sale kenitra": 10,
    "beni mellal khenifra": 7,
    "casablanca settat": 12,
    "marrakech safi": 10,
    "draa tafilalet": 6,
    "souss massa": 7,
    "guelmim oued noun": 5,
    "laayoune sakia el hamra": 5,
    "dakhla oued ed dahab": 3,
}


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"GEOMETRY_2026_CERTIFICATION_FAIL: {message}")


def main() -> None:
    witness = json.loads(WITNESS.read_text(encoding="utf-8"))
    probe = json.loads(PROBE.read_text(encoding="utf-8"))
    aliases = {norm(k): norm(v) for k, v in witness.get("explicit_aliases", {}).items()}

    repo_rows = read_csv(REPO_LOCAL)
    official_rows = read_csv(OFFICIAL_LOCAL)
    regional_rows = read_csv(OFFICIAL_REGIONAL)

    require(len(repo_rows) == 92, f"repo local row count {len(repo_rows)} != 92")
    require(len({r["constituency_id"] for r in repo_rows}) == 92, "repo constituency IDs are not unique")
    require(sum(int(r["seats"]) for r in repo_rows) == 305, "repo local seat total != 305")
    require(len(official_rows) == 92, f"official local row count {len(official_rows)} != 92")
    require(sum(int(r["seats"]) for r in official_rows) == 305, "official local seat total != 305")

    repo_by_name: dict[str, dict[str, str]] = {}
    for row in repo_rows:
        key = norm(row["name"])
        require(key not in repo_by_name, f"duplicate normalized repo name: {key}")
        repo_by_name[key] = row

    matched = []
    differences = []
    used_repo_ids = set()
    for row in official_rows:
        source_key = norm(row["official_name_fr"])
        target_key = aliases.get(source_key, source_key)
        repo = repo_by_name.get(target_key)
        if repo is None:
            differences.append(
                {
                    "kind": "OFFICIAL_ROW_UNMATCHED",
                    "official_name": row["official_name_fr"],
                    "normalized": source_key,
                    "target_normalized": target_key,
                }
            )
            continue
        official_seats = int(row["seats"])
        repo_seats = int(repo["seats"])
        match = {
            "constituency_id": repo["constituency_id"],
            "repo_name": repo["name"],
            "official_name": row["official_name_fr"],
            "prefecture_or_province": row["prefecture_or_province"],
            "repo_seats": repo_seats,
            "official_seats": official_seats,
            "name_match_mode": "EXPLICIT_ALIAS" if source_key in aliases else "NORMALIZED_EXACT",
        }
        matched.append(match)
        used_repo_ids.add(repo["constituency_id"])
        if repo_seats != official_seats:
            differences.append({"kind": "SEAT_MAGNITUDE_MISMATCH", **match})

    for row in repo_rows:
        if row["constituency_id"] not in used_repo_ids:
            differences.append(
                {
                    "kind": "REPO_ROW_NOT_IN_OFFICIAL_WITNESS",
                    "constituency_id": row["constituency_id"],
                    "repo_name": row["name"],
                    "repo_seats": int(row["seats"]),
                }
            )

    require(len(regional_rows) == 12, f"regional row count {len(regional_rows)} != 12")
    require(sum(int(r["seats"]) for r in regional_rows) == 90, "regional seat total != 90")
    regional_differences = []
    regional_normalized = {}
    for row in regional_rows:
        key = norm(row["official_name_fr"])
        # The official French table uses “L'Oriental”; project canonical is “Oriental”.
        if key == "l oriental":
            key = "oriental"
        regional_normalized[key] = int(row["seats"])
    for name, seats in CANONICAL_REGIONAL.items():
        if regional_normalized.get(name) != seats:
            regional_differences.append(
                {
                    "region": name,
                    "expected": seats,
                    "official": regional_normalized.get(name),
                }
            )
    for name, seats in regional_normalized.items():
        if name not in CANONICAL_REGIONAL:
            regional_differences.append(
                {"region": name, "expected": None, "official": seats, "kind": "UNEXPECTED_REGION"}
            )

    probe_statuses = {row["id"]: row.get("status") for row in probe["sources"]}
    require(probe_statuses, "geometry acquisition probe has no sources")
    require(all(status == 403 for status in probe_statuses.values()), "probe status changed; re-audit live acquisition")

    passed = not differences and not regional_differences and len(matched) == 92
    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-GEOMETRY-2026-CERTIFICATE-V1",
        "as_of": "2026-08-16",
        "gate": "PASS" if passed else "FAIL",
        "status": "RESOLVED_WITH_ACTIVE_LEGAL_WATCH" if passed else "BLOCKED",
        "epistemic_boundary": (
            "The project geometry is certified against the current official Parliament map/list witness and "
            "the SGG Article-1 regional table. Direct runner retrieval remains WAF-blocked; a superseding "
            "decree or official 2026 publication requires a new certificate version."
        ),
        "source_hashes": {
            "repo_local_csv_sha256": digest(REPO_LOCAL),
            "official_local_witness_sha256": digest(OFFICIAL_LOCAL),
            "official_regional_witness_sha256": digest(OFFICIAL_REGIONAL),
            "witness_metadata_sha256": digest(WITNESS),
            "acquisition_probe_sha256": digest(PROBE),
        },
        "local": {
            "repo_rows": len(repo_rows),
            "official_rows": len(official_rows),
            "matched_rows": len(matched),
            "repo_seats": sum(int(r["seats"]) for r in repo_rows),
            "official_seats": sum(int(r["seats"]) for r in official_rows),
            "differences": differences,
            "rows": matched,
        },
        "regional": {
            "rows": len(regional_rows),
            "seats": sum(int(r["seats"]) for r in regional_rows),
            "differences": regional_differences,
            "canonical": CANONICAL_REGIONAL,
        },
        "house_seats": 395,
        "direct_official_acquisition": {
            "status": "WAF_403_RECORDED",
            "probe_statuses": probe_statuses,
            "artifact": "morocco26/data/goal100/geometry_2026_probe.json",
        },
        "legal_watch": witness["legal_watch"],
    }
    OUT.write_text(json.dumps(certificate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gate": certificate["gate"],
                "local_matched": len(matched),
                "local_differences": len(differences),
                "regional_differences": len(regional_differences),
                "house_seats": 395,
                "legal_watch": certificate["legal_watch"]["status"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    raise SystemExit(0 if passed else 3)


if __name__ == "__main__":
    main()
