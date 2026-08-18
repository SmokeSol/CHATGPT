#!/usr/bin/env python3
from __future__ import annotations
import csv, importlib.util, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
M=ROOT/'morocco26'; G=M/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'; H=G/'historical'
CONTRACT=G/'e_collect'/'candidate_intelligence_v2_predictive_contract_v1.json'
POWER=CI/'candidate_intelligence_v2_power_gate_collision_resolved_final_v1.json'
LOCAL_RES=CI/'local2015_collision_resolution_v1.json'; A21_RES=CI/'2021'/'pjd_prior_mp_identity_resolution_v2.json'
OUT=CI/'candidate_intelligence_v2_predictive_gate_v1.json'
RIDGE=[0.01,0.1,1.0,10.0,100.0]; SEED=260818; NBOOT=10000; EPS=1e-9

spec=importlib.util.spec_from_file_location('hb',M/'scripts'/'e_reason_build_blind_holdout_bundle.py'); hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=hb.PARTIES; PJD_INDEX=PARTIES.index('PJD')

def rj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def jsonl(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x.strip()]
def logit(p):
 p=np.clip(np.asarray(p,dtype=float),EPS,1-EPS);return np.log(p/(1-p))
def logistic(z):return 1/(1+np.exp(-np.asarray(z,dtype=float)))
def shares(row):
 raw=row.get('votes',{}); vals=[float(raw.get(p,0) or 0) for p in hb.CORE]; vals.append(sum(float(v or 0) for k,v in raw.items() if k not in hb.CORE)); a=np.array(vals,float); return a/a.sum()
def load_hist(year):
 d=rj(H/f'tafra_legislative_{year}_canonical.json'); rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]; assert len(rows)==92; return rows

def feature_maps():
 A16={r['territory_id']:r['feature_state'] for r in jsonl(CI/'2016'/'pjd_reconciled_head_prior_mp_v1.jsonl')}
 A21={r['territory_id']:r['feature_state'] for r in jsonl(CI/'2021'/'pjd_reconciled_head_prior_mp_v1.jsonl')}
 for d in rj(A21_RES)['decisions']:
  if d['territory_id'] in A21 and A21[d['territory_id']]=='UNKNOWN':A21[d['territory_id']]=d['state']
 B16={r['territory_id']:r['state'] for r in jsonl(CI/'2016'/'pjd_local2015_collision_safe_v1.jsonl')}
 B21={r['territory_id']:r['state'] for r in jsonl(CI/'2021'/'pjd_local2015_collision_safe_v1.jsonl')}
 for d in rj(LOCAL_RES)['decisions']:
  b=B16 if d['transition']=='2011_TO_2016' else B21
  if d['territory_id'] in b and b[d['territory_id']]=='UNKNOWN':b[d['territory_id']]=d['state']
 cv=lambda s:1.0 if s=='VERIFIED_TRUE' else (0.0 if s=='VERIFIED_FALSE' else None)
 return ({k:cv(v) for k,v in A16.items()},{k:cv(v) for k,v in B16.items()},{k:cv(v) for k,v in A21.items()},{k:cv(v) for k,v in B21.items()})

def apply_shift(base,delta):
 p=float(base[PJD_INDEX]); q=float(logistic(logit(p)+delta)); out=np.array(base,float); denom=max(EPS,1-p); scale=(1-q)/denom
 for i in range(len(out)):
  if i==PJD_INDEX:out[i]=q
  else:out[i]*=scale
 out/=out.sum(); return out

