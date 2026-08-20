from __future__ import annotations

from observatory_base import *
from observatory_evidence import *

def derived_decision_fields(
    voter: Mapping[str, Any], decision: Mapping[str, Any]
) -> dict[str, Any]:
    top, top_p, runner, runner_p = top_two(decision)
    turnout = float(decision["turnout_probability"])
    margin = top_p - runner_p
    return {
        "decision_sha256": decision_digest(decision),
        "top_party_id": top,
        "runner_up_party_id": runner,
        "top_party_probability": top_p,
        "runner_up_probability": runner_p,
        "decision_margin": margin,
        "turnout_probability": turnout,
        "participation_posture": participation_posture(turnout),
        "transition_type": transition_type(voter, decision),
        "decision_certainty_band": certainty_band(margin),
    }


def _hash_rank(task_id: str, archetype_id: str) -> str:
    return hashlib.sha256((task_id + "|" + archetype_id + "|ATLAS_PANEL_V1").encode()).hexdigest()


def select_panel(
    task: R.FrozenTask,
    decisions: Sequence[Mapping[str, Any]],
    scope: str,
) -> list[SelectedVoter]:
    if len(decisions) != len(task.expected_rows):
        raise ObservatoryError("decision/voter row count mismatch")
    pairs = list(enumerate(zip(task.expected_rows, decisions)))
    if scope == "all":
        return [
            SelectedVoter("ALL", index, dict(voter), dict(decision))
            for index, (voter, decision) in pairs
        ]
    if scope != "panel":
        raise ObservatoryError("scope must be all or panel")

    selected: dict[int, str] = {}
    anchor = min(
        pairs,
        key=lambda pair: _hash_rank(
            task.task_id,
            str(pair[1][1]["weighted_archetype_id"]),
        ),
    )[0]
    selected[anchor] = "HASH_ANCHOR"

    swing = min(
        pairs,
        key=lambda pair: (
            derived_decision_fields(pair[1][0], pair[1][1])["decision_margin"],
            str(pair[1][1]["weighted_archetype_id"]),
        ),
    )[0]
    selected.setdefault(swing, "SWING")

    turnout = min(
        pairs,
        key=lambda pair: (
            abs(float(pair[1][1]["turnout_probability"]) - 0.5),
            str(pair[1][1]["weighted_archetype_id"]),
        ),
    )[0]
    selected.setdefault(turnout, "TURNOUT_PIVOT")

    switches = [
        pair
        for pair in pairs
        if transition_type(pair[1][0], pair[1][1]) == "SWITCH"
    ]
    if switches:
        strongest = max(
            switches,
            key=lambda pair: (
                top_two(pair[1][1])[1],
                -derived_decision_fields(pair[1][0], pair[1][1])["decision_margin"],
                str(pair[1][1]["weighted_archetype_id"]),
            ),
        )[0]
    else:
        strongest = min(
            pairs,
            key=lambda pair: (
                _hash_rank(task.task_id + "|switch_fallback", str(pair[1][1]["weighted_archetype_id"])),
            ),
        )[0]
    selected.setdefault(strongest, "STRONGEST_SWITCH")

    result = []
    for index in sorted(selected):
        voter, decision = pairs[index][1]
        result.append(SelectedVoter(selected[index], index, dict(voter), dict(decision)))
    return result


def select_counterfactual_panel(
    task: R.FrozenTask,
    decisions: Sequence[Mapping[str, Any]],
    panel_names: Sequence[str],
) -> list[SelectedVoter]:
    all_panel = select_panel(task, decisions, "panel")
    by_panel = {item.panel: item for item in all_panel}
    selected = [by_panel[name] for name in panel_names if name in by_panel]
    dedup: dict[str, SelectedVoter] = {}
    for item in selected:
        dedup.setdefault(item.archetype_id, item)
    return list(dedup.values())


def load_deliberation_base_schema(path: pathlib.Path) -> dict[str, Any]:
    schema = load_json(path)
    if schema.get("$id") != "ATLAS_G0_DELIBERATION_OUTPUT_SCHEMA_V1":
        raise ObservatoryError("unexpected deliberation schema")
    return schema


def dynamic_deliberation_schema(
    base_schema: Mapping[str, Any],
    task: R.FrozenTask,
    selected: Sequence[SelectedVoter],
) -> dict[str, Any]:
    schema = copy.deepcopy(base_schema)
    rows = schema["properties"]["rows"]
    rows["minItems"] = len(selected)
    rows["maxItems"] = len(selected)
    item = rows["items"]
    props = item["properties"]
    fixed = {
        "anonymous_election_id": task.election_id,
        "anonymous_territory_id": task.territory_id,
        "condition_id": task.condition_id,
        "batch_id": task.batch_id,
    }
    for key, value in fixed.items():
        props[key] = {"type": "string", "enum": [value]}
    archetypes = [item_.archetype_id for item_ in selected]
    props["weighted_archetype_id"] = {"type": "string", "enum": archetypes}
    props["top_party_id"] = {"type": "string", "enum": list(task.available_party_ids)}
    props["runner_up_party_id"] = {"type": "string", "enum": list(task.available_party_ids)}
    props["central_conflict"]["properties"]["factor_a"]["enum"] = list(FACTORS)
    props["central_conflict"]["properties"]["factor_b"]["enum"] = list(FACTORS)
    driver_props = props["drivers"]["items"]["properties"]
    driver_props["factor"]["enum"] = list(FACTORS)
    flip = props["minimum_flip_hypothesis"]["properties"]
    flip["target_party_id"] = {"type": "string", "enum": list(task.available_party_ids)}
    flip["lever"]["enum"] = list(FACTORS)
    turnout = props["minimum_turnout_hypothesis"]["properties"]
    turnout["lever"]["enum"] = list(FACTORS)
    return schema


