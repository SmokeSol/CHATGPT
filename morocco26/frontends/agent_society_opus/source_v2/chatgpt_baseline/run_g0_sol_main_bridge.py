#!/usr/bin/env python3
"""Canonical enriched G0 launcher: GPT-5.6 Sol + frozen main bridge."""
from __future__ import annotations
import copy, dataclasses, hashlib, json, pathlib, re, sys
from typing import Any

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_chatgpt_baseline as runner

FROZEN_MODEL = "gpt-5.6-sol"
FROZEN_REASONING = "medium"
PROTOCOL_ID = "ATLAS_CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V2_MAIN_BRIDGE"
BRIDGE_ID = "M26_AS_MAIN_BRIDGE_V1"

def pop_option(args: list[str], name: str) -> str:
    for i, value in enumerate(list(args)):
        if value == name:
            if i + 1 >= len(args):
                raise runner.RunnerError(f"{name} requires a value")
            result = args[i + 1]
            del args[i:i+2]
            return result
        if value.startswith(name + "="):
            result = value.split("=", 1)[1]
            args.remove(value)
            return result
    raise runner.RunnerError(f"{name} is mandatory for enriched G0")

def load_bridge(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise runner.RunnerError(f"main bridge not found: {path}")
    raw = path.read_bytes()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise runner.RunnerError(f"invalid main bridge JSON: {exc}") from exc
    checks = {
        "bridge_id": obj.get("bridge_id") == BRIDGE_ID,
        "status": obj.get("status") == "PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL",
        "target_outcomes_present": obj.get("target_outcomes_present") is False,
        "real_identity_material_present": obj.get("real_identity_material_present") is False,
        "floating_main_reads_allowed": obj.get("floating_main_reads_allowed") is False,
        "leak_scan": (obj.get("public_leak_scan") or {}).get("status") == "PASS",
        "main_sha": bool(re.fullmatch(r"[0-9a-f]{40}", str(obj.get("main_commit_sha", "")))),
        "items": isinstance(obj.get("items"), dict) and bool(obj.get("items")),
    }
    failed = sorted(k for k, ok in checks.items() if not ok)
    if failed:
        raise runner.RunnerError(f"main bridge validation failed: {failed}")
    return obj, hashlib.sha256(raw).hexdigest()

def patch_runner(bridge_path: pathlib.Path, bridge: dict[str, Any], bridge_file_sha: str) -> None:
    original_discover = runner.discover_tasks
    original_write_state = runner.write_run_state
    bridge_items = bridge["items"]
    main_sha = str(bridge["main_commit_sha"])

    def discover(root: pathlib.Path):
        tasks, mode = original_discover(root)
        enriched, missing = [], []
        for task in tasks:
            key = f"{task.election_id}|{task.territory_id}"
            item = bridge_items.get(key)
            if item is None:
                missing.append(key)
                continue
            packet = copy.deepcopy(task.packet)
            packet["main_bridge_v1"] = item
            enriched.append(dataclasses.replace(
                task,
                packet=packet,
                source_paths=task.source_paths + (f"MAIN_BRIDGE:{bridge_path}",),
                source_sha256=runner.sha256_json({
                    "frozen_environment_source_sha256": task.source_sha256,
                    "main_bridge_file_sha256": bridge_file_sha,
                    "main_bridge_item_sha256": runner.sha256_json(item),
                    "main_commit_sha": main_sha,
                }),
            ))
        if missing:
            sample = sorted(set(missing))[:5]
            raise runner.RunnerError(
                f"main bridge has no item for {len(set(missing))} election-territory keys, sample={sample}"
            )
        return enriched, mode + "+MAIN_BRIDGE_V1"

    def write_state(**kwargs):
        original_write_state(**kwargs)
        output_root = pathlib.Path(kwargs["output_root"])
        metadata = {
            "main_bridge_id": BRIDGE_ID,
            "main_bridge_path": str(bridge_path),
            "main_bridge_file_sha256": bridge_file_sha,
            "main_commit_sha": main_sha,
            "target_outcomes_present": False,
            "real_identity_material_present": False,
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
    for forbidden in ("--model", "--reasoning"):
        if forbidden in args or any(v.startswith(forbidden + "=") for v in args):
            raise runner.RunnerError(
                f"{forbidden} is frozen by run_g0_sol_main_bridge.py; use {FROZEN_MODEL}/{FROZEN_REASONING}"
            )
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
