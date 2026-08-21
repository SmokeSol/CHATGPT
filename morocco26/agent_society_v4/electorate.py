from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Mapping, Sequence

from .contracts import ContractError


class ElectorateError(ContractError): pass


def registration_propensity(cell: Mapping[str, Any]) -> float:
    age={"18_24":-.18,"25_34":-.08,"35_44":.02,"45_54":.08,"55_64":.12,"65_PLUS":.10}.get(str(cell.get("age_band") or "").upper(),0)
    education={"NONE":-.08,"PRIMARY":-.03,"SECONDARY":.02,"HIGH_SCHOOL":.05,"TERTIARY":.09,"SUPERIEUR":.09,"SUPÉRIEUR":.09}.get(str(cell.get("education_level") or "").upper(),0)
    try: discussion=.16*(float(cell.get("political_discussion") or cell.get("latent_attitude_political_discussion_mean") or .5)-.5)
    except (TypeError,ValueError): discussion=0
    return max(.001,min(.999,1/(1+math.exp(-(0.30+age+education+discussion)))))


def calibrate_to_registered_totals(cells: Sequence[Mapping[str, Any]], totals: Mapping[str, float]) -> list[dict[str, Any]]:
    grouped: dict[str,list[dict[str,Any]]]=defaultdict(list)
    for raw in cells:
        row=dict(raw); tid=str(row.get("territory_id") or ""); w=float(row.get("population_weight") or row.get("weight") or 0)
        if not tid or w<=0: raise ElectorateError("cells require territory_id and positive population weight")
        row["registration_propensity_prior"]=registration_propensity(row); row["registered_weight_prior"]=w*row["registration_propensity_prior"]; grouped[tid].append(row)
    output=[]
    for tid,rows in grouped.items():
        if tid not in totals or float(totals[tid])<=0: raise ElectorateError(f"registered total missing for {tid}")
        prior=sum(r["registered_weight_prior"] for r in rows); scale=float(totals[tid])/prior
        for row in rows: output.append({**row,"territory_id":tid,"registered_electorate_weight":row["registered_weight_prior"]*scale,"registration_calibration_factor":scale,"poststratification_target":"REGISTERED_ELECTORATE_2026"})
    for tid,target in totals.items():
        observed=sum(float(r["registered_electorate_weight"]) for r in output if r["territory_id"]==tid)
        if observed and abs(observed-float(target))>max(1e-6,float(target)*1e-10): raise ElectorateError(f"registration reconciliation failed for {tid}")
    return output
