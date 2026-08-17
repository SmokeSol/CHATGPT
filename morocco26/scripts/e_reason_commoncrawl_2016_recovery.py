#!/usr/bin/env python3
"""Recover pre-cutoff 2016 Médias24 maps from Common Crawl.

The Common Crawl capture timestamp is the admissibility timestamp. Records
captured after 2016-10-06 22:59:59 UTC are excluded.
"""
from __future__ import annotations
import gzip, hashlib, io, json, os, re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import requests

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
RID=os.environ.get('E_REASON_CC_RUN_ID') or 'commoncrawl2016_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/commoncrawl_2016'/RID
RAW=OUT/'raw'; RAW.mkdir(parents=True,exist_ok=False)
CUTOFF='20161006225959'
ARTICLE='medias24.com/2016/10/03/legislatives-les-principaux-candidats-circonscription-par-circonscription-17-cartes/'
QUERIES=[ARTICLE,'www.'+ARTICLE,'assets.medias24.com/js/carte/*','medias24.com/*17-cartes*','www.medias24.com/*17-cartes*']
S=requests.Session(); S.headers['User-Agent']='Atlas395-EReason-CommonCrawl/1.0'


def index_rows(api: str, query: str) -> tuple[list[dict[str,Any]],dict[str,Any]]:
    params={'url':query,'output':'json','filter':'status:200','collapse':'digest'}
    diag={'api':api,'query':query,'status':None,'bytes':0,'rows':0,'error':None}
    rows=[]
    try:
        r=S.get(api,params=params,timeout=(7,35)); diag.update(status=r.status_code,bytes=len(r.content)); r.raise_for_status()
        for line in r.text.splitlines():
            if not line.strip(): continue
            try:
                row=json.loads(line)
                if row.get('timestamp','')<=CUTOFF:
                    rows.append(row)
            except json.JSONDecodeError: pass
        diag['rows']=len(rows)
    except Exception as exc: diag['error']=f'{type(exc).__name__}: {exc}'
    return rows,diag


def retrieve(row: dict[str,Any]) -> tuple[bytes,str]:
    start=int(row['offset']); length=int(row['length'])
    url='https://data.commoncrawl.org/'+row['filename']
    r=S.get(url,headers={'Range':f'bytes={start}-{start+length-1}'},timeout=(10,55)); r.raise_for_status()
    raw=r.content
    try: payload=gzip.GzipFile(fileobj=io.BytesIO(raw)).read()
    except OSError: payload=raw
    # Strip WARC headers then HTTP headers, preserving body.
    _,_,rest=payload.partition(b'\r\n\r\n')
    if rest.startswith(b'HTTP/'):
        _,_,body=rest.partition(b'\r\n\r\n')
    else: body=rest
    return body,url


def main() -> int:
    colls=S.get('https://index.commoncrawl.org/collinfo.json',timeout=(7,25)).json()
    selected=[x for x in colls if x.get('id','').startswith('CC-MAIN-2016')]
    selected.sort(key=lambda x:x['id'],reverse=True)
    allrows={}; diagnostics=[]
    for coll in selected:
        api=coll['cdx-api']
        for query in QUERIES:
            rows,diag=index_rows(api,query); diagnostics.append(diag)
            for row in rows:
                key=(row.get('url'),row.get('timestamp'),row.get('digest'))
                allrows[key]=row
    catalog=sorted(allrows.values(),key=lambda x:(x.get('timestamp',''),x.get('url','')))
    (OUT/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    recovered=[]; assets=set()
    likely=[]
    for row in catalog:
        u=row.get('url',''); low=u.lower()
        if ('17-cartes' in low or 'principaux-candidats' in low or ('assets.medias24.com/js/carte/' in low and low.endswith(('.html','.htm','/')))):
            likely.append(row)
    for row in likely[:300]:
        rec={'url':row.get('url'),'timestamp':row.get('timestamp'),'mime':row.get('mime'),'status':row.get('status'),'filename':row.get('filename'),'offset':row.get('offset'),'length':row.get('length'),'sha256':None,'bytes':0,'path':None,'asset_urls':[],'error':None}
        try:
            body,_=retrieve(row); rec['bytes']=len(body); rec['sha256']=hashlib.sha256(body).hexdigest()
            suffix=Path(row.get('url','')).suffix.lower()
            if suffix not in {'.html','.htm','.json','.js','.css','.csv','.xml','.txt'}: suffix='.html'
            path=RAW/(rec['sha256']+suffix); path.write_bytes(body); rec['path']=str(path.relative_to(ROOT))
            text=body.decode('utf-8',errors='replace')
            for m in re.finditer(r'https?://assets\.medias24\.com/[^\s"\'<>]+',text):
                a=m.group(0).rstrip(')],.;'); assets.add(a); rec['asset_urls'].append(a)
            for m in re.finditer(r'(?:src|data-src|data-lazy-src)=["\']([^"\']+)["\']',text,re.I):
                a=m.group(1)
                if 'assets.medias24.com' in a: assets.add(a); rec['asset_urls'].append(a)
        except Exception as exc: rec['error']=f'{type(exc).__name__}: {exc}'
        recovered.append(rec)
    manifest={'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'cutoff_utc':CUTOFF,'commoncrawl_collections':[x['id'] for x in selected],'catalog_rows':len(catalog),'likely_records':len(likely),'recovered_records':recovered,'discovered_asset_urls':sorted(assets),'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False,'Atlas_UI_modified':False}
    (OUT/'run_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ER/'commoncrawl_2016_latest.json').write_text(json.dumps({'latest_run_id':RID,'latest_manifest':str((OUT/'run_manifest.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'run_id':RID,'collections':len(selected),'catalog_rows':len(catalog),'likely_records':len(likely),'discovered_asset_urls':sorted(assets)},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
