#!/usr/bin/env python3
"""Recover the pre-election Official Gazette carrying decree 2-07-160.

Outcome-blind acquisition only. Tries official SGG historical URL variants, then the
Internet Archive CDX index for archived copies of those *original 2007 official PDFs*.
An archived copy is acceptable provenance because the underlying official document
was published before election day; archive timestamp is recorded separately.
"""
from __future__ import annotations
import hashlib, json, re, shutil, subprocess
from pathlib import Path
from urllib.parse import quote
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'goal100'/'historical'/'2007_v2_research'/'official_gazette'
OUT.mkdir(parents=True,exist_ok=True)
BASE='2508256551f94ad67c23a39d7263e01202431bfe'
FORBIDDEN=[ROOT/'data'/'goal100'/'historical'/'2007'/'legislative_2007_outcome_canonical.json',ROOT/'data'/'goal100'/'historical'/'2007'/'historical_native_map_outcome_transcription.json']
URLS=[
 'https://www.sgg.gov.ma/BO/AR/2007/BO_5513_Ar.pdf',
 'https://www.sgg.gov.ma/BO/bulletin/Ar/2007/BO_5513_Ar.pdf',
 'https://www.sgg.gov.ma/BO/bulletin/AR/2007/BO_5513_Ar.pdf',
 'http://www.sgg.gov.ma/BO/bulletin/AR/2007/BO_5513_Ar.pdf',
 'http://www.sgg.gov.ma/BO/bulletin/Ar/2007/BO_5513_Ar.pdf',
 'https://www.sgg.gov.ma/BO/bo_fr/2007/bo_5514_fr.pdf',
 'https://www.sgg.gov.ma/BO/FR/2007/BO_5514_Fr.pdf',
 'http://www.sgg.gov.ma/BO/bulletin/FR/2007/BO_5514_Fr.pdf',
]
S=requests.Session(); S.headers.update({'User-Agent':'MOROCCO26-historical-research/2.0'})
def h(b): return hashlib.sha256(b).hexdigest()
def clean_guard():
 bad=[str(p.relative_to(ROOT)) for p in FORBIDDEN if p.exists()]
 if bad: raise SystemExit('LEAKAGE_GUARD_FAIL '+repr(bad))
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if subprocess.run(['git','merge-base','--is-ancestor',BASE,head],cwd=ROOT).returncode: raise SystemExit('LEAKAGE_GUARD_FAIL ancestry')
 return {'base':BASE,'head':head,'derived_outcome_paths_present':bad}
def get_pdf(url):
 try:
  r=S.get(url,timeout=35,allow_redirects=True)
  ok=r.status_code==200 and len(r.content)>10000 and r.content[:4]==b'%PDF'
  return {'requested_url':url,'final_url':r.url,'status_code':r.status_code,'bytes':len(r.content),'content_type':r.headers.get('content-type'),'is_pdf':ok,'data':r.content if ok else None}
 except Exception as e: return {'requested_url':url,'error':repr(e),'is_pdf':False,'data':None}
def cdx(original):
 api='https://web.archive.org/cdx/search/cdx?url='+quote(original,safe='')+'&output=json&filter=statuscode:200&collapse=digest&from=2007&to=2026'
 try:
  r=S.get(api,timeout=30); rows=r.json() if r.status_code==200 else []
 except Exception: return []
 if not isinstance(rows,list) or len(rows)<2: return []
 out=[]
 for row in rows[1:]:
  if len(row)<3: continue
  ts=row[1]; orig=row[2]
  out.append({'timestamp':ts,'original':orig,'archive_url':f'https://web.archive.org/web/{ts}id_/{orig}'})
 return out[-8:]
def extract_text(pdf_path):
 if not shutil.which('pdftotext'): return {'status':'PDFTOTEXT_UNAVAILABLE'}
 txt=pdf_path.with_suffix('.txt')
 p=subprocess.run(['pdftotext','-layout',str(pdf_path),str(txt)],capture_output=True,text=True)
 if p.returncode!=0: return {'status':'PDFTOTEXT_FAILED','stderr':p.stderr[-1000:]}
 text=txt.read_text(encoding='utf-8',errors='replace') if txt.exists() else ''
 hits=[]
 for pat in (r'2\s*[-.]\s*07\s*[-.]\s*160',r'2\s*[-.]\s*02\s*[-.]\s*587',r'circonscriptions?\s+électorales?',r'Chambre\s+des\s+représentants'):
  for m in re.finditer(pat,text,re.I): hits.append({'pattern':pat,'context':re.sub(r'\s+',' ',text[max(0,m.start()-250):m.end()+450]).strip()})
 return {'status':'TEXT_EXTRACTED' if text.strip() else 'EMPTY_SCAN_TEXT','text_bytes':len(text.encode()),'hits':hits[:100]}
def main():
 lineage=clean_guard(); attempts=[]; found=None; archive_meta=None
 for u in URLS:
  rec=get_pdf(u); data=rec.pop('data',None); attempts.append(rec)
  if data:
   found=(u,data); break
 if not found:
  for original in URLS:
   for ar in reversed(cdx(original)):
    rec=get_pdf(ar['archive_url']); data=rec.pop('data',None); rec['archive_timestamp']=ar['timestamp']; rec['archive_original']=ar['original']; attempts.append(rec)
    if data:
     found=(original,data); archive_meta=ar; break
   if found: break
 manifest={'schema_version':'2.0','research_id':'M26-HIST-2007-OFFICIAL-GAZETTE-RECOVERY-V2','outcome_used':False,'lineage':lineage,'target_decree':'2-07-160','expected_document_date':'2007-03-30','expected_gazettes':[{'number':'5513','language':'ar','date':'2007-04-02'},{'number':'5514','language':'fr','date':'2007-04-05'}],'attempts':attempts,'recovered':False}
 if found:
  original,data=found; name='BO_5513_or_5514_recovered.pdf'; p=OUT/name; p.write_bytes(data)
  manifest.update({'recovered':True,'original_official_url':original,'archive':archive_meta,'path':str(p.relative_to(ROOT)),'sha256':h(data),'bytes':len(data),'text_extraction':extract_text(p)})
 (OUT/'official_gazette_recovery_manifest_v2.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'recovered':manifest['recovered'],'attempts':len(attempts),'text_status':manifest.get('text_extraction',{}).get('status'),'hits':len(manifest.get('text_extraction',{}).get('hits',[]))}))
if __name__=='__main__': main()
