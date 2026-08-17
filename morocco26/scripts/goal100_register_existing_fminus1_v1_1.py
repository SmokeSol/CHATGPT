#!/usr/bin/env python3
"""Verify and register the already frozen F-1 V1.1 snapshot, fail-closed.

This is a compatibility/registration transition, not a model rerun.  The branch
already contains a complete F-1 artifact tree under ``data/goal100/forecasts/F-1``
and a PASS simulation certificate.  Earlier orchestration expected a second,
incompatible ``snapshots/F-1`` layout and therefore never appended the forecast
to the canonical registry.

The script:
* recomputes every declared SHA-256;
* validates the 50,000-draw, 92+12, 395-seat and legal invariants;
* refuses a conflicting existing F-1 registration;
* creates a small canonical registration envelope pointing to the immutable
  artifact tree (the forecast itself is never copied or rewritten);
* closes only the gates supported by the verified artifacts;
* advances the program to the non-agentic B2 phase while keeping every agentic
  experiment LOCKED.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
SOURCE = G100 / "forecasts" / "F-1"
CANON = G100 / "snapshots" / "F-1"

FORECAST = SOURCE / "forecast.json"
DATA_MANIFEST = SOURCE / "data_manifest.json"
PARAMETER_MANIFEST = SOURCE / "parameter_manifest.json"
RNG_MANIFEST = SOURCE / "rng_seed_manifest.json"
SOURCE_SNAPSHOT_MANIFEST = SOURCE / "snapshot_manifest.json"
SIMULATION = G100 / "simulation_certificate.json"
GEOMETRY = G100 / "geometry_2026_certificate.json"
UNCERTAINTY = G100 / "uncertainty_calibration_v2.json"
LOCAL_N = G100 / "local_N_posterior.json"
LEGAL_ALLOCATOR = ROOT / "src" / "morocco26" / "legal_allocator_2026.py"
FORECAST_REGISTRY = G100 / "forecast_registry.json"
GATE_REGISTRY = G100 / "gate_registry.json"
CURRENT_STATE = G100 / "current_state.json"
REGISTRATION_CERTIFICATE = G100 / "fminus1_registration_certificate.json"
CANON_MANIFEST = CANON / "manifest.json"
P0_RESOLUTION = G100 / "p0_resolution_v6.json"
FIL_ARIANE = ROOT / "FIL_ARIANE.md"
EVENT_DIR = G100 / "fil_ariane_events"
EVENT = EVENT_DIR / "A017.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FMINUS1_REGISTRATION_FAIL: {message}")


def finite(value: Any) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def verify_model_commit(commit: str) -> None:
    require(len(commit) == 40 and all(c in "0123456789abcdef" for c in commit), "invalid model commit SHA")
    try:
        subprocess.run(["git", "cat-file", "-e", f"{commit}^{{commit}}"], cwd=REPO, check=True, capture_output=True)
        subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=REPO, check=True, capture_output=True)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"FMINUS1_REGISTRATION_FAIL: model commit is not an ancestor of HEAD: {exc}")


def verify_probability_vector(values: list[Any], context: str, tolerance: float = 2e-9) -> None:
    require(values, f"empty probability vector: {context}")
    require(all(finite(v) and -tolerance <= float(v) <= 1.0 + tolerance for v in values), f"invalid probability in {context}")
    require(abs(sum(float(v) for v in values) - 1.0) <= tolerance, f"probabilities do not sum to one in {context}")


def verify_contest_rows(rows: list[dict], expected_rows: int, expected_seats: int, label: str) -> dict:
    require(len(rows) == expected_rows, f"{label} row count {len(rows)} != {expected_rows}")
    magnitude_sum = 0
    max_expected_sum_error = 0.0
    max_probability_sum_error = 0.0
    for index, row in enumerate(rows):
        magnitude = int(row["magnitude"])
        require(magnitude > 0, f"non-positive magnitude in {label}[{index}]")
        magnitude_sum += magnitude
        seat_distribution = row["seat_distribution"]
        require(seat_distribution, f"empty seat distribution in {label}[{index}]")
        expected_sum = 0.0
        for party, distribution in seat_distribution.items():
            probabilities = distribution["P_seats_k"]
            verify_probability_vector(probabilities, f"{label}[{index}].{party}.P_seats_k")
            max_probability_sum_error = max(
                max_probability_sum_error,
                abs(sum(float(v) for v in probabilities) - 1.0),
            )
            expected = float(distribution["expected_seats"])
            require(finite(expected) and -1e-9 <= expected <= magnitude + 1e-9, f"invalid expected seats in {label}[{index}].{party}")
            expected_sum += expected
        error = abs(expected_sum - magnitude)
        max_expected_sum_error = max(max_expected_sum_error, error)
        require(error <= 2e-8, f"expected seats do not sum to magnitude in {label}[{index}]: {expected_sum} vs {magnitude}")
    require(magnitude_sum == expected_seats, f"{label} magnitude sum {magnitude_sum} != {expected_seats}")
    return {
        "rows": expected_rows,
        "seat_sum": magnitude_sum,
        "max_expected_seat_sum_error": max_expected_sum_error,
        "max_probability_sum_error": max_probability_sum_error,
    }


def verify_candidate() -> dict:
    required = [
        FORECAST,
        DATA_MANIFEST,
        PARAMETER_MANIFEST,
        RNG_MANIFEST,
        SOURCE_SNAPSHOT_MANIFEST,
        SIMULATION,
        GEOMETRY,
        UNCERTAINTY,
        LOCAL_N,
        LEGAL_ALLOCATOR,
        FORECAST_REGISTRY,
        GATE_REGISTRY,
        CURRENT_STATE,
        FIL_ARIANE,
    ]
    for path in required:
        require(path.exists(), f"missing required artifact: {path.relative_to(REPO)}")

    manifest = load(SOURCE_SNAPSHOT_MANIFEST)
    simulation = load(SIMULATION)
    forecast = load(FORECAST)
    uncertainty = load(UNCERTAINTY)
    local_n = load(LOCAL_N)
    geometry = load(GEOMETRY)

    hashes = {
        "forecast": sha256(FORECAST),
        "data_manifest": sha256(DATA_MANIFEST),
        "parameter_manifest": sha256(PARAMETER_MANIFEST),
        "rng_manifest": sha256(RNG_MANIFEST),
        "source_snapshot_manifest": sha256(SOURCE_SNAPSHOT_MANIFEST),
        "geometry": sha256(GEOMETRY),
        "uncertainty": sha256(UNCERTAINTY),
        "local_N": sha256(LOCAL_N),
        "legal_allocator": sha256(LEGAL_ALLOCATOR),
        "simulation_certificate": sha256(SIMULATION),
    }

    require(manifest["snapshot_id"] == "F-1", "source manifest snapshot ID drift")
    require(manifest["snapshot_class"] == "STRUCTURAL_PROBABILISTIC_FORECAST", "source manifest class drift")
    require(int(manifest["monte_carlo_draws"]) == 50_000, "source manifest draw count != 50,000")
    require(manifest["forecast_artifact_hash"] == hashes["forecast"], "forecast hash mismatch")
    require(manifest["data_manifest_hash"] == hashes["data_manifest"], "data-manifest hash mismatch")
    require(manifest["parameter_manifest_hash"] == hashes["parameter_manifest"], "parameter-manifest hash mismatch")
    require(manifest["rng_seed_manifest"]["sha256"] == hashes["rng_manifest"], "RNG-manifest hash mismatch")
    require(manifest["geometry_certificate_hash"] == hashes["geometry"], "geometry hash mismatch")
    require(manifest["legal_allocator_version"] == hashes["legal_allocator"], "legal allocator hash mismatch")
    require(manifest["uncertainty_artifact"]["sha256"] == hashes["uncertainty"], "uncertainty artifact hash mismatch")
    verify_model_commit(manifest["model_code_commit"])

    require(simulation["gate"] == "PASS", "simulation certificate gate != PASS")
    require(simulation["snapshot_id"] == "F-1", "simulation snapshot ID drift")
    require(int(simulation["draws"]) == 50_000, "simulation draw count != 50,000")
    require(int(simulation["local_contests"]) == 92 and int(simulation["regional_contests"]) == 12, "simulation contest coverage != 92+12")
    require(int(simulation["local_seats"]) == 305 and int(simulation["regional_seats"]) == 90, "simulation seat geometry != 305+90")
    require(int(simulation["national_seats_every_draw"]) == 395, "simulation national seat sum != 395")
    require(simulation["N92_exact_sum_every_draw"] is True, "simulation N92 exact-sum invariant failed")
    require(int(simulation["legal_unique_list_threshold_failures"]) == 0, "unique-list legal failures present")
    require(int(simulation["legal_unfilled_seat_exceptions"]) == 0, "unfilled-seat legal failures present")
    require(int(simulation["legal_unresolved_after_age_prior"]) == 0, "unresolved legal allocations present")
    require(int(simulation["zero_vote_eligible_lists"]) == 0, "zero-vote eligible lists present")
    require(int(simulation["vectorized_scalar_legal_spot_checks"]) >= 1040, "insufficient scalar/vector legal spot checks")
    require(float(simulation["maximum_share_normalization_error"]) <= 1e-12, "probability normalization error too large")
    require(simulation["forecast_sha256"] == hashes["forecast"], "simulation/forecast hash mismatch")
    require(simulation["data_manifest_sha256"] == hashes["data_manifest"], "simulation/data-manifest hash mismatch")
    require(simulation["parameter_manifest_sha256"] == hashes["parameter_manifest"], "simulation/parameter-manifest hash mismatch")
    require(simulation["rng_manifest_sha256"] == hashes["rng_manifest"], "simulation/RNG-manifest hash mismatch")
    require(simulation["snapshot_manifest_sha256"] == hashes["source_snapshot_manifest"], "simulation/source-manifest hash mismatch")
    require(simulation["model_code_commit"] == manifest["model_code_commit"], "simulation/model commit mismatch")
    require(simulation["protocol_id"] == manifest["protocol_id"], "simulation/protocol mismatch")

    require(forecast["snapshot_id"] == "F-1", "forecast snapshot ID drift")
    require(int(forecast["draws"]) == 50_000, "forecast draw count != 50,000")
    local_checks = verify_contest_rows(forecast["local_92"], 92, 305, "local_92")
    regional_checks = verify_contest_rows(forecast["regional_12"], 12, 90, "regional_12")
    national = forecast["national_395"]["bucket_seat_distribution"]
    require(national, "national bucket-seat distribution missing")
    national_mean_sum = sum(float(value["mean"]) for value in national.values())
    require(abs(national_mean_sum - 395.0) <= 2e-8, f"national expected seats sum {national_mean_sum} != 395")
    for party, value in national.items():
        for field in ("mean", "sd", "q025", "q10", "q25", "q50", "q75", "q90", "q975", "mc_standard_error_expected"):
            require(finite(value[field]), f"non-finite national {party}.{field}")

    require(uncertainty["gate"] == "PASS", "uncertainty V2 gate != PASS")
    require(uncertainty["robust_simplex_projection"]["pass"] is True, "robust simplex projection failed")
    selected = uncertainty["robust_simplex_projection"]["selected_candidate_diagnostics"]
    require(float(selected["minimum_share"]) >= 0.0005 - 1e-12, "uncertainty minimum-share floor failed")
    require(float(selected["maximum_share"]) <= float(uncertainty["robust_simplex_projection"]["max_bucket_share_cap"]) + 1e-12, "uncertainty maximum-share cap failed")
    require(float(selected["normalization_error"]) <= 1e-12, "uncertainty normalization failed")

    require(local_n["gate"] == "PASS", "local-N posterior gate != PASS")
    require(local_n["epistemic_status"] == "LATENT_CALIBRATED_PRIOR_NOT_OFFICIAL_LOCAL_COUNTS", "local-N epistemic label drift")
    require(int(local_n["national_N_2026"]) == 15_801_162, "local-N national total drift")
    n_contract = local_n["draw_contract"]
    require(int(n_contract["draws"]) == 50_000, "local-N posterior draw count != 50,000")
    require(n_contract["positive_integer_entries"] is True, "local-N posterior has non-positive/non-integer values")
    require(n_contract["exact_sum_every_draw"] is True and int(n_contract["max_absolute_sum_error"]) == 0, "local-N exact-sum invariant failed")
    require(int(n_contract["feasibility_floor_violations"]) == 0, "local-N feasibility floors violated")
    require(int(local_n["local"]["rows"]) == 92 and int(local_n["regional"]["rows"]) == 12, "local-N coverage != 92+12")

    require(geometry["gate"] == "PASS", "geometry certificate gate != PASS")
    require(int(geometry["house_seats"]) == 395, "geometry house-seat total drift")
    require(geometry["legal_watch"]["status"] == "ACTIVE", "geometry legal watch inactive")

    return {
        "hashes": hashes,
        "manifest": manifest,
        "simulation": simulation,
        "forecast": forecast,
        "uncertainty": uncertainty,
        "local_N": local_n,
        "checks": {
            "local": local_checks,
            "regional": regional_checks,
            "national_expected_seats_sum": national_mean_sum,
            "statutory_age_prior_contest_draws": int(simulation["statutory_age_prior_contest_draws"]),
            "statutory_age_prior_rate": float(simulation["statutory_age_prior_rate_per_contest_draw"]),
            "legal_failures": 0,
        },
    }


def snapshot_registry_entry(verified: dict) -> dict:
    manifest = verified["manifest"]
    return {
        "snapshot_id": manifest["snapshot_id"],
        "snapshot_class": manifest["snapshot_class"],
        "created_at": manifest["created_at"],
        "data_cutoff": manifest["data_cutoff"],
        "protocol_id": manifest["protocol_id"],
        "model_code_commit": manifest["model_code_commit"],
        "data_manifest_hash": manifest["data_manifest_hash"],
        "parameter_manifest_hash": manifest["parameter_manifest_hash"],
        "rng_seed_manifest": manifest["rng_seed_manifest"],
        "monte_carlo_draws": manifest["monte_carlo_draws"],
        "legal_allocator_version": manifest["legal_allocator_version"],
        "geometry_certificate_hash": manifest["geometry_certificate_hash"],
        "registered_N_state": manifest["registered_N_state"],
        "candidate_evidence_state": manifest["candidate_evidence_state"],
        "event_evidence_state": manifest["event_evidence_state"],
        "forecast_artifact_hash": manifest["forecast_artifact_hash"],
        "calibration_status": manifest["calibration_status"],
        "known_limitations": manifest["known_limitations"],
        "artifact_root": "morocco26/data/goal100/forecasts/F-1",
        "canonical_registration_manifest": "morocco26/data/goal100/snapshots/F-1/manifest.json",
        "registration_certificate": "morocco26/data/goal100/fminus1_registration_certificate.json",
    }


def register(verified: dict) -> None:
    timestamp = now_utc()
    manifest = verified["manifest"]
    hashes = verified["hashes"]
    checks = verified["checks"]
    workflow_parent = os.environ.get("GITHUB_SHA") or subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()

    canonical_payload = {
        "schema_version": "1.0",
        "snapshot_id": "F-1",
        "snapshot_class": manifest["snapshot_class"],
        "registration_state": "REGISTERED_IMMUTABLE_STRUCTURAL_PRIOR",
        "registered_at": timestamp,
        "registration_parent_commit": workflow_parent,
        "source_artifact_root": "morocco26/data/goal100/forecasts/F-1",
        "source_snapshot_manifest": {
            "path": "morocco26/data/goal100/forecasts/F-1/snapshot_manifest.json",
            "sha256": hashes["source_snapshot_manifest"],
        },
        "immutable_artifacts": {
            "forecast": {"path": "morocco26/data/goal100/forecasts/F-1/forecast.json", "sha256": hashes["forecast"]},
            "data_manifest": {"path": "morocco26/data/goal100/forecasts/F-1/data_manifest.json", "sha256": hashes["data_manifest"]},
            "parameter_manifest": {"path": "morocco26/data/goal100/forecasts/F-1/parameter_manifest.json", "sha256": hashes["parameter_manifest"]},
            "rng_manifest": {"path": "morocco26/data/goal100/forecasts/F-1/rng_seed_manifest.json", "sha256": hashes["rng_manifest"]},
            "simulation_certificate": {"path": "morocco26/data/goal100/simulation_certificate.json", "sha256": hashes["simulation_certificate"]},
        },
        "model_code_commit": manifest["model_code_commit"],
        "protocol_id": manifest["protocol_id"],
        "monte_carlo_draws": manifest["monte_carlo_draws"],
        "geometry_certificate_hash": manifest["geometry_certificate_hash"],
        "calibration_status": manifest["calibration_status"],
        "candidate_evidence_state": manifest["candidate_evidence_state"],
        "event_evidence_state": manifest["event_evidence_state"],
        "registered_N_state": manifest["registered_N_state"],
        "statutory_age_prior": manifest["statutory_age_prior"],
        "known_limitations": manifest["known_limitations"],
    }
    canonical_payload["canonical_payload_sha256"] = canonical_sha256(canonical_payload)
    dump(CANON_MANIFEST, canonical_payload)

    registry = load(FORECAST_REGISTRY)
    entry = snapshot_registry_entry(verified)
    existing = registry.get("snapshots", [])
    if existing:
        fminus = [item for item in existing if item.get("snapshot_id") == "F-1"]
        require(len(fminus) == 1, "registry already contains a conflicting snapshot sequence")
        require(fminus[0].get("forecast_artifact_hash") == entry["forecast_artifact_hash"], "conflicting F-1 forecast hash already registered")
        require(len(existing) == 1, "unexpected snapshots registered before F0")
        registry["snapshots"] = [entry]
    else:
        registry["snapshots"] = [entry]
    registry["sequence"]["next_id"] = "F0"
    registry["status"] = "F-1_REGISTERED_IMMUTABLE"
    registry["last_registered_at"] = timestamp
    dump(FORECAST_REGISTRY, registry)

    gates = load(GATE_REGISTRY)
    p0 = {gate["id"]: gate for gate in gates["p0"]}
    p0["P0-6"].update({
        "status": "CLOSED",
        "resolved_claim": "Robust V2 national+regional+local vote and turnout uncertainty is retrospectively calibrated without 2026 outcomes; its exact frozen support generated the registered 50,000-draw F-1 snapshot.",
        "evidence": [
            "morocco26/data/goal100/uncertainty_protocol_v2.json",
            "morocco26/data/goal100/uncertainty_calibration_v2.json",
            "morocco26/data/goal100/simulation_certificate.json",
        ],
        "remaining_gate": None,
        "closure_criterion": "PASS calibration, bounded simplex projection, normalized probabilities, and a coherent 50,000-draw prospective snapshot with no unresolved legal allocation.",
    })
    unlock = {gate["id"]: gate for gate in gates["forecast_unlock"]}
    unlock["UNCERTAINTY-CALIBRATION"].update({
        "status": "CLOSED",
        "required_artifact": "morocco26/data/goal100/uncertainty_calibration_v2.json",
    })
    unlock["MC-50000-COHERENT"].update({
        "status": "CLOSED",
        "required_artifact": "morocco26/data/goal100/simulation_certificate.json",
    })
    unlock["SNAPSHOT-IMMUTABILITY-MANIFEST"].update({
        "status": "CLOSED",
        "required_artifact": "morocco26/data/goal100/snapshots/F-1/manifest.json",
    })
    require(all(gate["status"] == "CLOSED" for gate in gates["forecast_unlock"]), "not all forecast gates can be closed")
    require(all(gate["status"] == "LOCKED" for gate in gates["agentic_unlock"]), "agentic gate changed during F-1 registration")
    gates["as_of"] = timestamp
    dump(GATE_REGISTRY, gates)

    state = load(CURRENT_STATE)
    state["schema_version"] = "1.3"
    state["as_of"] = timestamp
    state["program_phase"] = "P7_B2_STRUCTURED_EVIDENCE_LAYER"
    state["goal100_objective"].update({
        "next_forecast": "F0",
        "next_forecast_class": "PRELIMINARY_PROBABILISTIC_FORECAST",
        "forecast_status": "F-1_ISSUED_IMMUTABLE",
        "first_calibrated_snapshot_status": "F-1_REGISTERED",
        "agentic_experiment_status": "LOCKED_UNTIL_B2_IS_FROZEN_AND_AGENTIC_ABLATIONS_ARE_PREREGISTERED",
    })
    state["p0_summary"].update({
        "closed": [
            "P0-1_2026_GEOMETRY",
            "P0-2_LEGAL_ALLOCATOR",
            "P0-3_REGISTERED_VOTER_N",
            "P0-4_HISTORICAL_PANEL",
            "P0-5_BSTAR_SELECTION",
            "P0-6_UNCERTAINTY_AND_CORRELATION",
        ],
        "substantially_resolved_with_residual_gate": [],
        "active": [],
        "authoritative_resolution": "morocco26/data/goal100/p0_resolution_v6.json",
    })
    breakthroughs = state.setdefault("verified_breakthroughs", [])
    if not any(item.get("id") == "BT-FMINUS1-REGISTERED" for item in breakthroughs):
        breakthroughs.append({
            "id": "BT-FMINUS1-REGISTERED",
            "claim": "F-1 is an immutable, non-agentic structural prior based on 50,000 coherent elections over all 395 seats, registered with recomputed artifact hashes.",
            "evidence": "morocco26/data/goal100/fminus1_registration_certificate.json",
        })
    state["uncertainty_model"].update({
        "status": "ROBUST_V2_CALIBRATED_AND_PROSPECTIVELY_FROZEN",
        "calibration_artifact": "morocco26/data/goal100/uncertainty_calibration_v2.json",
        "registered_snapshot": "F-1",
    })
    state["remaining_hard_gates_before_F_minus_1"] = []
    state["next_execution_order"] = [
        "freeze B2 admissibility, evidence schema, cutoff and transformation rules before collection",
        "populate deterministic structured candidate/list/defection/endorsement/event evidence with provenance and territorial mapping",
        "apply B2 to the frozen F-1 prior and issue immutable F0",
        "only then preregister E_collect / E_reason / E_full against the same cutoff and corpus",
    ]
    state["fminus1"] = {
        "status": "REGISTERED_IMMUTABLE",
        "forecast_sha256": hashes["forecast"],
        "source_manifest_sha256": hashes["source_snapshot_manifest"],
        "canonical_manifest": "morocco26/data/goal100/snapshots/F-1/manifest.json",
        "registration_certificate": "morocco26/data/goal100/fminus1_registration_certificate.json",
        "draws": 50_000,
        "house_seats_every_draw": 395,
        "candidate_evidence": "NONE_STRUCTURAL_ONLY",
        "event_evidence": "NONE_STRUCTURAL_ONLY",
    }
    state.setdefault("anti_drift", {})["F_minus_1_may_never_be_overwritten"] = True
    state["anti_drift"]["B2_must_be_frozen_before_F0"] = True
    state["anti_drift"]["agentic_layer_remains_locked"] = True
    dump(CURRENT_STATE, state)

    p0_resolution = {
        "schema_version": "6.0",
        "audit_id": "M26-GOAL100-P0-RESOLUTION-V6",
        "as_of": timestamp,
        "preserves": [f"p0_resolution_v{i}.json" for i in range(1, 6)],
        "current_p0_status": {f"P0-{i}": "CLOSED" for i in range(1, 7)},
        "forecast_unlock": {gate["id"]: gate["status"] for gate in gates["forecast_unlock"]},
        "registered_snapshot": {
            "snapshot_id": "F-1",
            "forecast_sha256": hashes["forecast"],
            "source_manifest_sha256": hashes["source_snapshot_manifest"],
            "canonical_manifest_sha256": sha256(CANON_MANIFEST),
            "draws": 50_000,
            "house_seats_every_draw": 395,
        },
        "agentic_layer_status": "LOCKED",
        "next_phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
    }
    dump(P0_RESOLUTION, p0_resolution)

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-FMINUS1-REGISTRATION-V1",
        "gate": "PASS",
        "snapshot_id": "F-1",
        "registered_at": timestamp,
        "registration_parent_commit": workflow_parent,
        "forecast_artifact_path": "morocco26/data/goal100/forecasts/F-1/forecast.json",
        "forecast_artifact_sha256": hashes["forecast"],
        "source_snapshot_manifest_sha256": hashes["source_snapshot_manifest"],
        "canonical_manifest_path": "morocco26/data/goal100/snapshots/F-1/manifest.json",
        "canonical_manifest_sha256": sha256(CANON_MANIFEST),
        "simulation_certificate_sha256": hashes["simulation_certificate"],
        "data_manifest_sha256": hashes["data_manifest"],
        "parameter_manifest_sha256": hashes["parameter_manifest"],
        "rng_manifest_sha256": hashes["rng_manifest"],
        "geometry_certificate_sha256": hashes["geometry"],
        "uncertainty_artifact_sha256": hashes["uncertainty"],
        "local_N_artifact_sha256": hashes["local_N"],
        "model_code_commit": manifest["model_code_commit"],
        "protocol_id": manifest["protocol_id"],
        "monte_carlo_draws": 50_000,
        "local_contests": 92,
        "regional_contests": 12,
        "house_seats_every_draw": 395,
        "legal_failures": 0,
        "statutory_age_prior_contest_draws": checks["statutory_age_prior_contest_draws"],
        "statutory_age_prior_rate": checks["statutory_age_prior_rate"],
        "forecast_registry_next_id": "F0",
        "all_forecast_unlock_gates_closed": True,
        "all_agentic_gates_locked": True,
        "verification_checks": checks,
        "registration_rule": "Existing immutable artifacts were re-hashed and registered; no model parameter, RNG seed, draw, probability or seat output was changed.",
    }
    dump(REGISTRATION_CERTIFICATE, certificate)

    event = {
        "event_id": "A017",
        "date": timestamp,
        "title": "Enregistrement fail-closed du snapshot F-1 existant",
        "gate": "SNAPSHOT-IMMUTABILITY-MANIFEST",
        "status": "PASS",
        "question": "Le candidat F-1 déjà calculé peut-il être raccordé au registre sans réexécution ni modification ?",
        "pre_test_hypothesis": "Oui uniquement si tous les hashes, les 50 000 tirages, les 104 scrutins, les 395 sièges et les invariants juridiques sont recomputés et concordants.",
        "machine_result": {
            "forecast_sha256": hashes["forecast"],
            "source_manifest_sha256": hashes["source_snapshot_manifest"],
            "draws": 50_000,
            "local_contests": 92,
            "regional_contests": 12,
            "house_seats_every_draw": 395,
            "legal_failures": 0,
            "statutory_age_prior_rate": checks["statutory_age_prior_rate"],
            "registry_next_id": "F0",
        },
        "correction": "Les workflows antérieurs mélangeaient deux schémas et deux répertoires (forecasts/F-1 et snapshots/F-1) et échouaient sur une rustine textuelle obsolète. La correction est une enveloppe de registration, pas un retuning.",
        "scientific_decision": "F-1 est enregistré comme prior structurel non agentique immuable. B2 peut commencer ; E_collect, E_reason et E_full restent verrouillés.",
        "next_action": "Geler le protocole B2 avant toute collecte structurée et avant F0.",
    }
    EVENT_DIR.mkdir(parents=True, exist_ok=True)
    dump(EVENT, event)

    text = FIL_ARIANE.read_text(encoding="utf-8")
    marker = "Entrée A017 — Enregistrement fail-closed du snapshot F−1 existant"
    if marker not in text:
        text += f"""

