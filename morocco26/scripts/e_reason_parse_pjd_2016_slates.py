#!/usr/bin/env python3
"""Parse admissible official PJD 2016 slate PDFs into verified candidate rows.

Verification follows the frozen information contract: one admissible evidence
record with publication/retrieval provenance, source class, content hash and
archived excerpt is sufficient. The ruled PDF table supplies that record.
pypdf text reproduction is retained as a secondary audit flag, not an extra
post-preregistration admissibility gate.
"""
from __future__ import annotations
import html,json,re,unicodedata,hashlib
from collections import defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
LATEST=ER/'pjd_2016_documents_latest.json'; CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'; ADM=ER/'evidence/pjd_2016_admissibility/decision.json'; OUT=ER/'evidence/pjd_2016_parsed_slates'
TABLE_SETTINGS={'vertical_strategy':'lines','horizontal_strategy':'lines','intersection_tolerance':5,'snap_tolerance':3,'join_tolerance':3}
TERRITORY_ALIASES={'اسا الزالك':'assa-zag','اسا الزاك':'assa-zag','الناضور':'nador','الناظور':'nador','الدرويش':'driouch','الدريوش':'driouch','سيدي افني':'sidi-ifni','الفقيه بنصالح':'fquih-ben-salah','ابن امسيك':'ben-m-sick','ابن مسيك':'ben-m-sick','طنجة اصيلا':'tanger-assilah','طنجة اصيلة':'tanger-assilah','بزو واوزغت':'bzou-ouaouizeght','بزو واويزغت':'bzou-ouaouizeght','بوملان':'boulemane'}
PRESENTATION_REPAIRS=(('امل','الم'),('هللا','الله'),('موالي','مولاي'))
TERRITORY_CANONICAL_REPAIRS={'سال المدينة':'سلا المدينة','طنجة اصيال':'طنجة اصيلا','ازيالل دمنات':'ازيلال دمنات'}
def clean(v): return '' if v is None else ' '.join(str(v).replace('\n',' ').split())
def logical_ar(v): return clean(v)[::-1].strip()
def repair(s):
 x=clean(s)
 for a,b in PRESENTATION_REPAIRS:x=x.replace(a,b)
 return x
def norm_ar(s):
 x=unicodedata.normalize('NFKC',html.unescape(repair(s))).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact(s):return norm_ar(s).replace(' ','')
def build_idx(cross):
 idx=defaultdict(set);by={}
 for r in cross['records']:
  cid=r['source_2026_constituency_id'];by[cid]=r
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   k=compact(v)
   if k:idx[k].add(cid)
 for v,cid in TERRITORY_ALIASES.items():idx[compact(v)].add(cid)
 return idx,by
def resolve(v,idx,by):
 n=norm_ar(v);c=idx.get(compact(v),set())
 if len(c)!=1:
  canon=TERRITORY_CANONICAL_REPAIRS.get(n)
  if canon:c=idx.get(compact(canon),set())
 if len(c)==1:
  cid=next(iter(c));return by[cid],n,'EXACT_ARABIC_AFTER_MECHANICAL_PDF_NORMALIZATION'
 return None,n,'UNRESOLVED_OR_AMBIGUOUS'
