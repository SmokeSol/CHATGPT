#!/usr/bin/env python3
"""Reconcile F-1 gate/state files from evidence, idempotently.

This is the single recovery path after concurrent evidence-producing workflows.
It never manufactures evidence; it only closes gates whose required artifacts
exist and pass their own contracts.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exists_pass(path: Path) -> bool:
    if not path.exists():
        return False
    try:
        obj = load(path)
    except Exception:
        return False
    return obj.get("gate") == "PASS"


def set_gate(reg: dict, p0_id: str, status: str, evidence: list[str], claim: str) -> None:
    gate = next(x for x in reg["p0"] if x["id"] == p0_id)
    gate["status"] = status
    if status == "CLOSED":
        gate["evidence"] = evidence
        gate["resolved_claim"] = claim
        gate["remaining_gate"] = None


def set_unlock(reg: dict, unlock_id: str, closed: bool, artifact: str | None = None) -> None:
    gate = next(x for x in reg["forecast_unlock"] if x["id"] == unlock_id)
    gate["status"] = "CLOSED" if closed else "OPEN"
    if artifact:
        gate["required_artifact"] = artifact


def main() -> None:
    reg_path = G100 / "gate_registry.json"
    state_path = G100 / "current_state.json"
    reg = load(reg_path)
    state = load(state_path)
    transitions = []

    geo_path = G100 / "geometry_2026_certificate.json"
    geo_ok = exists_pass(geo_path)
    if geo_ok:
        geo = load(geo_path)
        geo_ok = (
            geo["working_geometry"] == {
                "local_constituencies": 92,
                "local_seats": 305,
                "regional_constituencies": 12,
                "regional_seats": 90,
                "house_seats": 395,
            }
            and len(geo["local_row_crosswalk"]) == 92
            and not geo["unexplained_differences"]
            and geo["legal_watch"]["required_at_every_snapshot"] is True
        )
    if geo_ok:
        set_gate(reg, "P0-1", "CLOSED", [
            "morocco26/data/goal100/geometry_official_probe.json",
            "morocco26/data/goal100/geometry_2026_certificate.json",
            "morocco26/data/goal100/historical_panel_diagnostic.json",
        ], "Operational 2026 geometry certified as 92 local/305 plus 12 regional/90 with zero unexplained canonical row differences and mandatory per-snapshot legal watch.")
        set_unlock(reg, "GEO-2026-AUTHORITATIVE-DIFF", True, "morocco26/data/goal100/geometry_2026_certificate.json")
        transitions.append("P0-1:CLOSED")

    n_path = G100 / "local_N_posterior.json"
    inv_path = G100 / "n_scale_invariance_certificate.json"
    n_ok = exists_pass(n_path) and exists_pass(inv_path)
    if n_ok:
        n = load(n_path); inv = load(inv_path)
        n_ok = (
            n["national_N"] == 15801162 and n["draws"] >= 50000
            and n["constraints"]["all_positive_integer"] is True
            and n["constraints"]["all_sums_exact"] is True
            and len(n["local_92"]) == 92 and len(n["regional_12"]) == 12
            and inv["exact_scale_invariance"] is True
            and inv["summary"]["contests"] == 104
            and inv["summary"]["incomplete_allocations"] == 0
        )
    if n_ok:
        set_gate(reg, "P0-3", "CLOSED", [
            "morocco26/data/goal100/local_N_protocol_v1.json",
            "morocco26/data/goal100/local_N_posterior.json",
            "morocco26/data/goal100/n_scale_invariance_certificate.json",
        ], "Preregistered 50,000-draw N92 posterior is positive integer, exactly constrained to national N=15,801,162, with complete 104-contest N-only sensitivity and exact scale invariance.")
        set_unlock(reg, "N92-POSTERIOR-FIT", True, "morocco26/data/goal100/local_N_posterior.json")
        transitions.append("P0-3:CLOSED")

    cal_path = G100 / "uncertainty_calibration.json"
    par_path = G100 / "uncertainty_parameters_v1.json"
    cal_ok = exists_pass(cal_path) and par_path.exists()
    if cal_ok:
        cal = load(cal_path); par = load(par_path)
        cal_ok = (
            cal["final_parameter_manifest_sha256"] == par["parameter_manifest_sha256"]
            and cal["gate_checks"]["both_loto_directions_complete"] is True
            and cal["gate_checks"]["coverage_rule_satisfied"] is True
            and cal["gate_checks"]["anti_trivial_width_satisfied"] is True
            and cal["gate_checks"]["all_covariances_positive_definite"] is True
            and cal["gate_checks"]["2026_outcome_used"] is False
            and cal["gate_checks"]["post_selection_model_family_search"] is False
        )
    if cal_ok:
        set_gate(reg, "P0-6", "CLOSED", [
            "morocco26/data/goal100/uncertainty_protocol_v1.json",
            "morocco26/data/goal100/uncertainty_calibration.json",
            "morocco26/data/goal100/uncertainty_parameters_v1.json",
        ], "Hierarchical national+regional+local vote and turnout innovations are retrospectively calibrated under the frozen LOTO rule, with positive-definite shrunk covariance and no 2026 outcome access.")
        set_unlock(reg, "UNCERTAINTY-CALIBRATION", True, "morocco26/data/goal100/uncertainty_calibration.json")
        transitions.append("P0-6:CLOSED")

    sim_path = G100 / "simulation_certificate.json"
    sim_ok = exists_pass(sim_path)
    if sim_ok:
        sim = load(sim_path)
        sim_ok = (
            int(sim.get("valid_election_draws", 0)) >= 50000
            and sim.get("all_local_seat_sums_305") is True
            and sim.get("all_regional_seat_sums_90") is True
            and sim.get("all_house_seat_sums_395") is True
            and int(sim.get("registered_legal_failures", 1)) == 0
        )
    set_unlock(reg, "MC-50000-COHERENT", sim_ok, "morocco26/data/goal100/simulation_certificate.json")
    if sim_ok:
        transitions.append("MC-50000-COHERENT:CLOSED")

    forecast_registry = load(G100 / "forecast_registry.json")
    snapshot_ok = len(forecast_registry["snapshots"]) > 0
    if snapshot_ok:
        first = forecast_registry["snapshots"][0]
        snapshot_ok = first.get("snapshot_id") == "F-1" and bool(first.get("forecast_artifact_hash"))
    set_unlock(reg, "SNAPSHOT-IMMUTABILITY-MANIFEST", snapshot_ok,
               "morocco26/data/goal100/snapshots/F-1/manifest.json" if snapshot_ok else "created with first registered forecast snapshot")
    if snapshot_ok:
        transitions.append("SNAPSHOT-IMMUTABILITY-MANIFEST:CLOSED")

    reg["as_of"] = "2026-08-16T23:00:00+01:00"
    dump(reg_path, reg)

    p0 = {g["id"]: g for g in reg["p0"]}
    state["p0_summary"]["closed"] = [
        {
            "P0-1": "P0-1_2026_GEOMETRY",
            "P0-2": "P0-2_LEGAL_ALLOCATOR",
            "P0-3": "P0-3_REGISTERED_VOTER_N",
            "P0-4": "P0-4_HISTORICAL_PANEL",
            "P0-5": "P0-5_BSTAR_SELECTION",
            "P0-6": "P0-6_UNCERTAINTY_AND_CORRELATION",
        }[gid]
        for gid in sorted(p0)
        if p0[gid]["status"] == "CLOSED"
    ]
    state["p0_summary"]["active"] = [
        {
            "P0-1": "P0-1_2026_GEOMETRY",
            "P0-2": "P0-2_LEGAL_ALLOCATOR",
            "P0-3": "P0-3_REGISTERED_VOTER_N",
            "P0-4": "P0-4_HISTORICAL_PANEL",
            "P0-5": "P0-5_BSTAR_SELECTION",
            "P0-6": "P0-6_UNCERTAINTY_AND_CORRELATION",
        }[gid]
        for gid in sorted(p0)
        if p0[gid]["status"] in {"OPEN", "FAILED"}
    ]
    state["p0_summary"]["substantially_resolved_with_residual_gate"] = [
        "P0-1_2026_GEOMETRY" for gid in ("P0-1",) if p0[gid]["status"] == "PARTIAL"
    ]
    state["remaining_hard_gates_before_F_minus_1"] = [
        g["id"] for g in reg["forecast_unlock"] if g["status"] != "CLOSED"
    ]
    if geo_ok:
        state["geometry_2026"] = {
            "status": "CERTIFIED_OPERATIONAL_BOUNDED",
            "certificate": "morocco26/data/goal100/geometry_2026_certificate.json",
            "local_constituencies": 92,
            "local_seats": 305,
            "regional_constituencies": 12,
            "regional_seats": 90,
            "legal_watch_required_at_every_snapshot": True,
        }
    if n_ok:
        state["registered_voter_N"].update({
            "local_92_state": "POSTERIOR_FIT_CERTIFIED_NOT_OFFICIAL_COUNTS",
            "posterior_artifact": "morocco26/data/goal100/local_N_posterior.json",
            "scale_invariance_artifact": "morocco26/data/goal100/n_scale_invariance_certificate.json",
        })
    if cal_ok:
        state["uncertainty_model"].update({
            "status": "RETROSPECTIVELY_CALIBRATED_PARAMETERS_CERTIFIED",
            "calibration_artifact": "morocco26/data/goal100/uncertainty_calibration.json",
            "parameter_artifact": "morocco26/data/goal100/uncertainty_parameters_v1.json",
        })
    state["as_of"] = "2026-08-16T23:00:00+01:00"
    dump(state_path, state)

    evidence = {}
    for name in (
        "geometry_2026_certificate.json", "local_N_posterior.json",
        "n_scale_invariance_certificate.json", "uncertainty_calibration.json",
        "uncertainty_parameters_v1.json", "simulation_certificate.json",
        "forecast_registry.json",
    ):
        p = G100 / name
        if p.exists():
            evidence[name] = sha(p)
    reconciliation = {
        "schema_version": "1.0",
        "reconciliation_id": "M26-GOAL100-FMINUS1-STATE-RECONCILIATION",
        "transitions_supported_by_current_evidence": transitions,
        "p0_status": {gid: p0[gid]["status"] for gid in sorted(p0)},
        "remaining_hard_gates": state["remaining_hard_gates_before_F_minus_1"],
        "evidence_sha256": evidence,
        "rule": "Idempotent evidence-driven reconciliation; absence never closes a gate.",
    }
    dump(G100 / "fminus1_state_reconciliation.json", reconciliation)
    print(json.dumps(reconciliation, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
