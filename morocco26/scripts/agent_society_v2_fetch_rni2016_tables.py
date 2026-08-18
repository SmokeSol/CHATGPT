#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'goal100'/'agent_society_v2'/'acquisition'/'rni2016_tables'
OUT.mkdir(parents=True,exist_ok=True)
URLS=[
 'https://medias24.com/content/uploads/2016/09/rni_candidats_tableaux_1.jpg',
 'https://medias24.com/content/uploads/2016/09/rni_tableaux_candidats_2.jpg',
]
def main():
    sess=requests.Session();sess.headers.update({'User-Agent':'Atlas395-ASV2/1.0','Referer':'https://medias24.com/2016/09/04/legislatives-le-rni-devoile-81-tetes-de-liste/','Accept':'image/avif,image/webp,image/apng,image/*,*/*;q=0.8'})
    rec=[]
    for i,u in enumerate(URLS,1):
        r=sess.get(u,timeout=(20,90),allow_redirects=True)
        b=r.content
        p=OUT/f'rni2016_table_{i}.jpg'
        if r.status_code==200 and len(b)>1000:
            p.write_bytes(b)
        rec.append({'url':u,'final_url':r.url,'status_code':r.status_code,'content_type':r.headers.get('content-type'),'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'saved_path':str(p.relative_to(ROOT)) if p.exists() else None})
    manifest={'schema_version':'1.0','acquisition_id':'M26-ASV2-RNI2016-TABLE-FETCH-V1','retrieved_at':datetime.now(timezone.utc).isoformat(),'source_article':'https://medias24.com/2016/09/04/legislatives-le-rni-devoile-81-tetes-de-liste/','source_article_date':'2016-09-04','target_outcome_used':False,'records':rec,'status':'PASS' if all(x['saved_path'] for x in rec) else 'FAIL'}
    (OUT/'fetch_manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(manifest,ensure_ascii=False,indent=2))
    if manifest['status']!='PASS': raise SystemExit('RNI table image fetch failed')
if __name__=='__main__': main()
