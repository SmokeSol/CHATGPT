#!/usr/bin/env python3
from __future__ import annotations

import importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/"data"/"goal100"; HIST=G/"historical"; LAB=G/"forecast_lab"/"rolling_origin_v2"
spec=importlib.util.spec_from_file_location("rg",ROOT/"scripts"/"forecast_lab_rolling_generate_v2.py")
rg=importlib.util.module_from_spec(spec); spec.loader.exec_module(rg)
PARTIES=rg.PARTIES; MODELS=("NATIONAL_ONLY","HALF_SHRINK","PERSIST","ROLLING_LAMBDA")
SEED=26081927; BOOT=10000

def load_target(year):
    p=rg.path_for(year); d=rg.rj(p)
    rows=list(d["local_rows"]) if year==2007 else [r for r in d["rows"] if str(r.get("list_type","")).lower() in {"local","locale"}]
    expected=95 if year==2007 else 92
    if len(rows)!=expected: raise RuntimeError(f"BAD_TARGET_ROW_COUNT_{year}_{len(rows)}")
    return p,rows

def ranks(a):
    order=np.argsort(-a,axis=1); r=np.empty_like(order)
    for i in range(len(a)): r[i,order[i]]=np.arange(1,a.shape[1]+1)
    return r,order

def metrics(pred,actual,seats):
    err=pred-actual; rp,op=ranks(pred); ra,oa=ranks(actual); exact=[]; jac=[]; memb=[]; gap=[]; top1=[]
    for i,s0 in enumerate(seats):
        s=max(1,min(int(s0),pred.shape[1]-1)); ps=set(op[i,:s]); ac=set(oa[i,:s]); exact.append(ps==ac); jac.append(len(ps&ac)/max(1,len(ps|ac)))
        memb.append(np.mean([((j in ps)==(j in ac)) for j in range(pred.shape[1])]))
        gap.append(abs((pred[i,op[i,s-1]]-pred[i,op[i,s]])-(actual[i,oa[i,s-1]]-actual[i,oa[i,s]]))); top1.append(op[i,0]==oa[i,0])
    return {"party_share_RMSE":float(np.sqrt(np.mean(err**2))),"party_share_MAE":float(np.mean(np.abs(err))),"mean_territory_L1":float(np.mean(np.sum(np.abs(err),axis=1))),"topS_exact_set_accuracy":float(np.mean(exact)),"topS_set_Jaccard":float(np.mean(jac)),"topS_membership_accuracy":float(np.mean(memb)),"top_party_accuracy":float(np.mean(top1)),"party_rank_MAE":float(np.mean(np.abs(rp-ra))),"topS_share_gap_MAE":float(np.mean(gap)),"RMSE_by_party":{p:float(np.sqrt(np.mean(err[:,j]**2))) for j,p in enumerate(PARTIES)},"sse":float(np.sum(err**2)),"n_cells":int(err.size)}

def bootstrap(pred,actual,comp):
    rng=np.random.default_rng(SEED); n=len(actual); e1=(pred-actual)**2; e0=(comp-actual)**2; d=[]
    for _ in range(BOOT):
        ix=rng.integers(0,n,size=n); d.append(float(np.sqrt(e1[ix].mean())-np.sqrt(e0[ix].mean())))
    a=np.asarray(d); return {"comparator":"NATIONAL_ONLY","replicates":BOOT,"cluster":"territory","probability_model_better":float(np.mean(a<0)),"delta_RMSE_model_minus_comparator_interval95":[float(np.quantile(a,.025)),float(np.quantile(a,.975))]}

def project(x):
    a=np.maximum(np.asarray(x,float),0.0); s=a.sum(axis=1,keepdims=True); return a/np.where(s>0,s,1)

def decompose(fc,prior_terr,actual,target_rows):
    prior_nat=np.asarray([fc["prior_national_share"][p] for p in PARTIES],float); target_nat=rg.nat_share(target_rows)
    pres=prior_terr-prior_nat[None,:]; ares=actual-target_nat[None,:]
    corr=float(np.corrcoef(pres.ravel(),ares.ravel())[0,1]) if np.std(pres)>0 and np.std(ares)>0 else None
    oracle0=np.repeat(target_nat[None,:],len(actual),axis=0); base=float(np.sqrt(np.mean((oracle0-actual)**2)))
    cand=[]
    for lam in np.linspace(0,1,101):
        pred=project(target_nat[None,:]+float(lam)*pres); cand.append((float(np.sqrt(np.mean((pred-actual)**2))),float(lam)))
    ormse,olam=min(cand,key=lambda x:(x[0],x[1]))
    return {"prior_national_share":{p:float(prior_nat[j]) for j,p in enumerate(PARTIES)},"target_national_share":{p:float(target_nat[j]) for j,p in enumerate(PARTIES)},"national_shift_RMSE":float(np.sqrt(np.mean((prior_nat-target_nat)**2))),"national_shift_L1":float(np.sum(np.abs(prior_nat-target_nat))),"territorial_residual_correlation":corr,"oracle_target_national_only_RMSE":base,"oracle_target_national_plus_prior_residual_RMSE":ormse,"oracle_territorial_lambda":olam,"oracle_territorial_relative_improvement":float((base-ormse)/base) if base>0 else 0.0,"oracle_warning":"Uses target national shares after outcome open; diagnostic only, never a deployable forecast."}

