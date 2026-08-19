#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
H = G / "historical"
OUT = G / "forecast_lab" / "seat_allocator_validation_v1.json"
CONTRACT = G / "forecast_lab" / "seat_allocator_contract_v1.json"

spec = importlib.util.spec_from_file_location("lsa", ROOT / "scripts" / "legal_seat_allocator_v1.py")
lsa = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lsa)


def rj(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def local_rows(year: int):
    if year == 2007:
        d = rj(H / "2007" / "legislative_2007_outcome_canonical.json")
        return list(d["local_rows"]), d
    d = rj(H / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in d["rows"] if str(r.get("list_type", "")).lower() in {"local", "locale"}]
    return rows, d


def nonzero(d):
    return {str(k): int(v) for k, v in d.items() if int(v) != 0}


def group_2007(d):
    out = dict(d)
    sap = sum(out.pop(k, 0) for k in ("SAP", "SAP2", "SAP3"))
    if sap:
        out["SAP_GROUP"] = out.get("SAP_GROUP", 0) + sap
    return nonzero(out)


def validate_2007():
    rows, doc = local_rows(2007)
    mismatches = []
    ties = []
    aggregate = defaultdict(int)
    for r in rows:
        got = lsa.allocate(year=2007, votes=r["votes"], seats=int(r["magnitude"]))
        if got["status"] == "UNRESOLVED_LEGAL_TIE":
            ties.append(r["native_id"])
            continue
        if got["status"] != "ALLOCATED":
            mismatches.append({"native_id": r["native_id"], "kind": got["status"]})
            continue
        observed = nonzero(got["allocation"])
        expected = nonzero(r.get("local_seat_allocation_reconstructed") or {})
        if observed != expected:
            mismatches.append({"native_id": r["native_id"], "kind": "ROW_ALLOCATION_MISMATCH", "expected": expected, "observed": observed})
        for p, n in got["allocation"].items():
            aggregate[p] += int(n)
    grouped = group_2007(aggregate)
    official = nonzero(doc["district_seat_reconstruction"]["official_local_seats_by_party"])
    magnitude_sum = sum(int(r["magnitude"]) for r in rows)
    status = "PASS_EXACT_295_LOCAL_SEATS_AND_OFFICIAL_AGGREGATE" if (
        len(rows) == 95 and magnitude_sum == 295 and not mismatches and not ties and grouped == official
    ) else "FAIL_2007_REPRODUCTION"
    return {
        "status": status,
        "rows": len(rows),
        "magnitude_sum": magnitude_sum,
        "row_mismatches": mismatches,
        "unresolved_legal_ties": ties,
        "computed_official_grouping": grouped,
        "official_local_seats": official,
        "aggregate_exact_match": grouped == official,
    }


def validate_old_regime(year: int):
    rows, _ = local_rows(year)
    blocked = []
    allocated = []
    aggregate = defaultdict(int)
    for r in rows:
        got = lsa.allocate(year=year, votes=r["votes"], seats=int(r["seats"]))
        if got["status"] != "ALLOCATED":
            blocked.append({"constituency": r.get("constituency"), "status": got["status"]})
            continue
        if sum(got["allocation"].values()) != int(r["seats"]):
            blocked.append({"constituency": r.get("constituency"), "status": "SEAT_SUM_MISMATCH"})
            continue
        allocated.append(r.get("constituency"))
        for p, n in got["allocation"].items():
            aggregate[p] += int(n)
    magnitude_sum = sum(int(r["seats"]) for r in rows)
    return {
        "year": year,
        "rows": len(rows),
        "magnitude_sum": magnitude_sum,
        "allocated_rows": len(allocated),
        "blocked_rows": blocked,
        "computed_local_seats_by_party": dict(sorted((p, n) for p, n in aggregate.items() if n)),
        "status": "PASS_FULL_ROW_ARITHMETIC" if len(allocated) == len(rows) and not blocked else "PARTIAL_BLOCKED_REQUIRES_LEGAL_TIE_INPUT",
    }


def validate_2021_data_readiness():
    rows, _ = local_rows(2021)
    allocated = 0
    blocked_registered = 0
    other_blocked = []
    for r in rows:
        got = lsa.allocate(
            year=2021,
            votes=r["votes"],
            seats=int(r["seats"]),
            registered_voters=r.get("registered_reported"),
        )
        if got["status"] == "ALLOCATED":
            allocated += 1
        elif got["status"] == "BLOCKED_REGISTERED_VOTERS_REQUIRED":
            blocked_registered += 1
        else:
            other_blocked.append({"constituency": r.get("constituency"), "status": got["status"]})
    status = "CODE_READY_DATA_BLOCKED_REGISTERED_VOTERS_MISSING" if blocked_registered > 0 and not other_blocked else "REVIEW_2021_DATA_STATE"
    return {
        "status": status,
        "rows": len(rows),
        "allocated_rows": allocated,
        "blocked_missing_registered_voters": blocked_registered,
        "other_blocked": other_blocked,
    }


def unit_tests():
    # Primary judicial numerical anchor from the 2011 Constitutional Council:
    # 53,421 votes of qualified lists / 3 seats = quotient 17,807.
    judicial = lsa.allocate(year=2011, votes={"QUALIFIED_TOTAL_PROXY": 53421}, seats=3)
    judicial_pass = judicial["status"] == "ALLOCATED" and abs(judicial["quotient"] - 17807.0) < 1e-12

    # Version test: a 4% list is excluded under 2011's 6% threshold and included under 2016's 3% threshold.
    v2011 = lsa.allocate(year=2011, votes={"A": 960, "B": 40}, seats=3)
    v2016 = lsa.allocate(year=2016, votes={"A": 960, "B": 40}, seats=3)
    threshold_version_pass = (
        "B" in v2011.get("excluded_below_threshold", [])
        and "B" not in v2016.get("excluded_below_threshold", [])
    )

    # Registered-voter quotient test for the post-2021 regime.
    post = lsa.allocate(year=2021, votes={"A": 400, "B": 300, "C": 200}, seats=3, registered_voters=1200)
    post_pass = post["status"] == "ALLOCATED" and abs(post["quotient"] - 400.0) < 1e-12 and post["allocation"] == {"A": 1, "B": 1, "C": 1}
    missing = lsa.allocate(year=2021, votes={"A": 400, "B": 300}, seats=3)
    missing_pass = missing["status"] == "BLOCKED_REGISTERED_VOTERS_REQUIRED"

    # Exact remainder tie crossing the last seat must remain unresolved.
    tie = lsa.allocate(year=2011, votes={"A": 100, "B": 100, "C": 100}, seats=2)
    tie_pass = tie["status"] == "UNRESOLVED_LEGAL_TIE"

    return {
        "2011_judicial_quotient": {"status": "PASS" if judicial_pass else "FAIL", "expected": 17807.0, "observed": judicial.get("quotient")},
        "2011_vs_2016_threshold_version": {"status": "PASS" if threshold_version_pass else "FAIL", "2011_excluded": v2011.get("excluded_below_threshold"), "2016_excluded": v2016.get("excluded_below_threshold")},
        "2021_registered_voter_quotient": {"status": "PASS" if post_pass else "FAIL", "quotient": post.get("quotient"), "allocation": post.get("allocation")},
        "2021_missing_registered_hard_block": {"status": "PASS" if missing_pass else "FAIL"},
        "legal_tie_not_silently_broken": {"status": "PASS" if tie_pass else "FAIL", "allocator_status": tie.get("status")},
        "all_pass": all((judicial_pass, threshold_version_pass, post_pass, missing_pass, tie_pass)),
    }


def main():
    contract = rj(CONTRACT)
    if contract.get("contract_id") != "M26-LEGAL-SEAT-ALLOCATOR-V1" or contract.get("status") != "FROZEN_BEFORE_VALIDATION_RUN":
        raise RuntimeError("SEAT_ALLOCATOR_CONTRACT_NOT_FROZEN")

    tests = unit_tests()
    y2007 = validate_2007()
    y2011 = validate_old_regime(2011)
    y2016 = validate_old_regime(2016)
    y2021 = validate_2021_data_readiness()

    result = {
        "schema_version": "1.0",
        "result_id": "M26-LEGAL-SEAT-ALLOCATOR-VALIDATION-V1",
        "contract_id": contract["contract_id"],
        "unit_tests": tests,
        "regimes": {
            "2007": y2007,
            "2011": y2011,
            "2016": y2016,
            "2021": y2021,
            "2026": {
                "status": "CODE_READY_AWAITS_FINAL_REGISTERED_COUNTS_AND_BALLOT",
                "quotient_basis": "REGISTERED_VOTERS",
                "final_ballot_required": True,
                "candidate_identity_rule_scope": "OUT_OF_SCOPE_OF_SEAT_COUNT_ALLOCATOR",
            },
        },
        "historical_local_validation_status": "PASS" if (
            tests["all_pass"]
            and y2007["status"].startswith("PASS")
            and y2011["status"] == "PASS_FULL_ROW_ARITHMETIC"
            and y2016["status"] == "PASS_FULL_ROW_ARITHMETIC"
        ) else "REVIEW_REQUIRED",
        "2021_exact_historical_seat_validation": "BLOCKED_UNTIL_REGISTERED_VOTERS_BY_CONSTITUENCY_ARE_AVAILABLE" if y2021["blocked_missing_registered_voters"] else "AVAILABLE",
        "forecast_pipeline_effect": "NONE_UNTIL_EXPLICITLY_WIRED_AFTER_VALIDATION",
        "F0_modified": False,
    }
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "historical": result["historical_local_validation_status"],
        "2007": y2007["status"],
        "2011": y2011["status"],
        "2016": y2016["status"],
        "2021": y2021["status"],
        "unit_tests": tests["all_pass"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
