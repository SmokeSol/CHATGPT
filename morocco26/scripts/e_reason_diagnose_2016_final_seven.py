#!/usr/bin/env python3
"""Diagnose the remaining 2016 identity-gate gap after exact-header PPS parsing.

Planning-only. It joins the current combined gate to the 92-page PPS bijection
and historical seat magnitudes. No new candidate or territory evidence is
promoted and no target outcome is opened.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';GATE=ER/'evidence/combined_2016_candidate_gate/gate.json';BIJ=ER/'evidence/pps_2016_region_bijection/bijection.json';CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';OUT=ER/'evidence/2016_final_seven_diagnostic'
def main():
 gate=json.loads(GATE.read_text(encoding='utf-8'));bij=json.loads(BIJ.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'));meta={r['source_2026_constituency_id']:r for r in cross['records']};page_by_cid={p['assigned_constituency_id']:{'region':r['region_slug'],**p} for r in bij['regions'] for p in r.get('pages',[])};district={r['constituency_id']:r for r in gate['districts']};rows=[]
 for cid,m in sorted(meta.items()):
  g=district.get(cid,{'verified_distinct_candidate_identities':0,'pipeline_identity_counts':{}});current=int(g.get('verified_distinct_candidate_identities') or 0);seats=int(m['historical_seats_2016']);page=page_by_cid.get(cid);potential=current+(seats if not (g.get('pipeline_identity_counts') or {}).get('PPS_TYPO') else 0);rows.append({'constituency_id':cid,'historical_constituency':m['historical_constituency'],'historical_seats_2016':seats,'current_verified_identities':current,'current_pipeline_counts':g.get('pipeline_identity_counts',{}),'current_pass':current>=3,'pps_page':page,'potential_after_one_full_pps_page':potential,'can_reach_three_via_current_pps_page':current<3 and potential>=3})
 candidates=[r for r in rows if r['can_reach_three_via_current_pps_page']];candidates.sort(key=lambda r:(r['pps_page'].get('assignment_method')!='FILING_BIJECTION_ONLY_REQUIRES_AUDIT' if r.get('pps_page') else True,-r['current_verified_identities'],-r['historical_seats_2016'],r['historical_constituency']))
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'current_gate_counts':gate['counts'],'remaining_needed':max(0,70-int(gate['counts']['districts_with_at_least_three_verified_candidate_identities'])),'recoverable_with_unparsed_pps_page_count':len(candidates),'priority_candidates':candidates,'all_districts':rows,'invariants':{'planning_only':True,'evidence_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'current_gate_counts':payload['current_gate_counts'],'remaining_needed':payload['remaining_needed'],'recoverable_with_unparsed_pps_page_count':len(candidates),'priority_candidates':candidates[:20]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
