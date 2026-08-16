#!/usr/bin/env python3
"""Fail-closed integrity checks for MOROCCO//26 Goal100 tracking."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(cond: bool, message: str):
    if not cond:
        raise SystemExit(f"GOAL100_TRACKING_FAIL: {message}")


def repo_path(rel: str) -> Path:
    path = ROOT.parent / rel
    require(path.exists(), f"required evidence missing: {rel}")
    return path


def main():
    current = load(G100 / "current_state.json")
    gates = load(G100 / "gate_registry.json")
    forecasts = load(G100 / "forecast_registry.json")
    p0v5 = load(G100 / "p0_resolution_v5.json")
    geometry = load(G100 / "geometry_2026_certificate.json")
    legal = load(G100 / "legal_regression_104.json")
    local_n = load(G100 / "local_N_posterior.json")
    history = load(G100 / "historical_panel_diagnostic.json")
    bstar = load(G100 / "bstar_hindcast_v1.json")
    protocol = load(G100 / "forecast_protocol_v1.json")

    require((ROOT / "FIL_D_ARIANE.md").exists(), "canonical FIL_D_ARIANE.md missing")
    require(current["program_phase"] == "P6_PROBABILISTIC_FORECAST_ENGINE", "unexpected Goal100 program phase")
    require(current["goal75_checkpoint"]["scientifically_gated_completion_percent"] == 75, "Goal75 checkpoint must remain 75")
    require(current["goal75_checkpoint"]["status"] == "PRESERVED_IMMUTABLE", "Goal75 checkpoint not immutable")
    repo_path(current["goal75_checkpoint"]["reference"])

    expected = {
        "P0-1": "CLOSED",
        "P0-2": "CLOSED",
        "P0-3": "CLOSED",
        "P0-4": "CLOSED",
        "P0-5": "CLOSED",
        "P0-6": "OPEN",
    }
    p0 = {gate["id"]: gate for gate in gates["p0"]}
    require(set(p0) == set(expected), "P0 registry must contain exactly P0-1..P0-6")
    for gate_id, status in expected.items():
        require(p0[gate_id]["status"] == status, f"{gate_id} expected {status}, got {p0[gate_id]['status']}")
        for evidence in p0[gate_id].get("evidence", []):
            repo_path(evidence)

    require(p0v5["current_p0_status"]["P0-1_geometry"] == "RESOLVED_AND_CERTIFIED_WITH_ACTIVE_LEGAL_WATCH", "P0-1 resolution drift")
    require(p0v5["current_p0_status"]["P0-2_legal_allocator"] == "RESOLVED_AND_104_VECTOR_REGRESSION_CERTIFIED", "P0-2 resolution drift")
    require(p0v5["current_p0_status"]["P0-3_registered_N"] == "CONSTRAINED_N92_POSTERIOR_FIT_AND_SENSITIVITY_CERTIFIED", "P0-3 resolution drift")
    require(p0v5["current_p0_status"]["P0-4_history"] == "RESOLVED_AND_INGESTED_92_OF_92_MODERN_CONTINUITY", "P0-4 resolution drift")
    require(p0v5["current_p0_status"]["P0-5_Bstar"] == "CORE_SELECTED_PERSISTENCE_FIRST_2026_UNTOUCHED", "P0-5 resolution drift")

    # Geometry.
    require(geometry["gate"] == "PASS", "geometry gate is not PASS")
    require(geometry["status"] == "RESOLVED_WITH_ACTIVE_LEGAL_WATCH", "geometry status drift")
    require(geometry["local"]["repo_rows"] == geometry["local"]["official_rows"] == geometry["local"]["matched_rows"] == 92, "geometry local coverage != 92")
    require(geometry["local"]["repo_seats"] == geometry["local"]["official_seats"] == 305, "geometry local seats != 305")
    require(not geometry["local"]["differences"], "geometry local differences non-empty")
    require(geometry["regional"]["rows"] == 12 and geometry["regional"]["seats"] == 90, "geometry regional invariant failed")
    require(not geometry["regional"]["differences"], "geometry regional differences non-empty")
    require(geometry["house_seats"] == 395, "geometry House seats != 395")
    require(geometry["legal_watch"]["status"] == "ACTIVE", "geometry legal watch not active")
    require(current["geometry_2026"]["status"] == "CERTIFIED_WITH_ACTIVE_LEGAL_WATCH", "current geometry state drift")

    # Legal allocator.
    require(legal["gate"] == "PASS", "legal regression gate is not PASS")
    require(legal["local"]["n"] == legal["local"]["allocator_equivalent"] == 92, "legal local equivalence lost")
    require(legal["local"]["unresolved_statutory_ties"] == 0, "legal local unresolved ties present")
    require(legal["regional"]["n"] == legal["regional"]["allocator_equivalent_to_goal75_math"] == 12, "legal regional equivalence lost")
    require(legal["regional"]["unresolved_statutory_ties"] == 0, "legal regional unresolved ties present")
    require(legal["regional"]["observed_independent_matches"] == 10, "regional provenance-anomaly count drifted")
    require(set(legal["regional"]["expected_known_data_anomalies"]) == {"Casablanca - Settat", "Marrakech - Safi"}, "known regional anomalies changed")

    # N92 posterior.
    require(local_n["gate"] == "PASS", "N92 posterior gate is not PASS")
    require(local_n["epistemic_status"] == "LATENT_CALIBRATED_PRIOR_NOT_OFFICIAL_LOCAL_COUNTS", "N92 epistemic label drift")
    require(local_n["national_N_2026"] == 15_801_162, "N92 national total drift")
    contract = local_n["draw_contract"]
    require(contract["draws"] == 50_000, "N92 draw count != 50,000")
    require(contract["positive_integer_entries"] is True, "N92 contains non-positive entries")
    require(contract["exact_sum_every_draw"] is True and contract["max_absolute_sum_error"] == 0, "N92 exact-sum invariant failed")
    require(contract["feasibility_floor_violations"] == 0, "N92 feasibility floors violated")
    require(bool(contract["draw_stream_sha256_little_endian_int64"]), "N92 draw hash missing")
    require(local_n["local"]["rows"] == 92, "N92 local sensitivity coverage != 92")
    require(local_n["local"]["denominator_invariant_exact"] == 81, "N92 denominator-invariant count drift")
    require(local_n["local"]["denominator_sensitive"] == 11, "N92 denominator-sensitive count drift")
    require(local_n["regional"]["rows"] == 12, "N92 regional sensitivity coverage != 12")
    require(local_n["local"]["aggregate_unresolved_statutory_probability_sum"] <= 1 / 50_000, "N92 local unresolved tie mass increased")
    require(local_n["regional"]["aggregate_unresolved_statutory_probability_sum"] == 0.0, "N92 regional unresolved tie mass present")
    require(current["registered_voter_N"]["local_92_state"] == "LATENT_POSTERIOR_FIT_AND_CERTIFIED", "current N92 state drift")
    require(current["registered_voter_N"]["epistemic_status"] == "NOT_OFFICIAL_LOCAL_COUNTS", "current N92 falsely labelled official")

    # Modern historical panel continuity.
    continuity = history["continuity"]
    require(continuity["2011_2016_2021"]["common_local_ids_all_three"] == 92, "modern common local IDs != 92")
    require(continuity["2011_2016_2021"]["coverage_of_2021_local_ids"] == 1.0, "modern territorial coverage != 100%")
    for pair in ("2011_2016", "2016_2021", "2011_2021"):
        require(continuity[pair]["same_normalized_name"] == 92, f"{pair} normalized-name continuity lost")
        require(continuity[pair]["same_seat_magnitude"] == 92, f"{pair} seat-magnitude continuity lost")

    # B* selection.
    require(protocol["protocol_id"] == bstar["protocol_id"], "B* result/protocol ID mismatch")
    require(bstar["leakage_contract"]["fit_transition"] == "2011_to_2016_only", "B* fit transition drift")
    require(bstar["leakage_contract"]["validation_transition"] == "2016_to_2021", "B* validation transition drift")
    require(bstar["leakage_contract"]["goal75_holdout_used_for_fit"] is False, "Goal75 holdout leaked into B* fit")
    require(bstar["leakage_contract"]["post_validation_hyperparameter_search"] is False, "post-validation search detected")
    require(bstar["selected_vote_model"] == current["Bstar"]["vote_core"] == "V0_PERSIST", "selected vote B* changed")
    require(bstar["selected_turnout_model"] == current["Bstar"]["turnout_core"] == "T0_PERSIST", "selected turnout B* changed")

    # Forecast registry/current state synchronization.
    require(current["goal100_objective"]["next_forecast"] == forecasts["sequence"]["next_id"], "next forecast disagrees with registry")
    snapshots = forecasts["snapshots"]
    snapshot_ids = [snapshot["snapshot_id"] for snapshot in snapshots]
    require(len(snapshot_ids) == len(set(snapshot_ids)), "duplicate forecast snapshot IDs")
    required_fields = set(forecasts["required_snapshot_manifest_fields"])
    for snapshot in snapshots:
        missing = sorted(required_fields - set(snapshot))
        require(not missing, f"snapshot {snapshot.get('snapshot_id')} missing fields: {missing}")
        require(int(snapshot["monte_carlo_draws"]) >= 50_000, f"snapshot {snapshot['snapshot_id']} has <50,000 draws")
        for field in ("forecast_artifact_hash", "data_manifest_hash", "parameter_manifest_hash"):
            require(bool(snapshot[field]), f"snapshot {snapshot['snapshot_id']} lacks {field}")
    if not snapshots:
        require(forecasts["status"] == "NO_FORECAST_REGISTERED_YET", "empty forecast registry status inconsistent")
        require(current["goal100_objective"]["forecast_status"] == "NOT_YET_ISSUED", "current state falsely says forecast issued")

    unlock = {gate["id"]: gate for gate in gates["forecast_unlock"]}
    for gate in unlock.values():
        if gate["status"] == "CLOSED":
            artifact = gate.get("required_artifact")
            require(artifact and artifact != "created with first registered forecast snapshot", f"closed gate {gate['id']} lacks concrete artifact")
            repo_path(artifact)
    for gate_id in ("GEO-2026-AUTHORITATIVE-DIFF", "LEGAL-ALLOCATOR-CERTIFIED", "N92-POSTERIOR-FIT", "BSTAR-SELECTED"):
        require(unlock[gate_id]["status"] == "CLOSED", f"{gate_id} should be closed")
    for gate_id in ("UNCERTAINTY-CALIBRATION", "MC-50000-COHERENT", "SNAPSHOT-IMMUTABILITY-MANIFEST"):
        require(unlock[gate_id]["status"] == "OPEN", f"{gate_id} must remain open")
    require(current["remaining_hard_gates_before_F_minus_1"] == [
        "UNCERTAINTY-CALIBRATION",
        "MC-50000-COHERENT",
        "SNAPSHOT-IMMUTABILITY-MANIFEST",
    ], "current remaining F-1 gates drifted")

    for gate in gates["agentic_unlock"]:
        require(gate["status"] == "LOCKED", f"agentic gate {gate['id']} unlocked prematurely")
    require(current["goal100_objective"]["agentic_experiment_status"].startswith("LOCKED"), "agentic experiment unlocked prematurely")

    print("GOAL100_TRACKING_PASS")
    print("phase=P6_PROBABILISTIC_FORECAST_ENGINE")
    print("p0=CLOSED:5 OPEN:1")
    print(f"registered_forecasts={len(snapshots)} next={forecasts['sequence']['next_id']}")
    print("geometry=92/92 local + 12/12 regional; legal-watch=ACTIVE")
    print("N92=50000 exact-sum latent draws; official-label=FALSE")
    print("Bstar=V0_PERSIST/T0_PERSIST")
    print("agentic=LOCKED")


if __name__ == "__main__":
    main()
