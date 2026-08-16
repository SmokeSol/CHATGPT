#!/usr/bin/env python3
"""Fail-closed integrity checks for MOROCCO//26 Goal100 tracking.

This validator does not decide political outcomes. It prevents status drift:
- CLOSED gates must have their declared evidence;
- frozen breakthrough claims must match the underlying artifacts;
- current-state/forecast-registry semantics must agree;
- registered forecast snapshots must have complete immutable manifests;
- agentic work cannot be marked unlocked before the non-agentic gates allow it.
"""
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
    # Paths in machine registries are repository-root relative.
    p = ROOT.parent / rel
    require(p.exists(), f"required evidence missing: {rel}")
    return p


def main():
    current = load(G100 / "current_state.json")
    gates = load(G100 / "gate_registry.json")
    forecasts = load(G100 / "forecast_registry.json")
    p0v3 = load(G100 / "p0_resolution_v3.json")
    legal = load(G100 / "legal_regression_104.json")
    history = load(G100 / "historical_panel_diagnostic.json")
    bstar = load(G100 / "bstar_hindcast_v1.json")
    protocol = load(G100 / "forecast_protocol_v1.json")

    require(current["program_phase"] == "P6_PROBABILISTIC_FORECAST_ENGINE", "unexpected Goal100 program phase")
    require(current["goal75_checkpoint"]["scientifically_gated_completion_percent"] == 75, "Goal75 checkpoint must remain 75")
    require(current["goal75_checkpoint"]["status"] == "PRESERVED_IMMUTABLE", "Goal75 checkpoint not marked immutable")
    repo_path(current["goal75_checkpoint"]["reference"])

    expected = {
        "P0-1": "PARTIAL",
        "P0-2": "CLOSED",
        "P0-3": "OPEN",
        "P0-4": "CLOSED",
        "P0-5": "CLOSED",
        "P0-6": "OPEN",
    }
    p0 = {g["id"]: g for g in gates["p0"]}
    require(set(p0) == set(expected), "P0 registry must contain exactly P0-1..P0-6")
    for gid, status in expected.items():
        require(p0[gid]["status"] == status, f"{gid} expected {status}, got {p0[gid]['status']}")
        for evidence in p0[gid].get("evidence", []):
            repo_path(evidence)

    require(p0v3["current_p0_status"]["P0-2_legal_allocator"] == "RESOLVED_AND_104_VECTOR_REGRESSION_CERTIFIED", "P0-2 resolution drift")
    require(p0v3["current_p0_status"]["P0-4_history"] == "RESOLVED_AND_INGESTED_92_OF_92_MODERN_CONTINUITY", "P0-4 resolution drift")
    require(p0v3["current_p0_status"]["P0-5_Bstar"] == "CORE_SELECTED_PERSISTENCE_FIRST_2026_UNTOUCHED", "P0-5 resolution drift")

    # Legal breakthrough must remain exactly what was certified.
    require(legal["gate"] == "PASS", "legal regression gate is not PASS")
    require(legal["local"]["n"] == 92, "legal regression local n != 92")
    require(legal["local"]["allocator_equivalent"] == 92, "legal local allocator equivalence lost")
    require(legal["local"]["unresolved_statutory_ties"] == 0, "legal local unresolved ties present")
    require(legal["regional"]["n"] == 12, "legal regression regional n != 12")
    require(legal["regional"]["allocator_equivalent_to_goal75_math"] == 12, "legal regional allocator equivalence lost")
    require(legal["regional"]["unresolved_statutory_ties"] == 0, "legal regional unresolved ties present")
    require(legal["regional"]["observed_independent_matches"] == 10, "regional provenance-anomaly count drifted")
    require(set(legal["regional"]["expected_known_data_anomalies"]) == {"Casablanca - Settat", "Marrakech - Safi"}, "known regional anomalies changed")

    # Modern historical panel continuity is a hard structural invariant.
    cont = history["continuity"]
    require(cont["2011_2016_2021"]["common_local_ids_all_three"] == 92, "modern common local IDs != 92")
    require(cont["2011_2016_2021"]["coverage_of_2021_local_ids"] == 1.0, "modern territorial coverage != 100%")
    for pair in ("2011_2016", "2016_2021", "2011_2021"):
        require(cont[pair]["same_normalized_name"] == 92, f"{pair} normalized-name continuity lost")
        require(cont[pair]["same_seat_magnitude"] == 92, f"{pair} seat-magnitude continuity lost")

    # B* selection is frozen and cannot silently mutate after validation.
    require(protocol["protocol_id"] == bstar["protocol_id"], "B* result/protocol ID mismatch")
    require(bstar["leakage_contract"]["fit_transition"] == "2011_to_2016_only", "B* fit transition drift")
    require(bstar["leakage_contract"]["validation_transition"] == "2016_to_2021", "B* validation transition drift")
    require(bstar["leakage_contract"]["goal75_holdout_used_for_fit"] is False, "consumed Goal75 holdout leaked into B* fit")
    require(bstar["leakage_contract"]["post_validation_hyperparameter_search"] is False, "post-validation hyperparameter search detected")
    require(bstar["selected_vote_model"] == "V0_PERSIST", "selected vote B* changed")
    require(bstar["selected_turnout_model"] == "T0_PERSIST", "selected turnout B* changed")
    require(current["Bstar"]["vote_core"] == bstar["selected_vote_model"], "current vote B* disagrees with evidence")
    require(current["Bstar"]["turnout_core"] == bstar["selected_turnout_model"], "current turnout B* disagrees with evidence")

    # Forecast registry/current state synchronization.
    require(current["goal100_objective"]["next_forecast"] == forecasts["sequence"]["next_id"], "current state next forecast disagrees with registry")
    snapshots = forecasts["snapshots"]
    ids = [s["snapshot_id"] for s in snapshots]
    require(len(ids) == len(set(ids)), "duplicate forecast snapshot IDs")
    required_fields = set(forecasts["required_snapshot_manifest_fields"])
    for s in snapshots:
        missing = sorted(required_fields - set(s))
        require(not missing, f"snapshot {s.get('snapshot_id')} missing manifest fields: {missing}")
        require(int(s["monte_carlo_draws"]) >= 50000, f"snapshot {s['snapshot_id']} has <50,000 Monte Carlo draws")
        require(bool(s["forecast_artifact_hash"]), f"snapshot {s['snapshot_id']} lacks artifact hash")
        require(bool(s["data_manifest_hash"]), f"snapshot {s['snapshot_id']} lacks data manifest hash")
        require(bool(s["parameter_manifest_hash"]), f"snapshot {s['snapshot_id']} lacks parameter manifest hash")

    if not snapshots:
        require(forecasts["status"] == "NO_FORECAST_REGISTERED_YET", "empty snapshot registry has inconsistent status")
        require(current["goal100_objective"]["forecast_status"] == "NOT_YET_ISSUED", "current state falsely says forecast issued")

    # CLOSED unlock gates must already have their evidence.
    unlock = {g["id"]: g for g in gates["forecast_unlock"]}
    for g in unlock.values():
        if g["status"] == "CLOSED":
            artifact = g.get("required_artifact")
            require(artifact and artifact != "created with first registered forecast snapshot", f"closed gate {g['id']} lacks concrete artifact")
            repo_path(artifact)

    require(unlock["LEGAL-ALLOCATOR-CERTIFIED"]["status"] == "CLOSED", "legal unlock gate should be closed")
    require(unlock["BSTAR-SELECTED"]["status"] == "CLOSED", "B* unlock gate should be closed")
    for gid in ("GEO-2026-AUTHORITATIVE-DIFF", "N92-POSTERIOR-FIT", "UNCERTAINTY-CALIBRATION", "MC-50000-COHERENT", "SNAPSHOT-IMMUTABILITY-MANIFEST"):
        require(unlock[gid]["status"] == "OPEN", f"{gid} must remain open at this checkpoint")

    # Agentic experiment stays locked until B2 is frozen.
    for g in gates["agentic_unlock"]:
        require(g["status"] == "LOCKED", f"agentic gate {g['id']} unlocked prematurely")
    require(current["goal100_objective"]["agentic_experiment_status"].startswith("LOCKED"), "current state unlocked agentic experiment prematurely")

    print("GOAL100_TRACKING_PASS")
    print("phase=P6_PROBABILISTIC_FORECAST_ENGINE")
    print("p0=CLOSED:3 PARTIAL:1 OPEN:2")
    print(f"registered_forecasts={len(snapshots)} next={forecasts['sequence']['next_id']}")
    print("Bstar=V0_PERSIST/T0_PERSIST")
    print("agentic=LOCKED")


if __name__ == "__main__":
    main()
