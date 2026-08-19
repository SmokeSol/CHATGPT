# -*- coding: utf-8 -*-
"""Execute the pre-registered deterministic social ablations over a frozen isolated run.

Scientific AS3 runs require a true AS2 Opus-5 fresh-context baseline. The E0
deterministic corpus may be used only with the explicit --allow-e0-reference
flag for mechanics/reference checks; such a run is never calibration-eligible.
"""
from __future__ import division
import argparse
import os
import time

try:
    from .baseline_gate import classify_baseline, require_as2_baseline
    from .build_social_graph import validate_graph
    from .common import (
        RELATIONS, read_json, read_jsonl, sha256_file, write_json, write_jsonl,
    )
    from .deterministic_social import run_condition
except ImportError:
    from baseline_gate import classify_baseline, require_as2_baseline
    from build_social_graph import validate_graph
    from common import (
        RELATIONS, read_json, read_jsonl, sha256_file, write_json, write_jsonl,
    )
    from deterministic_social import run_condition


ALL_CONDITIONS = ("ISO", "FAM", "WORK", "NEIGH", "ALL", "SHUFFLE", "ALL_R2")


def resolve_lambdas(args):
    if args.lambda_file:
        payload = read_json(args.lambda_file)
        values = payload.get("lambdas", payload)
        source = {
            "kind": "file",
            "path": args.lambda_file,
            "sha256": sha256_file(args.lambda_file),
            "calibration_status": payload.get("calibration_status", "UNSPECIFIED"),
        }
    else:
        vals = (args.lambda_family, args.lambda_work, args.lambda_neighborhood)
        if any(v is None for v in vals):
            raise ValueError(
                "provide --lambda-file or all three explicit --lambda-family/"
                "--lambda-work/--lambda-neighborhood values"
            )
        values = {
            "family": args.lambda_family,
            "work": args.lambda_work,
            "neighborhood": args.lambda_neighborhood,
        }
        source = {
            "kind": "explicit_cli",
            "calibration_status": "UNSPECIFIED",
        }
    out = {r: float(values[r]) for r in RELATIONS}
    for r, v in out.items():
        if v < 0.0 or v > 0.92:
            raise ValueError("%s lambda must be in [0,0.92]" % r)
    return out, source


def _load_verified_graph(graph_root, ref, placebo=False):
    rel = ref["shuffle_graph"] if placebo else ref["graph"]
    expected = ref["shuffle_graph_sha256"] if placebo else ref["graph_sha256"]
    path = os.path.join(graph_root, rel)
    actual = sha256_file(path)
    if actual != expected:
        raise ValueError("graph hash mismatch: %s" % path)
    graph = read_json(path)
    errs = validate_graph(graph)
    if errs:
        raise ValueError("invalid graph %s: %s" % (path, "; ".join(errs)))
    return graph, actual


def run_work_item(item, env, baseline_run, graph_root, graph_index, dest,
                  conditions, lambdas):
    batch_ref = graph_index["graphs"].get(item["voter_batch_path"])
    if not batch_ref:
        raise ValueError("missing frozen graph for %s" % item["voter_batch_path"])

    batch_path = os.path.join(env, item["voter_batch_path"])
    if sha256_file(batch_path) != batch_ref["voter_batch_sha256"]:
        raise ValueError("voter batch changed since graph freeze: %s" % batch_path)

    baseline_path = os.path.join(baseline_run, item["output_path"])
    baseline_rows = read_jsonl(baseline_path)
    graph, graph_sha = _load_verified_graph(graph_root, batch_ref, False)
    placebo_graph = None
    placebo_sha = None
    records = []

    for condition in conditions:
        if condition == "SHUFFLE":
            if placebo_graph is None:
                placebo_graph, placebo_sha = _load_verified_graph(graph_root, batch_ref, True)
            rows = run_condition(baseline_rows, placebo_graph, "ALL", lambdas)
            for row in rows:
                row.setdefault("social_influence", {})["ablation"] = "SHUFFLE"
        else:
            rows = run_condition(baseline_rows, graph, condition, lambdas)
            if condition != "ISO":
                for row in rows:
                    row.setdefault("social_influence", {})["ablation"] = condition

        out_path = os.path.join(dest, "conditions", condition, item["output_path"])
        write_jsonl(out_path, rows)
        records.append({
            "condition": condition,
            "output_path": os.path.relpath(out_path, dest).replace(os.sep, "/"),
            "output_sha256": sha256_file(out_path),
            "rows": len(rows),
        })

    return {
        "election_id": item["anonymous_election_id"],
        "territory_id": item["anonymous_territory_id"],
        "condition_id": item["condition_id"],
        "voter_batch_path": item["voter_batch_path"],
        "baseline_output_path": item["output_path"],
        "baseline_output_sha256": sha256_file(baseline_path),
        "graph_sha256": graph_sha,
        "placebo_graph_sha256": placebo_sha,
        "outputs": records,
    }


