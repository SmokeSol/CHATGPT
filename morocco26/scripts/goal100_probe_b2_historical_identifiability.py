#!/usr/bin/env python3
"""Probe whether the existing repository can identify B2 coefficients historically.

The probe distinguishes outcome data from pre-election feature data. Election
results prove that a list received votes, but they do not retrospectively supply
candidate rank, incumbency, party-switch, network or event states at a forecast
cutoff. Missing features remain missing and generate an explicit backfill queue.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
HIST = G100 / "historical"
B2 = G100 / "b2" / "v1"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
YEARS = (2011, 2016, 2021)
FEATURES = (
    "HEAD_CANDIDATE_INCUMBENT",
    "INCUMBENT_COUNT_ON_LIST",
    "DEFECTION_IN_COUNT",
    "DEFECTION_OUT_COUNT",
    "MUNICIPAL_OFFICEHOLDER_SUPPORT",
    "FORMAL_ALLIANCE_SUPPORT",
    "CAMPAIGN_DISRUPTION_EVENT",
)


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("B2_HISTORICAL_PROBE_FAIL: " + message)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def local_rows(year: int) -> list[dict]:
    path = HIST / f"tafra_legislative_{year}_canonical.json"
    require(path.exists(), f"missing canonical {year}")
    rows = [row for row in load(path).get("rows", []) if str(row.get("list_type", "")).lower() == "locale"]
    require(len(rows) == 92, f"{year} local rows {len(rows)} != 92")
    return rows


def main() -> None:
    require(B2.exists(), "B2 scaffold missing")
    by_year = {year: local_rows(year) for year in YEARS}
    id_sets = [{str(row["id_constituency"]) for row in rows} for rows in by_year.values()]
    common = set.intersection(*id_sets)
    require(len(common) == 92, f"common modern territory IDs {len(common)} != 92")

    result_availability = {
        "OUTCOME_VOTE_COUNTS": {"coverage": 1.0, "role": "target_or_baseline_not_B2_feature"},
        "SOURCE_ELECTION_LIST_RECEIVED_POSITIVE_VOTES": {"coverage": 1.0, "role": "partial historical list-presence lower bound only"},
        "REGISTERED_VOTERS_2011": {"coverage": 1.0, "role": "structural denominator input"},
        "REGISTERED_VOTERS_2016": {"coverage": 0.0, "role": "missing_in_canonical_panel"},
        "REGISTERED_VOTERS_2021": {"coverage": 0.0, "role": "missing_in_canonical_panel"},
    }
    for feature in FEATURES:
        result_availability[feature] = {
            "coverage": 0.0,
            "role": "B2_predictive_feature",
            "reason": "no cutoff-specific source-backed historical feature panel found in canonical election result files"
        }

    # Outcome/result data cannot be relabelled as a pre-election candidate feature.
    predictive_identified = [
        feature for feature in FEATURES
        if result_availability[feature]["coverage"] > 0
    ]

    queue = []
    for year in YEARS:
        rows = sorted(by_year[year], key=lambda row: int(row["id_constituency"]))
        for row in rows:
            territory = str(row["id_constituency"])
            name = str(row["constituency"])
            for feature in FEATURES:
                queue.append({
                    "task_id": f"B2H-{year}-{territory}-{feature}",
                    "election_year": year,
                    "territory_historical_id": territory,
                    "territory_name": name,
                    "feature_id": feature,
                    "required_cutoff": f"PRE_ELECTION_{year}",
                    "preferred_source_tier": "A_OFFICIAL_OR_ARCHIVED_PRIMARY",
                    "status": "OPEN_MISSING",
                    "evidence_rows": 0,
                    "notes": "",
                })

    queue_path = B2 / "historical_backfill_queue.csv"
    fields = ["task_id", "election_year", "territory_historical_id", "territory_name", "feature_id", "required_cutoff", "preferred_source_tier", "status", "evidence_rows", "notes"]
    with queue_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(queue)

    transitions = ["2011_TO_2016", "2016_TO_2021"]
    report = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-B2-HISTORICAL-IDENTIFIABILITY-PROBE-V1",
        "created_at": NOW,
        "gate": "BLOCKED_HISTORICAL_FEATURE_BACKFILL_REQUIRED",
        "modern_elections": list(YEARS),
        "forecast_transitions_available": transitions,
        "common_local_territories": len(common),
        "result_data_status": "SUFFICIENT_FOR_TARGETS_AND_STRUCTURAL_BASELINE",
        "B2_predictive_feature_status": "NOT_IDENTIFIED_IN_CURRENT_REPO",
        "feature_availability": result_availability,
        "predictive_features_with_nonzero_historical_coverage": predictive_identified,
        "predictive_features_with_zero_historical_coverage": list(FEATURES),
        "historical_backfill_tasks": len(queue),
        "task_formula": f"{len(YEARS)} elections x {len(common)} territories x {len(FEATURES)} feature families",
        "queue": {
            "path": str(queue_path.relative_to(ROOT.parent)),
            "sha256": sha(queue_path)
        },
        "scientific_consequence": {
            "non_legal_B2_coefficients": "MUST_REMAIN_ZERO",
            "F0_adjustment_from_candidate_network_event_features": "BLOCKED",
            "legal_list_constraints": "may still apply when official cutoff-specific 2026 filings are proven",
            "agentic_experiment": "LOCKED"
        },
        "anti_leakage": [
            "Do not use target-election outcomes to reconstruct pre-election candidate features unless a dated source proves they were knowable at cutoff.",
            "Do not code a missing historical candidate as zero.",
            "Do not fit weights on 2026 evidence or on the direction of F0 implications.",
            "A failed historical backfill is a valid result: B2 remains an observation layer with zero residual weight."
        ],
        "next_action": "Backfill the highest-value historical features first: head candidate/incumbency and party switches for 2016 and 2021, with archived cutoff dates and source hashes."
    }
    out = B2 / "historical_identifiability_probe.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    residual_path = B2 / "b2_residual_backtest.json"
    residual = load(residual_path) if residual_path.exists() else {}
    residual.update({
        "gate": "BLOCKED_HISTORICAL_FEATURE_BACKFILL_REQUIRED",
        "identifiability_probe": str(out.relative_to(ROOT.parent)),
        "historical_backfill_tasks": len(queue),
        "predictive_features_identified": 0,
        "non_legal_coefficients": "ALL_ZERO",
        "2026_data_used_for_fit": False,
        "F0_unlocked": False,
        "next_action": report["next_action"]
    })
    residual_path.write_text(json.dumps(residual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    journal_candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    journal = next((path for path in journal_candidates if path.exists()), journal_candidates[0])
    marker = "B2-A006 — Probe d’identifiabilité historique"
    text = journal.read_text(encoding="utf-8")
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Les résultats 2011/2016/2021 couvrent `92/92` territoires et deux transitions, donc les cibles résiduelles sont calculables.\n- Ils ne contiennent pas, au cutoff pré-électoral, les rangs de candidats, incumbency, défections, réseaux ou événements nécessaires à B2.\n- Couverture historique actuelle des 7 familles prédictives B2 : `0 %`; aucune n’est identifiée.\n- File de backfill : `{len(queue)}` tâches (`3 × 92 × 7`).\n- Conséquence : tous les coefficients non juridiques restent exactement zéro ; F0 ajusté reste bloqué.\n- Ce résultat n’est pas contourné avec les résultats de l’élection cible ni avec une reconstruction narrative.\n- Prochaine action exacte : backfill prioritaire 2016/2021 des têtes de liste, incumbents et changements de parti, avec sources archivées et dates de cutoff.\n'''
        journal.write_text(text, encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
