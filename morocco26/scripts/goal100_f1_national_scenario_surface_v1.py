#!/usr/bin/env python3
from __future__ import annotations

import importlib.util, json, math, sys
from collections import defaultdict
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100';H=G/'historical';G75=ROOT/'data'/'goal75'
CONTRACT=G/'f1_national_scenario_surface_contract_v1.json';NPOST=G/'local_N_posterior.json';OUT=G/'f1_national_scenario_surface_v1.json'
EPS=.0005; RNG_SEED=26081877
sys.path.insert(0,str(ROOT/'scripts'));sys.path.insert(0,str(ROOT/'src'))
import goal100_run_fminus1 as eng
import goal100_fminus1_runtime_v4 as rt

spec=importlib.util.spec_from_file_location('hb',ROOT/'scripts'/'e_reason_build_blind_holdout_bundle.py');hb=importlib.util.module_from_spec(spec);spec.loader.exec_module(hb)
PARTIES=hb.PARTIES;CORE=eng.CORE;K=len(PARTIES)

def rj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def share9(row):
 x=eng.bucket_counts(row).astype(float);return x/x.sum()
def clr_share(s):
 a=np.clip(np.asarray(s,float),1e-9,1);z=np.log(a);return z-z.mean(axis=-1,keepdims=True)
def inv_clr(z):
 a=np.asarray(z,float);a=a-a.max(axis=-1,keepdims=True);e=np.exp(a);return e/e.sum(axis=-1,keepdims=True)
def normvec(x):
 a=np.asarray(x,float);a=np.maximum(a,1e-12);return a/a.sum()
def year_by_repo(year):
 rows=eng.load_year(year);mapping=eng.build_mapping(rows);return {mapping[hid]['constituency_id']:{'row':row,'repo':mapping[hid],'historical_id':hid} for hid,row in rows.items()}
def natshare(byrepo):
 c=np.sum(np.stack([eng.bucket_counts(v['row']).astype(float) for v in byrepo.values()]),axis=0);return c/c.sum()
def conditional(prior,nat_prev,nat_next):return normvec(np.asarray(prior,float)*((np.asarray(nat_next)+EPS)/(np.asarray(nat_prev)+EPS)))
def residual_map(prev,next_,nat_prev,nat_next):
 out={}
 for tid in sorted(set(prev)&set(next_)):
  p=share9(prev[tid]['row']);y=share9(next_[tid]['row']);c=conditional(p,nat_prev,nat_next);out[tid]=(clr_share(y)-clr_share(c)).reshape(-1)
 return out

def valid_fraction_by_repo(y11):
 raw=[];ids=[]
 for tid,v in y11.items():
  r=v['row'];reg=int(r['registered_reported']);turn=float(r['turnout_rate_reported']);ratio=sum(int(x) for x in r['votes'].values())/(reg*turn);raw.append(ratio);ids.append(tid)
 arr=np.asarray(raw,float);p05,p95=np.quantile(arr,[.05,.95]);med=float(np.median(arr));final=np.clip(.5*np.clip(arr,p05,p95)+.5*med,1e-6,1.0);return {tid:float(final[i]) for i,tid in enumerate(ids)}
def N_centres():
 d=rj(NPOST);rows=d['local']['rows_detail'];return {r['constituency_id']:int(r['posterior']['center']) for r in rows}
def bucket_from_actual(seats,parties):
 out=np.zeros(K,dtype=int);idx={p:i for i,p in enumerate(PARTIES)}
 for j,p in enumerate(parties):out[idx[p if p in CORE else 'OTHER']]+=int(seats[j])
 return out

def allocate_one(shares,row,registered,valid,magnitude,rng):
 s=np.asarray(shares,float).reshape(1,-1).copy();probs,parties,diag=rt.build_actual_probabilities(s,{str(p):int(v) for p,v in row['votes'].items()});vv=np.asarray([max(int(valid),len(parties))],dtype=np.int64);nn=np.asarray([int(registered)],dtype=np.int64);counts=rt.support_vote_round(probs,vv,rng);seats,binding=rt.vectorized_allocate(counts,nn,int(magnitude));tie=False
 if bool(binding[0]):
  alloc,event=rt.resolve_binding_tie_by_exchangeable_age(counts[0],int(registered),int(magnitude));seats[0]=alloc;tie=True
 return bucket_from_actual(seats[0],parties),{'active_lists':len(parties),'tie_age_prior_used':tie,'parties':parties}
