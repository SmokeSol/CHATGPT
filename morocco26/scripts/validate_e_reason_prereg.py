#!/usr/bin/env python3
"""Fail-closed preregistration and immutable-ancestry validator for E_reason V1."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26" / "data" / "goal100" / "e_reason"
BASE = "1f6403f80d1516de7c407d1a3ddebbbbd0f9c9b5"

IMMUTABLE_PREFIXES = (
    "morocco26/data/goal100/snapshots/F-1/",
    "morocco26/data/goal100/forecasts/F0/",
    "morocco26/data/goal100/f0_registration_certificate.json",
    "morocco26/data/goal100/b2",
    "morocco26/data/goal100/e_collect/",
    "morocco26/web/",
    "morocco26/vercel.json",
)

REQUIRED = [
    "e_reason_protocol_v1.json",
    "e_reason_information_set_v1.json",
    "e_reason_source_policy_v1.json",
    "e_reason_historical_cutoffs_v1.json",
    "e_reason_conditions_v1.json",
    "e_reason_output_schema_v1.json",
    "e_reason_scoring_contract_v1.json",
    "e_reason_leakage_control_v1.json",
    "e_reason_promotion_criteria_v1.json",
    "e_reason_source_seed_manifest_v1.json",
    "e_reason_current_state.json",
    "e_reason_preregistration_certificate.json",
]


def fail(message: str) -> None:
    raise SystemExit(f"E_REASON_PREREG_FAIL: {message}")


def git_blob_sha(path: Path) -> str:
    data = path.read_bytes()
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()


for name in REQUIRED:
    path = ER / name
    if not path.exists():
        fail(f"missing {path.relative_to(ROOT)}")
    try:
        json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(f"invalid JSON {name}: {exc}")

cert = json.loads((ER / "e_reason_preregistration_certificate.json").read_text())
if cert.get("gate") != "PASS":
    fail("certificate gate is not PASS")
if cert.get("exact_parent_commit_sha") != BASE:
    fail("wrong exact parent commit")

for entry in cert.get("artifact_manifest", []):
    path = ROOT / entry["path"]
    if not path.exists():
        fail(f"manifest path missing: {entry['path']}")
    if git_blob_sha(path) != entry["git_blob_sha"]:
        fail(f"git blob mismatch: {entry['path']}")

state = json.loads((ER / "e_reason_current_state.json").read_text())
if state.get("predictive_judgments_generated") is not False:
    fail("predictive judgments exist at preregistration")
if state.get("forecast_delta_generated") is not False:
    fail("forecast delta exists at preregistration")
if state.get("F1_created") is not False:
    fail("F1 already exists at preregistration")
if state.get("Atlas_UI_modified") is not False:
    fail("Atlas UI flag changed")

try:
    changed = subprocess.check_output(
        ["git", "diff", "--name-only", f"{BASE}...HEAD"],
        cwd=ROOT,
        text=True,
    ).splitlines()
except Exception as exc:
    fail(f"cannot compute immutable diff: {exc}")

for path in changed:
    if any(path == prefix or path.startswith(prefix) for prefix in IMMUTABLE_PREFIXES):
        fail(f"immutable path changed: {path}")

for forbidden in (
    ER / "outputs",
    ER / "forecasts",
    ROOT / "morocco26" / "data" / "goal100" / "forecasts" / "F1",
):
    if forbidden.exists():
        fail(f"pre-judgment forbidden path exists: {forbidden.relative_to(ROOT)}")

print("E_REASON_PREREG_PASS")
