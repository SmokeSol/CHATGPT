from __future__ import annotations

import copy,hashlib,json
from typing import Any,Mapping
from .contracts import BallotType,CandidateRecord,CandidateState,ContractError,parse_date

class VintageError(ContractError): pass

def _hash(value:Any)->str: return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(",",":"),allow_nan=False).encode()).hexdigest()
def _source(source:Mapping[str,Any],as_of:str)->None:
    if not str(source.get("source_id") or ""): raise VintageError("source_id required")
    known=str(source.get("known_at") or "")[:10]
    if not known: raise VintageError("source known_at required")
    if parse_date(known)>parse_date(as_of): raise VintageError("future source cannot enter vintage")

def build_named_vintage(spec:Mapping[str,Any])->dict[str,Any]:
    as_of=str(spec.get("as_of") or "")[:10]; parse_date(as_of); main_sha=str(spec.get("source_main_commit") or "")
    if len(main_sha)!=40 or any(c not in "0123456789abcdef" for c in main_sha.lower()): raise VintageError("source_main_commit must be exact SHA")
    territories=copy.deepcopy(spec.get("territories") or [])
    if not territories: raise VintageError("vintage requires territories")
    seen=set(); unknown=0
    for territory in territories:
        tid=str(territory.get("territory_id") or "")
        if not tid or tid in seen: raise VintageError("territory_id missing/duplicate")
        seen.add(tid)
        if not str(territory.get("territory_name") or ""): raise VintageError("named 2026 territory_name required")
        if float(territory.get("registered_electorate") or 0)<=0: raise VintageError("registered_electorate must be positive")
        ballots=territory.get("ballots") or {}
        if set(ballots)!={"LOCAL","REGIONAL"}: raise VintageError("LOCAL and REGIONAL ballots required")
        for ballot_name,contest in ballots.items():
            contest.setdefault("contest_id",f"{ballot_name}::{tid if ballot_name=='LOCAL' else territory.get('region_id')}"); options=contest.get("options") or []
            if len(options)<2: raise VintageError("each contest requires at least two option rows")
            parties=set(); selectable=0
            for option in options:
                party=str(option.get("party_id") or "")
                if not party or party in parties: raise VintageError("party_id missing/duplicate")
                parties.add(party)
                if not str(option.get("party_name") or ""): raise VintageError("party_name required")
                raw=option.get("candidate") or {"status":"UNKNOWN","candidate_name":None,"known_at":None,"sources":[],"attributes":{},"unknown_reason":"NOT_VERIFIED_AS_OF_VINTAGE"}; state=CandidateState(str(raw.get("status") or "UNKNOWN"))
                if state is CandidateState.UNKNOWN: raw.setdefault("candidate_name",None); raw.setdefault("unknown_reason","NOT_VERIFIED_AS_OF_VINTAGE"); unknown+=1
                rec=CandidateRecord(tid,party,BallotType(ballot_name),state,raw.get("candidate_name"),raw.get("known_at"),tuple(raw.get("sources") or ()),raw.get("attributes") or {}); rec.validate(as_of=as_of); option["candidate"]={**raw,"status":state.value}
                if state is not CandidateState.NO_LIST: selectable+=1
                axes=option.get("program_axes") or {}; program_sources=option.get("program_sources") or []
                if axes and not program_sources: raise VintageError("substantive program axes require provenance")
                for src in program_sources: _source(src,as_of)
            if selectable<2: raise VintageError("contest requires at least two selectable options")
    payload={"schema_version":"AGENT_SOCIETY_NAMED_2026_VINTAGE_V4","status":"PARTIAL_AS_OF_VINTAGE_READY" if unknown else "CANDIDATE_IDENTITIES_COMPLETE_NOT_YET_FINAL_BALLOT_CERTIFIED","snapshot_id":str(spec.get("snapshot_id") or f"M26_{as_of}"),"as_of":as_of,"source_main_commit":main_sha.lower(),"regime":"NAMED_REALISTIC_2026","territories":territories,"unknown_candidate_cells":unknown,"silent_candidate_imputation":False,"outcomes_present":False,"final_ballot_claim":False}; payload["snapshot_sha256"]=_hash(payload); return payload

def diff_vintages(old:Mapping[str,Any],new:Mapping[str,Any])->dict[str,Any]:
    if parse_date(str(new["as_of"])[:10])<=parse_date(str(old["as_of"])[:10]): raise VintageError("new vintage must be later")
    def idx(s): return {(str(t["territory_id"]),b,str(o["party_id"])):o for t in s.get("territories") or [] for b,c in (t.get("ballots") or {}).items() for o in c.get("options") or []}
    a,b=idx(old),idx(new); affected=set(); changes=[]
    for key in sorted(set(a)|set(b)):
        if a.get(key)!=b.get(key): affected.add((key[0],key[1])); changes.append({"territory_id":key[0],"ballot":key[1],"party_id":key[2],"before_sha256":_hash(a.get(key)),"after_sha256":_hash(b.get(key))})
    return {"schema_version":"AGENT_SOCIETY_VINTAGE_DIFF_V4","old_snapshot_id":old.get("snapshot_id"),"new_snapshot_id":new.get("snapshot_id"),"changes":changes,"affected_contests":[{"territory_id":t,"ballot":bb} for t,bb in sorted(affected)],"full_national_rerun_required":False}
