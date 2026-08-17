#!/usr/bin/env python3
"""Prepare Wave-1 B2 collection queues without creating political evidence.

The output is an exhaustive task universe over 92 local and 12 regional contests.
Every field starts UNKNOWN. The queue is a collection plan, never a claim that a
party or candidate is present or absent in 2026.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
G100 = DATA / "goal100"
B2 = G100 / "b2" / "v1"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("B2_QUEUE_FAIL: " + message)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    require(B2.exists(), "B2 scaffold missing")
    local_path = DATA / "constituencies_goal75.csv"
    regional_path = G100 / "geometry_authoritative_regional_rows_fr.csv"
    history_path = G100 / "historical" / "tafra_legislative_2021_canonical.json"
    require(local_path.exists(), "local geometry CSV missing")
    require(regional_path.exists(), "regional geometry CSV missing")
    require(history_path.exists(), "canonical 2021 history missing")

    local = read_csv(local_path)
    regional = read_csv(regional_path)
    require(len(local) == 92, f"local contest count {len(local)} != 92")
    require(len(regional) == 12, f"regional contest count {len(regional)} != 12")
    require(sum(int(row["seats"]) for row in local) == 305, "local seats != 305")
    require(sum(int(row["seats"]) for row in regional) == 90, "regional seats != 90")

    contests = []
    for row in local:
        contests.append({
            "contest_id": row["constituency_id"],
            "contest_type": "LOCAL",
            "contest_name": row["name"],
            "region": row["region"],
            "magnitude": int(row["seats"]),
        })
    for index, row in enumerate(regional, 1):
        name = row["official_name_fr"]
        contests.append({
            "contest_id": f"REG-{index:02d}",
            "contest_type": "REGIONAL",
            "contest_name": name,
            "region": name,
            "magnitude": int(row["seats"]),
        })
    require(len(contests) == 104 and sum(row["magnitude"] for row in contests) == 395,
            "104-contest/395-seat invariant failed")

    tasks = []
    required_fields = [
        ("OFFICIAL_FILING_UNIVERSE", "A_OFFICIAL", "CRITICAL"),
        ("HEAD_CANDIDATE_IDENTITY", "A_OFFICIAL", "CRITICAL"),
        ("FULL_CANDIDATE_RANKS", "A_OFFICIAL", "HIGH"),
        ("INCUMBENT_2026_STATUS", "A_OFFICIAL_OR_B_PRIMARY", "HIGH"),
        ("PARTY_SWITCHES", "A_OFFICIAL_OR_B_PRIMARY", "HIGH"),
        ("FORMAL_ALLIANCES_AND_ENDORSEMENTS", "A_OFFICIAL_OR_B_PRIMARY", "MEDIUM"),
        ("LOCAL_OFFICEHOLDER_NETWORK", "A_OFFICIAL_OR_B_PRIMARY", "MEDIUM"),
        ("VERIFIED_TAXONOMY_EVENTS", "A_TO_C", "MEDIUM"),
    ]
    for contest in contests:
        for field, tier, priority in required_fields:
            tasks.append({
                "task_id": f"B2Q-{contest['contest_id']}-{field}",
                "wave": 1 if field in {"OFFICIAL_FILING_UNIVERSE", "HEAD_CANDIDATE_IDENTITY", "FULL_CANDIDATE_RANKS"} else 2 if field in {"INCUMBENT_2026_STATUS", "PARTY_SWITCHES"} else 3 if field in {"FORMAL_ALLIANCES_AND_ENDORSEMENTS", "LOCAL_OFFICEHOLDER_NETWORK"} else 4,
                "priority": priority,
                "contest_id": contest["contest_id"],
                "contest_type": contest["contest_type"],
                "contest_name": contest["contest_name"],
                "region": contest["region"],
                "magnitude": contest["magnitude"],
                "required_field": field,
                "minimum_source_tier": tier,
                "status": "OPEN_UNKNOWN",
                "assigned_source_id": "",
                "evidence_count": 0,
                "closed_universe_certified": False,
                "notes": "",
            })

    history = load(history_path)
    party_codes = sorted({
        str(party)
        for row in history.get("rows", [])
        for party, votes in row.get("votes", {}).items()
        if int(votes or 0) > 0
    })
    source_tasks = [
        {
            "task_id": "B2SRC-MA-INTERIOR-ELECTION-HUB",
            "source_scope": "ELECTION_AUTHORITY",
            "party_code": "",
            "required_tier": "A_OFFICIAL",
            "status": "OPEN_DISCOVERY",
            "expected_output": "exact official endpoint(s), update cadence, content hash and WAF/access notes",
        },
        {
            "task_id": "B2SRC-MA-SGG-ELECTORAL-LAW",
            "source_scope": "LEGAL_WATCH",
            "party_code": "",
            "required_tier": "A_OFFICIAL",
            "status": "OPEN_DISCOVERY",
            "expected_output": "exact consolidated law/decree endpoints and last-modified checks",
        },
        {
            "task_id": "B2SRC-MA-PARLIAMENT-INCUMBENTS",
            "source_scope": "INCUMBENCY",
            "party_code": "",
            "required_tier": "A_OFFICIAL",
            "status": "OPEN_DISCOVERY",
            "expected_output": "member identity, constituency, party and source hash",
        },
    ]
    for code in party_codes:
        source_tasks.append({
            "task_id": f"B2SRC-PARTY-{code}",
            "source_scope": "PARTY_OFFICIAL",
            "party_code": code,
            "required_tier": "A_OFFICIAL",
            "status": "OPEN_DISCOVERY",
            "expected_output": "official site/account/communiqué endpoints; no evidence claim until verified",
        })

    queue_path = B2 / "collection_queue.csv"
    source_queue_path = B2 / "source_discovery_queue.csv"
    contest_path = B2 / "contest_registry.csv"
    write_csv(contest_path,
              ["contest_id", "contest_type", "contest_name", "region", "magnitude"], contests)
    write_csv(queue_path,
              ["task_id", "wave", "priority", "contest_id", "contest_type", "contest_name", "region", "magnitude", "required_field", "minimum_source_tier", "status", "assigned_source_id", "evidence_count", "closed_universe_certified", "notes"], tasks)
    write_csv(source_queue_path,
              ["task_id", "source_scope", "party_code", "required_tier", "status", "expected_output"], source_tasks)

    # Initialise one coverage row per task. This is explicitly not a party-list
    # universe; it is a required-field coverage denominator.
    coverage_rows = [
        {
            "cutoff": "UNSET",
            "territory_id": task["contest_id"],
            "party_or_list_id": "__UNIVERSE__",
            "required_field": task["required_field"],
            "coverage_status": "UNKNOWN",
            "evidence_count": 0,
            "certified_closed_universe": False,
        }
        for task in tasks
    ]
    write_csv(B2 / "coverage_matrix.csv",
              ["cutoff", "territory_id", "party_or_list_id", "required_field", "coverage_status", "evidence_count", "certified_closed_universe"], coverage_rows)

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-COLLECTION-QUEUE-V1",
        "created_at": NOW,
        "gate": "PASS",
        "claims_created": 0,
        "evidence_rows_created": 0,
        "contests": {"local": 92, "regional": 12, "total": 104, "seats": 395},
        "collection_tasks": len(tasks),
        "source_discovery_tasks": len(source_tasks),
        "2021_positive_vote_party_codes_for_source_discovery_only": party_codes,
        "all_coverage_initially_unknown": True,
        "artifacts": {
            "contest_registry": {"path": str(contest_path.relative_to(ROOT.parent)), "sha256": sha(contest_path)},
            "collection_queue": {"path": str(queue_path.relative_to(ROOT.parent)), "sha256": sha(queue_path)},
            "source_discovery_queue": {"path": str(source_queue_path.relative_to(ROOT.parent)), "sha256": sha(source_queue_path)},
            "coverage_matrix": {"path": str((B2 / "coverage_matrix.csv").relative_to(ROOT.parent)), "sha256": sha(B2 / "coverage_matrix.csv")},
        },
        "epistemic_rule": "Queue rows are tasks, not evidence. A 2021 party code only triggers source discovery and does not imply a 2026 filed list."
    }
    (B2 / "collection_queue_certificate.json").write_text(
        json.dumps(certificate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    journal_candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    journal = next((path for path in journal_candidates if path.exists()), journal_candidates[0])
    marker = "B2-A003 — File de collecte exhaustive 104 scrutins"
    text = journal.read_text(encoding="utf-8") if journal.exists() else "# MOROCCO//26 — FIL D’ARIANE\n"
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Univers de tâches créé pour `92` scrutins locaux et `12` régionaux, total `395` sièges.\n- Chaque champ démarre `UNKNOWN`; aucune liste 2026, candidature ou défection n’est inférée.\n- Les codes de partis 2021 servent uniquement à découvrir les endpoints officiels, jamais à affirmer une présence 2026.\n- Wave 1 prioritaire : univers officiel des listes et rangs de candidats.\n- En parallèle : backfill historique B2 nécessaire pour identifier les coefficients ; sans lui, poids non juridiques = zéro.\n- Prochaine action exacte : résoudre les tâches `B2SRC-*`, enregistrer les endpoints exacts et leurs hashes, puis créer les premières lignes atomiques Tier A.\n'''
        journal.write_text(text, encoding="utf-8")

    print(json.dumps(certificate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
