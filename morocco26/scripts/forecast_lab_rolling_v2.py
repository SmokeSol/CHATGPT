#!/usr/bin/env python3
from __future__ import annotations
import csv, hashlib, importlib.util, json
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100'; HIST=G/'historical'; LAB=G/'forecast_lab'
MODELS=('NATIONAL_ONLY','HALF_SHRINK','PERSIST')
LAMBDA={'NATIONAL_ONLY':0.0,'HALF_SHRINK':0.5,'PERSIST':1.0}
SEED=260819; BOOT=10000

spec=importlib.util.spec_from_file_location('hb',ROOT/'scripts'/'e_reason_build_blind_holdout_bundle.py')
hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=list(hb.PARTIES); CORE=list(hb.CORE)

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256();
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def counts(row):
    raw=row.get('votes',{}) or {}
    vals=[float(raw.get(p,0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE))
    a=np.asarray(vals,float)
    if np.any(a<0) or a.sum()<=0: raise RuntimeError('invalid vote vector')
    return a
def share(a): return a/a.sum(axis=1,keepdims=True)
def load_consts():
    with (ROOT/'data'/'constituencies_goal75.csv').open(encoding='utf-8',newline='') as f:
        return list(csv.DictReader(f))
def target_modern(year,consts):
    d=rj(HIST/f'tafra_legislative_{year}_canonical.json')
    rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
    mp=hb.match_rows(hb.load_constituencies(),rows)
    cids=[c['constituency_id'] for c in consts]
    a=np.stack([counts(mp[c]) for c in cids])
    return share(a),mp
def prior_modern(year,consts):
    actual,mp=target_modern(year,consts)
    cids=[c['constituency_id'] for c in consts]
    raw=np.stack([counts(mp[c]) for c in cids])
    return raw,actual

def metrics(pred,actual,seats):
    err=pred-actual
    op=np.argsort(-pred,axis=1); oa=np.argsort(-actual,axis=1)
    top=[]; jac=[]
    for i,s in enumerate(seats):
        s=min(int(s),pred.shape[1]-1)
        ps=set(op[i,:s].tolist()); ac=set(oa[i,:s].tolist())
        jac.append(len(ps&ac)/max(1,len(ps|ac))); top.append(op[i,0]==oa[i,0])
    return {'party_share_RMSE':float(np.sqrt(np.mean(err**2))),
            'party_share_MAE':float(np.mean(np.abs(err))),
            'mean_territory_L1':float(np.mean(np.sum(np.abs(err),axis=1))),
            'topS_set_Jaccard':float(np.mean(jac)),
            'top_party_accuracy':float(np.mean(top))}
def bootstrap(pred,actual,comp):
    rng=np.random.default_rng(SEED); n=len(actual); e1=(pred-actual)**2; e0=(comp-actual)**2
    d=np.empty(BOOT)
    for k in range(BOOT):
        ix=rng.integers(0,n,size=n); d[k]=np.sqrt(e1[ix].mean())-np.sqrt(e0[ix].mean())
    return {'replicates':BOOT,'cluster':'territory','probability_model_better':float(np.mean(d<0)),
            'delta_RMSE_model_minus_NATIONAL_ONLY_interval95':[float(np.quantile(d,.025)),float(np.quantile(d,.975))]}
def build_models(territory,national):
    out={}
    for m,lmb in LAMBDA.items():
        x=lmb*territory+(1-lmb)*national[None,:]
        out[m]=x/x.sum(axis=1,keepdims=True)
    return out

def fold_2007_2011(consts):
    gate=rj(HIST/'2007'/'acceptance_gate_v2.json')
    if gate.get('scientific_status')!='PASS_FOR_ROLLING_ORIGIN_BACKTEST': raise RuntimeError('2007 gate not PASS')
    src=rj(HIST/'2007'/'legislative_2007_outcome_canonical.json')['local_rows']
    by_native={r['native_id']:r for r in src}
    raw_all=np.stack([counts(r) for r in src]); national=raw_all.sum(axis=0); national/=national.sum()
    cw=rj(HIST/'2007'/'crosswalk_to_modern.json')['rows']
    candidate=defaultdict(list)
    for r in cw:
        tg=r.get('modern_targets') or []
        if r.get('mapping_type')!='UNRESOLVED' and len(tg)==1 and r.get('native_id') in by_native:
            candidate[tg[0]['constituency_id']].append(r['native_id'])
    cids=[c['constituency_id'] for c in consts]; pos={cid:i for i,cid in enumerate(cids)}
    mapped=[cid for cid in cids if cid in candidate and len(candidate[cid])==1]
    if not mapped: raise RuntimeError('no conservative 2007->modern mappings')
    territory=np.stack([counts(by_native[candidate[cid][0]]) for cid in mapped]); territory=share(territory)
    actual_all,_=target_modern(2011,consts); idx=[pos[cid] for cid in mapped]; actual=actual_all[idx]
    seats=[int(consts[i]['seats']) for i in idx]
    models=build_models(territory,national); mm={m:metrics(models[m],actual,seats) for m in MODELS}
    for m in ('HALF_SHRINK','PERSIST'): mm[m]['vs_NATIONAL_ONLY_bootstrap']=bootstrap(models[m],actual,models['NATIONAL_ONLY'])
    full_nat=np.repeat(national[None,:],len(consts),axis=0)
    return {'origin_year':2007,'target_year':2011,'support_policy':'COMMON_EXPLICIT_1_TO_1_CROSSWALK_ONLY',
            'origin_native_territories':len(src),'target_native_territories':len(consts),'mapped_territories':len(mapped),
            'mapped_territory_ids':mapped,'models':mm,'national_only_full_target':metrics(full_nat,actual_all,[int(c['seats']) for c in consts])}
def fold_direct(origin,target,consts):
    raw,territory=prior_modern(origin,consts); national=raw.sum(axis=0); national/=national.sum()
    actual,_=target_modern(target,consts); models=build_models(territory,national); seats=[int(c['seats']) for c in consts]
    mm={m:metrics(models[m],actual,seats) for m in MODELS}
    for m in ('HALF_SHRINK','PERSIST'): mm[m]['vs_NATIONAL_ONLY_bootstrap']=bootstrap(models[m],actual,models['NATIONAL_ONLY'])
    return {'origin_year':origin,'target_year':target,'support_policy':'FULL_NATIVE_IDENTITY_92','origin_native_territories':len(consts),
            'target_native_territories':len(consts),'mapped_territories':len(consts),'models':mm}
def main():
    LAB.mkdir(parents=True,exist_ok=True); consts=load_consts()
    folds=[fold_2007_2011(consts),fold_direct(2011,2016,consts),fold_direct(2016,2021,consts)]
    cross={m:{'mean_RMSE':float(np.mean([f['models'][m]['party_share_RMSE'] for f in folds])),
              'mean_L1':float(np.mean([f['models'][m]['mean_territory_L1'] for f in folds])),
              'mean_topS_Jaccard':float(np.mean([f['models'][m]['topS_set_Jaccard'] for f in folds]))} for m in MODELS}
    ranking=sorted(MODELS,key=lambda m:(cross[m]['mean_RMSE'],-cross[m]['mean_topS_Jaccard'],cross[m]['mean_L1']))
    winner=ranking[0]
    result={'schema_version':'2.0','result_id':'M26-ROLLING-ORIGIN-SKILL-FLOOR-V2','historical_status':'RETROSPECTIVE_ROLLING_ORIGIN',
            'folds':{str(f['target_year']):f for f in folds},'crossfold':cross,'crossfold_ranking':ranking,'skill_floor_winner':winner,
            'lambda_selected_for_2026':LAMBDA[winner],
            'selection_rule':'Lowest equal-weight mean fold RMSE; tie-break topS Jaccard then L1. Lambda grid frozen at {0,0.5,1}.',
            'integrity':{'2007_acceptance_gate':'PASS_FOR_ROLLING_ORIGIN_BACKTEST','no_95_to_92_coercion':True,
                         '2007_territorial_scoring_only_on_explicit_one_to_one_crosswalk':True,'F0_modified':False}}
    (LAB/'baseline_scores_v2.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    raw21,terr21=prior_modern(2021,consts); nat21=raw21.sum(axis=0); nat21/=nat21.sum(); models=build_models(terr21,nat21)
    rows=[]
    for i,c in enumerate(consts):
        rows.append({'territory_id':c['constituency_id'],'territory_name':c['name'],'region':c['region'],'seats':int(c['seats']),
                     'models':{m:{p:float(models[m][i,j]) for j,p in enumerate(PARTIES)} for m in MODELS}})
    w=raw21.sum(axis=1); sel=models[winner]; national2026=(sel*w[:,None]).sum(axis=0)/w.sum()
    fc={'schema_version':'2.0','forecast_id':'M26-FORECAST-2026-ROLLING-ORIGIN-SKILL-FLOOR-V2','target_year':2026,'prior_year':2021,
        'model':winner,'lambda':LAMBDA[winner],'party_order':PARTIES,'rows':rows,
        'national_share_prior_turnout_weighted':{p:float(national2026[j]) for j,p in enumerate(PARTIES)},
        'target_outcome_used':False,'forecast_status':'PROSPECTIVE_POINT_SKILL_FLOOR_NOT_OFFICIAL_F0',
        'seat_forecast_status':'NOT_EMITTED_POINT_SHARES_ALONE_DO_NOT_IDENTIFY_2026_REGISTERED_AND_TURNOUT_COUNTS',
        'interpretation':'Prospective structural skill-floor forecast selected only from 2007→2011, 2011→2016 and 2016→2021 historical folds.'}
    (LAB/'baseline_forecast_2026_v2.json').write_text(json.dumps(fc,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    snap={'schema_version':'2.0','snapshot_id':'M26-PRE-ELECTION-SNAPSHOT-2026-ROLLING-V2','target_year':2026,'target_outcome_present':False,
          'inputs':[{'path':'data/goal100/historical/tafra_legislative_2021_canonical.json','sha256':sha(HIST/'tafra_legislative_2021_canonical.json')},
                    {'path':'data/constituencies_goal75.csv','sha256':sha(ROOT/'data'/'constituencies_goal75.csv')},
                    {'path':'data/goal100/historical/2007/acceptance_gate_v2.json','sha256':sha(HIST/'2007'/'acceptance_gate_v2.json')}],
          'selection_evidence':'baseline_scores_v2.json','selected_model':winner,'selected_lambda':LAMBDA[winner]}
    (LAB/'pre_election_snapshot_2026_v2.json').write_text(json.dumps(snap,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    summary={'winner':winner,'lambda':LAMBDA[winner],'crossfold':cross,
             'folds':{str(f['target_year']):{'mapped_territories':f['mapped_territories'],'rmse':{m:f['models'][m]['party_share_RMSE'] for m in MODELS}} for f in folds},
             'national_2026':fc['national_share_prior_turnout_weighted']}
    (LAB/'run_summary_v2.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print('ROLLING_ORIGIN_RESULT='+json.dumps(summary,ensure_ascii=False,sort_keys=True))
if __name__=='__main__': main()
