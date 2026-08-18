#!/usr/bin/env python3
"""Verify readable candidate-name lines on exact-header OCR pages.

The prior frozen OCR diagnostic identifies the constituency independently from
page-image pixels. This script then reads the embedded PDF text *on that exact
page* and records person-like Arabic lines near the candidate area. It promotes
nothing; it is a cross-modal verification diagnostic.
"""
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
DIAG=ER/'evidence/strict_2016_three_district_ocr_diagnostic/diagnostic.json'
OUT=ER/'evidence/strict_2016_ifrane_sidi_embedded_name_diagnostic'
TARGETS={'ifrane','sidi-ifni'}
NONPERSON={'وكيل اللائحة','وكيلة اللائحة','رجل اعمال','استاذ','استاذة','موظف','موظفة','طالب جامعي','فاعلة جمعوية','فاعل جمعوي','تقني متخصص','مقاول','تاجر','تاجرة','فلاح','متقاعد','مستشار جماعي','مدير مدرسة','حاصلة على الاجازة'}
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',clean(s)).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact(s):return norm_ar(s).replace(' ','')
def person_like(line):
 n=norm_ar(line);tok=n.split()
 if len(tok)<2 or len(tok)>4:return False
 if n in NONPERSON:return False
 blocked=('اللائحة','الدائرة','الانتخاب','التشريعية','اكتوبر','حزب','صوتوا','الكتاب','رئيس','عضو','مستشار','فاعل','استاذ','طالب','موظف','مدير','مقاول','تاجر','فلاح','متقاعد','تقني','حاصلة','الاجازة','غرفة','شركة','قطاع')
 if any(b in n for b in blocked):return False
 if any(t.isdigit() for t in tok):return False
 return bool(re.search(r'[\u0600-\u06FF]',n))
def main():
 d=json.loads(DIAG.read_text(encoding='utf-8'));pages={x['constituency_id']:x for x in d['exact_header_pages'] if x['constituency_id'] in TARGETS};meta={x['constituency_id']:x for x in d['target_meta'] if x['constituency_id'] in TARGETS}
 if set(pages)!=TARGETS:raise RuntimeError('exact-header proof missing for Ifrane or Sidi-Ifni')
 rows=[]
 for cid in sorted(TARGETS):
  p=pages[cid];m=meta[cid];reader=PdfReader(str(ROOT/m['pdf_path']));raw=reader.pages[int(p['page'])-1].extract_text() or '';lines=[clean(x) for x in raw.splitlines() if clean(x)];norm=[norm_ar(x) for x in lines if norm_ar(x)];cands=[x for x in norm if person_like(x)]
  rows.append({'constituency_id':cid,'historical_constituency':m['historical_constituency'],'pdf_sha256':m['pdf_sha256'],'pdf_path':m['pdf_path'],'parent_page_url':m['parent_page_url'],'parent_page_timestamps':m['parent_page_timestamps'],'page':p['page'],'header_exact_match':p['header_exact_match'],'matched_header_variant_compact_ar':p['matched_variant_compact_ar'],'header_ocr_normalized':p['header_ocr_normalized'],'embedded_text_raw':raw,'embedded_text_lines_normalized':norm,'person_like_embedded_lines':cands})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'CROSS_MODAL_DIAGNOSTIC_ONLY','rows':rows,'counts':{'targets':2,'targets_with_exact_header':2,'targets_with_person_like_embedded_line':sum(bool(x['person_like_embedded_lines']) for x in rows)},'invariants':{'same_exact_page_cross_modal_verification':True,'candidate_identities_promoted':False,'person_name_fuzzy_matching':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'rows':[{'cid':x['constituency_id'],'page':x['page'],'person_like':x['person_like_embedded_lines'],'lines':x['embedded_text_lines_normalized']} for x in rows]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
