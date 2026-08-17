#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';SRC=ER/'evidence/pjd_2016_parsed_slates/parsed_slates.json';OUT=ER/'evidence/pjd_2016_valid_subset_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));by=defaultdict(list)
 for c in d.get('candidate_rows',[]):
  if c.get('constituency_id') and c.get('candidate_name_ar_normalized'):by[c['constituency_id']].append(c)
 rows=[]
 for cid,xs in sorted(by.items()):
  names={x['candidate_name_ar_normalized'] for x in xs};rows.append({'constituency_id':cid,'candidate_count':len(names),'at_least_three':len(names)>=3,'enriched':any(x.get('FORMAL_ENDORSEMENT') is True for x in xs),'historical_constituency':xs[0].get('historical_constituency')})
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_status':d.get('status'),'source_schema_version':d.get('schema_version'),'candidate_rows':sum(len(v) for v in by.values()),'districts_with_candidates':len(rows),'districts_with_at_least_three_verified_candidate_identities':sum(x['at_least_three'] for x in rows),'districts_with_enriched_fact':sum(x['enriched'] for x in rows),'failure_rows_excluded':len(d.get('failures',[])),'districts':rows,'invariants':{'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:p[k] for k in ('source_status','source_schema_version','candidate_rows','districts_with_candidates','districts_with_at_least_three_verified_candidate_identities','districts_with_enriched_fact','failure_rows_excluded')},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
