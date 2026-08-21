#!/usr/bin/env python3
"""Fail-closed orchestrator for the three-regime startup gates.

P0 already exists: one fully blind work item / 32 agents.
P1 runs the same one-work-item position under HISTORICAL_SEMIBLIND_RICH.
P2 may expand the historical pair to 32 work items / 1,024 agents.
P3 named 2026 remains blocked until the exact-SHA source gate passes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
from typing import Any, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
SCRIPTS = REPO_ROOT / "morocco26" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from three_regime_core import (  # noqa: E402
    BLIND_CONTROL_AGENTS,
    BLIND_CONTROL_BATCH,
    BLIND_CONTROL_REPORT_SHA256,
    BLIND_CONTROL_TERRITORY,
    GOAL_ID,
    REGIME_HISTORICAL,
    REGIME_NAMED,
    ThreeRegimeError,
    inspect_blind_control_run,
    read_json,
    sha256_file,
    utc_now,
    write_json,
)

SEMIBLIND_RUNNER = HERE / "run_g0_sol_semiblind_rich.py"
NAMED_RUNNER = HERE / "run_g0_sol_named_2026.py"
EXIT_USAGE_LIMIT = 75


def execute(command: list[str], label: str) -> int:
    print(f"\n=== {label} ===", flush=True)
    print(" ".join(command), flush=True)
    result = subprocess.run(command, check=False)
    if result.returncode == EXIT_USAGE_LIMIT:
        print(
            "PAUSED_CHATGPT_USAGE_LIMIT: rerun the identical command; validated artifacts are resumable.",
            file=sys.stderr,
        )
        return result.returncode
    if result.returncode:
        raise ThreeRegimeError(f"{label} failed with exit code {result.returncode}")
    return 0


def validate_control_report(path: pathlib.Path) -> dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise ThreeRegimeError(f"blind control report missing: {path}")
    digest = sha256_file(path)
    if digest != BLIND_CONTROL_REPORT_SHA256:
        raise ThreeRegimeError(
            f"blind control report hash {digest} != {BLIND_CONTROL_REPORT_SHA256}"
        )
    return {
        "status": "PASS_P0_BLIND_CONTROL_REPORT_BOUND",
        "report_path": str(path),
        "report_sha256": digest,
        "work_items": 1,
        "agents": BLIND_CONTROL_AGENTS,
        "anonymous_territory_id": BLIND_CONTROL_TERRITORY,
        "batch_id": BLIND_CONTROL_BATCH,
        "raw_D0_required_for_numeric_pairing": True,
    }


def validate_goal_root(path: pathlib.Path) -> tuple[dict[str, Any], pathlib.Path]:
    root = path.expanduser().resolve()
    manifest_path = root / "three_regime_goal_manifest.json"
    if not manifest_path.is_file():
        raise ThreeRegimeError(f"three-regime goal manifest missing: {manifest_path}")
    manifest = read_json(manifest_path)
    if manifest.get("goal_id") != GOAL_ID:
        raise ThreeRegimeError("wrong three-regime goal manifest")
    return manifest, root


def historical_command(
    args: argparse.Namespace,
    work_items: int,
    *,
    task_regex: str | None = None,
) -> list[str]:
    _, goal_root = validate_goal_root(args.goal_root)
    index = goal_root / "historical_semiblind_rich" / "contract_index.json"
    if not index.is_file():
        raise ThreeRegimeError("historical reading-contract index not built")
    command = [
        sys.executable,
        str(SEMIBLIND_RUNNER),
        "--bundle",
        str(args.environment.expanduser().resolve()),
        "--main-bridge",
        str(args.main_bridge.expanduser().resolve()),
        "--reading-contract-index",
        str(index),
        "--output",
        str(args.output.expanduser().resolve()),
        "--workers",
        str(args.workers),
        "--start",
        str(args.start),
        "--limit",
        str(work_items),
    ]
    selected_regex = task_regex if task_regex is not None else args.task_regex
    if selected_regex:
        command.extend(("--task-regex", selected_regex))
    if args.dry_run:
        command.append("--dry-run")
    return command


def command_status(args: argparse.Namespace) -> int:
    manifest, root = validate_goal_root(args.goal_root)
    named = manifest["regimes"][REGIME_NAMED]
    result = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "status": manifest.get("status"),
        "goal_root": str(root),
        "P0_blind_control": "REPORT_REGISTERED" if manifest["regimes"].get("BLIND_ATTRIBUTE_CONTROL") else "MISSING",
        "P1_historical_32_agents": (
            "READY" if (root / "historical_semiblind_rich" / "contract_index.json").is_file() else "PENDING_CONTRACT_INDEX"
        ),
        "P2_historical_1024_agents": "LOCKED_UNTIL_P1_REVIEW",
        "P3_named_2026": named.get("status"),
        "named_2026_ready": named.get("ready_to_generate_named_packets"),
        "generated_at": utc_now(),
    }
    if args.output:
        write_json(args.output.expanduser().resolve(), result)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


def command_historical_pilot(args: argparse.Namespace) -> int:
    report = validate_control_report(args.control_report)
    raw = inspect_blind_control_run(args.control_raw_run)
    if report["anonymous_territory_id"] != raw["identity"]["anonymous_territory_id"]:
        raise ThreeRegimeError("P0 report/raw territory mismatch")
    if report["batch_id"] != raw["identity"]["batch_id"]:
        raise ThreeRegimeError("P0 report/raw batch mismatch")
    if args.task_regex and args.task_regex != raw["task_regex"]:
        raise ThreeRegimeError("operator --task-regex differs from the exact P0 raw work item")
    command = historical_command(args, 1, task_regex=raw["task_regex"])
    code = execute(command, "P1 · exact same-work-item historical semiblind-rich pilot (32 agents)")
    if code == EXIT_USAGE_LIMIT:
        return code
    terminal = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "status": "PASS_P1_HISTORICAL_SEMIBLIND_32_COMPLETE",
        "regime": REGIME_HISTORICAL,
        "work_items": 1,
        "expected_rows": 32,
        "blind_control_report_sha256": BLIND_CONTROL_REPORT_SHA256,
        "blind_control_raw_output_sha256": raw["output_sha256"],
        "blind_control_raw_state_sha256": raw["run_state_sha256"],
        "paired_identity": raw["identity"],
        "paired_archetype_ids_sha256": raw["archetype_ids_sha256"],
        "same_task_position_verified": True,
        "task_regex": raw["task_regex"],
        "next_gate": "Compare the exact raw P0/P1 rows; do not expand to 1,024 before qualitative review.",
    }
    write_json(args.output.expanduser().resolve() / "three_regime_P1_terminal.json", terminal)
    print(terminal["status"])
    return 0


def command_historical_1024(args: argparse.Namespace) -> int:
    approval = args.p1_review.expanduser().resolve()
    review = read_json(approval)
    if review.get("status") != "PASS_P1_REVIEW_APPROVED_FOR_1024":
        raise ThreeRegimeError("P2 requires a signed-off PASS_P1_REVIEW_APPROVED_FOR_1024 artifact")
    if review.get("blind_vs_rich_reviewed") is not True:
        raise ThreeRegimeError("P1 review does not certify blind-vs-rich inspection")
    command = historical_command(args, 32)
    code = execute(command, "P2 · historical semiblind-rich 32-work-item expansion")
    if code == EXIT_USAGE_LIMIT:
        return code
    terminal = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "status": "PASS_P2_HISTORICAL_SEMIBLIND_1024_COMPLETE",
        "regime": REGIME_HISTORICAL,
        "work_items": 32,
        "expected_rows": 1024,
        "p1_review_sha256": sha256_file(approval),
        "automatic_scale_to_full": False,
    }
    write_json(args.output.expanduser().resolve() / "three_regime_P2_terminal.json", terminal)
    print(terminal["status"])
    return 0


def command_named(args: argparse.Namespace) -> int:
    manifest, _ = validate_goal_root(args.goal_root)
    readiness = manifest["regimes"][REGIME_NAMED]
    if readiness.get("ready_to_generate_named_packets") is not True:
        blockers = readiness.get("blockers") or []
        raise ThreeRegimeError(
            "P3 named 2026 is correctly blocked by source readiness: " + ", ".join(map(str, blockers))
        )
    command = [
        sys.executable,
        str(NAMED_RUNNER),
        "--bundle",
        str(args.named_environment.expanduser().resolve()),
        "--output",
        str(args.output.expanduser().resolve()),
        "--workers",
        str(args.workers),
        "--start",
        str(args.start),
        "--limit",
        str(args.limit),
    ]
    if args.dry_run:
        command.append("--dry-run")
    return execute(command, "P3 · realistic named 2026")


def command_named_paired(args: argparse.Namespace) -> int:
    manifest, _ = validate_goal_root(args.goal_root)
    readiness = manifest["regimes"][REGIME_NAMED]
    if readiness.get("ready_to_generate_named_packets") is not True:
        blockers = readiness.get("blockers") or []
        raise ThreeRegimeError(
            "P3 named/twin pilot is correctly blocked by source readiness: "
            + ", ".join(map(str, blockers))
        )
    named_command = [
        sys.executable,
        str(NAMED_RUNNER),
        "--bundle", str(args.named_environment.expanduser().resolve()),
        "--output", str(args.named_output.expanduser().resolve()),
        "--workers", str(args.workers),
        "--start", str(args.start),
        "--limit", str(args.limit),
    ]
    twin_command = [
        sys.executable,
        str(NAMED_RUNNER),
        "--bundle", str(args.twin_environment.expanduser().resolve()),
        "--pseudonymized-twin",
        "--output", str(args.twin_output.expanduser().resolve()),
        "--workers", str(args.workers),
        "--start", str(args.start),
        "--limit", str(args.limit),
    ]
    if args.dry_run:
        named_command.append("--dry-run")
        twin_command.append("--dry-run")
    code = execute(named_command, "P3A · realistic named 2026 pilot")
    if code == EXIT_USAGE_LIMIT:
        return code
    code = execute(twin_command, "P3B · same-facts pseudonymized 2026 twin")
    if code == EXIT_USAGE_LIMIT:
        return code
    terminal = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "status": "PASS_P3_NAMED_2026_AND_TWIN_PAIRED_PILOT_COMPLETE",
        "start": args.start,
        "work_items_each": args.limit,
        "same_start_and_limit": True,
        "automatic_scale": False,
        "next_gate": "Run compare_three_regime_startup.py and explicitly review identity-label sensitivity before any scale.",
    }
    terminal_root = args.named_output.expanduser().resolve().parent
    write_json(terminal_root / "three_regime_P3_paired_terminal.json", terminal)
    print(terminal["status"])
    return 0


def common_historical(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--goal-root", type=pathlib.Path, required=True)
    parser.add_argument("--environment", type=pathlib.Path, required=True)
    parser.add_argument("--main-bridge", type=pathlib.Path, required=True)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--workers", type=int, default=1, choices=(1, 2))
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--task-regex")
    parser.add_argument("--dry-run", action="store_true")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    status = sub.add_parser("status")
    status.add_argument("--goal-root", type=pathlib.Path, required=True)
    status.add_argument("--output", type=pathlib.Path)
    status.set_defaults(func=command_status)

    p1 = sub.add_parser("historical-pilot-32")
    common_historical(p1)
    p1.add_argument("--control-report", type=pathlib.Path, required=True)
    p1.add_argument("--control-raw-run", type=pathlib.Path, required=True)
    p1.set_defaults(func=command_historical_pilot)

    p2 = sub.add_parser("historical-expand-1024")
    common_historical(p2)
    p2.add_argument("--p1-review", type=pathlib.Path, required=True)
    p2.set_defaults(func=command_historical_1024)

    p3 = sub.add_parser("named-2026")
    p3.add_argument("--goal-root", type=pathlib.Path, required=True)
    p3.add_argument("--named-environment", type=pathlib.Path, required=True)
    p3.add_argument("--output", type=pathlib.Path, required=True)
    p3.add_argument("--workers", type=int, default=1, choices=(1, 2))
    p3.add_argument("--start", type=int, default=0)
    p3.add_argument("--limit", type=int, default=1)
    p3.add_argument("--dry-run", action="store_true")
    p3.set_defaults(func=command_named)

    paired = sub.add_parser("named-paired-pilot")
    paired.add_argument("--goal-root", type=pathlib.Path, required=True)
    paired.add_argument("--named-environment", type=pathlib.Path, required=True)
    paired.add_argument("--twin-environment", type=pathlib.Path, required=True)
    paired.add_argument("--named-output", type=pathlib.Path, required=True)
    paired.add_argument("--twin-output", type=pathlib.Path, required=True)
    paired.add_argument("--workers", type=int, default=1, choices=(1, 2))
    paired.add_argument("--start", type=int, default=0)
    paired.add_argument("--limit", type=int, default=1)
    paired.add_argument("--dry-run", action="store_true")
    paired.set_defaults(func=command_named_paired)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ThreeRegimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
