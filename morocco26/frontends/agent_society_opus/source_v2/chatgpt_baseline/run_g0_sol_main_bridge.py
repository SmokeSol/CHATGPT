#!/usr/bin/env python3
"""Canonical G0 launcher: GPT-5.6 Sol gated by the frozen exact-SHA main bridge."""
from __future__ import annotations
import dataclasses, hashlib, json, pathlib, sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_chatgpt_baseline as runner

FROZEN_MODEL = "gpt-5.6-sol"
FROZEN_REASONING = "medium"
PROTOCOL_ID = "ATLAS_CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V3_MAIN_BRIDGE"
BRIDGE_ID = "M26_AS_MAIN_BRIDGE_V1"
REGISTERED_MAIN_SHA = "4df897c356d3f0c36832405c7fcfc7f8f0cd6de2"
EXPECTED_BRIDGE_ITEMS = 184
FROZEN_BUNDLE_SHA256 = "e8acad28dea5a531c21171db570b60d612993edd91db8f893e58c187c226696a"


def pop_option(args: list[str], name: str) -> str:
    for i, value in enumerate(list(args)):
        if value == name:
            if i + 1 >= len(args):
                raise runner.RunnerError(f"{name} requires a value")
            result = args[i + 1]
            del args[i:i + 2]
            return result
        if value.startswith(name + "="):
            result = value.split("=", 1)[1]
            args.remove(value)
            return result
    raise runner.RunnerError(f"{name} is mandatory for enriched G0")


def option_value(args: list[str], name: str) -> str:
    for i, value in enumerate(args):
        if value == name:
            if i + 1 >= len(args):
                raise runner.RunnerError(f"{name} requires a value")
            return args[i + 1]
        if value.startswith(name + "="):
            return value.split("=", 1)[1]
    raise runner.RunnerError(f"{name} is mandatory for enriched G0")


def enforce_frozen_bundle(args: list[str]) -> pathlib.Path:
    path = pathlib.Path(option_value(args, "--bundle")).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != ".zip":
        raise runner.RunnerError(
            "enriched G0 requires the exact frozen full-environment ZIP, not an extracted directory"
        )
    digest = runner.sha256_file(path)
    if digest != FROZEN_BUNDLE_SHA256:
        raise runner.RunnerError(
            f"full-environment ZIP hash mismatch: got {digest}, expected {FROZEN_BUNDLE_SHA256}"
        )
    return path


