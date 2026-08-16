#!/usr/bin/env python3
"""Evidence-driven, fail-closed Goal100 tracker validation.

Unlike the initial checkpoint validator, this version does not hard-code a
particular count of OPEN/CLOSED gates. It validates each declared state against
its own evidence, allowing legitimate state transitions without weakening the
contracts.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str):
    if not condition:
        raise SystemExit(f"GOAL100_TRACKING_FAIL: {message}")


def evidence_path(rel: str) -> Path:
    p = REPO / rel
    require(p.exists(), f"declared evidence missing: {rel}")
    return p


def validate_closed_p0(gate: dict) -> None:
    gid = gate["id"]
    for rel in gate.get("evidence", []):
        evidence_path(rel)

    if gid == "P0-1":
        c = load(G100 / "geometry_2026_certificate.json")
        require(c["gate"] == "PASS", "P0-1 certificate gate != PASS")
        w = c["working_geometry"]
        require(w == {
            "local_constituencies": 92,
            "local_seats": 305,
            "regional_constituencies": 12,
            "regional_seats": 90,
            "house_seats": 395,
        }, "P0-1 geometry totals drift")
        require(len(c["local_row_crosswalk"]) == 92, "P0-1 local row crosswalk != 92")
        require(not c["unexplained_differences"], "P0-1 has unexplained row differences")
        require(c["legal_watch"]["required_at_every_snapshot"] is True, "P0-1 legal watch disabled")

    elif gid == "P0-2":
        legal = load(G100 / "legal_regression_104.json")
        require(legal["gate"] == "PASS", "P0-2 legal regression gate != PASS")
        require(legal["local"]["n"] == legal["local"]["allocator_equivalent"] == 92, "P0-2 local equivalence lost")
        require(legal["local"]["unresolved_statutory_ties"] == 0, "P0-2 local unresolved ties")
        require(legal["regional"]["n"] == legal["regional"]["allocator_equivalent_to_goal75_math"] == 12, "P0-2 regional equivalence lost")
        require(legal["regional"]["unresolved_statutory_ties"] == 0, "P0-2 regional unresolved ties")
        require(legal["regional"]["observed_independent_matches"] == 10, "P0-2 known regional anomaly count drift")

    elif gid == "P0-3":
        p = load(G100 / "local_N_posterior.json")
        n = load(G100 / "n_scale_invariance_certificate.json")
        require(p["gate"] == "PASS", "P0-3 posterior gate != PASS")
        require(p["national_N"] == 15801162, "P0-3 national N drift")
        require(p["draws"] >= 50000, "P0-3 posterior has fewer than 50,000 draws")
        require(p["constraints"]["all_positive_integer"] is True, "P0-3 non-positive/non-integer draws")
        require(p["constraints"]["all_sums_exact"] is True, "P0-3 draw sums not exact")
        require(len(p["local_92"]) == 92 and len(p["regional_12"]) == 12, "P0-3 posterior coverage != 92+12")
        require(n["gate"] == "PASS" and n["exact_scale_invariance"] is True, "P0-3 scale invariance failed")
        require(n["summary"]["contests"] == 104, "P0-3 sensitivity coverage != 104")
        require(n["summary"]["incomplete_allocations"] == 0, "P0-3 sensitivity has incomplete allocations")

    elif gid == "P0-4":
        h = load(G100 / "historical_panel_diagnostic.json")
        c = h["continuity"]
        require(c["2011_2016_2021"]["common_local_ids_all_three"] == 92, "P0-4 common IDs != 92")
        require(c["2011_2016_2021"]["coverage_of_2021_local_ids"] == 1.0, "P0-4 coverage != 100%")
        for pair in ("2011_2016", "2016_2021", "2011_2021"):
            require(c[pair]["same_normalized_name"] == 92, f"P0-4 names lost for {pair}")
            require(c[pair]["same_seat_magnitude"] == 92, f"P0-4 magnitudes lost for {pair}")

    elif gid == "P0-5":
        b = load(G100 / "bstar_hindcast_v1.json")
        require(b["selected_vote_model"] == "V0_PERSIST", "P0-5 vote B* changed")
        require(b["selected_turnout_model"] == "T0_PERSIST", "P0-5 turnout B* changed")
        require(b["leakage_contract"]["goal75_holdout_used_for_fit"] is False, "P0-5 Goal75 holdout leakage")
        require(b["leakage_contract"]["post_validation_hyperparameter_search"] is False, "P0-5 post-validation search")

    elif gid == "P0-6":
        c = load(G100 / "uncertainty_calibration.json")
        p = load(G100 / "uncertainty_parameters_v1.json")
        require(c["gate"] == "PASS", "P0-6 calibration gate != PASS")
        for key, value in c["gate_checks"].items():
            if key == "2026_outcome_used":
                require(value is False, "P0-6 used 2026 outcome")
            elif key == "post_selection_model_family_search":
                require(value is False, "P0-6 post-selection family search")
            else:
                require(value is True, f"P0-6 gate check failed: {key}")
        require(c["final_parameter_manifest_sha256"] == p["parameter_manifest_sha256"], "P0-6 parameter hash mismatch")
        for name, eig in p["eigenvalues"].items():
            require(min(eig) > 0, f"P0-6 non-positive covariance eigenvalue: {name}")


def validate_forecasts(registry: dict, current: dict) -> None:
    snapshots = registry["snapshots"]
    ids = [s["snapshot_id"] for s in snapshots]
    require(len(ids) == len(set(ids)), "duplicate forecast snapshot IDs")
    required = set(registry["required_snapshot_manifest_fields"])
    for snap in snapshots:
        missing = sorted(required - set(snap))
        require(not missing, f"snapshot {snap.get('snapshot_id')} missing fields {missing}")
        require(int(snap["monte_carlo_draws"]) >= 50000, f"snapshot {snap['snapshot_id']} has <50,000 draws")
        for field in ("data_manifest_hash", "parameter_manifest_hash", "forecast_artifact_hash", "geometry_certificate_hash"):
            require(bool(snap[field]), f"snapshot {snap['snapshot_id']} missing {field}")
    if not snapshots:
        require(registry["status"] == "NO_FORECAST_REGISTERED_YET", "empty registry status drift")
        require(current["goal100_objective"]["forecast_status"] == "NOT_YET_ISSUED", "current state falsely claims forecast")
    else:
        require(registry["status"] != "NO_FORECAST_REGISTERED_YET", "nonempty registry still marked empty")


def main() -> None:
    current = load(G100 / "current_state.json")
    gates = load(G100 / "gate_registry.json")
    forecasts = load(G100 / "forecast_registry.json")

    require(current["program_phase"] == "P6_PROBABILISTIC_FORECAST_ENGINE", "unexpected program phase")
    require(current["goal75_checkpoint"]["scientifically_gated_completion_percent"] == 75, "Goal75 checkpoint drift")
    require(current["goal75_checkpoint"]["status"] == "PRESERVED_IMMUTABLE", "Goal75 not immutable")
    evidence_path(current["goal75_checkpoint"]["reference"])

    p0 = {g["id"]: g for g in gates["p0"]}
    require(set(p0) == {f"P0-{i}" for i in range(1, 7)}, "P0 registry must contain P0-1..P0-6")
    for gate in p0.values():
        require(gate["status"] in gates["status_vocabulary"], f"invalid P0 status {gate['status']}")
        if gate["status"] == "CLOSED":
            validate_closed_p0(gate)

    unlock = {g["id"]: g for g in gates["forecast_unlock"]}
    for gate in unlock.values():
        if gate["status"] == "CLOSED":
            artifact = gate.get("required_artifact")
            require(bool(artifact) and artifact != "created with first registered forecast snapshot", f"closed unlock gate {gate['id']} lacks artifact")
            evidence_path(artifact)

    # P0 to unlock consistency.
    require((p0["P0-1"]["status"] == "CLOSED") == (unlock["GEO-2026-AUTHORITATIVE-DIFF"]["status"] == "CLOSED"), "P0-1/GEO unlock inconsistency")
    require((p0["P0-2"]["status"] == "CLOSED") == (unlock["LEGAL-ALLOCATOR-CERTIFIED"]["status"] == "CLOSED"), "P0-2/legal unlock inconsistency")
    require((p0["P0-3"]["status"] == "CLOSED") == (unlock["N92-POSTERIOR-FIT"]["status"] == "CLOSED"), "P0-3/N92 unlock inconsistency")
    require((p0["P0-5"]["status"] == "CLOSED") == (unlock["BSTAR-SELECTED"]["status"] == "CLOSED"), "P0-5/B* unlock inconsistency")
    require((p0["P0-6"]["status"] == "CLOSED") == (unlock["UNCERTAINTY-CALIBRATION"]["status"] == "CLOSED"), "P0-6/uncertainty unlock inconsistency")

    expected_remaining = [g["id"] for g in gates["forecast_unlock"] if g["status"] != "CLOSED"]
    actual_remaining = current["remaining_hard_gates_before_F_minus_1"]
    require(set(actual_remaining) == set(expected_remaining), f"remaining hard gates drift: expected {expected_remaining}, got {actual_remaining}")

    b = load(G100 / "bstar_hindcast_v1.json")
    require(current["Bstar"]["vote_core"] == b["selected_vote_model"], "current vote B* mismatch")
    require(current["Bstar"]["turnout_core"] == b["selected_turnout_model"], "current turnout B* mismatch")
    require(current["goal100_objective"]["next_forecast"] == forecasts["sequence"]["next_id"], "next forecast ID mismatch")
    validate_forecasts(forecasts, current)

    for gate in gates["agentic_unlock"]:
        require(gate["status"] == "LOCKED", f"agentic gate {gate['id']} unlocked prematurely")
    require(current["goal100_objective"]["agentic_experiment_status"].startswith("LOCKED"), "current state unlocked agentic layer")

    counts = Counter(g["status"] for g in p0.values())
    print("GOAL100_TRACKING_PASS")
    print("phase=P6_PROBABILISTIC_FORECAST_ENGINE")
    print("p0=" + " ".join(f"{k}:{counts.get(k,0)}" for k in ("CLOSED", "PARTIAL", "OPEN", "LOCKED", "FAILED")))
    print(f"registered_forecasts={len(forecasts['snapshots'])} next={forecasts['sequence']['next_id']}")
    print(f"remaining_hard_gates={','.join(actual_remaining)}")
    print("agentic=LOCKED")


if __name__ == "__main__":
    main()
