#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, math
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[2]
M=ROOT/'morocco26';G=M/'data'/'goal100';CI=G/'e_collect'/'candidate_intelligence_v2';H=G/'historical'
CONTRACT=G/'e_collect'/'candidate_intelligence_v2_multipart_head_contract_v1.json';POWER=CI/'candidate_intelligence_v2_multipart_head_power_gate_v1.json';D16=CI/'multipart'/'2016_head_prior_mp_features_v1.jsonl';D21=CI/'multipart'/'2021_head_prior_mp_features_v1.jsonl';OUT=CI/'candidate_intelligence_v2_multipart_head_predictive_gate_v1.json'
RIDGE=[0.01,0.1,1.0,10.0,100.0];NBOOT=10000;SEED=260818;EPS=1e-9
spec=importlib.util.spec_from_file_location('hb',M/'scripts'/'e_reason_build_blind_holdout_bundle.py');hb=importlib.util.module_from_spec(spec);spec.loader.exec_module(hb)
PARTIES=hb.PARTIES

def rj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def jsonl(p):return [json.loads(x) for x in Path(p).read_text(encoding='utf-8').splitlines() if x.strip()]
def logit(p):
 p=float(np.clip(p,EPS,1-EPS));return math.log(p/(1-p))
def logistic(z):return 1/(1+math.exp(-float(z)))
def shares(row):
 raw=row.get('votes',{});vals=[float(raw.get(p,0) or 0) for p in hb.CORE];vals.append(sum(float(v or 0) for k,v in raw.items() if k not in hb.CORE));a=np.array(vals,float);return a/a.sum()
def load_hist(year):
 d=rj(H/f'tafra_legislative_{year}_canonical.json');rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}];assert len(rows)==92;return rows
def fit_beta(X,y,alpha):return np.linalg.solve(X.T@X+alpha*np.eye(X.shape[1]),X.T@y)
def party_means(rows,features,target=None):
 out={}
 for p in ('PJD','RNI'):
  ix=[i for i,r in enumerate(rows) if r['party']==p];out[p]={'x':np.mean([[1.0 if rows[i]['feature_states'][f]=='VERIFIED_TRUE' else 0.0 for f in features] for i in ix],axis=0)}
  if target is not None:out[p]['y']=float(np.mean([target[i] for i in ix]))
 return out
def matrices(rows,features,base,obs,means=None,center_y=False):
 rawX=np.array([[1.0 if r['feature_states'][f]=='VERIFIED_TRUE' else 0.0 for f in features] for r in rows],float);y=np.array([logit(obs[(r['party'],r['territory_id'])])-logit(base[(r['party'],r['territory_id'])]) for r in rows],float)
 if means is None:means=party_means(rows,features,y)
 X=np.array([rawX[i]-means[r['party']]['x'] for i,r in enumerate(rows)],float);yy=np.array([y[i]-means[r['party']].get('y',0.0) if center_y else y[i] for i,r in enumerate(rows)],float);return X,yy,y,means
def apply(base_share,delta):return logistic(logit(base_share)+delta)
def metric(pred,base,obs,rows):
 e=np.array([pred[(r['party'],r['territory_id'])]-obs[(r['party'],r['territory_id'])] for r in rows]);b=np.array([base[(r['party'],r['territory_id'])]-obs[(r['party'],r['territory_id'])] for r in rows]);return {'model_RMSE':float(np.sqrt(np.mean(e**2))),'C0_RMSE':float(np.sqrt(np.mean(b**2))),'model_MAE':float(np.mean(np.abs(e))),'C0_MAE':float(np.mean(np.abs(b))),'sq_model':e**2,'sq_C0':b**2}
def bootstrap(m):
 rng=np.random.default_rng(SEED);n=len(m['sq_model']);ix=rng.integers(0,n,size=(NBOOT,n));rm=np.sqrt(m['sq_model'][ix].mean(axis=1));rb=np.sqrt(m['sq_C0'][ix].mean(axis=1));d=rm-rb;return {'point_delta_model_minus_C0':m['model_RMSE']-m['C0_RMSE'],'relative_improvement':(m['C0_RMSE']-m['model_RMSE'])/m['C0_RMSE'],'bootstrap_probability_model_better':float(np.mean(d<0)),'percentile_95_interval_delta':[float(np.quantile(d,.025)),float(np.quantile(d,.975))]}
