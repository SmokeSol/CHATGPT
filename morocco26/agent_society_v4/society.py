from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from .contracts import ContractError, simplex
from .information_diet import build_information_diet


class SocietyError(ContractError):
    pass


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def build_work_item(snapshot: Mapping[str, Any], cell: Mapping[str, Any]) -> dict[str, Any]:
    tid = str(cell.get("territory_id") or "")
    territory = next((t for t in snapshot.get("territories") or [] if str(t.get("territory_id")) == tid), None)
    if territory is None:
        raise SocietyError(f"unknown territory {tid}")
    ballots = territory.get("ballots") or {}
    item = {"schema_version": "AGENT_SOCIETY_DUAL_BALLOT_WORK_ITEM_V4", "snapshot_id": snapshot["snapshot_id"], "snapshot_sha256": snapshot["snapshot_sha256"], "regime": snapshot["regime"], "as_of": snapshot["as_of"], "cell": dict(cell), "territory": {k: territory.get(k) for k in ("territory_id", "territory_name", "region_id", "region_name", "registered_electorate")}, "information_diets": {"LOCAL": build_information_diet(cell, ballots["LOCAL"], snapshot_id=snapshot["snapshot_id"]), "REGIONAL": build_information_diet(cell, ballots["REGIONAL"], snapshot_id=snapshot["snapshot_id"])}, "required_output": {"turnout_probability": True, "local_party_simplex": True, "regional_party_simplex": True, "split_ticket_allowed": True, "observable_deliberation": True}, "raw_output_is_forecast": False, "outcomes_present": False}
    item["work_item_id"] = "WI_" + _hash({"snapshot": snapshot["snapshot_id"], "cell": cell.get("cell_id") or cell.get("weighted_archetype_id")})[:20]
    item["work_item_sha256"] = _hash(item)
    return item


def validate_decision(work_item: Mapping[str, Any], decision: Mapping[str, Any]) -> dict[str, Any]:
    if str(decision.get("work_item_id")) != str(work_item.get("work_item_id")):
        raise SocietyError("work_item_id mismatch")
    turnout = float(decision.get("turnout_probability"))
    if not 0 <= turnout <= 1:
        raise SocietyError("invalid turnout_probability")
    local_allowed = {str(x["party_id"]) for x in work_item["information_diets"]["LOCAL"]["options"]}
    regional_allowed = {str(x["party_id"]) for x in work_item["information_diets"]["REGIONAL"]["options"]}
    local = simplex(decision.get("local_party_probabilities") or {}, "local_party_probabilities")
    regional = simplex(decision.get("regional_party_probabilities") or {}, "regional_party_probabilities")
    if set(local) != local_allowed or set(regional) != regional_allowed:
        raise SocietyError("decision party universe differs from ballot")
    return {**decision, "turnout_probability": turnout, "local_party_probabilities": local, "regional_party_probabilities": regional, "raw_output_is_forecast": False, "schema_version": "AGENT_SOCIETY_DUAL_BALLOT_DECISION_V4"}
