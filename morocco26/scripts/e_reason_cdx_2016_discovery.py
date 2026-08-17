#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
RID=os.environ.get('E_REASON_CDX2016_RUN_ID') or 'cdx2016_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/cdx_2016_discovery'/RID
OUT.mkdir(parents=True,exist_ok=False)
s=requests.Session(); s.headers['User-Agent']='Atlas395-EReason-CDX2016/1.0'
queries=[
 {'url':'medias24.com/2016/10/03/*'},
 {'url':'www.medias24.com/2016/10/03/*'},
 {'url':'medias24.com/*legislatives-les-principaux-candidats*'},
 {'url':'www.medias24.com/*legislatives-les-principaux-candidats*'},
 {'url':'assets.medias24.com/js/carte/*'},
 {'url':'assets.medias24.com/js/*election*'},
]
rows=[]; candidates={}
for q in queries:
 params={**q,'output':'json','fl':'timestamp,original,statuscode,mimetype,digest','filter':'statuscode:200','from':'2016','to':'2016','limit':'5000','collapse':'urlkey'}
 diag={'params':params,'status':None,'bytes':0,'count':0,'error':None}
 try:
  r=s.get('https://web.archive.org/cdx/search/cdx',params=params,timeout=(6,30)); diag.update(status=r.status_code,bytes=len(r.content)); r.raise_for_status(); data=r.json()
  if data and len(data)>1:
   h=data[0]
   for x in data[1:]:
    item=dict(zip(h,x)); diag['count']+=1
    if item.get('timestamp','')<='20161006225959':
     old=candidates.get(item['original'])
     if old is None or item['timestamp']>old['timestamp']: candidates[item['original']]=item
 except Exception as exc: diag['error']=f'{type(exc).__name__}: {exc}'
 rows.append(diag)
# Fetch likely article snapshots and discover embedded assets.
discovered=set(); fetched=[]
for item in list(candidates.values()):
 u=item['original']; low=u.lower()
 if 'principaux-candidats' not in low and '17-cartes' not in low: continue
 archive=f"https://web.archive.org/web/{item['timestamp']}id_/{u}"
 try:
  r=s.get(archive,timeout=(6,25),allow_redirects=True); body=r.content
  rec={'original':u,'timestamp':item['timestamp'],'archive_url':archive,'status':r.status_code,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest() if body else None,'assets':[],'error':None}
  if r.ok and body:
   (OUT/(rec['sha256']+'.html')).write_bytes(body)
   text=body.decode('utf-8',errors='replace')
   for m in re.finditer(r'https?://assets\.medias24\.com/[^\s"\'<>]+',text):
    a=m.group(0).rstrip(')],.;'); rec['assets'].append(a); discovered.add(a)
   for m in re.finditer(r'(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',text,re.I):
    a=m.group(1)
    if 'assets.medias24.com' in a: rec['assets'].append(a); discovered.add(a)
  fetched.append(rec)
 except Exception as exc: fetched.append({'original':u,'timestamp':item['timestamp'],'error':f'{type(exc).__name__}: {exc}'})
manifest={'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'query_diagnostics':rows,'catalog_count':len(candidates),'candidate_catalog':sorted(candidates.values(),key=lambda x:x['original']),'fetched_articles':fetched,'discovered_asset_urls':sorted(discovered),'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}
(OUT/'discovery.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ER/'cdx_2016_discovery_latest.json').write_text(json.dumps({'latest_run_id':RID,'latest_manifest':str((OUT/'discovery.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'run_id':RID,'catalog_count':len(candidates),'discovered_asset_urls':sorted(discovered),'query_diagnostics':rows},ensure_ascii=False,indent=2))
