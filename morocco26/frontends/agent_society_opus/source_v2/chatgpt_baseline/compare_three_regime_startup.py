#!/usr/bin/env python3
"""Compare three-regime startup runs without reading historical outcomes."""
from __future__ import annotations

import argparse
import json
import math
import pathlib
import sys
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
SCRIPTS = REPO_ROOT / "morocco26" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from three_regime_core import (  # noqa: E402
    GOAL_ID,
    REGIME_BLIND,
    REGIME_HISTORICAL,
    REGIME_NAMED,
    REGIME_NAMED_TWIN,
    ThreeRegimeError,
    iter_jsonl,
    read_json,
    summarize_output_rows,
    utc_now,
    write_json,
)


def row_key(row: Mapping[str, Any]) -> tuple[str, ...]:
    return (
        str(row.get("anonymous_election_id") or row.get("election_id") or ""),
        str(row.get("anonymous_territory_id") or row.get("territory_id") or ""),
        str(row.get("condition_id") or ""),
        str(row.get("batch_id") or ""),
        str(row.get("weighted_archetype_id") or row.get("archetype_id") or ""),
    )


def load_run(root: pathlib.Path, expected_regime: str | None = None) -> dict[tuple[str, ...], dict[str, Any]]:
    root = root.expanduser().resolve()
    state_path = root / "run_state.json"
    if not state_path.is_file():
        raise ThreeRegimeError(f"run_state.json missing under {root}")
    state = read_json(state_path)
    if state.get("target_outcomes_opened") is not False:
        raise ThreeRegimeError(f"run does not certify sealed outcomes: {root}")
    metadata = state.get("three_regime") or {}
    if expected_regime is not None and metadata.get("regime") != expected_regime:
        if expected_regime == REGIME_BLIND and not metadata:
            pass  # pre-V6 blind control run, registered separately
        else:
            raise ThreeRegimeError(
                f"run regime {metadata.get('regime')!r} != {expected_regime!r}"
            )
    files = sorted((root / "outputs").rglob("*.jsonl"))
    files = [path for path in files if "all_outputs" not in path.name]
    if not files:
        raise ThreeRegimeError(f"no per-work-item outputs found under {root}")
    rows: dict[tuple[str, ...], dict[str, Any]] = {}
    for path in files:
        for row in iter_jsonl(path):
            key = row_key(row)
            if any(not item for item in key):
                raise ThreeRegimeError(f"output row identity incomplete: {path}")
            if key in rows:
                raise ThreeRegimeError(f"duplicate output row identity: {key}")
            rows[key] = row
    return rows


def top_two(probabilities: Mapping[str, Any]) -> tuple[str, float, str, float]:
    ordered = sorted(
        ((str(key), float(value)) for key, value in probabilities.items()),
        key=lambda item: (-item[1], item[0]),
    )
    if len(ordered) < 2:
        raise ThreeRegimeError("party simplex has fewer than two entries")
    return ordered[0][0], ordered[0][1], ordered[1][0], ordered[1][1]


def js_divergence(left: Mapping[str, Any], right: Mapping[str, Any]) -> float:
    keys = sorted(set(left) | set(right))
    p = [max(1e-15, float(left.get(key, 0.0))) for key in keys]
    q = [max(1e-15, float(right.get(key, 0.0))) for key in keys]
    ps, qs = sum(p), sum(q)
    p = [value / ps for value in p]
    q = [value / qs for value in q]
    m = [(a + b) / 2 for a, b in zip(p, q)]

    def kl(a, b):
        return sum(x * math.log(x / y, 2) for x, y in zip(a, b))

    return 0.5 * kl(p, m) + 0.5 * kl(q, m)


def paired_historical(
    blind: Mapping[tuple[str, ...], Mapping[str, Any]],
    rich: Mapping[tuple[str, ...], Mapping[str, Any]],
) -> dict[str, Any]:
    if set(blind) != set(rich):
        missing_left = sorted(set(rich) - set(blind))[:5]
        missing_right = sorted(set(blind) - set(rich))[:5]
        raise ThreeRegimeError(
            f"historical paired keys differ: blind_missing={missing_left}, rich_missing={missing_right}"
        )
    deltas = []
    top_changes = 0
    turnout_deltas = []
    margin_deltas = []
    for key in sorted(blind):
        left = blind[key]
        right = rich[key]
        lp = left["conditional_party_probabilities"]
        rp = right["conditional_party_probabilities"]
        if set(lp) != set(rp):
            raise ThreeRegimeError(f"historical party panel changed at {key}")
        ltop, ltp, _, lrp = top_two(lp)
        rtop, rtp, _, rrp = top_two(rp)
        top_changes += int(ltop != rtop)
        turnout_deltas.append(float(right["turnout_probability"]) - float(left["turnout_probability"]))
        margin_deltas.append((rtp - rrp) - (ltp - lrp))
        deltas.append(js_divergence(lp, rp))
    count = len(deltas)
    return {
        "comparison_id": "BLIND_VS_HISTORICAL_SEMIBLIND_RICH",
        "rows": count,
        "same_work_items_and_voters": True,
        "top_choice_change_rows": top_changes,
        "top_choice_change_rate": top_changes / count,
        "mean_turnout_delta": sum(turnout_deltas) / count,
        "mean_top_two_margin_delta": sum(margin_deltas) / count,
        "mean_party_js_divergence_bits": sum(deltas) / count,
        "interpretation": "prompt-framing/attention diagnostic under unchanged historical facts",
        "causal_claim_allowed": False,
    }


