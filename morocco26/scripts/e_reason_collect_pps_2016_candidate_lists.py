#!/usr/bin/env python3
"""Recover PPS regional candidate-list PDFs from the pre-cutoff official archive."""
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
S=requests.Session(); S.headers.update({'User-Agent':'Atlas395-EReason-PPS2016/2.0','Accept':'*/*','Accept-Language':'ar,fr;q=0.8'})
CUTOFF=datetime(2016,10,6,22,59,59,tzinfo=timezone.utc)
CAT='https://pps.ma/category/%D9%85%D8%B1%D8%B4%D8%AD%D9%8A-%D8%AD%D8%B2%D8%A8-%D8%A7%D9%84%D8%AA%D9%82%D8%AF%D9%85-%D9%88-%D8%A7%D9%84%D8%A7%D8%B4%D8%AA%D8%B1%D8%A7%D9%83%D9%8A%D8%A9/'
DISCOVERY=[CAT,CAT+'page/2/?filter_by=featured','https://pps.ma/wp-json/wp/v2/posts?after=2016-10-02T00:00:00&before=2016-10-07T00:00:00&per_page=100','https://pps.ma/10462/','https://pps.ma/10487/','https://pps.ma/10453/','https://pps.ma/10446/']
REGIONS=['الداخلة وادي الذهب','العيون الساقية الحمراء','كلميم واد نون','سوس ماسة','درعة تافيلالت','مراكش آسفي','البيضاء سطات','بني ملال الخنيفرة','الرباط سلا القنيطرة','فاس مكناس','الشرق','طنجة تطوان الحسيمة']
OUTCOME=('نتائج انتخابات 7 أكتوبر','نواب حزب التقدم','فاز','النتائج النهائية','المقاعد المحصل')
ALLOWED={'pps.ma','ppsmaroc.com'}
def host(u):return (urlparse(u).hostname or '').lower().removeprefix('www.')
def qualified():
 d=json.loads(REG.read_text(encoding='utf-8'));q={x.get('domain') for x in d.get('entries',[]) if x.get('source_class')=='T1_OFFICIAL_PARTY' and x.get('qualification_status')=='QUALIFIED_BEFORE_EXTRACTION'};return ALLOWED<=q
def get(u,attempts=3,timeout=(6,25)):
 e=None
 for i in range(attempts):
  try:
   r=S.get(u,timeout=timeout,allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}:return r
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as x:e=x
  time.sleep(min(4,2**i))
 if e:raise e
 return r
def freeze(b,s):
 h=hashlib.sha256(b).hexdigest();p=RAW/(h+s);p.write_bytes(b);return h,str(p.relative_to(ROOT))
def clean(x):return ' '.join(BeautifulSoup(html.unescape(x or ''),'html.parser').get_text(' ',strip=True).split())
def urls(text,base):
 text=html.unescape((text or '').replace('\\/','/'));s=BeautifulSoup(text,'html.parser');out=set()
 for a in s.find_all(['a','img']):
  for k in ('href','src','data-src'):
   v=a.get(k)
   if v:out.add(urljoin(base,str(v)))
 return sorted(u for u in out if host(u) in ALLOWED)
