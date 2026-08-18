#!/usr/bin/env python3
"""Combine independently admissible PJD and PPS 2016 candidate evidence.

For a PPS territory covered by the exact/high-header typographic parser, that
parser is authoritative and the older card parser is not unioned, preventing a
single PPS candidate from being counted twice under two text decodings. The old
parser contributes only territories absent from the typographic subset. PJD and
PPS remain distinct parties. No outcomes or predictive judgments are opened.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
PJD=ER/'evidence/pjd_2016_parsed_slates/parsed_slates.json'
PPS_LEGACY=ER/'evidence/pps_2016_parsed_missing_slates/parsed_missing_slates.json'
PPS_TYPO=ER/'evidence/pps_2016_typographic_identities/parsed_identities.json'
OUT=ER/'evidence/combined_2016_candidate_gate'

def main():
 pjd=json.loads(PJD.read_text(encoding='utf-8'));legacy=json.loads(PPS_LEGACY.read_text(encoding='utf-8'));typo=json.loads(PPS_TYPO.read_text(encoding='utf-8'))
 allowed={'PASS','PARTIAL_VALID','FAIL_CLOSED_DIAGNOSTIC_PERSISTED','PASS_2016_COLLECTION_GATE'}
 for label,payload in [('PJD',pjd),('PPS_LEGACY',legacy),('PPS_TYPO',typo)]:
  if payload.get('status') not in allowed:raise RuntimeError(f'unexpected {label} status: {payload.get("status")}')
 typo_territories={r.get('constituency_id') for r in typo.get('territory_rows',[]) if r.get('constituency_id')}
 sources=[('PJD',pjd,lambda c:True),('PPS_TYPO',typo,lambda c:True),('PPS_LEGACY_FALLBACK',legacy,lambda c:c.get('constituency_id') not in typo_territories)]
 all_rows=[];source_valid_rows={}
 for source,payload,include in sources:
  before=len(all_rows)
  for c in payload.get('candidate_rows',[]):
   if not include(c):continue
   identity=c.get('candidate_name_ar_normalized') or c.get('candidate_identity_key') or ''
   cid=c.get('constituency_id')
   if not cid or not identity:continue
   all_rows.append({**c,'candidate_identity_for_gate':identity,'evidence_pipeline':source})
  source_valid_rows[source]=len(all_rows)-before
 by=defaultdict(dict)
 for c in all_rows:
  key=(c.get('party'),c['candidate_identity_for_gate'])
  by[c['constituency_id']][key]=c
 districts=[]
 pipeline_names=[x[0] for x in sources]
 for cid,items in sorted(by.items()):
  xs=list(items.values());n=len(xs);enriched=any(x.get('FORMAL_ENDORSEMENT') is True for x in xs);counts={source:sum(x['evidence_pipeline']==source for x in xs) for source in pipeline_names}
  districts.append({'constituency_id':cid,'verified_distinct_candidate_identities':n,'identity_coverage_pass':n>=3,'enriched_candidate_fact_present':enriched,'parties':sorted({str(x.get('party')) for x in xs}),'pipelines':sorted({x['evidence_pipeline'] for x in xs}),'pipeline_identity_counts':counts,'candidate_keys':[{'party':x.get('party'),'identity':x['candidate_identity_for_gate'],'pipeline':x['evidence_pipeline']} for x in xs]})
 identity=sum(x['identity_coverage_pass'] for x in districts);enriched=sum(x['enriched_candidate_fact_present'] for x in districts);gate=identity>=70 and enriched>=50
 payload={'schema_version':'2.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'year':2016,'source_artifacts':{'PJD':str(PJD.relative_to(ROOT)),'PPS_TYPO':str(PPS_TYPO.relative_to(ROOT)),'PPS_LEGACY_FALLBACK':str(PPS_LEGACY.relative_to(ROOT))},'source_statuses':{'PJD':pjd.get('status'),'PPS_TYPO':typo.get('status'),'PPS_LEGACY_FALLBACK':legacy.get('status')},'source_schema_versions':{'PJD':pjd.get('schema_version'),'PPS_TYPO':typo.get('schema_version'),'PPS_LEGACY_FALLBACK':legacy.get('schema_version')},'authoritative_pps_typographic_territories':len(typo_territories),'counts':{'source_valid_candidate_rows':source_valid_rows,'candidate_rows_before_dedupe':len(all_rows),'districts_with_any_candidate':len(districts),'districts_with_at_least_three_verified_candidate_identities':identity,'required_identity_districts':70,'districts_with_at_least_one_enriched_candidate_fact':enriched,'required_enriched_districts':50,'identity_gate_pass':identity>=70,'enriched_gate_pass':enriched>=50,'data_sufficiency_gate_pass':gate},'districts':districts,'status':'E_REASON_2016_COLLECTION_GATE_PASS' if gate else 'E_REASON_2016_COLLECTION_PARTIAL','invariants':{'same_pps_territory_not_unioned_across_parsers':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'gate.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'counts':payload['counts'],'authoritative_pps_typographic_territories':payload['authoritative_pps_typographic_territories'],'districts_below_three':[{'id':x['constituency_id'],'n':x['verified_distinct_candidate_identities'],'pipeline_counts':x['pipeline_identity_counts']} for x in districts if x['verified_distinct_candidate_identities']<3]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
