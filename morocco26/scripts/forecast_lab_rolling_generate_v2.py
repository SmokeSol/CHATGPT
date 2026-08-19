#!/usr/bin/env python3
from __future__ import annotations

import argparse, csv, json, re, unicodedata
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
LAB = G / "forecast_lab" / "rolling_origin_v2"
CONTRACT = G / "forecast_lab" / "rolling_origin_contract_v2.json"
META = ROOT / "data" / "constituencies_goal75.csv"
CORE = ("RNI","PAM","PI","PJD","USFP","MP","UC","PPS")
PARTIES = (*CORE,"OTHER")
PRIOR = {2011:2007, 2016:2011, 2021:2016}
ALIASES = {
 "rabat el mouhit":"rabat ocean", "rabat al mouhit":"rabat ocean",
 "rabat challah":"rabat chellah", "rabat chellah":"rabat chellah",
 "fes janoubia":"fes sud", "fes chamalia":"fes nord", "fes shamalia":"fes nord",
 "marrakech medina":"medina sidi youssef", "marrakech gueliz ennakhil":"gueliz nakhil",
 "marrakech gueliz nakhil":"gueliz nakhil", "marrakech menara":"menara",
 "moulay yacoub":"moulay yaacoub", "m diq fnideq":"m diq fnideq",
 "taroudannt al janoubia":"taroudant sud", "taroudannt chamalia":"taroudant nord",
 "agadir ida ou tanane":"agadir ida outanane",
 "bzou ouaouizaght":"bzou ouaouizeght",
 "es smara":"es semara",
 "gueliz annakhil":"gueliz nakhil",
 "karia rhafsai":"karia ghafsay",
 "mohammadia":"mohammedia",
 "medina sidi youssef ben ali":"medina sidi youssef",
 "oued ed dahab":"oued eddahab",
 "sale al jadida":"sale el jadida",
 "tifelt rommani":"tiflet rommani"
}

def rj(p): return json.loads(Path(p).read_text(encoding="utf-8"))

def norm(v):
    x=unicodedata.normalize("NFKD",str(v or "")); x="".join(c for c in x if not unicodedata.combining(c))
    x=x.lower().replace("’", "'"); x=re.sub(r"[^a-z0-9]+"," ",x); x=re.sub(r"\s+"," ",x).strip()
    return ALIASES.get(x,x)

def path_for(year):
    return HIST/"2007"/"legislative_2007_outcome_canonical.json" if year==2007 else HIST/f"tafra_legislative_{year}_canonical.json"

def load_rows(year,current_target):
    if year>=current_target: raise RuntimeError(f"LEAKAGE_GUARD_REFUSES_{year}_FOR_{current_target}")
    p=path_for(year); d=rj(p)
    if year==2007:
        rows=list(d["local_rows"])
        if len(rows)!=95 or sum(int(r.get("magnitude",0)) for r in rows)!=295: raise RuntimeError("BAD_2007_NATIVE_MAP")
        if any(r.get("vote_matrix_status")!="OFFICIAL_ARCHIVE_FULL_LOCAL_PARTY_MATRIX" for r in rows): raise RuntimeError("BAD_2007_MATRIX_STATUS")
    else:
        rows=[r for r in d["rows"] if str(r.get("list_type","")).lower() in {"local","locale"}]
        if len(rows)!=92: raise RuntimeError(f"BAD_{year}_ROW_COUNT_{len(rows)}")
    return p,rows

def counts(r):
    raw=r.get("votes",{}); vals=[float(raw.get(p) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE)); a=np.asarray(vals,float)
    if np.any(a<0) or a.sum()<=0: raise RuntimeError("INVALID_VOTE_VECTOR")
    return a

def share(r):
    a=counts(r); return a/a.sum()

def nat_share(rows):
    a=np.stack([counts(r) for r in rows]).sum(axis=0); return a/a.sum()

def meta():
    with META.open(encoding="utf-8",newline="") as f: rows=list(csv.DictReader(f))
    if len(rows)!=92 or len({r["constituency_id"] for r in rows})!=92: raise RuntimeError("BAD_MODERN_META")
    by={}
    for r in rows:
        k=norm(r["name"])
        if k in by: raise RuntimeError(f"META_COLLISION_{k}")
        by[k]=r
    return rows,by