def dates(text):
 out=[]
 for p in [r'"datePublished"\s*:\s*"([^"]+)"',r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',r'<time[^>]+datetime=["\']([^"\']+)["\']']:
  out += [m.group(1) for m in re.finditer(p,text,re.I)]
 return sorted(set(out))
def pre(d):
 try:
  x=datetime.fromisoformat(str(d).replace('Z','+00:00'));x=x if x.tzinfo else x.replace(tzinfo=timezone.utc);return x.astimezone(timezone.utc)<=CUTOFF
 except:return False
def pdf_info(body,h):
 r=PdfReader(BytesIO(body));text='\n'.join((p.extract_text() or '') for p in r.pages);tp=TEXT/(h+'.txt');tp.write_text(text,encoding='utf-8');return {'pages':len(r.pages),'metadata':{str(k):str(v) for k,v in (r.metadata or {}).items()},'text_path':str(tp.relative_to(ROOT)),'text_chars':len(text),'outcome_terms':[x for x in OUTCOME if x in text]}
def main():
 if not qualified():raise RuntimeError('PPS domains not pre-qualified')
 fetched=[];post_urls=set();rest_posts=[]
 for u in DISCOVERY:
  rec={'url':u,'status':None,'bytes':0,'error':None}
  try:
   r=get(u);b=r.content;t=b.decode('utf-8',errors='replace');h,p=freeze(b,'.json' if 'json' in (r.headers.get('content-type') or '').lower() else '.html');rec.update(status=r.status_code,bytes=len(b),sha256=h,path=p)
   if 'json' in (r.headers.get('content-type') or '').lower():
    try:
     data=r.json();data=data if isinstance(data,list) else [data]
     for o in data:
      if not isinstance(o,dict):continue
      title=clean((o.get('title') or {}).get('rendered',''));dt=o.get('date_gmt') or o.get('date');link=str(o.get('link') or '')
      if any(x in title for x in REGIONS) and pre(dt):post_urls.add(link);rest_posts.append({'id':o.get('id'),'title':title,'date':dt,'link':link,'content':(o.get('content') or {}).get('rendered','')})
    except Exception:pass
   else:
    for v in urls(t,str(r.url)):
     if host(v)=='pps.ma' and re.fullmatch(r'https?://(?:www\.)?pps\.ma/\d+/?',v):post_urls.add(v)
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  fetched.append(rec)
 # Known indexed region pages ensure discovery survives category/CDN challenges.
 post_urls.update(['https://pps.ma/10462/','https://pps.ma/10487/','https://pps.ma/10453/','https://pps.ma/10446/'])
 pages=[];assets={}
 for u in sorted(x for x in post_urls if x):
  rec={'url':u,'status':None,'dates':[],'title':None,'download_urls':[],'admissible_parent':False,'error':None}
  try:
   r=get(u);b=r.content;t=b.decode('utf-8',errors='replace');h,p=freeze(b,'.html');ds=dates(t);title=clean(BeautifulSoup(t,'html.parser').find('h1').get_text(' ',strip=True) if BeautifulSoup(t,'html.parser').find('h1') else '');links=[x for x in urls(t,str(r.url)) if host(x)=='ppsmaroc.com' and '.pdf' in x.lower()];rec.update(status=r.status_code,dates=ds,title=title,download_urls=links,sha256=h,path=p,admissible_parent=bool(ds and any(pre(x) for x in ds) and (title in REGIONS or any(x in title for x in REGIONS)))
   if rec['admissible_parent']:
    for x in links:assets.setdefault(x,[]).append({'page':u,'title':title,'dates':ds})
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  pages.append(rec)
 # REST-rendered content can expose downloads even if individual page is challenged.
 for o in rest_posts:
  for x in urls(o['content'],o['link']):
   if host(x)=='ppsmaroc.com' and '.pdf' in x.lower():assets.setdefault(x,[]).append({'page':o['link'],'title':o['title'],'dates':[o['date']]})
 docs=[]
 for u,parents in sorted(assets.items()):
  rec={'url':u,'parents':parents,'status':None,'bytes':0,'sha256':None,'pdf':None,'admissible_candidate_evidence':False,'error':None}
  try:
   r=get(u,attempts=4,timeout=(8,45));b=r.content;h,p=freeze(b,'.pdf' if b.startswith(b'%PDF') else '.bin');rec.update(status=r.status_code,bytes=len(b),sha256=h,path=p)
   if r.ok and b.startswith(b'%PDF'):
    rec['pdf']=pdf_info(b,h);rec['admissible_candidate_evidence']=not rec['pdf']['outcome_terms']
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  docs.append(rec)
 payload={'schema_version':'2.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'source_class':'T1_OFFICIAL_PARTY','qualified_domains':sorted(ALLOWED),'discovery_fetches':fetched,'candidate_pages':pages,'documents':docs,'counts':{'candidate_page_urls':len(post_urls),'admissible_candidate_pages':sum(x['admissible_parent'] for x in pages),'pdf_urls':len(assets),'pdf_documents':sum(bool(x['pdf']) for x in docs),'admissible_pdf_documents':sum(x['admissible_candidate_evidence'] for x in docs)},'invariants':{'outcomes_unsealed':False,'predictive_judgments_generated':False,'forecast_delta_generated':False,'F1_created':False}}
 (OUT/'run_manifest.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(ER/'pps_2016_candidate_lists_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_manifest':str((OUT/'run_manifest.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8');print(json.dumps({'run_id':RID,'counts':payload['counts'],'documents':[{'url':x['url'],'bytes':x['bytes'],'pages':(x.get('pdf') or {}).get('pages'),'admissible':x['admissible_candidate_evidence']} for x in docs]},ensure_ascii=False,indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
