#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';MAP=ER/'evidence/pps_2016_direct_page_identity/direct_map.json';GATE=ER/'evidence/combined_2016_candidate_gate/gate.json';OUT=ER/'evidence/pps_2016_direct_page_identity_summary'
def main():
 m=json.loads(MAP.read_text(encoding='utf-8'));g=json.loads(GATE.read_text(encoding='utf-8'));current={r['constituency_id']:r for r in g['districts']};rows=[]
 for p in m['pages']:
  a=p.get('assignment')
  if not a:continue
  cid=a['constituency_id'];cur=current.get(cid,{'verified_distinct_candidate_identities':0,'pipeline_identity_counts':{}});ev=a['evidence'];src=ev.get('source') or {};rows.append({'region':p['region'],'page':p['page'],'constituency_id':cid,'historical_constituency':a['historical_constituency'],'historical_seats_2016':a['historical_seats_2016'],'current_verified_identities':cur.get('verified_distinct_candidate_identities',0),'current_pipeline_counts':cur.get('pipeline_identity_counts',{}),'would_add_identity_gate_district':cur.get('verified_distinct_candidate_identities',0)<3 and cur.get('verified_distinct_candidate_identities',0)+a['historical_seats_2016']>=3,'variant':ev.get('variant'),'exact':ev.get('exact'),'source_type':src.get('source'),'source_line_index':src.get('line_index'),'source_text':src.get('text'),'source_top_fraction':src.get('top_fraction'),'source_max_font_size':src.get('max_font_size')})
 rows.sort(key=lambda r:(not r['would_add_identity_gate_district'],r['constituency_id'],r['region'],r['page']))
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'map_counts':m['counts'],'gate_counts':g['counts'],'resolved_pages':rows,'potential_gap_closers':[r for r in rows if r['would_add_identity_gate_district']],'duplicates':m.get('duplicate_direct_titles',[]),'invariants':{'evidence_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'map_counts':p['map_counts'],'gate_counts':p['gate_counts'],'potential_gap_closers':p['potential_gap_closers'],'duplicates':p['duplicates']},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
