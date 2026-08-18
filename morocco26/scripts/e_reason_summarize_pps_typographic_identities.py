#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';SRC=ER/'evidence/pps_2016_typographic_identities/parsed_identities.json';OUT=ER/'evidence/pps_2016_typographic_identity_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));by=defaultdict(list)
 for c in d.get('candidate_rows',[]):
  if c.get('constituency_id'):by[c['constituency_id']].append(c)
 districts=[]
 for cid,xs in sorted(by.items()):
  ids={x.get('candidate_name_ar_normalized') or x.get('candidate_identity_key') for x in xs};districts.append({'constituency_id':cid,'historical_constituency':xs[0].get('historical_constituency'),'identity_count':len(ids),'at_least_three':len(ids)>=3,'human_readable':sum(bool(x.get('candidate_name_ar_normalized')) for x in xs),'raw_glyph':sum(not bool(x.get('candidate_name_ar_normalized')) for x in xs)})
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_schema_version':d.get('schema_version'),'source_status':d.get('status'),'source_counts':d.get('counts'),'districts_with_candidates':len(districts),'districts_with_at_least_three':sum(x['at_least_three'] for x in districts),'districts':districts,'failure_pages':[{'district':x.get('historical_constituency'),'constituency_id':x.get('constituency_id'),'seats':x.get('seats'),'eligible':x.get('eligible_group_count'),'errors':x.get('errors')} for x in d.get('failures',[])],'invariants':{'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'source_counts':p['source_counts'],'districts_with_candidates':p['districts_with_candidates'],'districts_with_at_least_three':p['districts_with_at_least_three'],'failure_pages':p['failure_pages']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
