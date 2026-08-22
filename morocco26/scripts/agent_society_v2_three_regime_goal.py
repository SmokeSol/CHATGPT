#!/usr/bin/env python3
from __future__ import annotations

"""Build and audit the Agent Society three-regime simulation goal.

This tool performs no model inference. It prepares and validates the immutable
artifacts that must exist before a Sol runner may be invoked.
"""

import argparse
import json
import pathlib
import shutil
import sys
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from three_regime_core import (  # noqa: E402
    BLIND_CONTROL_AGENTS,
    BLIND_CONTROL_BATCH,
    BLIND_CONTROL_REPORT_BYTES,
    BLIND_CONTROL_REPORT_SHA256,
    BLIND_CONTROL_TERRITORY,
    EXPECTED_CONTEXTS,
    EXPECTED_ELECTION_TERRITORY_ITEMS,
    FROZEN_FULL_ENVIRONMENT_SHA256,
    GOAL_ID,
    PRIMARY_REGIMES,
    PROTOCOL_ID,
    REGISTERED_BRANCH_HEAD,
    REGISTERED_MAIN_SHA,
    REGIME_BLIND,
    REGIME_HISTORICAL,
    REGIME_NAMED,
    REGIME_NAMED_TWIN,
    SCHEMA_VERSION,
    ThreeRegimeError,
    build_named_environment,
    build_pointer_only_historical_contract,
    collect_contexts,
    inspect_blind_control_run,
    load_main_bridge,
    named_2026_readiness,
    pseudonymize_named_input,
    read_json,
    safe_extract_environment,
    sha256_file,
    sha256_json,
    utc_now,
    validate_historical_contract,
    validate_named_input,
    verify_freeze_manifest,
    write_json,
)


def require_exact_environment(path: pathlib.Path) -> str:
    path = path.expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise ThreeRegimeError("the three-regime freeze requires the exact full-environment ZIP")
    digest = sha256_file(path)
    if digest != FROZEN_FULL_ENVIRONMENT_SHA256:
        raise ThreeRegimeError(
            f"full-environment SHA256 mismatch: {digest} != {FROZEN_FULL_ENVIRONMENT_SHA256}"
        )
    return digest


def control_registration(report: pathlib.Path | None, raw_run: pathlib.Path | None) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "regime": REGIME_BLIND,
        "scientific_role": "ATTRIBUTE_ONLY_CONTROL_NOT_PRIMARY_ELECTION_SIMULATION",
        "primary_simulation": False,
        "new_inference_allowed_by_default": False,
        "known_report": {
            "sha256": BLIND_CONTROL_REPORT_SHA256,
            "bytes": BLIND_CONTROL_REPORT_BYTES,
            "agents": BLIND_CONTROL_AGENTS,
            "batch_id": BLIND_CONTROL_BATCH,
            "anonymous_territory_id": BLIND_CONTROL_TERRITORY,
        },
        "raw_D0_registered": False,
        "report_registered": False,
    }
    if report is not None:
        report = report.expanduser().resolve()
        if not report.is_file():
            raise ThreeRegimeError(f"control report not found: {report}")
        digest = sha256_file(report)
        if digest != BLIND_CONTROL_REPORT_SHA256:
            raise ThreeRegimeError(
                f"control report SHA mismatch: {digest} != {BLIND_CONTROL_REPORT_SHA256}"
            )
        result["report_registered"] = True
        result["report_path"] = str(report)
    if raw_run is not None:
        raw = inspect_blind_control_run(raw_run)
        result["raw_D0_registered"] = True
        result["raw_run"] = raw
        result["raw_run_path"] = raw["root"]
        result["raw_run_state_sha256"] = raw["run_state_sha256"]
        result["validated_work_items"] = 1
        result["validated_rows"] = raw["rows"]
    result["status"] = (
        "PASS_BLIND_ATTRIBUTE_CONTROL_REGISTERED"
        if result["report_registered"] and result["raw_D0_registered"]
        else "PASS_BLIND_CONTROL_REPORT_REGISTERED_RAW_D0_PENDING"
        if result["report_registered"]
        else "BLIND_CONTROL_REFERENCE_DECLARED_NOT_MATERIALIZED"
    )
    return result


