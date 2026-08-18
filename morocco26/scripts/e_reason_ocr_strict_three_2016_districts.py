#!/usr/bin/env python3
"""Targeted OCR diagnostic for the three safest strict-2016 closure districts.

Targets are fixed *before OCR*: Fahs-Anjra, Ifrane, and Sidi-Ifni. Each already
has two independently verified PJD identities in the strict gate. This script
searches only the already-qualified PPS regional PDFs. It promotes nothing.
A page becomes a candidate for later manual/mechanical promotion only when the
normalized constituency identity appears exactly in the top 40% OCR crop.
"""
from __future__ import annotations
import hashlib,json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
import fitz
import pytesseract
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
AUD=ER/'evidence/pps_2016_pdf_provenance_audit/audit.json'
PTR=ER/'pps_2016_regional_pdf_probe_latest.json'
STRICT=ER/'evidence/strict_2016_integrity_gate/gate.json'
OUT=ER/'evidence/strict_2016_three_district_ocr_diagnostic'
TARGETS={'fahs-anjra','ifrane','sidi-ifni'}
REGION_SLUG={
 'Tanger - Tétouan - Al Hoceima':'tanger-tetouan-al-hoceima',
 'Fès - Meknès':'fes-meknes',
 'Guelmim - Oued-Noun':'guelmim-oued-noun',
}
def clean(v):return ' '.join(str(v or '').replace('\n',' ').split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',clean(s)).replace('ـ','')
 x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك','ۀ':'ة','ہ':'ه'}))
 x=re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]','',x)
 x=re.sub(r'[أإآٱ]','ا',x)
 x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x)
 return ' '.join(x.split())
def compact(s):return norm_ar(s).replace(' ','')
def sha256_file(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def image_from_page(page,scale=2.5):
 pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
 return Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
def tsv_rows(im,psm):
 d=pytesseract.image_to_data(im,lang='ara',config=f'--psm {psm}',output_type=pytesseract.Output.DICT)
 rows=[]
 for i,t in enumerate(d.get('text',[])):
  t=clean(t)
  if not t:continue
  try:conf=float(d['conf'][i])
  except:conf=-1
  rows.append({'text':t,'normalized_ar':norm_ar(t),'conf':conf,'left':int(d['left'][i]),'top':int(d['top'][i]),'width':int(d['width'][i]),'height':int(d['height'][i]),'block_num':int(d['block_num'][i]),'par_num':int(d['par_num'][i]),'line_num':int(d['line_num'][i])})
 return rows
def line_groups(rows):
 g={}
 for r in rows:
  k=(r['block_num'],r['par_num'],r['line_num'])
  g.setdefault(k,[]).append(r)
 out=[]
 for k,xs in g.items():
  xs=sorted(xs,key=lambda z:z['left'],reverse=True)
  text=' '.join(x['text'] for x in xs);n=norm_ar(text)
  confs=[x['conf'] for x in xs if x['conf']>=0]
  out.append({'key':list(k),'text':text,'normalized_ar':n,'compact_ar':compact(n),'mean_conf':round(sum(confs)/len(confs),2) if confs else None,'min_conf':round(min(confs),2) if confs else None,'top':min(x['top'] for x in xs),'bottom':max(x['top']+x['height'] for x in xs),'left':min(x['left'] for x in xs),'right':max(x['left']+x['width'] for x in xs),'words':xs})
 return sorted(out,key=lambda z:(z['top'],z['left']))
def main():
 cross=json.loads(CROSS.read_text(encoding='utf-8'));aud=json.loads(AUD.read_text(encoding='utf-8'));ptr=json.loads(PTR.read_text(encoding='utf-8'));strict=json.loads(STRICT.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 if strict.get('status')!='E_REASON_2016_STRICT_INTEGRITY_PARTIAL':raise RuntimeError('strict gate state changed; re-plan before OCR')
 residual={x['constituency_id']:x for x in strict.get('residual_below_three',[])}
 if not TARGETS.issubset(residual):raise RuntimeError('pre-fixed target set no longer matches strict residual')
 by={r['source_2026_constituency_id']:r for r in cross['records']}
 passed={r['probe_sha256']:r for r in aud['relationships'] if r.get('mechanical_pass')}
 docs_by_region={}
 for d in probe['pdf_hits']:
  if d['sha256'] in passed:docs_by_region[d['region_slug']]=d
 target_meta=[]
 for cid in sorted(TARGETS):
  r=by[cid];slug=REGION_SLUG[r['historical_region']];d=docs_by_region[slug];p=ROOT/d['pdf']['raw_path']
  if sha256_file(p)!=d['sha256']:raise RuntimeError(f'PDF hash mismatch for {slug}')
  variants=sorted({compact(r.get('name_ar')),compact(r.get('name_ar_source_form')),compact(r.get('name_ar_match_key'))}-{''},key=len,reverse=True)
  target_meta.append({'constituency_id':cid,'historical_constituency':r['historical_constituency'],'historical_region':r['historical_region'],'historical_seats_2016':r['historical_seats_2016'],'variants_compact_ar':variants,'region_slug':slug,'pdf_sha256':d['sha256'],'pdf_path':d['pdf']['raw_path'],'parent_page_url':passed[d['sha256']]['page_url'],'parent_page_timestamps':passed[d['sha256']]['page_timestamps']})
 pages=[]
 for tm in target_meta:
  doc=fitz.open(str(ROOT/tm['pdf_path']))
  for idx,page in enumerate(doc):
   im=image_from_page(page);w,h=im.size
   header=im.crop((0,0,w,int(h*.40)))
   header_text=pytesseract.image_to_string(header,lang='ara',config='--psm 6')
   hc=compact(header_text);matched=[v for v in tm['variants_compact_ar'] if v and v in hc]
   if not matched:continue
   full_rows=tsv_rows(im,11);lines=line_groups(full_rows)
   # Candidate-band diagnostics only; no automatic identity promotion.
   band=[x for x in lines if x['top']>=int(h*.45) and x['top']<=int(h*.88) and x['normalized_ar'] and x['mean_conf'] is not None]
   pages.append({'constituency_id':tm['constituency_id'],'page':idx+1,'header_exact_match':True,'matched_variant_compact_ar':matched[0],'header_ocr_text':header_text,'header_ocr_normalized':norm_ar(header_text),'image_size':[w,h],'candidate_band_lines':band,'all_high_conf_arabic_lines':[x for x in lines if x['mean_conf'] is not None and x['mean_conf']>=70 and re.search(r'[\u0600-\u06FF]',x['normalized_ar'])]})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'status':'DIAGNOSTIC_ONLY','pre_fixed_targets':sorted(TARGETS),'target_meta':target_meta,'exact_header_pages':pages,'counts':{'targets':len(TARGETS),'targets_with_exact_header_page':len({x['constituency_id'] for x in pages}),'exact_header_pages':len(pages)},'invariants':{'target_set_fixed_before_ocr':True,'qualified_pps_pdf_only':True,'exact_header_required':True,'candidate_identities_promoted':False,'candidate_rank_inferred':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'matches':[{'cid':x['constituency_id'],'page':x['page'],'header':x['header_ocr_normalized'],'candidate_band_sample':[y['normalized_ar'] for y in x['candidate_band_lines'][:12]]} for x in pages]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
