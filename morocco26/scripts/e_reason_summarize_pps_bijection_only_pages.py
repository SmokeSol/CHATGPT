#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';SRC=ER/'evidence/pps_2016_region_bijection/bijection.json';OUT=ER/'evidence/pps_2016_bijection_only_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));rows=[]
 for region in d['regions']:
  for p in region.get('pages',[]):
   if p.get('assignment_method') in {'EXACT_HEADER','HIGH_CONFIDENCE_HEADER'}:continue
   rows.append({'region':region['region_slug'],'page':p['page'],'constituency_id':p['assigned_constituency_id'],'historical_constituency':p['historical_constituency'],'historical_seats_2016':p['historical_seats_2016'],'assignment_score':p['assignment_score'],'page_local_second_score':p['page_local_second_score'],'page_local_margin':p['page_local_margin'],'matched_pair':p.get('matched_pair'),'header_lines':p.get('header_lines')})
 rows.sort(key=lambda x:(-x['assignment_score'],-x['page_local_margin'],x['region'],x['page']))
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'count':len(rows),'pages':rows,'invariants':{'evidence_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'count':len(rows),'pages':rows},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
