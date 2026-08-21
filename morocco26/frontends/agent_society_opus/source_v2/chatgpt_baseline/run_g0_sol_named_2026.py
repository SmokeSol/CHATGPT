#!/usr/bin/env python3
"""Canonical named-2026 Sol launcher.

This runner is intentionally unusable until an exact-SHA named environment has
passed the complete roster, programme, source-date and voter-surface gates. It
never falls back to anonymous historical packets and never invents candidates.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
SCRIPTS = REPO_ROOT / "morocco26" / "scripts"
for path in (HERE, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_chatgpt_baseline as runner  # noqa: E402
from three_regime_core import (  # noqa: E402
    FROZEN_MODEL,
    FROZEN_REASONING,
    GOAL_ID,
    REGISTERED_MAIN_SHA,
    REGIME_NAMED,
    REGIME_NAMED_TWIN,
    ThreeRegimeError,
    read_json,
    sha256_file,
)

PROTOCOL_ID = "ATLAS_CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V4_THREE_REGIME_NAMED_2026"


def option(args: list[str], name: str) -> str:
    for index, value in enumerate(args):
        if value == name:
            if index + 1 >= len(args):
                raise runner.RunnerError(f"{name} requires a value")
            return args[index + 1]
        if value.startswith(name + "="):
            return value.split("=", 1)[1]
    raise runner.RunnerError(f"{name} is mandatory")


def locate_manifest(bundle: pathlib.Path) -> pathlib.Path:
    bundle = bundle.expanduser().resolve()
    cache = bundle.parent / (bundle.name + ".named_manifest_cache")
    extracted, _ = runner.extract_bundle(bundle, cache)
    hits = sorted(extracted.rglob("named_2026_environment_manifest.json"))
    if len(hits) != 1:
        raise runner.RunnerError(
            f"named bundle must contain exactly one named_2026_environment_manifest.json; found {len(hits)}"
        )
    return hits[0]


def validate_manifest(
    path: pathlib.Path, *, expected_regime: str
) -> tuple[dict[str, Any], str]:
    value = read_json(path)
    identity_expected = expected_regime == REGIME_NAMED
    checks = {
        "regime": value.get("regime") == expected_regime,
        "status": value.get("status") == "PASS_REALISTIC_2026_NAMED_ENVIRONMENT_READY",
        "main_sha": value.get("main_commit_sha") == REGISTERED_MAIN_SHA,
        "named_source": value.get("named_source_gate") == "PASS_NAMED_2026_INPUT_READY",
        "identities": value.get("real_identity_material_present") is identity_expected,
        "outcomes": value.get("target_outcomes_present") is False,
        "candidate_fabrication": value.get("candidate_fabrication_used") is False,
        "partial_roster": value.get("partial_roster_used") is False,
        "information_diets": value.get("per_voter_information_diets_present") is True,
        "paired_twin": value.get("pseudonymized_twin_buildable") is True,
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise runner.RunnerError(f"named 2026 environment gate failed: {failed}")
    return dict(value), sha256_file(path)


def patch_state(
    manifest: Mapping[str, Any], digest: str, path: pathlib.Path, *, regime: str
) -> None:
    original = runner.write_run_state

    def write_state(**kwargs):
        original(**kwargs)
        output_root = pathlib.Path(kwargs["output_root"])
        metadata = {
            "goal_id": GOAL_ID,
            "regime": regime,
            "main_commit_sha": REGISTERED_MAIN_SHA,
            "environment_manifest": str(path),
            "environment_manifest_sha256": digest,
            "real_identity_material_present": regime == REGIME_NAMED,
            "target_outcomes_present": False,
            "per_voter_information_diets_present": True,
            "candidate_fabrication_used": False,
            "cross_era_causal_comparison_allowed": False,
        }
        for name in ("run_state.json", "output_manifest.json", "preflight.json"):
            target = output_root / name
            if not target.is_file():
                continue
            value = json.loads(target.read_text(encoding="utf-8"))
            value["three_regime"] = metadata
            runner.atomic_write_json(target, value)

    runner.write_run_state = write_state
    runner.PROTOCOL_ID = PROTOCOL_ID


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    for forbidden in ("--model", "--reasoning", "--allow-noncanonical-counts"):
        if forbidden in args or any(value.startswith(forbidden + "=") for value in args):
            raise runner.RunnerError(f"{forbidden} is forbidden by named-2026 freeze")
    twin = False
    if "--pseudonymized-twin" in args:
        args.remove("--pseudonymized-twin")
        twin = True
    regime = REGIME_NAMED_TWIN if twin else REGIME_NAMED
    bundle = pathlib.Path(option(args, "--bundle"))
    manifest_path = locate_manifest(bundle)
    manifest, digest = validate_manifest(manifest_path, expected_regime=regime)
    patch_state(manifest, digest, manifest_path, regime=regime)
    runner.CANONICAL_WORK_ITEMS = int(manifest["work_items"])
    runner.CANONICAL_ROWS = int(manifest["voter_rows_per_condition"]) * int(manifest["conditions"])
    return runner.main(args + ["--model", FROZEN_MODEL, "--reasoning", FROZEN_REASONING])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (runner.RunnerError, ThreeRegimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