def clean(m):return {k:v for k,v in m.items() if not k.startswith('sq_')}
def main():
 contract=rj(CONTRACT);power=rj(POWER)
 if power.get('status')!='PASS_MULTIPART_HEAD_POWER':raise RuntimeError(f'power gate not PASS: {power.get("status")}')
 features=power['eligible_features'];
 if not features:raise RuntimeError('no eligible features')
 rows16=[r for r in jsonl(D16) if r['party'] in {'PJD','RNI'} and all(r['feature_states'][f] in {'VERIFIED_TRUE','VERIFIED_FALSE'} for f in features)];rows21=[r for r in jsonl(D21) if r['party'] in {'PJD','RNI'} and all(r['feature_states'][f] in {'VERIFIED_TRUE','VERIFIED_FALSE'} for f in features)]
 const=hb.load_constituencies();bycid={c['constituency_id']:c for c in const};m11=hb.match_rows(const,hb.load_local(2011));m16=hb.match_rows(const,hb.load_local(2016));m21=hb.match_rows(const,load_hist(2021));bstar=hb.reproduce_bstar_v0(const,hb.load_local(2011),hb.load_local(2016))
 idx={p:PARTIES.index(p) for p in ('PJD','RNI')};base16={};obs16={};base21={};obs21={}
 for r in rows16:
  k=(r['party'],r['territory_id']);base16[k]=float(shares(m11[r['territory_id']])[idx[r['party']]]);obs16[k]=float(shares(m16[r['territory_id']])[idx[r['party']]])
 for r in rows21:
  k=(r['party'],r['territory_id']);base21[k]=float(bstar[r['territory_id']]['mean'][r['party']]);obs21[k]=float(shares(m21[r['territory_id']])[idx[r['party']]])
 regions=sorted(set(bycid[r['territory_id']]['region'] for r in rows16));cv=[]
 for alpha in RIDGE:
  sq=[];folds=[]
  for reg in regions:
   tr=[r for r in rows16 if bycid[r['territory_id']]['region']!=reg];te=[r for r in rows16 if bycid[r['territory_id']]['region']==reg]
   # All centering quantities come from the training fold only.
   _,_,yt,_=matrices(tr,features,base16,obs16,means=None,center_y=False);means=party_means(tr,features,yt);Xtr,ytr,_,_=matrices(tr,features,base16,obs16,means=means,center_y=True);beta=fit_beta(Xtr,ytr,float(alpha));Xte,_,_,_=matrices(te,features,base16,obs16,means=means,center_y=False);pred=[]
   for i,r in enumerate(te):pred.append(apply(base16[(r['party'],r['territory_id'])],float(Xte[i]@beta)))
   err=np.array([pred[i]-obs16[(r['party'],r['territory_id'])] for i,r in enumerate(te)]);sq.extend(err**2);folds.append({'region':reg,'n':len(te),'RMSE':float(np.sqrt(np.mean(err**2)))})
  cv.append({'alpha':float(alpha),'mean_heldout_focal_RMSE':float(np.sqrt(np.mean(sq))),'folds':folds})
 selected=sorted(cv,key=lambda z:(z['mean_heldout_focal_RMSE'],-z['alpha']))[0]['alpha'];_,_,yraw,means=matrices(rows16,features,base16,obs16,means=None,center_y=False);means=party_means(rows16,features,yraw);X16,y16,_,_=matrices(rows16,features,base16,obs16,means=means,center_y=True);beta=fit_beta(X16,y16,float(selected));X21,_,_,_=matrices(rows21,features,base21,obs21,means=means,center_y=False)
 pred16={(r['party'],r['territory_id']):apply(base16[(r['party'],r['territory_id'])],float(X16[i]@beta)) for i,r in enumerate(rows16)};pred21={(r['party'],r['territory_id']):apply(base21[(r['party'],r['territory_id'])],float(X21[i]@beta)) for i,r in enumerate(rows21)}
 pooled16=metric(pred16,base16,obs16,rows16);pooled21=metric(pred21,base21,obs21,rows21);comp=bootstrap(pooled21);per={}
 for p in ('PJD','RNI'):
  rr=[r for r in rows21 if r['party']==p];mm=metric(pred21,base21,obs21,rr);per[p]={'metrics':clean(mm),'comparison':bootstrap(mm)}
 favorable=all(per[p]['comparison']['relative_improvement']>0 for p in ('PJD','RNI'))
 if comp['relative_improvement']>=.005 and comp['bootstrap_probability_model_better']>=.90 and favorable:status='MATERIAL_MULTIPART_RETROSPECTIVE_SIGNAL'
 elif comp['relative_improvement']>0:status='WEAK_MULTIPART_RETROSPECTIVE_SIGNAL'
 else:status='NO_MULTIPART_RETROSPECTIVE_SIGNAL'
 out={'schema_version':'1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-HEAD-PREDICTIVE-GATE-V1','contract_id':contract['contract_id'],'scientific_status':contract['scientific_status'],'eligible_features':features,'fit_cells':len(rows16),'validation_cells':len(rows21),'fit_cells_by_party':{p:sum(r['party']==p for r in rows16) for p in ('PJD','RNI')},'validation_cells_by_party':{p:sum(r['party']==p for r in rows21) for p in ('PJD','RNI')},'selected_alpha':selected,'beta':{f:float(beta[i]) for i,f in enumerate(features)},'fit_party_feature_means':{p:{f:float(means[p]['x'][i]) for i,f in enumerate(features)} for p in ('PJD','RNI')},'ridge_cv':cv,'fit':clean(pooled16),'validation':clean(pooled21),'validation_comparison':comp,'validation_by_party':per,'terminal_interpretation':status,'llm_invoked':False,'forecast_modified':False,'note':'2021 is retrospective/burned; no deployment authority.'};OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps({'status':status,'features':features,'fit_cells':len(rows16),'validation_cells':len(rows21),'selected_alpha':selected,'beta':out['beta'],'pooled_relative':comp['relative_improvement'],'pooled_p':comp['bootstrap_probability_model_better'],'PJD_relative':per['PJD']['comparison']['relative_improvement'],'RNI_relative':per['RNI']['comparison']['relative_improvement']},sort_keys=True))
if __name__=='__main__':main()
