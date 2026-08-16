#!/usr/bin/env python3
"""Build the empirical top-N seat-margin layer separately from legal quota replay."""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT / "src"))

from morocco26.seat_margin import analyze_vote_rank_margin

PARTY_META = {"constituency_id", "region_code", "seats", "registered", "valid_votes", "data_status"}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Normalized constituency-wide vote CSV")
    parser.add_argument("--winners-json", type=Path, help="Optional {constituency_id:[party,...]} independent winner sets")
    parser.add_argument("--output", type=Path, default=ROOT / "data" / "seat_margin_map_2021.json")
    args = parser.parse_args()

    expected = json.loads(args.winners_json.read_text(encoding="utf-8")) if args.winners_json else {}
    rows = list(csv.DictReader(args.input.open(encoding="utf-8-sig", newline="")))
    results: list[dict[str, object]] = []
    mismatches: list[str] = []
    for row in rows:
        votes = {
            key: int(float(value or 0))
            for key, value in row.items()
            if key not in PARTY_META and value not in (None, "")
        }
        cid = row["constituency_id"]
        result = analyze_vote_rank_margin(
            votes,
            int(row["seats"]),
            valid_votes=int(row["valid_votes"]) if row.get("valid_votes") else None,
            expected_winners=expected.get(cid),
        )
        record = {"constituency_id": cid, "region_code": row.get("region_code"), **result.as_dict()}
        results.append(record)
        if result.winner_set_match is False:
            mismatches.append(cid)

    payload = {
        "schema_version": "1.0",
        "evidence_tier": "VOTE_RANK_DIAGNOSTIC_NOT_LEGAL_ALLOCATION",
        "constituencies": len(results),
        "independent_winner_sets_supplied": len(expected),
        "winner_set_mismatches": mismatches,
        "legal_quota_replay_status": "SEPARATE_GATE_REQUIRES_REGISTERED_DENOMINATORS",
        "records": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in payload.items() if k != "records"}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if not mismatches else 3)


if __name__ == "__main__":
    main()
