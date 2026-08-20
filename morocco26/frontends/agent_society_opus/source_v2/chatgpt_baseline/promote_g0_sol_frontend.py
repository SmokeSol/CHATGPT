#!/usr/bin/env python3
"""Canonical Sol-aware wrapper around the generic G0 frontend promoter.

The generic promoter predates the pre-output switch from Terra to Sol. This
wrapper leaves its mapping/aggregation logic unchanged, runs it preview-first,
then rewrites and re-hashes only the frozen baseline identifier before optional
application. It never touches model decisions or historical outcomes.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import sys
from typing import Any, Sequence

import promote_g0_frontend as P

FROZEN_MODEL = "gpt-5.6-sol"
OLD_BASELINE = "G0_CHATGPT_GPT56_TERRA"
NEW_BASELINE = "G0_CHATGPT_GPT56_SOL"


class SolPromotionError(RuntimeError):
    pass


def replace_baseline(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: replace_baseline(item) for key, item in value.items()}
    if isinstance(value, list):
        return [replace_baseline(item) for item in value]
    if value == OLD_BASELINE:
        return NEW_BASELINE
    if isinstance(value, str):
        return value.replace(OLD_BASELINE, NEW_BASELINE)
    return value


def rewrite_preview(preview: pathlib.Path) -> None:
    json_files = [path for path in preview.iterdir() if path.is_file() and path.suffix == ".json"]
    for path in json_files:
        payload = json.loads(path.read_text(encoding="utf-8"))
        P.write_json(path, replace_baseline(payload), pretty=(path.name != "maroc.json"))

    provenance_path = preview / "reference_provenance.json"
    if provenance_path.is_file():
        provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
        provenance["primary_reference_id"] = NEW_BASELINE
        provenance["model"] = FROZEN_MODEL
        derived = {}
        for name in ("societe.json", "portraits.json", "g0_simulator.json", "maroc.json"):
            path = preview / name
            if path.is_file():
                derived[name] = P.file_record(path)
        provenance["derived_files"] = derived
        P.write_json(provenance_path, provenance, pretty=True)

    audit_path = preview / "promotion_audit.json"
    if audit_path.is_file():
        audit = json.loads(audit_path.read_text(encoding="utf-8"))
        audit["model"] = FROZEN_MODEL
        audit["baseline_id"] = NEW_BASELINE
        audit["preview_files"] = {
            path.name: P.file_record(path)
            for path in sorted(preview.iterdir())
            if path.is_file() and path.name != "promotion_audit.json"
        }
        P.write_json(audit_path, audit, pretty=True)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, type=pathlib.Path)
    ap.add_argument("--run", required=True, type=pathlib.Path)
    ap.add_argument("--web-root", type=pathlib.Path, default=P.HERE.parent / "web")
    ap.add_argument("--e0-run", type=pathlib.Path)
    ap.add_argument("--preview-dir", type=pathlib.Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-territory-mean-cost", type=float, default=0.0025)
    ap.add_argument("--max-territory-cost", type=float, default=0.02)
    ap.add_argument("--max-party-residual", type=float, default=0.005)
    ap.add_argument("--party-ambiguity-epsilon", type=float, default=1e-8)
    args = ap.parse_args(argv)

    P.EXPECTED_MODEL = FROZEN_MODEL
    run_root = args.run.expanduser().resolve()
    state = P.read_json(run_root / "run_state.json")
    if state.get("model") != FROZEN_MODEL:
        raise SolPromotionError(
            f"G0 run model {state.get('model')!r} != frozen {FROZEN_MODEL!r}"
        )

    preview = (
        args.preview_dir.expanduser().resolve()
        if args.preview_dir
        else run_root / "promotion_preview"
    )
    underlying = [
        "--env", str(args.env),
        "--run", str(args.run),
        "--web-root", str(args.web_root),
        "--preview-dir", str(preview),
        "--max-territory-mean-cost", str(args.max_territory_mean_cost),
        "--max-territory-cost", str(args.max_territory_cost),
        "--max-party-residual", str(args.max_party_residual),
        "--party-ambiguity-epsilon", str(args.party_ambiguity_epsilon),
    ]
    if args.e0_run:
        underlying += ["--e0-run", str(args.e0_run)]
    code = P.main(underlying)
    if code != 0:
        return code
    rewrite_preview(preview)
    if args.apply:
        P.apply_preview(preview, args.web_root.expanduser().resolve() / "data")
        print("PASS_G0_SOL_REFERENCE_PROMOTED_TO_FRONTEND")
    else:
        print(f"PASS_G0_SOL_PROMOTION_PREVIEW_READY {preview}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (SolPromotionError, P.PromotionError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