### {timestamp[:10]} — {marker}

**Question/gate traité :** raccorder le candidat `F-1` déjà calculé au registre canonique, sans réexécution et sans modification d’un output.

**Hypothèse avant test :** l’enregistrement n’est permis que si les hashes du forecast, des manifests, du certificat de simulation, du code juridique, de la géométrie, de l’incertitude et du posterior N concordent exactement.

**Résultat machine :** `PASS` — 50 000 élections, 92 scrutins locaux / 305 sièges, 12 régionaux / 90 sièges, 395 sièges à chaque tirage, zéro échec juridique. Forecast SHA-256 `{hashes['forecast']}` ; manifest source SHA-256 `{hashes['source_snapshot_manifest']}`.

**Écart et correction :** les orchestrateurs précédents mélangeaient deux schémas de fichiers et échouaient sur `N92 correction locus absent`. Aucun seuil scientifique n’a été abaissé et aucun tirage n’a été changé ; une enveloppe canonique pointe vers l’arbre immuable `forecasts/F-1`.

**Décision scientifique :** `F-1` est désormais enregistré comme prior structurel non agentique. Le registre passe à `F0`. Toutes les expériences agentiques restent `LOCKED`.

**Prochaine action exacte :** geler `B2` — schéma, admissibilité, cutoff, provenance, transformations et tests de non-fuite — avant toute collecte de candidats, listes, défections, endorsements ou événements.
"""
        FIL_ARIANE.write_text(text, encoding="utf-8")

    wrapper = ROOT / "scripts" / "validate_goal100_tracking.py"
    wrapper.write_text(
        "#!/usr/bin/env python3\n"
        "\"\"\"Stable registered-state Goal100 validation entry point.\"\"\"\n"
        "from goal100_register_existing_fminus1_v1_1 import verify_registered_state\n\n"
        "if __name__ == '__main__':\n"
        "    verify_registered_state()\n",
        encoding="utf-8",
    )


def verify_registered_state() -> None:
    verified = verify_candidate()
    require(CANON_MANIFEST.exists(), "canonical registration manifest missing")
    require(REGISTRATION_CERTIFICATE.exists(), "registration certificate missing")
    canonical = load(CANON_MANIFEST)
    certificate = load(REGISTRATION_CERTIFICATE)
    registry = load(FORECAST_REGISTRY)
    gates = load(GATE_REGISTRY)
    state = load(CURRENT_STATE)

    require(certificate["gate"] == "PASS", "registration certificate gate != PASS")
    require(certificate["forecast_artifact_sha256"] == verified["hashes"]["forecast"], "registered forecast hash drift")
    require(certificate["source_snapshot_manifest_sha256"] == verified["hashes"]["source_snapshot_manifest"], "registered source-manifest hash drift")
    require(certificate["canonical_manifest_sha256"] == sha256(CANON_MANIFEST), "canonical manifest hash drift")
    require(canonical["immutable_artifacts"]["forecast"]["sha256"] == verified["hashes"]["forecast"], "canonical forecast pointer drift")

    snapshots = registry.get("snapshots", [])
    require(len(snapshots) == 1 and snapshots[0]["snapshot_id"] == "F-1", "forecast registry must contain exactly F-1")
    require(snapshots[0]["forecast_artifact_hash"] == verified["hashes"]["forecast"], "registry forecast hash drift")
    require(registry["sequence"]["next_id"] == "F0", "registry next ID != F0")
    require(registry["status"] == "F-1_REGISTERED_IMMUTABLE", "registry status drift")

    require(all(gate["status"] == "CLOSED" for gate in gates["p0"]), "not all P0 gates are closed")
    require(all(gate["status"] == "CLOSED" for gate in gates["forecast_unlock"]), "not all forecast gates are closed")
    require(all(gate["status"] == "LOCKED" for gate in gates["agentic_unlock"]), "agentic gate unlocked prematurely")
    require(state["program_phase"] == "P7_B2_STRUCTURED_EVIDENCE_LAYER", "program phase is not B2")
    require(state["goal100_objective"]["forecast_status"] == "F-1_ISSUED_IMMUTABLE", "current state does not identify registered F-1")
    require(state["goal100_objective"]["next_forecast"] == "F0", "current state next forecast != F0")
    require(state["remaining_hard_gates_before_F_minus_1"] == [], "F-1 hard gates remain")
    require(state["goal75_checkpoint"]["scientifically_gated_completion_percent"] == 75, "Goal75 checkpoint drift")
    require(state["goal75_checkpoint"]["status"] == "PRESERVED_IMMUTABLE", "Goal75 checkpoint not immutable")
    require(FIL_ARIANE.exists() and "Entrée A017" in FIL_ARIANE.read_text(encoding="utf-8"), "FIL_ARIANE A017 missing")

    print("GOAL100_REGISTERED_STATE_PASS")
    print("snapshot=F-1")
    print(f"forecast_sha256={verified['hashes']['forecast']}")
    print("draws=50000 contests=92+12 seats=395")
    print("forecast_unlock=ALL_CLOSED")
    print("agentic_unlock=ALL_LOCKED")
    print("next=F0 phase=P7_B2_STRUCTURED_EVIDENCE_LAYER")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify-only", action="store_true")
    args = parser.parse_args()
    if args.verify_only:
        verify_registered_state()
    else:
        verified = verify_candidate()
        register(verified)
        verify_registered_state()


if __name__ == "__main__":
    main()
