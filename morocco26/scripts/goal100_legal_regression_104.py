#!/usr/bin/env python3
"""Regression the Goal100 legal allocator over all historically testable contests.

Local 2021:
- 81 denominator-invariant rows use the lower bound of the exhaustive Goal75 N proof.
- 11 denominator-sensitive rows use the explicitly quarantined secondary N already
  recorded by Goal75.

Regional 2021:
- use the same external N/vote vectors as Goal75 and preserve observed-data
  mismatches.  The purpose is to test allocator equivalence, not force every
  independent affiliation table to agree with the vote table.
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from morocco26.legal_allocator_2026 import allocate_2026  # noqa: E402

G75 = ROOT / "data" / "goal75"
HIST = ROOT / "data" / "goal100" / "historical"
OUT = ROOT / "data" / "goal100" / "legal_regression_104.json"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def norm(v):
    s = unicodedata.normalize("NFKD", str(v)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", s)


def clean_alloc(a):
    return {str(k): int(v) for k, v in sorted(a.items()) if int(v) > 0}


def main():
    can21 = load(HIST / "tafra_legislative_2021_canonical.json")
    local_votes = {
        norm(r["constituency"]): r
        for r in can21["rows"]
        if str(r.get("list_type", "")).lower() in {"local", "locale"}
    }
    closure = load(G75 / "local_92_closure_v3.json")
    intervals = load(G75 / "local_allocation_interval_proof.json")
    interval_by_name = {norm(r["circonscription"]): r for r in intervals["rows"]}

    local_rows = []
    local_pass = 0
    local_unresolved = 0
    for row in closure["rows"]:
        key = norm(row["tafra_name"])
        if key not in local_votes:
            raise RuntimeError(f"missing canonical votes for {row['tafra_name']}")
        vr = local_votes[key]
        votes = {p: int(v) for p, v in vr["votes"].items() if int(v) > 0}
        if row.get("registered_used") is not None:
            N = int(row["registered_used"])
            n_source = "goal75_quarantined_secondary_N"
        else:
            proof = interval_by_name.get(key)
            if proof is None or not proof.get("invariant_to_topN_over_full_interval"):
                raise RuntimeError(f"missing invariant proof for {row['tafra_name']}")
            N = int(proof["lower_bound_registered"])
            n_source = "denominator_invariant_proof_lower_bound"

        result = allocate_2026(votes, N, int(row["seats"]))
        expected = clean_alloc(row["legal_allocation"])
        actual = clean_alloc(result.seats_by_list)
        passed = result.complete and actual == expected
        if passed:
            local_pass += 1
        if not result.complete:
            local_unresolved += 1
        local_rows.append({
            "constituency_id": row["constituency_id"],
            "name": row["name"],
            "N": N,
            "N_source": n_source,
            "status": result.status,
            "expected_goal75_legal_allocation": expected,
            "goal100_allocation": actual,
            "allocator_equivalent": passed,
            "observed_elected_match": actual == clean_alloc(row["observed_elected"]),
            "tie_events": list(result.tie_events),
        })

    regional = load(G75 / "regional_exact_crossballot_test.json")
    regional_rows = []
    regional_allocator_equiv = 0
    regional_observed_match = 0
    regional_unresolved = 0
    for row in regional["rows"]:
        result = allocate_2026(
            {p: int(v) for p, v in row["votes"].items() if int(v) > 0},
            int(row["registered_external"]),
            int(row["seats"]),
        )
        expected = clean_alloc(row["legal_list_allocation"])
        actual = clean_alloc(result.seats_by_list)
        equiv = result.complete and actual == expected
        observed_match = result.complete and actual == clean_alloc(row["observed_independent"])
        regional_allocator_equiv += int(equiv)
        regional_observed_match += int(observed_match)
        regional_unresolved += int(not result.complete)
        regional_rows.append({
            "region": row["region"],
            "N": int(row["registered_external"]),
            "seats": int(row["seats"]),
            "status": result.status,
            "expected_goal75_legal_allocation": expected,
            "goal100_allocation": actual,
            "allocator_equivalent": equiv,
            "observed_independent": clean_alloc(row["observed_independent"]),
            "observed_independent_match": observed_match,
            "known_goal75_observed_match": bool(row["exact_match"]),
            "tie_events": list(result.tie_events),
        })

    audit = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-LEGAL-REGRESSION-104-V1",
        "local": {
            "n": len(local_rows),
            "allocator_equivalent": local_pass,
            "unresolved_statutory_ties": local_unresolved,
            "all_equivalent": local_pass == 92 and local_unresolved == 0,
            "rows": local_rows,
        },
        "regional": {
            "n": len(regional_rows),
            "allocator_equivalent_to_goal75_math": regional_allocator_equiv,
            "unresolved_statutory_ties": regional_unresolved,
            "observed_independent_matches": regional_observed_match,
            "expected_known_data_anomalies": sorted(
                r["region"] for r in regional_rows if not r["known_goal75_observed_match"]
            ),
            "rows": regional_rows,
        },
        "gate": "PASS" if (
            local_pass == 92 and local_unresolved == 0 and
            regional_allocator_equiv == 12 and regional_unresolved == 0 and
            regional_observed_match == 10
        ) else "FAIL_CLOSED",
        "interpretation": "PASS requires mathematical equivalence on all 104 vectors and preserves the two known regional vote/observed-affiliation data anomalies rather than laundering them into allocator failures.",
    }
    OUT.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "gate": audit["gate"],
        "local_allocator_equivalent": local_pass,
        "local_unresolved": local_unresolved,
        "regional_allocator_equivalent": regional_allocator_equiv,
        "regional_unresolved": regional_unresolved,
        "regional_observed_matches": regional_observed_match,
        "regional_known_anomalies": audit["regional"]["expected_known_data_anomalies"],
    }, ensure_ascii=False, indent=2))
    if audit["gate"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
