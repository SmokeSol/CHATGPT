#!/usr/bin/env python3
"""Robust OCR search for the pre-fixed Fahs-Anjra PPS poster page.

Search scope is only the already-qualified Tanger-Tetouan-Al Hoceima PPS PDF.
The target Arabic territory identity is frozen from the crosswalk before OCR.
Multiple image transforms / Tesseract segmentation modes are diagnostic only;
no page or candidate is promoted unless an exact normalized target header is
recovered.
"""
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from difflib import SequenceMatcher
from pathlib import Path
import fitz,pytesseract
from PIL import Image,ImageEnhance,ImageFilter,ImageOps
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json';AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/strict_2016_fahs_anjra_header_ocr'
CID='fahs-anjra';REGION='tanger-tetouan-al-hoceima'
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',clean(s)).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def compact(s):return norm_ar(s).replace(' ','')
def transforms(crop):
 g=ImageOps.grayscale(crop);auto=ImageOps.autocontrast(g);sharp=auto.filter(ImageFilter.SHARPEN);boost=ImageEnhance.Contrast(sharp).enhance(1.8)
 out={'rgb':crop,'gray_auto':auto,'contrast':boost}
 for th in (120,145,165,185,205):out[f'threshold_{th}']=boost.point(lambda p,t=th:255 if p>t else 0)
 return out
def max_similarity(text,target):
 lines=[compact(x) for x in str(text).splitlines() if compact(x)];
 if not lines:return 0.0,None
 best=max(((SequenceMatcher(None,x,target).ratio(),x) for x in lines),key=lambda z:z[0]);return round(best[0],6),best[1]
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));audit=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'));r=next(x for x in cross['records'] if x['source_2026_constituency_id']==CID);target=compact(r['name_ar_match_key']);hit=next(x for x in probe['pdf_hits'] if x['region_slug']==REGION);rel=next(x for x in audit['relationships'] if x.get('probe_sha256')==hit['sha256'] and x.get('mechanical_pass'))
 doc=fitz.open(str(ROOT/hit['pdf']['raw_path']));runs=[];exact=[]
 for pi,page in enumerate(doc,1):
  pix=page.get_pixmap(matrix=fitz.Matrix(5,5),alpha=False);im=Image.frombytes('RGB',[pix.width,pix.height],pix.samples);crop=im.crop((0,0,im.width,int(im.height*.52)))
  for vname,vim in transforms(crop).items():
   for psm in (3,6,11,12):
    text=pytesseract.image_to_string(vim,lang='ara',config=f'--psm {psm}');nc=compact(text);is_exact=target in nc;sim,best=max_similarity(text,target);rec={'page':pi,'variant':vname,'psm':psm,'exact_target_present':is_exact,'similarity':sim,'best_line_compact_ar':best,'ocr_text':text,'ocr_normalized':norm_ar(text)};runs.append(rec)
    if is_exact:exact.append(rec)
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'EXACT_HEADER_FOUND' if exact else 'NO_EXACT_HEADER_YET','constituency_id':CID,'historical_constituency':r['historical_constituency'],'target_compact_ar':target,'source_pdf_sha256':hit['sha256'],'source_pdf_path':hit['pdf']['raw_path'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'page_count':len(doc),'exact_matches':exact,'top_diagnostics':sorted(runs,key=lambda x:(x['exact_target_present'],x['similarity']),reverse=True)[:30],'counts':{'ocr_runs':len(runs),'exact_matches':len(exact),'exact_pages':len({x['page'] for x in exact})},'invariants':{'target_fixed_from_crosswalk_before_ocr':True,'qualified_pps_pdf_only':True,'candidate_identities_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'counts':payload['counts'],'exact_pages':sorted({x['page'] for x in exact}),'top':[{'page':x['page'],'variant':x['variant'],'psm':x['psm'],'sim':x['similarity'],'best':x['best_line_compact_ar'],'exact':x['exact_target_present']} for x in payload['top_diagnostics'][:15]]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
