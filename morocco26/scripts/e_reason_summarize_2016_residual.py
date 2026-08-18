#!/usr/bin/env python3
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SRC=ROOT/'morocco26/data/goal100/e_reason/evidence/combined_2016_candidate_gate/gate.json'
OUT=ROOT/'morocco26/data/goal100/e_reason/evidence/combined_2016_candidate_gate/residual.json'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'))
 rows=[]
 for x in d.get('districts',[]):
  if x.get('verified_distinct_candidate_identities',0)>=3:continue
  rows.append({'constituency_id':x['constituency_id'],'verified_distinct_candidate_identities':x.get('verified_distinct_candidate_identities',0),'pipeline_identity_counts':x.get('pipeline_identity_counts',{}),'parties':x.get('parties',[]),'pipelines':x.get('pipelines',[]),'candidate_keys':x.get('candidate_keys',[])})
 rows.sort(key=lambda x:(-x['verified_distinct_candidate_identities'],x['constituency_id']))
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'gate_status':d.get('status'),'gate_counts':d.get('counts',{}),'residual_with_any_candidate_below_three':rows,'residual_count':len(rows),'nearest_to_pass':[x for x in rows if x['verified_distinct_candidate_identities']==max([r['verified_distinct_candidate_identities'] for r in rows],default=-1)][:10],'invariants':{'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps(p,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
