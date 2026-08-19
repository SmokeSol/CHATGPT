# -*- coding: utf-8 -*-
"""Calibrate social lambdas on one explicitly declared historical election.

The script refuses an outcome payload containing any other election id. It
also refuses to open the calibration outcome at all unless the isolated
baseline passes the AS2 Opus-5 fresh-context provenance gate.
"""
from __future__ import division
import argparse
import itertools
import math
import os
import time

try:
    from .baseline_gate import require_as2_baseline
    from .common import read_json, read_jsonl, sha256_file, write_json
    from .deterministic_social import run_condition
    from .score_social import aggregate_rows, outcome_lookup
except ImportError:
    from baseline_gate import require_as2_baseline
    from common import read_json, read_jsonl, sha256_file, write_json
    from deterministic_social import run_condition
    from score_social import aggregate_rows, outcome_lookup


def _target_for(lookup, e, t, c):
    return lookup.get((e, t, c)) or lookup.get((e, t, None))


def _score_aggregate(pred, target):
    keys = sorted(target["party_shares"])
    if set(keys) != set(pred["party_shares"]):
        raise ValueError("party pseudonym mismatch during calibration")
    ysum = sum(float(target["party_shares"][k]) for k in keys)
    if ysum <= 0:
        raise ValueError("target party shares sum to zero")
    y = {k: float(target["party_shares"][k]) / ysum for k in keys}
    diffs = [float(pred["party_shares"][k]) - y[k] for k in keys]
    party_mse = sum(d * d for d in diffs) / len(diffs)
    tdiff = None
    if target.get("turnout") is not None:
        tdiff = float(pred["turnout"]) - float(target["turnout"])
    return party_mse, tdiff


def _evaluate_tuple(items, env, baseline_run, graph_root, graph_index,
                    lookup, election_id, experiment_condition_ids,
                    lambdas, model_condition):
    from_graph_cache = {}
    party_mse = []
    turnout_err = []

    for item in items:
        if item["anonymous_election_id"] != election_id:
            continue
        if experiment_condition_ids and item["condition_id"] not in experiment_condition_ids:
            continue
        target = _target_for(
            lookup, item["anonymous_election_id"], item["anonymous_territory_id"],
            item["condition_id"]
        )
        if target is None:
            continue

        ref = graph_index["graphs"][item["voter_batch_path"]]
        gp = os.path.join(graph_root, ref["graph"])
        if gp not in from_graph_cache:
            if sha256_file(gp) != ref["graph_sha256"]:
                raise ValueError("graph hash mismatch during calibration: %s" % gp)
            from_graph_cache[gp] = read_json(gp)
        graph = from_graph_cache[gp]

        rows = read_jsonl(os.path.join(baseline_run, item["output_path"]))
        predicted = run_condition(rows, graph, model_condition, lambdas)
        agg = aggregate_rows(predicted)
        pmse, terr = _score_aggregate(agg, target)
        party_mse.append(pmse)
        if terr is not None:
            turnout_err.append(terr)

    if not party_mse:
        raise ValueError("no calibration work item matched declared election/outcomes")
    prmse = math.sqrt(sum(party_mse) / len(party_mse))
    trmse = (
        math.sqrt(sum(x * x for x in turnout_err) / len(turnout_err))
        if turnout_err else None
    )
    objective = prmse + (0.25 * trmse if trmse is not None else 0.0)
    return {
        "party_share_rmse": prmse,
        "turnout_rmse": trmse,
        "objective": objective,
        "n_work_items": len(party_mse),
    }


def calibrate(env, baseline_run, graph_root, outcomes_json, election_id,
              output_path, experiment_manifest_path, experiment_condition_ids=None):
    # CRITICAL ORDERING: provenance is checked before outcomes_json is opened.
    # This keeps the 2016 unseal behind the true AS2 fresh-context gate.
    baseline_provenance = require_as2_baseline(baseline_run)

    outcome_payload = read_json(outcomes_json)
    outcome_elections = sorted(set(x["anonymous_election_id"] for x in outcome_payload.get("items", [])))
    if outcome_elections != [election_id]:
        raise ValueError(
            "calibration outcome file must contain exactly election %s; found %s" %
            (election_id, outcome_elections)
        )

    proto = read_json(experiment_manifest_path)
    cal = proto["calibration"]
    grid = cal["lambda_candidates"]
    model_condition = cal.get("primary_model_condition", "ALL_R2").upper()

    wm_path = os.path.join(env, "work_manifest.json")
    wm = read_json(wm_path)
    graph_index_path = os.path.join(graph_root, "graph_index.json")
    gi = read_json(graph_index_path)
    if gi["work_manifest_sha256"] != sha256_file(wm_path):
        raise ValueError("graph index was built from another work_manifest")

    lookup = outcome_lookup(outcome_payload)
    ids = set(experiment_condition_ids or [])
    trials = []
    best = None
    for f, w, n in itertools.product(
        grid["family"], grid["work"], grid["neighborhood"]
    ):
        lambdas = {"family": float(f), "work": float(w), "neighborhood": float(n)}
        score = _evaluate_tuple(
            wm["work_items"], env, baseline_run, graph_root, gi, lookup,
            election_id, ids, lambdas, model_condition
        )
        trial = {"lambdas": lambdas, "score": score}
        trials.append(trial)
        key = (
            score["objective"], score["party_share_rmse"],
            sum(lambdas.values()), lambdas["family"], lambdas["work"],
            lambdas["neighborhood"]
        )
        if best is None or key < best[0]:
            best = (key, trial)

    result = {
        "schema_version": "ATLAS_SOCIAL_LAMBDA_CALIBRATION_V1",
        "calibration_status": "CALIBRATED_ON_DECLARED_ELECTION_ONLY_FROZEN_FOR_HOLDOUT",
        "calibration_election_id": election_id,
        "model_condition": model_condition,
        "experiment_condition_ids": sorted(ids),
        "objective_definition": "party_share_rmse + 0.25 * turnout_rmse",
        "lambdas": best[1]["lambdas"],
        "best_score": best[1]["score"],
        "grid_size": len(trials),
        "trials": trials,
        "baseline_provenance": baseline_provenance,
        "provenance": {
            "created_unix": int(time.time()),
            "work_manifest_sha256": sha256_file(wm_path),
            "graph_index_sha256": sha256_file(graph_index_path),
            "outcomes_sha256": sha256_file(outcomes_json),
            "experiment_manifest_sha256": sha256_file(experiment_manifest_path),
        },
    }
    write_json(output_path, result, pretty=True)
    print(
        "PASS_SOCIAL_LAMBDA_FROZEN %s objective=%.6f lambdas=%s baseline=%s" %
        (
            election_id, best[1]["score"]["objective"], best[1]["lambdas"],
            baseline_provenance["baseline_class"]
        )
    )
    return result


def cli(argv=None):
    default_manifest = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "SOCIAL_EXPERIMENT_MANIFEST.json")
    )
    ap = argparse.ArgumentParser()
    ap.add_argument("env")
    ap.add_argument("baseline_run")
    ap.add_argument("graph_root")
    ap.add_argument("calibration_outcomes_json")
    ap.add_argument("calibration_election_id")
    ap.add_argument("output_json")
    ap.add_argument("--experiment-manifest", default=default_manifest)
    ap.add_argument("--experiment-condition-id", action="append", default=[])
    args = ap.parse_args(argv)
    calibrate(
        args.env, args.baseline_run, args.graph_root,
        args.calibration_outcomes_json, args.calibration_election_id,
        args.output_json, args.experiment_manifest,
        args.experiment_condition_id,
    )


if __name__ == "__main__":
    cli()
