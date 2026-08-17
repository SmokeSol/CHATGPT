#!/usr/bin/env python3
"""Fail-closed validation of the frozen B2 -> registered F0 transition."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
F0 = G100 / "forecasts" / "F0"
F1 = "de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_F0_VALIDATION_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def req(ok: bool, msg: str):
    if not ok:
        raise SystemExit(f"B2_F0_VALIDATION_FAIL: {msg}")


def exact_checks(actual: dict, true_keys: set[str], false_keys: set[str], label: str):
    req(set(actual) == true_keys | false_keys, f"{label} check membership drift: {sorted(actual)}")
    req(all(actual[k] is True for k in true_keys), f"{label} required-true check failed")
    req(all(actual[k] is False for k in false_keys), f"{label} required-false check failed")


def main():
    protocol = load(G100 / "b2_protocol_v1.json")
    f1cert = load(G100 / "fminus1_registration_certificate.json")
    coeff = load(G100 / "b2_coefficients.json")
    audit = load(G100 / "b2_provenance_audit.json")
    effect = load(G100 / "b2_effect_calibration.json")
    freeze = load(G100 / "b2_freeze_certificate.json")
    registry = load(G100 / "forecast_registry.json")
    gates = load(G100 / "b2_gate_registry.json")
    state = load(G100 / "b2_current_state.json")
    forecast = load(F0 / "forecast.json")
    sim = load(F0 / "simulation_certificate.json")
    snap = load(F0 / "snapshot_manifest.json")
    reg = load(G100 / "snapshots" / "F0" / "manifest.json")
    cert = load(G100 / "f0_registration_certificate.json")

    req(protocol["protocol_id"] == "M26-GOAL100-B2-PROTOCOL-V1", "protocol ID drift")
    req(protocol["status"] == "FROZEN_PRE_COLLECTION", "B2 protocol not frozen")
    req(protocol["parent_snapshot"]["forecast_sha256"] == F1, "B2 parent hash drift")
    req(f1cert["gate"] == "PASS" and f1cert["forecast_artifact_sha256"] == F1, "F-1 registration drift")

    nums = list(coeff["predictive_coefficients"].values()) + list(coeff["reporting_only_coefficients"].values())
    req(nums and all(float(v) == 0.0 for v in nums), "nonzero frozen B2 coefficient")
    req(coeff["all_numeric_coefficients_exactly_zero"] is True, "zero coefficient invariant missing")
    req(all(str(v).startswith("NOT_APPLICABLE") for v in coeff["mechanical_features"].values()), "mechanical evidence admitted")
    req(audit["result"] == "PASS_EMPTY_ADMISSIBLE_SET", "provenance audit result drift")
    req(audit["counts"]["admissible_claim_records"] == 0, "admissible claim set nonempty")
    req(audit["counts"]["silent_conflicts_bridged"] == 0, "silent conflict bridge")
    req(effect["terminal_result"] == "FAIL_CLOSED_ZERO_COEFFICIENTS", "effect failure rule drift")
    req(effect["ridge_fit_executed"] is False and effect["forecast_shift_authorized"] is False, "effect fit/shift improperly enabled")

    req(freeze["b2_terminal_state"] == "FROZEN_NEGATIVE_RESULT", "B2 not frozen negative")
    req(freeze["parent_snapshot"]["forecast_sha256"] == F1, "freeze parent hash drift")
    req(freeze["frozen_effect_state"]["mechanical_constraints_admitted"] == 0, "freeze admits mechanical constraint")
    req(freeze["frozen_effect_state"]["all_predictive_coefficients_exactly_zero"] is True, "freeze lost zero coefficients")
    req(freeze["integrity_checks"]["agentic_experiment_executed"] is False, "agentic experiment entered B2")
    req(freeze["frozen_hashes"]["coefficient_artifact_sha256"] == sha(G100 / "b2_coefficients.json"), "coefficient hash mismatch")
    req(freeze["frozen_hashes"]["admissibility_audit_sha256"] == sha(G100 / "b2_provenance_audit.json"), "audit hash mismatch")
    req(freeze["frozen_hashes"]["effect_calibration_sha256"] == sha(G100 / "b2_effect_calibration.json"), "effect hash mismatch")

    ids = [x["snapshot_id"] for x in registry["snapshots"]]
    req(ids == ["F-1", "F0"], f"registry sequence drift: {ids}")
    req(registry["sequence"]["next_id"] == "F1", "next snapshot != F1")
    req(registry["status"] == "F0_REGISTERED_IMMUTABLE", "registry F0 state drift")
    f0row = registry["snapshots"][1]
    req(f0row["forecast_artifact_hash"] == sha(F0 / "forecast.json"), "registry forecast hash mismatch")
    req(f0row["distribution_sha256"] == F1 and f0row["distribution_equivalence_to_parent"] == "EXACT", "registry distribution not exact F-1")
    req(int(f0row["monte_carlo_draws"]) == 50000, "F0 draw count drift")

    req(forecast["snapshot_id"] == "F0", "forecast ID drift")
    req(forecast["parent_distribution"]["sha256"] == F1, "forecast parent hash drift")
    req(forecast["b2_application"]["mechanical_constraints_admitted"] == 0, "F0 applies mechanical constraint")
    req(forecast["b2_application"]["predictive_coefficients_all_exactly_zero"] is True, "F0 predictive vector nonzero")
    req(forecast["b2_application"]["agentic_input_used"] is False, "F0 contains agentic input")
    req(forecast["counterfactual_distribution"]["distribution_sha256"] == F1, "F0 distribution hash drift")
    req(forecast["counterfactual_distribution"]["distribution_equivalence"] == "EXACT", "F0 is not exact identity counterfactual")
    req(all(x["delta"] == "EXACT_ZERO" for x in forecast["ablations"].values()), "nonzero F0 ablation")

    req(sim["gate"] == "PASS_IDENTITY_REPLAY_PROOF", "simulation gate not PASS")
    req(sim["execution_mode"] == "EXACT_IDENTITY_REPLAY_OF_REGISTERED_F_MINUS_1_DRAWS", "execution mode drift")
    req(sim["fresh_stochastic_resimulation"] is False, "fresh resimulation incorrectly claimed")
    req(sim["parent_execution"]["coherent_elections"] == 50000, "parent election count drift")
    req(sim["parent_execution"]["house_seats_every_draw"] == 395, "395-seat invariant drift")
    req(sim["counterfactual_execution"]["coherent_elections_evaluated"] == 50000, "identity replay count drift")
    simc = sim["checks"]
    req(simc["b2_freeze_certificate_sha256"] == sha(G100 / "b2_freeze_certificate.json"), "simulation freeze hash mismatch")
    exact_checks(
        {k:v for k,v in simc.items() if k != "b2_freeze_certificate_sha256"},
        {"f_minus_1_hash_match","minimum_50000_coherent_elections","house_seats_every_draw_395","mechanical_ablation_reported","predictive_ablation_reported","full_b2_ablation_reported","forecast_distribution_exact_parent_equivalence"},
        {"F_minus_1_rewritten","agentic_input_used","llm_semantic_evidence_used"},
        "simulation",
    )

    files = {
        "forecast": F0 / "forecast.json",
        "data_manifest": F0 / "data_manifest.json",
        "parameter_manifest": F0 / "parameter_manifest.json",
        "rng_manifest": F0 / "rng_seed_manifest.json",
        "simulation_certificate": F0 / "simulation_certificate.json",
    }
    for key, path in files.items():
        req(snap["immutable_artifacts"][key]["sha256"] == sha(path), f"snapshot hash mismatch {key}")
        req(reg["immutable_artifacts"][key]["sha256"] == sha(path), f"registration hash mismatch {key}")
    req(cert["gate"] == "PASS", "registration certificate not PASS")
    req(cert["canonical_registration_manifest"]["sha256"] == sha(G100 / "snapshots" / "F0" / "manifest.json"), "canonical manifest hash mismatch")
    req(cert["forecast_artifact"]["sha256"] == sha(F0 / "forecast.json"), "certificate forecast hash mismatch")
    req(cert["forecast_artifact"]["distribution_sha256"] == F1, "certificate distribution hash drift")
    exact_checks(
        cert["checks"],
        {"snapshot_id_unique","parent_f_minus_1_hash_matches","b2_frozen_before_f0","f0_data_cutoff_equals_b2_cutoff","forecast_artifact_hash_recorded","distribution_exact_parent_equivalence","minimum_50000_counterfactual_elections","house_seats_every_draw_395","mechanical_ablation_reported","predictive_ablation_reported","full_b2_ablation_reported","all_b2_numeric_coefficients_zero","mechanical_constraints_applied_zero"},
        {"f_minus_1_rewritten","agentic_input_used"},
        "registration",
    )

    byid = {x["id"]: x for x in gates["gates"]}
    req(byid["B2-3-HISTORICAL-FEATURE-PANEL"]["status"] == "FAILED", "B2-3 failure erased")
    req(byid["B2-4-2026-BALLOT-ROSTER"]["status"] == "FAILED", "B2-4 failure erased")
    req(byid["B2-6-EFFECT-CALIBRATION"]["status"] == "FAILED", "B2-6 failure erased")
    req(byid["B2-7-B2-FROZEN"]["status"] == "CLOSED", "B2-7 not closed")
    req(byid["B2-8-F0-COUNTERFACTUAL-SIMULATION"]["status"] == "CLOSED", "B2-8 not closed")
    agent = {x["id"]: x for x in gates["agentic_gates"]}
    req(agent["E-COLLECT-PREREGISTERED"]["status"] == "OPEN" and agent["E-COLLECT-PREREGISTERED"]["execution_status"] == "NOT_STARTED", "E_collect boundary drift")
    req(agent["E-REASON-PREREGISTERED"]["status"] == "LOCKED", "E_reason unlocked")
    req(agent["E-FULL-PREREGISTERED"]["status"] == "LOCKED", "E_full unlocked")

    req(state["phase"] == "F0_REGISTERED_B2_COMPLETE", "current phase drift")
    req(state["B2"]["all_predictive_coefficients_exactly_zero"] is True, "current coefficient drift")
    req(state["F0"]["status"] == "REGISTERED_IMMUTABLE_PRELIMINARY_FORECAST", "current F0 state drift")
    req(state["F0"]["distribution_sha256"] == F1, "current F0 distribution drift")
    req(state["agentic"]["e_collect_execution"] == "NOT_STARTED", "E_collect executed")
    req(state["agentic"]["agentic_information_in_F0"] is False, "agentic information entered F0")

    print("B2_F0_VALIDATION_PASS")
    print(f"F0_forecast_sha256={sha(F0 / 'forecast.json')}")
    print(f"F0_distribution_sha256={F1}")
    print("counterfactual_elections=50000")
    print("agentic_execution=NOT_STARTED")


if __name__ == "__main__":
    main()
