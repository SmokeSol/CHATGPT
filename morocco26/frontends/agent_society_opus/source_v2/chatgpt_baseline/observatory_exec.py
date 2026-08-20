from __future__ import annotations

from observatory_base import *
from observatory_evidence import *
from observatory_selection import *

def codex_command(
    *,
    codex_bin: str,
    model: str,
    reasoning: str,
    schema_path: pathlib.Path,
    final_path: pathlib.Path,
    phase: str,
) -> list[str]:
    return [
        codex_bin,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--ignore-rules",
        "--skip-git-repo-check",
        "--sandbox",
        "read-only",
        "--json",
        "--model",
        model,
        "--output-schema",
        str(schema_path),
        "--output-last-message",
        str(final_path),
        "-c",
        'forced_login_method="chatgpt"',
        "-c",
        'web_search="disabled"',
        "-c",
        'approval_policy="never"',
        "-c",
        'features.apps=false',
        "-c",
        'features.multi_agent=false',
        "-c",
        'features.shell_tool=false',
        "-c",
        'features.memories=false',
        "-c",
        'features.hooks=false',
        "-c",
        'features.goals=false',
        "-c",
        'history.persistence="none"',
        "-c",
        f'model_reasoning_effort="{reasoning}"',
        (
            f"Execute the ATLAS {phase} structured task from the piped context. "
            "Do not use tools, files, network access, memory, hidden chain-of-thought disclosure, "
            "or outside information. Return only the schema-valid final object."
        ),
    ]


def invoke_structured(
    *,
    task_id: str,
    phase: str,
    context: str,
    schema: Mapping[str, Any],
    output_path: pathlib.Path,
    run_dir: pathlib.Path,
    validator,
    codex_bin: str,
    model: str,
    reasoning: str,
    max_attempts: int,
    timeout_seconds: int,
    dry_run: bool,
) -> InvocationResult:
    if output_path.is_file():
        try:
            existing = load_jsonl(output_path)
            validated = validator({"rows": existing})
            if len(validated) == len(existing):
                return InvocationResult(
                    task_id=task_id,
                    phase=phase,
                    status="ALREADY_VALID",
                    output_path=str(output_path),
                    attempts=0,
                    rows=len(existing),
                    output_sha256=R.sha256_file(output_path),
                )
        except Exception:
            pass

    run_dir.mkdir(parents=True, exist_ok=True)
    schema_path = run_dir / "transport_schema.json"
    R.atomic_write_json(schema_path, schema)
    context_hash = R.sha256_bytes(context.encode("utf-8"))
    if dry_run:
        R.atomic_write_json(
            run_dir / "dry_run.json",
            {
                "protocol_id": PROTOCOL_ID,
                "phase": phase,
                "task_id": task_id,
                "context_sha256": context_hash,
                "schema_sha256": R.sha256_file(schema_path),
                "output_path": str(output_path),
            },
        )
        return InvocationResult(task_id, phase, "DRY_RUN_VALIDATED", str(output_path), 0)

    aggregate_usage: dict[str, int] = {}
    last_error = "unknown failure"
    for attempt in range(1, max_attempts + 1):
        attempt_dir = run_dir / f"attempt_{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        final_path = attempt_dir / "final.json"
        events_path = attempt_dir / "events.jsonl"
        stderr_path = attempt_dir / "stderr.txt"
        command = codex_command(
            codex_bin=codex_bin,
            model=model,
            reasoning=reasoning,
            schema_path=schema_path,
            final_path=final_path,
            phase=phase,
        )
        R.atomic_write_json(
            attempt_dir / "invocation.json",
            {
                "protocol_id": PROTOCOL_ID,
                "phase": phase,
                "task_id": task_id,
                "attempt": attempt,
                "started_at": R.utc_now(),
                "model": model,
                "reasoning": reasoning,
                "context_sha256": context_hash,
                "command_without_credentials": command,
            },
        )
        empty = attempt_dir / "empty_read_only_workdir"
        empty.mkdir(exist_ok=True)
        try:
            proc = subprocess.run(
                command,
                input=context,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=empty,
                timeout=timeout_seconds,
                check=False,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"OPENAI_API_KEY", "CODEX_API_KEY"}
                },
            )
        except subprocess.TimeoutExpired as exc:
            R.atomic_write(stderr_path, (str(exc) + "\n").encode())
            return InvocationResult(
                task_id, phase, "FAILED_TRANSPORT_NO_RETRY", str(output_path), attempt,
                error=f"timeout after {timeout_seconds}s"
            )
        R.atomic_write(events_path, proc.stdout.encode("utf-8", errors="replace"))
        R.atomic_write(stderr_path, proc.stderr.encode("utf-8", errors="replace"))
        for key, value in R.parse_usage(events_path).items():
            aggregate_usage[key] = aggregate_usage.get(key, 0) + value
        combined = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0:
            limited = any(marker in combined.lower() for marker in RATE_LIMIT_MARKERS)
            return InvocationResult(
                task_id, phase,
                "PAUSED_USAGE_LIMIT" if limited else "FAILED_TRANSPORT_NO_RETRY",
                str(output_path), attempt,
                usage=aggregate_usage,
                error=f"codex exit {proc.returncode}",
                rate_limited=limited,
            )
        violations = R.event_tool_violations(events_path)
        if violations:
            return InvocationResult(
                task_id, phase, "FAILED_EXECUTION_CONTRACT_NO_RETRY", str(output_path), attempt,
                usage=aggregate_usage, error="forbidden tool events: " + ",".join(violations)
            )
        if not final_path.is_file():
            return InvocationResult(
                task_id, phase, "FAILED_TRANSPORT_NO_RETRY", str(output_path), attempt,
                usage=aggregate_usage, error="missing final output"
            )
        try:
            value = load_json(final_path)
            rows = validator(value)
        except Exception as exc:
            last_error = f"schema-invalid output: {exc}"
            continue
        R.atomic_write_jsonl(output_path, rows)
        meta = {
            "schema_version": "ATLAS_G0_OBSERVATORY_TASK_META_V1",
            "protocol_id": PROTOCOL_ID,
            "phase": phase,
            "task_id": task_id,
            "status": "VALIDATED",
            "model": model,
            "reasoning": reasoning,
            "fresh_context": True,
            "codex_ephemeral": True,
            "chatgpt_managed_auth_required": True,
            "attempts": attempt,
            "retry_semantic_feedback": False,
            "context_sha256": context_hash,
            "schema_sha256": R.sha256_file(schema_path),
            "output_sha256": R.sha256_file(output_path),
            "rows": len(rows),
            "usage": aggregate_usage,
            "validated_at": R.utc_now(),
            "forbidden_tool_events": [],
        }
        R.atomic_write_json(output_path.with_suffix(output_path.suffix + ".meta.json"), meta)
        return InvocationResult(
            task_id, phase, "VALIDATED", str(output_path), attempt,
            rows=len(rows), output_sha256=meta["output_sha256"], usage=aggregate_usage
        )
    return InvocationResult(
        task_id, phase, "FAILED", str(output_path), max_attempts,
        usage=aggregate_usage, error=last_error
    )


