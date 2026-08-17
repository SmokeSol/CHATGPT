#!/usr/bin/env python3
"""Fail-closed validation of the non-agentic B2 protocol freeze."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"


def load(name: str):
    path = G100 / name
    if not path.exists():
        raise SystemExit(f"B2_PROTOCOL_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_PROTOCOL_FAIL: {message}")


def main() -> None:
    protocol = load("b2_protocol_v1.json")
    schema = load("b2_evidence_schema_v1.json")
    features = load("b2_feature_dictionary_v1.json")
    gates = load("b2_gate_registry.json")
    sources = load("b2_source_registry.json")
    b2_state = load("b2_current_state.json")
    f1_cert = load("fminus1_registration_certificate.json")
    f_registry = load("forecast_registry.json")
    current = load("current_state.json")
    global_gates = load("gate_registry.json")
    event = load("fil_ariane_events/A018.json")

    f1_hash = "de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1"
    require(f1_cert["gate"] == "PASS", "F-1 registration certificate not PASS")
    require(f1_cert["forecast_artifact_sha256"] == f1_hash, "F-1 registration hash drift")
    require(f1_cert["all_forecast_unlock_gates_closed"] is True, "F-1 forecast gates not all closed")
    require(f1_cert["all_agentic_gates_locked"] is True, "F-1 certificate says an agentic gate is unlocked")
    require(len(f_registry["snapshots"]) == 1 and f_registry["snapshots"][0]["snapshot_id"] == "F-1", "forecast registry is not exactly [F-1]")
    require(f_registry["snapshots"][0]["forecast_artifact_hash"] == f1_hash, "forecast registry F-1 hash drift")
    require(f_registry["sequence"]["next_id"] == "F0", "forecast registry next snapshot != F0")

    require(protocol["protocol_id"] == "M26-GOAL100-B2-PROTOCOL-V1", "unexpected B2 protocol ID")
    require(protocol["status"] == "FROZEN_PRE_COLLECTION", "B2 protocol not frozen pre-collection")
    require(protocol["parent_snapshot"]["snapshot_id"] == "F-1", "B2 parent snapshot != F-1")
    require(protocol["parent_snapshot"]["forecast_sha256"] == f1_hash, "B2 parent hash drift")
    require(protocol["scientific_role"]["baseline_name"] == "B2", "baseline name drift")
    require(protocol["scientific_role"]["agentic_status"] == "PROHIBITED_AND_LOCKED", "agentic boundary weakened")
    require(protocol["time_contract"]["evidence_cutoff_state"] == "UNSET_UNTIL_B2_FREEZE_CERTIFICATE", "evidence cutoff was prematurely set")
    require(protocol["time_contract"]["timezone"] == "Africa/Casablanca", "B2 timezone drift")
    require(len(protocol["admissible_evidence_classes"]) == 3, "unexpected evidence-class count")
    require(set(protocol["source_tiers"]) == {"T0", "T1", "T2", "T3", "T4"}, "source tiers drift")
    exclusions = " ".join(protocol["explicit_exclusions_v1"]).lower()
    require("poll" in exclusions, "poll exclusion missing")
    require("llm" in exclusions, "LLM exclusion missing")
    require(protocol["collection_contract"]["missingness"].startswith("Missing is NA"), "missingness contract weakened")
    require(protocol["feature_and_effect_contract"]["failure_rule"].startswith("If calibration"), "zero-on-failure rule missing")
    require(protocol["F0_contract"]["required_parent"].startswith("The registered F-1"), "F0 parent contract missing")

    required_record_fields = set(schema["required"])
    require({
        "record_id", "claim_key", "evidence_class", "evidence_type", "subject",
        "territorial_scope", "claim", "time", "source", "verification",
        "extraction", "admissibility", "integrity"
    }.issubset(required_record_fields), "B2 evidence schema required fields weakened")
    require(schema["properties"]["extraction"]["properties"]["llm_used"]["const"] is False, "schema allows LLM extraction")
    require(schema["properties"]["source"]["properties"]["source_tier"]["enum"] == ["T0", "T1", "T2", "T3", "T4"], "schema source-tier order drift")
    require("CONFLICTED" in schema["properties"]["verification"]["properties"]["status"]["enum"], "schema cannot represent conflicts")
    require("POST_CUTOFF" in schema["properties"]["admissibility"]["properties"]["reason_codes"]["items"]["enum"], "schema lacks post-cutoff exclusion")

    feature_rows = features["features"]
    feature_ids = [row["feature_id"] for row in feature_rows]
    require(len(feature_ids) == len(set(feature_ids)), "duplicate B2 feature IDs")
    require(len(feature_rows) >= 15, "B2 feature dictionary unexpectedly small")
    predictive = [row for row in feature_rows if row["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION"]
    require(predictive, "no predictive feature family defined")
    require(all(row["coefficient_state"] == "LOCKED_ZERO_UNTIL_HISTORICAL_CALIBRATION_PASS" for row in predictive), "a predictive coefficient is not locked at zero")
    reporting = [row for row in feature_rows if "REPORTING" in row["forecast_role"]]
    require(all("ZERO" in row["coefficient_state"] for row in reporting), "reporting-only feature acquired a coefficient")
    require(features["global_rules"]["predictive_coefficient_default"] == 0.0, "default predictive coefficient != 0")
    require(features["global_rules"]["no_2026_outcome_used"] is True, "feature dictionary permits 2026 outcome")
    require(features["historical_calibration_contract"]["fit_transition"] == "2011_TO_2016", "B2 fit transition drift")
    require(features["historical_calibration_contract"]["validation_transition"] == "2016_TO_2021", "B2 validation transition drift")
    require(features["historical_calibration_contract"]["core_panel_minimum_coverage_each_transition"] == 0.8, "coverage threshold drift")
    require(features["historical_calibration_contract"]["binary_feature_minimum_positive_instances"] == 30, "minimum support drift")

    b2_gates = {row["id"]: row for row in gates["gates"]}
    expected_ids = {
        "B2-0-PROTOCOL-FROZEN",
        "B2-1-SOURCE-UNIVERSE-FROZEN",
        "B2-2-IDENTITY-TERRITORY-CROSSWALK",
        "B2-3-HISTORICAL-FEATURE-PANEL",
        "B2-4-2026-BALLOT-ROSTER",
        "B2-5-PROVENANCE-CONFLICT-AUDIT",
        "B2-6-EFFECT-CALIBRATION",
        "B2-7-B2-FROZEN",
        "B2-8-F0-COUNTERFACTUAL-SIMULATION",
    }
    require(set(b2_gates) == expected_ids, "B2 gate registry membership drift")
    require(b2_gates["B2-0-PROTOCOL-FROZEN"]["status"] == "CLOSED", "B2-0 not closed")
    for gate_id in expected_ids - {"B2-0-PROTOCOL-FROZEN", "B2-8-F0-COUNTERFACTUAL-SIMULATION"}:
        require(b2_gates[gate_id]["status"] == "OPEN", f"{gate_id} prematurely closed")
    require(b2_gates["B2-8-F0-COUNTERFACTUAL-SIMULATION"]["status"] == "LOCKED", "F0 simulation prematurely unlocked")
    require(all(row["status"] == "LOCKED" for row in gates["agentic_gates"]), "B2 agentic gate unlocked")
    require(gates["next_gate"] == "B2-1-SOURCE-UNIVERSE-FROZEN", "unexpected next B2 gate")

    require(sources["status"] == "DOMAIN_ALLOWLIST_PENDING_COLLECTION_LOCKED", "source registry status drift")
    require(sources["collection_allowed"] is False, "collection enabled before source freeze")
    require(sources["source_entries"] == [], "source entries were collected before source-universe freeze")
    require(sources["query_templates"] == [], "query templates populated without source-universe gate transition")
    evidence_dir = G100 / "b2_evidence"
    require(not evidence_dir.exists() or not any(evidence_dir.rglob("*.json")), "claim records exist before source-universe freeze")

    require(b2_state["phase"] == "B2_PROTOCOL_FROZEN_SOURCE_UNIVERSE_PENDING", "B2 state phase drift")
    require(b2_state["collection"]["status"] == "LOCKED", "B2 state says collection is open")
    require(b2_state["collection"]["evidence_records"] == 0, "B2 state evidence count nonzero")
    require(b2_state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION", "B2 state coefficient lock drift")
    require(b2_state["parent_snapshot"]["forecast_sha256"] == f1_hash, "B2 state parent hash drift")

    require(current["program_phase"] == "P7_B2_STRUCTURED_EVIDENCE_LAYER", "global state is not B2 phase")
    require(current["goal100_objective"]["forecast_status"] == "F-1_ISSUED_IMMUTABLE", "global state lost F-1")
    require(current["goal100_objective"]["next_forecast"] == "F0", "global next forecast != F0")
    require(current["goal75_checkpoint"]["scientifically_gated_completion_percent"] == 75, "Goal75 checkpoint drift")
    require(all(row["status"] == "LOCKED" for row in global_gates["agentic_unlock"]), "global agentic gate unlocked")

    require(event["event_id"] == "A018" and event["status"] == "PASS", "A018 event missing or invalid")
    require(event["machine_result"]["parent_forecast_sha256"] == f1_hash, "A018 parent hash drift")
    journal = (ROOT / "FIL_ARIANE.md").read_text(encoding="utf-8")
    require("Entrée A018 — Gel du protocole B2 non agentique avant collecte" in journal, "FIL_ARIANE A018 entry missing")

    print("B2_PROTOCOL_PASS")
    print(f"protocol={protocol['protocol_id']}")
    print(f"parent_F_minus_1={f1_hash}")
    print(f"features={len(feature_rows)} predictive_locked_zero={len(predictive)}")
    print("collection=LOCKED evidence_records=0")
    print("B2-0=CLOSED next=B2-1-SOURCE-UNIVERSE-FROZEN")
    print("F0=LOCKED agentic=ALL_LOCKED")


if __name__ == "__main__":
    main()
