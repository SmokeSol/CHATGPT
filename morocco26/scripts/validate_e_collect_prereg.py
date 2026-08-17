#!/usr/bin/env python3
"""Fail-closed preflight validator for E_collect V1 preregistration."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
E = G / "e_collect"

EXPECTED = {
    "e_collect_protocol_v1.json": "39eaa017d0b6b66d39e63a3a6ddf0cc99a1076e5f83ce333c31b8158f85831f7",
    "e_collect_source_policy_v1.json": "68f86826cafc504b5b5d9b8d437a8e5e756f163022a8a1608cd3c265d4bd4e22",
    "e_collect_arabic_normalization_v1.json": "67302ed082498d9e3ff46ba67d096288de6abb529bc218b799d1f8d8ae225c81",
    "e_collect_output_schema_v1.json": "bf0b306d124ded421d19722c12f2fdc9a14f5ceaacd7d431aba5d682a932f4eb",
    "e_collect_scoring_contract_v1.json": "bea7c607576bdaa259521056b24717596a462d064056749e2723a7532617f8f2",
    "e_collect_testset_manifest_v1.json": "7004dd93ce828dadbd0f2a1daa36e18accb8f5ee46e6379a5ab7080a855fef77",
    "atlas_v1_release_contract.json": "1ce5b3c17c4888606fd392998666c1b78d9a3c399cc6b540a6aedcfd38e5a599",
}
PARENT_F0 = "fbe5197999f20d0612bc0c66e1954b5c611b11208e43a72eb5494a03b1e40d3f"
B2_ROSTER = "b702b92929f7271c0309c0e3a8d4336b6e1bd79ee87a222b0cf834bc37c767ac"

def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def die(msg: str):
    raise SystemExit(f"E_COLLECT_PREREG_FAIL: {msg}")

def main():
    cert = json.loads((E / "e_collect_preregistration_certificate.json").read_text(encoding="utf-8"))
    for name, expected in EXPECTED.items():
        actual = sha(E / name)
        if expected.startswith("PLACEHOLDER"):
            expected = cert["frozen_protocol_artifacts"]["testset_manifest"]["sha256"]
        if actual != expected:
            die(f"hash mismatch {name}: {actual} != {expected}")
    if sha(G / "b2_2026_ballot_roster.json") != B2_ROSTER:
        die("reserved 92-row roster changed")
    f0 = json.loads((G / "forecasts" / "F0" / "forecast.json").read_text(encoding="utf-8"))
    if sha(G / "forecasts" / "F0" / "forecast.json") != PARENT_F0:
        die("F0 forecast artifact changed")
    state = json.loads((E / "e_collect_current_state.json").read_text(encoding="utf-8"))
    if state["preregistration"]["status"] != "FROZEN":
        die("preregistration not frozen")
    if state["execution"]["status"] != "NOT_STARTED":
        die("execution already started at preregistration checkpoint")
    if cert["preregistration_checks"]["agentic_execution_started"]:
        die("certificate says execution started")
    print("E_COLLECT_PREREG_PASS")

if __name__ == "__main__":
    main()
