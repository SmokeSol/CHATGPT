#!/usr/bin/env python3
"""Fail-closed validation of the non-agentic B2 protocol and source state."""
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


def validate_source_universe_shape(sources: dict) -> dict:
    entries = sources["source_entries"]
    queries = sources["query_templates"]
    source_ids = [row["source_id"] for row in entries]
    require(len(source_ids) == len(set(source_ids)), "duplicate B2 source IDs")
    require(len(entries) == 19, f"frozen B2 source count {len(entries)} != 19")
    require(len(queries) == 5, f"frozen query-template count {len(queries)} != 5")
    require(len({row["query_id"] for row in queries}) == len(queries), "duplicate query-template IDs")

    tiers = {tier: [row for row in entries if row["tier"] == tier] for tier in ("T0", "T1", "T2")}
    require(len(tiers["T0"]) == 5, "T0 source count drift")
    require(len(tiers["T1"]) == 8, "T1 source count drift")
    require(len(tiers["T2"]) == 6, "T2 source count drift")
    require(len({row["independence_cluster"] for row in tiers["T2"]}) == 6, "T2 independence clusters are not unique")

    parties = sources["in_scope_parties"]
    require(parties == ["RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS"], "in-scope party order/membership drift")
    party_map = sources["party_official_source_map"]
    require(set(party_map) == set(parties), "party/source map coverage drift")
    t1_by_party = {row.get("party_id"): row["source_id"] for row in tiers["T1"]}
    require(t1_by_party == party_map, "party/source map disagrees with T1 entries")

    for row in entries:
        require(row["allowed_domains"], f"source {row['source_id']} lacks allowed domains")
        require(row["probe_url"].startswith("https://"), f"source {row['source_id']} probe is not HTTPS")
        require(row["seed_urls"], f"source {row['source_id']} lacks seed URLs")
        require(all(url.startswith("https://") for url in row["seed_urls"]), f"source {row['source_id']} contains non-HTTPS seed URL")
        require(row["path_allowlist"], f"source {row['source_id']} lacks path allowlist")
        require(row["retrieval_policy"] in {
            "DIRECT_REQUIRED",
            "DIRECT_OR_REFERENCE_ONLY",
            "DIRECT_OR_DOCUMENTED_WAF_REFERENCE_ONLY",
        }, f"source {row['source_id']} has unknown retrieval policy")
        require(row["archive_policy"], f"source {row['source_id']} lacks archive policy")
        require(row["claim_boundary"], f"source {row['source_id']} lacks claim boundary")

    query_ids = {row["query_id"] for row in queries}
    require(query_ids == {
        "Q01_FIXED_SEED_AND_SAME_DOMAIN_LINK_SCAN",
        "Q02_SITEMAP_BOUNDED_SCAN",
        "Q03_EXACT_ENTITY_TERRITORY_SCAN",
        "Q04_OFFICIAL_DIRECTORY_EXACT_NAME",
        "Q05_CORRECTION_AND_SUPERSESSION_SCAN",
    }, "query-template membership drift")
    q3 = next(row for row in queries if row["query_id"] == "Q03_EXACT_ENTITY_TERRITORY_SCAN")
    require(q3["parameters"]["exact_quote_candidate"] is True, "candidate query is not exact-quoted")
    require(q3["parameters"]["exact_quote_territory"] is True, "territory query is not exact-quoted")
    require("T4 leads only" in q3["output_rule"], "external-search lead boundary weakened")

    smoke = sources["smoke_test_contract"]
    require(smoke["minimum_active_T0_sources"] == 2, "active T0 threshold drift")
    require(smoke["minimum_represented_T1_parties"] == 8, "represented T1 threshold drift")
    require(smoke["minimum_active_T1_parties"] == 5, "active T1 threshold drift")
    require(smoke["minimum_active_T2_independence_clusters"] == 3, "active T2-cluster threshold drift")
    require(smoke["minimum_total_active_sources"] == 10, "total active-source threshold drift")
    require(smoke["zero_claim_records_before_pass"] is True, "pre-smoke zero-claim gate weakened")
    prohibited = " ".join(sources["prohibited_sources"]).lower()
    require("poll" in prohibited and "llm" in prohibited and "search-result snippets" in prohibited, "source prohibitions weakened")

    return {
        "entries": entries,
        "tiers": tiers,
        "queries": queries,
    }


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
    require(len(feature_rows) == 16, "B2 feature dictionary count drift")
    predictive = [row for row in feature_rows if row["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION"]
    require(len(predictive) == 8, "predictive feature count drift")
    require(all(row["coefficient_state"] == "LOCKED_ZERO_UNTIL_HISTORICAL_CALIBRATION_PASS" for row in predictive), "a predictive coefficient is not locked at zero")
    reporting = [row for row in feature_rows if "REPORTING" in row["forecast_role"]]
    require(all("ZERO" in row["coefficient_state"] for row in reporting), "reporting-only feature acquired a coefficient")
    require(features["global_rules"]["predictive_coefficient_default"] == 0.0, "default predictive coefficient != 0")
    require(features["global_rules"]["no_2026_outcome_used"] is True, "feature dictionary permits 2026 outcome")
    require(features["historical_calibration_contract"]["fit_transition"] == "2011_TO_2016", "B2 fit transition drift")
    require(features["historical_calibration_contract"]["validation_transition"] == "2016_TO_2021", "B2 validation transition drift")
    require(features["historical_calibration_contract"]["core_panel_minimum_coverage_each_transition"] == 0.8, "coverage threshold drift")
    require(features["historical_calibration_contract"]["binary_feature_minimum_positive_instances"] == 30, "minimum support drift")

    source_shape = validate_source_universe_shape(sources)
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
    require(b2_gates["B2-8-F0-COUNTERFACTUAL-SIMULATION"]["status"] == "LOCKED", "F0 simulation prematurely unlocked")
    require(all(row["status"] == "LOCKED" for row in gates["agentic_gates"]), "B2 agentic gate unlocked")

    evidence_dir = G100 / "b2_evidence"
    claim_count = 0 if not evidence_dir.exists() else sum(1 for _ in evidence_dir.rglob("*.json"))
    status = sources["status"]
    require(status in {"FROZEN_PENDING_SMOKE_TEST", "FROZEN_COLLECTION_ENABLED_BOUNDED"}, "source registry status invalid")

    if status == "FROZEN_PENDING_SMOKE_TEST":
        require(sources["collection_allowed"] is False, "collection enabled before smoke test")
        require(sources["smoke_test"] is None, "pending source registry already contains smoke result")
        require(claim_count == 0, "claim records exist before source-universe smoke PASS")
        require(b2_gates["B2-1-SOURCE-UNIVERSE-FROZEN"]["status"] == "OPEN", "B2-1 prematurely closed")
        for gate_id in expected_ids - {"B2-0-PROTOCOL-FROZEN", "B2-1-SOURCE-UNIVERSE-FROZEN", "B2-8-F0-COUNTERFACTUAL-SIMULATION"}:
            require(b2_gates[gate_id]["status"] == "OPEN", f"{gate_id} prematurely closed")
        require(gates["next_gate"] == "B2-1-SOURCE-UNIVERSE-FROZEN", "unexpected next B2 gate before smoke")
        require(b2_state["phase"] == "B2_PROTOCOL_FROZEN_SOURCE_UNIVERSE_PENDING", "B2 pending phase drift")
        require(b2_state["collection"]["status"] == "LOCKED", "B2 state says collection is open before smoke")
        require(b2_state["collection"]["evidence_records"] == 0, "B2 state evidence count nonzero before smoke")
        source_state_label = "FROZEN_PENDING_SMOKE_TEST"
    else:
        certificate = load("b2_source_universe_certificate.json")
        probe = load("b2_source_universe_probe.json")
        event20 = load("fil_ariane_events/A020.json")
        require(sources["collection_allowed"] is True, "collection remains disabled after source gate PASS")
        require(isinstance(sources["smoke_test"], dict), "source registry smoke result missing")
        require(certificate["gate"] == "PASS", "source-universe certificate not PASS")
        require(probe["gate"] == "PASS", "source-universe probe not PASS")
        require(certificate["source_universe_sha256"] == probe["source_universe_sha256"], "source-universe hash mismatch between probe and certificate")
        require(certificate["source_universe_sha256"] == sources["smoke_test"]["source_universe_sha256"], "source registry universe hash mismatch")
        require(certificate["active_T0_sources"] >= 2, "active T0 threshold not met")
        require(certificate["represented_T1_parties"] == 8, "T1 party representation threshold not met")
        require(certificate["active_T1_parties"] >= 5, "active T1 threshold not met")
        require(certificate["active_T2_independence_clusters"] >= 3, "active T2 cluster threshold not met")
        require(certificate["total_active_sources"] >= 10, "total active source threshold not met")
        require(certificate["claim_records_before_pass"] == 0, "claims existed before source gate PASS")
        require(len(sources["source_entries"]) == len(probe["sources"]), "probe/source entry coverage mismatch")
        require(all(row.get("operational_state") in {"ACTIVE", "REFERENCE_ONLY", "INACTIVE"} for row in sources["source_entries"]), "source operational state missing")
        require(b2_gates["B2-1-SOURCE-UNIVERSE-FROZEN"]["status"] == "CLOSED", "B2-1 not closed after source PASS")
        for gate_id in expected_ids - {"B2-0-PROTOCOL-FROZEN", "B2-1-SOURCE-UNIVERSE-FROZEN", "B2-8-F0-COUNTERFACTUAL-SIMULATION"}:
            require(b2_gates[gate_id]["status"] == "OPEN", f"{gate_id} prematurely closed after source PASS")
        require(gates["next_gate"] == "B2-2-IDENTITY-TERRITORY-CROSSWALK", "next gate not B2-2 after source PASS")
        require(b2_state["phase"] == "B2_SOURCE_UNIVERSE_FROZEN_COLLECTION_ENABLED", "B2 source-frozen phase drift")
        require(b2_state["collection"]["status"] == "ENABLED_BOUNDED", "B2 collection not bounded-enabled")
        require(b2_state["collection"]["evidence_records"] == 0, "B2 state evidence count must remain zero at source-gate closure")
        require(event20["event_id"] == "A020" and event20["status"] == "PASS", "A020 event missing/invalid")
        source_state_label = "FROZEN_COLLECTION_ENABLED_BOUNDED"

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
    require("Entrée A019 — Correction du validateur de provenance après squash" in journal, "FIL_ARIANE A019 entry missing")
    if status == "FROZEN_COLLECTION_ENABLED_BOUNDED":
        require("Entrée A020 — Gel de l’univers de sources B2" in journal, "FIL_ARIANE A020 entry missing")

    print("B2_PROTOCOL_PASS")
    print(f"protocol={protocol['protocol_id']}")
    print(f"parent_F_minus_1={f1_hash}")
    print(f"features={len(feature_rows)} predictive_locked_zero={len(predictive)}")
    print(f"sources={len(source_shape['entries'])} query_templates={len(source_shape['queries'])}")
    print(f"source_state={source_state_label} claim_records={claim_count}")
    print(f"next={gates['next_gate']}")
    print("F0=LOCKED agentic=ALL_LOCKED")


if __name__ == "__main__":
    main()
