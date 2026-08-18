#!/usr/bin/env python3
"""Recompute the 2016 collection gate from conservative evidence layers only.

This audit deliberately excludes PPS_DIRECT and PPS_LEGACY_FALLBACK after a
manual integrity check found non-person phrases among rows counted as candidate
identities in the direct-extension layer. It uses only:
  * fail-closed PJD parsed slate rows,
  * the original exact-header PPS typographic parser,
  * the narrowly validated Moulay-Yacoub targeted OCR artifact.
No outcome data are opened. This artifact is an integrity audit and becomes the
scientific gate of record only if/when its thresholds pass.
"""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
PJD=ER/'evidence/pjd_2016_parsed_slates/parsed_slates.json'
PPS=ER/'evidence/pps_2016_typographic_identities/parsed_identities.json'
OCR=ER/'evidence/pps_2016_ocr_moulay_yacoub/evidence.json'
OUT=ER/'evidence/strict_2016_integrity_gate'

def identity(c):
    return c.get('candidate_name_ar_normalized') or c.get('candidate_identity_key') or ''

def main():
    pjd=json.loads(PJD.read_text(encoding='utf-8'))
    pps=json.loads(PPS.read_text(encoding='utf-8'))
    ocr=json.loads(OCR.read_text(encoding='utf-8'))
    if ocr.get('status')!='PASS': raise RuntimeError('targeted OCR artifact not PASS')
    if ocr.get('invariants',{}).get('person_name_fuzzy_matching') is not False: raise RuntimeError('OCR fuzzy-name invariant drift')
    rows=[]
    for label,payload in [('PJD',pjd),('PPS_TYPO',pps),('PPS_OCR_FINAL',ocr)]:
        for c in payload.get('candidate_rows',[]):
            cid=c.get('constituency_id'); ident=identity(c)
            if cid and ident:
                rows.append({**c,'gate_identity':ident,'evidence_pipeline':label})
    by=defaultdict(dict)
    for c in rows:
        by[c['constituency_id']][(str(c.get('party')),c['gate_identity'])]=c
    districts=[]
    for cid,items in sorted(by.items()):
        xs=list(items.values())
        n=len(xs)
        districts.append({
            'constituency_id':cid,
            'verified_distinct_candidate_identities':n,
            'identity_coverage_pass':n>=3,
            'enriched_candidate_fact_present':any(x.get('FORMAL_ENDORSEMENT') is True for x in xs),
            'pipeline_identity_counts':{p:sum(x['evidence_pipeline']==p for x in xs) for p in ('PJD','PPS_TYPO','PPS_OCR_FINAL')},
            'candidate_keys':[{'party':x.get('party'),'identity':x['gate_identity'],'pipeline':x['evidence_pipeline']} for x in xs],
        })
    identity_n=sum(x['identity_coverage_pass'] for x in districts)
    enriched_n=sum(x['enriched_candidate_fact_present'] for x in districts)
    gate=identity_n>=70 and enriched_n>=50
    residual=sorted([
        {'constituency_id':x['constituency_id'],'verified_distinct_candidate_identities':x['verified_distinct_candidate_identities'],'pipeline_identity_counts':x['pipeline_identity_counts'],'candidate_keys':x['candidate_keys']}
        for x in districts if x['verified_distinct_candidate_identities']<3
    ],key=lambda x:(-x['verified_distinct_candidate_identities'],x['constituency_id']))
    payload={
        'schema_version':'1.0',
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'year':2016,
        'status':'E_REASON_2016_STRICT_INTEGRITY_GATE_PASS' if gate else 'E_REASON_2016_STRICT_INTEGRITY_PARTIAL',
        'excluded_layers':{
            'PPS_DIRECT':'EXCLUDED_WHOLE_LAYER_AFTER_NON_PERSON_PHRASES_WERE_OBSERVED_AMONG_COUNTED_IDENTITIES',
            'PPS_LEGACY_FALLBACK':'EXCLUDED_FROM_STRICT_AUDIT_TO_AVOID_LAYOUT_HEURISTIC_DEPENDENCE',
        },
        'source_artifacts':{'PJD':str(PJD.relative_to(ROOT)),'PPS_TYPO':str(PPS.relative_to(ROOT)),'PPS_OCR_FINAL':str(OCR.relative_to(ROOT))},
        'counts':{
            'candidate_rows_before_dedupe':len(rows),
            'districts_with_any_candidate':len(districts),
            'districts_with_at_least_three_verified_candidate_identities':identity_n,
            'required_identity_districts':70,
            'districts_with_at_least_one_enriched_candidate_fact':enriched_n,
            'required_enriched_districts':50,
            'identity_gate_pass':identity_n>=70,
            'enriched_gate_pass':enriched_n>=50,
            'data_sufficiency_gate_pass':gate,
        },
        'residual_below_three':residual,
        'districts':districts,
        'invariants':{
            'direct_extension_rows_counted':False,
            'legacy_fallback_rows_counted':False,
            'outcomes_unsealed':False,
            'predictive_judgments_generated':False,
            'forecast_delta_generated':False,
            'F1_created':False,
        },
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'gate.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'counts':payload['counts'],'nearest_residual':residual[:25]},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
