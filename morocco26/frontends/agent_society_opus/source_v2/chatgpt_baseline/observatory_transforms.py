from __future__ import annotations

from observatory_base import *
from observatory_evidence import *
from observatory_selection import *
from observatory_exec import *

def find_offer_card(context: MutableMapping[str, Any], party: str) -> MutableMapping[str, Any]:
    cards = (context.get("election_environment_card") or {}).get("party_offer_cards") or []
    for card in cards:
        if str(card.get("anonymous_party_id")) == party:
            return card
    raise ObservatoryError(f"party offer card missing for {party}")


def find_local_card(context: MutableMapping[str, Any], party: str) -> MutableMapping[str, Any]:
    cards = (context.get("common_territory_card") or {}).get("party_context_cards") or []
    for card in cards:
        if str(card.get("anonymous_party_id")) == party:
            return card
    raise ObservatoryError(f"local party card missing for {party}")


def set_local_feature(
    card: MutableMapping[str, Any],
    feature_id: str,
    value: Any,
    *,
    status: str = "VERIFIED",
    conflict: bool = False,
) -> None:
    features = card.setdefault("features", [])
    for feature in features:
        if str(feature.get("feature_id")) == feature_id:
            feature["status"] = status
            feature["value"] = value
            feature["conflict"] = conflict
            return
    features.append(
        {
            "feature_id": feature_id,
            "status": status,
            "value": value,
            "conflict": conflict,
        }
    )


def government_status(context: Mapping[str, Any], party: str) -> str:
    return str((party_offer_lookup(context).get(party) or {}).get("government_status") or "UNKNOWN")


