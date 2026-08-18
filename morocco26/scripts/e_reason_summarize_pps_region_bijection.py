#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';SRC=ER/'evidence/pps_2016_region_bijection/bijection.json';OUT=ER/'evidence/pps_2016_region_bijection_summary'
def main():
 d=json.loads(SRC.read_text(encoding='utf-8'));regions=[];ids=[];methods=Counter()
 for r in d.get('regions',[]):
  pages=r.get('pages',[]);ids.extend(p.get('assigned_constituency_id') for p in pages if p.get('assigned_constituency_id'))
  methods.update(p.get('assignment_method') for p in pages)
  regions.append({'region_slug':r.get('region_slug'),'status':r.get('status'),'page_count':r.get('page_count'),'canonical_district_count':r.get('canonical_district_count'),'assigned_pages':len(pages),'exact_or_high_confidence_pages':r.get('exact_or_high_confidence_pages',0),'bijection_only_pages':r.get('bijection_only_pages',0),'assigned_ids':[p.get('assigned_constituency_id') for p in pages]})
 duplicates=[{'constituency_id':cid,'count':count} for cid,count in Counter(ids).items() if count>1]
 p={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_status':d.get('status'),'source_counts':d.get('counts'),'regions':regions,'assignment_method_counts':dict(methods),'assigned_ids_total':len(ids),'unique_assigned_ids':len(set(ids)),'duplicate_assignments':duplicates,'invariants':{'evidence_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'summary.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'source_status':p['source_status'],'regions':regions,'assignment_method_counts':p['assignment_method_counts'],'assigned_ids_total':p['assigned_ids_total'],'unique_assigned_ids':p['unique_assigned_ids'],'duplicate_assignments':duplicates},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