def fit_beta(X,y,alpha):return np.linalg.solve(X.T@X+float(alpha)*np.eye(X.shape[1]),X.T@y)
def metrics(pred,base,obs,cids):
 pjd_e=np.array([pred[c][PJD_INDEX]-obs[c][PJD_INDEX] for c in cids]); pjd_b=np.array([base[c][PJD_INDEX]-obs[c][PJD_INDEX] for c in cids]);
 all_e=np.stack([pred[c]-obs[c] for c in cids]); all_b=np.stack([base[c]-obs[c] for c in cids])
 return {'model':{'PJD_RMSE':float(np.sqrt(np.mean(pjd_e**2))),'PJD_MAE':float(np.mean(np.abs(pjd_e))),'ALL_PARTY_RMSE':float(np.sqrt(np.mean(all_e**2))),'ALL_PARTY_L1':float(np.mean(np.abs(all_e).sum(axis=1)))},'C0':{'PJD_RMSE':float(np.sqrt(np.mean(pjd_b**2))),'PJD_MAE':float(np.mean(np.abs(pjd_b))),'ALL_PARTY_RMSE':float(np.sqrt(np.mean(all_b**2))),'ALL_PARTY_L1':float(np.mean(np.abs(all_b).sum(axis=1)))},'_sq_pjd_model':pjd_e**2,'_sq_pjd_c0':pjd_b**2,'_mse_all_model':np.mean(all_e**2,axis=1),'_mse_all_c0':np.mean(all_b**2,axis=1)}
def comparison(m):
 rng=np.random.default_rng(SEED); n=len(m['_sq_pjd_model']); idx=rng.integers(0,n,size=(NBOOT,n))
 bp_m=np.sqrt(m['_sq_pjd_model'][idx].mean(axis=1));bp_c=np.sqrt(m['_sq_pjd_c0'][idx].mean(axis=1));ba_m=np.sqrt(m['_mse_all_model'][idx].mean(axis=1));ba_c=np.sqrt(m['_mse_all_c0'][idx].mean(axis=1))
 def one(vm,vc,bm,bc):
  delta=vm-vc; bd=bm-bc; return {'point_delta_model_minus_C0':float(delta),'relative_improvement':float((vc-vm)/vc),'bootstrap_probability_model_better':float(np.mean(bd<0)),'percentile_95_interval_delta':[float(np.quantile(bd,.025)),float(np.quantile(bd,.975))]}
 return {'PJD_RMSE':one(m['model']['PJD_RMSE'],m['C0']['PJD_RMSE'],bp_m,bp_c),'ALL_PARTY_RMSE':one(m['model']['ALL_PARTY_RMSE'],m['C0']['ALL_PARTY_RMSE'],ba_m,ba_c)}