def build_historical_contracts(
    *,
    environment_zip: pathlib.Path,
    bridge_path: pathlib.Path,
    output_dir: pathlib.Path,
) -> dict[str, Any]:
    environment_digest = require_exact_environment(environment_zip)
    bridge, bridge_digest = load_main_bridge(bridge_path)
    cache = output_dir / "_environment_cache"
    extracted, _ = safe_extract_environment(environment_zip, cache)
    records, audit = collect_contexts(extracted, strict_counts=True)
    if audit["context_count"] != EXPECTED_CONTEXTS:
        raise ThreeRegimeError("historical context count gate failed")
    if audit["election_territory_count"] != EXPECTED_ELECTION_TERRITORY_ITEMS:
        raise ThreeRegimeError("historical election×territory gate failed")

    contracts_root = output_dir / "historical_semiblind_rich" / "contracts"
    contracts: list[dict[str, Any]] = []
    bridge_items = bridge["items"]
    controls_scope = (bridge.get("historical_controls") or {}).get("scope")
    scoped = controls_scope == "DEVELOPMENT_ONLY_P1_PILOT"
    seen_et: set[str] = set()
    for record in records:
        if scoped and record.election_id not in {k.split("|", 1)[0] for k in bridge_items}:
            continue
        if record.election_territory_key not in bridge_items:
            raise ThreeRegimeError(
                f"main bridge missing historical key {record.election_territory_key}"
            )
        contract = build_pointer_only_historical_contract(record)
        validate_historical_contract(contract, strict_shape=True)
        seen_et.add(record.election_territory_key)
        path = (
            contracts_root
            / record.election_id
            / record.condition_id
            / f"{record.territory_id}.json"
        )
        write_json(path, contract)
        contracts.append(
            {
                "context_key": record.context_key,
                "election_territory_key": record.election_territory_key,
                "contract_path": str(path.relative_to(output_dir)),
                "contract_sha256": sha256_file(path),
                "source_context_sha256": record.raw_sha256,
            }
        )
    extra = sorted(set(bridge_items) - seen_et)
    if extra:
        raise ThreeRegimeError(f"main bridge contains keys outside the full environment: {extra[:5]}")

    index = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "protocol_id": PROTOCOL_ID,
        "regime": REGIME_HISTORICAL,
        "status": "PASS_HISTORICAL_SEMIBLIND_RICH_POINTER_CONTRACTS_READY",
        "generated_at": utc_now(),
        "full_environment_zip_sha256": environment_digest,
        "main_bridge_file_sha256": bridge_digest,
        "main_commit_sha": bridge["main_commit_sha"],
        "model_packet_mutated": False,
        "model_packet_values_duplicated": False,
        "prompt_delta": "POINTER_ONLY_READING_CONTRACT_AND_INTERPRETATION_INSTRUCTION",
        "context_audit": audit,
        "historical_controls": {
            "scope": (bridge.get("historical_controls") or {}).get("scope"),
        },
        "contracts": contracts,
        "target_outcomes_read": False,
        "real_identity_material_written": False,
        "promotion_allowed": False,
        "next_gate": "Run only the fixed 32-work-item startup through run_g0_sol_semiblind_rich.py.",
    }
    index_path = output_dir / "historical_semiblind_rich" / "contract_index.json"
    write_json(index_path, index)
    shutil.rmtree(cache, ignore_errors=True)
    return index


