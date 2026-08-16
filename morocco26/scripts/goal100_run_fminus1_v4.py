#!/usr/bin/env python3
"""Execute and re-hash F-1 under frozen protocol V1.1 / uncertainty V2."""
from __future__ import annotations

import json
from pathlib import Path

import goal100_run_fminus1 as engine
import goal100_fminus1_runtime_v4 as runtime

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
F1 = G100 / "forecasts" / "F-1"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def file_entry(path: Path) -> dict:
    return {
        "path": str(path.relative_to(ROOT.parent)),
        "sha256": engine.sha256_path(path),
    }


def aggregate_legal_diagnostics(forecast: dict) -> dict:
    rows = [*forecast["local_92"], *forecast["regional_12"]]
    diagnostics = [row["legal_diagnostics"] for row in rows]
    return {
        "contest_count": len(rows),
        "contest_draws": len(rows) * int(forecast["draws"]),
        "statutory_age_prior_contest_draws": sum(int(row["statutory_age_prior_draws"]) for row in diagnostics),
        "statutory_age_prior_seats_marginalized": sum(int(row["statutory_age_prior_seats_marginalized"]) for row in diagnostics),
        "statutory_age_prior_max_group_size": max(int(row["statutory_age_prior_max_group_size"]) for row in diagnostics),
        "unique_list_threshold_failures": sum(int(row["unique_list_threshold_failures"]) for row in diagnostics),
        "unfilled_seat_exceptions": sum(int(row["unfilled_seat_exceptions"]) for row in diagnostics),
        "unresolved_after_age_prior": sum(int(row["unresolved_after_age_prior"]) for row in diagnostics),
        "zero_vote_eligible_lists": sum(int(row["zero_vote_eligible_lists"]) for row in diagnostics),
        "scalar_complete_spot_checks": sum(int(row["scalar_complete_spot_checks"]) for row in diagnostics),
        "scalar_binding_tie_spot_checks": sum(int(row["scalar_binding_tie_spot_checks"]) for row in diagnostics),
        "active_bucket_min_share": min(float(row["active_bucket_min_share"]) for row in diagnostics),
        "active_bucket_max_share": max(float(row["active_bucket_max_share"]) for row in diagnostics),
        "active_list_count_min": min(int(row["active_list_count"]) for row in diagnostics),
        "active_list_count_max": max(int(row["active_list_count"]) for row in diagnostics),
        "other_absent_and_dropped_contests": sum(bool(row["other_absent_and_dropped"]) for row in diagnostics),
    }