def validate_decision_run(
    decision_root: pathlib.Path,
    tasks: Sequence[R.FrozenTask],
    row_schema: Mapping[str, Any],
    selected_tasks: Sequence[R.FrozenTask],
) -> dict[str, list[dict[str, Any]]]:
    state_path = decision_root / "run_state.json"
    if not state_path.is_file():
        raise ObservatoryError("decision run_state.json missing")
    state = load_json(state_path)
    if state.get("model") != DECISION_MODEL:
        raise ObservatoryError(
            f"decision run model {state.get('model')!r} != frozen {DECISION_MODEL!r}"
        )
    if state.get("reasoning_effort") != DECISION_REASONING:
        raise ObservatoryError("decision reasoning effort mismatch")
    if state.get("auth_mode") != "CHATGPT_MANAGED_CODEX_LOGIN":
        raise ObservatoryError("decision run is not ChatGPT-managed auth")
    if state.get("api_key_used") is not False:
        raise ObservatoryError("decision run reports API key usage")
    if state.get("fresh_context_per_work_item") is not True:
        raise ObservatoryError("decision run is not fresh-context")
    if state.get("target_outcomes_opened") is not False:
        raise ObservatoryError("decision run opened outcomes")

    by_task = {}
    for task in selected_tasks:
        path = decision_root / task.output_relpath
        valid, rows = R.existing_output_valid(task, path, row_schema)
        if not valid or rows is None:
            raise ObservatoryError(f"missing/invalid D0 decision output: {task.task_id}")
        meta_path = path.with_suffix(path.suffix + ".meta.json")
        if not meta_path.is_file():
            raise ObservatoryError(f"missing D0 meta: {task.task_id}")
        meta = load_json(meta_path)
        checks = (
            meta.get("status") == "VALIDATED",
            meta.get("model") == DECISION_MODEL,
            meta.get("reasoning") == DECISION_REASONING,
            meta.get("fresh_context") is True,
            meta.get("codex_ephemeral") is True,
            meta.get("forbidden_tool_events") == [],
            meta.get("output_sha256") == R.sha256_file(path),
        )
        if not all(checks):
            raise ObservatoryError(f"D0 provenance gate failed: {task.task_id}")
        by_task[task.task_id] = rows
    return by_task


def deliberation_output_path(output_root: pathlib.Path, task: R.FrozenTask) -> pathlib.Path:
    rel = pathlib.PurePosixPath(task.output_relpath)
    parts = list(rel.parts)
    if parts and parts[0] == "outputs":
        parts[0] = "deliberations"
    else:
        parts.insert(0, "deliberations")
    return output_root / pathlib.Path(*parts)


def run_deliberation_task(
    *,
    task: R.FrozenTask,
    decisions: Sequence[Mapping[str, Any]],
    scope: str,
    prompt: str,
    base_schema: Mapping[str, Any],
    output_root: pathlib.Path,
    codex_bin: str,
    model: str,
    reasoning: str,
    max_attempts: int,
    timeout_seconds: int,
    dry_run: bool,
) -> InvocationResult:
    selected = select_panel(task, decisions, scope)
    schema = dynamic_deliberation_schema(base_schema, task, selected)
    context = build_deliberation_request(prompt=prompt, task=task, selected=selected)
    output = deliberation_output_path(output_root, task)
    run_dir = output_root / "_observatory_runs" / "deliberation" / task.task_id
    return invoke_structured(
        task_id=task.task_id,
        phase="L0_OBSERVABLE_DELIBERATION",
        context=context,
        schema=schema,
        output_path=output,
        run_dir=run_dir,
        validator=lambda value: validate_deliberations(value, task, selected),
        codex_bin=codex_bin,
        model=model,
        reasoning=reasoning,
        max_attempts=max_attempts,
        timeout_seconds=timeout_seconds,
        dry_run=dry_run,
    )
