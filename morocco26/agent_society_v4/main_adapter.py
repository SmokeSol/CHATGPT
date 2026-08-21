from __future__ import annotations

import csv,io,json,pathlib,subprocess
from typing import Any,Iterator,Mapping,Sequence
from .contracts import BallotType,CandidateRecord,CandidateState,ContractError

class MainAdapterError(ContractError): pass
class GitSnapshotReader:
    def __init__(self,repo_root:pathlib.Path,ref:str): self.repo_root=repo_root.resolve(); self.commit_sha=self._git("rev-parse",ref).strip();
    def _git(self,*args:str,binary:bool=False):
        p=subprocess.run(["git","-C",str(self.repo_root),*args],capture_output=True,text=not binary,check=False)
        if p.returncode: raise MainAdapterError((p.stderr.decode(errors="replace") if binary else p.stderr).strip())
        return p.stdout
    def paths(self,prefix="morocco26/"): return [x for x in str(self._git("ls-tree","-r","--name-only",self.commit_sha,prefix)).splitlines() if x]
    def read_bytes(self,path:str)->bytes: return bytes(self._git("show",f"{self.commit_sha}:{path}",binary=True))

def discover_sources(reader:GitSnapshotReader)->dict[str,list[str]]:
    b={"candidate":[],"program":[],"territory":[],"registered_electorate":[]}
    for path in reader.paths():
        lower=path.lower(); suffix=pathlib.PurePosixPath(path).suffix.lower()
        if suffix not in {".json",".jsonl",".csv"}: continue
        if any(x in lower for x in ("candidate_ledger","ballot_roster","candidate_intelligence","candidate_coverage","candidat")): b["candidate"].append(path)
        if any(x in lower for x in ("program","programme","manifesto","party_offer")): b["program"].append(path)
        if any(x in lower for x in ("territory_crosswalk","circonscriptions_raw","constituencies","territor","circonscription")): b["territory"].append(path)
        if any(x in lower for x in ("registered_elector","electoral_roll","inscrits","electeurs")): b["registered_electorate"].append(path)
    return {k:sorted(set(v)) for k,v in b.items()}

def source_inventory(reader:GitSnapshotReader)->dict[str,Any]:
    import hashlib; records=[]
    for kind,paths in discover_sources(reader).items():
        for path in paths:
            payload=reader.read_bytes(path); records.append({"kind":kind,"path":path,"sha256":hashlib.sha256(payload).hexdigest(),"bytes":len(payload)})
    return {"schema_version":"AGENT_SOCIETY_MAIN_SOURCE_INVENTORY_V4","main_commit_sha":reader.commit_sha,"sources":records,"floating_reads":False}

def _walk(value:Any)->Iterator[Mapping[str,Any]]:
    if isinstance(value,list):
        for x in value: yield from _walk(x)
    elif isinstance(value,dict):
        keys={str(k).lower() for k in value}
        if keys.intersection({"party","party_id","party_code","parti"}) and keys.intersection({"territory_id","territory","constituency","circonscription","district"}): yield value
        for x in value.values():
            if isinstance(x,(dict,list)): yield from _walk(x)

def _rows(payload:bytes,path:str):
    suffix=pathlib.PurePosixPath(path).suffix.lower()
    if suffix==".json": return list(_walk(json.loads(payload.decode())))
    if suffix==".jsonl":
        out=[]
        for line in payload.decode().splitlines():
            if line.strip(): out.extend(_walk(json.loads(line)))
        return out
    if suffix==".csv": return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    return []
def _first(row:Mapping[str,Any],keys:Sequence[str]):
    low={str(k).lower():v for k,v in row.items()}; return next((low[k] for k in keys if k in low and low[k] not in (None,"")),None)

