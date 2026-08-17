#!/usr/bin/env python3
"""Recover official PPS candidate-list documents published before 7 Oct 2016.

Both pps.ma and its legacy official download domain ppsmaroc.com must be
pre-qualified as T1_OFFICIAL_PARTY before this script runs. Discovery is
bounded to the PPS candidate category and 2-6 Oct 2016 publication window.
Post-election pages are excluded by construction.
"""
from __future__ import annotations

import hashlib,html,json,os,re,time
from datetime import datetime,timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'; REG=ER/'e_reason_source_registry_v1.json'
RID=os.environ.get('E_REASON_PPS2016_RUN_ID') or 'pps2016_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/pps_2016_candidate_lists'/RID; RAW=OUT/'raw'; TEXT=OUT/'text'; RAW.mkdir(parents=True,exist_ok=False); TEXT.mkdir(parents=True,exist_ok=True)
S=requests.Session(); S.headers.update({'User-Agent':'Atlas395-EReason-PPS2016/1.2','Accept':'*/*','Accept-Language':'ar,fr;q=0.8,en;q=0.5'})
CUTOFF=datetime(2016,10,6,22,59,59,tzinfo=timezone.utc)
CATEGORY='https://pps.ma/category/%D9%85%D8%B1%D8%B4%D8%AD%D9%8A-%D8%AD%D8%B2%D8%A8-%D8%A7%D9%84%D8%AA%D9%82%D8%AF%D9%85-%D9%88-%D8%A7%D9%84%D8%A7%D8%B4%D8%AA%D8%B1%D8%A7%D9%83%D9%8A%D8%A9/'
SEEDS=[CATEGORY,CATEGORY+'page/2/?filter_by=featured',CATEGORY+'feed/','https://pps.ma/wp-json/wp/v2/posts?after=2016-10-02T00:00:00&before=2016-10-07T00:00:00&per_page=100','https://pps.ma/10462/','https://pps.ma/10487/','https://pps.ma/10453/','https://pps.ma/10446/']
REGIONS=['الداخلة وادي الذهب','العيون الساقية الحمراء','كلميم واد نون','سوس ماسة','درعة تافيلالت','مراكش آسفي','البيضاء سطات','بني ملال الخنيفرة','الرباط سلا القنيطرة','فاس مكناس','الشرق','طنجة تطوان الحسيمة']
PRE_TERMS=('7 أكتوبر 2016','7 اكتوبر 2016','الانتخابات التشريعية','مرشحي حزب التقدم','مرشحو حزب التقدم','حمل اللائحة','مرشح')
OUTCOME_TERMS=('نتائج انتخابات 7 أكتوبر','نواب حزب التقدم','فاز','النتائج النهائية','المقاعد المحصل')
STATIC_SUFFIXES=('.pdf','.jpg','.jpeg','.png','.webp','.doc','.docx','.xls','.xlsx')
ALLOWED_HOSTS={'pps.ma','ppsmaroc.com'}

def host(u): return (urlparse(u).hostname or '').lower().removeprefix('www.')
def qualified():
 d=json.loads(REG.read_text(encoding='utf-8')); ok={x.get('domain') for x in d.get('entries',[]) if x.get('source_class')=='T1_OFFICIAL_PARTY' and x.get('qualification_status')=='QUALIFIED_BEFORE_EXTRACTION'}; return {'pps.ma','ppsmaroc.com'}<=ok
def get(url,attempts=4,timeout=(7,35)):
 last=None
 for i in range(attempts):
  try:
   r=S.get(url,timeout=timeout,allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}: return r
   last=requests.HTTPError(str(r.status_code))
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as e:last=e
  if i+1<attempts:time.sleep(min(8,2**i))
 if last:raise last
 raise RuntimeError('request failed')
def freeze(body,suffix):
 h=hashlib.sha256(body).hexdigest(); p=RAW/(h+suffix); p.write_bytes(body); return h,str(p.relative_to(ROOT))
def clean_text(raw): return ' '.join(BeautifulSoup(html.unescape(raw or ''),'html.parser').get_text(' ',strip=True).split())
def parse_dt(value):
 if not value:return None
 try:
  dt=datetime.fromisoformat(str(value).replace('Z','+00:00'))
  if dt.tzinfo is None:dt=dt.replace(tzinfo=timezone.utc)
  return dt.astimezone(timezone.utc)
 except Exception:return None
