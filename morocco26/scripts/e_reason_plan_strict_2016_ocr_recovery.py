#!/usr/bin/env python3
"""Build a deterministic recovery plan for the strict 2016 residual.

No evidence is promoted. The planner joins the strict residual to TAFRA seat
magnitude and the already-admissible PPS typographic artifact. It identifies
residual districts that can be closed by exactly one additional identity from
an existing PPS poster: PJD already contributes two, or PPS contributes two
while the historical PPS slate has at least three seats/candidate slots.
"""
from __future__ import annotations
import json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
STRICT=ER/'evidence/strict_2016_integrity_gate/gate.json'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
PPS=ER/'evidence/pps_2016_typographic_identities/parsed_identities.json'
OUT=ER/'evidence/strict_2016_ocr_recovery_plan'
def main():
 strict=json.loads(STRICT.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'));pps=json.loads(PPS.read_text(encoding='utf-8'))
 by={x['source_2026_constituency_id']:x for x in cross['records']}
 pt={x['constituency_id']:x for x in pps.get('territory_rows',[]) if x.get('constituency_id')}
 rows=[]
 for r in strict['residual_below_three']:
  cid=r['constituency_id'];x=by.get(cid);tr=pt.get(cid);seats=int(x['historical_seats_2016']) if x else None;pc=r['pipeline_identity_counts'];pjd_n=int(pc.get('PJD',0));pps_n=int(pc.get('PPS_TYPO',0));reason=[]
  if pjd_n==2: reason.append('TWO_PJD_IDENTITIES_NEED_ONE_INDEPENDENT_PPS_IDENTITY')
  if pps_n==2 and seats is not None and seats>=3: reason.append('PPS_HAS_TWO_BUT_HISTORICAL_SLATE_HAS_AT_LEAST_THREE_SLOTS')
  evidence=(tr or {}).get('evidence_excerpt',{})
  rows.append({'constituency_id':cid,'historical_constituency':x.get('historical_constituency') if x else None,'historical_region':x.get('historical_region') if x else None,'historical_seats_2016':seats,'pjd_identities':pjd_n,'pps_typographic_identities':pps_n,'one_more_pps_identity_can_close':bool(reason),'closure_reasons':reason,'pps_typographic_page':evidence.get('page'),'pps_pdf_sha256':tr.get('pdf_sha256') if tr else None,'pps_parent_page_url':tr.get('parent_page_url') if tr else None,'existing_candidate_keys':r.get('candidate_keys',[])})
 rows.sort(key=lambda x:(not x['one_more_pps_identity_can_close'],-x['pjd_identities'],-x['historical_seats_2016'],x['constituency_id']))
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'strict_gate_status':strict['status'],'strict_gate_counts':strict['counts'],'rows':rows,'counts':{'residual_districts':len(rows),'one_more_existing_pps_identity_can_close':sum(x['one_more_pps_identity_can_close'] for x in rows),'pjd_two_identity_targets':sum(x['pjd_identities']==2 for x in rows),'pps_two_with_ge3_seats_targets':sum(x['pps_typographic_identities']==2 and x['historical_seats_2016']>=3 for x in rows)},'invariants':{'candidate_identities_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'plan.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'top_targets':[x for x in rows if x['one_more_pps_identity_can_close']][:20]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
