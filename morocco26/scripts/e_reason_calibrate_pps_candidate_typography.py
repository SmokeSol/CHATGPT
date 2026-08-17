#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/pps_2016_candidate_typography_calibration'
TARGETS={'casablanca-settat':[7,9,12,13],'oriental':[2],'beni-mellal-khenifra':[5],'souss-massa':[1]}
def ar(x):return bool(re.search(r'[\u0600-\u06ff]',unicodedata.normalize('NFKC',str(x or ''))))
def main():
 ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'));out=[]
 for d in probe['pdf_hits']:
  if d['region_slug'] not in TARGETS:continue
  with pdfplumber.open(str(ROOT/d['pdf']['raw_path'])) as pdf:
   for pn in TARGETS[d['region_slug']]:
    if pn>len(pdf.pages):continue
    p=pdf.pages[pn-1];words=p.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=1,y_tolerance=1,extra_attrs=['size','fontname']) or []
    selected=[]
    for w in words:
     top=float(w['top']);size=float(w.get('size') or 0)
     if 0.50*float(p.height)<=top<=0.74*float(p.height) and size>=9.0 and ar(w['text']):selected.append({'text':w['text'],'nfkc':unicodedata.normalize('NFKC',w['text']),'reversed_nfkc':unicodedata.normalize('NFKC',w['text'])[::-1],'size':round(size,2),'fontname':w.get('fontname'),'x0':round(float(w['x0']),2),'x1':round(float(w['x1']),2),'top':round(top,2),'bottom':round(float(w['bottom']),2)})
    out.append({'region_slug':d['region_slug'],'page':pn,'width':p.width,'height':p.height,'words':sorted(selected,key=lambda z:(z['top'],z['x0']))})
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'pages':out,'invariants':{'candidate_facts_promoted':False,'outcomes_unsealed':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'calibration.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps([{'region':x['region_slug'],'page':x['page'],'words':len(x['words']),'sizes':sorted(set(w['size'] for w in x['words']),reverse=True)} for x in out],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
