#!/usr/bin/env python3
"""Certify that B2 is operationally open, while keeping B2-FROZEN/F0 locked."""
from __future__ import annotations

import csv
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
B2 = G100 / "b2" / "v1"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit("B2_OPEN_ACCEPTANCE_FAIL: " + message)


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    subprocess.run(["python", str(ROOT / "scripts" / "goal100_validate_b2_v1.py")], check=True)
    required = [
        B2 / "b2_preflight.json",
        B2 / "b2_protocol_v1.json",
        B2 / "b2_source_policy_v1.json",
        B2 / "b2_evidence_schema_v1.json",
        B2 / "b2_feature_dictionary_v1.json",
        B2 / "b2_feature_build_protocol_v1.json",
        B2 / "b2_residual_backtest_protocol_v1.json",
        B2 / "b2_collection_plan_v1.json",
        B2 / "b2_coverage_protocol_v1.json",
        B2 / "collection_queue_certificate.json",
        B2 / "b2_reconciliation_status.json",
        B2 / "b2_residual_backtest.json",
        B2 / "source_registry.json",
        B2 / "collection_queue.csv",
        B2 / "source_discovery_queue.csv",
        B2 / "coverage_matrix.csv",
        B2 / "evidence_ledger.ndjson",
        ROOT / "scripts" / "goal100_build_b2_features_v1.py",
        ROOT / "scripts" / "goal100_backtest_b2_residual_v1.py",
        ROOT / "scripts" / "goal100_b2_source_watch.py",
    ]
    require(all(path.exists() for path in required), "required B2 artifact missing")

    preflight = load(B2 / "b2_preflight.json")
    protocol = load(B2 / "b2_protocol_v1.json")
    queue_cert = load(B2 / "collection_queue_certificate.json")
    reconciliation = load(B2 / "b2_reconciliation_status.json")
    residual = load(B2 / "b2_residual_backtest.json")
    queue = csv_rows(B2 / "collection_queue.csv")
    source_queue = csv_rows(B2 / "source_discovery_queue.csv")
    coverage = csv_rows(B2 / "coverage_matrix.csv")
    evidence_count = sum(bool(line.strip()) for line in (B2 / "evidence_ledger.ndjson").read_text(encoding="utf-8").splitlines())
    watches = sorted((B2 / "source_watch").glob("*.json"))

    require(reconciliation["gate"] == "PASS", "reconciliation not PASS")
    require(queue_cert["gate"] == "PASS", "queue certificate not PASS")
    require(queue_cert["contests"] == {"local": 92, "regional": 12, "total": 104, "seats": 395}, "contest universe drift")
    require(len(queue) == 104 * 8, f"collection queue {len(queue)} != 832")
    require(all(row["status"] == "OPEN_UNKNOWN" for row in queue), "queue contains inferred completion")
    require(len(coverage) == len(queue), "coverage denominator differs from task denominator")
    require(all(row["coverage_status"] == "UNKNOWN" for row in coverage), "initial unknown coverage was overwritten")
    require(evidence_count == 0, "phase-open certificate expects zero unreviewed evidence rows")
    require(residual["gate"] == "BLOCKED_MISSING_HISTORICAL_FEATURE_PANEL", "residual gate not honestly blocked")
    require(residual["2026_data_used_for_fit"] is False and residual["F0_unlocked"] is False, "residual leaked 2026/F0")
    require(all(float(value) == 0 for value in residual["coefficients"].values()), "non-legal coefficient is nonzero")
    require(protocol["agentic_boundary"]["status"] == "LOCKED", "agentic boundary unlocked")
    require(not (B2 / "b2_freeze_certificate.json").exists(), "B2 unexpectedly frozen during opening")
    require(watches, "no source-watch acquisition snapshot")
    latest_watch = load(watches[-1])
    require(latest_watch["evidence_rows_created"] == 0 and latest_watch["interpretation_performed"] is False,
            "source watch created/interpreted evidence")

    gates_path = G100 / "gate_registry.json"
    gates = load(gates_path)
    b2_gate = next((row for row in gates.get("agentic_unlock", []) if row.get("id") == "B2-FROZEN"), None)
    require(b2_gate is not None, "B2-FROZEN gate absent")
    require(b2_gate["status"] in {"OPEN", "LOCKED"}, "B2-FROZEN closed prematurely")
    for row in gates.get("agentic_unlock", []):
        if row.get("id") != "B2-FROZEN":
            require(row.get("status") == "LOCKED", f"agentic gate {row.get('id')} unlocked")

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-PHASE-OPEN-V1",
        "created_at": NOW,
        "gate": "PASS_B2_OPEN_NOT_FROZEN",
        "F_minus_1_preflight_ready": preflight["ready_for_b2_non_agentic_scaffold"],
        "B2_status": "OPEN_COLLECTION_NOT_FROZEN" if preflight["ready_for_b2_non_agentic_scaffold"] else "SCAFFOLD_READY_BUT_F_MINUS_1_BLOCKED",
        "protocol_id": protocol["protocol_id"],
        "contest_universe": {"local": 92, "regional": 12, "total": 104, "seats": 395},
        "collection_tasks": len(queue),
        "source_discovery_tasks": len(source_queue),
        "coverage_state": "ALL_UNKNOWN_INITIAL",
        "evidence_rows": evidence_count,
        "source_watch_snapshots": len(watches),
        "latest_source_watch": {
            "path": str(watches[-1].relative_to(ROOT.parent)),
            "sha256": sha(watches[-1]),
            "sources": len(latest_watch["sources"]),
            "interpretation_performed": False,
            "evidence_rows_created": 0,
        },
        "deterministic_feature_compiler": "READY_NO_COEFFICIENTS_APPLIED",
        "historical_residual_backtest": residual["gate"],
        "non_legal_coefficients": "ALL_ZERO",
        "B2_frozen": False,
        "F0_created": False,
        "agentic_status": "ALL_LOCKED",
        "artifacts": [
            {"path": str(path.relative_to(ROOT.parent)), "sha256": sha(path)} for path in required
        ],
        "next_action": "Resolve exact Tier-A election/party endpoints and ingest the first atomic LIST_FILED/CANDIDATE rows; backfill the historical B2 feature panel in parallel."
    }
    out = B2 / "b2_phase_open_certificate.json"
    require(not out.exists(), "phase-open certificate already exists; do not overwrite")
    dump(out, certificate)

    state_path = G100 / "current_state.json"
    state = load(state_path)
    state.setdefault("B2", {}).update({
        "status": certificate["B2_status"],
        "phase_open_certificate": str(out.relative_to(ROOT.parent)),
        "evidence_rows": 0,
        "collection_tasks": len(queue),
        "historical_residual_backtest": residual["gate"],
        "non_legal_coefficients": "ALL_ZERO",
        "forecast_generated": False,
        "agentic": False,
        "next_gate": "B2_SCHEMA_VALID_AND_FIRST_TIER_A_EVIDENCE"
    })
    state["as_of"] = NOW
    dump(state_path, state)

    journal_candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    journal = next((path for path in journal_candidates if path.exists()), journal_candidates[0])
    marker = "B2-A005 — Certificat d’ouverture B2, non gelée"
    text = journal.read_text(encoding="utf-8")
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Certificat : `PASS_B2_OPEN_NOT_FROZEN`.\n- Univers : `92 + 12 = 104` scrutins, `395` sièges, `832` tâches atomiques de couverture.\n- Évidence B2 active : `0` ligne à l’ouverture ; toutes les cases restent `UNKNOWN`.\n- Compilateur de features : prêt, sans coefficient appliqué.\n- Backtest résiduel : `BLOCKED_MISSING_HISTORICAL_FEATURE_PANEL`; tous les poids non juridiques restent zéro.\n- `B2-FROZEN` : non franchi. `F0` : non créé. Agentique : intégralement verrouillée.\n- Prochaine action exacte : premières lignes Tier A sur l’univers officiel des listes/candidats, et backfill historique en parallèle.\n'''
        journal.write_text(text, encoding="utf-8")

    print(json.dumps(certificate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
