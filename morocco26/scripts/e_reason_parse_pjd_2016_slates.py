#!/usr/bin/env python3
"""Parse admissible official PJD 2016 slate PDFs into candidate rows.

The parser is fail-closed at row level. It accepts a row only when the Arabic
territory maps uniquely through the audited 92/92 identity bridge, PDF seat
magnitude equals TAFRA-2016, and the number of non-empty ordered candidate
cells equals seats. Failed rows are persisted as diagnostics but never promoted
into candidate evidence. No target-election outcomes are opened or used.
"""
from __future__ import annotations

import html,json,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

import pdfplumber

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
ADM=ER/'evidence/pjd_2016_admissibility/decision.json'
OUT=ER/'evidence/pjd_2016_parsed_slates'

TABLE_SETTINGS={'vertical_strategy':'lines','horizontal_strategy':'lines','intersection_tolerance':5,'snap_tolerance':3,'join_tolerance':3}

TERRITORY_ALIASES={
 'اسا الزالك':'assa-zag','اسا الزاك':'assa-zag','الناضور':'nador','الناظور':'nador',
 'الدرويش':'driouch','الدريوش':'driouch','سيدي افني':'sidi-ifni','الفقيه بنصالح':'fquih-ben-salah',
 'ابن امسيك':'ben-m-sick','ابن مسيك':'ben-m-sick','طنجة اصيلا':'tanger-assilah','طنجة اصيلة':'tanger-assilah',
 'بزو واوزغت':'bzou-ouaouizeght','بزو واويزغت':'bzou-ouaouizeght',
}

def clean(v):
    if v is None:return ''
    return ' '.join(str(v).replace('\n',' ').split())

def norm_ar(s):
    x=html.unescape(clean(s)); x=unicodedata.normalize('NFC',x).replace('ـ','')
    x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x); x=re.sub(r'[أإآٱ]','ا',x)
    x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x)
    return ' '.join(x.split())

def build_territory_index(cross):
    idx=defaultdict(set); by_cid={}
    for r in cross['records']:
        cid=r['source_2026_constituency_id']; by_cid[cid]=r
        for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
            n=norm_ar(v)
            if n: idx[n].add(cid)
    for n,cid in TERRITORY_ALIASES.items(): idx[norm_ar(n)].add(cid)
    return idx,by_cid

def resolve_territory(value,idx,by_cid):
    n=norm_ar(value); cids=idx.get(n,set())
    if len(cids)==1:
        cid=next(iter(cids)); return by_cid[cid],n,'EXACT_ARABIC_OR_AUDITED_TYPO_ALIAS'
    return None,n,'UNRESOLVED_OR_AMBIGUOUS'

def extract_rows(pdf_path):
    out=[]; diagnostics=[]
    with pdfplumber.open(str(pdf_path)) as pdf:
      for pageno,page in enumerate(pdf.pages,1):
        table=page.find_table(TABLE_SETTINGS)
        if table is None:
            diagnostics.append({'page':pageno,'error':'NO_TABLE'}); continue
        try:
            rows=table.extract(char_dir='rtl',line_dir='ttb',x_tolerance=2,y_tolerance=2) or []
            mode='NATIVE_RTL'
        except Exception as exc:
            # Persist the extraction exception and fall back only for diagnosis;
            # fallback rows remain subject to exact territory/seat/rank checks.
            rows=table.extract(x_tolerance=2,y_tolerance=2) or []
            mode='RAW_VISUAL_FALLBACK'
            diagnostics.append({'page':pageno,'rtl_extract_error':f'{type(exc).__name__}: {exc}'})
        diagnostics.append({'page':pageno,'extraction_mode':mode,'table_rows':len(rows),'table_cells':len(table.cells),'sample':[[clean(c) for c in r] for r in rows[:4]]})
        for ri,row in enumerate(rows):
            cells=[clean(c) for c in row]
            if len(cells)<11: continue
            if not re.fullmatch(r'\d+',cells[6] or ''): continue
            seats=int(cells[6])
            if seats<2 or seats>6: continue
            out.append({'page':pageno,'row_index_on_page':ri,'cells':cells,'seats_pdf':seats,'extraction_mode':mode})
    return out,diagnostics

