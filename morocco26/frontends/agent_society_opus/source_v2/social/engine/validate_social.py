# -*- coding: utf-8 -*-
"""Validation gates for ATLAS social graphs and social run artifacts."""
from __future__ import division
import argparse
import os

try:
    from .baseline_gate import classify_baseline
    from .build_social_graph import validate_graph
    from .common import read_json, read_jsonl, sha256_file
    from .deterministic_social import max_decision_delta, run_condition
except ImportError:
    from baseline_gate import classify_baseline
    from build_social_graph import validate_graph
    from common import read_json, read_jsonl, sha256_file
    from deterministic_social import max_decision_delta, run_condition


CORE_FIELDS = (
    "weighted_archetype_id",
    "turnout_probability",
    "conditional_party_probabilities",
    "factor_importance",
    "reason_codes",
)


def _core(row):
    return {k: row.get(k) for k in CORE_FIELDS}


def _validate_probabilities(rows, label):
    errors = []
    for i, row in enumerate(rows):
        t = float(row["turnout_probability"])
        if t < -1e-12 or t > 1.0 + 1e-12:
            errors.append("%s row %d turnout out of range" % (label, i))
        p = row["conditional_party_probabilities"]
        if any(float(v) < -1e-12 for v in p.values()):
            errors.append("%s row %d negative party probability" % (label, i))
        s = sum(float(v) for v in p.values())
        if abs(s - 1.0) > 1e-8:
            errors.append("%s row %d probabilities sum %.12f" % (label, i, s))
    return errors


def validate_graph_root(env, graph_root):
    wm_path = os.path.join(env, "work_manifest.json")
    idx_path = os.path.join(graph_root, "graph_index.json")
    idx = read_json(idx_path)
    errors = []
    if idx["work_manifest_sha256"] != sha256_file(wm_path):
        errors.append("work_manifest hash mismatch")
    for batch_path, ref in idx["graphs"].items():
        batch_abs = os.path.join(env, batch_path)
        if sha256_file(batch_abs) != ref["voter_batch_sha256"]:
            errors.append("voter batch hash mismatch: %s" % batch_path)
        for kind, hkey in (("graph", "graph_sha256"),
                           ("shuffle_graph", "shuffle_graph_sha256")):
            path = os.path.join(graph_root, ref[kind])
            if sha256_file(path) != ref[hkey]:
                errors.append("%s hash mismatch: %s" % (kind, path))
                continue
            g = read_json(path)
            for err in validate_graph(g):
                errors.append("%s: %s" % (path, err))
    if errors:
        raise ValueError("\n".join(errors))
    print("PASS_SOCIAL_GRAPH_VALIDATION %d graphs" % len(idx["graphs"]))