def page_dates(text):
 vals=[]
 for pat in [r'"datePublished"\s*:\s*"([^"]+)"',r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',r'<time[^>]+datetime=["\']([^"\']+)["\']']:
  vals.extend(m.group(1) for m in re.finditer(pat,text,re.I))
 return sorted(set(vals))
def extract_urls(text,base):
 text=html.unescape(text.replace('\\/','/')); soup=BeautifulSoup(text,'html.parser'); out=set()
 for node in soup.find_all(['a','img','source']):
  for attr in ('href','src','data-src'):
   v=node.get(attr)
   if v:out.add(urljoin(base,str(v)))
 for m in re.finditer(r'https?://[^\s\"\'<>]+',text):out.add(m.group(0).rstrip(')],.;'))
 return sorted(u for u in out if host(u) in ALLOWED_HOSTS)
def is_candidate_context(text):
 t=clean_text(text); return any(x in t for x in PRE_TERMS) and not any(x in t for x in OUTCOME_TERMS)
def inspect_pdf(body,h):
 reader=PdfReader(BytesIO(body)); pages=[f'--- PAGE {i+1} ---\n'+(p.extract_text() or '') for i,p in enumerate(reader.pages)]; text='\n'.join(pages); tp=TEXT/(h+'.txt'); tp.write_text(text,encoding='utf-8'); meta={str(k):str(v) for k,v in (reader.metadata or {}).items()}; return {'pages':len(reader.pages),'metadata':meta,'text_path':str(tp.relative_to(ROOT)),'text_chars':len(text),'pre_terms':[x for x in PRE_TERMS if x in text],'outcome_terms':[x for x in OUTCOME_TERMS if x in text]}

def main():
 if not qualified():raise RuntimeError('pps.ma and ppsmaroc.com must both be T1-qualified before extraction')
 fetches=[]; discovered=set(); candidate_pages={}; queue=list(SEEDS); seen=set()
 while queue and len(seen)<120:
  u=queue.pop(0)
  if u in seen:continue
  seen.add(u); rec={'url':u,'status':None,'bytes':0,'content_type':None,'sha256':None,'path':None,'dates':[],'candidate_context':False,'links':[],'error':None,'current_response_is_candidate_evidence':False}
  try:
   r=get(u); body=r.content; ct=(r.headers.get('content-type') or '').lower(); suffix='.json' if 'json' in ct else '.html'; h,p=freeze(body,suffix); text=body.decode('utf-8',errors='replace'); links=extract_urls(text,str(r.url)); rec.update(status=r.status_code,bytes=len(body),content_type=ct,sha256=h,path=p,dates=page_dates(text),candidate_context=is_candidate_context(text),links=links)
   for v in links:
    if v.lower().split('?',1)[0].endswith(STATIC_SUFFIXES): discovered.add(v)
    elif host(v)=='pps.ma' and v not in seen and (('/104' in v) or ('2016' in v.lower()) or any(reg in clean_text(text) for reg in REGIONS)): queue.append(v)
   if 'json' in ct:
    try:
     data=r.json(); objs=data if isinstance(data,list) else [data]
     for o in objs:
      if not isinstance(o,dict):continue
      dt=parse_dt(o.get('date_gmt') or o.get('date')); title=clean_text((o.get('title') or {}).get('rendered','')); content=(o.get('content') or {}).get('rendered',''); link=o.get('link')
      if dt and datetime(2016,10,2,tzinfo=timezone.utc)<=dt<=CUTOFF and (any(x in title for x in REGIONS) or is_candidate_context(content)):
       urls=extract_urls(content,str(link or u)); candidate_pages[str(link or u)+'#'+str(o.get('id'))]={'post_id':o.get('id'),'date':dt.isoformat(),'title':title,'link':link,'urls':urls}; discovered.update(x for x in urls if x.lower().split('?',1)[0].endswith(STATIC_SUFFIXES))
    except Exception:pass
   if host(u)=='pps.ma' and rec['candidate_context'] and rec['dates'] and any((parse_dt(x) and parse_dt(x)<=CUTOFF) for x in rec['dates']): candidate_pages[u]={'date_candidates':rec['dates'],'title':clean_text(text)[:200],'link':u,'urls':links}
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  fetches.append(rec)
 static=[]
 for u in sorted(discovered):
  rec={'url':u,'host':host(u),'status':None,'bytes':0,'content_type':None,'sha256':None,'path':None,'pdf':None,'error':None,'source_class':'T1_OFFICIAL_PARTY','transport':'CURRENT_FIRST_PARTY_STATIC_DISCOVERY'}
  try:
   r=get(u,attempts=3,timeout=(7,50)); body=r.content; ct=(r.headers.get('content-type') or '').lower(); ext=Path(urlparse(str(r.url)).path).suffix.lower() or '.bin'; ext=ext if len(ext)<=8 else '.bin'; h,p=freeze(body,ext); rec.update(status=r.status_code,bytes=len(body),content_type=ct,sha256=h,path=p)
   if r.ok and body.startswith(b'%PDF'):rec['pdf']=inspect_pdf(body,h)
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  static.append(rec)
 for s in static:
  parents=[]
  for key,p in candidate_pages.items():
   if s['url'] in p.get('urls',[]):parents.append({'page_key':key,'date':p.get('date') or p.get('date_candidates'),'title':p.get('title'),'link':p.get('link')})
  s['precutoff_candidate_page_parents']=parents; pdf=s.get('pdf') or {}; s['admissible_candidate_evidence']=bool(parents and s.get('status')==200 and not pdf.get('outcome_terms'))
 payload={'schema_version':'1.2','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'cutoff_utc':CUTOFF.isoformat(),'source_class':'T1_OFFICIAL_PARTY','qualified_domains':sorted(ALLOWED_HOSTS),'fetches':fetches,'candidate_pages':candidate_pages,'static_assets':static,'counts':{'fetches':len(fetches),'candidate_pages':len(candidate_pages),'static_assets':len(static),'pdf_assets':sum(bool(x.get('pdf')) for x in static),'admissible_static_assets':sum(bool(x.get('admissible_candidate_evidence')) for x in static)},'invariants':{'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 (OUT/'run_manifest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); (ER/'pps_2016_candidate_lists_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_manifest':str((OUT/'run_manifest.json').relative_to(ROOT))},ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'run_id':RID,'counts':payload['counts'],'assets':[{'url':x['url'],'bytes':x['bytes'],'pages':(x.get('pdf') or {}).get('pages'),'parents':x['precutoff_candidate_page_parents'],'admissible':x['admissible_candidate_evidence']} for x in static]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
