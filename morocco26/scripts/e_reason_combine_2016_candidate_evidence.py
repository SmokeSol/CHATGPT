#!/usr/bin/env python3
"""Combine independently admissible PJD and PPS 2016 candidate evidence.

This is a collection-gate evaluator only. It does not generate predictive
judgments and never opens target-election outcomes. Candidate identities are
deduplicated within territory by party + normalized Arabic identity. A district
passes identity coverage when >=3 distinct verified candidate identities exist.
Enrichment is counted when at least one candidate has a preregistered enriched
fact (currently FORMAL_ENDORSEMENT) backed by admissible T1 evidence.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
PJD=ER/'evidence/pjd_2016_parsed_slates/parsed_slates.json';PPS=ER/'evidence/pps_2016_parsed_missing_slates/parsed_missing_slates.json';OUT=ER/'evidence/combined_2016_candidate_gate'

def main():
 pjd=json.loads(PJD.read_text(encoding='utf-8'));pps=json.loads(PPS.read_text(encoding='utf-8'))
 allowed_status={'PASS','PARTIAL_VALID','FAIL_CLOSED_DIAGNOSTIC_PERSISTED','PASS_2016_COLLECTION_GATE'}
 if pjd.get('status') not in allowed_status:raise RuntimeError('unexpected PJD parser status')
 if pps.get('status') not in allowed_status:raise RuntimeError('PPS parser is not a usable valid subset')
 all_rows=[];source_valid_rows={}
 for source,payload in [('PJD',pjd),('PPS',pps)]:
  before=len(all_rows)
  for c in payload.get('candidate_rows',[]):
   name=c.get('candidate_name_ar_normalized') or c.get('candidate_identity_key') or ''
   cid=c.get('constituency_id')
   if not cid or not name:continue
   all_rows.append({**c,'candidate_identity_for_gate':name,'evidence_pipeline':source})
  source_valid_rows[source]=len(all_rows)-before
 by=defaultdict(dict)
 for c in all_rows:
  key=(c.get('party'),c['candidate_identity_for_gate'])
  by[c['constituency_id']][key]=c
 district_rows=[]
 for cid,items in sorted(by.items()):
  xs=list(items.values());identity_count=len(xs);enriched=[x for x in xs if x.get('FORMAL_ENDORSEMENT') is True]
  pipeline_counts={source:sum(x['evidence_pipeline']==source for x in xs) for source in ('PJD','PPS')}
  district_rows.append({'constituency_id':cid,'verified_distinct_candidate_identities':identity_count,'identity_coverage_pass':identity_count>=3,'enriched_candidate_fact_present':bool(enriched),'parties':sorted({str(x.get('party')) for x in xs}),'pipelines':sorted({x['evidence_pipeline'] for x in xs}),'pipeline_identity_counts':pipeline_counts,'candidate_keys':[{'party':x.get('party'),'identity':x['candidate_identity_for_gate'],'pipeline':x['evidence_pipeline']} for x in xs]})
 identity=sum(x['identity_coverage_pass'] for x in district_rows);enriched=sum(x['enriched_candidate_fact_present'] for x in district_rows);gate=identity>=70 and enriched>=50
 payload={'schema_version':'1.1','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'year':2016,'source_artifacts':{'PJD':str(PJD.relative_to(ROOT)),'PPS':str(PPS.relative_to(ROOT))},'source_statuses':{'PJD':pjd.get('status'),'PPS':pps.get('status')},'source_schema_versions':{'PJD':pjd.get('schema_version'),'PPS':pps.get('schema_version')},'counts':{'source_valid_candidate_rows':source_valid_rows,'candidate_rows_before_dedupe':len(all_rows),'districts_with_any_candidate':len(district_rows),'districts_with_at_least_three_verified_candidate_identities':identity,'required_identity_districts':70,'districts_with_at_least_one_enriched_candidate_fact':enriched,'required_enriched_districts':50,'identity_gate_pass':identity>=70,'enriched_gate_pass':enriched>=50,'data_sufficiency_gate_pass':gate},'districts':district_rows,'status':'E_REASON_2016_COLLECTION_GATE_PASS' if gate else 'E_REASON_2016_COLLECTION_PARTIAL','invariants':{'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'gate.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'source_statuses':payload['source_statuses'],'source_schema_versions':payload['source_schema_versions'],'counts':payload['counts'],'districts_below_three':[{'id':x['constituency_id'],'n':x['verified_distinct_candidate_identities'],'pipeline_counts':x['pipeline_identity_counts']} for x in district_rows if x['verified_distinct_candidate_identities']<3]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
