#!/usr/bin/env python3
"""Fail-closed validation of the frozen B2 -> F0 transition."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
F0 = G100 / "forecasts" / "F0"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_F0_VALIDATION_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_F0_VALIDATION_FAIL: {message}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    f1_hash = "de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1"

    protocol = load(G100 / "b2_protocol_v1.json")
    f1_cert = load(G100 / "fminus1_registration_certificate.json")
    registry = load(G100 / "forecast_registry.json")
    freeze = load(G100 / "b2_freeze_certificate.json")
    coeff = load(G100 / "b2_coefficients.json")
    audit = load(G100 / "b2_provenance_audit.json")
    effect = load(G100 / "b2_effect_calibration.json")
    gates = load(G100 / "b2_gate_registry.json")
    state = load(G100 / "b2_current_state.json")
    f0_cert = load(G100 / "f0_registration_certificate.json")
    forecast = load(F0 / "forecast.json")
    simulation = load(F0 / "simulation_certificate.json")
    snapshot = load(F0 / "snapshot_manifest.json")
    registration = load(G100 / "snapshots" / "F0" / "manifest.json")

    require(protocol["protocol_id"] == "M26-GOAL100-B2-PROTOCOL-V1", "protocol ID drift")
    require(protocol["status"] == "FROZEN_PRE_COLLECTION", "B2 protocol is not the frozen V1 protocol")
    require(protocol["parent_snapshot"]["snapshot_id"] == "F-1", "B2 parent snapshot drift")
    require(protocol["parent_snapshot"]["forecast_sha256"] == f1_hash, "B2 parent hash drift")
    require(protocol["feature_and_effect_contract"]["failure_rule"].startswith("If calibration"), "B2 zero-on-failure rule missing")

    require(f1_cert["gate"] == "PASS", "F-1 registration certificate not PASS")
    require(f1_cert["forecast_artifact_sha256"] == f1_hash, "registered F-1 hash drift")

    numeric = list(coeff["predictive_coefficients"].values()) + list(coeff["reporting_only_coefficients"].values())
    require(numeric and all(float(v) == 0.0 for v in numeric), "a frozen numeric B2 coefficient is nonzero")
    require(coeff["all_numeric_coefficients_exactly_zero"] is True, "coefficient zero invariant missing")
    require(all(str(v).startswith("NOT_APPLICABLE") for v in coeff["mechanical_features"].values()), "mechanical evidence was silently admitted")

    require(audit["result"] == "PASS_EMPTY_ADMISSIBLE_SET", "B2 provenance audit is not the empty admissible-set PASS")
    require(audit["counts"]["admissible_claim_records"] == 0, "B2 admissible claim count is nonzero")
    require(audit["counts"]["silent_conflicts_bridged"] == 0, "B2 silently bridged a conflict")
    require(effect["terminal_result"] == "FAIL_CLOSED_ZERO_COEFFICIENTS", "B2 effect calibration did not fail closed")
    require(effect["ridge_fit_executed"] is False, "ridge fit ran despite failed coverage precondition")
    require(effect["forecast_shift_authorized"] is False, "B2 forecast shift was authorized")

    require(freeze["b2_terminal_state"] == "FROZEN_NEGATIVE_RESULT", "B2 terminal freeze state drift")
    require(freeze["parent_snapshot"]["forecast_sha256"] == f1_hash, "B2 freeze parent hash drift")
    require(freeze["frozen_effect_state"]["mechanical_constraints_admitted"] == 0, "B2 freeze admits a mechanical constraint")
    require(freeze["frozen_effect_state"]["all_predictive_coefficients_exactly_zero"] is True, "B2 freeze lost zero coefficient invariant")
    require(freeze["integrity_checks"]["agentic_experiment_executed"] is False, "agentic experiment entered B2")
    require(freeze["frozen_hashes"]["coefficient_artifact_sha256"] == digest(G100 / "b2_coefficients.json"), "B2 coefficient hash mismatch")
    require(freeze["frozen_hashes"]["admissibility_audit_sha256"] == digest(G100 / "b2_provenance_audit.json"), "B2 audit hash mismatch")
    require(freeze["frozen_hashes"]["effect_calibration_sha256"] == digest(G100 / "b2_effect_calibration.json"), "B2 effect hash mismatch")

    ids = [row["snapshot_id"] for row in registry["snapshots"]]
    require(ids == ["F-1", "F0"], f"forecast registry sequence drift: {ids}")
    require(registry["sequence"]["next_id"] == "F1", "next snapshot is not F1")
    require(registry["status"] == "F0_REGISTERED_IMMUTABLE", "registry does not declare immutable F0")
    f0row = registry["snapshots"][1]
    require(f0row["forecast_artifact_hash"] == digest(F0 / "forecast.json"), "registry F0 forecast hash mismatch")
    require(f0row["distribution_sha256"] == f1_hash, "registry F0 distribution is not exact parent distribution")
    require(f0row["distribution_equivalence_to_parent"] == "EXACT", "registry F0 equivalence is not EXACT")
    require(int(f0row["monte_carlo_draws"]) == 50000, "registry F0 draw count drift")

    require(forecast["snapshot_id"] == "F0", "F0 forecast ID drift")
    require(forecast["parent_distribution"]["sha256"] == f1_hash, "F0 forecast parent hash drift")
    require(forecast["b2_application"]["mechanical_constraints_admitted"] == 0, "F0 applies a mechanical constraint")
    require(forecast["b2_application"]["predictive_coefficients_all_exactly_zero"] is True, "F0 predictive vector not zero")
    require(forecast["b2_application"]["agentic_input_used"] is False, "F0 contains agentic input")
    require(forecast["counterfactual_distribution"]["distribution_sha256"] == f1_hash, "F0 distribution hash drift")
    require(forecast["counterfactual_distribution"]["distribution_equivalence"] == "EXACT", "F0 is not an exact identity counterfactual")
    require(all(row["delta"] == "EXACT_ZERO" for row in forecast["ablations"].values()), "F0 has nonzero ablation delta")

    require(simulation["gate"] == "PASS_IDENTITY_REPLAY_PROOF", "F0 simulation certificate not PASS")
    require(simulation["execution_mode"] == "EXACT_IDENTITY_REPLAY_OF_REGISTERED_F_MINUS_1_DRAWS", "F0 execution mode drift")
    require(simulation["fresh_stochastic_resimulation"] is False, "F0 incorrectly claims a fresh stochastic resimulation")
    require(simulation["parent_execution"]["coherent_elections"] == 50000, "F0 parent execution draw count drift")
    require(simulation["parent_execution"]["house_seats_every_draw"] == 395, "F0 seat-total invariant drift")
    require(simulation["counterfactual_execution"]["coherent_elections_evaluated"] == 50000, "F0 identity replay count drift")
    require(all(v is True for v in simulation["checks"].values()), "an F0 simulation check is not true")

    manifest_files = {
        "forecast": F0 / "forecast.json",
        "data_manifest": F0 / "data_manifest.json",
        "parameter_manifest": F0 / "parameter_manifest.json",
        "rng_manifest": F0 / "rng_seed_manifest.json",
        "simulation_certificate": F0 / "simulation_certificate.json",
    }
    for key, path in manifest_files.items():
        require(snapshot["immutable_artifacts"][key]["sha256"] == digest(path), f"F0 snapshot hash mismatch: {key}")
        require(registration["immutable_artifacts"][key]["sha256"] == digest(path), f"F0 registration hash mismatch: {key}")
    require(f0_cert["gate"] == "PASS", "F0 registration certificate not PASS")
    require(f0_cert["canonical_registration_manifest"]["sha256"] == digest(G100 / "snapshots" / "F0" / "manifest.json"), "F0 canonical manifest hash mismatch")
    require(f0_cert["forecast_artifact"]["sha256"] == digest(F0 / "forecast.json"), "F0 certificate forecast hash mismatch")
    require(f0_cert["forecast_artifact"]["distribution_sha256"] == f1_hash, "F0 certificate parent distribution hash drift")
    require(all(v is True for v in f0_cert["checks"].values()), "an F0 registration check is not true")

    by_id = {row["id"]: row for row in gates["gates"]}
    require(set(by_id) == {
        "B2-0-PROTOCOL-FROZEN", "B2-1-SOURCE-UNIVERSE-FROZEN", "B2-2-IDENTITY-TERRITORY-CROSSWALK",
        "B2-3-HISTORICAL-FEATURE-PANEL", "B2-4-2026-BALLOT-ROSTER", "B2-5-PROVENANCE-CONFLICT-AUDIT",
        "B2-6-EFFECT-CALIBRATION", "B2-7-B2-FROZEN", "B2-8-F0-COUNTERFACTUAL-SIMULATION"
    }, "B2 gate membership drift")
    require(by_id["B2-3-HISTORICAL-FEATURE-PANEL"]["status"] == "FAILED", "B2-3 failure was erased")
    require(by_id["B2-4-2026-BALLOT-ROSTER"]["status"] == "FAILED", "B2-4 failure was erased")
    require(by_id["B2-6-EFFECT-CALIBRATION"]["status"] == "FAILED", "B2-6 failure was erased")
    require(by_id["B2-7-B2-FROZEN"]["status"] == "CLOSED", "B2-7 is not closed")
    require(by_id["B2-8-F0-COUNTERFACTUAL-SIMULATION"]["status"] == "CLOSED", "B2-8 is not closed")
    agentic = {row["id"]: row for row in gates["agentic_gates"]}
    require(agentic["E-COLLECT-PREREGISTERED"]["status"] == "OPEN", "E_collect preregistration is not open after F0")
    require(agentic["E-COLLECT-PREREGISTERED"]["execution_status"] == "NOT_STARTED", "E_collect execution started before preregistration")
    require(agentic["E-REASON-PREREGISTERED"]["status"] == "LOCKED", "E_reason unlocked prematurely")
    require(agentic["E-FULL-PREREGISTERED"]["status"] == "LOCKED", "E_full unlocked prematurely")

    require(state["phase"] == "F0_REGISTERED_B2_COMPLETE", "B2 current state not advanced through F0")
    require(state["B2"]["all_predictive_coefficients_exactly_zero"] is True, "B2 current state coefficient drift")
    require(state["F0"]["status"] == "REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST", "B2 current state lacks F0 registration")
    require(state["F0"]["distribution_sha256"] == f1_hash, "B2 current state F0 distribution drift")
    require(state["agentic"]["e_collect_execution"] == "NOT_STARTED", "B2 current state says E_collect executed")
    require(state["agentic"]["agentic_information_in_F0"] is False, "B2 current state says F0 contains agentic information")

    print("B2_F0_VALIDATION_PASS")
    print(f"F0_forecast_sha256={digest(F0 / 'forecast.json')}")
    print(f"F0_distribution_sha256={f1_hash}")
    print("counterfactual_elections=50000")
    print("agentic_execution=NOT_STARTED")


if __name__ == "__main__":
    main()
