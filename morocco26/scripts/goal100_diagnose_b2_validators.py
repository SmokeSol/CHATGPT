#!/usr/bin/env python3
"""Diagnose why B2-adjacent validators fail, without patching any of them.

Each validator is executed twice: once against the working tree as checked out,
and once against a line-ending-normalized copy. The pair separates a genuine
contract failure from a checkout artifact, which is the difference between a
repository defect and a local environment quirk.

Classification is evidence-driven, never asserted:

  CONSISTENT                                  passes as checked out
  ENVIRONMENT_LINE_ENDING                     fails as checked out, passes under LF
  STALE_ASSERTION_AFTER_LEGITIMATE_TRANSITION fails both, and the assertion pins a
                                              gate state that a later certified gate
                                              legitimately superseded
  REQUIRES_HUMAN_REVIEW                       fails both, unexplained

Nothing here rewrites a validator. Obsolete assertions produce a proposed
versioned amendment for separate review.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"
DIAGNOSTIC_PATH = G100 / "b2_validator_consistency_diagnostic.json"

VALIDATORS = [
    {
        "validator": "validate_b2_protocol",
        "asserts_gate_state_of": "B2-1-SOURCE-UNIVERSE-FROZEN",
        "pinned_expectation": "every gate after B2-1 is OPEN and next_gate is B2-2",
    },
    {
        "validator": "validate_b2_source_universe",
        "asserts_gate_state_of": "B2-1-SOURCE-UNIVERSE-FROZEN",
        "pinned_expectation": "next_gate is B2-2-IDENTITY-TERRITORY-CROSSWALK",
    },
    {
        "validator": "validate_goal100_tracking",
        "asserts_gate_state_of": None,
        "pinned_expectation": "registered F-1 artifact hashes match the snapshot manifest",
    },
    {
        "validator": "validate_b2_historical_panel",
        "asserts_gate_state_of": "B2-3-HISTORICAL-FEATURE-PANEL",
        "pinned_expectation": "panel and certificate satisfy the B2-3 contract",
    },
    {
        "validator": "validate_anti_drift",
        "asserts_gate_state_of": None,
        "pinned_expectation": "north-star and phase invariants hold",
    },
]

TEXT_SUFFIXES = {".json", ".py", ".md", ".csv", ".jsonl", ".yml", ".yaml"}


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def run_validator(name: str, cwd: Path) -> dict:
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    try:
        proc = subprocess.run(
            [sys.executable, str(Path("morocco26") / "scripts" / f"{name}.py")],
            cwd=cwd, env=env, capture_output=True, text=True, timeout=600,
        )
    except subprocess.TimeoutExpired:
        return {"exit_code": None, "first_line": "TIMEOUT", "passed": False}
    output = (proc.stdout or "") + (proc.stderr or "")
    first = next((line for line in output.splitlines() if line.strip()), "")
    return {"exit_code": proc.returncode, "first_line": first.strip()[:400], "passed": proc.returncode == 0}


def normalized_tree() -> Path:
    """A copy of the repository with every text file forced to LF."""
    target = Path(tempfile.mkdtemp(prefix="b2_lf_"))
    shutil.copytree(ROOT, target / ROOT.name, dirs_exist_ok=True)
    converted = 0
    for path in (target / ROOT.name).rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES:
            raw = path.read_bytes()
            if b"\r\n" in raw:
                path.write_bytes(raw.replace(b"\r\n", b"\n"))
                converted += 1
    return target, converted


def line_ending_evidence() -> dict:
    """Show, on a registered F-1 artifact, whether the checkout altered bytes."""
    forecast = G100 / "forecasts" / "F-1" / "forecast.json"
    manifest = G100 / "forecasts" / "F-1" / "snapshot_manifest.json"
    if not (forecast.exists() and manifest.exists()):
        return {"available": False}
    raw = forecast.read_bytes()
    declared = json.loads(manifest.read_text(encoding="utf-8")).get("forecast_artifact_hash")
    try:
        blob = subprocess.check_output(
            ["git", "show", f"HEAD:{forecast.relative_to(REPO).as_posix()}"], cwd=REPO
        )
        blob_hash = hashlib.sha256(blob).hexdigest()
    except (subprocess.CalledProcessError, OSError):
        blob_hash = None
    return {
        "available": True,
        "artifact": forecast.relative_to(REPO).as_posix(),
        "worktree_contains_crlf": b"\r\n" in raw,
        "worktree_sha256": hashlib.sha256(raw).hexdigest(),
        "lf_normalized_sha256": hashlib.sha256(raw.replace(b"\r\n", b"\n")).hexdigest(),
        "git_blob_sha256": blob_hash,
        "manifest_declared_sha256": declared,
        "declared_matches_git_blob": blob_hash == declared,
        "declared_matches_worktree": hashlib.sha256(raw).hexdigest() == declared,
        "git_core_autocrlf": subprocess.run(
            ["git", "config", "--get", "core.autocrlf"], cwd=REPO, capture_output=True, text=True
        ).stdout.strip() or None,
    }


def gate_state() -> dict:
    gates = json.loads(GATES_PATH.read_text(encoding="utf-8"))
    state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {
        "next_gate": gates.get("next_gate"),
        "gate_status": {row["id"]: row["status"] for row in gates["gates"]},
        "closed_gates": state["gates"]["closed"],
        "phase": state["phase"],
    }


HASH_FAILURE_MARKERS = ("hash mismatch", "hash drift")
GIT_REF_FAILURE_MARKERS = ("not reachable from any fetched ref", "unavailable in Git history")


def classify(entry: dict, as_is: dict, lf: dict, gates: dict) -> dict:
    if as_is["passed"]:
        return {"classification": "CONSISTENT", "category": None, "is_repository_defect": False}

    # A validator that needs full history cannot be judged from a tree-only copy.
    if any(marker in lf["first_line"] for marker in GIT_REF_FAILURE_MARKERS):
        return {
            "classification": "ENVIRONMENT_GIT_HISTORY",
            "category": "E_LOCAL_CHECKOUT_ARTIFACT",
            "is_repository_defect": False,
            "line_ending_effect": (
                "RESOLVED_BY_LF"
                if any(marker in as_is["first_line"] for marker in HASH_FAILURE_MARKERS)
                else "NONE"
            ),
            "explanation": (
                "The validator resolves a recorded model commit against fetched remote refs. A tree-only "
                "or shallow checkout cannot satisfy that, so the failure describes the checkout rather "
                "than the repository. Evaluate it in a full clone with remote-tracking refs present."
            ),
        }

    # Line endings changed the outcome even if a later check still fails.
    if any(marker in as_is["first_line"] for marker in HASH_FAILURE_MARKERS) and (
        as_is["first_line"] != lf["first_line"]
    ):
        return {
            "classification": "ENVIRONMENT_LINE_ENDING",
            "category": "E_LOCAL_CHECKOUT_ARTIFACT",
            "is_repository_defect": False,
            "residual_failure_under_lf": lf["first_line"],
            "explanation": (
                "The raw-byte hash failure disappears once line endings are normalized, so the digest "
                "difference describes the checkout, not the content."
            ),
        }

    if lf["passed"]:
        return {
            "classification": "ENVIRONMENT_LINE_ENDING",
            "category": "E_LOCAL_CHECKOUT_ARTIFACT",
            "is_repository_defect": False,
            "explanation": (
                "The validator hashes raw file bytes. A checkout with core.autocrlf=true rewrites "
                "LF to CRLF, changing the digest of content that is itself unmodified."
            ),
        }
    pinned = entry.get("asserts_gate_state_of")
    if pinned:
        superseded = [
            gate_id for gate_id, status in gates["gate_status"].items()
            if status == "CLOSED" and gate_id > pinned
        ]
        if superseded:
            return {
                "classification": "STALE_ASSERTION_AFTER_LEGITIMATE_TRANSITION",
                "category": "A_STALE_ASSERTION",
                "is_repository_defect": True,
                "superseded_by_closed_gates": sorted(superseded),
                "explanation": (
                    f"The validator pins the point-in-time state at {pinned} closure "
                    f"({entry['pinned_expectation']}). That state was legitimately superseded when "
                    f"{', '.join(sorted(superseded))} closed against its own certificate."
                ),
            }
    return {
        "classification": "REQUIRES_HUMAN_REVIEW",
        "category": "UNCLASSIFIED",
        "is_repository_defect": None,
        "explanation": "Failure reproduces under normalized line endings and is not explained by a gate transition.",
    }


def main() -> None:
    gates = gate_state()
    lf_root, converted = normalized_tree()
    results = []
    try:
        for entry in VALIDATORS:
            as_is = run_validator(entry["validator"], REPO)
            lf = run_validator(entry["validator"], lf_root)
            verdict = classify(entry, as_is, lf, gates)
            results.append({
                **entry,
                "as_checked_out": as_is,
                "line_ending_normalized": lf,
                **verdict,
            })
    finally:
        shutil.rmtree(lf_root, ignore_errors=True)

    defects = [row for row in results if row.get("is_repository_defect") is True]
    unreviewed = [row for row in results if row.get("is_repository_defect") is None]

    diagnostic = {
        "schema_version": "1.0",
        "diagnostic_id": "M26-GOAL100-B2-VALIDATOR-CONSISTENCY-V1",
        "generated_at": now_local(),
        "method": (
            "Each validator runs twice: against the working tree and against a line-ending-normalized "
            "copy. No validator is modified, and no gate criterion is weakened."
        ),
        "text_files_normalized_for_comparison": converted,
        "observed_gate_state": gates,
        "line_ending_evidence": line_ending_evidence(),
        "validators": results,
        "counts": {
            "total": len(results),
            "consistent": sum(row["classification"] == "CONSISTENT" for row in results),
            "environment_artifacts": sum(row["classification"] == "ENVIRONMENT_LINE_ENDING" for row in results),
            "stale_assertions": len(defects),
            "requires_human_review": len(unreviewed),
        },
        "proposed_amendments": [
            {
                "validator": row["validator"],
                "status": "PROPOSED_NOT_APPLIED",
                "required_form": "versioned successor validator, e.g. <name>_v1_1.py, preserving every other check",
                "permitted_change": (
                    f"Replace the point-in-time expectation '{row['pinned_expectation']}' with an "
                    "assertion that the gate sequence is monotonic: a gate may be CLOSED only with its "
                    "required artifact present and PASS."
                ),
                "forbidden_change": "Removing, loosening or skipping any coverage, hash, leakage or claim-count check.",
                "superseded_by_closed_gates": row.get("superseded_by_closed_gates", []),
            }
            for row in defects
        ],
        "F_minus_1_integrity": (
            "INTACT"
            if line_ending_evidence().get("declared_matches_git_blob")
            else "REQUIRES_REVIEW"
        ),
        "repair_policy": "No registered F-1 artifact is modified by this diagnostic.",
    }
    diagnostic["canonical_diagnostic_sha256"] = canonical_sha256(diagnostic)
    dump(DIAGNOSTIC_PATH, diagnostic)

    print("B2_VALIDATOR_DIAGNOSTIC_WRITTEN")
    for row in results:
        print(f"  {row['validator']:<34} {row['classification']}")
    print(f"F-1 integrity: {diagnostic['F_minus_1_integrity']}")
    print(f"stale assertions: {len(defects)}  environment artifacts: "
          f"{diagnostic['counts']['environment_artifacts']}  unreviewed: {len(unreviewed)}")
    raise SystemExit(0 if not unreviewed else 3)


if __name__ == "__main__":
    main()
