#!/usr/bin/env python3
"""Generate the Agent Society GPT baseline through Codex ChatGPT-managed auth.

One `codex exec --ephemeral` process is launched per frozen work item. The
runner never uses an OpenAI API key and never stores ChatGPT auth material.
It is resumable, fail-closed, and validates every 32-row response before
promotion into the output corpus.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import dataclasses
import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import zipfile
from typing import Any, Iterable, Mapping, Sequence

PROTOCOL_ID = "ATLAS_CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V1"
DEFAULT_MODEL = "gpt-5.6-terra"
DEFAULT_REASONING = "medium"
DEFAULT_ROWS_PER_TASK = 32
CANONICAL_WORK_ITEMS = 2944
CANONICAL_ROWS = 94208
FACTORS = (
    "prior_vote_inertia",
    "turnout_habit",
    "personal_economic_conditions",
    "employment_and_income",
    "social_protection_and_public_services",
    "policy_program_fit",
    "governance_and_institutions",
    "territorial_rural_fit",
    "government_reward_punishment",
    "local_candidate_context",
    "other_verified_context",
)
EXIT_PAUSED = 75
RATE_LIMIT_MARKERS = (
    "usage limit",
    "rate limit",
    "too many requests",
    "insufficient credits",
    "credit balance",
    "limit reached",
    "429",
)
PRINT_LOCK = threading.Lock()


class RunnerError(RuntimeError):
    pass


class ValidationError(RunnerError):
    pass


@dataclasses.dataclass(frozen=True)
class FrozenTask:
    task_id: str
    packet: dict[str, Any]
    expected_rows: tuple[dict[str, Any], ...]
    available_party_ids: tuple[str, ...]
    output_relpath: str
    source_paths: tuple[str, ...]
    source_sha256: str

    @property
    def election_id(self) -> str:
        return str(self.packet["anonymous_election_id"])

    @property
    def territory_id(self) -> str:
        return str(self.packet["anonymous_territory_id"])

    @property
    def condition_id(self) -> str:
        return str(self.packet["condition_id"])

    @property
    def batch_id(self) -> str:
        return str(self.packet["batch_id"])


@dataclasses.dataclass
class TaskResult:
    task_id: str
    status: str
    output_relpath: str
    attempts: int
    rows: int = 0
    output_sha256: str | None = None
    usage: dict[str, int] | None = None
    error: str | None = None
    rate_limited: bool = False


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_text(path: pathlib.Path) -> str:
    if path.suffix == ".gz":
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            return fh.read()
    return path.read_text(encoding="utf-8")


def read_json(path: pathlib.Path) -> Any:
    return json.loads(read_text(path))


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass


def atomic_write_json(path: pathlib.Path, value: Any, *, pretty: bool = True) -> None:
    if pretty:
        data = (
            json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        ).encode("utf-8")
    else:
        data = canonical_bytes(value) + b"\n"
    atomic_write(path, data)


def atomic_write_jsonl(path: pathlib.Path, rows: Sequence[Mapping[str, Any]]) -> None:
    data = b"".join(canonical_bytes(row) + b"\n" for row in rows)
    atomic_write(path, data)


def resolve_single(root: pathlib.Path, patterns: Sequence[str], label: str) -> pathlib.Path:
    candidates: list[pathlib.Path] = []
    for pattern in patterns:
        candidates.extend(p for p in root.rglob(pattern) if p.is_file())
    unique = sorted(set(candidates), key=lambda p: (len(p.parts), str(p)))
    if not unique:
        raise RunnerError(f"{label} not found under {root}")
    return unique[0]


def extract_bundle(bundle: pathlib.Path, cache_root: pathlib.Path) -> tuple[pathlib.Path, str]:
    bundle = bundle.expanduser().resolve()
    if bundle.is_dir():
        digest_parts = []
        for name in (
            "work_manifest.json",
            "handoff_manifest.json",
            "as2_full_environment_prompt_v2.md",
            "as2_prompt_v2.md",
        ):
            hits = sorted(bundle.rglob(name))
            if hits:
                digest_parts.append(name + ":" + sha256_file(hits[0]))
        digest = sha256_bytes("\n".join(digest_parts).encode()) if digest_parts else "DIRECTORY"
        return bundle, digest

    if not bundle.is_file() or bundle.suffix.lower() != ".zip":
        raise RunnerError("--bundle must be an extracted directory or ZIP archive")
    digest = sha256_file(bundle)
    target = cache_root / digest
    marker = target / ".atlas_extracted_ok"
    if not marker.exists():
        tmp = target.with_name(target.name + ".tmp")
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle) as archive:
            for info in archive.infolist():
                member = pathlib.PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise RunnerError(f"unsafe ZIP member: {info.filename}")
            archive.extractall(tmp)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        os.replace(tmp, target)
        marker.write_text(digest + "\n", encoding="utf-8")
    return target, digest


def find_environment_root(extracted: pathlib.Path) -> pathlib.Path:
    indicators = (
        "work_manifest.json",
        "handoff_manifest.json",
        "as2_full_environment_prompt_v2.md",
        "as2_prompt_v2.md",
    )
    candidates: list[pathlib.Path] = []
    for indicator in indicators:
        candidates.extend(path.parent for path in extracted.rglob(indicator))
    if not candidates:
        raise RunnerError("could not locate a frozen Agent Society environment")

    def score(path: pathlib.Path) -> tuple[int, int]:
        points = sum((path / name).exists() for name in indicators)
        points += 2 * sum((path / name).is_dir() for name in ("packets", "contexts", "voter_batches"))
        return points, -len(path.parts)

    return max(set(candidates), key=score)


def locate_relative(root: pathlib.Path, rel: str) -> pathlib.Path:
    normalized = rel.replace("\\", "/").lstrip("./")
    direct = root / normalized
    if direct.is_file():
        return direct
    basename = pathlib.PurePosixPath(normalized).name
    hits = sorted(root.rglob(basename))
    if len(hits) == 1:
        return hits[0]
    raise RunnerError(f"referenced file not found unambiguously: {rel}")


def voter_rows(value: Mapping[str, Any]) -> list[dict[str, Any]]:
    for key in ("voter_archetypes", "archetypes", "voters"):
        rows = value.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows]
    raise RunnerError("voter batch has no voter_archetypes/archetypes/voters array")


def available_parties(*objects: Mapping[str, Any]) -> tuple[str, ...]:
    for obj in objects:
        value = obj.get("available_party_ids")
        if isinstance(value, list) and value:
            return tuple(sorted(str(x) for x in value))
    raise RunnerError("available_party_ids missing")


def common_identity(*objects: Mapping[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    aliases = {
        "anonymous_election_id": ("anonymous_election_id", "election_id"),
        "anonymous_territory_id": ("anonymous_territory_id", "territory_id"),
        "condition_id": ("condition_id",),
        "batch_id": ("batch_id",),
    }
    for target, keys in aliases.items():
        for obj in objects:
            for key in keys:
                if obj.get(key) is not None:
                    result[target] = str(obj[key])
                    break
            if target in result:
                break
        if target not in result:
            raise RunnerError(f"{target} missing from frozen work item")
    return result


def safe_task_id(parts: Iterable[str]) -> str:
    raw = "__".join(str(x) for x in parts)
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", raw)


def discover_packet_tasks(root: pathlib.Path) -> list[FrozenTask]:
    packet_root = root / "packets"
    if not packet_root.is_dir():
        return []
    tasks: list[FrozenTask] = []
    for path in sorted(packet_root.rglob("*.json")):
        packet = read_json(path)
        voters = voter_rows(packet)
        ids = common_identity(packet)
        parties = available_parties(packet)
        task_id = safe_task_id(
            (ids["anonymous_election_id"], ids["condition_id"],
             ids["anonymous_territory_id"], ids["batch_id"])
        )
        rel = (
            pathlib.PurePosixPath("outputs")
            / ids["anonymous_election_id"]
            / ids["condition_id"]
            / ids["anonymous_territory_id"]
            / f'{ids["batch_id"]}.jsonl'
        )
        tasks.append(
            FrozenTask(
                task_id=task_id,
                packet=packet,
                expected_rows=tuple(voters),
                available_party_ids=parties,
                output_relpath=str(rel),
                source_paths=(str(path.relative_to(root)),),
                source_sha256=sha256_file(path),
            )
        )
    return tasks


def _context_path_from_item(item: Mapping[str, Any]) -> str:
    for key in ("context_path", "territory_context_path", "common_context_path"):
        if item.get(key):
            return str(item[key])
    e = item.get("anonymous_election_id")
    c = item.get("condition_id")
    t = item.get("anonymous_territory_id")
    if all((e, c, t)):
        return f"contexts/{e}/{c}/{t}.json"
    raise RunnerError("cannot derive context path from work manifest item")


def _voter_path_from_item(item: Mapping[str, Any]) -> str:
    for key in ("voter_batch_path", "voters_path", "batch_path", "input_path"):
        if item.get(key):
            return str(item[key])
    e = item.get("anonymous_election_id")
    t = item.get("anonymous_territory_id")
    b = item.get("batch_id")
    if all((e, t, b)):
        return f"voter_batches/{e}/{t}/{b}.json"
    raise RunnerError("cannot derive voter batch path from work manifest item")


def discover_manifest_tasks(root: pathlib.Path) -> list[FrozenTask]:
    manifests = sorted(root.rglob("work_manifest.json"), key=lambda p: (len(p.parts), str(p)))
    if not manifests:
        return []
    manifest_path = manifests[0]
    manifest = read_json(manifest_path)
    items = manifest.get("work_items")
    if not isinstance(items, list) or not items:
        raise RunnerError("work_manifest.json contains no work_items")
    tasks: list[FrozenTask] = []
    for ordinal, raw in enumerate(items):
        item = dict(raw)
        context_path = locate_relative(root, _context_path_from_item(item))
        voter_path = locate_relative(root, _voter_path_from_item(item))
        context = read_json(context_path)
        batch = read_json(voter_path)
        voters = voter_rows(batch)
        ids = common_identity(item, batch, context)
        parties = available_parties(batch, context)
        packet = {
            "schema_version": "ATLAS_CODEX_TRANSPORT_PACKET_V1",
            **ids,
            "available_party_ids": list(parties),
            "context": context,
            "voter_batch": batch,
        }
        task_id = safe_task_id(
            (f"{ordinal:04d}", ids["anonymous_election_id"], ids["condition_id"],
             ids["anonymous_territory_id"], ids["batch_id"])
        )
        rel = item.get("output_path") or (
            pathlib.PurePosixPath("outputs")
            / ids["anonymous_election_id"]
            / ids["condition_id"]
            / ids["anonymous_territory_id"]
            / f'{ids["batch_id"]}.jsonl'
        )
        source_paths = (
            str(context_path.relative_to(root)),
            str(voter_path.relative_to(root)),
        )
        tasks.append(
            FrozenTask(
                task_id=task_id,
                packet=packet,
                expected_rows=tuple(voters),
                available_party_ids=parties,
                output_relpath=str(rel).replace("\\", "/"),
                source_paths=source_paths,
                source_sha256=sha256_json(
                    {
                        "context_sha256": sha256_file(context_path),
                        "voter_batch_sha256": sha256_file(voter_path),
                    }
                ),
            )
        )
    return tasks


def discover_tasks(root: pathlib.Path) -> tuple[list[FrozenTask], str]:
    tasks = discover_manifest_tasks(root)
    mode = "WORK_MANIFEST"
    if not tasks:
        tasks = discover_packet_tasks(root)
        mode = "PACKETS"
    if not tasks:
        raise RunnerError("no work_manifest or packets found")
    ids = [task.task_id for task in tasks]
    if len(ids) != len(set(ids)):
        raise RunnerError("duplicate task ids")
    output_paths = [task.output_relpath for task in tasks]
    if len(output_paths) != len(set(output_paths)):
        raise RunnerError("duplicate output paths")
    return tasks, mode


def discover_prompt_and_schema(root: pathlib.Path) -> tuple[pathlib.Path, pathlib.Path]:
    prompt = resolve_single(
        root,
        (
            "as2_full_environment_prompt_v2.md",
            "as2_prompt_v2.md",
            "*prompt*v2*.md",
        ),
        "frozen prompt",
    )
    schema = resolve_single(
        root,
        (
            "as2_full_environment_output_schema_v2.json",
            "as2_output_schema_v2.json",
            "*output_schema*v2*.json",
        ),
        "frozen output schema",
    )
    return prompt, schema


def wrapper_schema(
    row_schema: Mapping[str, Any],
    task: FrozenTask,
) -> dict[str, Any]:
    schema = json.loads(json.dumps(row_schema))
    schema.pop("$id", None)
    schema.pop("$schema", None)
    properties = schema.get("properties") or {}
    for key, value in {
        "anonymous_election_id": task.election_id,
        "anonymous_territory_id": task.territory_id,
        "condition_id": task.condition_id,
        "batch_id": task.batch_id,
    }.items():
        if key in properties:
            properties[key] = {"type": "string", "enum": [value]}
    party_prop = properties.get("conditional_party_probabilities")
    if isinstance(party_prop, dict):
        number_schema = party_prop.get("additionalProperties")
        if not isinstance(number_schema, dict):
            number_schema = {"type": "number", "minimum": 0, "maximum": 1}
        party_prop.pop("minProperties", None)
        party_prop.pop("maxProperties", None)
        party_prop["properties"] = {
            party: json.loads(json.dumps(number_schema))
            for party in task.available_party_ids
        }
        party_prop["required"] = list(task.available_party_ids)
        party_prop["additionalProperties"] = False
    factor_prop = properties.get("factor_importance")
    if isinstance(factor_prop, dict) and not factor_prop.get("properties"):
        number_schema = factor_prop.get("additionalProperties")
        if not isinstance(number_schema, dict):
            number_schema = {"type": "number", "minimum": 0, "maximum": 1}
        factor_prop.pop("minProperties", None)
        factor_prop.pop("maxProperties", None)
        factor_prop["properties"] = {
            factor: json.loads(json.dumps(number_schema)) for factor in FACTORS
        }
        factor_prop["required"] = list(FACTORS)
        factor_prop["additionalProperties"] = False
    count = len(task.expected_rows)
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ATLAS Codex transport wrapper — one frozen batch",
        "type": "object",
        "additionalProperties": False,
        "required": ["rows"],
        "properties": {
            "rows": {
                "type": "array",
                "minItems": count,
                "maxItems": count,
                "items": schema,
            }
        },
    }


def build_context(
    frozen_prompt: str,
    row_schema: Mapping[str, Any],
    task: FrozenTask,
) -> str:
    return "\n".join(
        (
            "FROZEN SCIENTIFIC PROMPT — USE VERBATIM:",
            frozen_prompt,
            "",
            "TRANSPORT-ONLY WRAPPER:",
            (
                'The scientific schema applies to every row. For this Codex automation '
                'transport, return exactly one JSON object {"rows":[...]} containing '
                f"exactly {len(task.expected_rows)} row objects in the supplied order. "
                "This wrapper changes no scientific field or rule. Return no prose."
            ),
            "",
            "ROW SCHEMA:",
            json.dumps(row_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "",
            "FROZEN PACKET:",
            json.dumps(task.packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    )


def extract_schema_properties(row_schema: Mapping[str, Any]) -> tuple[set[str], set[str]]:
    props = set((row_schema.get("properties") or {}).keys())
    required = set(row_schema.get("required") or ())
    return props, required


def enum_for_property(row_schema: Mapping[str, Any], name: str) -> set[str] | None:
    prop = (row_schema.get("properties") or {}).get(name) or {}
    items = prop.get("items") or {}
    values = items.get("enum")
    return set(str(v) for v in values) if isinstance(values, list) else None


def validate_rows(
    value: Any,
    task: FrozenTask,
    row_schema: Mapping[str, Any],
) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"rows"}:
        raise ValidationError('final output must be exactly {"rows":[...]}')
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) != len(task.expected_rows):
        raise ValidationError(
            f"row count {len(rows) if isinstance(rows, list) else 'non-array'} "
            f"!= {len(task.expected_rows)}"
        )
    properties, required = extract_schema_properties(row_schema)
    reason_enum = enum_for_property(row_schema, "reason_codes")

    identity = {
        "anonymous_election_id": task.election_id,
        "anonymous_territory_id": task.territory_id,
        "condition_id": task.condition_id,
        "batch_id": task.batch_id,
    }
    expected_archetypes = [
        str(row.get("weighted_archetype_id") or row.get("archetype_id") or "")
        for row in task.expected_rows
    ]
    if any(not value for value in expected_archetypes):
        raise ValidationError("frozen voter rows are missing archetype ids")

    validated: list[dict[str, Any]] = []
    for i, raw in enumerate(rows):
        if not isinstance(raw, dict):
            raise ValidationError(f"row {i}: not an object")
        row = dict(raw)
        missing = required - set(row)
        if missing:
            raise ValidationError(f"row {i}: missing {sorted(missing)}")
        if row_schema.get("additionalProperties") is False:
            extras = set(row) - properties
            if extras:
                raise ValidationError(f"row {i}: extra keys {sorted(extras)}")
        for key, expected in identity.items():
            if key in properties and str(row.get(key)) != expected:
                raise ValidationError(f"row {i}: {key} mismatch")
        if str(row.get("weighted_archetype_id")) != expected_archetypes[i]:
            raise ValidationError(f"row {i}: archetype order mismatch")

        turnout = row.get("turnout_probability")
        if isinstance(turnout, bool) or not isinstance(turnout, (int, float)):
            raise ValidationError(f"row {i}: turnout is not numeric")
        if not 0.0 <= float(turnout) <= 1.0:
            raise ValidationError(f"row {i}: turnout out of range")

        parties = row.get("conditional_party_probabilities")
        if not isinstance(parties, dict):
            raise ValidationError(f"row {i}: party probabilities missing")
        if set(parties) != set(task.available_party_ids):
            raise ValidationError(f"row {i}: party ids mismatch")
        pvals = list(parties.values())
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= float(v) <= 1
            for v in pvals
        ):
            raise ValidationError(f"row {i}: invalid party probability")
        if abs(sum(float(v) for v in pvals) - 1.0) > 1e-9:
            raise ValidationError(f"row {i}: party simplex does not sum to one")

        if "factor_importance" in required or "factor_importance" in row:
            factors = row.get("factor_importance")
            prop = (row_schema.get("properties") or {}).get("factor_importance") or {}
            declared = set((prop.get("properties") or {}).keys()) or set(FACTORS)
            if not isinstance(factors, dict) or set(factors) != declared:
                raise ValidationError(f"row {i}: factor keys mismatch")
            fvals = list(factors.values())
            if any(
                isinstance(v, bool) or not isinstance(v, (int, float)) or not 0 <= float(v) <= 1
                for v in fvals
            ):
                raise ValidationError(f"row {i}: invalid factor importance")
            if abs(sum(float(v) for v in fvals) - 1.0) > 1e-9:
                raise ValidationError(f"row {i}: factor simplex does not sum to one")

        reasons = row.get("reason_codes")
        if not isinstance(reasons, list) or not reasons:
            raise ValidationError(f"row {i}: reason_codes invalid")
        if len(reasons) != len(set(reasons)):
            raise ValidationError(f"row {i}: duplicate reason code")
        if reason_enum is not None and not set(map(str, reasons)) <= reason_enum:
            raise ValidationError(f"row {i}: reason code outside schema")
        reason_prop = (row_schema.get("properties") or {}).get("reason_codes") or {}
        if len(reasons) < int(reason_prop.get("minItems", 0)):
            raise ValidationError(f"row {i}: too few reason codes")
        if "maxItems" in reason_prop and len(reasons) > int(reason_prop["maxItems"]):
            raise ValidationError(f"row {i}: too many reason codes")
        validated.append(row)
    return validated


def parse_usage(event_log: pathlib.Path) -> dict[str, int]:
    total: dict[str, int] = {}
    if not event_log.exists():
        return total
    for line in event_log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("type") != "turn.completed":
            continue
        usage = event.get("usage") or {}
        for key, value in usage.items():
            if isinstance(value, int):
                total[key] = total.get(key, 0) + value
    return total


def event_tool_violations(event_log: pathlib.Path) -> list[str]:
    violations: list[str] = []
    if not event_log.exists():
        return violations
    for line in event_log.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        item = event.get("item") or {}
        item_type = str(item.get("type", ""))
        if item_type in {
            "command_execution",
            "file_change",
            "mcp_tool_call",
            "web_search",
            "computer_use",
        }:
            violations.append(item_type)
    return sorted(set(violations))


def codex_command(
    codex_bin: str,
    model: str,
    reasoning: str,
    schema_path: pathlib.Path,
    final_path: pathlib.Path,
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
            "Produce the frozen voter-level structured output from the piped context. "
            "Do not use tools, files, network access, memory, or outside information."
        ),
    ]


def rate_limited(text: str) -> bool:
    lower = text.lower()
    return any(marker in lower for marker in RATE_LIMIT_MARKERS)


def existing_output_valid(
    task: FrozenTask,
    output_path: pathlib.Path,
    row_schema: Mapping[str, Any],
) -> tuple[bool, list[dict[str, Any]] | None]:
    if not output_path.is_file():
        return False, None
    try:
        rows = [
            json.loads(line)
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        validated = validate_rows({"rows": rows}, task, row_schema)
        return True, validated
    except Exception:
        return False, None


def run_one(
    *,
    task: FrozenTask,
    frozen_prompt: str,
    row_schema: Mapping[str, Any],
    output_root: pathlib.Path,
    codex_bin: str,
    model: str,
    reasoning: str,
    max_attempts: int,
    timeout_seconds: int,
    dry_run: bool,
) -> TaskResult:
    output_path = output_root / task.output_relpath
    valid, rows = existing_output_valid(task, output_path, row_schema)
    if valid:
        return TaskResult(
            task_id=task.task_id,
            status="ALREADY_VALID",
            output_relpath=task.output_relpath,
            attempts=0,
            rows=len(rows or ()),
            output_sha256=sha256_file(output_path),
        )

    context = build_context(frozen_prompt, row_schema, task)
    task_dir = output_root / "_runs" / task.task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    wrapper_path = task_dir / "transport_schema.json"
    atomic_write_json(wrapper_path, wrapper_schema(row_schema, task))
    context_hash = sha256_bytes(context.encode("utf-8"))

    if dry_run:
        atomic_write_json(
            task_dir / "dry_run.json",
            {
                "task_id": task.task_id,
                "context_sha256": context_hash,
                "source_sha256": task.source_sha256,
                "expected_rows": len(task.expected_rows),
                "output_relpath": task.output_relpath,
            },
        )
        return TaskResult(
            task_id=task.task_id,
            status="DRY_RUN_VALIDATED",
            output_relpath=task.output_relpath,
            attempts=0,
        )

    last_error = "unknown failure"
    aggregate_usage: dict[str, int] = {}
    for attempt in range(1, max_attempts + 1):
        attempt_dir = task_dir / f"attempt_{attempt:02d}"
        attempt_dir.mkdir(parents=True, exist_ok=True)
        final_path = attempt_dir / "final.json"
        event_path = attempt_dir / "events.jsonl"
        stderr_path = attempt_dir / "stderr.txt"
        command = codex_command(
            codex_bin, model, reasoning, wrapper_path, final_path
        )
        command_record = {
            "protocol_id": PROTOCOL_ID,
            "task_id": task.task_id,
            "attempt": attempt,
            "started_at": utc_now(),
            "model": model,
            "reasoning": reasoning,
            "context_sha256": context_hash,
            "source_sha256": task.source_sha256,
            "command_without_credentials": command,
        }
        atomic_write_json(attempt_dir / "invocation.json", command_record)

        empty_workdir = attempt_dir / "empty_read_only_workdir"
        empty_workdir.mkdir(exist_ok=True)
        try:
            proc = subprocess.run(
                command,
                input=context,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=empty_workdir,
                timeout=timeout_seconds,
                check=False,
                env={
                    key: value
                    for key, value in os.environ.items()
                    if key not in {"OPENAI_API_KEY", "CODEX_API_KEY"}
                },
            )
        except subprocess.TimeoutExpired as exc:
            last_error = f"timeout after {timeout_seconds}s"
            atomic_write(stderr_path, (str(exc) + "\n").encode())
            return TaskResult(
                task_id=task.task_id,
                status="FAILED_TRANSPORT_NO_RETRY",
                output_relpath=task.output_relpath,
                attempts=attempt,
                usage=aggregate_usage,
                error=last_error,
            )

        atomic_write(event_path, proc.stdout.encode("utf-8", errors="replace"))
        atomic_write(stderr_path, proc.stderr.encode("utf-8", errors="replace"))
        usage = parse_usage(event_path)
        for key, value in usage.items():
            aggregate_usage[key] = aggregate_usage.get(key, 0) + value

        combined = proc.stdout + "\n" + proc.stderr
        if proc.returncode != 0:
            last_error = f"codex exit {proc.returncode}"
            if rate_limited(combined):
                return TaskResult(
                    task_id=task.task_id,
                    status="PAUSED_USAGE_LIMIT",
                    output_relpath=task.output_relpath,
                    attempts=attempt,
                    usage=aggregate_usage,
                    error=last_error,
                    rate_limited=True,
                )
            return TaskResult(
                task_id=task.task_id,
                status="FAILED_TRANSPORT_NO_RETRY",
                output_relpath=task.output_relpath,
                attempts=attempt,
                usage=aggregate_usage,
                error=last_error,
            )

        violations = event_tool_violations(event_path)
        if violations:
            last_error = "forbidden tool events: " + ",".join(violations)
            return TaskResult(
                task_id=task.task_id,
                status="FAILED_EXECUTION_CONTRACT_NO_RETRY",
                output_relpath=task.output_relpath,
                attempts=attempt,
                usage=aggregate_usage,
                error=last_error,
            )
        if not final_path.is_file():
            last_error = "Codex produced no final output file"
            return TaskResult(
                task_id=task.task_id,
                status="FAILED_TRANSPORT_NO_RETRY",
                output_relpath=task.output_relpath,
                attempts=attempt,
                usage=aggregate_usage,
                error=last_error,
            )
        try:
            value = read_json(final_path)
            validated = validate_rows(value, task, row_schema)
        except Exception as exc:
            last_error = f"schema-invalid output: {exc}"
            continue

        atomic_write_jsonl(output_path, validated)
        meta = {
            "schema_version": "ATLAS_CHATGPT_BASELINE_TASK_META_V1",
            "protocol_id": PROTOCOL_ID,
            "task_id": task.task_id,
            "status": "VALIDATED",
            "model": model,
            "reasoning": reasoning,
            "fresh_context": True,
            "codex_ephemeral": True,
            "chatgpt_managed_auth_required": True,
            "attempts": attempt,
            "retry_semantic_feedback": False,
            "context_sha256": context_hash,
            "source_sha256": task.source_sha256,
            "source_paths": list(task.source_paths),
            "output_relpath": task.output_relpath,
            "output_sha256": sha256_file(output_path),
            "rows": len(validated),
            "usage": aggregate_usage,
            "validated_at": utc_now(),
            "forbidden_tool_events": [],
        }
        atomic_write_json(output_path.with_suffix(output_path.suffix + ".meta.json"), meta)
        return TaskResult(
            task_id=task.task_id,
            status="VALIDATED",
            output_relpath=task.output_relpath,
            attempts=attempt,
            rows=len(validated),
            output_sha256=meta["output_sha256"],
            usage=aggregate_usage,
        )

    return TaskResult(
        task_id=task.task_id,
        status="FAILED",
        output_relpath=task.output_relpath,
        attempts=max_attempts,
        usage=aggregate_usage,
        error=last_error,
    )


def sum_usage(results: Sequence[TaskResult]) -> dict[str, int]:
    result: dict[str, int] = {}
    for item in results:
        for key, value in (item.usage or {}).items():
            result[key] = result.get(key, 0) + value
    return result


def task_manifest_record(task: FrozenTask, output_root: pathlib.Path) -> dict[str, Any]:
    output_path = output_root / task.output_relpath
    meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
    return {
        "task_id": task.task_id,
        "source_paths": list(task.source_paths),
        "source_sha256": task.source_sha256,
        "output_path": task.output_relpath,
        "output_sha256": sha256_file(output_path) if output_path.is_file() else None,
        "meta_sha256": sha256_file(meta_path) if meta_path.is_file() else None,
        "rows": sum(
            1 for line in output_path.read_text(encoding="utf-8").splitlines() if line.strip()
        ) if output_path.is_file() else 0,
    }


def write_run_state(
    *,
    output_root: pathlib.Path,
    bundle_sha256: str,
    environment_root: pathlib.Path,
    discovery_mode: str,
    tasks: Sequence[FrozenTask],
    model: str,
    reasoning: str,
    prompt_sha256: str,
    schema_sha256: str,
    results: Sequence[TaskResult],
    complete: bool,
) -> None:
    records = [task_manifest_record(task, output_root) for task in tasks]
    valid = [record for record in records if record["output_sha256"]]
    rows = sum(int(record["rows"]) for record in valid)
    state = {
        "schema_version": "ATLAS_CHATGPT_BASELINE_RUN_STATE_V1",
        "protocol_id": PROTOCOL_ID,
        "status": (
            "PASS_CHATGPT_ACCOUNT_BASELINE_FROZEN_READY_FOR_SCORING"
            if complete
            else "IN_PROGRESS_RESUMABLE"
        ),
        "baseline_id": f"G0_CHATGPT_{model.upper().replace('-', '_').replace('.', '_')}",
        "created_or_updated_at": utc_now(),
        "bundle_sha256": bundle_sha256,
        "environment_root": str(environment_root),
        "discovery_mode": discovery_mode,
        "model": model,
        "reasoning_effort": reasoning,
        "auth_mode": "CHATGPT_MANAGED_CODEX_LOGIN",
        "api_key_used": False,
        "fresh_context_per_work_item": True,
        "codex_ephemeral": True,
        "web_search": "disabled",
        "tools_allowed": False,
        "outside_information_allowed": False,
        "target_outcomes_opened": False,
        "semantic_retry_feedback": False,
        "prompt_sha256": prompt_sha256,
        "row_schema_sha256": schema_sha256,
        "work_items_expected": len(tasks),
        "work_items_validated": len(valid),
        "rows_expected": sum(len(task.expected_rows) for task in tasks),
        "rows_validated": rows,
        "latest_invocation_results": [dataclasses.asdict(item) for item in results],
        "latest_invocation_usage": sum_usage(results),
    }
    atomic_write_json(output_root / "run_state.json", state)
    atomic_write_json(
        output_root / "output_manifest.json",
        {
            "schema_version": "ATLAS_CHATGPT_BASELINE_OUTPUT_MANIFEST_V1",
            "protocol_id": PROTOCOL_ID,
            "bundle_sha256": bundle_sha256,
            "prompt_sha256": prompt_sha256,
            "row_schema_sha256": schema_sha256,
            "model": model,
            "records": records,
        },
    )


def check_codex(codex_bin: str) -> str:
    path = shutil.which(codex_bin)
    if path is None:
        raise RunnerError(
            f"{codex_bin!r} not found. Install the official Codex CLI and run `codex login`."
        )
    proc = subprocess.run(
        [path, "--version"], text=True, capture_output=True, check=False
    )
    if proc.returncode != 0:
        raise RunnerError(f"could not execute {path}: {proc.stderr.strip()}")
    return (proc.stdout or proc.stderr).strip()


def select_tasks(
    tasks: Sequence[FrozenTask],
    *,
    start: int,
    limit: int | None,
    task_regex: str | None,
) -> list[FrozenTask]:
    chosen = list(tasks)
    if task_regex:
        rx = re.compile(task_regex)
        chosen = [task for task in chosen if rx.search(task.task_id)]
    chosen = chosen[start:]
    if limit is not None:
        chosen = chosen[:limit]
    return chosen


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=(
            "Generate all frozen Agent Society work items with a fresh Codex "
            "context authenticated through the user's ChatGPT account."
        )
    )
    ap.add_argument("--bundle", required=True, type=pathlib.Path)
    ap.add_argument("--output", required=True, type=pathlib.Path)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--reasoning", default=DEFAULT_REASONING)
    ap.add_argument("--codex-bin", default="codex")
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--max-attempts", type=int, default=2)
    ap.add_argument("--timeout-seconds", type=int, default=3600)
    ap.add_argument("--start", type=int, default=0)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--task-regex")
    ap.add_argument("--expected-work-items", type=int, default=CANONICAL_WORK_ITEMS)
    ap.add_argument("--expected-rows", type=int, default=CANONICAL_ROWS)
    ap.add_argument("--allow-noncanonical-counts", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args(argv)

    if args.workers < 1 or args.workers > 8:
        raise RunnerError("--workers must be between 1 and 8")
    if args.max_attempts not in (1, 2):
        raise RunnerError("--max-attempts must be 1 or 2")
    if args.reasoning not in {"low", "medium", "high", "extra_high", "max"}:
        raise RunnerError("unsupported --reasoning value")

    codex_version = "DRY_RUN_NO_CODEX"
    if not args.dry_run:
        codex_version = check_codex(args.codex_bin)

    output_root = args.output.expanduser().resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    cache_root = output_root / "_bundle_cache"
    extracted, bundle_sha256 = extract_bundle(args.bundle, cache_root)
    environment_root = find_environment_root(extracted)
    prompt_path, schema_path = discover_prompt_and_schema(environment_root)
    frozen_prompt = read_text(prompt_path)
    row_schema = read_json(schema_path)
    tasks, discovery_mode = discover_tasks(environment_root)
    discovered_rows = sum(len(task.expected_rows) for task in tasks)
    scoped_half = (
        getattr(args, "dev_pilot_scope", False)
        or os.environ.get("M26_DEV_PILOT_SCOPE") == "1"
    )
    expected_wi = args.expected_work_items // 2 if scoped_half else args.expected_work_items
    expected_rows_n = args.expected_rows // 2 if scoped_half else args.expected_rows
    if not args.allow_noncanonical_counts:
        if len(tasks) != expected_wi or discovered_rows != expected_rows_n:
            raise RunnerError(
                "wrong frozen package: discovered "
                f"{len(tasks)} work items / {discovered_rows} rows; expected "
                f"{expected_wi} / {expected_rows_n}. "
                "Use the 94,208-row full-environment ZIP, not the earlier 47,104-row handoff."
            )
    selected = select_tasks(
        tasks, start=args.start, limit=args.limit, task_regex=args.task_regex
    )
    if not selected:
        raise RunnerError("task selection is empty")

    preflight = {
        "schema_version": "ATLAS_CHATGPT_BASELINE_PREFLIGHT_V1",
        "protocol_id": PROTOCOL_ID,
        "generated_at": utc_now(),
        "codex_version": codex_version,
        "bundle_sha256": bundle_sha256,
        "environment_root": str(environment_root),
        "discovery_mode": discovery_mode,
        "prompt_path": str(prompt_path.relative_to(environment_root)),
        "prompt_sha256": sha256_file(prompt_path),
        "schema_path": str(schema_path.relative_to(environment_root)),
        "schema_sha256": sha256_file(schema_path),
        "model": args.model,
        "reasoning_effort": args.reasoning,
        "work_items_discovered": len(tasks),
        "rows_discovered": discovered_rows,
        "work_items_selected_this_invocation": len(selected),
        "workers": args.workers,
        "fresh_context_per_work_item": True,
        "chatgpt_login_required": True,
        "api_key_forbidden": True,
        "web_search_disabled": True,
        "tools_disabled": True,
        "outcomes_opened": False,
    }
    atomic_write_json(output_root / "preflight.json", preflight)

    with PRINT_LOCK:
        print(
            f"{PROTOCOL_ID}: discovered {len(tasks)} work items / "
            f"{sum(len(t.expected_rows) for t in tasks)} rows; "
            f"running {len(selected)} with {args.model} ({args.reasoning}), "
            f"workers={args.workers}"
        )

    results: list[TaskResult] = []
    stop_event = threading.Event()

    def invoke(task: FrozenTask) -> TaskResult:
        if stop_event.is_set():
            return TaskResult(
                task_id=task.task_id,
                status="NOT_STARTED_AFTER_PAUSE",
                output_relpath=task.output_relpath,
                attempts=0,
            )
        result = run_one(
            task=task,
            frozen_prompt=frozen_prompt,
            row_schema=row_schema,
            output_root=output_root,
            codex_bin=args.codex_bin,
            model=args.model,
            reasoning=args.reasoning,
            max_attempts=args.max_attempts,
            timeout_seconds=args.timeout_seconds,
            dry_run=args.dry_run,
        )
        if result.rate_limited:
            stop_event.set()
        with PRINT_LOCK:
            print(
                f"[{result.status}] {result.task_id} "
                f"attempts={result.attempts} rows={result.rows}"
                + (f" error={result.error}" if result.error else ""),
                flush=True,
            )
        return result

    if args.workers == 1:
        for task in selected:
            result = invoke(task)
            results.append(result)
            if result.rate_limited:
                break
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            future_by_task = {pool.submit(invoke, task): task for task in selected}
            for future in concurrent.futures.as_completed(future_by_task):
                results.append(future.result())

    all_valid = True
    for task in tasks:
        valid, _ = existing_output_valid(
            task, output_root / task.output_relpath, row_schema
        )
        all_valid = all_valid and valid
    write_run_state(
        output_root=output_root,
        bundle_sha256=bundle_sha256,
        environment_root=environment_root,
        discovery_mode=discovery_mode,
        tasks=tasks,
        model=args.model,
        reasoning=args.reasoning,
        prompt_sha256=sha256_file(prompt_path),
        schema_sha256=sha256_file(schema_path),
        results=results,
        complete=all_valid,
    )

    if any(result.rate_limited for result in results):
        print(
            "PAUSED_CHATGPT_USAGE_LIMIT: rerun the identical command later; "
            "validated work items will be skipped.",
            file=sys.stderr,
        )
        return EXIT_PAUSED
    failures = [r for r in results if r.status.startswith("FAILED")]
    if failures:
        print(f"FAILED_WORK_ITEMS={len(failures)}", file=sys.stderr)
        return 2
    if all_valid:
        print("PASS_CHATGPT_ACCOUNT_BASELINE_FROZEN_READY_FOR_SCORING")
    else:
        print("PASS_PARTIAL_RESUMABLE_RUN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
