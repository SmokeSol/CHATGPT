#!/usr/bin/env python3
"""Probe exact PPS 2016 regional candidate-list PDF filenames.

Discovery-only. Every primary filename in NAMES below is now sourced directly
from a pre-cutoff official pps.ma region page recorded in the PPS provenance
audit. Legacy bounded variants are retained only where they previously produced
an exact file. No candidate identity is extracted or promoted by this probe.
"""
from __future__ import annotations
import hashlib,json,os,time
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
import requests
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';REG=ER/'e_reason_source_registry_v1.json'
RID=os.environ.get('E_REASON_PPS_PDF_PROBE_RUN_ID') or 'pps_pdf_probe_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/pps_2016_regional_pdf_probe'/RID;RAW=OUT/'raw';TEXT=OUT/'text';RAW.mkdir(parents=True,exist_ok=False);TEXT.mkdir(parents=True,exist_ok=True)
BASE='https://ppsmaroc.com/ar/wp-content/uploads/2016/10/'
NAMES={
 'fes-meknes':['fes_meknes.pdf'],
 'beni-mellal-khenifra':['beni_mellal_khenifra.pdf'],
 'rabat-sale-kenitra':['rabat-sale-kenitra.pdf'],
 'casablanca-settat':['casa_settat.pdf'],
 'marrakech-safi':['marrakech-safi.pdf'],
 'souss-massa':['souss_massa.pdf'],
 'oriental':['oriental.pdf'],
 'tanger-tetouan-al-hoceima':['tanger_tetouan_asilah.pdf'],
 'draa-tafilalet':['draa_tafilalet.pdf'],
 'guelmim-oued-noun':['guelmim_oued_noun.pdf'],
 'laayoune-sakia-el-hamra':['el_ayoun_sakia_hamra-1.pdf'],
 'dakhla-oued-ed-dahab':['dakhela_ouddahab.pdf'],
}
OUTCOME=('نتائج','فاز','الفائزون','المقاعد المحصل','النتائج النهائية')
S=requests.Session();S.headers.update({'User-Agent':'Atlas395-EReason-PPSRegionalPDFProbe/2.0','Accept':'application/pdf,*/*'})
def qualified():
 d=json.loads(REG.read_text(encoding='utf-8'));return any(x.get('domain')=='ppsmaroc.com' and x.get('source_class')=='T1_OFFICIAL_PARTY' and x.get('qualification_status')=='QUALIFIED_BEFORE_EXTRACTION' for x in d.get('entries',[]))
def get(u):
 last=None
 for i in range(4):
  try:
   r=S.get(u,timeout=(7,45),allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}:return r
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as e:last=e
  time.sleep(min(6,2**i))
 if last:raise last
 return r
def main():
 if not qualified():raise RuntimeError('ppsmaroc.com not pre-qualified')
 rows=[]
 for region,names in NAMES.items():
  for name in names:
   u=BASE+name;rec={'region_slug':region,'filename':name,'url':u,'status':None,'final_url':None,'bytes':0,'content_type':None,'sha256':None,'pdf':None,'error':None,'discovery_only':True}
   try:
    r=get(u);b=r.content;rec.update(status=r.status_code,final_url=str(r.url),bytes=len(b),content_type=r.headers.get('content-type'))
    if r.ok and b.startswith(b'%PDF'):
     h=hashlib.sha256(b).hexdigest();p=RAW/(h+'.pdf');p.write_bytes(b);reader=PdfReader(BytesIO(b));pages=[p.extract_text() or '' for p in reader.pages];text='\n'.join(pages);tp=TEXT/(h+'.txt');tp.write_text(text,encoding='utf-8');rec.update(sha256=h,pdf={'pages':len(reader.pages),'metadata':{str(k):str(v) for k,v in (reader.metadata or {}).items()},'raw_path':str(p.relative_to(ROOT)),'text_path':str(tp.relative_to(ROOT)),'text_chars':len(text),'outcome_terms':[x for x in OUTCOME if x in text]})
   except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
   rows.append(rec);time.sleep(.05)
 hits=[x for x in rows if x['pdf']]
 payload={'schema_version':'2.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_class':'T1_OFFICIAL_PARTY','qualified_domain':'ppsmaroc.com','method':'EXACT_FILENAMES_FROM_PRE_CUTOFF_OFFICIAL_PPS_REGION_PAGES','rows':rows,'pdf_hits':hits,'counts':{'attempts':len(rows),'pdf_hits':len(hits),'regions_with_pdf':len({x['region_slug'] for x in hits})},'invariants':{'candidate_facts_extracted':False,'evidence_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 (OUT/'probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(ER/'pps_2016_regional_pdf_probe_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_probe':str((OUT/'probe.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'hits':[{'region':x['region_slug'],'url':x['url'],'bytes':x['bytes'],'pages':x['pdf']['pages'],'metadata':x['pdf']['metadata']} for x in hits]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
