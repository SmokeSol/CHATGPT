#!/usr/bin/env python3
from __future__ import annotations
import json, math
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
CI=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2'
CONTRACT=ROOT/'morocco26'/'data'/'goal100'/'e_collect'/'candidate_intelligence_v2_reasoner_power_contract_v1.json'
OUT=CI/'candidate_intelligence_v2_reasoner_power_gate_v1.json'
PATHS={
 '2011_TO_2016':{
  'A':CI/'2016'/'pjd_reconciled_head_prior_mp_v1.jsonl',
  'B':CI/'2016'/'pjd_local2015_closed_universe_v1.jsonl'},
 '2016_TO_2021':{
  'A':CI/'2021'/'pjd_reconciled_head_prior_mp_v1.jsonl',
  'B':CI/'2021'/'pjd_local2015_closed_universe_v1.jsonl'}}

def load_jsonl(path):
 return [json.loads(x) for x in path.read_text(encoding='utf-8').splitlines() if x.strip()]

def phi(n00,n01,n10,n11):
 den=(n11+n10)*(n01+n00)*(n11+n01)*(n10+n00)
 if den<=0:return None
 return (n11*n00-n10*n01)/math.sqrt(den)

def eval_transition(label, paths, req):
 A={r['territory_id']:r for r in load_jsonl(paths['A'])}
 B={r['territory_id']:r for r in load_jsonl(paths['B'])}
 common=sorted(set(A)&set(B)); rows=[]; unknown=[]
 for tid in common:
  sa=A[tid].get('feature_state'); sb=B[tid].get('council_member_state')
  if sa not in {'VERIFIED_TRUE','VERIFIED_FALSE'} or sb not in {'VERIFIED_TRUE','VERIFIED_FALSE'}:
   unknown.append({'territory_id':tid,'A_state':sa,'B_state':sb}); continue
  a=1 if sa=='VERIFIED_TRUE' else 0; b=1 if sb=='VERIFIED_TRUE' else 0; rows.append((tid,a,b))
 pats=Counter(f'{a}{b}' for _,a,b in rows)
 n00=pats['00'];n01=pats['01'];n10=pats['10'];n11=pats['11'];p=phi(n00,n01,n10,n11)
 joint=len(rows); discord=n01+n10; pattern5=sum(1 for k in ('00','01','10','11') if pats[k]>=5); bothA={a for _,a,_ in rows}=={0,1};bothB={b for _,_,b in rows}=={0,1}
 gates={
  'joint_coverage':joint>=req['minimum_joint_known_territories'],
  'phi':p is not None and abs(p)<=req['maximum_absolute_phi'],
  'discordance':discord>=req['minimum_discordant_cells_A10_plus_A01'],
  'patterns':pattern5>=req['minimum_joint_patterns_with_at_least_5_cells'],
  'both_values':bothA and bothB if req['require_both_feature_values_present'] else True}
 return {
  'transition':label,'A_rows':len(A),'B_rows':len(B),'territories_intersection':len(common),'joint_known_territories':joint,'unknown_joint_rows':unknown,
  'patterns':{'00':n00,'01':n01,'10':n10,'11':n11},'discordant_cells_01_plus_10':discord,'phi':p,'absolute_phi':abs(p) if p is not None else None,
  'patterns_with_at_least_5_cells':pattern5,'A_values_present':sorted({a for _,a,_ in rows}),'B_values_present':sorted({b for _,_,b in rows}),
  'gates':gates,'gate_pass':all(gates.values())}

def main():
 c=json.loads(CONTRACT.read_text(encoding='utf-8'));req=c['joint_identifiability_requirements_each_transition']
 results={k:eval_transition(k,v,req) for k,v in PATHS.items()};passed=all(v['gate_pass'] for v in results.values())
 out={
  'schema_version':'1.0','gate_id':'M26-CANDIDATE-INTELLIGENCE-V2-REASONER-POWER-GATE-V1','contract_id':c['contract_id'],'contract_frozen_at':c['frozen_at'],
  'feature_A':'V2_HEAD_PRIOR_CYCLE_MP','feature_B':'V2_HEAD_ELECTED_LOCAL_COUNCIL_2015','feature_B_selection_reason':'Executive candidate failed >=30 positive support; council membership passed in both transitions under frozen priority rule.',
  'transitions':results,'status':'PASS_REASONER_POWER' if passed else 'FAIL_REASONER_POWER','llm_treatment_authorized':False,
  'next_if_pass':'Freeze a separate immutable E_reason V2 model/reasoner specification and prospective C1-vs-C2 contrast surface before invoking any LLM.',
  'forecast_modified':False,'predictive_value_estimated':False}
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');print(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
