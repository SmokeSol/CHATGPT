#!/usr/bin/env python3
"""Promote only cross-modally verified PPS identities for Ifrane and Sidi-Ifni.

Promotion is intentionally narrow. Territory identity was independently proven
by exact Arabic OCR of the poster header. Candidate identity must then occur as
an exact normalized standalone line in the embedded text of that same PDF page.
The accepted lines below are the person-name lines adjudicated from the frozen
cross-modal diagnostic; descriptive/biographical lines are explicitly rejected.
No rank, result, or post-election fact is inferred.
"""
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
DIAG=ER/'evidence/strict_2016_ifrane_sidi_embedded_name_diagnostic/diagnostic.json'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
OUT=ER/'evidence/strict_2016_ifrane_sidi_crossmodal_candidates'
ACCEPTED={
 'ifrane':['حسن السعودي'],
 'sidi-ifni':['مبارك البطاح','نعيمة كريم'],
}
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',clean(s)).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def main():
 d=json.loads(DIAG.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'));rows={x['constituency_id']:x for x in d['rows']};meta={x['source_2026_constituency_id']:x for x in cross['records']}
 if set(rows)!=set(ACCEPTED):raise RuntimeError('diagnostic target drift')
 territories=[];candidates=[]
 for cid,names in ACCEPTED.items():
  r=rows[cid];m=meta[cid]
  if r.get('header_exact_match') is not True:raise RuntimeError(f'header not exact for {cid}')
  if str(m.get('historical_seats_2016'))!='2':raise RuntimeError(f'unexpected seat magnitude for {cid}')
  embedded=set(r['embedded_text_lines_normalized'])
  for name in names:
   if norm_ar(name) not in embedded:raise RuntimeError(f'accepted name absent as standalone exact line: {cid} {name}')
  territories.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':m['historical_id_constituency'],'historical_constituency':m['historical_constituency'],'historical_region':m['historical_region'],'seats':m['historical_seats_2016'],'candidate_count_promoted':len(names),'FORMAL_ENDORSEMENT':True,'source_class':'T1_OFFICIAL_PARTY','identity_verification':'EXACT_HEADER_OCR_PLUS_EXACT_SAME_PAGE_EMBEDDED_NAME_LINE','pdf_sha256':r['pdf_sha256'],'parent_page_url':r['parent_page_url'],'parent_page_timestamps':r['parent_page_timestamps'],'page':r['page']})
  for name in names:
   candidates.append({'year':2016,'party':'PPS','constituency_id':cid,'historical_id_constituency':m['historical_id_constituency'],'historical_constituency':m['historical_constituency'],'candidate_name_ar':name,'candidate_name_ar_normalized':norm_ar(name),'candidate_rank':None,'CANDIDATE_REGISTERED_RANK':None,'rank_evidence_status':'MISSING_NOT_INFERRED','FORMAL_ENDORSEMENT':True,'party_fact_status':'PARTY_ANNOUNCED','identity_verification':'EXACT_HEADER_OCR_PLUS_EXACT_SAME_PAGE_EMBEDDED_NAME_LINE','evidence':{'publication_time':r['parent_page_timestamps'][0],'retrieval_time':d['created_at'],'source_class':'T1_OFFICIAL_PARTY','content_sha256':r['pdf_sha256'],'parent_page_url':r['parent_page_url'],'pdf_page':r['page'],'matched_header_variant_compact_ar':r['matched_header_variant_compact_ar'],'header_ocr_normalized':r['header_ocr_normalized'],'exact_embedded_name_line':norm_ar(name)}})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'PASS','source_diagnostic':str(DIAG.relative_to(ROOT)),'territory_rows':territories,'candidate_rows':candidates,'counts':{'territories':len(territories),'candidate_rows':len(candidates)},'explicit_rejections':['للشؤون الصحراوية','والخدمات بجهة كلميم وادنون','والخدمات بجهة كلميم السمارة'],'invariants':{'exact_header_ocr_required':True,'exact_same_page_standalone_name_line_required':True,'person_name_fuzzy_matching':False,'biography_lines_promoted':False,'candidate_rank_inferred':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'evidence.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'candidate_rows':[{'cid':x['constituency_id'],'name':x['candidate_name_ar_normalized']} for x in candidates]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
