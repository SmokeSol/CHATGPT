#!/usr/bin/env python3
"""Fail-closed validation for B2-1 source-universe closure."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"


def load(name: str):
    path = G100 / name
    if not path.exists():
        raise SystemExit(f"B2_SOURCE_VALIDATION_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_SOURCE_VALIDATION_FAIL: {message}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def universe_payload(registry: dict) -> dict:
    entries = []
    for source in registry["source_entries"]:
        row = dict(source)
        row.pop("operational_state", None)
        row.pop("probe_result", None)
        entries.append(row)
    return {
        "registry_id": registry["registry_id"],
        "protocol_id": registry["protocol_id"],
        "source_universe_frozen_at": registry["source_universe_frozen_at"],
        "in_scope_parties": registry["in_scope_parties"],
        "party_official_source_map": registry["party_official_source_map"],
        "source_entries": entries,
        "query_templates": registry["query_templates"],
        "prohibited_sources": registry["prohibited_sources"],
        "smoke_test_contract": registry["smoke_test_contract"],
        "closure_requirements": registry["closure_requirements"],
        "independence_rule": registry["independence_rule"],
        "archive_rule": registry["archive_rule"],
    }


def main() -> None:
    registry = load("b2_source_registry.json")
    probe = load("b2_source_universe_probe.json")
    certificate = load("b2_source_universe_certificate.json")
    gates = load("b2_gate_registry.json")
    state = load("b2_current_state.json")
    event = load("fil_ariane_events/A020.json")

    require(registry["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED", "source registry is not bounded-enabled")
    require(registry["collection_allowed"] is True, "source registry collection flag is false")
    require(probe["gate"] == certificate["gate"] == "PASS", "source probe/certificate gate not PASS")
    expected_hash = canonical_sha256(universe_payload(registry))
    require(probe["source_universe_sha256"] == expected_hash, "probe source-universe hash drift")
    require(certificate["source_universe_sha256"] == expected_hash, "certificate source-universe hash drift")
    require(registry["smoke_test"]["source_universe_sha256"] == expected_hash, "registry smoke source-universe hash drift")
    require(len(registry["source_entries"]) == probe["source_count"] == certificate["source_count"] == 19, "source coverage drift")
    require(len(registry["query_templates"]) == probe["query_template_count"] == certificate["query_template_count"] == 5, "query-template coverage drift")

    contract = registry["smoke_test_contract"]
    require(certificate["active_T0_sources"] >= contract["minimum_active_T0_sources"], "active T0 threshold failed")
    require(certificate["represented_T1_parties"] >= contract["minimum_represented_T1_parties"], "represented T1 threshold failed")
    require(certificate["active_T1_parties"] >= contract["minimum_active_T1_parties"], "active T1 threshold failed")
    require(certificate["active_T2_independence_clusters"] >= contract["minimum_active_T2_independence_clusters"], "active T2 cluster threshold failed")
    require(certificate["total_active_sources"] >= contract["minimum_total_active_sources"], "total active source threshold failed")
    require(certificate["claim_records_before_pass"] == 0, "claims existed before source-universe PASS")
    require(all(certificate["checks"].values()), "one or more frozen source checks failed")

    probe_by_id = {row["source_id"]: row for row in probe["sources"]}
    registry_by_id = {row["source_id"]: row for row in registry["source_entries"]}
    require(set(probe_by_id) == set(registry_by_id), "probe/source registry ID mismatch")
    active_ids = set(certificate["active_source_ids"])
    reference_ids = set(certificate["reference_only_source_ids"])
    inactive_ids = set(certificate["inactive_source_ids"])
    require(not (active_ids & reference_ids or active_ids & inactive_ids or reference_ids & inactive_ids), "operational source classes overlap")
    require(active_ids | reference_ids | inactive_ids == set(registry_by_id), "operational source classes are incomplete")
    for source_id, source in registry_by_id.items():
        probe_row = probe_by_id[source_id]
        require(source["operational_state"] == probe_row["operational_state"], f"operational state mismatch for {source_id}")
        require(source["probe_result"]["access_class"] == probe_row["access_class"], f"access class mismatch for {source_id}")
        require(source["probe_result"]["content_sha256"] == probe_row["content_sha256"], f"content hash mismatch for {source_id}")
        if source["operational_state"] == "ACTIVE":
            require(probe_row["status_code"] == 200, f"active source {source_id} did not return HTTP 200")
            require(probe_row["final_domain_allowed"] is True, f"active source {source_id} redirected outside allowlist")
            require(probe_row["challenge_marker"] is None, f"active source {source_id} contains a challenge marker")

    gate = next(row for row in gates["gates"] if row["id"] == "B2-1-SOURCE-UNIVERSE-FROZEN")
    require(gate["status"] == "CLOSED", "B2-1 gate is not CLOSED")
    require(gate["required_artifact"] == "morocco26/data/goal100/b2_source_universe_certificate.json", "B2-1 artifact path drift")
    require(gates["next_gate"] == "B2-2-IDENTITY-TERRITORY-CROSSWALK", "next B2 gate is not B2-2")
    require(all(row["status"] == "LOCKED" for row in gates["agentic_gates"]), "agentic gate unlocked")
    require(next(row for row in gates["gates"] if row["id"] == "B2-8-F0-COUNTERFACTUAL-SIMULATION")["status"] == "LOCKED", "F0 gate unlocked")

    require(state["phase"] == "B2_SOURCE_UNIVERSE_FROZEN_COLLECTION_ENABLED", "B2 state phase drift")
    require(state["collection"]["status"] == "ENABLED_BOUNDED", "B2 collection state not bounded-enabled")
    require(state["collection"]["evidence_records"] == 0, "B2 evidence count nonzero at source closure")
    require(state["collection"]["source_universe_sha256"] == expected_hash, "B2 state source-universe hash drift")
    require(state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION", "predictive coefficient lock drift")

    require(event["event_id"] == "A020" and event["status"] == "PASS", "A020 event invalid")
    require(event["machine_result"]["source_universe_sha256"] == expected_hash, "A020 source-universe hash drift")
    journal = (ROOT / "FIL_ARIANE.md").read_text(encoding="utf-8")
    require("Entrée A020 — Gel de l’univers de sources B2" in journal, "A020 journal entry missing")

    print("B2_SOURCE_UNIVERSE_PASS")
    print(f"source_universe_sha256={expected_hash}")
    print(f"active_T0={certificate['active_T0_sources']}")
    print(f"active_T1_parties={certificate['active_T1_parties']}")
    print(f"active_T2_clusters={certificate['active_T2_independence_clusters']}")
    print(f"active_total={certificate['total_active_sources']}")
    print(f"reference_only={certificate['reference_only_sources']} inactive={certificate['inactive_sources']}")
    print("claim_records_before_pass=0")
    print("next=B2-2-IDENTITY-TERRITORY-CROSSWALK")
    print("predictive_coefficients=ALL_ZERO agentic=ALL_LOCKED")


if __name__ == "__main__":
    main()
