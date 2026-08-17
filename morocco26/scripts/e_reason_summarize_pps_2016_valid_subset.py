#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';SRC=ER/'evidence/pps_2016_parsed_missing_slates/parsed_missing_slates.json';OUT=ER/'evidence/pps_2016_valid_subset_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));by=defaultdict(list)
 for c in d.get('candidate_rows',[]):
  if c.get('constituency_id') and c.get('candidate_name_ar_normalized'):by[c['constituency_id']].append(c)
 districts=[]
 for cid,xs in sorted(by.items()):
  n=len({x['candidate_name_ar_normalized'] for x in xs});districts.append({'constituency_id':cid,'candidate_count':n,'at_least_three':n>=3,'enriched':any(x.get('FORMAL_ENDORSEMENT') is True for x in xs),'historical_constituency':xs[0].get('historical_constituency')})
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_status':d.get('status'),'source_schema_version':d.get('schema_version'),'candidate_rows':sum(len(x) for x in by.values()),'districts_with_candidates':len(districts),'districts_with_at_least_three_verified_candidate_identities':sum(x['at_least_three'] for x in districts),'districts_with_enriched_fact':sum(x['enriched'] for x in districts),'failure_pages_excluded':len(d.get('failures',[])),'unresolved_header_pages':sum(x.get('status') in {'SKIP_HEADER_TERRITORY_NOT_UNIQUE','SKIP_TERRITORY_NOT_UNIQUE'} for x in d.get('page_diagnostics',[])),'districts':districts,'invariants':{'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:p[k] for k in ('source_status','source_schema_version','candidate_rows','districts_with_candidates','districts_with_at_least_three_verified_candidate_identities','districts_with_enriched_fact','failure_pages_excluded','unresolved_header_pages')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