def apply_scenario(
    *,
    task: R.FrozenTask,
    selected: SelectedVoter,
    scenario: str,
) -> tuple[R.FrozenTask, dict[str, Any]]:
    if scenario not in SCENARIOS:
        raise ObservatoryError(f"unknown scenario {scenario}")
    voter = copy.deepcopy(selected.voter)
    context = task_context(task)
    top, _, runner, _ = top_two(selected.decision)
    changes = []

    if scenario == "PRIOR_ANCHOR_ALTERNATIVE":
        before = voter.get("prior_vote_or_abstention")
        after = runner if str(before) == top else top
        voter["prior_vote_or_abstention"] = after
        changes.append({"path": "voter.prior_vote_or_abstention", "before": before, "after": after})

    elif scenario == "GOVERNMENT_OUTLOOK_REVERSE":
        sign = -1.0 if government_status(context, top) == "INCUMBENT_COALITION" else 1.0
        shifts = {
            "latent_attitude_government_economic_performance_mean": 0.25,
            "latent_attitude_government_poverty_performance_mean": 0.25,
            "latent_attitude_government_anticorruption_performance_mean": 0.25,
            "latent_attitude_democracy_satisfaction_mean": 0.15,
            "latent_attitude_economic_condition_mean": 0.10,
        }
        for field, amount in shifts.items():
            before = float(voter.get(field, 0.5))
            after = clamp(before + sign * amount)
            voter[field] = after
            changes.append({"path": "voter." + field, "before": before, "after": after})

    elif scenario == "RUNNER_LOCAL_STRENGTH":
        card = find_local_card(context, runner)
        updates = {
            "CANDIDATE_REGISTERED_RANK": 1,
            "FORMER_MP": True,
            "LOCAL_EXECUTIVE_OFFICE": True,
            "PROVINCIAL_OR_REGIONAL_OFFICE": True,
            "WITHDRAWN_OR_DISQUALIFIED": False,
            "OFFICIAL_SANCTION_OR_INVESTIGATION": False,
            "VERIFIED_DEATH_OR_INCAPACITY": False,
        }
        before_lookup = {
            str(feature.get("feature_id")): copy.deepcopy(feature)
            for feature in card.get("features") or []
        }
        for feature_id, value in updates.items():
            set_local_feature(card, feature_id, value)
            changes.append(
                {
                    "path": f"context.local.{runner}.{feature_id}",
                    "before": before_lookup.get(feature_id),
                    "after": {"status": "VERIFIED", "value": value, "conflict": False},
                }
            )

    elif scenario == "TOP_RUNNER_PROGRAM_SWAP":
        top_card = find_offer_card(context, top)
        runner_card = find_offer_card(context, runner)
        top_program = copy.deepcopy(top_card.get("program_priority_levels") or {})
        runner_program = copy.deepcopy(runner_card.get("program_priority_levels") or {})
        top_card["program_priority_levels"] = runner_program
        runner_card["program_priority_levels"] = top_program
        changes.extend(
            [
                {
                    "path": f"context.program.{top}",
                    "before": top_program,
                    "after": runner_program,
                },
                {
                    "path": f"context.program.{runner}",
                    "before": runner_program,
                    "after": top_program,
                },
            ]
        )

    elif scenario == "NONINFORMATIVE_METADATA_PLACEBO":
        nonce = hashlib.sha256(
            (task.task_id + "|" + selected.archetype_id + "|PLACEBO_V1").encode()
        ).hexdigest()[:24]
        context["diagnostic_metadata"] = {
            "noninformative_placebo_nonce": nonce,
            "explicitly_nonpolitical": True,
            "must_not_be_used_as_directional_evidence": True,
        }
        changes.append(
            {
                "path": "context.diagnostic_metadata",
                "before": None,
                "after": copy.deepcopy(context["diagnostic_metadata"]),
            }
        )

    packet = {
        "schema_version": "ATLAS_G0_COUNTERFACTUAL_PACKET_V1",
        "anonymous_election_id": task.election_id,
        "anonymous_territory_id": task.territory_id,
        "condition_id": task.condition_id,
        "batch_id": task.batch_id,
        "available_party_ids": list(task.available_party_ids),
        "context": context,
        "voter_batch": {
            "anonymous_election_id": task.election_id,
            "anonymous_territory_id": task.territory_id,
            "batch_id": task.batch_id,
            "available_party_ids": list(task.available_party_ids),
            "voter_archetypes": [voter],
        },
    }
    cf_id = scenario + "__" + selected.archetype_id
    cf_task = R.FrozenTask(
        task_id=task.task_id + "__" + cf_id,
        packet=packet,
        expected_rows=(voter,),
        available_party_ids=task.available_party_ids,
        output_relpath=str(
            pathlib.PurePosixPath("counterfactuals")
            / task.election_id
            / task.condition_id
            / task.territory_id
            / task.batch_id
            / selected.archetype_id
            / (scenario + ".jsonl")
        ),
        source_paths=task.source_paths,
        source_sha256=R.sha256_json(
            {
                "original_source_sha256": task.source_sha256,
                "scenario": scenario,
                "archetype_id": selected.archetype_id,
                "changes": changes,
            }
        ),
    )
    manifest = {
        "schema_version": "ATLAS_G0_COUNTERFACTUAL_TRANSFORM_V1",
        "scenario_id": scenario,
        "task_id": task.task_id,
        "archetype_id": selected.archetype_id,
        "panel": selected.panel,
        "D0_decision_sha256": decision_digest(selected.decision),
        "D0_top_party_id": top,
        "D0_runner_up_party_id": runner,
        "changes": changes,
        "modified_packet_sha256": R.sha256_json(packet),
        "synthetic_diagnostic_not_observed_fact": True,
    }
    return cf_task, manifest


def counterfactual_context(
    frozen_decision_prompt: str,
    row_schema: Mapping[str, Any],
    cf_task: R.FrozenTask,
    manifest: Mapping[str, Any],
) -> str:
    return "\n".join(
        (
            "COUNTERFACTUAL DIAGNOSTIC BOUNDARY:",
            "The packet below is a synthetic diagnostic perturbation. Judge the supplied voter independently under the modified packet. Do not compare with, recover or mention the original decision. Diagnostic metadata explicitly marked non-political is not evidence.",
            "",
            "FROZEN D0 DECISION PROMPT — APPLY TO THE MODIFIED PACKET:",
            frozen_decision_prompt,
            "",
            "TRANSFORM MANIFEST:",
            json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "",
            "ROW SCHEMA:",
            json.dumps(row_schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "",
            "MODIFIED PACKET:",
            json.dumps(cf_task.packet, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "",
            'Return exactly {"rows":[ONE_ROW]} and no prose.',
        )
    )


def counterfactual_output_path(output_root: pathlib.Path, cf_task: R.FrozenTask) -> pathlib.Path:
    return output_root / pathlib.Path(*pathlib.PurePosixPath(cf_task.output_relpath).parts)