def exact_modern_map(year,rows):
    mrows,by=meta(); mapped={}; unresolved=[]; collisions=[]
    for r in rows:
        k=norm(r.get("constituency")); m=by.get(k)
        if m is None: unresolved.append(str(r.get("constituency"))); continue
        tid=m["constituency_id"]
        if tid in mapped:
            collisions.append(tid); mapped.pop(tid,None); continue
        mapped[tid]=r
    return mapped,{"year":year,"method":"EXACT_NORMALIZED_PLUS_FROZEN_ALIASES","mapped":len(mapped),"unresolved":sorted(unresolved),"collisions":sorted(set(collisions)),"fuzzy_used":False,"target_universe":len(mrows)}

def map_2007(rows):
    cw=rj(HIST/"2007"/"crosswalk_to_modern.json"); by_native={str(r.get("native_id")):r for r in rows}
    accepted={"EXACT","RENAMED","EXPLICIT"}; mapped={}; excluded=[]; collisions=[]
    for x in cw["rows"]:
        typ=str(x.get("mapping_type","")).upper(); targets=x.get("modern_targets") or []; nid=str(x.get("native_id"))
        if typ not in accepted or len(targets)!=1 or nid not in by_native:
            excluded.append({"native_id":nid,"name":x.get("native_constituency"),"mapping_type":typ,"target_count":len(targets)}); continue
        tid=str(targets[0]["constituency_id"])
        if tid in mapped:
            collisions.append(tid); mapped.pop(tid,None); continue
        mapped[tid]=by_native[nid]
    return mapped,{"year":2007,"method":"FROZEN_CROSSWALK_ONE_TO_ONE_ONLY","accepted_types":sorted(accepted),"mapped":len(mapped),"excluded_count":len(excluded),"excluded":excluded,"collisions":sorted(set(collisions)),"fuzzy_used":False}

def map_prior(year,rows): return map_2007(rows) if year==2007 else exact_modern_map(year,rows)

def verify_2007():
    gate=rj(HIST/"2007"/"acceptance_gate_v2.json"); cert=rj(HIST/"2007"/"anti_leakage_certificate_v2.json")
    if gate.get("scientific_status")!="PASS_FOR_ROLLING_ORIGIN_BACKTEST": raise RuntimeError("2007_GATE_NOT_PASS")
    rec=gate.get("reconciliation",{})
    if (rec.get("matched_rows"),rec.get("unresolved_rows"),rec.get("seat_mismatches"),rec.get("unused_outcome_rows"))!=(95,0,0,0): raise RuntimeError("2007_RECONCILIATION_INVARIANT_FAIL")
    if cert.get("declaration")!="TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT": raise RuntimeError("2007_ANTI_LEAKAGE_FAIL")
    return {"status":gate["scientific_status"],"matched_rows":95,"seat_mismatches":0,"snapshot_unchanged":gate["controls"].get("target_snapshot_mutation")=="PASS_READ_ONLY"}

def training_fold(train_target,current_target):
    py=PRIOR[train_target]; _,pr=load_rows(py,current_target); _,ar=load_rows(train_target,current_target)
    pm,pdiag=map_prior(py,pr); am,adiag=exact_modern_map(train_target,ar); order,_=meta()
    ids=[r["constituency_id"] for r in order if r["constituency_id"] in pm and r["constituency_id"] in am]
    if not ids: raise RuntimeError(f"ZERO_SUPPORT_{py}_{train_target}")
    return {"prior":py,"target":train_target,"ids":ids,"territory":np.stack([share(pm[i]) for i in ids]),"actual":np.stack([share(am[i]) for i in ids]),"national":nat_share(pr),"prior_mapping":pdiag,"target_mapping":adiag}

