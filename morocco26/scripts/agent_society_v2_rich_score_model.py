from __future__ import annotations
import math,random
from collections import defaultdict
from agent_society_v2_rich_score_common import ARCHETYPES
BOOTSTRAP_REPS=10000;BOOTSTRAP_SEED=260819
def aggregate(valid,priv):
 g=defaultdict(list)
 for k,v in valid.items():g[k[:3]].append((k[4],v))
 a={}
 for (eid,tid,cid),items in g.items():
  if len(items)!=ARCHETYPES:raise RuntimeError('incomplete territory-condition')
  w=priv['weights_by_election_territory_archetype'][eid][tid];l2g=priv['local_party_to_global_by_election_territory'][eid][tid];parties=tuple(sorted(l2g.values()));mass={p:0. for p in parties};turn=0.;seen=set()
  for aid,v in items:
   if aid in seen:raise RuntimeError('duplicate archetype')
   seen.add(aid);ww=float(w[aid]);u=v['turnout'];turn+=ww*u
   for lp,pv in v['probs'].items():mass[l2g[lp]]+=ww*u*pv
  den=sum(mass.values());a[(eid,tid,cid)]={'turnout':turn,'shares':{p:mass[p]/den for p in parties}}
 true=next(k for k,v in priv['condition_role_by_id'].items() if v=='AS2_LLM_INDEPENDENT');shuf=next(k for k,v in priv['condition_role_by_id'].items() if v=='AS2_SHUFFLED_CONTEXT');pred={'C0':{},'R3_TRUE':{},'R3_SHUFFLED':{}}
 for eid in priv['year_by_anonymous_election_id']:
  for tid,base in priv['baseline_vote_share_global_by_election_territory'][eid].items():
   k=(eid,tid);pred['C0'][k]={'shares':{p:float(x) for p,x in base.items()}};pred['R3_TRUE'][k]=a[(eid,tid,true)];pred['R3_SHUFFLED'][k]=a[(eid,tid,shuf)]
 return pred
def outcome_maps(out16,out21,recon,map21,pop21,priv):
 o16={str(r['id_constituency']):r for r in out16['rows'] if r.get('list_type')=='locale'};o21={str(r['id_constituency']):r for r in out21['rows'] if r.get('list_type')=='locale'};e16=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2016);e21=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2021);t16={a:str(r) for a,r in recon['territory_mapping_anonymous_to_historical_id'].items()};p16={r:a for a,r in recon['party_mapping'].items()};slugid={t['constituency_id']:str(t['prior_historical_match']['id_constituency']) for t in pop21['territories']};t21={a:slugid[s] for s,a in map21['territories'].items()};p21=dict(map21['parties'])
 def build(eid,tids,pmap,rows):
  other=pmap['OTHER'];res={}
  for tid,rid in tids.items():
   acc={p:0. for p in set(pmap.values())}
   for real,v in rows[rid]['votes'].items():acc[pmap.get(real,other)]+=float(v)
   z=sum(acc.values());res[(eid,tid)]={'shares':{p:acc[p]/z for p in sorted(acc)}}
  return res
 r={};r.update(build(e16,t16,p16,o16));r.update(build(e21,t21,p21,o21));return r
def keys_for(priv,year,direct=False):
 eid=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==year);t=sorted(priv['baseline_vote_share_global_by_election_territory'][eid])
 if direct:t=[x for x in t if priv['geography_confidence_by_election_territory'][eid][x]=='DIRECT_MICRODATA_ADMIN']
 return [(eid,x) for x in t]
def metric(pred,obs,keys):
 sq=[];mse=[];l1=[];ok=0
 for k in keys:
  ps=sorted(obs[k]['shares']);d=[pred[k]['shares'][p]-obs[k]['shares'][p] for p in ps];sq += [x*x for x in d];mse.append(sum(x*x for x in d)/len(d));l1.append(sum(abs(x) for x in d));ok+=max(ps,key=lambda p:pred[k]['shares'][p])==max(ps,key=lambda p:obs[k]['shares'][p])
 return {'macro_party_share_RMSE':math.sqrt(sum(sq)/len(sq)),'mean_constituency_L1':sum(l1)/len(l1),'top_party_accuracy':ok/len(keys),'territory_mse':mse}
def bootstrap(a,b):
 r=random.Random(BOOTSTRAP_SEED);n=len(a);d=[];better=0
 for _ in range(BOOTSTRAP_REPS):
  ix=[r.randrange(n) for _ in range(n)];x=math.sqrt(sum(a[i] for i in ix)/n)-math.sqrt(sum(b[i] for i in ix)/n);d.append(x);better+=x<0
 d.sort();return {'replicates':BOOTSTRAP_REPS,'seed':BOOTSTRAP_SEED,'probability_treatment_better':better/BOOTSTRAP_REPS,'percentile_95_interval_delta_RMSE':[d[int(.025*len(d))],d[min(len(d)-1,int(.975*len(d)))]]}
