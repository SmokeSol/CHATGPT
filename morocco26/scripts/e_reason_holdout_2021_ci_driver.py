#!/usr/bin/env python3
"""Technical CI driver for the frozen E_reason 2021 holdout.

This driver orchestrates only the already-frozen holdout builder, deterministic C1
judgments, public freeze receipts, and the hermetic Opus5 handoff. It never opens,
searches for, scores, or derives the 2021 target outcome.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
SCRIPTS = ROOT / "scripts"
HOLDOUT = E / "blind" / "holdout"
C1 = E / "judgments" / "holdout" / "c1_rule_only"


def die(msg: str) -> None:
    raise SystemExit(msg)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_core_sha(bundle_path: Path) -> tuple[str, dict]:
    b = read_json(bundle_path)
    declared = b.pop("bundle_sha256")
    raw = json.dumps(b, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    got = hashlib.sha256(raw).hexdigest()
    if got != declared:
        die(f"bundle canonical-core SHA mismatch: {got} != {declared}")
    return got, b


def validate_preconditions() -> None:
    f = read_json(E / "lambda_freeze_v1.json")
    if f.get("status") != "FROZEN_BEFORE_2021_JUDGMENTS":
        die("lambda freeze status invalid")
    if f.get("holdout_2021_outcome_seen_before_freeze") is not False:
        die("2021 outcome was marked seen before lambda freeze")
    if f.get("lambda_C1") != 0.3 or f.get("lambda_C2") != 0.3:
        die("frozen lambdas are not 0.30 / 0.30")
    # Deliberately check only the experiment's forbidden in-band outcome path.
    if (HOLDOUT / "outcome.json").exists():
        die("forbidden holdout outcome exists inside blinded holdout directory")


def validate_bundle() -> tuple[str, str]:
    m = read_json(HOLDOUT / "bundle_manifest.json")
    s = read_json(HOLDOUT / "mapping_seal.json")
    bundle_sha, core = canonical_core_sha(HOLDOUT / "blind_bundle.json")
    prompt_sha = sha_file(E / "c2_prompt_v1.md")
    if m.get("status") != "FROZEN_BLIND_HOLDOUT_BUNDLE":
        die("holdout manifest status invalid")
    if m.get("packets") != 92 or m.get("party_cells") != 828:
        die("holdout panel is not 92 x 9")
    if m.get("target_outcome_read") is not False:
        die("holdout builder reports target outcome read")
    if (m.get("leakage_scan") or {}).get("status") != "PASS":
        die("holdout leakage scan failed")
    if m.get("anonymization_independent_from_development") is not True:
        die("holdout anonymization is not independent from development")
    if s.get("status") != "SEALED_BEFORE_ANY_HOLDOUT_PREDICTIVE_JUDGMENT":
        die("holdout mapping seal status invalid")
    if s.get("mapping_material_committed") is not False or s.get("mapping_material_judge_access") is not False:
        die("mapping material exposure guard failed")
    if bundle_sha != m.get("bundle_sha256") or bundle_sha != s.get("blind_bundle_sha256"):
        die("bundle SHA disagreement across manifest/seal")
    if prompt_sha != m.get("c2_prompt_sha256") or prompt_sha != s.get("c2_prompt_sha256"):
        die("prompt SHA disagreement across manifest/seal")
    packets = core.get("packets") or []
    if len(packets) != 92 or sum(len(p.get("parties") or []) for p in packets) != 828:
        die("bundle content is not 92 packets / 828 cells")
    return bundle_sha, prompt_sha


def cmd_build(secret_path: Path) -> None:
    validate_preconditions()
    if (HOLDOUT / "bundle_manifest.json").exists():
        validate_bundle()
        print("HOLDOUT_BUNDLE_ALREADY_FROZEN")
        return
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, str(SCRIPTS / "e_reason_build_blind_holdout_bundle.py"), "--secret-mapping-output", str(secret_path)],
        cwd=ROOT.parent,
        check=True,
    )
    if not secret_path.is_file():
        die("secret mapping was not created outside repository")
    if (HOLDOUT / "holdout_mapping.json").exists():
        die("secret mapping leaked into repository holdout directory")
    bundle_sha, prompt_sha = validate_bundle()
    print("HOLDOUT_BUNDLE_LEAKAGE_GUARD_PASS", bundle_sha, prompt_sha)


def cmd_locator(artifact_id: str, run_id: str) -> None:
    bundle_sha, _ = validate_bundle()
    s = read_json(HOLDOUT / "mapping_seal.json")
    x = {
        "schema_version": "1.0",
        "locator_id": "M26-E-REASON-HOLDOUT-MAPPING-ARTIFACT-LOCATOR-V1",
        "artifact_name": "e-reason-holdout-secret-mapping",
        "artifact_id": str(artifact_id),
        "workflow_run_id": str(run_id),
        "mapping_sha256": s["mapping_sha256"],
        "blind_bundle_sha256": bundle_sha,
        "mapping_material_committed": False,
        "access_rule": "DO_NOT_DOWNLOAD_OR_EXPOSE_TO_C2_BEFORE_HOLDOUT_JUDGMENT_HASHES_FREEZE",
    }
    (HOLDOUT / "mapping_artifact_locator.json").write_text(json.dumps(x, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print("HOLDOUT_MAPPING_LOCATOR_WRITTEN", artifact_id)


def validate_c1() -> dict:
    x = read_json(C1 / "c1_judgment_manifest.json")
    if x.get("status") != "PASS_C1_HOLDOUT_JUDGMENTS_FROZEN_AWAITING_C2":
        die("C1 holdout manifest status invalid")
    if x.get("outcomes_seen") is not False or x.get("mapping_seen") is not False:
        die("C1 reports forbidden outcome/mapping access")
    counts = x.get("counts") or {}
    if counts.get("packets") != 92 or counts.get("party_cells") != 828:
        die("C1 holdout judgment panel is not 92 x 9")
    return x


def cmd_c1() -> None:
    validate_bundle()
    if not (C1 / "c1_judgment_manifest.json").exists():
        subprocess.run([sys.executable, str(SCRIPTS / "e_reason_generate_c1_holdout.py")], cwd=ROOT.parent, check=True)
    x = validate_c1()
    print("C1_HOLDOUT_FREEZE_GUARD_PASS", json.dumps((x.get("counts") or {}).get("score_distribution"), sort_keys=True))


def cmd_handoff(out: Path) -> None:
    bundle_sha, prompt_sha = validate_bundle()
    validate_c1()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files = [
        HOLDOUT / "blind_bundle.json",
        HOLDOUT / "bundle_manifest.json",
        HOLDOUT / "mapping_seal.json",
        E / "c2_prompt_v1.md",
        E / "e_reason_output_schema_v1.json",
        E / "e_reason_conditions_v1.json",
    ]
    for p in files:
        shutil.copy2(p, out / p.name)
    start = f"""# OPUS 5 — E_reason C2 LOCKED HOLDOUT RUN — EXACT HANDOFF