def build_deliberation_request(
    *,
    prompt: str,
    task: R.FrozenTask,
    selected: Sequence[SelectedVoter],
) -> str:
    context = task_context(task)
    rows = []
    for item in selected:
        rows.append(
            {
                "panel": item.panel,
                "voter": item.voter,
                "frozen_D0_decision": item.decision,
                "derived_immutable_fields": derived_decision_fields(item.voter, item.decision),
                "evidence_catalogue": evidence_catalogue(task, item.voter, item.decision),
            }
        )
    payload = {
        "task_identity": {
            "anonymous_election_id": task.election_id,
            "anonymous_territory_id": task.territory_id,
            "condition_id": task.condition_id,
            "batch_id": task.batch_id,
        },
        "anonymous_context": context,
        "selected_voters_in_required_order": rows,
    }
    return "\n".join(
        (
            "FROZEN OBSERVABLE-DELIBERATION PROMPT — USE VERBATIM:",
            prompt,
            "",
            "REQUEST PAYLOAD:",
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
    )


def validate_deliberations(
    value: Any,
    task: R.FrozenTask,
    selected: Sequence[SelectedVoter],
) -> list[dict[str, Any]]:
    if not isinstance(value, dict) or set(value) != {"rows"}:
        raise DeliberationValidationError('output must be exactly {"rows":[...]}')
    rows = value["rows"]
    if not isinstance(rows, list) or len(rows) != len(selected):
        raise DeliberationValidationError("deliberation row count mismatch")
    validated = []
    for index, (raw, selected_item) in enumerate(zip(rows, selected)):
        if not isinstance(raw, dict):
            raise DeliberationValidationError(f"row {index}: not an object")
        row = dict(raw)
        expected_identity = {
            "anonymous_election_id": task.election_id,
            "anonymous_territory_id": task.territory_id,
            "condition_id": task.condition_id,
            "batch_id": task.batch_id,
            "weighted_archetype_id": selected_item.archetype_id,
        }
        for key, expected in expected_identity.items():
            if str(row.get(key)) != expected:
                raise DeliberationValidationError(f"row {index}: {key} mismatch")
        derived = derived_decision_fields(selected_item.voter, selected_item.decision)
        for key, expected in derived.items():
            if key.endswith("probability") or key == "decision_margin":
                if not exact_float(row.get(key), expected):
                    raise DeliberationValidationError(f"row {index}: {key} changed")
            elif row.get(key) != expected:
                raise DeliberationValidationError(f"row {index}: {key} mismatch")
        if row.get("top_party_id") == row.get("runner_up_party_id"):
            raise DeliberationValidationError(f"row {index}: top and runner-up identical")
        if row.get("unsupported_claims_detected") is not False:
            raise DeliberationValidationError(f"row {index}: unsupported claim flag")
        if row.get("self_reported_confidence") not in CERTAINTY:
            raise DeliberationValidationError(f"row {index}: invalid confidence")
        conflict = row.get("central_conflict") or {}
        if conflict.get("factor_a") not in FACTORS or conflict.get("factor_b") not in FACTORS:
            raise DeliberationValidationError(f"row {index}: invalid conflict factors")
        if conflict.get("factor_a") == conflict.get("factor_b"):
            raise DeliberationValidationError(f"row {index}: conflict factors identical")
        catalogue = evidence_catalogue(task, selected_item.voter, selected_item.decision)
        allowed_evidence = {entry["evidence_id"]: entry for entry in catalogue}
        drivers = row.get("drivers")
        if not isinstance(drivers, list) or not 2 <= len(drivers) <= 5:
            raise DeliberationValidationError(f"row {index}: invalid drivers")
        for driver in drivers:
            if driver.get("factor") not in FACTORS:
                raise DeliberationValidationError(f"row {index}: invalid driver factor")
            if driver.get("direction") not in DRIVER_DIRECTIONS:
                raise DeliberationValidationError(f"row {index}: invalid driver direction")
            if driver.get("strength") not in STRENGTHS:
                raise DeliberationValidationError(f"row {index}: invalid driver strength")
            evidence_ids = driver.get("evidence_ids")
            if not isinstance(evidence_ids, list) or not evidence_ids:
                raise DeliberationValidationError(f"row {index}: driver lacks evidence")
            unknown = set(map(str, evidence_ids)) - set(allowed_evidence)
            if unknown:
                raise DeliberationValidationError(f"row {index}: unknown evidence {sorted(unknown)}")
            if any(not allowed_evidence[str(eid)]["directional"] for eid in evidence_ids):
                raise DeliberationValidationError(f"row {index}: non-directional evidence cited")
        for key in ("minimum_flip_hypothesis", "minimum_turnout_hypothesis"):
            hypothesis = row.get(key) or {}
            if hypothesis.get("lever") not in FACTORS:
                raise DeliberationValidationError(f"row {index}: invalid {key} lever")
            evidence_ids = hypothesis.get("evidence_ids") or []
            unknown = set(map(str, evidence_ids)) - set(allowed_evidence)
            if unknown:
                raise DeliberationValidationError(f"row {index}: unknown hypothesis evidence")
        if row["minimum_flip_hypothesis"].get("target_party_id") != derived["runner_up_party_id"]:
            raise DeliberationValidationError(f"row {index}: flip target must be D0 runner-up")
        row["panel"] = selected_item.panel
        row["evidence_catalogue_sha256"] = R.sha256_json(catalogue)
        validated.append(row)
    return validated
