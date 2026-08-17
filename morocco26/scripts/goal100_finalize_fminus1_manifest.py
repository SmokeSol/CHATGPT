#!/usr/bin/env python3
"""Finalize the unregistered F-1 manifest against the exact evidence commit.

The forecast is still mutable before registry insertion. This step recomputes all
artifact hashes after simulation, binds the executable source by both commit and
SHA-256, and updates the simulation certificate consistently. Once registered,
any change requires a new snapshot ID.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
SNAP = G100 / "snapshots" / "F-1"
PROTOCOL = G100 / "fminus1_protocol_v1.json"
MODEL = ROOT / "scripts" / "goal100_run_fminus1.py"
LEGAL = ROOT / "src" / "morocco26" / "legal_allocator_2026.py"
GEOMETRY = G100 / "geometry_2026_certificate.json"
ROOT_CERT = G100 / "simulation_certificate.json"
SNAP_CERT = SNAP / "simulation_certificate.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha(obj) -> str:
    text = json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def main() -> None:
    required = [
        PROTOCOL, MODEL, LEGAL, GEOMETRY, ROOT_CERT,
        SNAP / "forecast.json", SNAP / "data_manifest.json",
        SNAP / "parameter_manifest.json", SNAP / "seed_manifest.json",
        SNAP / "manifest.json", SNAP_CERT,
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"FMINUS1_MANIFEST_FAIL missing {missing}")

    protocol = load(PROTOCOL)
    cert = load(ROOT_CERT)
    snap_cert = load(SNAP_CERT)
    if cert["gate"] != "PASS" or snap_cert["gate"] != "PASS":
        raise SystemExit("FMINUS1_MANIFEST_FAIL simulation certificate is not PASS")
    if cert["valid_election_draws"] < 50000:
        raise SystemExit("FMINUS1_MANIFEST_FAIL fewer than 50,000 valid draws")

    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
        dirty = subprocess.check_output(["git", "status", "--porcelain"], cwd=REPO, text=True).splitlines()
    except Exception as exc:
        raise SystemExit(f"FMINUS1_MANIFEST_FAIL cannot identify git state: {exc!r}")

    # Forecast/data files are expected to be tracked at this stage. Dirty state is
    # allowed only for files this finalizer is about to replace.
    allowed_dirty = {
        "morocco26/data/goal100/snapshots/F-1/manifest.json",
        "morocco26/data/goal100/snapshots/F-1/simulation_certificate.json",
        "morocco26/data/goal100/simulation_certificate.json",
    }
    unexpected = []
    for line in dirty:
        path = line[3:].strip()
        if path and path not in allowed_dirty:
            unexpected.append(line)
    if unexpected:
        raise SystemExit(f"FMINUS1_MANIFEST_FAIL unexpected dirty files before finalization: {unexpected}")

    manifest = load(SNAP / "manifest.json")
    manifest.pop("manifest_sha256", None)
    manifest.update({
        "snapshot_id": "F-1",
        "snapshot_class": protocol["snapshot_class"],
        "created_at": datetime.now(ZoneInfo("Africa/Casablanca")).isoformat(timespec="seconds"),
        "data_cutoff": protocol["data_cutoff"],
        "protocol_id": protocol["protocol_id"],
        "model_code_commit": commit,
        "model_source_path": "morocco26/scripts/goal100_run_fminus1.py",
        "model_source_sha256": sha(MODEL),
        "data_manifest_hash": sha(SNAP / "data_manifest.json"),
        "parameter_manifest_hash": sha(SNAP / "parameter_manifest.json"),
        "rng_seed_manifest": sha(SNAP / "seed_manifest.json"),
        "monte_carlo_draws": int(cert["valid_election_draws"]),
        "legal_allocator_version": sha(LEGAL),
        "geometry_certificate_hash": sha(GEOMETRY),
        "forecast_artifact_hash": sha(SNAP / "forecast.json"),
        "finalized_before_registration": True,
        "evidence_commit_contains_model_and_simulation_artifacts": True,
    })
    manifest["manifest_sha256"] = canonical_sha(manifest)
    dump(SNAP / "manifest.json", manifest)

    for certificate in (cert, snap_cert):
        certificate["snapshot_manifest_sha256"] = manifest["manifest_sha256"]
        certificate["forecast_artifact_sha256"] = manifest["forecast_artifact_hash"]
        certificate["model_code_commit"] = commit
        certificate["model_source_sha256"] = manifest["model_source_sha256"]
        certificate["manifest_finalized_before_registration"] = True
    dump(ROOT_CERT, cert)
    dump(SNAP_CERT, snap_cert)

    finalization = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-FMINUS1-MANIFEST-FINALIZATION-V1",
        "snapshot_id": "F-1",
        "evidence_commit": commit,
        "model_source_sha256": manifest["model_source_sha256"],
        "forecast_artifact_sha256": manifest["forecast_artifact_hash"],
        "manifest_sha256": manifest["manifest_sha256"],
        "registered_at_finalization": False,
        "rule": "The manifest is finalized only after model code and simulation artifacts exist in the evidence commit; registry insertion is a separate append-only transition.",
        "gate": "PASS",
    }
    dump(SNAP / "manifest_finalization_certificate.json", finalization)
    print(json.dumps(finalization, indent=2))


if __name__ == "__main__":
    main()
