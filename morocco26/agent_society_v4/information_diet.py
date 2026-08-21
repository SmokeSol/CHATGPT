from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .contracts import ContractError


class InformationDietError(ContractError):
    pass


def _unit(value: Any, default: float = 0.5) -> float:
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value > 1.0:
        value /= 100.0
    return max(0.0, min(1.0, value))


def derive_profile(cell: Mapping[str, Any]) -> dict[str, Any]:
    discussion = _unit(cell.get("political_discussion") or cell.get("latent_attitude_political_discussion_mean"), 0.35)
    education = str(cell.get("education_level") or "").upper()
    education_score = {"NONE": .1, "PRIMARY": .3, "SECONDARY": .55, "HIGH_SCHOOL": .65, "TERTIARY": .9, "SUPERIEUR": .9, "SUPÉRIEUR": .9}.get(education, .5)
    localism = _unit(cell.get("localism") or cell.get("latent_attitude_local_responsiveness_mean"), .5)
    digital = _unit(cell.get("digital_news_exposure"), .4)
    attention = max(0.0, min(1.0, .45 * discussion + .30 * education_score + .15 * digital + .10 * localism))
    tier = "LOW" if attention < .34 else "MEDIUM" if attention < .68 else "HIGH"
    return {"attention": attention, "tier": tier, "localism": localism, "program_literacy": max(0.0, min(1.0, .55 * education_score + .45 * discussion)), "social_reliance": max(0.0, min(1.0, .75 - .35 * attention + .15 * localism))}


def _fraction(*parts: Any) -> float:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big") / float(2**64 - 1)


def build_information_diet(cell: Mapping[str, Any], contest: Mapping[str, Any], *, snapshot_id: str) -> dict[str, Any]:
    """All registered options remain visible; depth and salience vary by profile."""
    profile = derive_profile(cell)
    program_limit = {"LOW": 3, "MEDIUM": 8, "HIGH": 18}[profile["tier"]]
    candidate_threshold = {"LOW": .75, "MEDIUM": .45, "HIGH": .15}[profile["tier"]]
    options = []
    for option in contest.get("options") or []:
        candidate = option.get("candidate") or {}
        candidate_visible = candidate.get("candidate_name") is not None and (profile["attention"] + .25 * profile["localism"] + .1 * _fraction(snapshot_id, cell.get("cell_id"), option.get("party_id"))) >= candidate_threshold
        axes = option.get("program_axes") or {}
        ranked = sorted(axes.items(), key=lambda kv: (-_salience(kv[1]), str(kv[0])))[:program_limit]
        options.append({"party_id": option.get("party_id"), "party_name": option.get("party_name"), "party_exposure_status": "SALIENT" if profile["attention"] >= .4 else "LOW_SALIENCE_BALLOT_OPTION", "candidate_state": candidate.get("status", "UNKNOWN"), "candidate_name": candidate.get("candidate_name") if candidate_visible else None, "candidate_known_to_agent": candidate_visible, "candidate_attributes": candidate.get("attributes", {}) if candidate_visible else {}, "program_axes_seen": dict(ranked), "program_axes_total": len(axes)})
    if len(options) < 2:
        raise InformationDietError("diet cannot remove registered ballot alternatives")
    return {"schema_version": "AGENT_SOCIETY_INFORMATION_DIET_V4", "snapshot_id": snapshot_id, "cell_id": cell.get("cell_id") or cell.get("weighted_archetype_id"), "profile": profile, "options": options, "omniscient": False, "all_registered_options_retained": True}


def _salience(value: Any) -> float:
    if isinstance(value, (int, float)):
        return abs(float(value))
    return {"VERY_HIGH": 1.0, "HIGH": .85, "MEDIUM": .55, "LOW": .25, "UNKNOWN": 0.0}.get(str(value).upper(), .4)
