#!/usr/bin/env python3
from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CI=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2'
CONTRACT=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2_reasoner_power_contract_v1.json'
LOCAL_RES=CI/'local2015_collision_resolution_v1.json'
A21_RES=CI/'2021'/'pjd_prior_mp_identity_resolution_v2.json'
OUT=CI/'candidate_intelligence_v2_power_gate_collision_resolved_final_v1.json'

PATHS={
 '2011_TO_2016':{
  'A':CI/'2016'/'pjd_reconciled_head_prior_mp_v1.jsonl',
  'B':CI/'2016'/'pjd_local2015_collision_safe_v1.jsonl'},
 '2016_TO_2021':{
  'A':CI/'2021'/'pjd_reconciled_head_prior_mp_v1.jsonl',
  'B':CI/'2021'/'pjd_local2015_collision_safe_v1.jsonl'},
}

def load_jsonl(p):
 return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]

def phi(n00,n01,n10,n11):
 den=(n11+n10)*(n01+n00)*(n11+n01)*(n10+n00)
 if den<=0:return None
 return (n11*n00-n10*n01)/math.sqrt(den)

def main():
 contract=json.loads(CONTRACT.read_text(encoding='utf-8')); req=contract['joint_identifiability_requirements_each_transition']
 local_res=json.loads(LOCAL_RES.read_text(encoding='utf-8'))
 r_by={(d['transition'],d['territory_id']):d for d in local_res['decisions']}
 a21={d['territory_id']:d for d in json.loads(A21_RES.read_text(encoding='utf-8'))['decisions']}
 transitions={}
 for label,paths in PATHS.items():
  A={r['territory_id']:r for r in load_jsonl(paths['A'])}; B={r['territory_id']:r for r in load_jsonl(paths['B'])}
  # Apply only explicit prior-MP resolutions that replace UNKNOWN.
  if label=='2016_TO_2021':
   for tid,d in a21.items():
    if tid in A and A[tid].get('feature_state')=='UNKNOWN': A[tid]={**A[tid],'feature_state':d['state'],'final_identity_resolution':d}
  # Apply only explicit local-council resolutions that replace UNKNOWN.
  applied=[]
  for tid,row in list(B.items()):
   d=r_by.get((label,tid))
   if d is None: continue
   if row.get('state')!='UNKNOWN': raise RuntimeError(f'local collision resolution can only replace UNKNOWN: {label} {tid} {row.get("state")}')
   B[tid]={**row,'state':d['state'],'final_identity_resolution':d}; applied.append({'territory_id':tid,'state':d['state'],'method':d['method']})
  bstates=Counter(r.get('state') for r in B.values()); bknown=bstates['VERIFIED_TRUE']+bstates['VERIFIED_FALSE']; bpos=bstates['VERIFIED_TRUE']
  bpower={'rows':len(B),'states':dict(bstates),'known':bknown,'positive':bpos,'coverage_gate':bknown>=74,'support_gate':bpos>=30,'gate_pass':bknown>=74 and bpos>=30,'resolutions_applied':applied}
  common=sorted(set(A)&set(B)); rows=[]; unknown=[]
  for tid in common:
   sa=A[tid].get('feature_state'); sb=B[tid].get('state')
   if sa not in {'VERIFIED_TRUE','VERIFIED_FALSE'} or sb not in {'VERIFIED_TRUE','VERIFIED_FALSE'}:
    unknown.append({'territory_id':tid,'A_state':sa,'B_state':sb}); continue
   rows.append((tid,1 if sa=='VERIFIED_TRUE' else 0,1 if sb=='VERIFIED_TRUE' else 0))
  pats=Counter(f'{a}{b}' for _,a,b in rows); n00,n01,n10,n11=(pats['00'],pats['01'],pats['10'],pats['11']); p=phi(n00,n01,n10,n11); joint=len(rows); discord=n01+n10; pattern5=sum(pats[k]>=5 for k in ('00','01','10','11'))
  gates={'joint_coverage':joint>=req['minimum_joint_known_territories'],'phi':p is not None and abs(p)<=req['maximum_absolute_phi'],'discordance':discord>=req['minimum_discordant_cells_A10_plus_A01'],'patterns':pattern5>=req['minimum_joint_patterns_with_at_least_5_cells'],'both_values':({a for _,a,_ in rows}=={0,1} and {b for _,_,b in rows}=={0,1}) if req['require_both_feature_values_present'] else True}
  transitions[label]={'B_data_power':bpower,'joint_known_territories':joint,'unknown_joint_rows':unknown,'patterns':{'00':n00,'01':n01,'10':n10,'11':n11},'discordant_cells_01_plus_10':discord,'phi':p,'absolute_phi':None if p is None else abs(p),'patterns_with_at_least_5_cells':pattern5,'gates':gates,'gate_pass':bpower['gate_pass'] and all(gates.values())}
 passed=all(v['gate_pass'] for v in transitions.values())
 out={'schema_version':'1.0','gate_id':'M26-CANDIDATE-INTELLIGENCE-V2-COLLISION-RESOLVED-FINAL-POWER-GATE-V1','contract_id':contract['contract_id'],'contract_frozen_at':contract['frozen_at'],'feature_A':'V2_HEAD_PRIOR_CYCLE_MP','feature_B':'V2_HEAD_ELECTED_LOCAL_COUNCIL_2015','local_collision_resolution_artifact':str(LOCAL_RES.relative_to(ROOT)),'A21_resolution_artifact':str(A21_RES.relative_to(ROOT)),'transitions':transitions,'status':'PASS_REASONER_POWER_COLLISION_SAFE' if passed else 'FAIL_REASONER_POWER_COLLISION_SAFE','llm_treatment_authorized':False,'next_if_pass':'Freeze predictive/model specification and prospective C1-vs-C2 contrast before any LLM call.','forecast_modified':False,'predictive_value_estimated':False}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
