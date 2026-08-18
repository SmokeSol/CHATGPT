#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
SRC=ER/'evidence/pps_2016_failed_card_geometry/calibration.json'
OUT=ER/'evidence/pps_2016_failed_geometry_group_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));rows=[]
 for doc in d['documents']:
  groups=[]
  for line in doc.get('geometry_lines',[]):
   for g in line.get('groups',[]):
    max_size=max(g.get('font_sizes') or [0])
    if max_size>=10:
     groups.append({'top':line['top'],'top_fraction':line['top_fraction'],'x0':g['x0'],'x1':g['x1'],'max_font_size':max_size,'logical_text':g['logical_text'],'raw_words_rtl':g['raw_words_rtl']})
  rows.append({'region':doc.get('region'),'page':doc.get('page'),'constituency_id':doc.get('constituency_id'),'historical_constituency':doc.get('historical_constituency'),'seats':doc.get('historical_seats_2016'),'groups':groups})
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'pages':rows,'invariants':{'evidence_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps([{'district':x['historical_constituency'],'groups':len(x['groups'])} for x in rows],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
