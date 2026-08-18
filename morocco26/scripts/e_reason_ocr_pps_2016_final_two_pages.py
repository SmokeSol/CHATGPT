#!/usr/bin/env python3
"""Last-resort OCR diagnostic for two PPS pages blocked only by PDF font maps.

The underlying Fès-Meknès PDF is already mechanically admissible T1 evidence.
Only pages 3 and 5 are rasterized because their embedded Arabic header text is
font-map-corrupted and earlier exact typographic extraction could not resolve
them safely. OCR is diagnostic here: no candidate fact is promoted by this
script. Full raster hashes, OCR text and word-level confidence boxes are frozen.
"""
from __future__ import annotations
import hashlib,json,os,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
import fitz
import pytesseract
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json'
OUT=ER/'evidence/pps_2016_final_two_page_ocr';OUT.mkdir(parents=True,exist_ok=True)
TARGET_PAGES=[3,5]
def norm_ar(s):
 x=unicodedata.normalize('NFKC',str(s or '')).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}));x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x);x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def main():
 ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'));audit=json.loads(AUD.read_text(encoding='utf-8'))
 hit=next(x for x in probe['pdf_hits'] if x['region_slug']=='fes-meknes')
 rel=next((x for x in audit['relationships'] if x.get('probe_sha256')==hit['sha256'] and x.get('mechanical_pass')),None)
 if rel is None:raise RuntimeError('Fes-Meknes PPS PDF is not mechanically admissible')
 pdf_path=ROOT/hit['pdf']['raw_path'];doc=fitz.open(str(pdf_path));rows=[]
 for pageno in TARGET_PAGES:
  page=doc[pageno-1];pix=page.get_pixmap(matrix=fitz.Matrix(4,4),alpha=False);png=OUT/f'page_{pageno}.png';pix.save(str(png));b=png.read_bytes();im=Image.open(png)
  text=pytesseract.image_to_string(im,lang='ara',config='--psm 6')
  txt=OUT/f'page_{pageno}.txt';txt.write_text(text,encoding='utf-8')
  data=pytesseract.image_to_data(im,lang='ara',config='--psm 6',output_type=pytesseract.Output.DICT)
  words=[]
  for i,t in enumerate(data.get('text',[])):
   t=str(t).strip()
   if not t:continue
   try:conf=float(data['conf'][i])
   except:conf=-1
   words.append({'text':t,'normalized_ar':norm_ar(t),'conf':conf,'left':int(data['left'][i]),'top':int(data['top'][i]),'width':int(data['width'][i]),'height':int(data['height'][i])})
  wp=OUT/f'page_{pageno}_words.json';wp.write_text(json.dumps(words,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
  rows.append({'page':pageno,'raster_sha256':hashlib.sha256(b).hexdigest(),'raster_path':str(png.relative_to(ROOT)),'raster_width':im.width,'raster_height':im.height,'ocr_text_path':str(txt.relative_to(ROOT)),'ocr_words_path':str(wp.relative_to(ROOT)),'ocr_text':text,'ocr_text_normalized':norm_ar(text),'word_count':len(words),'high_conf_arabic_words':[x for x in words if x['conf']>=70 and x['normalized_ar']]})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_class':'T1_OFFICIAL_PARTY','source_pdf_sha256':hit['sha256'],'source_pdf_path':hit['pdf']['raw_path'],'parent_page_url':rel['page_url'],'parent_page_timestamps':rel['page_timestamps'],'target_pages':TARGET_PAGES,'pages':rows,'status':'OCR_DIAGNOSTIC_COMPLETE','invariants':{'ocr_scope_pages_exactly':[3,5],'underlying_pdf_mechanically_admissible':True,'candidate_identities_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 (OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'pages':[{'page':x['page'],'text':x['ocr_text'],'high_conf_words':x['high_conf_arabic_words']} for x in rows]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
