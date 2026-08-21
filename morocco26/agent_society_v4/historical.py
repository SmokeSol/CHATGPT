from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from .contracts import ContractError, Regime


class HistoricalError(ContractError): pass

OUTCOME_KEYS={"actual_result","actual_results","actual_vote_share","actual_votes","actual_seats","winner","target_outcome","target_outcomes","ground_truth"}
IDENTITY_KEYS={"real_party_name","real_candidate_name","real_territory_name","party_mapping","territory_mapping","candidate_mapping"}


def _scan(value: Any, forbidden: set[str], path: str="$") -> list[str]:
    found=[]
    if isinstance(value,dict):
        for k,v in value.items():
            if str(k).lower() in forbidden: found.append(f"{path}.{k}")
            found.extend(_scan(v,forbidden,f"{path}.{k}"))
    elif isinstance(value,list):
        for i,v in enumerate(value): found.extend(_scan(v,forbidden,f"{path}[{i}]"))
    return found


def register_surface(surface: Mapping[str,Any], bridge: Mapping[str,Any], *, election_year:int) -> dict[str,Any]:
    if election_year not in {2016,2021}: raise HistoricalError("historical surface must be 2016 or 2021")
    if _scan(surface,OUTCOME_KEYS) or _scan(surface,IDENTITY_KEYS): raise HistoricalError("historical surface leaks outcome or identity")
    if bridge.get("status")!="PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL" or bridge.get("target_outcomes_present") is not False or bridge.get("real_identity_material_present") is not False: raise HistoricalError("valid blind Main Bridge required")
    return {"schema_version":"AGENT_SOCIETY_HISTORICAL_SURFACE_V4","regime":Regime.RICH_SEMI_BLIND_BACKTEST.value,"election_year":election_year,"role":"DEVELOPMENT" if election_year==2016 else "HOLDOUT","identity_blinded":True,"outcomes_present":False,"main_bridge_id":bridge.get("bridge_id"),"surface":dict(surface),"unseal_authorized_here":False}


def pairing_index(rich: Sequence[Mapping[str,Any]], blind: Sequence[Mapping[str,Any]]) -> dict[str,Any]:
    def key(row:Mapping[str,Any]): return (str(row.get("source_work_item_id") or row.get("task_id") or ""),str(row.get("cell_id") or row.get("weighted_archetype_id") or ""))
    a={key(r):r for r in rich}; b={key(r):r for r in blind}
    if set(a)!=set(b) or any(not all(k) for k in a): raise HistoricalError("rich and blind cohorts must pair exactly")
    pairs=[]
    for k in sorted(a):
        pair_id="PAIR_"+hashlib.sha256("|".join(k).encode()).hexdigest()[:20]
        pairs.append({"pair_id":pair_id,"source_work_item_id":k[0],"cell_id":k[1],"rich_ref":a[k].get("output_ref"),"blind_ref":b[k].get("output_ref")})
    return {"schema_version":"AGENT_SOCIETY_PAIRING_V4","pair_count":len(pairs),"pairs":pairs,"deterministic":True}
