from __future__ import annotations

import copy
import math
from typing import Any, Mapping, Sequence

from .contracts import ContractError


class SocialError(ContractError):
    pass


DIMENSIONS = {"awareness", "credibility", "salience", "viability", "government_evaluation", "candidate_perception", "social_norm", "turnout_norm"}
CHANNELS = {"FAMILY": 1.0, "WORK": .75, "NEIGHBORHOOD": .85}


def apply_social_round(state: Mapping[str, Any], messages: Sequence[Mapping[str, Any]], *, susceptibility: float, round_index: int) -> dict[str, Any]:
    """Update beliefs synchronously. Direct vote-probability edits are forbidden."""
    if int(state.get("round", 0)) != round_index - 1:
        raise SocialError("social rounds must be sequential")
    beliefs = copy.deepcopy(state.get("parties") or {})
    aggregate: dict[tuple[str, str], float] = {}
    for message in messages:
        if any(key in message for key in ("vote_delta", "probability_delta", "party_probability")):
            raise SocialError("social layer may not modify vote probabilities directly")
        channel = str(message.get("channel") or "").upper()
        dimension = str(message.get("dimension") or "")
        party = str(message.get("party_id") or "")
        if channel not in CHANNELS or dimension not in DIMENSIONS or party not in beliefs:
            raise SocialError("invalid social message")
        strength = float(message.get("strength", 0))
        credibility = float(message.get("source_credibility", .5))
        if not -1 <= strength <= 1 or not 0 <= credibility <= 1:
            raise SocialError("invalid social message bounds")
        aggregate[(party, dimension)] = aggregate.get((party, dimension), 0.0) + strength * credibility * CHANNELS[channel] * max(0.0, min(1.0, susceptibility))
    for (party, dimension), value in aggregate.items():
        previous = float(beliefs[party].get(dimension) or 0.0)
        beliefs[party][dimension] = max(-1.0, min(1.0, previous + math.tanh(value)))
    return {"schema_version": "AGENT_SOCIETY_SOCIAL_STATE_V4", "round": round_index, "parties": beliefs, "direct_probability_adjustment_forbidden": True}