def remap_named_twin_row(
    row: Mapping[str, Any],
    party_map: Mapping[str, str],
) -> dict[str, Any]:
    result = dict(row)
    probabilities = row.get("conditional_party_probabilities") or {}
    inverse = {str(twin): str(named) for named, twin in party_map.items()}
    if set(map(str, probabilities)) != set(inverse):
        raise ThreeRegimeError("named twin party panel does not match pair map")
    result["conditional_party_probabilities"] = {
        inverse[str(twin)]: value for twin, value in probabilities.items()
    }
    return result


def paired_named(
    named: Mapping[tuple[str, ...], Mapping[str, Any]],
    twin: Mapping[tuple[str, ...], Mapping[str, Any]],
    pair_map: Mapping[str, Any],
) -> dict[str, Any]:
    territory_map = {str(k): str(v) for k, v in (pair_map.get("territory_map") or {}).items()}
    party_map = {str(k): str(v) for k, v in (pair_map.get("party_map") or {}).items()}
    if not territory_map or not party_map:
        raise ThreeRegimeError("named pair map lacks territory_map or party_map")
    twin_by_named: dict[tuple[str, ...], Mapping[str, Any]] = {}
    inverse_territory = {twin_id: named_id for named_id, twin_id in territory_map.items()}
    for key, row in twin.items():
        election, territory, condition, batch, archetype = key
        named_territory = inverse_territory.get(territory)
        if named_territory is None:
            raise ThreeRegimeError(f"twin territory absent from pair map: {territory}")
        named_key = (election, named_territory, condition, batch, archetype)
        twin_by_named[named_key] = remap_named_twin_row(row, party_map)
    if set(named) != set(twin_by_named):
        raise ThreeRegimeError("named and pseudonymized-twin paired rows differ")
    top_changes = 0
    turnout_deltas = []
    divergences = []
    for key in sorted(named):
        left = named[key]
        right = twin_by_named[key]
        lp = left["conditional_party_probabilities"]
        rp = right["conditional_party_probabilities"]
        ltop, *_ = top_two(lp)
        rtop, *_ = top_two(rp)
        top_changes += int(ltop != rtop)
        turnout_deltas.append(float(left["turnout_probability"]) - float(right["turnout_probability"]))
        divergences.append(js_divergence(lp, rp))
    count = len(divergences)
    return {
        "comparison_id": "NAMED_2026_VS_PSEUDONYMIZED_TWIN",
        "rows": count,
        "same_2026_facts_except_identity_labels": True,
        "top_choice_change_rows": top_changes,
        "top_choice_change_rate": top_changes / count,
        "mean_named_minus_twin_turnout_delta": sum(turnout_deltas) / count,
        "mean_party_js_divergence_bits": sum(divergences) / count,
        "interpretation": "within-2026 identity-label sensitivity diagnostic",
        "causal_claim_allowed": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind-run", type=pathlib.Path, required=True)
    parser.add_argument("--historical-rich-run", type=pathlib.Path, required=True)
    parser.add_argument("--named-run", type=pathlib.Path)
    parser.add_argument("--named-twin-run", type=pathlib.Path)
    parser.add_argument("--named-pair-map", type=pathlib.Path)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    args = parser.parse_args(argv)

    blind = load_run(args.blind_run, REGIME_BLIND)
    rich = load_run(args.historical_rich_run, REGIME_HISTORICAL)
    report: dict[str, Any] = {
        "schema_version": "1.0",
        "goal_id": GOAL_ID,
        "status": "PASS_THREE_REGIME_STARTUP_COMPARISON_READY",
        "generated_at": utc_now(),
        "historical_blind_summary": summarize_output_rows(list(blind.values())),
        "historical_semiblind_rich_summary": summarize_output_rows(list(rich.values())),
        "historical_paired_comparison": paired_historical(blind, rich),
        "named_2026_summary": None,
        "named_twin_summary": None,
        "named_paired_comparison": None,
        "cross_era_comparison": {
            "status": "DESCRIPTIVE_ONLY",
            "causal_claim_allowed": False,
            "reason": "historical and 2026 contexts differ in election, candidates, information set and time",
        },
        "target_outcomes_read": False,
    }
    named_args = (args.named_run, args.named_twin_run, args.named_pair_map)
    if any(value is not None for value in named_args):
        if not all(value is not None for value in named_args):
            raise ThreeRegimeError(
                "--named-run, --named-twin-run and --named-pair-map must be supplied together"
            )
        named = load_run(args.named_run, REGIME_NAMED)
        twin = load_run(args.named_twin_run, REGIME_NAMED_TWIN)
        pair_map = read_json(args.named_pair_map)
        report["named_2026_summary"] = summarize_output_rows(list(named.values()))
        report["named_twin_summary"] = summarize_output_rows(list(twin.values()))
        report["named_paired_comparison"] = paired_named(named, twin, pair_map)
    write_json(args.output.expanduser().resolve(), report)
    print(report["status"])
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ThreeRegimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
