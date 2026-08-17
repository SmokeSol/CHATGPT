#!/usr/bin/env python3
"""Diagnose page-level geometry of recovered PPS 2016 regional candidate PDFs.

Discovery/diagnostic only. Candidate facts are not promoted. The output exposes
page text, word positions, font sizes and candidate-like lines so a deterministic
parser can be frozen before extraction.
"""
from __future__ import annotations
import json,re,unicodedata
from collections import Counter,defaultdict
from datetime import datetime,timezone
from pathlib import Path
import pdfplumber
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
PTR=ER/'pps_2016_regional_pdf_probe_latest.json'
OUT=ER/'evidence/pps_2016_pdf_page_diagnostic'
TARGET_REGIONS={'casablanca-settat','souss-massa','oriental','beni-mellal-khenifra','rabat-sale-kenitra','marrakech-safi'}

def clean(x):return ' '.join(str(x or '').replace('\n',' ').split())
def arabic_ratio(s):
 s=clean(s);letters=[c for c in s if c.isalpha()];return (sum('\u0600'<=c<='\u06ff' for c in letters)/len(letters)) if letters else 0.0
def main():
 ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'))
 docs=[x for x in probe['pdf_hits'] if x['region_slug'] in TARGET_REGIONS]
 out=[]
 for d in docs:
  path=ROOT/d['pdf']['raw_path'];rec={'region_slug':d['region_slug'],'filename':d['filename'],'sha256':d['sha256'],'pages':[]}
  with pdfplumber.open(str(path)) as pdf:
   for pn,page in enumerate(pdf.pages,1):
    words=page.extract_words(use_text_flow=False,keep_blank_chars=False,x_tolerance=2,y_tolerance=2,extra_attrs=['fontname','size']) or []
    groups=defaultdict(list)
    for w in words:
     top=round(float(w['top']),1);key=None
     for k in groups:
      if abs(k-top)<=2.2:key=k;break
     if key is None:key=top
     groups[key].append(w)
    lines=[]
    for top,ws in sorted(groups.items()):
     logical=' '.join(clean(w['text']) for w in sorted(ws,key=lambda z:float(z['x0'])))
     rtl=' '.join(clean(w['text']) for w in sorted(ws,key=lambda z:-float(z['x0'])))
     sizes=sorted({round(float(w.get('size') or 0),1) for w in ws},reverse=True)
     lines.append({'top':top,'text_x_ascending':logical,'text_rtl_spatial':rtl,'sizes':sizes,'arabic_ratio':round(arabic_ratio(logical),3),'x_min':round(min(float(w['x0']) for w in ws),1),'x_max':round(max(float(w['x1']) for w in ws),1)})
    size_counts=Counter(round(float(w.get('size') or 0),1) for w in words if float(w.get('size') or 0)>0)
    rec['pages'].append({'page':pn,'width':page.width,'height':page.height,'text':page.extract_text(x_tolerance=2,y_tolerance=2) or '','font_size_counts':dict(size_counts.most_common()),'lines':lines})
  out.append(rec)
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'documents':out,'invariants':{'candidate_facts_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'diagnostic.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps([{'region':x['region_slug'],'pages':len(x['pages']),'page_sizes':[p['font_size_counts'] for p in x['pages'][:3]]} for x in out],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
