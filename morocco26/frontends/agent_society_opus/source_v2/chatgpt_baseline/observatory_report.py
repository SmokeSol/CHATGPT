from __future__ import annotations

from observatory_base import *
from observatory_evidence import *
from observatory_selection import *
from observatory_exec import *
from observatory_transforms import *
from observatory_causal import *

def deliberation_rows_for_task(output_root: pathlib.Path, task: R.FrozenTask) -> list[dict[str, Any]]:
    path = deliberation_output_path(output_root, task)
    return load_jsonl(path) if path.is_file() else []


def build_observatory_report(
    *,
    tasks: Sequence[R.FrozenTask],
    output_root: pathlib.Path,
    decisions_by_task: Mapping[str, Sequence[Mapping[str, Any]]],
    scope: str,
    cf_panels: Sequence[str],
    include_counterfactuals: bool,
) -> dict[str, Any]:
    deliberations = []
    counters = []
    for task in tasks:
        deliberations.extend(deliberation_rows_for_task(output_root, task))
        if include_counterfactuals:
            selected = select_counterfactual_panel(task, decisions_by_task[task.task_id], cf_panels)
            for item in selected:
                evaluation = evaluate_counterfactuals(task=task, selected=item, output_root=output_root)
                if evaluation:
                    counters.append(evaluation)
    driver_counts = collections.Counter()
    direction_counts = collections.Counter()
    transition_counts = collections.Counter()
    confidence_counts = collections.Counter()
    conflict_counts = collections.Counter()
    lever_counts = collections.Counter()
    for row in deliberations:
        transition_counts[row["transition_type"]] += 1
        confidence_counts[row["self_reported_confidence"]] += 1
        conflict = row["central_conflict"]
        conflict_counts[tuple(sorted((conflict["factor_a"], conflict["factor_b"])))] += 1
        lever_counts[row["minimum_flip_hypothesis"]["lever"]] += 1
        for driver in row["drivers"]:
            driver_counts[driver["factor"]] += 1
            direction_counts[driver["direction"]] += 1
    counter_status = collections.Counter(item["causal_support_status"] for item in counters)
    return {
        "schema_version": "ATLAS_G0_DELIBERATION_OBSERVATORY_REPORT_V1",
        "status": "OBSERVATORY_PARTIAL_OR_STARTUP_COMPLETE",
        "generated_at": R.utc_now(),
        "baseline_id": BASELINE_ID,
        "model_contract": {
            "decision": [DECISION_MODEL, DECISION_REASONING],
            "deliberation": [DELIBERATION_MODEL, DELIBERATION_REASONING],
            "counterfactual": [COUNTERFACTUAL_MODEL, COUNTERFACTUAL_REASONING],
        },
        "scope": scope,
        "work_items": len(tasks),
        "deliberation_rows": len(deliberations),
        "counterfactual_agents": len(counters),
        "methodological_labels": {
            "deliberation": "MODEL_GENERATED_OBSERVABLE_EXPLANATION_NOT_PRIVATE_CHAIN_OF_THOUGHT",
            "counterfactual": "SYNTHETIC_PACKET_PERTURBATION_DIAGNOSTIC",
            "predictive_validity": "NOT_ESTABLISHED_BEFORE_BLIND_HISTORICAL_SCORING",
        },
        "aggregates": {
            "drivers": dict(driver_counts.most_common()),
            "directions": dict(direction_counts.most_common()),
            "transitions": dict(transition_counts.most_common()),
            "self_reported_confidence": dict(confidence_counts.most_common()),
            "central_conflicts": {
                "|".join(key): value for key, value in conflict_counts.most_common()
            },
            "minimum_flip_levers": dict(lever_counts.most_common()),
            "counterfactual_support": dict(counter_status.most_common()),
            "placebo_stable_share": (
                sum(1 for item in counters if item["placebo_stable"]) / len(counters)
                if counters else None
            ),
        },
        "deliberations": deliberations,
        "counterfactual_evaluations": counters,
    }


def sum_usage(results: Sequence[InvocationResult]) -> dict[str, int]:
    out: dict[str, int] = {}
    for result in results:
        for key, value in (result.usage or {}).items():
            out[key] = out.get(key, 0) + int(value)
    return out


def write_state(
    *,
    output_root: pathlib.Path,
    bundle_sha256: str,
    decision_root: pathlib.Path,
    tasks: Sequence[R.FrozenTask],
    scope: str,
    cf_panels: Sequence[str],
    deliberation_results: Sequence[InvocationResult],
    counterfactual_results: Sequence[InvocationResult],
    report: Mapping[str, Any],
    dry_run: bool,
) -> None:
    failures = [
        result
        for result in list(deliberation_results) + list(counterfactual_results)
        if result.status.startswith("FAILED")
    ]
    limited = any(
        result.rate_limited
        for result in list(deliberation_results) + list(counterfactual_results)
    )
    status = (
        "DRY_RUN_READY"
        if dry_run
        else "PAUSED_USAGE_LIMIT"
        if limited
        else "FAILED"
        if failures
        else "PASS_STARTUP_DELIBERATION_OBSERVATORY_COMPLETE"
        if len(tasks) == 32 and scope == "all"
        else "PASS_PARTIAL_RESUMABLE_OBSERVATORY"
    )
    state = {
        "schema_version": "ATLAS_G0_DELIBERATION_OBSERVATORY_STATE_V1",
        "protocol_id": PROTOCOL_ID,
        "status": status,
        "generated_at": R.utc_now(),
        "baseline_id": BASELINE_ID,
        "bundle_sha256": bundle_sha256,
        "decision_run_state_sha256": R.sha256_file(decision_root / "run_state.json"),
        "work_items_selected": len(tasks),
        "scope": scope,
        "deliberation_rows": report["deliberation_rows"],
        "counterfactual_agents": report["counterfactual_agents"],
        "counterfactual_panels": list(cf_panels),
        "models": {
            "decision": {"model": DECISION_MODEL, "reasoning": DECISION_REASONING},
            "deliberation": {"model": DELIBERATION_MODEL, "reasoning": DELIBERATION_REASONING},
            "counterfactual": {"model": COUNTERFACTUAL_MODEL, "reasoning": COUNTERFACTUAL_REASONING},
        },
        "auth_mode": "CHATGPT_MANAGED_CODEX_LOGIN",
        "api_key_used": False,
        "private_chain_of_thought_requested": False,
        "observable_deliberation_requested": True,
        "outcomes_opened": False,
        "latest_results": [dataclasses.asdict(result) for result in list(deliberation_results) + list(counterfactual_results)],
        "latest_usage": sum_usage(list(deliberation_results) + list(counterfactual_results)),
    }
    R.atomic_write_json(output_root / "observatory_state.json", state)
    R.atomic_write_json(output_root / "observatory_report.json", report)