def validate_run(env, baseline_run, graph_root, run_root):
    wm = read_json(os.path.join(env, "work_manifest.json"))
    gi = read_json(os.path.join(graph_root, "graph_index.json"))
    manifest = read_json(os.path.join(run_root, "run_manifest.json"))
    errors = []

    actual_baseline = classify_baseline(baseline_run)
    recorded_baseline = manifest.get("baseline_provenance") or {}
    if recorded_baseline.get("baseline_class") != actual_baseline.get("baseline_class"):
        errors.append("run baseline_class differs from current baseline provenance")
    if recorded_baseline.get("terminal_report_sha256") != actual_baseline.get("terminal_report_sha256"):
        errors.append("run terminal report provenance hash mismatch")
    if recorded_baseline.get("output_manifest_sha256") != actual_baseline.get("output_manifest_sha256"):
        errors.append("run output manifest provenance hash mismatch")

    scientific_status = manifest.get("scientific_status")
    if scientific_status == "AS3_FROM_TRUE_AS2_BASELINE":
        if actual_baseline.get("eligible_for_as3_calibration") is not True:
            errors.append("AS3 scientific run does not have a true AS2 fresh-context baseline")
    elif scientific_status == "E0_MECHANICS_REFERENCE_ONLY_NOT_AS3":
        if actual_baseline.get("baseline_class") != "E0_DETERMINISTIC_REFERENCE":
            errors.append("E0 mechanics run is not backed by E0 deterministic provenance")
    else:
        errors.append("unknown or missing scientific_status in run manifest")

    if manifest["work_manifest_sha256"] != sha256_file(os.path.join(env, "work_manifest.json")):
        errors.append("run work_manifest hash mismatch")
    if manifest["graph_index_sha256"] != sha256_file(os.path.join(graph_root, "graph_index.json")):
        errors.append("run graph_index hash mismatch")

    by_key = {
        (x["election_id"], x["territory_id"], x["condition_id"], x["baseline_output_path"]): x
        for x in manifest["work_items"]
    }
    zero = {"family": 0.0, "work": 0.0, "neighborhood": 0.0}

    for item in wm["work_items"]:
        key = (
            item["anonymous_election_id"], item["anonymous_territory_id"],
            item["condition_id"], item["output_path"]
        )
        rec = by_key.get(key)
        if rec is None:
            errors.append("missing run manifest record for %r" % (key,))
            continue
        baseline_path = os.path.join(baseline_run, item["output_path"])
        if sha256_file(baseline_path) != rec["baseline_output_sha256"]:
            errors.append("baseline output hash mismatch %s" % item["output_path"])
            continue
        baseline = read_jsonl(baseline_path)

        gref = gi["graphs"][item["voter_batch_path"]]
        graph = read_json(os.path.join(graph_root, gref["graph"]))
        ident = run_condition(baseline, graph, "ALL_R2", zero)
        if max_decision_delta(baseline, ident) > 1e-15:
            errors.append("zero-lambda identity failed %s" % item["output_path"])

        for outrec in rec["outputs"]:
            path = os.path.join(run_root, outrec["output_path"])
            if sha256_file(path) != outrec["output_sha256"]:
                errors.append("social output hash mismatch %s" % outrec["output_path"])
                continue
            rows = read_jsonl(path)
            errors.extend(_validate_probabilities(rows, outrec["output_path"]))
            if len(rows) != len(baseline):
                errors.append("row count mismatch %s" % outrec["output_path"])
                continue
            if outrec["condition"] == "ISO":
                for i, (a, b) in enumerate(zip(baseline, rows)):
                    if _core(a) != _core(b):
                        errors.append("ISO changed core decision %s row %d" %
                                      (item["output_path"], i))
                        break
            else:
                expected_round = "R2" if outrec["condition"] == "ALL_R2" else "R1"
                for i, row in enumerate(rows):
                    meta = row.get("social_influence")
                    if not meta:
                        errors.append("%s row %d missing social_influence" %
                                      (outrec["output_path"], i))
                        break
                    if meta.get("round") != expected_round:
                        errors.append("%s row %d wrong round" %
                                      (outrec["output_path"], i))
                        break
                    if not meta.get("synchronous"):
                        errors.append("%s row %d not marked synchronous" %
                                      (outrec["output_path"], i))
                        break

    if errors:
        raise ValueError("\n".join(errors[:100]))
    print("PASS_SOCIAL_RUN_VALIDATION %d work_items baseline=%s status=%s" %
          (len(manifest["work_items"]), actual_baseline["baseline_class"], scientific_status))


def cli(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("graphs")
    p.add_argument("env")
    p.add_argument("graph_root")

    p = sub.add_parser("run")
    p.add_argument("env")
    p.add_argument("baseline_run")
    p.add_argument("graph_root")
    p.add_argument("run_root")

    args = ap.parse_args(argv)
    if args.cmd == "graphs":
        validate_graph_root(args.env, args.graph_root)
    else:
        validate_run(args.env, args.baseline_run, args.graph_root, args.run_root)


if __name__ == "__main__":
    cli()
