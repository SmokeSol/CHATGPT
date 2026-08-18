#!/usr/bin/env python3
"""Recover explicit 2021 head-of-list rank facts from archived Médias24 maps.

Every relevant table is headed "Candidats têtes de liste" in a pre-cutoff
M24_MEDIAS24 archive. A candidate receives CANDIDATE_REGISTERED_RANK=1 only
when the same normalized district and candidate identity are present inside such
a table. This additive postprocessor does not modify the frozen roster run,
open outcomes, or generate predictive judgments.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
LATEST = ER / "historical_rosters_latest.json"
OUT = ER / "evidence/2021_head_list_rank_enrichment"


def norm(value: str | None) -> str:
    if not value:
        return ""
    text = unicodedata.normalize("NFKD", html.unescape(value))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace("’", " ").replace("'", " ").replace("-", " ")
    text = re.sub(r"\b(circonscription|province|prefecture|préfecture|region|région|locale|electorale|électorale)\b", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def norm_person(value: str | None) -> str:
    substitutions = {
        "mohammed": "mohamed",
        "mohammad": "mohamed",
        "mohamad": "mohamed",
        "abdellah": "abdallah",
        "abdelilah": "abdellah",
        "mustapha": "mostafa",
        "yousef": "youssef",
    }
    return " ".join(substitutions.get(t, t) for t in norm(value).split())


def parse_explicit_tables(raw_path: Path) -> tuple[dict[str, set[str]], list[dict[str, Any]]]:
    body = raw_path.read_bytes()
    soup = BeautifulSoup(body.decode("utf-8", errors="replace"), "html.parser")
    explicit: dict[str, set[str]] = defaultdict(set)
    diagnostics: list[dict[str, Any]] = []
    for container in soup.select(".modal"):
        heading = container.find(["h2", "h3"])
        table = container.find("table")
        if not heading or not table:
            continue
        district_source = " ".join(heading.get_text(" ", strip=True).split())
        rows = table.find_all("tr")
        label = ""
        for tr in rows:
            text = " ".join(tr.get_text(" ", strip=True).split())
            if "candidat" in norm(text) and "tete" in norm(text) and "liste" in norm(text):
                label = text
                break
        candidate_names: list[str] = []
        if label:
            for tr in rows:
                cells = [" ".join(x.get_text(" ", strip=True).split()) for x in tr.find_all(["td", "th"])]
                if len(cells) < 2:
                    continue
                name, party = cells[0], cells[1]
                if not name or not party:
                    continue
                if "candidat" in norm(name) or "nombre de siege" in norm(name):
                    continue
                normalized = norm_person(name)
                if len(normalized.split()) >= 2:
                    candidate_names.append(normalized)
                    explicit[norm(district_source)].add(normalized)
        diagnostics.append(
            {
                "district_source": district_source,
                "district_normalized": norm(district_source),
                "explicit_head_list_label": label or None,
                "candidate_names_under_label": candidate_names,
                "candidate_count": len(candidate_names),
            }
        )
    return explicit, diagnostics


def main() -> int:
    pointer = json.loads(LATEST.read_text(encoding="utf-8"))
    roster_path = ROOT / pointer["latest_roster"]
    run_dir = (ROOT / pointer["latest_manifest"]).parent
    roster = json.loads(roster_path.read_text(encoding="utf-8"))

    explicit_by_sha: dict[str, dict[str, set[str]]] = {}
    source_diagnostics: list[dict[str, Any]] = []
    for sha in sorted({r.get("content_sha256") for r in roster if r.get("year") == 2021 and r.get("content_sha256")}):
        raw_path = run_dir / "raw" / f"{sha}.html"
        if not raw_path.exists():
            source_diagnostics.append({"content_sha256": sha, "error": "RAW_HTML_MISSING"})
            continue
        explicit, diagnostics = parse_explicit_tables(raw_path)
        explicit_by_sha[sha] = explicit
        source_diagnostics.append(
            {
                "content_sha256": sha,
                "raw_path": str(raw_path.relative_to(ROOT)),
                "district_tables": diagnostics,
                "explicit_head_list_tables": sum(bool(x["explicit_head_list_label"]) for x in diagnostics),
            }
        )

    enriched_rows: list[dict[str, Any]] = []
    rank_facts: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for source_row in roster:
        if source_row.get("year") != 2021:
            continue
        row = dict(source_row)
        district_key = norm(row.get("district_source"))
        candidate_key = norm_person(row.get("candidate_name_source"))
        sha = row.get("content_sha256")
        exact = candidate_key in explicit_by_sha.get(sha, {}).get(district_key, set())
        row["BALLOT_LIST_PRESENT"] = bool(exact)
        row["CANDIDATE_REGISTERED_RANK"] = 1 if exact else None
        row["rank_evidence_status"] = "EXPLICIT_CANDIDATS_TETES_DE_LISTE" if exact else "MISSING"
        if exact:
            evidence = {
                "year": 2021,
                "territory_id": row.get("territory_id"),
                "id_constituency": row.get("id_constituency"),
                "candidate_name_source": row.get("candidate_name_source"),
                "candidate_name_normalized": candidate_key,
                "party_bucket": row.get("party_bucket"),
                "feature": "CANDIDATE_REGISTERED_RANK",
                "value": 1,
                "source_class": "M24_MEDIAS24",
                "original_url": row.get("original_url"),
                "archive_timestamp": row.get("archive_timestamp"),
                "content_sha256": sha,
                "archived_excerpt": "Candidats têtes de liste",
            }
            row["head_list_rank_evidence"] = evidence
            rank_facts.append(evidence)
        else:
            row["head_list_rank_evidence"] = None
            unmatched.append(
                {
                    "district_source": row.get("district_source"),
                    "candidate_name_source": row.get("candidate_name_source"),
                    "content_sha256": sha,
                    "territory_id": row.get("territory_id"),
                }
            )
        enriched_rows.append(row)

    by_territory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched_rows:
        if row.get("territory_id"):
            by_territory[row["territory_id"]].append(row)
    identity_districts = sum(len({x["candidate_name_normalized"] for x in rows}) >= 3 for rows in by_territory.values())
    enriched_districts = sum(
        any(
            x.get("CANDIDATE_REGISTERED_RANK") == 1
            or x.get("INCUMBENT_SAME_PARTY_SAME_DISTRICT") is True
            or x.get("PARTY_SWITCH_IN") is True
            for x in rows
        )
        for rows in by_territory.values()
    )
    gate_pass = identity_districts >= 70 and enriched_districts >= 50

    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_run_id": pointer["latest_run_id"],
        "source_roster": pointer["latest_roster"],
        "counts": {
            "source_2021_candidate_rows": len(enriched_rows),
            "explicit_rank_candidate_facts": len(rank_facts),
            "unmatched_candidate_rows": len(unmatched),
            "resolved_canonical_districts": len(by_territory),
            "districts_with_at_least_three_verified_candidate_identities": identity_districts,
            "required_identity_districts": 70,
            "districts_with_at_least_one_enriched_candidate_fact": enriched_districts,
            "required_enriched_districts": 50,
            "identity_gate_pass": identity_districts >= 70,
            "enriched_gate_pass": enriched_districts >= 50,
            "gate_pass": gate_pass,
        },
        "status": "E_REASON_2021_COLLECTION_GATE_PASS" if gate_pass else "E_REASON_2021_COLLECTION_PARTIAL",
        "proof_rule": "Same normalized candidate identity inside a pre-cutoff table explicitly labelled Candidats têtes de liste.",
        "unmatched": unmatched,
        "invariants": {
            "candidate_rank_inferred_from_row_order": False,
            "rank_one_from_explicit_head_list_label_only": True,
            "outcomes_unsealed": False,
            "predictive_judgments_generated": False,
            "forecast_delta_generated": False,
            "F1_created": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "enriched_candidate_roster.json").write_text(json.dumps(enriched_rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "rank_facts.json").write_text(json.dumps(rank_facts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "source_diagnostics.json").write_text(json.dumps(source_diagnostics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (OUT / "gate.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "counts": payload["counts"], "unmatched_sample": unmatched[:10]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