def build_goal_manifest(
    *,
    output_dir: pathlib.Path,
    control: Mapping[str, Any],
    historical: Mapping[str, Any] | None,
    named: Mapping[str, Any],
) -> dict[str, Any]:
    named_ready = named.get("ready_to_generate_named_packets") is True
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "protocol_id": PROTOCOL_ID,
        "status": (
            "PASS_THREE_REGIME_GOAL_READY_NAMED_SOURCE_BLOCKED"
            if not named_ready
            else "PASS_THREE_REGIME_GOAL_ALL_SOURCE_GATES_READY"
        ),
        "created_at": utc_now(),
        "branch_parent_head": REGISTERED_BRANCH_HEAD,
        "registered_main_sha": REGISTERED_MAIN_SHA,
        "primary_regimes": list(PRIMARY_REGIMES),
        "diagnostic_non_primary_regime": REGIME_NAMED_TWIN,
        "regimes": {
            REGIME_BLIND: dict(control),
            REGIME_HISTORICAL: (
                {
                    "status": historical.get("status"),
                    "context_count": (historical.get("context_audit") or {}).get("context_count"),
                    "contract_index_sha256": sha256_json(historical),
                }
                if historical is not None
                else {"status": "PENDING_ENVIRONMENT_AND_BRIDGE_CERTIFICATE"}
            ),
            REGIME_NAMED: dict(named),
        },
        "comparison_contract": {
            "blind_vs_semiblind": {
                "same_historical_work_items_required": True,
                "exact_raw_P0_hash_binding_required": True,
                "interpretation": "effect of explicit electoral reading/framing under unchanged historical facts",
                "causal_label_allowed": False,
            },
            "named_vs_named_pseudonymized_twin": {
                "same_2026_packets_except_identity_labels_required": True,
                "paired_pilot_required_before_scale": True,
                "interpretation": "within-2026 identity-label diagnostic",
                "causal_label_allowed": False,
            },
            "historical_vs_named_2026": {
                "interpretation": "descriptive cross-era comparison only",
                "causal_label_allowed": False,
            },
        },
        "hard_stops": {
            "scale_to_94208_before_startup_review": False,
            "named_2026_partial_roster": False,
            "candidate_fabrication": False,
            "historical_identity_unblinding": False,
            "historical_outcome_access": False,
            "duplicate_candidate_or_programme_values": False,
        },
        "next_actions": [
            "Bind the exact one-work-item raw P0 snapshot, then run one same-work-item historical semiblind-rich P1 pilot.",
            "Do not invoke named 2026 while readiness is BLOCKED_NAMED_2026_INCOMPLETE_ROSTER.",
            "Do not expand P1 to 32 work items until the exact paired P0/P1 review is approved.",
        ],
    }
    write_json(output_dir / "three_regime_goal_manifest.json", manifest)
    return manifest


def command_audit_main(args: argparse.Namespace) -> int:
    readiness = named_2026_readiness(args.repo_root.expanduser().resolve(), args.main_sha)
    write_json(args.output.expanduser().resolve(), readiness)
    print(readiness["status"])
    return 0 if readiness["ready_to_generate_named_packets"] else 3


def command_register_control(args: argparse.Namespace) -> int:
    value = control_registration(args.report, args.raw_run)
    write_json(args.output.expanduser().resolve(), value)
    print(value["status"])
    return 0