def choose_lambda(target):
    trains={2011:[],2016:[2011],2021:[2011,2016]}[target]
    if not trains: return 0.5,{"policy":"COLD_START_FIXED_HALF_SHRINK","selected_lambda":0.5,"training_folds":[]}
    fs=[training_fold(t,target) for t in trains]; grid=np.linspace(0,1,101); scored=[]
    for lam in grid:
        sse=0.; n=0
        for f in fs:
            pred=lam*f["territory"]+(1-lam)*f["national"][None,:]; e=pred-f["actual"]; sse+=float(np.sum(e*e)); n+=e.size
        scored.append((float(np.sqrt(sse/n)),float(lam)))
    rmse,lam=min(scored,key=lambda x:(x[0],x[1])); sums=[]
    for f in fs:
        pred=lam*f["territory"]+(1-lam)*f["national"][None,:]
        sums.append({"transition":f"{f['prior']}->{f['target']}","support":len(f["ids"]),"rmse_at_selected_lambda":float(np.sqrt(np.mean((pred-f["actual"])**2))),"prior_mapping":f["prior_mapping"],"target_mapping":f["target_mapping"]})
    return lam,{"policy":"PAST_FOLDS_ONLY_GRID_RMSE","grid":{"min":0,"max":1,"step":0.01},"selected_lambda":lam,"pooled_training_rmse":rmse,"training_folds":sums}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--target",type=int,choices=[2011,2016,2021],required=True); target=ap.parse_args().target
    if rj(CONTRACT).get("contract_id")!="M26-FORECAST-LAB-ROLLING-ORIGIN-V2": raise RuntimeError("WRONG_CONTRACT")
    lineage=verify_2007(); py=PRIOR[target]; prior_path,pr=load_rows(py,target); pm,pdiag=map_prior(py,pr); order,_=meta(); ids=[r["constituency_id"] for r in order if r["constituency_id"] in pm]
    nat=nat_share(pr); terr=np.stack([share(pm[i]) for i in ids]); lam,lfit=choose_lambda(target)
    models={"NATIONAL_ONLY":np.repeat(nat[None,:],len(ids),axis=0),"HALF_SHRINK":.5*terr+.5*nat[None,:],"PERSIST":terr,"ROLLING_LAMBDA":lam*terr+(1-lam)*nat[None,:]}
    byid={r["constituency_id"]:r for r in order}; out=[]
    for i,tid in enumerate(ids):
        src=pm[tid]; out.append({"territory_id":tid,"territory_name":byid[tid]["name"],"prior_native_id":src.get("native_id",src.get("id_constituency")),"prior_constituency":src.get("constituency"),"models":{m:{p:float(models[m][i,j]) for j,p in enumerate(PARTIES)} for m in models}})
    LAB.mkdir(parents=True,exist_ok=True)
    snap={"schema_version":"2.0","snapshot_id":f"M26-ROLLING-PRE-ELECTION-{target}-V2","target_year":target,"prior_year":py,"as_if_date":f"PRE_{target}_ELECTION","target_outcome_present":False,"forbidden_target_path":str(path_for(target).relative_to(ROOT)),"generator":"forecast_lab_rolling_generate_v2.py","territorial_policy":"NATIVE_FIRST_EXPLICIT_CROSSWALK_NO_FUZZY_NO_FORCED_92","support_territories":len(ids),"target_universe_territories":92,"prior_mapping":pdiag,"lineage_2007":lineage}
    fc={"schema_version":"2.0","forecast_id":f"M26-ROLLING-POINT-{target}-V2","contract_id":"M26-FORECAST-LAB-ROLLING-ORIGIN-V2","target_year":target,"prior_year":py,"models":list(models),"party_order":list(PARTIES),"lambda_fit":lfit,"prior_national_share":{p:float(nat[j]) for j,p in enumerate(PARTIES)},"rows":out,"support_territories":len(out),"target_outcome_used":False,"fuzzy_matching_used":False,"forced_target_universe_coercion":False,"seat_probabilities_available":False}
    (LAB/f"pre_election_snapshot_{target}_v2.json").write_text(json.dumps(snap,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (LAB/f"point_forecast_{target}_v2.json").write_text(json.dumps(fc,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"target":target,"prior":py,"support":len(out),"lambda":lam,"mapping":pdiag["method"],"target_outcome_used":False},sort_keys=True))

if __name__=="__main__": main()
