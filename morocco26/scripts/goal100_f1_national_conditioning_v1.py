#!/usr/bin/env python3
from __future__ import annotations

import importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1];G=ROOT/'data'/'goal100';H=G/'historical'
CONTRACT=G/'f1_national_conditioning_contract_v1.json';OUT=G/'f1_national_conditioning_result_v1.json'
EPS=.0005; C80=.7182; C95=.9054
spec=importlib.util.spec_from_file_location('hb',ROOT/'scripts'/'e_reason_build_blind_holdout_bundle.py');hb=importlib.util.module_from_spec(spec);spec.loader.exec_module(hb)
PARTIES=hb.PARTIES;K=len(PARTIES)

def rj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def load_local(y):
 d=rj(H/f'tafra_legislative_{y}_canonical.json');rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
 if len(rows)!=92:raise RuntimeError(f'{y}: expected 92 local rows, got {len(rows)}')
 return rows

def counts(row):return hb.bucket_counts(row).astype(float)
def shares(row):
 x=counts(row);return x/x.sum()
def transition(consts,prev,next_):
 mp=hb.match_rows(consts,prev);mn=hb.match_rows(consts,next_);cids=[c['constituency_id'] for c in consts]
 prior=np.stack([shares(mp[c]) for c in cids]);actual=np.stack([shares(mn[c]) for c in cids])
 nat_prev=np.sum(np.stack([counts(mp[c]) for c in cids]),axis=0);nat_next=np.sum(np.stack([counts(mn[c]) for c in cids]),axis=0);nat_prev/=nat_prev.sum();nat_next/=nat_next.sum()
 ratio=(nat_next+EPS)/(nat_prev+EPS);cond=prior*ratio[None,:];cond/=cond.sum(axis=1,keepdims=True)
 return {'cids':cids,'prior':prior,'actual':actual,'conditional':cond,'national_prior':nat_prev,'national_next':nat_next,'national_ratio':ratio,'residual':actual-cond}

def metric(pred,actual,consts):
 e=pred-actual;mse=float(np.mean(e**2));rmse=float(np.sqrt(mse));mae=float(np.mean(np.abs(e)));by={p:float(np.sqrt(np.mean(e[:,j]**2))) for j,p in enumerate(PARTIES)}
 top=float(np.mean(np.argmax(pred,axis=1)==np.argmax(actual,axis=1)));over=[];exact=[]
 for i,c in enumerate(consts):
  s=int(c['seats']);pp=set(np.argsort(-pred[i])[:s]);aa=set(np.argsort(-actual[i])[:s]);over.append(len(pp&aa)/s);exact.append(pp==aa)
 return {'rmse':rmse,'mae':mae,'mse':mse,'rmse_by_party':by,'top_party_accuracy':top,'mean_topS_overlap':float(np.mean(over)),'exact_topS_set_accuracy':float(np.mean(exact))}

def intervals(fam,train_resid,center):
 if fam=='SHARE_SIGNED_EMPIRICAL':
  q10,q90=np.quantile(train_resid,[.10,.90],axis=0);q025,q975=np.quantile(train_resid,[.025,.975],axis=0);l80=np.clip(center+q10,0,1);u80=np.clip(center+q90,0,1);l95=np.clip(center+q025,0,1);u95=np.clip(center+q975,0,1)
 elif fam=='SHARE_ABS_SYMMETRIC':
  a=np.abs(train_resid);q80=np.quantile(a,.80,axis=0);q95=np.quantile(a,.95,axis=0);l80=np.clip(center-q80,0,1);u80=np.clip(center+q80,0,1);l95=np.clip(center-q95,0,1);u95=np.clip(center+q95,0,1)
 else:raise KeyError(fam)
 return l80,u80,l95,u95

def residual_eval(fam,train,held):
 l80,u80,l95,u95=intervals(fam,train['residual'],held['conditional']);y=held['actual'];c80=((y>=l80)&(y<=u80)).mean(axis=0);c95=((y>=l95)&(y<=u95)).mean(axis=0)
 return {'coverage80_by_party':{p:float(c80[j]) for j,p in enumerate(PARTIES)},'coverage95_by_party':{p:float(c95[j]) for j,p in enumerate(PARTIES)},'min_party_coverage80':float(c80.min()),'min_party_coverage95':float(c95.min()),'party_gate':bool(np.all(c80>=C80)&np.all(c95>=C95)),'calibration_abs_error':float(np.mean(np.abs(c80-.8))+np.mean(np.abs(c95-.95))),'width95':float(np.mean(u95-l95))}

