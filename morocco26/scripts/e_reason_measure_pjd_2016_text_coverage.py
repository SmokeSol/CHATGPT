#!/usr/bin/env python3
"""Measure territory coverage of recovered 2016 PJD slate documents.

Identity-only diagnostic: territory labels come from the accepted Arabic bridge;
historical seat magnitudes come from TAFRA-2016 through that bridge. This does
not yet count candidate identities; it measures the maximum district capacity
of the recovered slate documents before table parsing.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
AUDIT=ER/'evidence/pjd_2016_provenance_audit/audit.json'
OUT=ER/'evidence/pjd_2016_text_coverage'


def norm_ar(s:str|None)->str:
    x=html.unescape(s or '')
    x=unicodedata.normalize('NFC',x).replace('ـ','')
    x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x)
    x=re.sub(r'[أإآٱ]','ا',x)
    x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x)
    return ' '.join(x.split())

# Historical/typographic Arabic aliases observed in the 2016 PDFs.
ALIASES={
    'assa-zag':['اسا الزاك','اسا الزالك'],
    'nador':['الناظور','الناضور'],
    'driouch':['الدريوش','الدرويش'],
    'sidi-ifni':['سيدي افني','سيدي إفني'],
    'fquih-ben-salah':['الفقيه بن صالح','الفقيه بنصالح'],
    'ain-chock':['عين الشق','عين الشق'],
    'ben-m-sick':['ابن مسيك','ابن امسيك'],
    'tanger-assilah':['طنجة اصيلة','طنجة اصيلا'],
    'azilal-demnate':['ازيلال دمنات','ازيلال دمنات'],
    'bzou-ouaouizeght':['بزو واويزغت','بزو واوزغت'],
}


def main():
    audit=json.loads(AUDIT.read_text(encoding='utf-8'))
    if not audit.get('all_mechanical_checks_pass'): raise RuntimeError('provenance audit not PASS')
    cross=json.loads(CROSS.read_text(encoding='utf-8'))
    if cross.get('status')!='PASS': raise RuntimeError('Arabic historical bridge not PASS')
    latest=json.loads(LATEST.read_text(encoding='utf-8'))
    manifest=json.loads((ROOT/latest['latest_manifest']).read_text(encoding='utf-8'))
    docs=[d for d in manifest['documents'] if d.get('text_path')]
    texts={d['article_id']:norm_ar((ROOT/d['text_path']).read_text(encoding='utf-8',errors='replace')) for d in docs}
    records=[]
    for r in cross['records']:
        cid=r['source_2026_constituency_id']
        variants={norm_ar(r.get('name_ar')),norm_ar(r.get('name_ar_source_form'))}
        variants.update(norm_ar(x) for x in ALIASES.get(cid,[]))
        variants={x for x in variants if x}
        hits=[]
        for aid,text in texts.items():
            matched=sorted([v for v in variants if v in text],key=len,reverse=True)
            if matched: hits.append({'article_id':aid,'matched_variant':matched[0]})
        records.append({
            'constituency_id':cid,
            'name_ar':r['name_ar'],
            'historical_id_constituency':r['historical_id_constituency'],
            'historical_constituency':r['historical_constituency'],
            'historical_seats_2016':int(r['historical_seats_2016']),
            'document_hits':hits,
            'covered':bool(hits),
        })
    covered=[r for r in records if r['covered']]
    ge3=[r for r in covered if r['historical_seats_2016']>=3]
    missing=[r for r in records if not r['covered']]
    payload={
        'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'documents':list(texts),'counts':{
            'canonical_territories':92,
            'territories_detected_in_recovered_documents':len(covered),
            'detected_territories_with_historical_seats_at_least_3':len(ge3),
            'identity_gate_threshold':70,
            'maximum_possible_identity_gate_from_current_documents_if_all_candidate_rows_parse':len(ge3)>=70,
            'additional_ge3_territories_needed_to_reach_70':max(0,70-len(ge3)),
            'missing_territories':len(missing),
        },
        'missing':[{'constituency_id':r['constituency_id'],'name_ar':r['name_ar'],'historical_constituency':r['historical_constituency'],'historical_seats_2016':r['historical_seats_2016']} for r in missing],
        'covered':covered,
        'invariants':{'candidate_identities_not_yet_counted':True,'predictive_judgments_generated':False,'outcomes_unsealed':False,'F1_created':False},
    }
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/'coverage.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'counts':payload['counts'],'missing':payload['missing']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
