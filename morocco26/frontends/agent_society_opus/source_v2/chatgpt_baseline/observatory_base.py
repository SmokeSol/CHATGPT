#!/usr/bin/env python3
"""ATLAS G0 observable-deliberation and counterfactual observatory.

This runner is deliberately downstream of the immutable D0 decision corpus.
It never asks for private chain-of-thought. A fresh Sol context produces a
structured external explanation tied to a closed evidence catalogue; separate
fresh Sol contexts then re-run deterministic packet perturbations to test the
explanation's causal predictions.
"""
from __future__ import annotations

import argparse
import collections
import concurrent.futures
import copy
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

HERE = pathlib.Path(__file__).resolve().parent
RUNNER_PATH = HERE / "run_chatgpt_baseline.py"
SPEC = importlib.util.spec_from_file_location("atlas_g0_runner", RUNNER_PATH)
R = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R
assert SPEC.loader is not None
SPEC.loader.exec_module(R)

PROTOCOL_ID = "ATLAS_G0_DELIBERATION_OBSERVATORY_PROTOCOL_V1"
BASELINE_ID = "G0_CHATGPT_GPT56_SOL"
DECISION_MODEL = "gpt-5.6-sol"
DECISION_REASONING = "medium"
DELIBERATION_MODEL = "gpt-5.6-sol"
DELIBERATION_REASONING = "high"
COUNTERFACTUAL_MODEL = "gpt-5.6-sol"
COUNTERFACTUAL_REASONING = "medium"
EXPECTED_ROWS_PER_TASK = 32
FACTORS = tuple(R.FACTORS)
PARTICIPATION_POSTURES = ("LIKELY_ABSTAIN", "UNCERTAIN", "LIKELY_VOTE")
TRANSITIONS = ("LOYALTY", "SWITCH", "MOBILIZATION", "ABSTENTION_CONTINUITY", "OPEN_FIELD")
CERTAINTY = ("LOW", "MEDIUM", "HIGH")
DRIVER_DIRECTIONS = (
    "SUPPORTS_TOP",
    "SUPPORTS_RUNNER_UP",
    "SUPPORTS_TURNOUT",
    "SUPPORTS_ABSTENTION",
    "AMBIVALENT",
)
STRENGTHS = ("WEAK", "MEDIUM", "STRONG")
SCENARIOS = (
    "PRIOR_ANCHOR_ALTERNATIVE",
    "GOVERNMENT_OUTLOOK_REVERSE",
    "RUNNER_LOCAL_STRENGTH",
    "TOP_RUNNER_PROGRAM_SWAP",
    "NONINFORMATIVE_METADATA_PLACEBO",
)
PANEL_NAMES = ("HASH_ANCHOR", "SWING", "TURNOUT_PIVOT", "STRONGEST_SWITCH")
RATE_LIMIT_MARKERS = tuple(R.RATE_LIMIT_MARKERS)
PRINT_LOCK = threading.Lock()


class ObservatoryError(RuntimeError):
    pass


class DeliberationValidationError(ObservatoryError):
    pass


@dataclasses.dataclass(frozen=True)
class SelectedVoter:
    panel: str
    index: int
    voter: dict[str, Any]
    decision: dict[str, Any]

    @property
    def archetype_id(self) -> str:
        return str(self.decision["weighted_archetype_id"])


@dataclasses.dataclass
class InvocationResult:
    task_id: str
    phase: str
    status: str
    output_path: str
    attempts: int
    rows: int = 0
    output_sha256: str | None = None
    usage: dict[str, int] | None = None
    error: str | None = None
    rate_limited: bool = False


def load_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: pathlib.Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, float(value)))


def exact_float(a: Any, b: Any, tolerance: float = 1e-12) -> bool:
    try:
        return abs(float(a) - float(b)) <= tolerance
    except (TypeError, ValueError):
        return False


def decision_digest(row: Mapping[str, Any]) -> str:
    return R.sha256_json(row)


def top_two(decision: Mapping[str, Any]) -> tuple[str, float, str, float]:
    values = decision.get("conditional_party_probabilities")
    if not isinstance(values, dict) or len(values) < 2:
        raise ObservatoryError("decision lacks at least two party probabilities")
    ordered = sorted(
        ((str(party), float(prob)) for party, prob in values.items()),
        key=lambda item: (-item[1], item[0]),
    )
    return ordered[0][0], ordered[0][1], ordered[1][0], ordered[1][1]


def participation_posture(turnout: float) -> str:
    if turnout <= 0.33:
        return "LIKELY_ABSTAIN"
    if turnout >= 0.67:
        return "LIKELY_VOTE"
    return "UNCERTAIN"


def certainty_band(margin: float) -> str:
    if margin < 0.10:
        return "LOW"
    if margin < 0.25:
        return "MEDIUM"
    return "HIGH"


def transition_type(voter: Mapping[str, Any], decision: Mapping[str, Any]) -> str:
    prior = str(voter.get("prior_vote_or_abstention") or "")
    top, _, _, _ = top_two(decision)
    turnout = float(decision["turnout_probability"])
    if prior == "ABSTAIN":
        return "MOBILIZATION" if turnout >= 0.5 else "ABSTENTION_CONTINUITY"
    if prior in decision["conditional_party_probabilities"]:
        return "LOYALTY" if prior == top else "SWITCH"
    return "OPEN_FIELD"


def task_context(task: R.FrozenTask) -> dict[str, Any]:
    context = task.packet.get("context")
    if isinstance(context, dict):
        return copy.deepcopy(context)
    return copy.deepcopy(task.packet)


def task_voter_batch(task: R.FrozenTask) -> dict[str, Any]:
    batch = task.packet.get("voter_batch")
    if isinstance(batch, dict):
        return copy.deepcopy(batch)
    return {
        "anonymous_election_id": task.election_id,
        "anonymous_territory_id": task.territory_id,
        "batch_id": task.batch_id,
        "available_party_ids": list(task.available_party_ids),
        "voter_archetypes": [copy.deepcopy(row) for row in task.expected_rows],
    }


def party_offer_lookup(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    cards = (
        (context.get("election_environment_card") or {}).get("party_offer_cards")
        or []
    )
    return {
        str(card.get("anonymous_party_id")): dict(card)
        for card in cards
        if isinstance(card, dict) and card.get("anonymous_party_id")
    }


def party_local_lookup(context: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    cards = (
        (context.get("common_territory_card") or {}).get("party_context_cards")
        or []
    )
    return {
        str(card.get("anonymous_party_id")): dict(card)
        for card in cards
        if isinstance(card, dict) and card.get("anonymous_party_id")
    }