def candidate_records(reader:GitSnapshotReader,*,as_of:str)->tuple[list[CandidateRecord],list[dict[str,Any]]]:
    records={}; unresolved=[]; rank={CandidateState.OFFICIAL:5,CandidateState.DECLARED:4,CandidateState.REPORTED:3,CandidateState.UNKNOWN:2,CandidateState.NO_LIST:1}
    for path in discover_sources(reader)["candidate"]:
        try: rows=_rows(reader.read_bytes(path),path)
        except Exception: continue
        for row in rows:
            party=_first(row,("party","party_id","party_code","parti")); territory=_first(row,("territory_id","territory","constituency","circonscription","district")); name=_first(row,("candidate_name","candidate","name","nom","full_name","tete_de_liste"))
            if not party or not territory: continue
            status=str(_first(row,("status","candidate_status","nomination_status","state")) or ("DECLARED" if name else "UNKNOWN")).upper().replace(" ","_"); status={"REGISTERED":"OFFICIAL","CONFIRMED":"OFFICIAL","DECLARED_ACTIVE":"DECLARED","ANNOUNCED":"DECLARED","PENDING_NOMINATION":"UNKNOWN","PENDING":"UNKNOWN","SOURCE_GAP":"UNKNOWN","REPORTED_UNCONFIRMED":"REPORTED","RUMORED":"REPORTED","ABSENT":"NO_LIST"}.get(status,status); state=CandidateState[status] if status in CandidateState.__members__ else CandidateState.UNKNOWN
            if state in {CandidateState.OFFICIAL,CandidateState.DECLARED,CandidateState.REPORTED} and not name: state=CandidateState.UNKNOWN
            known=str(_first(row,("source_date","known_at","verified_at","as_of","published_at","updated_at")) or "")[:10] or None; src=str(_first(row,("source_ref","source_url","url","source")) or path); sources=({"source_id":src,"known_at":known or as_of,"tier":str(row.get("source_tier") or "UNSPECIFIED")},) if state is not CandidateState.UNKNOWN else (); rec=CandidateRecord(str(territory),str(party).upper(),BallotType.REGIONAL if "REG" in str(row.get("ballot_type") or row.get("ballot") or "LOCAL").upper() else BallotType.LOCAL,state,str(name).strip() if name and state not in {CandidateState.UNKNOWN,CandidateState.NO_LIST} else None,known,sources,{})
            try: rec.validate(as_of=as_of)
            except ContractError as exc: unresolved.append({"path":path,"party":party,"territory":territory,"reason":str(exc)}); continue
            key=(rec.territory_id,rec.party_id,rec.ballot); current=records.get(key)
            if current is None or rank[rec.state]>rank[current.state]: records[key]=rec
    return sorted(records.values(),key=lambda r:(r.territory_id,r.ballot.value,r.party_id)),unresolved

def program_records(reader:GitSnapshotReader,*,as_of:str)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    programs={}; unresolved=[]
    for path in discover_sources(reader)["program"]:
        try: rows=_rows(reader.read_bytes(path),path)
        except Exception: continue
        for row in rows:
            party=_first(row,("party","party_id","party_code","parti")); axes=row.get("axes") or row.get("priorities") or row.get("program_priority_levels")
            if not party or not isinstance(axes,dict): continue
            known=str(_first(row,("source_date","known_at","verified_at","as_of","published_at","updated_at")) or as_of)[:10]
            try:
                from .contracts import parse_date
                if parse_date(known)>parse_date(as_of): continue
            except Exception as exc: unresolved.append({"path":path,"party":party,"reason":str(exc)}); continue
            record={"party_id":str(party).upper(),"program_axes":axes,"program_sources":[{"source_id":path,"known_at":known,"tier":str(row.get("source_tier") or "UNSPECIFIED")}],"known_at":known}
            if str(party).upper() not in programs or len(axes)>len(programs[str(party).upper()]["program_axes"]): programs[str(party).upper()]=record
    return [programs[k] for k in sorted(programs)],unresolved

def territory_records(reader:GitSnapshotReader)->list[dict[str,Any]]:
    result={}
    for path in discover_sources(reader)["territory"]:
        try: rows=_rows(reader.read_bytes(path),path)
        except Exception: continue
        for row in rows:
            tid=_first(row,("territory_id","constituency_id","circonscription_id","district_id","id")); name=_first(row,("territory_name","constituency_name","circonscription_name","district_name","public","name","nom","territory","constituency","circonscription"))
            if not tid: continue
            result[str(tid)]={"territory_id":str(tid),"territory_name":str(name or tid),"region_id":_first(row,("region_id","region")),"source_path":path}
    return [result[k] for k in sorted(result)]
