#!/usr/bin/env python3
"""Recover the two versioned Médias24 RNI candidate-table images from Sep 2016.

The frozen source policy explicitly permits a versioned static asset when a
live historical page was later modified. The article was published 2016-09-04
and today still links two assets whose immutable upload paths are versioned
/content/uploads/2016/09/*. The article itself is provenance/discovery only;
only the static image bytes are candidate evidence inputs. OCR is diagnostic at
this stage and promotes no identity.
"""
from __future__ import annotations
import hashlib,json,os,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlparse
import requests
from bs4 import BeautifulSoup
from PIL import Image
import pytesseract
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';POL=ER/'e_reason_source_policy_v1.json'
RID=os.environ.get('E_REASON_M24_RNI_RUN_ID') or 'm24_rni_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/m24_rni_2016_static_tables'/RID;RAW=OUT/'raw';TEXT=OUT/'ocr';RAW.mkdir(parents=True,exist_ok=False);TEXT.mkdir(parents=True,exist_ok=True)
ARTICLE='https://medias24.com/2016/09/04/legislatives-le-rni-devoile-81-tetes-de-liste/'
EXPECTED=['rni_candidats_tableaux_1.jpg','rni_tableaux_candidats_2.jpg']
CUTOFF=datetime(2016,10,6,22,59,59,tzinfo=timezone.utc)
S=requests.Session();S.headers.update({'User-Agent':'Atlas395-EReason-M24RNIStatic/1.0','Accept':'text/html,image/*,*/*','Accept-Language':'fr,en;q=0.8'})
def get(u,attempts=4,timeout=(7,45)):
 last=None
 for i in range(attempts):
  try:
   r=S.get(u,timeout=timeout,allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}:return r
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as e:last=e
  time.sleep(min(6,2**i))
 if last:raise last
 return r
def sha(b):return hashlib.sha256(b).hexdigest()
def page_dates(text):
 pub=[];mod=[]
 for pat in [r'"datePublished"\s*:\s*"([^"]+)"',r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)']:
  pub += [m.group(1) for m in re.finditer(pat,text,re.I)]
 for pat in [r'"dateModified"\s*:\s*"([^"]+)"',r'property=["\']article:modified_time["\'][^>]*content=["\']([^"\']+)']:
  mod += [m.group(1) for m in re.finditer(pat,text,re.I)]
 return sorted(set(pub)),sorted(set(mod))
def dt(x):
 try:
  v=datetime.fromisoformat(str(x).replace('Z','+00:00'));return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
 except:return None
def main():
 pol=json.loads(POL.read_text(encoding='utf-8'))
 if 'M24_MEDIAS24' not in pol.get('allowed_source_classes',[]):raise RuntimeError('M24 source class not allowed')
 if 'versioned static asset' not in pol.get('historical_article_update_rule',''):raise RuntimeError('frozen policy lacks versioned-static route')
 ar=get(ARTICLE);ar.raise_for_status();html=ar.text;pub,mod=page_dates(html);soup=BeautifulSoup(html,'html.parser');urls=[]
 for node in soup.find_all(['img','a']):
  for attr in ('src','href','data-src','data-lazy-src'):
   v=node.get(attr)
   if not v:continue
   if any(x in str(v) for x in EXPECTED):urls.append(str(v).replace('http://','https://'))
 # HTML parsers/CDN transforms can omit lazy attributes; exact asset URLs are
 # independently exposed by the article link graph and are deterministic.
 for name in EXPECTED:
  u=f'https://medias24.com/content/uploads/2016/09/{name}'
  if u not in urls:urls.append(u)
 assets=[]
 for name in EXPECTED:
  candidates=[u for u in urls if name in u];u=candidates[0] if candidates else f'https://medias24.com/content/uploads/2016/09/{name}'
  rec={'filename':name,'url':u,'status':None,'final_url':None,'bytes':0,'sha256':None,'raw_path':None,'width':None,'height':None,'ocr_path':None,'ocr_chars':0,'error':None,'candidate_identity_promoted':False}
  try:
   r=get(u);b=r.content;rec.update(status=r.status_code,final_url=str(r.url),bytes=len(b));r.raise_for_status()
   if not b.startswith((b'\xff\xd8\xff',b'\x89PNG')):raise RuntimeError('static asset is not an image')
   h=sha(b);p=RAW/(h+'.jpg');p.write_bytes(b);im=Image.open(p);rec.update(sha256=h,raw_path=str(p.relative_to(ROOT)),width=im.width,height=im.height)
   # OCR is used only because the admissible source is an image table; preserve
   # full text + TSV confidence diagnostics. No identity is promoted here.
   text=pytesseract.image_to_string(im,lang='fra+eng',config='--psm 6')
   tp=TEXT/(h+'.txt');tp.write_text(text,encoding='utf-8');tsv=pytesseract.image_to_data(im,lang='fra+eng',config='--psm 6',output_type=pytesseract.Output.DICT)
   rows=[]
   for i,t in enumerate(tsv.get('text',[])):
    if str(t).strip():rows.append({'text':str(t),'conf':str(tsv['conf'][i]),'left':int(tsv['left'][i]),'top':int(tsv['top'][i]),'width':int(tsv['width'][i]),'height':int(tsv['height'][i])})
   jp=TEXT/(h+'.tsv.json');jp.write_text(json.dumps(rows,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');rec.update(ocr_path=str(tp.relative_to(ROOT)),ocr_tsv_path=str(jp.relative_to(ROOT)),ocr_chars=len(text))
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  assets.append(rec)
 prepub=any(dt(x) and dt(x)<=CUTOFF for x in pub)
 payload={'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_class':'M24_MEDIAS24','article_url':ARTICLE,'article_publication_dates':pub,'article_modified_dates':mod,'article_published_pre_cutoff':prepub,'article_current_body_used_as_candidate_evidence':False,'versioned_static_rule':pol['historical_article_update_rule'],'expected_asset_filenames':EXPECTED,'linked_or_deterministic_static_urls':urls,'assets':assets,'counts':{'assets_expected':2,'assets_recovered':sum(bool(x['sha256']) for x in assets),'assets_with_ocr':sum(bool(x['ocr_path']) for x in assets)},'status':'STATIC_ASSETS_RECOVERED_DIAGNOSTIC_ONLY' if sum(bool(x['sha256']) for x in assets)==2 else 'FAIL_CLOSED','invariants':{'postcutoff_article_body_not_used_for_candidate_fact':True,'static_asset_path_versioned_2016_09':all('/2016/09/' in x['url'] for x in assets),'candidate_identities_promoted':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 (OUT/'manifest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(ER/'m24_rni_2016_static_tables_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_manifest':str((OUT/'manifest.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'counts':payload['counts'],'publication_dates':pub,'modified_dates':mod,'assets':[{'filename':x['filename'],'status':x['status'],'bytes':x['bytes'],'sha256':x['sha256'],'size':[x['width'],x['height']],'ocr_chars':x['ocr_chars'],'error':x['error']} for x in assets]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
