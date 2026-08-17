#!/usr/bin/env python3
from __future__ import annotations
import hashlib,json,os,time
from datetime import datetime,timezone
from pathlib import Path
from io import BytesIO
import requests
from pypdf import PdfReader
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
RID=os.environ.get('E_REASON_PJD_SERIES_RUN_ID') or 'pjd_series_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/pjd_2016_pdf_series_probe'/RID; RAW=OUT/'raw'; RAW.mkdir(parents=True,exist_ok=False)
S=requests.Session(); S.headers['User-Agent']='Atlas395-EReason-PJDSeriesProbe/1.0'
# Deterministic neighbors of already-proven ldf_3.pdf in the same migration bucket.
names=[]
for n in (1,2,4,5):
    names += [f'ldf_{n}.pdf',f'ldf_{n}_0.pdf',f'ldf{n}.pdf']
rows=[]
for month in ('04','05','06'):
  for name in names:
    u=f'https://www.pjd.ma/static/uploads/2022/{month}/{name}'
    rec={'url':u,'status':None,'bytes':0,'content_type':None,'sha256':None,'pdf_metadata':None,'pages':None,'text_sample':None,'error':None,'discovery_only':True}
    try:
      r=S.get(u,timeout=(6,20),allow_redirects=True); rec.update(status=r.status_code,bytes=len(r.content),content_type=r.headers.get('content-type'))
      if r.ok and r.content.startswith(b'%PDF'):
        rec['sha256']=hashlib.sha256(r.content).hexdigest(); (RAW/f"{rec['sha256']}.pdf").write_bytes(r.content)
        reader=PdfReader(BytesIO(r.content)); rec['pages']=len(reader.pages); rec['pdf_metadata']={str(k):str(v) for k,v in (reader.metadata or {}).items()}
        rec['text_sample']=' '.join((reader.pages[0].extract_text() or '').split())[:1200]
    except Exception as exc: rec['error']=f'{type(exc).__name__}: {exc}'
    rows.append(rec); time.sleep(.05)
hits=[x for x in rows if x['sha256']]
payload={'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'method':'DETERMINISTIC_FILENAME_NEIGHBORS_OF_PROVEN_LDF_3_ONLY','rows':rows,'pdf_hits':hits,'pdf_hit_count':len(hits),'predictive_judgments_generated':False,'outcomes_unsealed':False,'F1_created':False}
(OUT/'probe.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ER/'pjd_2016_pdf_series_probe_latest.json').write_text(json.dumps({'latest_run_id':RID,'latest_probe':str((OUT/'probe.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'run_id':RID,'pdf_hit_count':len(hits),'hits':[{'url':x['url'],'bytes':x['bytes'],'metadata':x['pdf_metadata'],'sample':x['text_sample']} for x in hits]},ensure_ascii=False,indent=2))
