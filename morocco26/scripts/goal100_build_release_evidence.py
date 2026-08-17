#!/usr/bin/env python3
"""Build definitive postflight/release evidence from an already registered F-1."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    required = [
        G100 / "fminus1_registration_certificate.json",
        G100 / "forecast_registry.json", G100 / "gate_registry.json",
        G100 / "current_state.json", G100 / "simulation_certificate.json",
        G100 / "snapshots" / "F-1" / "forecast.json",
        G100 / "snapshots" / "F-1" / "manifest.json",
        G100 / "geometry_2026_certificate.json", G100 / "local_N_posterior.json",
        G100 / "uncertainty_calibration.json", ROOT / "FIL_ARIANE.md",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise SystemExit(f"RELEASE_EVIDENCE_FAIL missing {missing}")

    validations = []
    for cmd in (
        [sys.executable, str(ROOT / "scripts" / "validate_anti_drift.py")],
        [sys.executable, str(ROOT / "scripts" / "validate_goal100_tracking_dynamic.py")],
    ):
        r = subprocess.run(cmd, text=True, capture_output=True)
        validations.append({
            "command": " ".join(cmd), "returncode": r.returncode,
            "stdout": r.stdout[-12000:], "stderr": r.stderr[-12000:],
        })
        if r.returncode:
            raise SystemExit(f"RELEASE_EVIDENCE_FAIL {' '.join(cmd)}\n{r.stdout}\n{r.stderr}")

    registry = load(G100 / "forecast_registry.json")
    gates = load(G100 / "gate_registry.json")
    registration = load(G100 / "fminus1_registration_certificate.json")
    simulation = load(G100 / "simulation_certificate.json")
    manifest = load(G100 / "snapshots" / "F-1" / "manifest.json")
    forecast_path = G100 / "snapshots" / "F-1" / "forecast.json"

    if registration["gate"] != "PASS":
        raise SystemExit("RELEASE_EVIDENCE_FAIL registration gate")
    if [x["snapshot_id"] for x in registry["snapshots"]] != ["F-1"] or registry["sequence"]["next_id"] != "F0":
        raise SystemExit("RELEASE_EVIDENCE_FAIL registry")
    if not all(x["status"] == "CLOSED" for x in gates["forecast_unlock"]):
        raise SystemExit("RELEASE_EVIDENCE_FAIL forecast gates remain open")
    if not all(x["status"] == "LOCKED" for x in gates["agentic_unlock"]):
        raise SystemExit("RELEASE_EVIDENCE_FAIL agentic boundary")
    if simulation["gate"] != "PASS" or simulation["valid_election_draws"] < 50000:
        raise SystemExit("RELEASE_EVIDENCE_FAIL simulation")

    forecast_sha = hashlib.sha256(forecast_path.read_bytes()).hexdigest()
    if not (forecast_sha == registration["forecast_artifact_sha256"] == manifest["forecast_artifact_hash"]):
        raise SystemExit("RELEASE_EVIDENCE_FAIL forecast hash")
    if registration["manifest_sha256"] != manifest["manifest_sha256"]:
        raise SystemExit("RELEASE_EVIDENCE_FAIL manifest hash")

    details = {
        "snapshot_ids": ["F-1"], "next_snapshot": "F0",
        "p0": {x["id"]: x["status"] for x in gates["p0"]},
        "forecast_unlock": {x["id"]: x["status"] for x in gates["forecast_unlock"]},
        "agentic_unlock": {x["id"]: x["status"] for x in gates["agentic_unlock"]},
        "forecast_sha256": forecast_sha,
        "manifest_sha256": manifest["manifest_sha256"],
        "valid_draws": simulation["valid_election_draws"],
        "rejection_rate": simulation["legal_rejection_rate"],
    }
    now = datetime.now(ZoneInfo("Africa/Casablanca")).isoformat(timespec="seconds")
    postflight = {
        "schema_version": "4.0", "report_id": "M26-GOAL100-FMINUS1-POSTFLIGHT-V4",
        "created_at": now, "status": "PASS", "missing_evidence": [],
        "validations": validations, "details": details,
        "rule": "Definitive postflight generated from the exact registered branch head; PASS is never inferred from workflow silence.",
    }
    post_path = G100 / "fminus1_postflight.json"
    dump(post_path, postflight)
    release = {
        "schema_version": "1.0", "release_gate_id": "M26-GOAL100-FMINUS1-RELEASE-V1",
        "created_at": now, "postflight_sha256": hashlib.sha256(post_path.read_bytes()).hexdigest(),
        "forecast_sha256": forecast_sha, "manifest_sha256": manifest["manifest_sha256"],
        "snapshot_ids": ["F-1"], "next_snapshot": "F0",
        "forecast_unlock": "ALL_CLOSED", "agentic_unlock": "ALL_LOCKED",
        "goal75_anti_drift": "PASS", "goal100_tracking": "PASS", "gate": "PASS",
    }
    dump(G100 / "fminus1_release_gate.json", release)

    journal = ROOT / "FIL_ARIANE.md"
    text = journal.read_text(encoding="utf-8")
    if "Entrée A015 — Postflight F−1" not in text:
        text += f'''\n\n### 2026-08-16 — Entrée A015 — Postflight F−1\n\n**Statut :** `PASS`.\n\n**Détails :** `{json.dumps(details, ensure_ascii=False, sort_keys=True)}`.\n\n**Décision :** F−1 est utilisable comme snapshot structurel immuable ; la fusion est autorisée. Rapport : `data/goal100/fminus1_postflight.json`.\n'''
    if "Entrée A018 — Release gate F−1" not in text:
        text += f'''\n\n### 2026-08-16 — Entrée A018 — Release gate F−1\n\n**Résultat :** `PASS`. Goal75 anti-drift et Goal100 tracking passent ; tous les gates forecast sont fermés ; tous les gates agentiques restent verrouillés.\n\n**Hashes :** forecast `{release['forecast_sha256']}` ; manifest `{release['manifest_sha256']}` ; postflight `{release['postflight_sha256']}`.\n\n**Décision :** PR #8 autorisée à fusionner. Prochain objectif : B2 puis F0.\n'''
    journal.write_text(text, encoding="utf-8")

    sys.path.insert(0, str(ROOT / "scripts"))
    import goal100_sync_fil_ariane as sync  # noqa: E402
    sync.main()
    print(json.dumps(release, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
