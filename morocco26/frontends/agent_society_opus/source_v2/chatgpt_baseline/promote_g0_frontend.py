#!/usr/bin/env python3
"""Promote a complete ChatGPT-account G0 corpus into the static Agent Society front.

The command is deliberately fail-closed. It first validates all 2,944 fresh-
context outputs and their provenance. It then derives a complete preview in a
staging directory. Public files are changed only with --apply and only after
all requested promotion products have been built successfully.

E0 is never deleted. On first application, the current deterministic public
reference is archived under web/data/reference/e0/. G0 becomes the primary
reference while E0 remains an inspectable control.
"""
from __future__ import annotations

import argparse
import dataclasses
import importlib.util
import json
import math
import os
import pathlib
import shutil
import statistics
import subprocess
import sys
import tempfile
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_chatgpt_baseline.py"
SPEC = importlib.util.spec_from_file_location("atlas_chatgpt_runner", RUNNER_PATH)
R = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R
assert SPEC.loader is not None
SPEC.loader.exec_module(R)

EXPECTED_STATUS = "PASS_CHATGPT_ACCOUNT_BASELINE_FROZEN_READY_FOR_SCORING"
EXPECTED_MODEL = "gpt-5.6-terra"
EXPECTED_REASONING = "medium"
EXPECTED_WORK_ITEMS = 2944
EXPECTED_ROWS = 94208


class PromotionError(RuntimeError):
    pass


@dataclasses.dataclass(frozen=True)
class TerritoryAggregate:
    election_id: str
    territory_id: str
    condition_id: str
    turnout: float
    expected_vote: dict[str, float]
    mean_probability: dict[str, float]
    rows: int


@dataclasses.dataclass(frozen=True)
class PublicTerritory:
    year: str
    index: int
    data: dict[str, Any]

    @property
    def simulation(self) -> dict[str, float]:
        return {str(k): float(v) for k, v in self.data["simulation"].items()}

    @property
    def turnout(self) -> float:
        return float(self.data["turnout_sim"])

    @property
    def label(self) -> str:
        return f"{self.year}:{self.data.get('slug') or self.data.get('name') or self.index}"


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: pathlib.Path, value: Any, *, pretty: bool = True) -> None:
    R.atomic_write_json(path, value, pretty=pretty)