def main():
    cross=json.loads(CROSS.read_text(encoding='utf-8'))
    if cross.get('status')!='PASS' or cross['counts']['resolved']!=92: raise RuntimeError('historical Arabic bridge not PASS 92/92')
    adm=json.loads(ADM.read_text(encoding='utf-8'))
    if adm.get('status')!='PASS' or adm.get('accepted_document_count')!=3: raise RuntimeError('PJD admissibility not PASS 3/3')
    accepted={d['article_id']:d for d in adm['decisions'] if d['decision'].startswith('ADMISSIBLE')}
    latest=json.loads(LATEST.read_text(encoding='utf-8')); manifest=json.loads((ROOT/latest['latest_manifest']).read_text(encoding='utf-8'))
    docs=[d for d in manifest['documents'] if d['article_id'] in accepted]
    idx,by_cid=build_territory_index(cross)
    candidate_rows=[]; territory_rows=[]; failures=[]; docdiag=[]
    seen_territories={}
    for doc in docs:
      rows,diag=extract_rows(ROOT/doc['raw_path']); docdiag.append({'article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'diagnostics':diag})
      for raw in rows:
        cells=raw['cells']; tr,norm,method=resolve_territory(cells[7],idx,by_cid)
        failure=[]
        if raw['extraction_mode']!='NATIVE_RTL': failure.append('NON_NATIVE_RTL_EXTRACTION_NOT_ADMISSIBLE')
        if tr is None: failure.append('TERRITORY_UNRESOLVED')
        seats=raw['seats_pdf']; hist_seats=int(tr['historical_seats_2016']) if tr else None
        if tr and hist_seats!=seats: failure.append(f'SEAT_MISMATCH_PDF_{seats}_TAFRA_{hist_seats}')
        names={rank:cells[6-rank] for rank in range(1,7) if cells[6-rank]}
        expected_ranks=set(range(1,seats+1)); actual_ranks=set(names)
        if actual_ranks!=expected_ranks: failure.append(f'RANK_SET_MISMATCH_expected_{sorted(expected_ranks)}_actual_{sorted(actual_ranks)}')
        if len({norm_ar(x) for x in names.values() if norm_ar(x)})!=seats: failure.append('CANDIDATE_IDENTITY_DUPLICATE_OR_EMPTY')
        if failure:
            failures.append({'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page'],'extraction_mode':raw['extraction_mode'],'territory_raw':cells[7],'territory_normalized':norm,'failures':failure,'cells':cells}); continue
        cid=tr['source_2026_constituency_id']
        if cid in seen_territories:
            failures.append({'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page'],'territory_raw':cells[7],'failures':['DUPLICATE_TERRITORY_ACROSS_DOCUMENTS'],'prior':seen_territories[cid]}); continue
        seen_territories[cid]={'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page']}
        territory_rows.append({'year':2016,'party':'PJD','article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'constituency_id':cid,'territory_raw_ar':cells[7],'territory_resolution':method,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'historical_region':tr['historical_region'],'seats':seats,'candidate_count':len(names),'formal_endorsement':True,'source_class':'T1_OFFICIAL_PARTY','transport':'MIGRATED_STATIC_ARCHIVAL_MIRROR'})
        for rank in range(1,seats+1):
            raw_name=names[rank]
            candidate_rows.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'candidate_rank':rank,'candidate_name_ar':raw_name,'candidate_name_ar_normalized':norm_ar(raw_name),'CANDIDATE_REGISTERED_RANK':rank,'FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'source_class':'T1_OFFICIAL_PARTY','transport':'MIGRATED_STATIC_ARCHIVAL_MIRROR'})
    byterrit=defaultdict(list)
    for c in candidate_rows: byterrit[c['constituency_id']].append(c)
    identity_ge3=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in byterrit.values())
    enriched=len({c['constituency_id'] for c in candidate_rows if c['FORMAL_ENDORSEMENT']})
    payload={'schema_version':'1.1','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS' if not failures and len(territory_rows)>=70 else ('PARTIAL_VALID' if not failures else 'FAIL_CLOSED_DIAGNOSTIC_PERSISTED'),'documents':[d['article_id'] for d in docs],'territory_rows':territory_rows,'candidate_rows':candidate_rows,'failures':failures,'counts':{'territories_parsed':len(territory_rows),'candidate_rows':len(candidate_rows),'districts_with_at_least_three_verified_candidate_identities':identity_ge3,'districts_with_formal_endorsement_enrichment':enriched,'required_identity_districts':70,'required_enriched_districts':50,'identity_gate_pass':identity_ge3>=70,'enriched_gate_pass':enriched>=50},'document_diagnostics':docdiag,'invariants':{'failed_rows_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
    OUT.mkdir(parents=True,exist_ok=True); (OUT/'parsed_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':payload['status'],'counts':payload['counts'],'failure_count':len(failures),'failure_sample':failures[:12]},ensure_ascii=False,indent=2))
    return 0

if __name__=='__main__': raise SystemExit(main())
