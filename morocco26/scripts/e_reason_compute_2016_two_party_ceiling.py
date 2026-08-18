#!/usr/bin/env python3
"""Compute the preregistered identity gate ceiling using PJD plus a full PPS slate.

This is planning-only. It assumes every PPS constituency page can eventually be
parsed to exactly historical seat magnitude identities, but creates no candidate
facts. It identifies whether an additional admissible party source is required.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';PJD=ER/'evidence/pjd_2016_valid_subset_summary/summary.json';CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';OUT=ER/'evidence/2016_two_party_ceiling'
def main():
 pjd=json.loads(PJD.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'));pjd_count={r['constituency_id']:int(r['candidate_count']) for r in pjd['districts']};rows=[]
 for r in cross['records']:
  cid=r['source_2026_constituency_id'];seats=int(r['historical_seats_2016']);n=pjd_count.get(cid,0);total=n+seats;rows.append({'constituency_id':cid,'historical_constituency':r['historical_constituency'],'historical_seats_2016':seats,'pjd_verified_identities':n,'full_pps_assumed_identities':seats,'two_party_identity_count_upper_bound':total,'two_party_passes_three':total>=3,'needs_third_party_identity':total<3})
 passes=sum(x['two_party_passes_three'] for x in rows);need=[x for x in rows if x['needs_third_party_identity']];payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'counts':{'territories':len(rows),'two_party_ge3_ceiling':passes,'required_ge3_districts':70,'remaining_after_perfect_pps':max(0,70-passes),'districts_needing_one_third_party_identity':len(need)},'districts_needing_third_party_identity':need,'all_districts':rows,'invariants':{'hypothetical_only':True,'candidate_facts_generated':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'ceiling.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'districts_needing_third_party_identity':need},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
