#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/"data"/"goal100"; HIST=G/"historical"; LAB=G/"forecast_lab"
spec=importlib.util.spec_from_file_location("hb",ROOT/"scripts"/"e_reason_build_blind_holdout_bundle.py")
hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=hb.PARTIES; CORE=hb.CORE
MODELS=("PERSIST","HALF_SHRINK","NATIONAL_ONLY")
SEED=260819; BOOT=10000

def rj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def counts(row):
    raw=row.get("votes",{})
    vals=[float(raw.get(p,0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE))
    return np.asarray(vals,float)
def load_target(year,consts):
    d=rj(HIST/f"tafra_legislative_{year}_canonical.json")
    rows=[r for r in d["rows"] if str(r.get("list_type","")).lower() in {"local","locale"}]
    if len(rows)!=92: raise RuntimeError(f"{year}: expected 92 target rows")
    m=hb.match_rows(consts,rows); cids=[c["constituency_id"] for c in consts]
    a=np.stack([counts(m[c]) for c in cids]); return a/a.sum(axis=1,keepdims=True)

def ranks(a):
    order=np.argsort(-a,axis=1); r=np.empty_like(order)
    for i in range(len(a)): r[i,order[i]]=np.arange(1,a.shape[1]+1)
    return r,order

def model_metrics(pred,actual,seats):
    err=pred-actual; rp,op=ranks(pred); ra,oa=ranks(actual)
    exact=[]; jac=[]; memb=[]; gap=[]; top1=[]
    for i,s in enumerate(seats):
        s=min(int(s),pred.shape[1]-1); ps=set(op[i,:s].tolist()); ac=set(oa[i,:s].tolist())
        exact.append(ps==ac); jac.append(len(ps&ac)/max(1,len(ps|ac)))
        memb.append(np.mean([((j in ps)==(j in ac)) for j in range(pred.shape[1])]))
        pg=pred[i,op[i,s-1]]-pred[i,op[i,s]]; ag=actual[i,oa[i,s-1]]-actual[i,oa[i,s]]
        gap.append(abs(pg-ag)); top1.append(op[i,0]==oa[i,0])
    return {
      "party_share_RMSE":float(np.sqrt(np.mean(err**2))),"party_share_MAE":float(np.mean(np.abs(err))),
      "mean_territory_L1":float(np.mean(np.sum(np.abs(err),axis=1))),"topS_exact_set_accuracy":float(np.mean(exact)),
      "topS_set_Jaccard":float(np.mean(jac)),"topS_membership_accuracy":float(np.mean(memb)),
      "top_party_accuracy":float(np.mean(top1)),"party_rank_MAE":float(np.mean(np.abs(rp-ra))),
      "topS_share_gap_MAE":float(np.mean(gap)),
      "RMSE_by_party":{p:float(np.sqrt(np.mean(err[:,j]**2))) for j,p in enumerate(PARTIES)}
    }

def bootstrap(pred,actual,comp):
    rng=np.random.default_rng(SEED); n=len(actual); deltas=[]; e1=(pred-actual)**2; e0=(comp-actual)**2
    for _ in range(BOOT):
        ix=rng.integers(0,n,size=n); deltas.append(float(np.sqrt(e1[ix].mean())-np.sqrt(e0[ix].mean())))
    a=np.asarray(deltas)
    return {"comparator":"NATIONAL_ONLY","replicates":BOOT,"cluster":"territory","probability_model_better":float(np.mean(a<0)),"delta_RMSE_model_minus_comparator_interval95":[float(np.quantile(a,.025)),float(np.quantile(a,.975))]}

def main():
    contract=rj(LAB/"forecast_skill_contract_v1.json"); consts=hb.load_constituencies(); seats=[int(c["seats"]) for c in consts]; cids=[c["constituency_id"] for c in consts]
    folds={}
    for target in (2016,2021):
        snap=rj(LAB/f"pre_election_snapshot_{target}_v1.json")
        if snap.get("target_outcome_present") is not False: raise RuntimeError("snapshot leakage")
        fc=rj(LAB/f"baseline_forecast_{target}_v1.json")
        if fc.get("target_outcome_used") is not False: raise RuntimeError("forecast leakage")
        if [r["territory_id"] for r in fc["rows"]]!=cids: raise RuntimeError("forecast territory order mismatch")
        actual=load_target(target,consts)
        pm={m:np.asarray([[r["models"][m][p] for p in PARTIES] for r in fc["rows"]],float) for m in MODELS}
        mm={m:model_metrics(pm[m],actual,seats) for m in MODELS}
        for m in ("PERSIST","HALF_SHRINK"): mm[m]["vs_NATIONAL_ONLY_bootstrap"]=bootstrap(pm[m],actual,pm["NATIONAL_ONLY"])
        order=sorted(MODELS,key=lambda m:(mm[m]["party_share_RMSE"],-mm[m]["topS_set_Jaccard"],mm[m]["party_rank_MAE"]))
        folds[str(target)]={"models":mm,"ranking_by_RMSE_then_topS":order,"winner":order[0]}
    cross={}
    for m in MODELS:
        cross[m]={"mean_RMSE":float(np.mean([folds[y]["models"][m]["party_share_RMSE"] for y in ("2016","2021")])),"mean_topS_Jaccard":float(np.mean([folds[y]["models"][m]["topS_set_Jaccard"] for y in ("2016","2021")])),"mean_rank_MAE":float(np.mean([folds[y]["models"][m]["party_rank_MAE"] for y in ("2016","2021")]))}
    cross_order=sorted(MODELS,key=lambda m:(cross[m]["mean_RMSE"],-cross[m]["mean_topS_Jaccard"],cross[m]["mean_rank_MAE"]))
    result={
      "schema_version":"1.0","result_id":"M26-FORECAST-LAB-SKILL-FLOOR-RESULT-V1","contract_id":contract["contract_id"],"historical_status":"RETROSPECTIVE_DEVELOPMENT_ONLY",
      "folds":folds,"crossfold":cross,"crossfold_ranking":cross_order,"skill_floor_winner":cross_order[0],
      "forecastability_diagnostic":{"territorial_memory_present":bool(cross["PERSIST"]["mean_RMSE"]<cross["NATIONAL_ONLY"]["mean_RMSE"]),"shrinkage_beats_raw_persistence":bool(cross["HALF_SHRINK"]["mean_RMSE"]<cross["PERSIST"]["mean_RMSE"]),"interpretation":"If territory-aware baselines beat NATIONAL_ONLY on both folds, historical geography contains reusable forecast signal. This does not establish calibrated 2026 probabilities."},
      "seat_metrics_status":"BLOCKED_CROSS_YEAR_LEGAL_ALLOCATOR_NOT_FOUND_IN_REPO_SEARCH",
      "probabilistic_status":{"2016":"BLOCKED_NO_PRE_2011_TRANSITION_FOR_EX_ANTE_RESIDUAL_CALIBRATION","2021":"POSSIBLE_USING_2011_TO_2016_BUT_NOT_IMPLEMENTED_IN_POINT_SKILL_V1","next_unlock":"ADD_2007_AND_IDEALLY_2002_FOR_ROLLING_ORIGIN_PROBABILITY_CALIBRATION"},"F0_modified":False
    }
    (LAB/"baseline_scores_v1.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"winner":cross_order[0],"crossfold":cross,"fold_winners":{y:folds[y]["winner"] for y in folds}},sort_keys=True))
if __name__=="__main__": main()