def copy_file(src: pathlib.Path, dst: pathlib.Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    data = src.read_bytes()
    R.atomic_write(dst, data)


def load_complete_run(run_root: pathlib.Path) -> tuple[dict[str, Any], dict[str, Any]]:
    state_path = run_root / "run_state.json"
    manifest_path = run_root / "output_manifest.json"
    if not state_path.is_file() or not manifest_path.is_file():
        raise PromotionError("run_state.json and output_manifest.json are required")
    state = read_json(state_path)
    manifest = read_json(manifest_path)
    checks = {
        "terminal status": state.get("status") == EXPECTED_STATUS,
        "model": state.get("model") == EXPECTED_MODEL,
        "reasoning": state.get("reasoning_effort") == EXPECTED_REASONING,
        "auth": state.get("auth_mode") == "CHATGPT_MANAGED_CODEX_LOGIN",
        "no API key": state.get("api_key_used") is False,
        "fresh context": state.get("fresh_context_per_work_item") is True,
        "ephemeral": state.get("codex_ephemeral") is True,
        "web disabled": state.get("web_search") == "disabled",
        "tools disabled": state.get("tools_allowed") is False,
        "outside information disabled": state.get("outside_information_allowed") is False,
        "outcomes sealed": state.get("target_outcomes_opened") is False,
        "work item count": state.get("work_items_validated") == EXPECTED_WORK_ITEMS,
        "row count": state.get("rows_validated") == EXPECTED_ROWS,
        "expected work items": state.get("work_items_expected") == EXPECTED_WORK_ITEMS,
        "expected rows": state.get("rows_expected") == EXPECTED_ROWS,
        "manifest model": manifest.get("model") == EXPECTED_MODEL,
        "manifest records": len(manifest.get("records") or ()) == EXPECTED_WORK_ITEMS,
    }
    failed = [name for name, ok in checks.items() if not ok]
    if failed:
        raise PromotionError("G0 terminal gate failed: " + ", ".join(failed))
    return state, manifest


def verify_outputs(
    env_root: pathlib.Path,
    run_root: pathlib.Path,
    state: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> tuple[list[R.FrozenTask], Mapping[str, Any], pathlib.Path, pathlib.Path]:
    prompt_path, schema_path = R.discover_prompt_and_schema(env_root)
    row_schema = read_json(schema_path)
    tasks, _ = R.discover_tasks(env_root)
    if len(tasks) != EXPECTED_WORK_ITEMS:
        raise PromotionError(f"environment has {len(tasks)} work items, expected {EXPECTED_WORK_ITEMS}")
    if sum(len(task.expected_rows) for task in tasks) != EXPECTED_ROWS:
        raise PromotionError("environment row total is not 94,208")
    if state.get("prompt_sha256") != R.sha256_file(prompt_path):
        raise PromotionError("frozen prompt hash differs from G0 run state")
    if state.get("row_schema_sha256") != R.sha256_file(schema_path):
        raise PromotionError("frozen row schema hash differs from G0 run state")

    records = {str(rec["task_id"]): rec for rec in manifest.get("records") or ()}
    missing_records: list[str] = []
    invalid: list[str] = []
    total_rows = 0
    for task in tasks:
        rec = records.get(task.task_id)
        if not rec:
            missing_records.append(task.task_id)
            continue
        output_path = run_root / task.output_relpath
        meta_path = output_path.with_suffix(output_path.suffix + ".meta.json")
        valid, rows = R.existing_output_valid(task, output_path, row_schema)
        if not valid or rows is None:
            invalid.append(task.task_id + ":rows")
            continue
        if not meta_path.is_file():
            invalid.append(task.task_id + ":meta")
            continue
        meta = read_json(meta_path)
        meta_checks = (
            meta.get("status") == "VALIDATED",
            meta.get("model") == EXPECTED_MODEL,
            meta.get("reasoning") == EXPECTED_REASONING,
            meta.get("fresh_context") is True,
            meta.get("codex_ephemeral") is True,
            meta.get("chatgpt_managed_auth_required") is True,
            meta.get("retry_semantic_feedback") is False,
            meta.get("forbidden_tool_events") == [],
            meta.get("source_sha256") == task.source_sha256,
            meta.get("output_sha256") == R.sha256_file(output_path),
            rec.get("output_sha256") == R.sha256_file(output_path),
            rec.get("meta_sha256") == R.sha256_file(meta_path),
            int(rec.get("rows") or 0) == len(task.expected_rows),
        )
        if not all(meta_checks):
            invalid.append(task.task_id + ":provenance")
            continue
        total_rows += len(rows)
    if missing_records or invalid:
        sample = (missing_records[:3] + invalid[:7])
        raise PromotionError(
            f"G0 output audit failed ({len(missing_records)} missing records, "
            f"{len(invalid)} invalid): {sample}"
        )
    if total_rows != EXPECTED_ROWS:
        raise PromotionError(f"validated row total {total_rows} != {EXPECTED_ROWS}")
    return tasks, row_schema, prompt_path, schema_path


def load_judge_helpers(source_v2: pathlib.Path):
    path = source_v2 / "scripts" / "judge_engine.py"
    spec = importlib.util.spec_from_file_location("atlas_judge_helpers", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def government_evaluation(signals: Mapping[str, float]) -> float:
    g = (
        0.38 * signals["gov_econ"]
        + 0.20 * signals["gov_pov"]
        + 0.17 * signals["gov_anti"]
        + 0.25 * signals["trust_parl"]
    )
    c = (
        0.38 * signals["c_gecon"]
        + 0.20 * signals["c_gpov"]
        + 0.17 * signals["c_ganti"]
        + 0.25 * signals["c_tparl"]
    )
    adjusted = (
        g
        + 0.40 * (signals["dem_sat"] - 0.50) * signals["c_dsat"]
        + 0.12 * (signals["econ_cond"] - 0.55) * signals["c_econ"]
        - 0.18 * (signals["corruption"] - 0.44) * signals["c_cloc"]
    )
    return (adjusted - 0.50) * c


def choose_simulator_group(tasks: Sequence[R.FrozenTask]) -> list[R.FrozenTask]:
    groups: dict[tuple[str, str, str], list[R.FrozenTask]] = defaultdict(list)
    for task in tasks:
        groups[(task.election_id, task.territory_id, task.condition_id)].append(task)
    candidates = []
    for key, group in groups.items():
        row_count = sum(len(task.expected_rows) for task in group)
        if row_count == 256:
            candidates.append((key, sorted(group, key=lambda task: task.batch_id)))
    if not candidates:
        raise PromotionError("no complete 256-archetype context available for G0 explorer")
    return min(candidates, key=lambda item: item[0])[1]


def task_context(task: R.FrozenTask) -> Mapping[str, Any]:
    value = task.packet.get("context")
    if isinstance(value, dict):
        return value
    return task.packet


def build_g0_simulator(
    *,
    tasks: Sequence[R.FrozenTask],
    run_root: pathlib.Path,
    source_v2: pathlib.Path,
    state: Mapping[str, Any],
) -> dict[str, Any]:
    helper = load_judge_helpers(source_v2)
    group = choose_simulator_group(tasks)
    context = task_context(group[0])
    prepared = helper.prepare_context(context)
    parties = list(prepared["parties"])
    gov_status = {party: prepared["gov_status"].get(party) for party in parties}
    records: list[dict[str, Any]] = []
    for task in group:
        output_path = run_root / task.output_relpath
        rows = [
            json.loads(line)
            for line in output_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(rows) != len(task.expected_rows):
            raise PromotionError("G0 explorer row/voter count mismatch")
        for voter, row in zip(task.expected_rows, rows):
            signals = helper.voter_signals(voter)
            records.append(
                {
                    "weighted_archetype_id": row["weighted_archetype_id"],
                    "age_band": voter.get("age_band"),
                    "age_years": voter.get("age_years"),
                    "sex": voter.get("sex"),
                    "urban_rural": voter.get("urban_rural"),
                    "education_level": voter.get("education_level"),
                    "activity_status": voter.get("activity_status"),
                    "latent_national_quintile": voter.get("latent_national_quintile"),
                    "prior_vote_or_abstention": voter.get("prior_vote_or_abstention"),
                    "trust": round(float(signals["trust"]), 8),
                    "government_evaluation": round(float(government_evaluation(signals)), 8),
                    "turnout_probability": row["turnout_probability"],
                    "conditional_party_probabilities": row["conditional_party_probabilities"],
                    "factor_importance": row["factor_importance"],
                    "reason_codes": row["reason_codes"],
                }
            )
    if len(records) != 256:
        raise PromotionError(f"G0 explorer contains {len(records)} rows, expected 256")
    return {
        "schema_version": "ATLAS_G0_EMPIRICAL_EXPLORER_V1",
        "status": "GPT_DECISIONS_GENERATED_NOT_YET_HISTORICALLY_SCORED",
        "reference_id": "G0_CHATGPT_GPT56_TERRA",
        "model": state["model"],
        "reasoning_effort": state["reasoning_effort"],
        "source_run_state_sha256": R.sha256_file(run_root / "run_state.json"),
        "context": {
            "anonymous_election_id": group[0].election_id,
            "anonymous_territory_id": group[0].territory_id,
            "condition_id": group[0].condition_id,
            "label": (
                group[0].election_id[:8]
                + " / "
                + group[0].territory_id[:8]
                + " / "
                + group[0].condition_id[:8]
            ),
            "available_party_ids": parties,
            "gov_status": gov_status,
            "previous_turnout": prepared.get("prev_turnout"),
        },
        "factors": list(R.FACTORS),
        "records": records,
    }


def run_derivation(
    source_v2: pathlib.Path,
    env_root: pathlib.Path,
    run_root: pathlib.Path,
    destination: pathlib.Path,
) -> None:
    script = source_v2 / "scripts" / "derive.py"
    proc = subprocess.run(
        [sys.executable, str(script), str(env_root), str(run_root), str(destination)],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if proc.returncode != 0:
        raise PromotionError(
            "derive.py failed: " + (proc.stderr.strip() or proc.stdout.strip())
        )
    for name in ("societe.json", "portraits.json"):
        if not (destination / name).is_file():
            raise PromotionError(f"derive.py did not create {name}")
    society = read_json(destination / "societe.json")
    portraits = read_json(destination / "portraits.json")
    if int(society.get("meta", {}).get("rows") or 0) != EXPECTED_ROWS:
        raise PromotionError("derived society does not contain 94,208 rows")
    if not portraits.get("agents"):
        raise PromotionError("derived portraits are empty")


def read_task_rows(task: R.FrozenTask, run_root: pathlib.Path) -> list[dict[str, Any]]:
    path = run_root / task.output_relpath
    if not path.is_file():
        raise PromotionError(f"missing output for territory aggregation: {task.task_id}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def aggregate_by_condition(
    tasks: Sequence[R.FrozenTask], run_root: pathlib.Path
) -> dict[tuple[str, str, str], TerritoryAggregate]:
    acc: dict[tuple[str, str, str], dict[str, Any]] = {}
    for task in tasks:
        key = (task.election_id, task.territory_id, task.condition_id)
        cur = acc.setdefault(
            key,
            {
                "rows": 0,
                "turnout": 0.0,
                "turnout_mass": 0.0,
                "expected": defaultdict(float),
                "mean": defaultdict(float),
            },
        )
        rows = read_task_rows(task, run_root)
        for row in rows:
            turnout = float(row["turnout_probability"])
            cur["rows"] += 1
            cur["turnout"] += turnout
            cur["turnout_mass"] += turnout
            for party, prob in row["conditional_party_probabilities"].items():
                cur["mean"][party] += float(prob)
                cur["expected"][party] += turnout * float(prob)
    out: dict[tuple[str, str, str], TerritoryAggregate] = {}
    for key, cur in acc.items():
        n = int(cur["rows"])
        if n != 256:
            raise PromotionError(f"territory/condition {key} has {n} rows, expected 256")
        mass = float(cur["turnout_mass"])
        if mass <= 0:
            raise PromotionError(f"territory/condition {key} has zero expected turnout")
        out[key] = TerritoryAggregate(
            election_id=key[0],
            territory_id=key[1],
            condition_id=key[2],
            turnout=float(cur["turnout"]) / n,
            expected_vote={party: value / mass for party, value in cur["expected"].items()},
            mean_probability={party: value / n for party, value in cur["mean"].items()},
            rows=n,
        )
    return out


def combine_conditions(
    by_condition: Mapping[tuple[str, str, str], TerritoryAggregate],
    mode: str,
) -> dict[tuple[str, str], tuple[float, dict[str, float]]]:
    nested: dict[tuple[str, str], list[TerritoryAggregate]] = defaultdict(list)
    for (election, territory, _), aggregate in by_condition.items():
        nested[(election, territory)].append(aggregate)
    result: dict[tuple[str, str], tuple[float, dict[str, float]]] = {}
    for key, groups in nested.items():
        groups = sorted(groups, key=lambda item: item.condition_id)
        if len(groups) != 2:
            raise PromotionError(f"{key} has {len(groups)} conditions, expected 2")
        if mode.startswith("condition0_"):
            selected = [groups[0]]
        elif mode.startswith("condition1_"):
            selected = [groups[1]]
        elif mode.startswith("average_"):
            selected = groups
        else:
            raise PromotionError(f"unknown aggregation mode {mode}")
        field = "expected_vote" if mode.endswith("expected_vote") else "mean_probability"
        parties = set(getattr(selected[0], field))
        if any(set(getattr(item, field)) != parties for item in selected):
            raise PromotionError(f"party keys differ across conditions for {key}")
        shares = {
            party: sum(getattr(item, field)[party] for item in selected) / len(selected)
            for party in sorted(parties)
        }
        total = sum(shares.values())
        shares = {party: value / total for party, value in shares.items()}
        turnout = sum(item.turnout for item in selected) / len(selected)
        result[key] = (turnout, shares)
    return result


def public_territories(template: Mapping[str, Any]) -> dict[str, list[PublicTerritory]]:
    years = template.get("years") or {}
    result: dict[str, list[PublicTerritory]] = {}
    for year, data in years.items():
        territories = data.get("territories") or []
        result[str(year)] = [
            PublicTerritory(str(year), index, dict(item))
            for index, item in enumerate(territories)
        ]
    if len(result) != 2 or any(len(items) != 92 for items in result.values()):
        raise PromotionError("maroc.json must contain two years of 92 territories")
    return result


def vector(values: Mapping[str, float], size: int = 9) -> list[float]:
    result = sorted((float(v) for v in values.values()), reverse=True)
    if len(result) > size:
        raise PromotionError("party vector is wider than expected")
    return result + [0.0] * (size - len(result))


def fingerprint_cost(
    anonymous: tuple[float, Mapping[str, float]], public: PublicTerritory
) -> float:
    turnout, shares = anonymous
    a = vector(shares)
    b = vector(public.simulation)
    rmse = math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a))
    return rmse + 0.25 * abs(float(turnout) - public.turnout)


def hungarian(cost: Sequence[Sequence[float]]) -> list[int]:
    """Minimum-cost one-to-one assignment; return column index for each row."""
    n = len(cost)
    if n == 0 or any(len(row) != n for row in cost):
        raise PromotionError("Hungarian assignment requires a non-empty square matrix")
    u = [0.0] * (n + 1)
    v = [0.0] * (n + 1)
    p = [0] * (n + 1)
    way = [0] * (n + 1)
    for i in range(1, n + 1):
        p[0] = i
        j0 = 0
        minv = [float("inf")] * (n + 1)
        used = [False] * (n + 1)
        while True:
            used[j0] = True
            i0 = p[j0]
            delta = float("inf")
            j1 = 0
            for j in range(1, n + 1):
                if used[j]:
                    continue
                cur = float(cost[i0 - 1][j - 1]) - u[i0] - v[j]
                if cur < minv[j]:
                    minv[j] = cur
                    way[j] = j0
                if minv[j] < delta:
                    delta = minv[j]
                    j1 = j
            for j in range(n + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    assignment = [-1] * n
    for j in range(1, n + 1):
        if p[j]:
            assignment[p[j] - 1] = j - 1
    if any(value < 0 for value in assignment):
        raise PromotionError("Hungarian assignment incomplete")
    return assignment


def match_territories_for_mode(
    anonymous: Mapping[tuple[str, str], tuple[float, Mapping[str, float]]],
    public: Mapping[str, Sequence[PublicTerritory]],
) -> tuple[dict[tuple[str, str], PublicTerritory], dict[str, Any]]:
    elections = sorted({key[0] for key in anonymous})
    years = sorted(public)
    if len(elections) != 2 or len(years) != 2:
        raise PromotionError("territory matching requires exactly two elections and two years")
    by_election = {
        election: sorted(
            [key for key in anonymous if key[0] == election], key=lambda key: key[1]
        )
        for election in elections
    }
    if any(len(keys) != 92 for keys in by_election.values()):
        raise PromotionError("each anonymous election must contain 92 territories")

    candidates = []
    for permutation in ((years[0], years[1]), (years[1], years[0])):
        mapping: dict[tuple[str, str], PublicTerritory] = {}
        costs: list[float] = []
        for election, year in zip(elections, permutation):
            keys = by_election[election]
            targets = list(public[year])
            matrix = [
                [fingerprint_cost(anonymous[key], target) for target in targets]
                for key in keys
            ]
            assignment = hungarian(matrix)
            for row_index, column_index in enumerate(assignment):
                mapping[keys[row_index]] = targets[column_index]
                costs.append(matrix[row_index][column_index])
        candidates.append((sum(costs), permutation, mapping, costs))
    _, permutation, mapping, costs = min(candidates, key=lambda item: item[0])
    audit = {
        "election_to_year": dict(zip(elections, permutation)),
        "mean_cost": statistics.mean(costs),
        "median_cost": statistics.median(costs),
        "max_cost": max(costs),
    }
    return mapping, audit


def choose_reference_match(
    e0_by_condition: Mapping[tuple[str, str, str], TerritoryAggregate],
    template: Mapping[str, Any],
) -> tuple[
    str,
    dict[tuple[str, str], tuple[float, dict[str, float]]],
    dict[tuple[str, str], PublicTerritory],
    dict[str, Any],
]:
    modes = (
        "average_expected_vote",
        "condition0_expected_vote",
        "condition1_expected_vote",
        "average_mean_probability",
        "condition0_mean_probability",
        "condition1_mean_probability",
    )
    public = public_territories(template)
    candidates = []
    for mode in modes:
        anonymous = combine_conditions(e0_by_condition, mode)
        mapping, audit = match_territories_for_mode(anonymous, public)
        candidates.append((audit["mean_cost"], mode, anonymous, mapping, audit))
    _, mode, anonymous, mapping, audit = min(candidates, key=lambda item: item[0])
    audit = dict(audit)
    audit["aggregation_mode"] = mode
    audit["alternative_mean_costs"] = {
        candidate[1]: candidate[4]["mean_cost"] for candidate in candidates
    }
    return mode, anonymous, mapping, audit


def party_mapping(
    e0_shares: Mapping[str, float], public_simulation: Mapping[str, float]
) -> tuple[dict[str, str], dict[str, float]]:
    qids = sorted(e0_shares)
    labels = sorted(public_simulation)
    if len(qids) != len(labels):
        raise PromotionError("E0 Q parties and public party labels have different widths")
    matrix = [
        [abs(float(e0_shares[q]) - float(public_simulation[label])) for label in labels]
        for q in qids
    ]
    assignment = hungarian(matrix)
    mapping = {qids[i]: labels[column] for i, column in enumerate(assignment)}
    residuals = {qids[i]: matrix[i][column] for i, column in enumerate(assignment)}
    values = sorted(float(value) for value in public_simulation.values())
    gaps = [abs(values[i + 1] - values[i]) for i in range(len(values) - 1)]
    min_gap = min(gaps) if gaps else 1.0
    audit = {
        "max_residual": max(residuals.values()) if residuals else 0.0,
        "mean_residual": statistics.mean(residuals.values()) if residuals else 0.0,
        "min_public_value_gap": min_gap,
    }
    return mapping, audit


def build_g0_maroc(
    *,
    tasks: Sequence[R.FrozenTask],
    g0_run: pathlib.Path,
    e0_run: pathlib.Path,
    template_path: pathlib.Path,
    max_match_mean: float,
    max_match_cost: float,
    max_party_residual: float,
    ambiguity_epsilon: float,
) -> tuple[dict[str, Any], dict[str, Any]]:
    template = read_json(template_path)
    e0_condition = aggregate_by_condition(tasks, e0_run)
    g0_condition = aggregate_by_condition(tasks, g0_run)
    mode, e0_combined, territory_match, audit = choose_reference_match(
        e0_condition, template
    )
    if audit["mean_cost"] > max_match_mean or audit["max_cost"] > max_match_cost:
        raise PromotionError(
            "territory mapping is not exact enough: "
            f"mean={audit['mean_cost']:.8f}, max={audit['max_cost']:.8f}"
        )
    g0_combined = combine_conditions(g0_condition, mode)
    output = json.loads(json.dumps(template))
    mapping_audits = []
    for anonymous_key, public_territory in territory_match.items():
        e0_turnout, e0_shares = e0_combined[anonymous_key]
        g0_turnout, g0_shares = g0_combined[anonymous_key]
        mapping, paudit = party_mapping(e0_shares, public_territory.simulation)
        if paudit["max_residual"] > max_party_residual:
            raise PromotionError(
                f"party mapping residual too high for {anonymous_key}: {paudit}"
            )
        if paudit["min_public_value_gap"] < ambiguity_epsilon:
            raise PromotionError(
                f"party mapping ambiguous for {anonymous_key}: minimum gap "
                f"{paudit['min_public_value_gap']:.10f}"
            )
        mapped = {mapping[q]: float(g0_shares[q]) for q in sorted(g0_shares)}
        mapped_total = sum(mapped.values())
        mapped = {label: value / mapped_total for label, value in mapped.items()}
        target = output["years"][public_territory.year]["territories"][public_territory.index]
        target["turnout_sim"] = float(g0_turnout)
        target["simulation"] = mapped
        target["leader_sim"] = max(mapped, key=mapped.get)
        target["parties"] = sorted(mapped, key=lambda label: (-mapped[label], label))
        mapping_audits.append(
            {
                "anonymous_election_id": anonymous_key[0],
                "anonymous_territory_id": anonymous_key[1],
                "public": public_territory.label,
                "e0_turnout": e0_turnout,
                "g0_turnout": g0_turnout,
                "party_mapping": mapping,
                "party_mapping_audit": paudit,
            }
        )
    audit["party_mapping_max_residual"] = max(
        item["party_mapping_audit"]["max_residual"] for item in mapping_audits
    )
    audit["party_mapping_min_gap"] = min(
        item["party_mapping_audit"]["min_public_value_gap"] for item in mapping_audits
    )
    audit["territories_mapped"] = len(mapping_audits)
    audit["mappings"] = mapping_audits
    output.setdefault("meta", {})["simulation_reference_id"] = "G0_CHATGPT_GPT56_TERRA"
    output["meta"]["simulation_reference_kind"] = "CHATGPT_ACCOUNT_GPT_BASELINE"
    output["meta"]["simulation_historically_scored"] = False
    return output, audit


def file_record(path: pathlib.Path) -> dict[str, Any]:
    return {"path": str(path), "sha256": R.sha256_file(path), "bytes": path.stat().st_size}


def backup_e0(web_data: pathlib.Path) -> None:
    backup = web_data / "reference" / "e0"
    backup.mkdir(parents=True, exist_ok=True)
    for name in (
        "societe.json",
        "portraits.json",
        "simulateur.json",
        "maroc.json",
        "reference_provenance.json",
    ):
        source = web_data / name
        target = backup / name
        if source.is_file() and not target.exists():
            copy_file(source, target)


def apply_preview(preview: pathlib.Path, web_data: pathlib.Path) -> None:
    backup_e0(web_data)
    g0_reference = web_data / "reference" / "g0"
    g0_reference.mkdir(parents=True, exist_ok=True)
    for name in (
        "societe.json",
        "portraits.json",
        "g0_simulator.json",
        "reference_provenance.json",
        "promotion_audit.json",
    ):
        source = preview / name
        if source.is_file():
            copy_file(source, g0_reference / name)
            copy_file(source, web_data / name)
    maroc = preview / "maroc.json"
    if maroc.is_file():
        copy_file(maroc, g0_reference / "maroc.json")
        copy_file(maroc, web_data / "maroc.json")


def build_provenance(
    *,
    state: Mapping[str, Any],
    run_root: pathlib.Path,
    preview: pathlib.Path,
    map_status: str,
    territory_audit: Mapping[str, Any] | None,
) -> dict[str, Any]:
    files = {
        name: file_record(preview / name)
        for name in ("societe.json", "portraits.json", "g0_simulator.json")
    }
    if (preview / "maroc.json").is_file():
        files["maroc.json"] = file_record(preview / "maroc.json")
    return {
        "schema_version": "ATLAS_PUBLIC_REFERENCE_PROVENANCE_V2",
        "primary_reference_id": "G0_CHATGPT_GPT56_TERRA",
        "primary_reference_kind": "CHATGPT_ACCOUNT_GPT_BASELINE",
        "status": "GPT_GENERATED_COMPLETE_PENDING_BLIND_HISTORICAL_SCORING",
        "model": state["model"],
        "reasoning_effort": state["reasoning_effort"],
        "auth_mode": "CHATGPT_MANAGED_CODEX_LOGIN",
        "api_key_used": False,
        "fresh_context_per_work_item": True,
        "public_rows": EXPECTED_ROWS,
        "public_work_items": EXPECTED_WORK_ITEMS,
        "g0_available": True,
        "g0_simulator_path": "data/g0_simulator.json",
        "interactive_explainer_kind": "EMPIRICAL_NEAREST_NEIGHBOUR_OVER_FROZEN_GPT_DECISIONS",
        "territorial_map_status": map_status,
        "territorial_mapping_audit": territory_audit,
        "source_run": {
            "run_state_sha256": R.sha256_file(run_root / "run_state.json"),
            "output_manifest_sha256": R.sha256_file(run_root / "output_manifest.json"),
            "terminal": state["status"],
        },
        "derived_files": files,
        "labels": {
            "short": "G0 · référence GPT via compte ChatGPT",
            "long": (
                "Les chiffres affichés proviennent de 94 208 décisions générées dans "
                "2 944 contextes GPT éphémères, authentifiés par le compte ChatGPT du "
                "propriétaire. E0 reste disponible comme contrôle déterministe. Cette "
                "génération n’est pas encore une preuve de justesse prédictive avant le "
                "backtest historique aveugle."
            ),
        },
        "scientific_claim": "GPT_GENERATED_BEHAVIOURAL_BASELINE_NOT_YET_VALIDATED_AS_PREDICTIVE",
        "e0_retained_after_g0": True,
        "social_lambdas_status": "ILLUSTRATIVE_NOT_CALIBRATED",
        "outcomes_opened_during_generation": False,
    }


def main(argv: Sequence[str] | None = None) -> int:
    default_source_v2 = HERE.parent
    default_web = default_source_v2 / "web"
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", required=True, type=pathlib.Path)
    ap.add_argument("--run", required=True, type=pathlib.Path)
    ap.add_argument("--web-root", type=pathlib.Path, default=default_web)
    ap.add_argument(
        "--e0-run",
        type=pathlib.Path,
        help="extracted deterministic E0 output root; required to promote the named territorial map",
    )
    ap.add_argument("--preview-dir", type=pathlib.Path)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-territory-mean-cost", type=float, default=0.0025)
    ap.add_argument("--max-territory-cost", type=float, default=0.02)
    ap.add_argument("--max-party-residual", type=float, default=0.005)
    ap.add_argument("--party-ambiguity-epsilon", type=float, default=1e-8)
    args = ap.parse_args(argv)

    env_root = args.env.expanduser().resolve()
    run_root = args.run.expanduser().resolve()
    web_root = args.web_root.expanduser().resolve()
    source_v2 = web_root.parent
    if not (web_root / "data").is_dir():
        raise PromotionError(f"web data directory not found under {web_root}")

    state, manifest = load_complete_run(run_root)
    tasks, _, prompt_path, schema_path = verify_outputs(
        env_root, run_root, state, manifest
    )
    preview = (
        args.preview_dir.expanduser().resolve()
        if args.preview_dir
        else run_root / "promotion_preview"
    )
    if preview.exists():
        shutil.rmtree(preview)
    preview.mkdir(parents=True)

    run_derivation(source_v2, env_root, run_root, preview)
    simulator = build_g0_simulator(
        tasks=tasks,
        run_root=run_root,
        source_v2=source_v2,
        state=state,
    )
    write_json(preview / "g0_simulator.json", simulator, pretty=False)

    map_status = "E0_DETERMINISTIC_MAP_RETAINED_E0_RUN_NOT_SUPPLIED"
    territory_audit = None
    if args.e0_run:
        e0_run = args.e0_run.expanduser().resolve()
        maroc, territory_audit = build_g0_maroc(
            tasks=tasks,
            g0_run=run_root,
            e0_run=e0_run,
            template_path=web_root / "data" / "maroc.json",
            max_match_mean=args.max_territory_mean_cost,
            max_match_cost=args.max_territory_cost,
            max_party_residual=args.max_party_residual,
            ambiguity_epsilon=args.party_ambiguity_epsilon,
        )
        write_json(preview / "maroc.json", maroc, pretty=False)
        write_json(preview / "territory_mapping_audit.json", territory_audit)
        map_status = "G0_CHATGPT_GPT_BASELINE_PROMOTED"

    provenance = build_provenance(
        state=state,
        run_root=run_root,
        preview=preview,
        map_status=map_status,
        territory_audit=(
            {
                key: value
                for key, value in territory_audit.items()
                if key != "mappings"
            }
            if territory_audit
            else None
        ),
    )
    write_json(preview / "reference_provenance.json", provenance)
    audit = {
        "schema_version": "ATLAS_G0_FRONTEND_PROMOTION_AUDIT_V1",
        "status": "PASS_PREVIEW_READY" if not args.apply else "PASS_APPLIED",
        "generated_at": R.utc_now(),
        "model": state["model"],
        "reasoning_effort": state["reasoning_effort"],
        "work_items": EXPECTED_WORK_ITEMS,
        "rows": EXPECTED_ROWS,
        "prompt_sha256": R.sha256_file(prompt_path),
        "row_schema_sha256": R.sha256_file(schema_path),
        "run_state_sha256": R.sha256_file(run_root / "run_state.json"),
        "output_manifest_sha256": R.sha256_file(run_root / "output_manifest.json"),
        "map_status": map_status,
        "preview_files": {
            path.name: file_record(path)
            for path in sorted(preview.iterdir())
            if path.is_file()
        },
    }
    write_json(preview / "promotion_audit.json", audit)

    if args.apply:
        apply_preview(preview, web_root / "data")
        print("PASS_G0_CHATGPT_REFERENCE_PROMOTED_TO_FRONTEND")
    else:
        print(f"PASS_G0_PROMOTION_PREVIEW_READY {preview}")
        print("Re-run with --apply only after reviewing promotion_audit.json.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PromotionError, R.RunnerError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