def command_build_historical(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    index = build_historical_contracts(
        environment_zip=args.environment,
        bridge_path=args.main_bridge,
        output_dir=output,
    )
    print(f"{index['status']} contexts={index['context_audit']['context_count']}")
    return 0


def command_validate_named(args: argparse.Namespace) -> int:
    value = read_json(args.input.expanduser().resolve())
    result = validate_named_input(value)
    if args.output:
        write_json(args.output.expanduser().resolve(), result)
    print(result["status"])
    return 0


def command_pseudonymize_named(args: argparse.Namespace) -> int:
    value = read_json(args.input.expanduser().resolve())
    result = pseudonymize_named_input(value)
    write_json(args.output.expanduser().resolve(), result)
    print("PASS_NAMED_2026_PSEUDONYMIZED_TWIN_READY")
    return 0


def command_build_goal(args: argparse.Namespace) -> int:
    output = args.output.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    control = control_registration(args.control_report, args.control_raw_run)
    write_json(output / "blind_attribute_control" / "registration.json", control)
    named = named_2026_readiness(args.repo_root.expanduser().resolve(), args.main_sha)
    write_json(output / "realistic_2026_named" / "readiness.json", named)
    historical = None
    if args.environment is not None or args.main_bridge is not None:
        if args.environment is None or args.main_bridge is None:
            raise ThreeRegimeError("--environment and --main-bridge must be supplied together")
        historical = build_historical_contracts(
            environment_zip=args.environment,
            bridge_path=args.main_bridge,
            output_dir=output,
        )
    manifest = build_goal_manifest(
        output_dir=output,
        control=control,
        historical=historical,
        named=named,
    )
    print(manifest["status"])
    return 0



def command_build_named_environment(args: argparse.Namespace) -> int:
    value = read_json(args.input.expanduser().resolve())
    output = args.output.expanduser().resolve()
    manifest = build_named_environment(
        value,
        output,
        pseudonymized_twin=args.pseudonymized_twin,
    )
    protocol_root = args.protocol_root.expanduser().resolve()
    prompt = protocol_root / "as2_named_2026_prompt_v2.md"
    schema = protocol_root / "as2_named_2026_output_schema_v2.json"
    if not prompt.is_file() or not schema.is_file():
        raise ThreeRegimeError(
            "named prompt/schema missing from --protocol-root"
        )
    shutil.copy2(prompt, output / prompt.name)
    shutil.copy2(schema, output / schema.name)
    print(
        f"{manifest['status']} regime={manifest['regime']} "
        f"work_items={manifest['work_items']}"
    )
    return 0

def command_verify_freeze(args: argparse.Namespace) -> int:
    result = verify_freeze_manifest(
        args.repo_root.expanduser().resolve(), args.manifest.expanduser().resolve()
    )
    print(
        f"{result['status']} files={result['files_verified']} "
        f"parent={result['parent_branch_head']}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build the named-2026 / rich-historical / blind-control Agent Society goal without model inference."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit-main-2026", help="evaluate exact-SHA 2026 named-input readiness")
    audit.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("."))
    audit.add_argument("--main-sha", default=REGISTERED_MAIN_SHA)
    audit.add_argument("--output", type=pathlib.Path, required=True)
    audit.set_defaults(func=command_audit_main)

    control = sub.add_parser("register-control", help="register the existing blind 32-control artifacts")
    control.add_argument("--report", type=pathlib.Path)
    control.add_argument("--raw-run", type=pathlib.Path)
    control.add_argument("--output", type=pathlib.Path, required=True)
    control.set_defaults(func=command_register_control)

    historical = sub.add_parser("build-historical", help="build pointer-only rich historical reading contracts")
    historical.add_argument("--environment", type=pathlib.Path, required=True)
    historical.add_argument("--main-bridge", type=pathlib.Path, required=True)
    historical.add_argument("--output", type=pathlib.Path, required=True)
    historical.set_defaults(func=command_build_historical)

    named = sub.add_parser("validate-named-input", help="validate a complete current-election named input")
    named.add_argument("--input", type=pathlib.Path, required=True)
    named.add_argument("--output", type=pathlib.Path)
    named.set_defaults(func=command_validate_named)

    twin = sub.add_parser("pseudonymize-named-input", help="create the internal same-facts 2026 twin")
    twin.add_argument("--input", type=pathlib.Path, required=True)
    twin.add_argument("--output", type=pathlib.Path, required=True)
    twin.set_defaults(func=command_pseudonymize_named)

    goal = sub.add_parser("build-goal", help="build the complete goal state and available regime artifacts")
    goal.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("."))
    goal.add_argument("--main-sha", default=REGISTERED_MAIN_SHA)
    goal.add_argument("--environment", type=pathlib.Path)
    goal.add_argument("--main-bridge", type=pathlib.Path)
    goal.add_argument("--control-report", type=pathlib.Path)
    goal.add_argument("--control-raw-run", type=pathlib.Path)
    goal.add_argument("--output", type=pathlib.Path, required=True)
    goal.set_defaults(func=command_build_goal)

    named_environment = sub.add_parser(
        "build-named-environment",
        help="build a runner-compatible named 2026 environment or its same-facts twin",
    )
    named_environment.add_argument("--input", type=pathlib.Path, required=True)
    named_environment.add_argument("--output", type=pathlib.Path, required=True)
    named_environment.add_argument(
        "--protocol-root",
        type=pathlib.Path,
        required=True,
        help="simulation_goal directory containing the frozen named prompt/schema",
    )
    named_environment.add_argument("--pseudonymized-twin", action="store_true")
    named_environment.set_defaults(func=command_build_named_environment)

    freeze = sub.add_parser("verify-freeze", help="verify V6 frozen implementation files")
    freeze.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("."))
    freeze.add_argument("--manifest", type=pathlib.Path, required=True)
    freeze.set_defaults(func=command_verify_freeze)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ThreeRegimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
