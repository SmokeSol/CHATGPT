#!/usr/bin/env python3
"""Run the rich historical semi-blind startup without duplicating evidence values.

The exact V5 full-environment packet remains the sole model-visible source of
candidate/programme values. This wrapper adds only:

* an interpretation contract;
* JSON pointers to the already-present cards;
* deterministic awareness instructions derived from fields already in each voter;
* provenance hashes.

It delegates exact bundle/main-bridge/model gates to run_g0_sol_main_bridge.py.
"""
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any, Mapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[4]
SCRIPTS = REPO_ROOT / "morocco26" / "scripts"
for path in (HERE, SCRIPTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import run_chatgpt_baseline as runner  # noqa: E402
import run_g0_sol_main_bridge as bridge_runner  # noqa: E402
from three_regime_core import (  # noqa: E402
    GOAL_ID,
    REGIME_HISTORICAL,
    ThreeRegimeError,
    read_json,
    sha256_file,
    validate_historical_contract,
)

PROTOCOL_ID = "ATLAS_CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V4_THREE_REGIME"


def pop_option(args: list[str], name: str) -> str:
    for index, value in enumerate(list(args)):
        if value == name:
            if index + 1 >= len(args):
                raise runner.RunnerError(f"{name} requires a value")
            result = args[index + 1]
            del args[index:index + 2]
            return result
        if value.startswith(name + "="):
            result = value.split("=", 1)[1]
            args.remove(value)
            return result
    raise runner.RunnerError(f"{name} is mandatory for {REGIME_HISTORICAL}")


def load_contract_index(path: pathlib.Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any], str]:
    path = path.expanduser().resolve()
    index = read_json(path)
    checks = {
        "regime": index.get("regime") == REGIME_HISTORICAL,
        "status": index.get("status") == "PASS_HISTORICAL_SEMIBLIND_RICH_POINTER_CONTRACTS_READY",
        "packet_mutation": index.get("model_packet_mutated") is False,
        "value_duplication": index.get("model_packet_values_duplicated") is False,
        "outcomes": index.get("target_outcomes_read") is False,
        "identities": index.get("real_identity_material_written") is False,
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise runner.RunnerError(f"historical contract index gate failed: {failed}")
    contracts: dict[str, dict[str, Any]] = {}
    root = path.parent.parent
    for item in index.get("contracts") or []:
        relative = str(item.get("contract_path") or "")
        contract_path = root / relative
        if not contract_path.is_file():
            raise runner.RunnerError(f"historical contract missing: {contract_path}")
        if sha256_file(contract_path) != item.get("contract_sha256"):
            raise runner.RunnerError(f"historical contract hash mismatch: {contract_path}")
        contract = read_json(contract_path)
        try:
            validate_historical_contract(contract, strict_shape=True)
        except ThreeRegimeError as exc:
            raise runner.RunnerError(str(exc)) from exc
        key = "|".join(
            (
                str(contract["anonymous_election_id"]),
                str(contract["condition_id"]),
                str(contract["anonymous_territory_id"]),
            )
        )
        if key in contracts:
            raise runner.RunnerError(f"duplicate historical reading contract: {key}")
        contracts[key] = contract
    expected_contracts = 368
    scope = (index.get("historical_controls") or {}).get("scope") or (
        "DEVELOPMENT_ONLY_P1_PILOT"
        if len(contracts) == 184
        and all(k.startswith("E_563101AA29400273|") for k in contracts)
        else None
    )
    if scope == "DEVELOPMENT_ONLY_P1_PILOT":
        expected_contracts = 184
    if len(contracts) != expected_contracts:
        raise runner.RunnerError(f"historical contract count {len(contracts)} != {expected_contracts}")
    return contracts, index, sha256_file(path)


def install_reading_contract(
    contracts: Mapping[str, Mapping[str, Any]],
    index: Mapping[str, Any],
    index_sha256: str,
    index_path: pathlib.Path,
) -> None:
    original_build_context = runner.build_context
    original_write_state = runner.write_run_state

    def build_context(frozen_prompt: str, row_schema: Mapping[str, Any], task: runner.FrozenTask) -> str:
        key = "|".join((task.election_id, task.condition_id, task.territory_id))
        contract = contracts.get(key)
        if contract is None:
            raise runner.RunnerError(f"no semiblind reading contract for {key}")
        if contract.get("source_context_sha256") not in task.source_sha256:
            # task.source_sha256 is a compound canonical hash, so direct containment is
            # not guaranteed. The exact file binding is already proven by index hashes;
            # retain this explicit provenance note instead of pretending otherwise.
            binding_note = "SOURCE_CONTEXT_BOUND_BY_CONTRACT_INDEX_AND_MAIN_BRIDGE"
        else:
            binding_note = "SOURCE_CONTEXT_DIRECT_HASH_MATCH"
        pointer_cards = [
            {
                "anonymous_party_id": card["anonymous_party_id"],
                "anonymous_candidate_id": card["anonymous_candidate_id"],
                "candidate_card_json_pointer": card["candidate_card_json_pointer"],
                "programme_card_json_pointer": card["programme_card_json_pointer"],
                "candidate_feature_ids": card["candidate_feature_ids"],
                "programme_axis_ids": card["programme_axis_ids"],
            }
            for card in contract["cards"]
        ]
        preamble = {
            "goal_id": GOAL_ID,
            "regime": REGIME_HISTORICAL,
            "binding": binding_note,
            "contract_index_sha256": index_sha256,
            "model_packet_values_duplicated": False,
            "real_identity_material_present": False,
            "target_outcomes_present": False,
            "reading_instruction": contract["reading_instruction"],
            "awareness_rule": {
                "inputs_already_in_voter_row": [
                    "prior_vote_or_abstention",
                    "latent_attitude_political_discussion_mean",
                ],
                "LOW": "recognize the ballot options and salient verified local/programme signals; do not act omniscient",
                "MEDIUM": "compare core verified candidate and programme signals",
                "HIGH": "use the full verified 16-feature/18-axis surface",
                "protected_or_demographic_fields_used_for_awareness": [],
            },
            "pointer_cards": pointer_cards,
        }
        return "\n".join(
            (
                "THREE-REGIME HISTORICAL SEMIBLIND READING CONTRACT:",
                json.dumps(preamble, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "",
                original_build_context(frozen_prompt, row_schema, task),
            )
        )

    def write_state(**kwargs):
        original_write_state(**kwargs)
        output_root = pathlib.Path(kwargs["output_root"])
        metadata = {
            "goal_id": GOAL_ID,
            "regime": REGIME_HISTORICAL,
            "reading_contract_index": str(index_path),
            "reading_contract_index_sha256": index_sha256,
            "contracts": len(contracts),
            "model_packet_mutated": False,
            "candidate_or_programme_values_duplicated": False,
            "prompt_interpretation_delta": True,
            "real_identity_material_present": False,
            "target_outcomes_present": False,
            "cross_regime_interpretation": "COMPARE_WITH_BLIND_AS_FRAMING_INFORMATION_EFFECT_NOT_CAUSAL_EFFECT",
        }
        for name in ("run_state.json", "output_manifest.json", "preflight.json"):
            path = output_root / name
            if not path.is_file():
                continue
            value = json.loads(path.read_text(encoding="utf-8"))
            value["three_regime"] = metadata
            runner.atomic_write_json(path, value)

    runner.build_context = build_context
    runner.write_run_state = write_state
    runner.PROTOCOL_ID = PROTOCOL_ID


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--allow-noncanonical-counts" in args:
        raise runner.RunnerError("--allow-noncanonical-counts is forbidden")
    index_path = pathlib.Path(pop_option(args, "--reading-contract-index")).expanduser().resolve()
    contracts, index, digest = load_contract_index(index_path)
    install_reading_contract(contracts, index, digest, index_path)
    return bridge_runner.main(args)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (runner.RunnerError, ThreeRegimeError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