def regional_rows_2021(regions):
 d=rj(H/'tafra_legislative_2021_canonical.json');rows=[r for r in d['rows'] if eng.norm(r.get('list_type'))=='regionale'];out={}
 for r in rows:
  reg=eng.match_region(r.get('region') or r.get('constituency'),regions);out[reg]=r
 if len(out)!=12:raise RuntimeError(f'regional rows !=12: {len(out)}')
 return out

def main():
 c=rj(CONTRACT)
 if c.get('status')!='FROZEN_BEFORE_SCENARIO_SURFACE_EXECUTION':raise RuntimeError('scenario contract not frozen')
 y11=year_by_repo(2011);y16=year_by_repo(2016);y21=year_by_repo(2021)
 if len(y11)!=len(y16)!=len(y21):pass
 tids=sorted(y21);n11=natshare(y11);n16=natshare(y16);n21=natshare(y21)
 scenarios={
  'NO_SWING_2021':n21,
  'REPLAY_2011_TO_2016':normvec(n21*((n16+EPS)/(n11+EPS))),
  'REPLAY_2016_TO_2021':normvec(n21*((n21+EPS)/(n16+EPS))),
 }
 residuals={'CENTRAL_PROPORTIONAL_SWING':{tid:np.zeros(K) for tid in tids},'REPLAY_2011_TO_2016_TERRITORIAL_RESIDUAL':residual_map(y11,y16,n11,n16),'REPLAY_2016_TO_2021_TERRITORIAL_RESIDUAL':residual_map(y16,y21,n16,n21)}
 ncenter=N_centres();vf=valid_fraction_by_repo(y11);regions=sorted({v['repo']['region'] for v in y21.values()});r21=regional_rows_2021(regions)
 # F-1 regional valid-vote bridge, frozen mechanically from 2021.
 obs_local=defaultdict(int)
 for tid,v in y21.items():obs_local[v['repo']['region']]+=sum(int(x) for x in v['row']['votes'].values())
 raw_ratio=np.asarray([sum(int(x) for x in r21[reg]['votes'].values())/obs_local[reg] for reg in regions],float);p05,p95=np.quantile(raw_ratio,[.05,.95]);reg_ratio={reg:float(.5*np.clip(raw_ratio[i],p05,p95)+.5) for i,reg in enumerate(regions)}
 results={}
 for si,(sid,snat) in enumerate(scenarios.items()):
  ratio=(snat+EPS)/(n21+EPS);styles={}
  for ri,(rid,rmap) in enumerate(residuals.items()):
   rng=np.random.default_rng(RNG_SEED+si*100+ri);rt.AGE_RNG=np.random.default_rng(RNG_SEED+5000+si*100+ri);local_total=np.zeros(K,int);regional_total=np.zeros(K,int);local_details=[];region_valid=defaultdict(int);region_resids=defaultdict(list)
   for tid in tids:
    v=y21[tid];base=normvec(share9(v['row'])*ratio);res=np.asarray(rmap.get(tid,np.zeros(K)),float);sh=inv_clr(clr_share(base)+res);reg=v['repo']['region'];registered=ncenter[tid];turn=float(v['row']['turnout_rate_reported']);valid=int(math.floor(registered*turn*vf[tid]));valid=max(1,min(valid,registered));seats,diag=allocate_one(sh,v['row'],registered,valid,int(v['repo']['seats']),rng);local_total+=seats;region_valid[reg]+=valid;region_resids[reg].append(res);local_details.append({'constituency_id':tid,'name':v['repo']['name'],'region':reg,'magnitude':int(v['repo']['seats']),'conditional_share':{p:float(sh[j]) for j,p in enumerate(PARTIES)},'seat_buckets':{p:int(seats[j]) for j,p in enumerate(PARTIES) if int(seats[j])},'registered_center':registered,'turnout_2021_mean':turn,'valid_votes_structural':valid,'active_list_count':diag['active_lists'],'tie_age_prior_used':diag['tie_age_prior_used']})
   regional_details=[]
   for reg in regions:
    row=r21[reg];prior=share9(row);base=normvec(prior*ratio);mean_res=np.mean(np.stack(region_resids[reg]),axis=0) if region_resids[reg] else np.zeros(K);sh=inv_clr(clr_share(base)+mean_res);registered=sum(ncenter[tid] for tid in tids if y21[tid]['repo']['region']==reg);valid=int(round(region_valid[reg]*reg_ratio[reg]));valid=max(1,min(valid,registered));seats,diag=allocate_one(sh,row,registered,valid,int(row['seats']),rng);regional_total+=seats;regional_details.append({'region':reg,'magnitude':int(row['seats']),'conditional_share':{p:float(sh[j]) for j,p in enumerate(PARTIES)},'seat_buckets':{p:int(seats[j]) for j,p in enumerate(PARTIES) if int(seats[j])},'registered_center_sum':registered,'valid_votes_structural':valid,'active_list_count':diag['active_lists'],'tie_age_prior_used':diag['tie_age_prior_used']})
   total=local_total+regional_total
   if int(local_total.sum())!=305 or int(regional_total.sum())!=90 or int(total.sum())!=395:raise RuntimeError(f'seat invariant failed {sid}/{rid}: {local_total.sum()}/{regional_total.sum()}/{total.sum()}')
   styles[rid]={'local_305':{p:int(local_total[j]) for j,p in enumerate(PARTIES)},'regional_90':{p:int(regional_total[j]) for j,p in enumerate(PARTIES)},'house_395':{p:int(total[j]) for j,p in enumerate(PARTIES)},'local':local_details,'regional':regional_details}
  envelope={p:{'min':min(styles[r]['house_395'][p] for r in styles),'max':max(styles[r]['house_395'][p] for r in styles)} for p in PARTIES}
  results[sid]={'national_share':{p:float(snat[j]) for j,p in enumerate(PARTIES)},'territorial_styles':styles,'house_395_envelope_across_historical_territorial_styles':envelope}
 out={'schema_version':'1.0','result_id':'M26-GOAL100-F1-NATIONAL-SCENARIO-SURFACE-V1','contract_id':c['contract_id'],'status':'F1_CONDITIONAL_SCENARIO_SURFACE_PROVISIONAL','probabilistic_forecast':False,'2026_legal_ballot_certified':False,'F0_modified':False,'E_reason_reopened':False,'historical_national_vectors':{'2011':{p:float(n11[j]) for j,p in enumerate(PARTIES)},'2016':{p:float(n16[j]) for j,p in enumerate(PARTIES)},'2021':{p:float(n21[j]) for j,p in enumerate(PARTIES)}},'scenarios':results,'mandatory_disclosure':['These are conditional stress surfaces, not scenario probabilities.','Ballot support is still the frozen 2021 contest universe, not the final 2026 legal ballot.','Registered counts are latent posterior centres, not official 2026 local counts.','Territorial styles are historical residual replays, not calibrated 2026 probabilities.'],'next_action':'Replace provisional list support with the certified 2026 legal ballot when available; then freeze a 2026 scenario-conditioned conventional seat surface before any candidate-delta or E_reason incremental test.'}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 compact={sid:{rid:results[sid]['territorial_styles'][rid]['house_395'] for rid in results[sid]['territorial_styles']} for sid in results}
 print('F1_SCENARIO_SURFACE_RESULT='+json.dumps({'status':out['status'],'house_seats':compact,'envelopes':{sid:results[sid]['house_395_envelope_across_historical_territorial_styles'] for sid in results}},ensure_ascii=False,sort_keys=True))
if __name__=='__main__':main()
