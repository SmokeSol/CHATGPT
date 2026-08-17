#!/usr/bin/env python3
"""Prioritize historical B2 collection tasks without assigning forecast weights.

Priority is a research-efficiency score using only election recency, district
magnitude and observed historical competitiveness. It never changes a forecast,
a feature value or a residual coefficient.
"""
from __future__ import annotations

import csv
import json
import math
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
HIST = G100 / "historical"
B2 = G100 / "b2" / "v1"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()

RECENCY = {2011: 0.50, 2016: 0.75, 2021: 1.00}
FEATURE_VALUE = {
    "HEAD_CANDIDATE_INCUMBENT": 1.00,
    "INCUMBENT_COUNT_ON_LIST": 0.90,
    "DEFECTION_IN_COUNT": 0.85,
    "DEFECTION_OUT_COUNT": 0.85,
    "MUNICIPAL_OFFICEHOLDER_SUPPORT": 0.60,
    "FORMAL_ALLIANCE_SUPPORT": 0.55,
    "CAMPAIGN_DISRUPTION_EVENT": 0.40,
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("B2_BACKFILL_PRIORITY_FAIL: " + message)


def local_by_id(year: int) -> dict[str, dict]:
    rows = [row for row in load(HIST / f"tafra_legislative_{year}_canonical.json")["rows"] if str(row.get("list_type", "")).lower() == "locale"]
    require(len(rows) == 92, f"{year} local rows != 92")
    return {str(row["id_constituency"]): row for row in rows}


def competitiveness(row: dict) -> tuple[float, float, float]:
    votes = [int(value or 0) for value in row.get("votes", {}).values() if int(value or 0) > 0]
    require(len(votes) >= 2, f"territory {row.get('id_constituency')} has <2 positive lists")
    total = sum(votes)
    shares = sorted((value / total for value in votes), reverse=True)
    gap = shares[0] - shares[1]
    entropy = -sum(share * math.log(share) for share in shares)
    normalized_entropy = entropy / math.log(len(shares)) if len(shares) > 1 else 0.0
    score = 0.5 * (1.0 - gap) + 0.5 * normalized_entropy
    return score, gap, normalized_entropy


def main() -> None:
    queue_path = B2 / "historical_backfill_queue.csv"
    require(queue_path.exists(), "historical backfill queue missing")
    with queue_path.open(encoding="utf-8", newline="") as handle:
        tasks = list(csv.DictReader(handle))
    require(len(tasks) == 1932, f"backfill task count {len(tasks)} != 1932")
    histories = {year: local_by_id(year) for year in RECENCY}

    ranked = []
    for task in tasks:
        year = int(task["election_year"])
        territory = task["territory_historical_id"]
        feature = task["feature_id"]
        row = histories[year][territory]
        comp, gap, entropy = competitiveness(row)
        magnitude = int(row["seats"])
        score = RECENCY[year] * FEATURE_VALUE[feature] * magnitude * comp
        ranked.append({
            **task,
            "recency_weight": RECENCY[year],
            "feature_research_weight": FEATURE_VALUE[feature],
            "district_magnitude": magnitude,
            "top_two_share_gap": gap,
            "normalized_vote_entropy": entropy,
            "historical_competitiveness": comp,
            "collection_priority_score": score,
        })

    ranked.sort(key=lambda row: (-float(row["collection_priority_score"]), -int(row["election_year"]), row["territory_historical_id"], row["feature_id"]))
    for index, row in enumerate(ranked, 1):
        row["priority_rank"] = index
        row["priority_band"] = "P0_TOP_100" if index <= 100 else "P1_TOP_300" if index <= 300 else "P2_TOP_750" if index <= 750 else "P3_REMAINDER"

    fields = [
        "priority_rank", "priority_band", "task_id", "election_year", "territory_historical_id", "territory_name", "feature_id", "required_cutoff", "preferred_source_tier", "status", "evidence_rows", "recency_weight", "feature_research_weight", "district_magnitude", "top_two_share_gap", "normalized_vote_entropy", "historical_competitiveness", "collection_priority_score", "notes"
    ]
    out = B2 / "historical_backfill_priority.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(ranked)

    top100 = ranked[:100]
    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-HISTORICAL-BACKFILL-PRIORITY-V1",
        "created_at": NOW,
        "gate": "PASS_RESEARCH_PRIORITY_ONLY",
        "tasks_ranked": len(ranked),
        "formula": "recency_weight * feature_research_weight * district_magnitude * [0.5*(1-top2_gap)+0.5*normalized_entropy]",
        "weights": {"recency": RECENCY, "feature_research": FEATURE_VALUE},
        "top100_distribution": {
            "election_year": {str(year): sum(int(row["election_year"]) == year for row in top100) for year in RECENCY},
            "feature": {feature: sum(row["feature_id"] == feature for row in top100) for feature in FEATURE_VALUE},
            "territories": len({(row["election_year"], row["territory_historical_id"]) for row in top100}),
        },
        "forecast_effect": False,
        "coefficient_effect": False,
        "evidence_created": False,
        "scientific_boundary": "The score determines only collection order. It must never be used as an electoral feature or forecast weight.",
        "next_action": "Execute P0_TOP_100 starting with 2021/2016 head-candidate and incumbency tasks; require archived pre-election source timestamps."
    }
    (B2 / "historical_backfill_priority_certificate.json").write_text(json.dumps(certificate, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    journal_candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    journal = next((path for path in journal_candidates if path.exists()), journal_candidates[0])
    marker = "B2-A008 — Priorisation du backfill historique"
    text = journal.read_text(encoding="utf-8")
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Les `{len(ranked)}` tâches historiques sont classées par récence, magnitude et compétitivité historique.\n- Les poids de classement concernent uniquement le coût d’acquisition ; ils n’entrent jamais dans le forecast.\n- Bande immédiate : `P0_TOP_100`, centrée sur les têtes de liste/incumbency les plus récentes et les territoires à forte valeur d’information.\n- Aucune évidence, feature ou coefficient n’est créé par le ranking.\n- Prochaine action exacte : exécuter les 100 premières tâches avec archives pré-électorales datées ; rejeter toute source publiée après le cutoff historique ciblé.\n'''
        journal.write_text(text, encoding="utf-8")

    print(json.dumps(certificate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