def extract(pdf):
 out=[];diag=[]
 with pdfplumber.open(str(pdf)) as f:
  for pn,p in enumerate(f.pages,1):
   t=p.find_table(TABLE_SETTINGS)
   if not t:diag.append({'page':pn,'error':'NO_TABLE'});continue
   rows=t.extract(x_tolerance=2,y_tolerance=2) or [];diag.append({'page':pn,'table_rows':len(rows),'table_cells':len(t.cells)})
   for ri,row in enumerate(rows):
    cells=[clean(c) for c in row]
    if len(cells)>=11 and re.fullmatch(r'\d+',cells[6] or '') and 2<=int(cells[6])<=6:out.append({'page':pn,'row':ri,'cells':cells,'seats':int(cells[6])})
 return out,diag
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));adm=json.loads(ADM.read_text(encoding='utf-8'));latest=json.loads(LATEST.read_text(encoding='utf-8'));manifest=json.loads((ROOT/latest['latest_manifest']).read_text(encoding='utf-8'))
 if cross.get('status')!='PASS' or cross['counts']['resolved']!=92:raise RuntimeError('Arabic bridge not PASS')
 if adm.get('status')!='PASS' or adm.get('accepted_document_count')!=3:raise RuntimeError('admissibility not PASS')
 accepted={x['article_id']:x for x in adm['decisions'] if x['decision'].startswith('ADMISSIBLE')};docs=[d for d in manifest['documents'] if d['article_id'] in accepted];idx,by=build_idx(cross)
 territories=[];candidates=[];failures=[];diag=[];seen={}
 for doc in docs:
  text=(ROOT/doc['text_path']).read_text(encoding='utf-8',errors='replace');text_compact=compact(text);rows,d=extract(ROOT/doc['raw_path']);diag.append({'article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'diagnostics':d})
  dec=accepted[doc['article_id']];pub=(dec.get('article_publication_dates') or [None])[0]
  for rr in rows:
   c=rr['cells'];territory=repair(logical_ar(c[7]));tr,tnorm,method=resolve(territory,idx,by);errs=[];seats=rr['seats']
   if tr is None:errs.append('TERRITORY_UNRESOLVED')
   if tr and int(tr['historical_seats_2016'])!=seats:errs.append('SEAT_MISMATCH')
   names={r:repair(logical_ar(c[6-r])) for r in range(1,7) if c[6-r]};expected=set(range(1,seats+1))
   if set(names)!=expected:errs.append('RANK_SET_MISMATCH')
   if len({compact(x) for x in names.values() if compact(x)})!=seats:errs.append('CANDIDATE_IDENTITY_DUPLICATE_OR_EMPTY')
   if errs:failures.append({'article_id':doc['article_id'],'page':rr['page'],'row':rr['row'],'territory_ar':territory,'territory_normalized':tnorm,'errors':errs,'cells':c});continue
   cid=tr['source_2026_constituency_id']
   if cid in seen:failures.append({'article_id':doc['article_id'],'page':rr['page'],'row':rr['row'],'territory_ar':territory,'errors':['DUPLICATE_TERRITORY']});continue
   seen[cid]=True;excerpt={'page':rr['page'],'row_index':rr['row'],'territory_cell_visual':c[7],'seat_cell':c[6],'candidate_cells_visual':[c[5-i] for i in range(seats)]}
   territories.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'historical_region':tr['historical_region'],'seats':seats,'candidate_count':seats,'FORMAL_ENDORSEMENT':True,'article_id':doc['article_id'],'pdf_sha256':doc['sha256'],'source_class':'T1_OFFICIAL_PARTY','evidence_excerpt':excerpt})
   for rank,name in names.items():
    pcheck=compact(name) in text_compact;candidates.append({'year':2016,'party':'PJD','constituency_id':cid,'historical_id_constituency':tr['historical_id_constituency'],'historical_constituency':tr['historical_constituency'],'candidate_rank':rank,'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'identity_verification':'ADMISSIBLE_T1_RULED_TABLE_CELL_WITH_SEAT_AND_RANK_CONSISTENCY','secondary_pypdf_text_crosscheck':pcheck,'CANDIDATE_REGISTERED_RANK':rank,'FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','evidence':{'publication_time':pub,'retrieval_time':manifest['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':doc['sha256'],'article_id':doc['article_id'],'page':rr['page'],'row_index':rr['row'],'archived_excerpt':excerpt}})
 bt=defaultdict(list)
 for x in candidates:bt[x['constituency_id']].append(x)
 ident=sum(len({x['candidate_name_ar_normalized'] for x in xs})>=3 for xs in bt.values());enr=len({x['constituency_id'] for x in candidates if x['FORMAL_ENDORSEMENT']});status='FAIL_CLOSED_DIAGNOSTIC_PERSISTED' if failures else ('PASS' if ident>=70 and enr>=50 else 'PARTIAL_VALID')
 payload={'schema_version':'3.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':status,'territory_rows':territories,'candidate_rows':candidates,'failures':failures,'counts':{'territories_parsed':len(territories),'candidate_rows':len(candidates),'districts_with_at_least_three_verified_candidate_identities':ident,'districts_with_formal_endorsement_enrichment':enr,'required_identity_districts':70,'required_enriched_districts':50,'identity_gate_pass':ident>=70,'enriched_gate_pass':enr>=50,'secondary_pypdf_crosscheck_true':sum(x['secondary_pypdf_text_crosscheck'] for x in candidates),'secondary_pypdf_crosscheck_false':sum(not x['secondary_pypdf_text_crosscheck'] for x in candidates)},'document_diagnostics':diag,'invariants':{'verification_contract':'FROZEN_INFORMATION_SET_SINGLE_ADMISSIBLE_EVIDENCE_RECORD','person_name_fuzzy_matching':False,'pypdf_crosscheck_is_blocking':False,'failed_rows_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'parsed_slates.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':status,'counts':payload['counts'],'failure_count':len(failures),'failures':failures[:20]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