def execute(env, baseline_run, graph_root, dest, conditions, lambdas,
            lambda_source=None, allow_e0_reference=False):
    if allow_e0_reference:
        baseline_provenance = classify_baseline(baseline_run)
        if baseline_provenance["baseline_class"] != "E0_DETERMINISTIC_REFERENCE":
            raise ValueError(
                "--allow-e0-reference is only valid for the registered E0 deterministic baseline; got %s"
                % baseline_provenance["baseline_class"]
            )
        scientific_status = "E0_MECHANICS_REFERENCE_ONLY_NOT_AS3"
    else:
        baseline_provenance = require_as2_baseline(baseline_run)
        scientific_status = "AS3_FROM_TRUE_AS2_BASELINE"

    wm_path = os.path.join(env, "work_manifest.json")
    wm = read_json(wm_path)
    index_path = os.path.join(graph_root, "graph_index.json")
    graph_index = read_json(index_path)
    if graph_index["work_manifest_sha256"] != sha256_file(wm_path):
        raise ValueError("work_manifest differs from graph freeze")

    conditions = tuple(c.upper() for c in conditions)
    bad = [c for c in conditions if c not in ALL_CONDITIONS]
    if bad:
        raise ValueError("unsupported conditions: %s" % ",".join(bad))

    manifest = {
        "schema_version": "ATLAS_SOCIAL_RUN_MANIFEST_V1",
        "protocol": "R0_ISOLATED__R1_SYNCHRONOUS__R2_SYNCHRONOUS_STOP",
        "scientific_status": scientific_status,
        "created_unix": int(time.time()),
        "work_manifest_sha256": sha256_file(wm_path),
        "graph_index_sha256": sha256_file(index_path),
        "baseline_provenance": baseline_provenance,
        "lambdas": lambdas,
        "lambda_source": lambda_source or {"kind": "programmatic"},
        "conditions": list(conditions),
        "work_items": [],
    }

    for idx, item in enumerate(wm["work_items"], 1):
        manifest["work_items"].append(
            run_work_item(
                item, env, baseline_run, graph_root, graph_index, dest,
                conditions, lambdas
            )
        )
        if idx % 25 == 0:
            print("social work items %d/%d" % (idx, len(wm["work_items"])))

    write_json(os.path.join(dest, "run_manifest.json"), manifest, pretty=True)
    print("PASS_SOCIAL_RUN %d work_items conditions=%s baseline=%s status=%s" %
          (
              len(manifest["work_items"]), ",".join(conditions),
              baseline_provenance["baseline_class"], scientific_status
          ))
    return manifest


def cli(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("env")
    ap.add_argument("baseline_run")
    ap.add_argument("graph_root")
    ap.add_argument("dest")
    ap.add_argument("--conditions", default=",".join(ALL_CONDITIONS))
    ap.add_argument("--lambda-file")
    ap.add_argument("--lambda-family", type=float)
    ap.add_argument("--lambda-work", type=float)
    ap.add_argument("--lambda-neighborhood", type=float)
    ap.add_argument(
        "--allow-e0-reference", action="store_true",
        help="allow the deterministic E0 baseline for mechanics only; never AS3/calibration",
    )
    args = ap.parse_args(argv)
    lambdas, source = resolve_lambdas(args)
    execute(
        args.env, args.baseline_run, args.graph_root, args.dest,
        [x.strip() for x in args.conditions.split(",") if x.strip()],
        lambdas, source, args.allow_e0_reference
    )


if __name__ == "__main__":
    cli()