def main():
    folds={}; total={m:[0.0,0] for m in MODELS}
    for target in (2011,2016,2021):
        snap=rg.rj(LAB/f"pre_election_snapshot_{target}_v2.json"); fc=rg.rj(LAB/f"point_forecast_{target}_v2.json")
        if snap.get("target_outcome_present") is not False or fc.get("target_outcome_used") is not False: raise RuntimeError(f"FORECAST_LEAKAGE_FLAG_{target}")
        _,ar=load_target(target); am,adiag=rg.exact_modern_map(target,ar); fr={r["territory_id"]:r for r in fc["rows"]}; order,_=rg.meta(); ids=[r["constituency_id"] for r in order if r["constituency_id"] in fr and r["constituency_id"] in am]
        dropped=[i for i in fr if i not in am]
        if not ids: raise RuntimeError(f"ZERO_SCORE_SUPPORT_{target}")
        actual=np.stack([rg.share(am[i]) for i in ids]); seats=[int(am[i].get("seats",am[i].get("magnitude",1))) for i in ids]
        pm={m:np.asarray([[fr[i]["models"][m][p] for p in PARTIES] for i in ids],float) for m in MODELS}; mm={m:metrics(pm[m],actual,seats) for m in MODELS}
        for m in ("HALF_SHRINK","PERSIST","ROLLING_LAMBDA"): mm[m]["vs_NATIONAL_ONLY_bootstrap"]=bootstrap(pm[m],actual,pm["NATIONAL_ONLY"])
        for m in MODELS: total[m][0]+=mm[m]["sse"]; total[m][1]+=mm[m]["n_cells"]
        rank=sorted(MODELS,key=lambda m:(mm[m]["party_share_RMSE"],-mm[m]["topS_set_Jaccard"],mm[m]["party_rank_MAE"]))
        folds[str(target)]={"transition":f"{fc['prior_year']}->{target}","forecast_support":fc["support_territories"],"score_support":len(ids),"score_support_fraction_of_92":len(ids)/92.0,"dropped_forecast_ids_without_exact_target_resolution":sorted(dropped),"target_mapping":adiag,"lambda_fit":fc["lambda_fit"],"models":mm,"ranking_by_RMSE_then_topS":rank,"winner":rank[0],"national_territorial_decomposition":decompose(fc,pm["PERSIST"],actual,ar)}
    cross={m:{"weighted_RMSE":float(np.sqrt(total[m][0]/total[m][1])),"n_cells":total[m][1]} for m in MODELS}; ranking=sorted(MODELS,key=lambda m:cross[m]["weighted_RMSE"])
    result={"schema_version":"2.0","result_id":"M26-FORECAST-LAB-ROLLING-ORIGIN-RESULT-V2","contract_id":"M26-FORECAST-LAB-ROLLING-ORIGIN-V2","scientific_status":"STRICT_ROLLING_ORIGIN_RETROSPECTIVE_BACKTEST","folds":folds,"crossfold":cross,"crossfold_ranking":ranking,"winner":ranking[0],"anti_leakage":{"target_opened_only_by_scorer":True,"fuzzy_matching_used":False,"forced_92_coercion":False,"2007_gate_required":True},"probabilistic_status":{"2011":"COLD_START_NO_PRIOR_TRANSITION_RESIDUALS","2016":"ONE_PRIOR_TRANSITION_NOW_AVAILABLE_FOR_EX_ANTE_RESIDUAL_CALIBRATION","2021":"TWO_PRIOR_TRANSITIONS_NOW_AVAILABLE_FOR_EX_ANTE_RESIDUAL_CALIBRATION","2026":"THREE_COMPLETED_TRANSITIONS_AVAILABLE_AFTER_FINAL_MODEL_FREEZE"},"seat_metrics_status":"TOP_S_ONLY_NOT_LEGAL_SEAT_ALLOCATOR","F0_modified":False}
    (LAB/"rolling_origin_scores_v2.json").write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["scientific_status"],"winner":result["winner"],"weighted_RMSE":cross[result["winner"]]["weighted_RMSE"],"supports":{y:folds[y]["score_support"] for y in folds},"lambdas":{y:folds[y]["lambda_fit"]["selected_lambda"] for y in folds}},sort_keys=True))

if __name__=="__main__": main()
