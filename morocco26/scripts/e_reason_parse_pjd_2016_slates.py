#!/usr/bin/env python3
"""Parse admissible official PJD 2016 slate PDFs into verified candidate rows.

The Excel PDFs expose deterministic table cells but store Arabic glyphs in
visual character order. Each Arabic cell is converted to logical order by one
mechanical whole-cell reversal. A candidate identity is accepted only if that
logical character sequence (ignoring whitespace/diacritics) is independently
found in pypdf's text extraction of the same PDF. Territory, seats and ranks
remain fail-closed against the audited 92/92 TAFRA-2016 bridge.
"""
from __future__ import annotations

import html,json,re,unicodedata
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path

import pdfplumber

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'; CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'; ADM=ER/'evidence/pjd_2016_admissibility/decision.json'; OUT=ER/'evidence/pjd_2016_parsed_slates'
TABLE_SETTINGS={'vertical_strategy':'lines','horizontal_strategy':'lines','intersection_tolerance':5,'snap_tolerance':3,'join_tolerance':3}
TERRITORY_ALIASES={'اسا الزالك':'assa-zag','اسا الزاك':'assa-zag','الناضور':'nador','الناظور':'nador','الدرويش':'driouch','الدريوش':'driouch','سيدي افني':'sidi-ifni','الفقيه بنصالح':'fquih-ben-salah','ابن امسيك':'ben-m-sick','ابن مسيك':'ben-m-sick','طنجة اصيلا':'tanger-assilah','طنجة اصيلة':'tanger-assilah','بزو واوزغت':'bzou-ouaouizeght','بزو واويزغت':'bzou-ouaouizeght'}

def clean(v): return '' if v is None else ' '.join(str(v).replace('\n',' ').split())
def logical_ar(v): return clean(v)[::-1].strip()
def norm_ar(s):
 x=html.unescape(clean(s)); x=unicodedata.normalize('NFC',x).replace('ـ',''); x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x); x=re.sub(r'[أإآٱ]','ا',x); x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x); return ' '.join(x.split())
def compact_ar(s): return norm_ar(s).replace(' ','')
def build_territory_index(cross):
 idx=defaultdict(set); by={}
 for r in cross['records']:
  cid=r['source_2026_constituency_id']; by[cid]=r
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   n=norm_ar(v)
   if n:idx[n].add(cid)
 for n,cid in TERRITORY_ALIASES.items():idx[norm_ar(n)].add(cid)
 return idx,by
def resolve_territory(value,idx,by):
 n=norm_ar(value); c=idx.get(n,set())
 if len(c)==1:
  cid=next(iter(c)); return by[cid],n,'MECHANICAL_VISUAL_TO_LOGICAL_PLUS_EXACT_ARABIC'
 return None,n,'UNRESOLVED_OR_AMBIGUOUS'
def extract_rows(pdf_path):
 out=[]; diag=[]
 with pdfplumber.open(str(pdf_path)) as pdf:
  for pageno,page in enumerate(pdf.pages,1):
   table=page.find_table(TABLE_SETTINGS)
   if table is None:diag.append({'page':pageno,'error':'NO_TABLE'});continue
   rows=table.extract(x_tolerance=2,y_tolerance=2) or []
   diag.append({'page':pageno,'extraction_mode':'VISUAL_TABLE_CELLS','table_rows':len(rows),'table_cells':len(table.cells),'sample_raw':[[clean(c) for c in r] for r in rows[:4]],'sample_logical':[[logical_ar(c) if c and re.search(r'[\u0600-\u06FF]',str(c)) else clean(c) for c in r] for r in rows[:4]]})
   for ri,row in enumerate(rows):
    cells=[clean(c) for c in row]
    if len(cells)<11 or not re.fullmatch(r'\d+',cells[6] or ''):continue
    seats=int(cells[6])
    if 2<=seats<=6:out.append({'page':pageno,'row_index_on_page':ri,'cells':cells,'seats_pdf':seats})
 return out,diag