Execute the blinded C2 residual-reasoning arm of preregistered experiment `M26-GOAL100-E-REASON-V1` on a LOCKED HOLDOUT.

## Absolute information boundary
Work ONLY inside this handoff directory. Do not browse, use tools, inspect repositories or git history, request extra context, infer real identities, consult remembered election outcomes, or access anything outside this directory. The target outcome and real-to-anonymous mapping are intentionally absent. If either becomes visible, STOP with `E_REASON_LEAKAGE_INVALIDATED` and produce no judgments.

## Frozen treatment
Use `c2_prompt_v1.md` VERBATIM. Bundle canonical-core SHA-256: `{bundle_sha}`. Prompt SHA-256: `{prompt_sha}`.

Verify exactly 92 packets and 828 party cells. Judge each packet independently under the frozen prompt using RUN_ID `M26-E-REASON-C2-HOLDOUT-OPUS5-V1`, MODEL_ID `OPUS-5`, ATTEMPT_NUMBER=1 initially, and exactly one PACKET_JSON at a time. Validate against `e_reason_output_schema_v1.json` and all frozen semantic guards. Retry ONLY schema-invalid JSON with identical prompt/packet and no semantic feedback; retain every attempt.

Write `outputs/c2_judgments.jsonl`, `outputs/c2_all_attempts.jsonl`, `outputs/c2_judgment_manifest.json`, and `outputs/c2_terminal_report.json`. Freeze ordered packet hashes and ordered canonical judgment SHA-256 hashes. Manifest must state `outcomes_seen=false`, `mapping_seen=false`, `web_used=false`, `tools_used=false`. Terminal status may be `PASS_C2_HOLDOUT_JUDGMENTS_FROZEN_READY_FOR_OUTCOME_UNSEAL` only on 92/92 valid judgments.

## STOP BOUNDARY
STOP immediately after the 92 C2 judgments and hashes are frozen. Do NOT seek/open the target outcome, score C0/C1/C2, alter lambda/prompt/features/baseline/packets, create F1, or touch Atlas.
"""
    (out / "START_HERE_OPUS5.md").write_text(start, encoding="utf-8")
    forbidden = [p.name for p in out.iterdir() if any(t in p.name.lower() for t in ("outcome", "result", "holdout_mapping"))]
    if forbidden:
        die("forbidden material in Opus handoff: " + repr(forbidden))
    sums = []
    for p in sorted(out.iterdir()):
        if p.is_file() and p.name != "HANDOFF_SHA256SUMS.txt":
            sums.append(f"{sha_file(p)}  {p.name}")
    (out / "HANDOFF_SHA256SUMS.txt").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print("OPUS5_HOLDOUT_HANDOFF_INTEGRITY_PASS", bundle_sha, prompt_sha)


def main() -> None:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--secret-path", required=True)
    l = sub.add_parser("locator"); l.add_argument("--artifact-id", required=True); l.add_argument("--run-id", required=True)
    sub.add_parser("c1")
    h = sub.add_parser("handoff"); h.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.cmd == "build": cmd_build(Path(a.secret_path).resolve())
    elif a.cmd == "locator": cmd_locator(a.artifact_id, a.run_id)
    elif a.cmd == "c1": cmd_c1()
    elif a.cmd == "handoff": cmd_handoff(Path(a.out).resolve())


if __name__ == "__main__":
    main()
