#!/usr/bin/env python3
from __future__ import annotations
import argparse, pathlib, sys, tempfile
from typing import Sequence

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from main_bridge_core import (
    BLIND_PATHS, BRIDGE_ID, CONTROL_PATHS, REGISTERED_MAIN_SHA, SCHEMA_VERSION,
    BridgeError, sha256_json, show_json, validate_commit, write_json,
)
from main_bridge_environment import collect_environment, extract_environment
from main_bridge_overlay import build_overlay

def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Build exact-SHA main -> Agent Society anonymous context bridge"
    )
    ap.add_argument("--repo-root", type=pathlib.Path, default=pathlib.Path("."))
    ap.add_argument("--main-sha", default=REGISTERED_MAIN_SHA)
    ap.add_argument("--environment", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--allow-unregistered-main-sha", action="store_true")
    args = ap.parse_args(argv)

    repo = args.repo_root.expanduser().resolve()
    sha = validate_commit(repo, args.main_sha)
    if sha != REGISTERED_MAIN_SHA and not args.allow_unregistered_main_sha:
        raise BridgeError(
            f"main SHA {sha} is not preregistered {REGISTERED_MAIN_SHA}; "
            "review changes and explicitly allow a new snapshot"
        )

    hashes, blind = {}, []
    for _, path in BLIND_PATHS.items():
        obj, digest = show_json(repo, sha, path)
        if not obj.get("anonymous_election_id") or not obj.get("packets"):
            raise BridgeError(f"unexpected blind bundle at {path}")
        blind.append(obj)
        hashes[path] = digest

    controls = {}
    for path in CONTROL_PATHS:
        obj, digest = show_json(repo, sha, path)
        hashes[path] = digest
        controls[pathlib.PurePosixPath(path).name] = {
            "contract_id": obj.get("contract_id"),
            "sha256": digest,
        }

    with tempfile.TemporaryDirectory(prefix="m26-main-bridge-") as tmp:
        envroot = extract_environment(args.environment, pathlib.Path(tmp))
        environment, audit = collect_environment(envroot)
        overlay = build_overlay(
            main_sha=sha,
            blind_bundles=blind,
            environment=environment,
            source_hashes=hashes,
            controls=controls,
        )
        overlay_sha = sha256_json(overlay)
        output = args.output.expanduser().resolve()
        write_json(output, overlay)
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "bridge_id": BRIDGE_ID,
            "status": overlay["status"],
            "main_commit_sha": sha,
            "overlay_path": str(output),
            "overlay_sha256_canonical_json": overlay_sha,
            "source_hashes": hashes,
            "environment_audit": audit,
            "item_count": overlay["item_count"],
            "target_outcomes_read": False,
            "real_identity_material_written": False,
            "programme_layer_status": "EXISTING_FROZEN_ANONYMOUS_PRIORITY_CARDS_PRESERVED",
            "candidate_layer_status": "MAIN_BLIND_EVIDENCE_CONNECTED_WITH_SOURCE_PROVENANCE",
        }
        write_json(output.with_suffix(output.suffix + ".manifest.json"), manifest)

    print(
        f"PASS_MAIN_TO_AGENT_SOCIETY_BRIDGE_V1 items={overlay['item_count']} "
        f"main={sha} sha256={overlay_sha}"
    )
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