def load_bridge(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise runner.RunnerError(f"main bridge not found: {path}")
    raw = path.read_bytes()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise runner.RunnerError(f"invalid main bridge JSON: {exc}") from exc
    items = obj.get("items")
    semantic = obj.get("semantic_equivalence_audit") or {}
    checks = {
        "bridge_id": obj.get("bridge_id") == BRIDGE_ID,
        "status": obj.get("status") == "PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL",
        "target_outcomes_present": obj.get("target_outcomes_present") is False,
        "real_identity_material_present": obj.get("real_identity_material_present") is False,
        "floating_main_reads_allowed": obj.get("floating_main_reads_allowed") is False,
        "model_semantic_delta_v1": obj.get("model_semantic_delta_v1") is False,
        "semantic_equivalence": semantic.get("status") == "PASS_SEMANTIC_EQUIVALENCE_ONLY",
        "leak_scan": (obj.get("public_leak_scan") or {}).get("status") == "PASS",
        "registered_main_sha": obj.get("main_commit_sha") == REGISTERED_MAIN_SHA,
        "items_type": isinstance(items, dict),
        "items_count": isinstance(items, dict) and len(items) == (
            EXPECTED_BRIDGE_ITEMS
            if (obj.get("historical_controls") or {}).get("scope")
            != "DEVELOPMENT_ONLY_P1_PILOT"
            else EXPECTED_BRIDGE_ITEMS // 2
        ),
        "declared_item_count": obj.get("item_count") == len(items),
    }
    failed = sorted(k for k, ok in checks.items() if not ok)
    if failed:
        raise runner.RunnerError(f"main bridge validation failed: {failed}")
    return obj, hashlib.sha256(raw).hexdigest()


def patch_runner(bridge_path: pathlib.Path, bridge: dict[str, Any], bridge_file_sha: str) -> None:
    """Bind exact main provenance to every task without duplicating model-visible evidence.

    Bridge V1 must be semantically identical to the candidate/programme information
    already in the frozen environment. Therefore the original model packet stays
    unchanged. Any semantic delta is rejected by the bridge builder/load gate and
    requires a new protocol version.
    """
    original_discover = runner.discover_tasks
    original_write_state = runner.write_run_state
    bridge_items = bridge["items"]
    main_sha = str(bridge["main_commit_sha"])
    semantic_audit = bridge["semantic_equivalence_audit"]

    scoped_elections = (
        {k.split("|", 1)[0] for k in bridge_items}
        if (bridge.get("historical_controls") or {}).get("scope")
        == "DEVELOPMENT_ONLY_P1_PILOT"
        else None
    )

    def discover(root: pathlib.Path):
        tasks, mode = original_discover(root)
        if scoped_elections is not None:
            tasks = [t for t in tasks if t.election_id in scoped_elections]
        bound, missing = [], []
        seen_keys = set()
        for task in tasks:
            key = f"{task.election_id}|{task.territory_id}"
            seen_keys.add(key)
            item = bridge_items.get(key)
            if item is None:
                missing.append(key)
                continue
            if item.get("anonymous_election_id") != task.election_id or item.get("anonymous_territory_id") != task.territory_id:
                raise runner.RunnerError(f"main bridge identity mismatch for {key}")
            bound.append(dataclasses.replace(
                task,
                packet=task.packet,
                source_paths=task.source_paths + (f"MAIN_BRIDGE_PROVENANCE:{bridge_path}",),
                source_sha256=runner.sha256_json({
                    "frozen_environment_source_sha256": task.source_sha256,
                    "main_bridge_file_sha256": bridge_file_sha,
                    "main_bridge_item_sha256": runner.sha256_json(item),
                    "main_commit_sha": main_sha,
                    "bridge_semantic_policy": "PASS_SEMANTIC_EQUIVALENCE_ONLY_NO_MODEL_PACKET_DUPLICATION",
                }),
            ))
        if missing:
            sample = sorted(set(missing))[:5]
            raise runner.RunnerError(
                f"main bridge has no item for {len(set(missing))} election-territory keys, sample={sample}"
            )
        extra = sorted(set(bridge_items) - seen_keys)
        if extra:
            raise runner.RunnerError(
                f"main bridge contains {len(extra)} keys outside the frozen environment, sample={extra[:5]}"
            )
        return bound, mode + "+MAIN_BRIDGE_V1_PROVENANCE_BOUND"

    def write_state(**kwargs):
        original_write_state(**kwargs)
        output_root = pathlib.Path(kwargs["output_root"])
        metadata = {
            "main_bridge_id": BRIDGE_ID,
            "main_bridge_path": str(bridge_path),
            "main_bridge_file_sha256": bridge_file_sha,
            "main_commit_sha": main_sha,
            "registered_main_commit_sha": REGISTERED_MAIN_SHA,
            "frozen_full_environment_zip_sha256": FROZEN_BUNDLE_SHA256,
            "target_outcomes_present": False,
            "real_identity_material_present": False,
            "bridge_items": EXPECTED_BRIDGE_ITEMS,
            "semantic_equivalence_status": semantic_audit.get("status"),
            "model_packet_modified_by_bridge_v1": False,
            "duplicate_candidate_or_programme_evidence_added_to_model": False,
        }
        for name in ("run_state.json", "output_manifest.json", "preflight.json"):
            p = output_root / name
            if not p.is_file():
                continue
            data = json.loads(p.read_text(encoding="utf-8"))
            data["main_bridge"] = metadata
            runner.atomic_write_json(p, data)

    runner.discover_tasks = discover
    runner.write_run_state = write_state
    runner.PROTOCOL_ID = PROTOCOL_ID


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    for forbidden in ("--model", "--reasoning", "--allow-noncanonical-counts"):
        if forbidden in args or any(v.startswith(forbidden + "=") for v in args):
            raise runner.RunnerError(f"{forbidden} is forbidden by the enriched G0 freeze")
    enforce_frozen_bundle(args)
    bridge_path = pathlib.Path(pop_option(args, "--main-bridge")).expanduser().resolve()
    bridge, digest = load_bridge(bridge_path)
    patch_runner(bridge_path, bridge, digest)
    return runner.main(args + ["--model", FROZEN_MODEL, "--reasoning", FROZEN_REASONING])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except runner.RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
