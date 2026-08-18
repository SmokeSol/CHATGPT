#!/usr/bin/env python3
"""Recompute the 2016 collection gate from conservative evidence layers only.

The direct typographic extension and legacy layout fallback remain excluded in
full after integrity concerns. Counted evidence is limited to:
  * fail-closed PJD parsed slate rows,
  * the original exact-header PPS typographic parser,
  * narrowly validated Moulay-Yacoub targeted OCR evidence,
  * Ifrane/Sidi-Ifni identities cross-modally verified by an exact OCR header
    plus an exact standalone embedded-text name line on the same PDF page.
No outcome data are opened.
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
CROSSMODAL=ER/'evidence/strict_2016_ifrane_sidi_crossmodal_candidates/evidence.json'
CROSSDIAG=ER/'evidence/strict_2016_ifrane_sidi_embedded_name_diagnostic/diagnostic.json'
OUT=ER/'evidence/strict_2016_integrity_gate'

def identity(c):
    return c.get('candidate_name_ar_normalized') or c.get('candidate_identity_key') or ''

def main():
    pjd=json.loads(PJD.read_text(encoding='utf-8'))
    pps=json.loads(PPS.read_text(encoding='utf-8'))
    ocr=json.loads(OCR.read_text(encoding='utf-8'))
    cross=json.loads(CROSSMODAL.read_text(encoding='utf-8'))
    cdiag=json.loads(CROSSDIAG.read_text(encoding='utf-8'))
    if ocr.get('status')!='PASS': raise RuntimeError('targeted Moulay-Yacoub OCR artifact not PASS')
    if ocr.get('invariants',{}).get('person_name_fuzzy_matching') is not False: raise RuntimeError('Moulay-Yacoub fuzzy-name invariant drift')
    if cross.get('status')!='PASS': raise RuntimeError('cross-modal Ifrane/Sidi evidence not PASS')
    cinv=cross.get('invariants',{})
    if cinv.get('exact_header_ocr_required') is not True or cinv.get('exact_same_page_standalone_name_line_required') is not True or cinv.get('person_name_fuzzy_matching') is not False or cinv.get('biography_lines_promoted') is not False:
        raise RuntimeError('cross-modal safety invariants missing')
    # Re-verify every promoted cross-modal identity against the frozen diagnostic
    # rather than trusting the derived evidence file alone.
    drows={r['constituency_id']:r for r in cdiag.get('rows',[])}
    if set(drows)!={'ifrane','sidi-ifni'}: raise RuntimeError('cross-modal diagnostic target drift')
    for c in cross.get('candidate_rows',[]):
        cid=c.get('constituency_id'); ident=identity(c); dr=drows.get(cid)
        if dr is None or dr.get('header_exact_match') is not True: raise RuntimeError(f'exact-header diagnostic missing for {cid}')
        if ident not in set(dr.get('embedded_text_lines_normalized',[])): raise RuntimeError(f'{cid} identity absent as exact embedded line: {ident}')
        if int(c.get('evidence',{}).get('pdf_page',-1))!=int(dr.get('page',-2)): raise RuntimeError(f'{cid} page mismatch')
        if c.get('evidence',{}).get('content_sha256')!=dr.get('pdf_sha256'): raise RuntimeError(f'{cid} PDF hash mismatch')
    rows=[]
    sources=[('PJD',pjd),('PPS_TYPO',pps),('PPS_OCR_MOULAY',ocr),('PPS_CROSSMODAL',cross)]
    for label,payload in sources:
        for c in payload.get('candidate_rows',[]):
            cid=c.get('constituency_id'); ident=identity(c)
            if cid and ident:
                rows.append({**c,'gate_identity':ident,'evidence_pipeline':label})
    by=defaultdict(dict)
    for c in rows:
        by[c['constituency_id']][(str(c.get('party')),c['gate_identity'])]=c
    pipelines=tuple(x[0] for x in sources)
    districts=[]
    for cid,items in sorted(by.items()):
        xs=list(items.values());n=len(xs)
        districts.append({
            'constituency_id':cid,
            'verified_distinct_candidate_identities':n,
            'identity_coverage_pass':n>=3,
            'enriched_candidate_fact_present':any(x.get('FORMAL_ENDORSEMENT') is True for x in xs),
            'pipeline_identity_counts':{p:sum(x['evidence_pipeline']==p for x in xs) for p in pipelines},
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
        'schema_version':'2.0',
        'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'year':2016,
        'status':'E_REASON_2016_STRICT_INTEGRITY_GATE_PASS' if gate else 'E_REASON_2016_STRICT_INTEGRITY_PARTIAL',
        'excluded_layers':{
            'PPS_DIRECT':'EXCLUDED_WHOLE_LAYER_AFTER_NON_PERSON_PHRASES_WERE_OBSERVED_AMONG_COUNTED_IDENTITIES',
            'PPS_LEGACY_FALLBACK':'EXCLUDED_FROM_STRICT_AUDIT_TO_AVOID_LAYOUT_HEURISTIC_DEPENDENCE',
        },
        'source_artifacts':{'PJD':str(PJD.relative_to(ROOT)),'PPS_TYPO':str(PPS.relative_to(ROOT)),'PPS_OCR_MOULAY':str(OCR.relative_to(ROOT)),'PPS_CROSSMODAL':str(CROSSMODAL.relative_to(ROOT)),'PPS_CROSSMODAL_DIAGNOSTIC':str(CROSSDIAG.relative_to(ROOT))},
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
            'crossmodal_rows_reverified_against_frozen_diagnostic':True,
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
