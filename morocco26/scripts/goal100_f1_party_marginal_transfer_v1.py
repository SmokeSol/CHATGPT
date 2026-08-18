#!/usr/bin/env python3
from __future__ import annotations

import importlib.util, json
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100'; H=G/'historical'
CONTRACT=G/'f1_party_marginal_transfer_contract_v1.json'
OUT=G/'f1_party_marginal_transfer_result_v1.json'
EPS=1e-5; C80=.7182; C95=.9054

spec=importlib.util.spec_from_file_location('hb',ROOT/'scripts'/'e_reason_build_blind_holdout_bundle.py')
hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=hb.PARTIES; K=len(PARTIES)

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def load_local(y):
 d=rj(H/f'tafra_legislative_{y}_canonical.json'); rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
 if len(rows)!=92: raise RuntimeError(f'{y}: expected 92 local rows, got {len(rows)}')
 return rows

def share(row):
 x=hb.bucket_counts(row); return x/x.sum()

def mat(consts, rows):
 m=hb.match_rows(consts,rows); return np.stack([share(m[c['constituency_id']]) for c in consts])

def logit(x):
 x=np.clip(np.asarray(x,float),EPS,1-EPS); return np.log(x/(1-x))
def logistic(z): return 1/(1+np.exp(-np.asarray(z,float)))

def make_intervals(family, train_prior, train_next, held_prior):
 if family=='SHARE_SIGNED_EMPIRICAL':
  e=train_next-train_prior
  q10,q90=np.quantile(e,[.10,.90],axis=0); q025,q975=np.quantile(e,[.025,.975],axis=0)
  l80=np.clip(held_prior+q10,0,1); u80=np.clip(held_prior+q90,0,1); l95=np.clip(held_prior+q025,0,1); u95=np.clip(held_prior+q975,0,1)
 elif family=='SHARE_ABS_SYMMETRIC':
  a=np.abs(train_next-train_prior); q80=np.quantile(a,.80,axis=0); q95=np.quantile(a,.95,axis=0)
  l80=np.clip(held_prior-q80,0,1); u80=np.clip(held_prior+q80,0,1); l95=np.clip(held_prior-q95,0,1); u95=np.clip(held_prior+q95,0,1)
 elif family=='LOGIT_SIGNED_EMPIRICAL':
  e=logit(train_next)-logit(train_prior); q10,q90=np.quantile(e,[.10,.90],axis=0); q025,q975=np.quantile(e,[.025,.975],axis=0)
  z=logit(held_prior); l80=logistic(z+q10); u80=logistic(z+q90); l95=logistic(z+q025); u95=logistic(z+q975)
 else: raise KeyError(family)
 return l80,u80,l95,u95

def evaluate(family, train_prior, train_next, held_prior, held_next):
 l80,u80,l95,u95=make_intervals(family,train_prior,train_next,held_prior)
 c80=((held_next>=l80)&(held_next<=u80)).mean(axis=0); c95=((held_next>=l95)&(held_next<=u95)).mean(axis=0)
 misslow80=(held_next<l80).mean(axis=0); misshi80=(held_next>u80).mean(axis=0)
 return {
  'coverage80_by_party':{p:float(c80[j]) for j,p in enumerate(PARTIES)},
  'coverage95_by_party':{p:float(c95[j]) for j,p in enumerate(PARTIES)},
  'low_tail_miss80_by_party':{p:float(misslow80[j]) for j,p in enumerate(PARTIES)},
  'high_tail_miss80_by_party':{p:float(misshi80[j]) for j,p in enumerate(PARTIES)},
  'min_party_coverage80':float(c80.min()),'min_party_coverage95':float(c95.min()),
  'party_gate':bool(np.all(c80>=C80)&np.all(c95>=C95)),
  'mean_abs_calibration_error':float(np.mean(np.abs(c80-.80))+np.mean(np.abs(c95-.95))),
  'mean_width80':float(np.mean(u80-l80)),'mean_width95':float(np.mean(u95-l95))}

def main():
 c=rj(CONTRACT)
 if c.get('status')!='FROZEN_BEFORE_PARTY_MARGINAL_TRANSFER_EXECUTION': raise RuntimeError('contract not frozen')
 consts=hb.load_constituencies(); m11=mat(consts,load_local(2011));m16=mat(consts,load_local(2016));m21=mat(consts,load_local(2021))
 families=[x['id'] for x in c['candidate_families']]; rows=[]
 for order,fam in enumerate(families):
  a=evaluate(fam,m11,m16,m16,m21) # train 11->16, hold 16->21
  b=evaluate(fam,m16,m21,m11,m16) # train 16->21, hold 11->16
  eligible=a['party_gate'] and b['party_gate']
  rows.append({'family':fam,'order':order,'heldout_2016_TO_2021':a,'heldout_2011_TO_2016':b,'eligible':eligible,
   'selection_calibration_error':float((a['mean_abs_calibration_error']+b['mean_abs_calibration_error'])/2),
   'selection_width95':float((a['mean_width95']+b['mean_width95'])/2)})
 elig=[x for x in rows if x['eligible']]
 selected=sorted(elig,key=lambda x:(x['selection_calibration_error'],x['selection_width95'],x['order']))[0] if elig else None
 out={'schema_version':'1.0','result_id':'M26-GOAL100-F1-PARTY-MARGINAL-TRANSFER-V1','contract_id':c['contract_id'],'scientific_status':'POST_2021_DEVELOPMENT_2026_UNTOUCHED','families':rows,'eligible_family_count':len(elig),'selected_family':selected,
  'status':'PASS_PARTY_MARGINAL_TRANSFER' if selected else 'FAIL_PARTY_MARGINAL_TRANSFER_NONSTATIONARY','F0_modified':False,'E_reason_reopened':False,
  'next_action':('Freeze shared-dependence/copula construction using the selected party-marginal family, then refit on both transitions for provisional 2026 uncertainty.' if selected else 'Treat temporal regime instability as first-class. Freeze a scenario/conformal envelope over both historical regimes; do not widen a global parametric scale and do not reopen E_reason.')}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print('F1_PARTY_MARGINAL_RESULT='+json.dumps({'status':out['status'],'eligible_family_count':len(elig),'selected_family':None if selected is None else selected['family'],'diagnostic':{r['family']:{'f16to21_min80':r['heldout_2016_TO_2021']['min_party_coverage80'],'f16to21_min95':r['heldout_2016_TO_2021']['min_party_coverage95'],'f11to16_min80':r['heldout_2011_TO_2016']['min_party_coverage80'],'f11to16_min95':r['heldout_2011_TO_2016']['min_party_coverage95'],'width95':r['selection_width95']} for r in rows}},sort_keys=True))
if __name__=='__main__': main()
