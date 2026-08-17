#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
RUN_ID=os.environ.get('E_REASON_IFRAME_RUN_ID') or 'iframe_discovery_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/iframe_discovery'/RUN_ID
OUT.mkdir(parents=True,exist_ok=False)
base='https://medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/'
variants=[base,base+'amp/',base+'?amp=1',base+'?output=1',base+'?no_cache=1','https://preprod.medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/']
headersets=[
 {'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/126 Safari/537.36','Accept-Language':'fr-FR,fr;q=0.9'},
 {'User-Agent':'Googlebot/2.1 (+http://www.google.com/bot.html)'},
 {'User-Agent':'bingbot/2.0 (+http://www.bing.com/bingbot.htm)'},
]
rows=[]; found=set()
for url in variants:
 for hi,headers in enumerate(headersets):
  row={'url':url,'header_set':hi,'status':None,'bytes':0,'final_url':None,'sha256':None,'iframes':[],'asset_urls':[],'error':None}
  try:
   r=requests.get(url,headers=headers,timeout=(6,20),allow_redirects=True)
   row.update(status=r.status_code,bytes=len(r.content),final_url=str(r.url),sha256=hashlib.sha256(r.content).hexdigest())
   if r.content:
    (OUT/f"{row['sha256']}.html").write_bytes(r.content)
    text=r.text
    soup=BeautifulSoup(text,'html.parser')
    for x in soup.find_all('iframe'):
     src=x.get('src') or x.get('data-src') or x.get('data-lazy-src')
     if src:
      src=urljoin(str(r.url),src); row['iframes'].append(src); found.add(src)
    for m in re.finditer(r'https?://assets\.medias24\.com/[^\s"\'<>]+',text):
     asset=m.group(0).rstrip(')],.;'); row['asset_urls'].append(asset); found.add(asset)
  except Exception as exc: row['error']=f'{type(exc).__name__}: {exc}'
  rows.append(row)
manifest={'schema_version':'1.0','run_id':RUN_ID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'rows':rows,'discovered_urls':sorted(found),'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}
(OUT/'discovery.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
(ER/'iframe_discovery_latest.json').write_text(json.dumps({'latest_run_id':RUN_ID,'latest_manifest':str((OUT/'discovery.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8')
print(json.dumps({'run_id':RUN_ID,'attempts':len(rows),'discovered_urls':sorted(found)},ensure_ascii=False,indent=2))