def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'))
 if cross.get('status')!='PASS' or cross['counts']['resolved']!=92:raise RuntimeError('historical Arabic bridge not PASS 92/92')
 adm=json.loads(ADM.read_text(encoding='utf-8'))
 if adm.get('status')!='PASS' or adm.get('accepted_document_count')!=3:raise RuntimeError('PJD admissibility not PASS 3/3')
 accepted={d['article_id']:d for d in adm['decisions'] if d['decision'].startswith('ADMISSIBLE')}
 latest=json.loads(LATEST.read_text(encoding='utf-8')); manifest=json.loads((ROOT/latest['latest_manifest']).read_text(encoding='utf-8')); docs=[d for d in manifest['documents'] if d['article_id'] in accepted]
 idx,by=build_territory_index(cross); candidates=[]; territories=[]; failures=[]; docdiag=[]; seen={}
 for doc in docs:
  doc_text=(ROOT/doc['text_path']).read_text(encoding='utf-8',errors='replace'); doc_compact=compact_ar(doc_text); rows,diag=extract_rows(ROOT/doc['raw_path']); docdiag.append({'article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'text_sha256':__import__('hashlib').sha256(doc_text.encode('utf-8')).hexdigest(),'diagnostics':diag})
  for raw in rows:
   cells=raw['cells']; territory_logical=logical_ar(cells[7]); tr,tnorm,method=resolve_territory(territory_logical,idx,by); failure=[]
   if tr is None:failure.append('TERRITORY_UNRESOLVED')
   seats=raw['seats_pdf']; hist=int(tr['historical_seats_2016']) if tr else None
   if tr and hist!=seats:failure.append(f'SEAT_MISMATCH_PDF_{seats}_TAFRA_{hist}')
   names={rank:logical_ar(cells[6-rank]) for rank in range(1,7) if cells[6-rank]}
   expected=set(range(1,seats+1)); actual=set(names)
   if actual!=expected:failure.append(f'RANK_SET_MISMATCH_expected_{sorted(expected)}_actual_{sorted(actual)}')
   if len({compact_ar(x) for x in names.values() if compact_ar(x)})!=seats:failure.append('CANDIDATE_IDENTITY_DUPLICATE_OR_EMPTY')
   unverified=[{'rank':rank,'name':name} for rank,name in names.items() if compact_ar(name) not in doc_compact]
   if unverified:failure.append('CANDIDATE_NOT_CROSS_VERIFIED_IN_PYPDF_TEXT')
   if failure:
    failures.append({'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page'],'territory_visual_raw':cells[7],'territory_logical':territory_logical,'territory_normalized':tnorm,'unverified_candidates':unverified,'failures':failure,'cells_visual_raw':cells,'names_logical':names});continue
   cid=tr['source_2026_constituency_id']
   if cid in seen:
    failures.append({'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page'],'territory_logical':territory_logical,'failures':['DUPLICATE_TERRITORY_ACROSS_DOCUMENTS'],'prior':seen[cid]});continue
   seen[cid]={'article_id':doc['article_id'],'page':raw['page'],'row':raw['row_index_on_page']}
   territories.append({'year':2016,'party':'PJD','article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'constituency_id':cid,'territory_visual_raw_ar':cells[7],'territory_logical_ar':territory_logical,'territory_resolution':method,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'historical_region':tr['historical_region'],'seats':seats,'candidate_count':len(names),'formal_endorsement':True,'source_class':'T1_OFFICIAL_PARTY','transport':'MIGRATED_STATIC_ARCHIVAL_MIRROR'})
   for rank in range(1,seats+1):
    name=names[rank]; candidates.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'candidate_rank':rank,'candidate_name_ar':name,'candidate_name_ar_visual_raw':cells[6-rank],'candidate_name_ar_normalized':norm_ar(name),'identity_cross_verified_in_pypdf_text':True,'CANDIDATE_REGISTERED_RANK':rank,'FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'source_class':'T1_OFFICIAL_PARTY','transport':'MIGRATED_STATIC_ARCHIVAL_MIRROR'})
 byterrit=defaultdict(list)
 for c in candidates:byterrit[c['constituency_id']].append(c)
 identity_ge3=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in byterrit.values()); enriched=len({c['constituency_id'] for c in candidates if c['FORMAL_ENDORSEMENT']})
 status='FAIL_CLOSED_DIAGNOSTIC_PERSISTED' if failures else ('PASS' if identity_ge3>=70 and enriched>=50 else 'PARTIAL_VALID')
 payload={'schema_version':'2.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':status,'documents':[d['article_id'] for d in docs],'territory_rows':territories,'candidate_rows':candidates,'failures':failures,'counts':{'territories_parsed':len(territories),'candidate_rows':len(candidates),'districts_with_at_least_three_verified_candidate_identities':identity_ge3,'districts_with_formal_endorsement_enrichment':enriched,'required_identity_districts':70,'required_enriched_districts':50,'identity_gate_pass':identity_ge3>=70,'enriched_gate_pass':enriched>=50},'document_diagnostics':docdiag,'invariants':{'visual_to_logical_transform':'WHOLE_CELL_CODEPOINT_REVERSAL','candidate_identity_requires_independent_pypdf_text_match':True,'failed_rows_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':status,'counts':payload['counts'],'failure_count':len(failures),'failure_sample':failures[:10]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
