from __future__ import annotations

from observatory_base import *
from observatory_evidence import *
from observatory_selection import *
from observatory_exec import *
from observatory_transforms import *

def run_counterfactual(
    *,
    original_task: R.FrozenTask,
    selected: SelectedVoter,
    scenario: str,
    frozen_decision_prompt: str,
    row_schema: Mapping[str, Any],
    output_root: pathlib.Path,
    codex_bin: str,
    model: str,
    reasoning: str,
    max_attempts: int,
    timeout_seconds: int,
    dry_run: bool,
) -> InvocationResult:
    cf_task, manifest = apply_scenario(task=original_task, selected=selected, scenario=scenario)
    schema = R.wrapper_schema(row_schema, cf_task)
    context = counterfactual_context(frozen_decision_prompt, row_schema, cf_task, manifest)
    output = counterfactual_output_path(output_root, cf_task)
    run_dir = output_root / "_observatory_runs" / "counterfactual" / cf_task.task_id
    R.atomic_write_json(run_dir / "transform_manifest.json", manifest)
    return invoke_structured(
        task_id=cf_task.task_id,
        phase="CF_BEHAVIOURAL_ABLATION",
        context=context,
        schema=schema,
        output_path=output,
        run_dir=run_dir,
        validator=lambda value: R.validate_rows(value, cf_task, row_schema),
        codex_bin=codex_bin,
        model=model,
        reasoning=reasoning,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
    )


def js_divergence(p: Mapping[str, float], q: Mapping[str, float]) -> float:
    keys = sorted(set(p) | set(q))
    eps = 1e-15
    pv = [max(eps, float(p.get(key, 0.0))) for key in keys]
    qv = [max(eps, float(q.get(key, 0.0))) for key in keys]
    ps = sum(pv)
    qs = sum(qv)
    pv = [value / ps for value in pv]
    qv = [value / qs for value in qv]
    mv = [(a + b) / 2.0 for a, b in zip(pv, qv)]

    def kl(a, b):
        return sum(x * math.log(x / y, 2) for x, y in zip(a, b))

    return 0.5 * kl(pv, mv) + 0.5 * kl(qv, mv)


def scenario_output_path(
    output_root: pathlib.Path,
    task: R.FrozenTask,
    archetype_id: str,
    scenario: str,
) -> pathlib.Path:
    return (
        output_root
        / "counterfactuals"
        / task.election_id
        / task.condition_id
        / task.territory_id
        / task.batch_id
        / archetype_id
        / (scenario + ".jsonl")
    )


def evaluate_counterfactuals(
    *,
    task: R.FrozenTask,
    selected: SelectedVoter,
    output_root: pathlib.Path,
) -> dict[str, Any] | None:
    original = selected.decision
    top, top_p, runner, runner_p = top_two(original)
    scenarios = {}
    for scenario in SCENARIOS:
        path = scenario_output_path(output_root, task, selected.archetype_id, scenario)
        if not path.is_file():
            return None
        rows = load_jsonl(path)
        if len(rows) != 1:
            raise ObservatoryError(f"counterfactual output row count invalid: {path}")
        row = rows[0]
        probs = {str(k): float(v) for k, v in row["conditional_party_probabilities"].items()}
        cf_top, cf_top_p, _, _ = top_two(row)
        scenarios[scenario] = {
            "top_party_id": cf_top,
            "top_party_probability": cf_top_p,
            "original_top_delta": probs[top] - top_p,
            "runner_up_delta": probs[runner] - runner_p,
            "turnout_delta": float(row["turnout_probability"]) - float(original["turnout_probability"]),
            "party_jsd": js_divergence(original["conditional_party_probabilities"], probs),
            "flipped_to_runner_up": cf_top == runner,
            "output_sha256": R.sha256_file(path),
        }
    placebo = scenarios["NONINFORMATIVE_METADATA_PLACEBO"]
    placebo_stable = (
        placebo["party_jsd"] <= 0.015
        and abs(placebo["turnout_delta"]) <= 0.02
    )
    substantive = [scenario for scenario in SCENARIOS if "PLACEBO" not in scenario]
    best = max(
        substantive,
        key=lambda scenario: (
            scenarios[scenario]["runner_up_delta"],
            scenarios[scenario]["flipped_to_runner_up"],
            scenario,
        ),
    )
    best_delta = scenarios[best]["runner_up_delta"]
    if not placebo_stable:
        support = "UNSAFE_PLACEBO_SENSITIVE"
    elif scenarios[best]["flipped_to_runner_up"] or best_delta >= 0.05:
        support = "SUPPORTED"
    elif best_delta >= 0.02:
        support = "PARTIAL"
    elif best_delta <= -0.02:
        support = "REFUTED_DIRECTION"
    else:
        support = "NOT_SUPPORTED"
    return {
        "task_id": task.task_id,
        "archetype_id": selected.archetype_id,
        "panel": selected.panel,
        "D0_top_party_id": top,
        "D0_runner_up_party_id": runner,
        "D0_margin": top_p - runner_p,
        "placebo_stable": placebo_stable,
        "best_flip_scenario": best,
        "best_runner_up_delta": best_delta,
        "causal_support_status": support,
        "scenarios": scenarios,
    }
