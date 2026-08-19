# -*- coding: utf-8 -*-
"""Outcome-facing scorer for the social experiment.

This is deliberately an adapter boundary: the social graph and social runners
never import or discover outcomes.  Outcomes must be supplied explicitly after
the relevant unseal gate.

Expected outcome JSON:
{
  "items": [
    {
      "anonymous_election_id": "...",
      "anonymous_territory_id": "...",
      "condition_id": null,              # optional
      "party_shares": {"Q_01": 0.3, ...},
      "turnout": 0.48
    }
  ]
}
"""
from __future__ import division
import argparse
import math
import os

try:
    from .common import clip, normalize, read_json, read_jsonl, write_json
except ImportError:
    from common import clip, normalize, read_json, read_jsonl, write_json


EPS = 1e-12


def _js_divergence(p, q):
    p = normalize(p)
    q = normalize(q)
    keys = sorted(set(p) | set(q))
    m = {k: 0.5 * (p.get(k, EPS) + q.get(k, EPS)) for k in keys}

    def kl(a, b):
        return sum(
            max(EPS, a.get(k, EPS)) *
            math.log(max(EPS, a.get(k, EPS)) / max(EPS, b.get(k, EPS)))
            for k in keys
        )
    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def aggregate_rows(rows):
    if not rows:
        raise ValueError("cannot aggregate empty work item")
    keys = tuple(sorted(rows[0]["conditional_party_probabilities"]))
    p = {k: 0.0 for k in keys}
    turnout = 0.0
    for row in rows:
        if tuple(sorted(row["conditional_party_probabilities"])) != keys:
            raise ValueError("party set differs within work item")
        for k in keys:
            p[k] += float(row["conditional_party_probabilities"][k])
        turnout += float(row["turnout_probability"])
    n = float(len(rows))
    return {
        "party_shares": normalize({k: p[k] / n for k in keys}),
        "turnout": turnout / n,
        "rows": len(rows),
    }


def outcome_lookup(payload):
    lookup = {}
    for item in payload.get("items", []):
        e = item["anonymous_election_id"]
        t = item["anonymous_territory_id"]
        c = item.get("condition_id")
        lookup[(e, t, c)] = item
    return lookup


def _find_outcome(lookup, e, t, c):
    return lookup.get((e, t, c)) or lookup.get((e, t, None))


def score_run(run_root, condition, outcomes_payload, election_ids=None,
              experiment_condition_ids=None):
    manifest = read_json(os.path.join(run_root, "run_manifest.json"))
    lookup = outcome_lookup(outcomes_payload)
    election_ids = set(election_ids or [])
    experiment_condition_ids = set(experiment_condition_ids or [])

    records = []
    for wi in manifest["work_items"]:
        e, t, c = wi["election_id"], wi["territory_id"], wi["condition_id"]
        if election_ids and e not in election_ids:
            continue
        if experiment_condition_ids and c not in experiment_condition_ids:
            continue
        outcome = _find_outcome(lookup, e, t, c)
        if not outcome:
            continue
        out_rec = next((x for x in wi["outputs"] if x["condition"] == condition), None)
        if out_rec is None:
            continue
        rows = read_jsonl(os.path.join(run_root, out_rec["output_path"]))
        pred = aggregate_rows(rows)
        target = normalize(outcome["party_shares"])
        if set(pred["party_shares"]) != set(target):
            raise ValueError(
                "party pseudonym set mismatch for %s/%s: pred=%s target=%s" %
                (e, t, sorted(pred["party_shares"]), sorted(target))
            )

        diffs = [pred["party_shares"][k] - target[k] for k in sorted(target)]
        share_mse = sum(d * d for d in diffs) / max(1, len(diffs))
        share_mae = sum(abs(d) for d in diffs) / max(1, len(diffs))
        ce = -sum(target[k] * math.log(max(EPS, pred["party_shares"][k])) for k in target)
        turn_diff = None
        if outcome.get("turnout") is not None:
            turn_diff = pred["turnout"] - float(outcome["turnout"])
        records.append({
            "election_id": e,
            "territory_id": t,
            "condition_id": c,
            "rows": pred["rows"],
            "party_share_mse": share_mse,
            "party_share_mae": share_mae,
            "cross_entropy": ce,
            "js_divergence": _js_divergence(pred["party_shares"], target),
            "turnout_error": turn_diff,
        })

    if not records:
        raise ValueError("no scored work item matched the supplied outcomes/filters")
    n = float(len(records))
    mse = sum(r["party_share_mse"] for r in records) / n
    mae = sum(r["party_share_mae"] for r in records) / n
    ce = sum(r["cross_entropy"] for r in records) / n
    jsd = sum(r["js_divergence"] for r in records) / n
    turns = [r["turnout_error"] for r in records if r["turnout_error"] is not None]
    trmse = math.sqrt(sum(x * x for x in turns) / len(turns)) if turns else None
    tmae = sum(abs(x) for x in turns) / len(turns) if turns else None
    share_rmse = math.sqrt(mse)

    # Pre-registered scalar used only for 2016 lambda selection.
    objective = share_rmse + (0.25 * trmse if trmse is not None else 0.0)
    return {
        "schema_version": "ATLAS_SOCIAL_SCORE_V1",
        "condition": condition,
        "n_work_items": len(records),
        "party_share_rmse": share_rmse,
        "party_share_mae": mae,
        "cross_entropy": ce,
        "js_divergence": jsd,
        "turnout_rmse": trmse,
        "turnout_mae": tmae,
        "calibration_objective": objective,
        "records": records,
    }


def cli(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("run_root")
    ap.add_argument("condition")
    ap.add_argument("outcomes_json")
    ap.add_argument("--election-id", action="append", default=[])
    ap.add_argument("--experiment-condition-id", action="append", default=[])
    ap.add_argument("--output")
    args = ap.parse_args(argv)
    result = score_run(
        args.run_root, args.condition.upper(), read_json(args.outcomes_json),
        args.election_id, args.experiment_condition_id
    )
    if args.output:
        write_json(args.output, result, pretty=True)
    print(
        "SCORE %s n=%d party_rmse=%.6f turnout_rmse=%s objective=%.6f" %
        (
            result["condition"], result["n_work_items"],
            result["party_share_rmse"],
            "NA" if result["turnout_rmse"] is None else "%.6f" % result["turnout_rmse"],
            result["calibration_objective"],
        )
    )


if __name__ == "__main__":
    cli()