def postprocess() -> None:
    protocol_path = G100 / "fminus1_protocol_v1_1.json"
    uncertainty_path = G100 / "uncertainty_calibration_v2.json"
    uncertainty_protocol_path = G100 / "uncertainty_protocol_v2.json"
    rejected_protocol_path = G100 / "fminus1_protocol_v1.json"
    rejected_uncertainty_path = G100 / "uncertainty_calibration.json"
    runtime_path = ROOT / "scripts" / "goal100_fminus1_runtime_v4.py"
    wrapper_path = ROOT / "scripts" / "goal100_run_fminus1_v4.py"
    vector_path = ROOT / "scripts" / "goal100_fminus1_vector_allocator_v2.py"
    base_engine_path = ROOT / "scripts" / "goal100_run_fminus1.py"

    protocol = load(protocol_path)
    uncertainty = load(uncertainty_path)
    engine.require(protocol["protocol_id"] == "M26-GOAL100-FMINUS1-PROTOCOL-V1.1", "postprocess protocol drift")
    engine.require(uncertainty["gate"] == "PASS", "postprocess uncertainty V2 gate not PASS")

    forecast_path = F1 / "forecast.json"
    data_manifest_path = F1 / "data_manifest.json"
    parameter_manifest_path = F1 / "parameter_manifest.json"
    rng_manifest_path = F1 / "rng_seed_manifest.json"
    snapshot_manifest_path = F1 / "snapshot_manifest.json"
    simulation_path = G100 / "simulation_certificate.json"
    for path in (
        forecast_path,
        data_manifest_path,
        parameter_manifest_path,
        rng_manifest_path,
        snapshot_manifest_path,
        simulation_path,
    ):
        engine.require(path.exists(), f"postprocess missing generated artifact {path.relative_to(ROOT)}")

    forecast = load(forecast_path)
    data_manifest = load(data_manifest_path)
    parameter_manifest = load(parameter_manifest_path)
    rng_manifest = load(rng_manifest_path)
    snapshot_manifest = load(snapshot_manifest_path)
    simulation = load(simulation_path)
    legal = aggregate_legal_diagnostics(forecast)
    legal["statutory_age_prior_rate_per_contest_draw"] = (
        legal["statutory_age_prior_contest_draws"] / legal["contest_draws"]
    )

    # Correct the hard-coded V1 source paths emitted by the preserved base engine.
    data_manifest["schema_version"] = "1.1"
    data_manifest["protocol_id"] = protocol["protocol_id"]
    data_manifest["inputs"]["protocol"] = file_entry(protocol_path)
    data_manifest["inputs"]["uncertainty"] = file_entry(uncertainty_path)
    data_manifest["methodological_history_preserved"] = {
        "uncertainty_protocol_v2": file_entry(uncertainty_protocol_path),
        "rejected_fminus1_protocol_v1": file_entry(rejected_protocol_path),
        "rejected_uncertainty_v1": file_entry(rejected_uncertainty_path),
    }
    data_manifest["runtime_code"] = {
        "base_engine": file_entry(base_engine_path),
        "runtime_v4": file_entry(runtime_path),
        "wrapper_v4": file_entry(wrapper_path),
        "vector_allocator_v2": file_entry(vector_path),
    }
    write(data_manifest_path, data_manifest)

    parameter_manifest["schema_version"] = "1.1"
    parameter_manifest["protocol_id"] = protocol["protocol_id"]
    parameter_manifest["uncertainty_protocol_id"] = uncertainty["protocol_id"]
    parameter_manifest["uncertainty_artifact"] = file_entry(uncertainty_path)
    parameter_manifest["uncertainty_support_sha256"] = protocol["uncertainty"]["support_sha256"]
    parameter_manifest["robust_simplex_projection"] = protocol["uncertainty"]["robust_projection"]
    parameter_manifest["legal_party_mapping"] = protocol["legal_party_mapping"]
    parameter_manifest["integer_vote_model"] = protocol["integer_vote_model"]
    parameter_manifest["statutory_tie_uncertainty"] = protocol["statutory_tie_uncertainty"]
    parameter_manifest["legal_runtime_diagnostics"] = legal
    parameter_manifest["runtime_code"] = data_manifest["runtime_code"]
    write(parameter_manifest_path, parameter_manifest)

    rng_manifest["schema_version"] = "1.1"
    rng_manifest["protocol_id"] = protocol["protocol_id"]
    engine.require(
        int(rng_manifest["seeds"]["statutory_age_prior"])
        == int(protocol["monte_carlo"]["seed_manifest"]["statutory_age_prior"]),
        "age-prior seed missing from RNG manifest",
    )
    write(rng_manifest_path, rng_manifest)

    forecast["schema_version"] = "1.1"
    forecast["protocol_id"] = protocol["protocol_id"]
    forecast["calibration_status"] = protocol["uncertainty"]["calibration_label"]
    forecast["mandatory_calibration_disclosure"] = protocol["uncertainty"]["mandatory_disclosure"]
    forecast["diagnostics"].update(
        {
            "legal_rerounded_contest_draws": 0,
            "legal_rerounding_rate_per_contest_draw": 0.0,
            "legal_maximum_attempts_used": 0,
            "legal_unresolved_after_retries": 0,
            "statutory_age_prior_contest_draws": legal["statutory_age_prior_contest_draws"],
            "statutory_age_prior_rate_per_contest_draw": legal["statutory_age_prior_rate_per_contest_draw"],
            "statutory_age_prior_seats_marginalized": legal["statutory_age_prior_seats_marginalized"],
            "statutory_age_prior_max_group_size": legal["statutory_age_prior_max_group_size"],
            "legal_unique_list_threshold_failures": legal["unique_list_threshold_failures"],
            "legal_unfilled_seat_exceptions": legal["unfilled_seat_exceptions"],
            "legal_unresolved_after_age_prior": legal["unresolved_after_age_prior"],
            "zero_vote_eligible_lists": legal["zero_vote_eligible_lists"],
            "active_bucket_min_share": legal["active_bucket_min_share"],
            "active_bucket_max_share": legal["active_bucket_max_share"],
            "active_list_count_min": legal["active_list_count_min"],
            "active_list_count_max": legal["active_list_count_max"],
            "scalar_complete_spot_checks": legal["scalar_complete_spot_checks"],
            "scalar_binding_tie_spot_checks": legal["scalar_binding_tie_spot_checks"],
            "other_absent_and_dropped_contest_count": legal["other_absent_and_dropped_contests"],
        }
    )
    forecast["methodological_revision_history"] = {
        "uncertainty_V1_prior_predictive_gate": "REJECTED_BEFORE_FORECAST_OUTPUT",
        "uncertainty_V2": "PASS",
        "preserved_failed_workflows": [31973622928, 31973812526],
        "preserved_diagnostic_workflow": 31973893554,
    }
    forecast["known_limitations"] = [
        "F-1 persists the 2021 structural mean and contains no 2026 candidate, defection, endorsement or event adjustment.",
        "Local registered-voter counts are latent constrained draws, not official 2026 local counts.",
        "Robust Uncertainty V2 was introduced after a prior-predictive legal-feasibility failure and before any forecast artifact; V1 and the failed executions remain preserved.",
        "Vote uncertainty meets aggregate componentwise coverage thresholds; party-level historical coverage remains heterogeneous and is published in uncertainty_calibration_v2.json.",
        "For a binding exact-remainder tie, F-1 marginalizes unknown candidate-age ordering using a frozen exchangeable prior; verified ages may replace it only in a later immutable snapshot.",
        "The invalid-ballot/valid-vote fraction is a shrunk 2011 structural persistence without an additional F-1 shock.",
        "The regional ballot uses a structural bridge from local innovations because only 2021 supplies the current regional-list ballot.",
        "Only lists with positive 2021 votes are eligible in F-1; verified 2026 list changes belong to B2/F0 or later snapshots.",
    ]
    engine.require(legal["unique_list_threshold_failures"] == 0, "unique-list threshold failures survived V1.1")
    engine.require(legal["unfilled_seat_exceptions"] == 0, "unfilled-seat exceptions survived V1.1")
    engine.require(legal["unresolved_after_age_prior"] == 0, "unresolved legal allocations survived V1.1")
    engine.require(legal["zero_vote_eligible_lists"] == 0, "zero-vote eligible lists survived V1.1")
    write(forecast_path, forecast)

    data_hash = engine.sha256_path(data_manifest_path)
    parameter_hash = engine.sha256_path(parameter_manifest_path)
    rng_hash = engine.sha256_path(rng_manifest_path)
    forecast_hash = engine.sha256_path(forecast_path)

    snapshot_manifest["schema_version"] = "1.1"
    snapshot_manifest["protocol_id"] = protocol["protocol_id"]
    snapshot_manifest["data_cutoff"] = protocol["data_cutoff"]
    snapshot_manifest["data_manifest_hash"] = data_hash
    snapshot_manifest["parameter_manifest_hash"] = parameter_hash
    snapshot_manifest["rng_seed_manifest"] = {
        "path": str(rng_manifest_path.relative_to(ROOT.parent)),
        "sha256": rng_hash,
    }
    snapshot_manifest["forecast_artifact_hash"] = forecast_hash
    snapshot_manifest["calibration_status"] = protocol["uncertainty"]["calibration_label"]
    snapshot_manifest["known_limitations"] = forecast["known_limitations"]
    snapshot_manifest["uncertainty_artifact"] = file_entry(uncertainty_path)
    snapshot_manifest["statutory_age_prior"] = {
        "state": "UNKNOWN_AGE_EXCHANGEABLE",
        "contest_draws": legal["statutory_age_prior_contest_draws"],
        "rate": legal["statutory_age_prior_rate_per_contest_draw"],
        "seed": int(protocol["monte_carlo"]["seed_manifest"]["statutory_age_prior"]),
    }
    write(snapshot_manifest_path, snapshot_manifest)
    snapshot_hash = engine.sha256_path(snapshot_manifest_path)

    simulation["schema_version"] = "1.1"
    simulation["certificate_id"] = "M26-GOAL100-FMINUS1-SIMULATION-CERTIFICATE-V1.1"
    simulation["protocol_id"] = protocol["protocol_id"]
    simulation["gate"] = "PASS"
    simulation["legal_rerounded_contest_draws"] = 0
    simulation["legal_rerounding_rate_per_contest_draw"] = 0.0
    simulation["legal_maximum_attempts_used"] = 0
    simulation["legal_unresolved_after_retries"] = 0
    simulation["statutory_age_prior_contest_draws"] = legal["statutory_age_prior_contest_draws"]
    simulation["statutory_age_prior_rate_per_contest_draw"] = legal["statutory_age_prior_rate_per_contest_draw"]
    simulation["statutory_age_prior_seats_marginalized"] = legal["statutory_age_prior_seats_marginalized"]
    simulation["legal_unique_list_threshold_failures"] = 0
    simulation["legal_unfilled_seat_exceptions"] = 0
    simulation["legal_unresolved_after_age_prior"] = 0
    simulation["zero_vote_eligible_lists"] = 0
    simulation["scalar_complete_legal_spot_checks"] = legal["scalar_complete_spot_checks"]
    simulation["scalar_binding_tie_spot_checks"] = legal["scalar_binding_tie_spot_checks"]
    simulation["vectorized_scalar_legal_spot_checks"] = (
        legal["scalar_complete_spot_checks"] + legal["scalar_binding_tie_spot_checks"]
    )
    simulation["forecast_sha256"] = forecast_hash
    simulation["data_manifest_sha256"] = data_hash
    simulation["parameter_manifest_sha256"] = parameter_hash
    simulation["rng_manifest_sha256"] = rng_hash
    simulation["snapshot_manifest_sha256"] = snapshot_hash
    simulation["uncertainty_support_sha256"] = protocol["uncertainty"]["support_sha256"]
    simulation["active_bucket_min_share"] = legal["active_bucket_min_share"]
    simulation["active_bucket_max_share"] = legal["active_bucket_max_share"]
    write(simulation_path, simulation)

    national = forecast["national_395"]["bucket_seat_distribution"]
    print(
        json.dumps(
            {
                "gate": "PASS",
                "snapshot": "F-1",
                "protocol": protocol["protocol_id"],
                "draws": forecast["draws"],
                "seats_every_draw": simulation["national_seats_every_draw"],
                "age_prior_contest_draws": legal["statutory_age_prior_contest_draws"],
                "age_prior_rate": legal["statutory_age_prior_rate_per_contest_draw"],
                "unique_failures": 0,
                "unfilled_failures": 0,
                "unresolved": 0,
                "forecast_hash": forecast_hash,
                "snapshot_hash": snapshot_hash,
                "expected_bucket_seats": {
                    bucket: national[bucket]["mean"] for bucket in engine.BUCKETS
                },
            },
            ensure_ascii=False,
            indent=2,
        )
    )


def main() -> None:
    runtime.install()
    engine.main()
    postprocess()


if __name__ == "__main__":
    main()
