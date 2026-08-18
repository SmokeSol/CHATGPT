#!/usr/bin/env python3
"""Certify that E_reason historical collection is scientifically closed.

This is additive and does not mutate the preregistered current-state artifact.
It requires the strict 2016 integrity gate and the independent 2021 collection
gate to pass while all outcome/judgment/F1 leakage flags remain false.
"""
from __future__ import annotations
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
G16=ER/'evidence/strict_2016_integrity_gate/gate.json'
G21=ER/'evidence/2021_head_list_rank_enrichment/gate.json'
STATE=ER/'e_reason_current_state.json'
PROTO=ER/'e_reason_protocol_v1.json'
OUT=ER/'evidence/historical_collection_closure'

def sha(path:Path):return hashlib.sha256(path.read_bytes()).hexdigest()
def require_false(payload,label,fields=('outcomes_unsealed','predictive_judgments_generated','forecast_delta_generated','F1_created')):
 inv=payload.get('invariants',payload)
 for field in fields:
  if inv.get(field) is not False:raise RuntimeError(f'{label}: {field} is not false')
def main():
 g16=json.loads(G16.read_text(encoding='utf-8'));g21=json.loads(G21.read_text(encoding='utf-8'));state=json.loads(STATE.read_text(encoding='utf-8'));proto=json.loads(PROTO.read_text(encoding='utf-8'))
 c16=g16.get('counts',{});c21=g21.get('counts',{})
 if g16.get('status')!='E_REASON_2016_STRICT_INTEGRITY_GATE_PASS' or c16.get('data_sufficiency_gate_pass') is not True:raise RuntimeError('2016 strict integrity gate not PASS')
 if c16.get('districts_with_at_least_three_verified_candidate_identities',0)<70 or c16.get('districts_with_at_least_one_enriched_candidate_fact',0)<50:raise RuntimeError('2016 threshold mismatch')
 if g16.get('excluded_layers',{}).get('PPS_DIRECT') is None or g16.get('excluded_layers',{}).get('PPS_LEGACY_FALLBACK') is None:raise RuntimeError('2016 unsafe-layer exclusions missing')
 if g16.get('invariants',{}).get('direct_extension_rows_counted') is not False or g16.get('invariants',{}).get('legacy_fallback_rows_counted') is not False:raise RuntimeError('2016 unsafe layer counted')
 if g16.get('invariants',{}).get('pjd_south_rows_reverified_against_certificate_hash_and_source_text') is not True:raise RuntimeError('2016 final PJD source re-verification missing')
 if g21.get('status')!='E_REASON_2021_COLLECTION_GATE_PASS' or c21.get('gate_pass') is not True:raise RuntimeError('2021 gate not PASS')
 if c21.get('districts_with_at_least_three_verified_candidate_identities',0)<70 or c21.get('districts_with_at_least_one_enriched_candidate_fact',0)<50:raise RuntimeError('2021 threshold mismatch')
 require_false(g16,'2016')
 require_false(g21,'2021',('outcomes_unsealed','predictive_judgments_generated','forecast_delta_generated','F1_created'))
 for f in ('outcomes_unsealed','predictive_judgments_generated','forecast_delta_generated','F1_created'):
  if state.get(f) is not False:raise RuntimeError(f'frozen prereg state leakage flag changed: {f}')
 order=proto.get('execution_order',[])
 if len(order)<4 or 'Build complete 2016 and 2021 evidence packets with missingness explicit.' not in order[2]:raise RuntimeError('protocol execution order drift')
 payload={'schema_version':'1.0','certificate_id':'M26-E-REASON-HISTORICAL-COLLECTION-CLOSURE-V1','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS','experiment_id':proto.get('experiment_id'),'branch':proto.get('branch'),'gates':{'2016':{'path':str(G16.relative_to(ROOT)),'sha256':sha(G16),'status':g16['status'],'identity_districts':c16['districts_with_at_least_three_verified_candidate_identities'],'required_identity_districts':c16['required_identity_districts'],'enriched_districts':c16['districts_with_at_least_one_enriched_candidate_fact'],'required_enriched_districts':c16['required_enriched_districts'],'unsafe_layers_excluded':['PPS_DIRECT','PPS_LEGACY_FALLBACK']},'2021':{'path':str(G21.relative_to(ROOT)),'sha256':sha(G21),'status':g21['status'],'identity_districts':c21['districts_with_at_least_three_verified_candidate_identities'],'required_identity_districts':c21['required_identity_districts'],'enriched_districts':c21['districts_with_at_least_one_enriched_candidate_fact'],'required_enriched_districts':c21['required_enriched_districts']}},'collection_phase':'CLOSED_PASS','next_authorized_protocol_step':'BUILD_COMPLETE_2016_AND_2021_EVIDENCE_PACKETS_WITH_EXPLICIT_MISSINGNESS','invariants':{'preregistration_not_rewritten':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False,'F0_overwritten':False,'Atlas_UI_modified':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'certificate.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(payload,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