def main():
 c=rj(CONTRACT)
 if c.get('status')!='FROZEN_BEFORE_NATIONAL_CONDITIONING_AUDIT':raise RuntimeError('contract not frozen')
 consts=hb.load_constituencies();t16=transition(consts,load_local(2011),load_local(2016));t21=transition(consts,load_local(2016),load_local(2021))
 point={}
 for label,t in [('2011_TO_2016',t16),('2016_TO_2021',t21)]:
  base=metric(t['prior'],t['actual'],consts);cond=metric(t['conditional'],t['actual'],consts);point[label]={'persistence':base,'oracle_national_conditional':cond,'relative_rmse_improvement':float((base['rmse']-cond['rmse'])/base['rmse']),'fraction_squared_error_removed':float(1-cond['mse']/base['mse']),'national_prior':{p:float(t['national_prior'][j]) for j,p in enumerate(PARTIES)},'national_next':{p:float(t['national_next'][j]) for j,p in enumerate(PARTIES)}}
 fams=[]
 for fam in c['territorial_residual_transfer']['families']:
  a=residual_eval(fam,t16,t21);b=residual_eval(fam,t21,t16);eligible=a['party_gate'] and b['party_gate'];fams.append({'family':fam,'heldout_2016_TO_2021':a,'heldout_2011_TO_2016':b,'eligible':eligible,'selection_calibration_error':float((a['calibration_abs_error']+b['calibration_abs_error'])/2),'selection_width95':float((a['width95']+b['width95'])/2)})
 elig=[x for x in fams if x['eligible']];sel=sorted(elig,key=lambda x:(x['selection_calibration_error'],x['selection_width95']))[0] if elig else None
 both_gain=all(point[k]['relative_rmse_improvement']>0 for k in point)
 if both_gain and sel is not None:status='CONDITIONAL_TRANSFER_PASS'
 elif both_gain:status='CONDITIONAL_POINT_GAIN_BUT_RESIDUAL_FAIL'
 else:status='NO_OR_MIXED_CONDITIONAL_GAIN'
 out={'schema_version':'1.0','result_id':'M26-GOAL100-F1-NATIONAL-CONDITIONING-V1','contract_id':c['contract_id'],'scientific_status':'ORACLE_DIAGNOSTIC_POST_2021_2026_UNTOUCHED','point_diagnostics':point,'territorial_residual_families':fams,'eligible_residual_family_count':len(elig),'selected_residual_family':sel,'status':status,'F0_modified':False,'oracle_is_forecast':False,'E_reason_reopened':False,'next_action':('Build a national-scenario-conditioned F1 surface and shared dependence layer; do not assign national scenario probabilities from history.' if status=='CONDITIONAL_TRANSFER_PASS' else ('Build a national-scenario-conditioned F1 surface with conservative pooled territorial envelope; do not claim unconditional calibration.' if status=='CONDITIONAL_POINT_GAIN_BUT_RESIDUAL_FAIL' else 'Revisit the conventional territorial mean mapping before any candidate or agent layer.'))}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print('F1_NATIONAL_CONDITIONING_RESULT='+json.dumps({'status':status,'2011_to_2016_rmse_gain':point['2011_TO_2016']['relative_rmse_improvement'],'2016_to_2021_rmse_gain':point['2016_TO_2021']['relative_rmse_improvement'],'2011_to_2016_topS_gain':point['2011_TO_2016']['oracle_national_conditional']['mean_topS_overlap']-point['2011_TO_2016']['persistence']['mean_topS_overlap'],'2016_to_2021_topS_gain':point['2016_TO_2021']['oracle_national_conditional']['mean_topS_overlap']-point['2016_TO_2021']['persistence']['mean_topS_overlap'],'eligible_residual_family_count':len(elig),'selected_residual_family':None if sel is None else sel['family'],'residual_diagnostics':{x['family']:{'held21_min80':x['heldout_2016_TO_2021']['min_party_coverage80'],'held21_min95':x['heldout_2016_TO_2021']['min_party_coverage95'],'held16_min80':x['heldout_2011_TO_2016']['min_party_coverage80'],'held16_min95':x['heldout_2011_TO_2016']['min_party_coverage95']} for x in fams}},sort_keys=True))
if __name__=='__main__':main()
