#!/usr/bin/env python3
"""Append F-1 to the forecast registry after every prerequisite is certified."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
SNAP = G100 / "snapshots" / "F-1"
REGISTRY = G100 / "forecast_registry.json"
STATE = G100 / "current_state.json"
GATES = G100 / "gate_registry.json"
CERT = G100 / "simulation_certificate.json"
FINALIZATION = SNAP / "manifest_finalization_certificate.json"
MANIFEST = SNAP / "manifest.json"
OUT = G100 / "fminus1_registration_certificate.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    required = [REGISTRY, STATE, GATES, CERT, FINALIZATION, MANIFEST, SNAP / "forecast.json"]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"FMINUS1_REGISTER_FAIL missing {missing}")

    # First reconcile every non-registration gate directly from evidence.
    sys.path.insert(0, str(ROOT / "scripts"))
    import goal100_reconcile_fminus1_state as reconcile  # noqa: E402
    reconcile.main()

    gates = load(GATES)
    unlock = {g["id"]: g for g in gates["forecast_unlock"]}
    prerequisite_ids = [
        "GEO-2026-AUTHORITATIVE-DIFF",
        "LEGAL-ALLOCATOR-CERTIFIED",
        "N92-POSTERIOR-FIT",
        "BSTAR-SELECTED",
        "UNCERTAINTY-CALIBRATION",
        "MC-50000-COHERENT",
    ]
    not_closed = [gid for gid in prerequisite_ids if unlock[gid]["status"] != "CLOSED"]
    if not_closed:
        raise SystemExit(f"FMINUS1_REGISTER_FAIL prerequisite gates not closed: {not_closed}")

    cert = load(CERT)
    finalization = load(FINALIZATION)
    manifest = load(MANIFEST)
    if cert["gate"] != "PASS" or finalization["gate"] != "PASS":
        raise SystemExit("FMINUS1_REGISTER_FAIL simulation/finalization not PASS")
    if finalization["manifest_sha256"] != manifest["manifest_sha256"]:
        raise SystemExit("FMINUS1_REGISTER_FAIL finalization/manifest hash mismatch")
    if manifest["forecast_artifact_hash"] != sha(SNAP / "forecast.json"):
        raise SystemExit("FMINUS1_REGISTER_FAIL forecast artifact changed after finalization")
    if manifest["model_source_sha256"] != sha(ROOT / "scripts" / "goal100_run_fminus1.py"):
        raise SystemExit("FMINUS1_REGISTER_FAIL model source changed after finalization")

    registry = load(REGISTRY)
    snapshots = registry["snapshots"]
    existing = next((s for s in snapshots if s.get("snapshot_id") == "F-1"), None)
    if existing:
        if existing.get("manifest_sha256") != manifest["manifest_sha256"] or existing.get("forecast_artifact_hash") != manifest["forecast_artifact_hash"]:
            raise SystemExit("FMINUS1_REGISTER_FAIL conflicting F-1 already registered")
        idempotent = True
    else:
        if snapshots:
            raise SystemExit("FMINUS1_REGISTER_FAIL F-1 must be the first registered snapshot")
        snapshots.append(manifest)
        idempotent = False

    registry["status"] = "FORECASTS_REGISTERED"
    registry["sequence"]["next_id"] = "F0"
    registry["last_registered_snapshot"] = {
        "snapshot_id": "F-1",
        "registered_at": datetime.now(ZoneInfo("Africa/Casablanca")).isoformat(timespec="seconds"),
        "manifest_sha256": manifest["manifest_sha256"],
        "forecast_artifact_hash": manifest["forecast_artifact_hash"],
    }
    dump(REGISTRY, registry)

    # Reconcile again: registry insertion is the evidence for the immutable-manifest gate.
    reconcile.main()

    state = load(STATE)
    state["goal100_objective"].update({
        "next_forecast": "F0",
        "next_forecast_class": "PRELIMINARY_PROBABILISTIC_FORECAST",
        "forecast_status": "F-1_ISSUED_IMMUTABLE",
        "first_calibrated_snapshot_status": "F-1_REGISTERED",
        "last_registered_forecast": "F-1",
        "last_registered_manifest_sha256": manifest["manifest_sha256"],
        "agentic_experiment_status": "LOCKED_UNTIL_B2_IS_FROZEN_AFTER_FMINUS1"
    })
    state["next_execution_order"] = [
        "build and freeze B2 structured non-agentic candidate/network/event evidence",
        "issue immutable F0 under a versioned protocol",
        "preregister E_collect / E_reason / E_full only after B2 freeze",
        "continue immutable F1..Fn updates until FINAL"
    ]
    state["as_of"] = datetime.now(ZoneInfo("Africa/Casablanca")).isoformat(timespec="seconds")
    dump(STATE, state)

    registration = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-FMINUS1-REGISTRATION-V1",
        "snapshot_id": "F-1",
        "snapshot_class": manifest["snapshot_class"],
        "registered_at": registry["last_registered_snapshot"]["registered_at"],
        "idempotent_existing_registration": idempotent,
        "model_code_commit": manifest["model_code_commit"],
        "model_source_sha256": manifest["model_source_sha256"],
        "forecast_artifact_sha256": manifest["forecast_artifact_hash"],
        "manifest_sha256": manifest["manifest_sha256"],
        "monte_carlo_draws": manifest["monte_carlo_draws"],
        "registry_sha256_after_insertion": sha(REGISTRY),
        "all_prerequisite_gates_closed_before_insertion": True,
        "overwrite_performed": False,
        "next_snapshot_id": "F0",
        "agentic_status": "LOCKED_UNTIL_B2_FREEZE",
        "gate": "PASS",
    }
    dump(OUT, registration)

    # Ensure the snapshot gate remains closed after the final state update.
    reconcile.main()
    print(json.dumps(registration, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
