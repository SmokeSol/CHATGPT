from __future__ import annotations

import hashlib
from typing import Any, Mapping

from .contracts import CandidateState, ContractError


class InformationDietError(ContractError):
    pass


def _unit(value: Any, default: float = 0.5) -> float:
    try: value=float(value)
    except (TypeError,ValueError): return default
    if value>1: value/=100
    return max(0,min(1,value))


def derive_profile(cell: Mapping[str, Any]) -> dict[str, Any]:
    discussion_raw=cell.get("political_discussion")
    if discussion_raw is None: discussion_raw=cell.get("latent_attitude_political_discussion_mean")
    discussion=_unit(discussion_raw,.35)
    education=str(cell.get("education_level") or "").upper()
    e={"NONE":.1,"PRIMARY":.3,"SECONDARY":.55,"HIGH_SCHOOL":.65,"TERTIARY":.9,"SUPERIEUR":.9,"SUPÉRIEUR":.9}.get(education,.5)
    localism_raw=cell.get("localism")
    if localism_raw is None: localism_raw=cell.get("latent_attitude_local_responsiveness_mean")
    localism=_unit(localism_raw,.5)
    digital=_unit(cell.get("digital_news_exposure"),.4)
    attention=max(0,min(1,.45*discussion+.30*e+.15*digital+.10*localism))
    tier="LOW" if attention<.34 else "MEDIUM" if attention<.68 else "HIGH"
    return {"attention":attention,"tier":tier,"localism":localism,"program_literacy":max(0,min(1,.55*e+.45*discussion)),"social_reliance":max(0,min(1,.75-.35*attention+.15*localism))}


def _fraction(*parts: Any) -> float:
    digest=hashlib.sha256("|".join(map(str,parts)).encode()).digest(); return int.from_bytes(digest[:8],"big")/float(2**64-1)


def build_information_diet(cell: Mapping[str, Any], contest: Mapping[str, Any], *, snapshot_id: str) -> dict[str, Any]:
    """Keep every selectable ballot option; exclude explicit NO_LIST rows.

    Visibility changes detail and salience, not the existence of a real ballot option.
    """
    profile=derive_profile(cell); program_limit={"LOW":3,"MEDIUM":8,"HIGH":18}[profile["tier"]]; threshold={"LOW":.75,"MEDIUM":.45,"HIGH":.15}[profile["tier"]]; options=[]; excluded=[]
    for option in contest.get("options") or []:
        candidate=option.get("candidate") or {}; state=CandidateState(str(candidate.get("status") or "UNKNOWN"))
        if state is CandidateState.NO_LIST:
            excluded.append({"party_id":option.get("party_id"),"reason":"NO_LIST"}); continue
        visible=candidate.get("candidate_name") is not None and profile["attention"]+.25*profile["localism"]+.1*_fraction(snapshot_id,cell.get("cell_id"),option.get("party_id"))>=threshold; axes=option.get("program_axes") or {}; ranked=sorted(axes.items(),key=lambda kv:(-_salience(kv[1]),str(kv[0])))[:program_limit]
        options.append({"party_id":option.get("party_id"),"party_name":option.get("party_name"),"party_exposure_status":"SALIENT" if profile["attention"]>=.4 else "LOW_SALIENCE_BALLOT_OPTION","candidate_state":state.value,"candidate_name":candidate.get("candidate_name") if visible else None,"candidate_known_to_agent":visible,"candidate_attributes":candidate.get("attributes",{}) if visible else {},"program_axes_seen":dict(ranked),"program_axes_total":len(axes)})
    if len(options)<2: raise InformationDietError("fewer than two selectable ballot options")
    return {"schema_version":"AGENT_SOCIETY_INFORMATION_DIET_V4","snapshot_id":snapshot_id,"cell_id":cell.get("cell_id") or cell.get("weighted_archetype_id"),"profile":profile,"options":options,"excluded_non_ballot_options":excluded,"omniscient":False,"all_selectable_options_retained":True}


def _salience(value: Any) -> float:
    if isinstance(value,(int,float)): return abs(float(value))
    return {"VERY_HIGH":1,"HIGH":.85,"MEDIUM":.55,"LOW":.25,"UNKNOWN":0}.get(str(value).upper(),.4)
