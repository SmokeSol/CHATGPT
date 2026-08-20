#!/usr/bin/env python3
"""CLI for the ATLAS G0 deliberation and counterfactual observatory."""
from __future__ import annotations

import pathlib
import sys
HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from observatory_base import *
from observatory_evidence import *
from observatory_selection import *
from observatory_exec import *
from observatory_transforms import *
from observatory_causal import *
from observatory_report import *

def select_tasks(
    tasks: Sequence[R.FrozenTask], start: int, limit: int | None, regex: str | None
) -> list[R.FrozenTask]:
    chosen = list(tasks)
    if regex:
        pattern = re.compile(regex)
        chosen = [task for task in chosen if pattern.search(task.task_id)]
    chosen = chosen[start:]
    if limit is not None:
        chosen = chosen[:limit]
    return chosen


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Generate observable deliberations and validate them with counterfactual packet re-runs."
    )
    ap.add_argument("--bundle", required=True, type=pathlib.Path)
    ap.add_argument("--decision-run", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--scope", choices=("all", "panel"), default="panel")
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--task-regex")
    ap.add_argument("--counterfactual-suite", choices=("none", "core"), default="none")
    ap.add_argument(
        "--counterfactual-panels",
        default="SWING",
        help="comma-separated subset of HASH_ANCHOR,SWING,TURNOUT_PIVOT,STRONGEST_SWITCH",
    )
    ap.add_argument("--codex-bin", default="codex")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--timeout-seconds", type=int, default=3600)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.workers < 1 or args.workers > 4:
        raise ObservatoryError("--workers must be between 1 and 4")
    if args.max_attempts not in (1, 2):
        raise ObservatoryError("--max-attempts must be 1 or 2")
    cf_panels = tuple(
        value.strip() for value in args.counterfactual_panels.split(",") if value.strip()
    )
    if any(value not in PANEL_NAMES for value in cf_panels):
        raise ObservatoryError("invalid --counterfactual-panels")

    codex_version = "DRY_RUN_NO_CODEX"
    if not args.dry_run:
        codex_version = R.check_codex(args.codex_bin)

    output_root = args.output.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    extracted, bundle_sha256 = R.extract_bundle(
        args.bundle, output_root / "_bundle_cache"
    )
    env_root = R.find_environment_root(extracted)
    decision_prompt_path, row_schema_path = R.discover_prompt_and_schema(env_root)
    decision_prompt = R.read_text(decision_prompt_path)
    row_schema = R.read_json(row_schema_path)
    tasks, _ = R.discover_tasks(env_root)
    selected_tasks = select_tasks(tasks, args.start, args.limit, args.task_regex)
    if not selected_tasks:
        raise ObservatoryError("selected work-item set is empty")
    if args.scope == "all" and any(len(task.expected_rows) != 32 for task in selected_tasks):
        raise ObservatoryError("startup all scope requires 32-row work items")

    decision_root = args.decision_run.expanduser().resolve()
    decisions_by_task = validate_decision_run(
        decision_root, tasks, row_schema, selected_tasks
    )
    deliberation_prompt_path = HERE / "DELIBERATION_PROMPT_V1.md"
    deliberation_schema_path = HERE / "DELIBERATION_OUTPUT_SCHEMA_V1.json"
    if not deliberation_prompt_path.is_file() or not deliberation_schema_path.is_file():
        raise ObservatoryError("deliberation prompt/schema missing next to runner")
    deliberation_prompt = deliberation_prompt_path.read_text(encoding="utf-8")
    base_schema = load_deliberation_base_schema(deliberation_schema_path)

    R.atomic_write_json(
        output_root / "observatory_preflight.json",
        {
            "schema_version": "ATLAS_G0_DELIBERATION_PREFLIGHT_V1",
            "protocol_id": PROTOCOL_ID,
            "generated_at": R.utc_now(),
            "codex_version": codex_version,
            "bundle_sha256": bundle_sha256,
            "environment_root": str(env_root),
            "decision_run_state_sha256": R.sha256_file(decision_root / "run_state.json"),
            "decision_prompt_sha256": R.sha256_file(decision_prompt_path),
            "decision_schema_sha256": R.sha256_file(row_schema_path),
            "deliberation_prompt_sha256": R.sha256_file(deliberation_prompt_path),
            "deliberation_schema_sha256": R.sha256_file(deliberation_schema_path),
            "work_items_selected": len(selected_tasks),
            "scope": args.scope,
            "counterfactual_suite": args.counterfactual_suite,
            "counterfactual_panels": list(cf_panels),
            "outcomes_opened": False,
            "private_chain_of_thought_requested": False,
        },
    )

    print(
        f"{PROTOCOL_ID}: {len(selected_tasks)} work items; scope={args.scope}; "
        f"counterfactuals={args.counterfactual_suite}; workers={args.workers}"
    )

    stop = threading.Event()
    deliberation_results: list[InvocationResult] = []

    def deliberation_invoker(task: R.FrozenTask) -> InvocationResult:
        if stop.is_set():
            return InvocationResult(task.task_id, "L0_OBSERVABLE_DELIBERATION", "NOT_STARTED_AFTER_PAUSE", "", 0)
        result = run_deliberation_task(
            task=task,
            decisions=decisions_by_task[task.task_id],
            scope=args.scope,
            prompt=deliberation_prompt,
            base_schema=base_schema,
            output_root=output_root,
            codex_bin=args.codex_bin,
            model=DELIBERATION_MODEL,
            reasoning=DELIBERATION_REASONING,
            max_attempts=args.max_attempts,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
        if result.rate_limited:
            stop.set()
        with PRINT_LOCK:
            print(f"[{result.status}] DELIBERATION {task.task_id} rows={result.rows}", flush=True)
        return result

    if args.workers == 1:
        for task in selected_tasks:
            result = deliberation_invoker(task)
            deliberation_results.append(result)
            if result.rate_limited:
                break
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = [pool.submit(deliberation_invoker, task) for task in selected_tasks]
            for future in concurrent.futures.as_completed(futures):
                deliberation_results.append(future.result())

    if any(result.status.startswith("FAILED") for result in deliberation_results):
        report = build_observatory_report(
            tasks=selected_tasks,
            output_root=output_root,
            decisions_by_task=decisions_by_task,
            scope=args.scope,
            cf_panels=cf_panels,
            include_counterfactuals=False,
        )
        write_state(
            output_root=output_root,
            bundle_sha256=bundle_sha256,
            decision_root=decision_root,
            tasks=selected_tasks,
            scope=args.scope,
            cf_panels=cf_panels,
            deliberation_results=deliberation_results,
            counterfactual_results=[],
            report=report,
            dry_run=args.dry_run,
        )
        return 2

    counterfactual_results: list[InvocationResult] = []
    if args.counterfactual_suite == "core" and not stop.is_set():
        jobs = []
        for task in selected_tasks:
            selected = select_counterfactual_panel(
                task, decisions_by_task[task.task_id], cf_panels
            )
            for voter in selected:
                for scenario in SCENARIOS:
                    jobs.append((task, voter, scenario))

        def cf_invoker(job) -> InvocationResult:
            task, voter, scenario = job
            if stop.is_set():
                return InvocationResult(task.task_id, "CF_BEHAVIOURAL_ABLATION", "NOT_STARTED_AFTER_PAUSE", "", 0)
            result = run_counterfactual(
                original_task=task,
                selected=voter,
                scenario=scenario,
                frozen_decision_prompt=decision_prompt,
                row_schema=row_schema,
                output_root=output_root,
                codex_bin=args.codex_bin,
                model=COUNTERFACTUAL_MODEL,
                reasoning=COUNTERFACTUAL_REASONING,
                max_attempts=args.max_attempts,
                timeout_seconds=args.timeout_seconds,
                dry_run=args.dry_run,
            )
            if result.rate_limited:
                stop.set()
            with PRINT_LOCK:
                print(
                    f"[{result.status}] CF {task.task_id} {voter.archetype_id} {scenario}",
                    flush=True,
                )
            return result

        if args.workers == 1:
            for job in jobs:
                result = cf_invoker(job)
                counterfactual_results.append(result)
                if result.rate_limited:
                    break
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = [pool.submit(cf_invoker, job) for job in jobs]
                for future in concurrent.futures.as_completed(futures):
                    counterfactual_results.append(future.result())

    include_cf = args.counterfactual_suite == "core" and not args.dry_run
    report = build_observatory_report(
        tasks=selected_tasks,
        output_root=output_root,
        decisions_by_task=decisions_by_task,
        scope=args.scope,
        cf_panels=cf_panels,
        include_counterfactuals=include_cf,
    )
    write_state(
        output_root=output_root,
        bundle_sha256=bundle_sha256,
        decision_root=decision_root,
        tasks=selected_tasks,
        scope=args.scope,
        cf_panels=cf_panels,
        deliberation_results=deliberation_results,
        counterfactual_results=counterfactual_results,
        report=report,
        dry_run=args.dry_run,
    )
    if any(result.rate_limited for result in deliberation_results + counterfactual_results):
        print("PAUSED_CHATGPT_USAGE_LIMIT: rerun the identical command; valid artifacts are skipped.", file=sys.stderr)
        return R.EXIT_PAUSED
    failures = [
        result
        for result in deliberation_results + counterfactual_results
        if result.status.startswith("FAILED")
    ]
    if failures:
        print(f"FAILED_OBSERVATORY_JOBS={len(failures)}", file=sys.stderr)
        return 2
    if len(selected_tasks) == 32 and args.scope == "all":
        print("PASS_STARTUP_32_DELIBERATION_OBSERVATORY_COMPLETE")
    else:
        print("PASS_PARTIAL_RESUMABLE_DELIBERATION_OBSERVATORY")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ObservatoryError, R.RunnerError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
