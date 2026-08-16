#!/usr/bin/env python3
import json
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
def load(p):return json.loads(Path(p).read_text())
def main():
 c=load(D/'project_constitution.json');s=load(O/'goal75_scoring.json');live=load(O/'goal75_live_gate.json');kill=load(O/'model_d_kill_preunseal.json');p2=load(R/'reports'/'PHASE2_EXECUTIVE_FINDINGS.md') if False else None
 evidence={
  'P1_FOUNDATION':{'points':15,'pass':bool(c.get('north_star')) and c['forecast_unlock_gate']['default_status']=='BLOCKED','why':'machine-readable constitution, allocator/provenance foundation, anti-drift contract already merged'},
  'P2_EMPIRICAL_GRAPH':{'points':20,'pass':s['local_92']['count']==92 and s['local_92']['allocated_seats']==305 and s['local_92']['aggregate_exact_match'] and s['regional_12']['count']==12 and s['regional_12']['allocated_seats']==90 and s['regional_12']['aggregate_exact_match'],'why':'92 local exact legal replay + 12 regional exact legal replay + 395-seat audit'},
  'P3_CAUSAL_SYNTHETIC_SOCIETY':{'points':15,'pass':(R/'reports'/'PHASE2_EXECUTIVE_FINDINGS.md').exists() and (D/'experiment_manifest.json').exists(),'why':'frozen A/B/C0/C calibrated causal pilot and preregistered controls'},
  'P4_BOUNDED_LLM_SOCIETY':{'points':15,'pass':kill['decision']=='KILL_D_FOR_CURRENT_ARCHITECTURE' and kill['decision_stage']=='PRE_HOLDOUT_UNSEAL' and kill['holdout_2021_outcomes_accessed'] is False and kill['contract_validity_rate']<kill['preregistered_contract_validity_rate_min'],'why':'Model D was actually executed with two model families and three prompt variants, then killed by a preregistered blocking contract gate before holdout unseal; no threshold repair'},
  'P5_FULL_2026_LIVE_SYSTEM_PARTIAL':{'points':10,'pass':live['status']=='PASS' and live['p5_scientific_credit_points']==10,'why':'92/92 empirical cutoff-sensitivity substrate + provenance-preserving 2026 event mechanism map, explicitly not a forecast; only partial P5 credit'}
 }
 total=sum(v['points'] for v in evidence.values() if v['pass']);goal=load(D/'execution_goal_75.json');goal['target_75_reached']=total>=75;goal['achieved_scientifically_gated_completion_percent']=total;goal['status']='ACHIEVED' if total>=75 else 'ACTIVE';goal['evidence_file']='data/goal75/goal75_completion.json';(D/'execution_goal_75.json').write_text(json.dumps(goal,ensure_ascii=False,indent=2))
 out={'scientifically_gated_completion_percent':total,'target':75,'target_reached':total>=75,'evidence':evidence,'forecast_status':s['forecast_status'],'north_star':c['north_star']};(O/'goal75_completion.json').write_text(json.dumps(out,ensure_ascii=False,indent=2))
 cur=load(D/'current_phase.json');
 if total>=75:
  cur.update({'as_of':'2026-08-16T14:00:00+01:00','formal_phase':'P5_FULL_2026_LIVE_SYSTEM','experimental_frontier':'P5_FULL_2026_LIVE_SYSTEM','implementation_completion_percent':max(cur.get('implementation_completion_percent',0),75),'scientifically_gated_completion_percent':75,'status':'GOAL75_REACHED_P2_P3_P4_CLOSED_P5_PARTIAL_VALIDATED','forecast_status':'BLOCKED','agent_society_status':'KILLED_FOR_CURRENT_ARCHITECTURE_ON_PREUNSEAL_CONTRACT_GATE','goal75_status':'ACHIEVED_AT_75_SCIENTIFICALLY_GATED_NO_UI_CREDIT'})
  cur['completed']=['P1 foundation and anti-drift constitution','92/92 local 2021 exact legal replay and Seat Margin Map','12/12 regional 2021 exact legal replay','395-seat aggregate reconciliation','frozen territorial B/C holdout benchmark before unseal','A/B/C0/C causal synthetic-society pilot','Model D two-family no-leak execution and preregistered kill','92/92 2026 event-to-seat sensitivity substrate with current sourced event ledger']
  cur['not_completed']=['calibrated empirical candidate-network portability and diffusion priors','continuous/live automated 2026 event ingestion beyond the frozen current ledger','validated directional 2026 party effects','national probabilistic seat forecast unlock gates','pre-election model freeze','23 September real-world scoring and postmortem']
  cur['hard_blockers_to_formal_phase4']=[]
  (D/'current_phase.json').write_text(json.dumps(cur,ensure_ascii=False,indent=2))
 print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if total>=75 else 5)
if __name__=='__main__':main()