def main():
 contract=rj(CONTRACT); power=rj(POWER); assert power['status']=='PASS_REASONER_POWER_COLLISION_SAFE'; assert contract['eligibility']['required_prior_gate']=='PASS_REASONER_POWER_COLLISION_SAFE'
 consts=hb.load_constituencies(); bycid={c['constituency_id']:c for c in consts}; rows11=hb.load_local(2011); rows16=hb.load_local(2016); rows21=load_hist(2021); m11=hb.match_rows(consts,rows11);m16=hb.match_rows(consts,rows16);m21=hb.match_rows(consts,rows21)
 base16={c['constituency_id']:shares(m11[c['constituency_id']]) for c in consts}; bstar=hb.reproduce_bstar_v0(consts,rows11,rows16); base21={c['constituency_id']:np.array([bstar[c['constituency_id']]['mean'][p] for p in PARTIES],float) for c in consts}; obs16={c['constituency_id']:shares(m16[c['constituency_id']]) for c in consts};obs21={c['constituency_id']:shares(m21[c['constituency_id']]) for c in consts}
 A16,B16,A21,B21=feature_maps(); fit=sorted(k for k in B16 if k in A16 and A16[k] is not None and B16[k] is not None); val=sorted(k for k in B21 if k in A21 and A21[k] is not None and B21[k] is not None); assert len(fit)==74 and len(val)==74
 X=np.array([[A16[c],B16[c]] for c in fit],float); means=X.mean(axis=0);Xc=X-means; y=np.array([float(logit(obs16[c][PJD_INDEX])-logit(base16[c][PJD_INDEX])) for c in fit]); regions={c:bycid[c]['region'] for c in fit}; region_names=sorted(set(regions.values()))
 cv=[]
 for alpha in RIDGE:
  errs=[]; fold=[]
  for region in region_names:
   tr=np.array([regions[c]!=region for c in fit]);te=~tr; beta=fit_beta(Xc[tr],y[tr],alpha); cap=float(np.quantile(np.abs(y[tr]),.90)); deltas=np.clip(Xc[te]@beta,-cap,cap); ids=[fit[i] for i in np.where(te)[0]]; pe=[]
   for cid,d in zip(ids,deltas): pe.append((apply_shift(base16[cid],float(d))[PJD_INDEX]-obs16[cid][PJD_INDEX])**2)
   errs.extend(pe);fold.append({'region':region,'n':len(ids),'PJD_RMSE':float(np.sqrt(np.mean(pe)))})
  cv.append({'alpha':alpha,'mean_heldout_PJD_RMSE':float(np.sqrt(np.mean(errs))),'folds':fold})
 selected=sorted(cv,key=lambda z:(z['mean_heldout_PJD_RMSE'],-z['alpha']))[0]['alpha'];beta=fit_beta(Xc,y,selected); cap=float(np.quantile(np.abs(y),.90))
 pred16={c:apply_shift(base16[c],float(np.clip(np.dot(np.array([A16[c],B16[c]])-means,beta),-cap,cap))) for c in fit}; pred21={c:apply_shift(base21[c],float(np.clip(np.dot(np.array([A21[c],B21[c]])-means,beta),-cap,cap))) for c in val}
 met16=metrics(pred16,base16,obs16,fit);met21=metrics(pred21,base21,obs21,val);cmp21=comparison(met21)
 clean=lambda m:{k:v for k,v in m.items() if not k.startswith('_')}
 rule=contract['interpretation_rules']; pjd=cmp21['PJD_RMSE']; allp=cmp21['ALL_PARTY_RMSE'];
 if pjd['relative_improvement']>0 and allp['relative_improvement']>0 and pjd['bootstrap_probability_model_better']>=.90: status='POSITIVE_RETROSPECTIVE_SIGNAL'
 elif pjd['relative_improvement']>0 or allp['relative_improvement']>0: status='WEAK_RETROSPECTIVE_SIGNAL'
 else: status='NO_RETROSPECTIVE_PREDICTIVE_SIGNAL'
 out={'schema_version':'1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-PREDICTIVE-GATE-V1','contract_id':contract['contract_id'],'scientific_status':contract['scientific_status'],'panel':{'fit_2016_territories':len(fit),'validation_2021_territories':len(val),'fit_territory_ids':fit,'validation_territory_ids':val},'feature_means_fit':{'V2_HEAD_PRIOR_CYCLE_MP':float(means[0]),'V2_HEAD_ELECTED_LOCAL_COUNCIL_2015':float(means[1])},'ridge_cv':cv,'selected_alpha':selected,'beta':{'V2_HEAD_PRIOR_CYCLE_MP':float(beta[0]),'V2_HEAD_ELECTED_LOCAL_COUNCIL_2015':float(beta[1])},'effect_cap_abs_logit_shift':cap,'fit_2011_TO_2016':clean(met16),'validation_2016_TO_2021':clean(met21),'validation_comparisons':cmp21,'terminal_interpretation':status,'forecast_modified':False,'llm_invoked':False,'implementation_note':'All feature definitions and the deterministic model contract were frozen before this feature-specific retrospective scoring. 2021 is not a blind holdout.'}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps({'status':status,'selected_alpha':selected,'beta':out['beta'],'fit_PJD_RMSE_model':out['fit_2011_TO_2016']['model']['PJD_RMSE'],'fit_PJD_RMSE_C0':out['fit_2011_TO_2016']['C0']['PJD_RMSE'],'val_PJD_RMSE_model':out['validation_2016_TO_2021']['model']['PJD_RMSE'],'val_PJD_RMSE_C0':out['validation_2016_TO_2021']['C0']['PJD_RMSE'],'val_PJD_relative':pjd['relative_improvement'],'val_PJD_p':pjd['bootstrap_probability_model_better'],'val_all_relative':allp['relative_improvement'],'val_all_p':allp['bootstrap_probability_model_better']},sort_keys=True))
if __name__=='__main__':main()
