#!/usr/bin/env python3
"""Finalize F0 hash metadata in dependency order without changing forecast semantics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
F0 = G100 / "forecasts" / "F0"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    coeff_path = G100 / "b2_coefficients.json"
    audit_path = G100 / "b2_provenance_audit.json"
    effect_path = G100 / "b2_effect_calibration.json"
    freeze_path = G100 / "b2_freeze_certificate.json"

    coeff_hash = sha(coeff_path)
    audit_hash = sha(audit_path)

    effect = load(effect_path)
    effect["coefficient_artifact"]["sha256"] = coeff_hash
    write(effect_path, effect)
    effect_hash = sha(effect_path)

    freeze = load(freeze_path)
    freeze["frozen_hashes"]["coefficient_artifact_sha256"] = coeff_hash
    freeze["frozen_hashes"]["admissibility_audit_sha256"] = audit_hash
    freeze["frozen_hashes"]["effect_calibration_sha256"] = effect_hash
    write(freeze_path, freeze)
    freeze_hash = sha(freeze_path)

    forecast_path = F0 / "forecast.json"
    forecast = load(forecast_path)
    forecast["b2_application"]["freeze_certificate"]["sha256"] = freeze_hash
    write(forecast_path, forecast)
    forecast_hash = sha(forecast_path)

    data_path = F0 / "data_manifest.json"
    data = load(data_path)
    data["b2_frozen_inputs"]["freeze_certificate"]["sha256"] = freeze_hash
    data["b2_frozen_inputs"]["coefficients"]["sha256"] = coeff_hash
    data["b2_frozen_inputs"]["provenance_audit"]["sha256"] = audit_hash
    data["b2_frozen_inputs"]["effect_calibration"]["sha256"] = effect_hash
    write(data_path, data)
    data_hash = sha(data_path)

    params_path = F0 / "parameter_manifest.json"
    params = load(params_path)
    params["counterfactual_transform"]["predictive_coefficients"]["sha256"] = coeff_hash
    write(params_path, params)
    params_hash = sha(params_path)

    rng_path = F0 / "rng_seed_manifest.json"
    rng_hash = sha(rng_path)

    sim_path = F0 / "simulation_certificate.json"
    sim = load(sim_path)
    sim["checks"]["b2_freeze_certificate_sha256"] = freeze_hash
    write(sim_path, sim)
    sim_hash = sha(sim_path)

    snap_path = F0 / "snapshot_manifest.json"
    snap = load(snap_path)
    snap["data_manifest_hash"] = data_hash
    snap["parameter_manifest_hash"] = params_hash
    snap["rng_seed_manifest"]["sha256"] = rng_hash
    snap["forecast_artifact_hash"] = forecast_hash
    snap["b2_freeze"]["sha256"] = freeze_hash
    snap["immutable_artifacts"]["forecast"]["sha256"] = forecast_hash
    snap["immutable_artifacts"]["data_manifest"]["sha256"] = data_hash
    snap["immutable_artifacts"]["parameter_manifest"]["sha256"] = params_hash
    snap["immutable_artifacts"]["rng_manifest"]["sha256"] = rng_hash
    snap["immutable_artifacts"]["simulation_certificate"]["sha256"] = sim_hash
    write(snap_path, snap)
    snap_hash = sha(snap_path)

    registration_path = G100 / "snapshots" / "F0" / "manifest.json"
    registration = load(registration_path)
    registration["source_snapshot_manifest"]["sha256"] = snap_hash
    registration["immutable_artifacts"]["forecast"]["sha256"] = forecast_hash
    registration["immutable_artifacts"]["data_manifest"]["sha256"] = data_hash
    registration["immutable_artifacts"]["parameter_manifest"]["sha256"] = params_hash
    registration["immutable_artifacts"]["rng_manifest"]["sha256"] = rng_hash
    registration["immutable_artifacts"]["simulation_certificate"]["sha256"] = sim_hash
    registration["b2_freeze_certificate"]["sha256"] = freeze_hash
    write(registration_path, registration)
    registration_hash = sha(registration_path)

    cert_path = G100 / "f0_registration_certificate.json"
    cert = load(cert_path)
    cert["canonical_registration_manifest"]["sha256"] = registration_hash
    cert["source_snapshot_manifest"]["sha256"] = snap_hash
    cert["forecast_artifact"]["sha256"] = forecast_hash
    cert["b2_freeze_certificate_sha256"] = freeze_hash
    write(cert_path, cert)
    cert_hash = sha(cert_path)

    registry_path = G100 / "forecast_registry.json"
    registry = load(registry_path)
    f0_rows = [row for row in registry["snapshots"] if row.get("snapshot_id") == "F0"]
    if len(f0_rows) != 1:
        raise SystemExit(f"F0_HASH_FINALIZE_FAIL: expected one F0 registry row, got {len(f0_rows)}")
    row = f0_rows[0]
    row["data_manifest_hash"] = data_hash
    row["parameter_manifest_hash"] = params_hash
    row["rng_seed_manifest"]["sha256"] = rng_hash
    row["forecast_artifact_hash"] = forecast_hash
    row["registration_certificate_sha256"] = cert_hash
    row["b2_freeze_certificate_sha256"] = freeze_hash
    write(registry_path, registry)

    state_path = G100 / "b2_current_state.json"
    state = load(state_path)
    state["B2"]["freeze_certificate_sha256"] = freeze_hash
    state["F0"]["forecast_artifact_sha256"] = forecast_hash
    state["F0"]["registration_manifest_sha256"] = registration_hash
    state["F0"]["registration_certificate_sha256"] = cert_hash
    write(state_path, state)

    print("F0_HASH_FINALIZE_PASS")
    print(f"b2_coefficients={coeff_hash}")
    print(f"b2_provenance_audit={audit_hash}")
    print(f"b2_effect_calibration={effect_hash}")
    print(f"b2_freeze_certificate={freeze_hash}")
    print(f"f0_forecast={forecast_hash}")
    print(f"f0_data_manifest={data_hash}")
    print(f"f0_parameter_manifest={params_hash}")
    print(f"f0_rng_manifest={rng_hash}")
    print(f"f0_simulation_certificate={sim_hash}")
    print(f"f0_snapshot_manifest={snap_hash}")
    print(f"f0_registration_manifest={registration_hash}")
    print(f"f0_registration_certificate={cert_hash}")


if __name__ == "__main__":
    main()
