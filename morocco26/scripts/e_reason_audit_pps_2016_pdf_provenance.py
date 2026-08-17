#!/usr/bin/env python3
"""Audit provenance of recovered PPS 2016 regional candidate PDFs.

The audit follows only already-qualified T1 first-party domains. It re-discovers
region pages from the official PPS candidate category, requires their published
or modified timestamp to be no later than the frozen cutoff, and requires an
exact PDF link matching a recovered probe hit. It does not parse candidate facts.
"""
from __future__ import annotations
import hashlib,html,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';REG=ER/'e_reason_source_registry_v1.json';PTR=ER/'pps_2016_regional_pdf_probe_latest.json';OUT=ER/'evidence/pps_2016_pdf_provenance_audit'
CUTOFF=datetime(2016,10,6,22,59,59,tzinfo=timezone.utc)
CAT='https://pps.ma/category/%D9%85%D8%B1%D8%B4%D8%AD%D9%8A-%D8%AD%D8%B2%D8%A8-%D8%A7%D9%84%D8%AA%D9%82%D8%AF%D9%85-%D9%88-%D8%A7%D9%84%D8%A7%D8%B4%D8%AA%D8%B1%D8%A7%D9%83%D9%8A%D8%A9/'
S=requests.Session();S.headers.update({'User-Agent':'Atlas395-EReason-PPSProvenance/1.0','Accept':'text/html,application/json,*/*','Accept-Language':'ar,fr;q=0.8'})
OUTCOME=('نتائج انتخابات 7 أكتوبر','نواب حزب التقدم','فاز','النتائج النهائية','المقاعد المحصل')
def host(u):return (urlparse(u).hostname or '').lower().removeprefix('www.')
def get(u):
 last=None
 for i in range(4):
  try:
   r=S.get(u,timeout=(7,35),allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}:return r
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as e:last=e
  time.sleep(min(6,2**i))
 if last:raise last
 return r
def clean(x):return ' '.join(BeautifulSoup(html.unescape(x or ''),'html.parser').get_text(' ',strip=True).split())
def parse_dt(x):
 if not x:return None
 try:
  d=datetime.fromisoformat(str(x).replace('Z','+00:00'));return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
 except:return None
def dates(text):
 out=[]
 for p in [r'"datePublished"\s*:\s*"([^"]+)"',r'"dateModified"\s*:\s*"([^"]+)"',r'property=["\']article:published_time["\'][^>]*content=["\']([^"\']+)',r'property=["\']article:modified_time["\'][^>]*content=["\']([^"\']+)']:
  out.extend(m.group(1) for m in re.finditer(p,text,re.I))
 return sorted(set(out))
def links(text,base):
 s=BeautifulSoup(html.unescape(text.replace('\\/','/')),'html.parser');out=set()
 for a in s.find_all('a'):
  v=a.get('href')
  if v:out.add(urljoin(base,str(v)))
 return sorted(out)
def main():
 reg=json.loads(REG.read_text(encoding='utf-8'));q={x.get('domain') for x in reg.get('entries',[]) if x.get('source_class')=='T1_OFFICIAL_PARTY' and x.get('qualification_status')=='QUALIFIED_BEFORE_EXTRACTION'}
 if not {'pps.ma','ppsmaroc.com'}<=q:raise RuntimeError('PPS domains not qualified before extraction')
 ptr=json.loads(PTR.read_text(encoding='utf-8'));probe=json.loads((ROOT/ptr['latest_probe']).read_text(encoding='utf-8'));hits={x['filename']:x for x in probe['pdf_hits']}
 # Candidate category pages reveal the bounded set of region post links.
 post_urls=set();category_rows=[]
 for u in (CAT,CAT+'page/2/?filter_by=featured'):
  r=get(u);text=r.text;ls=links(text,str(r.url));nums=[x for x in ls if host(x)=='pps.ma' and re.fullmatch(r'https?://(?:www\.)?pps\.ma/\d+/?',x)];post_urls.update(nums);category_rows.append({'url':u,'status':r.status_code,'sha256':hashlib.sha256(r.content).hexdigest(),'numeric_post_links':nums})
 # Include four exact pages already established during qualification/search discovery.
 post_urls.update({'https://pps.ma/10462/','https://pps.ma/10487/','https://pps.ma/10453/','https://pps.ma/10446/'})
 pages=[];relationships=[]
 for u in sorted(post_urls):
  rec={'url':u,'status':None,'title':None,'timestamps':[],'precutoff':False,'pdf_links':[],'outcome_terms':[],'sha256':None,'error':None}
  try:
   r=get(u);text=r.text;soup=BeautifulSoup(text,'html.parser');h=soup.find('h1');title=clean(h.get_text(' ',strip=True) if h else '');ds=dates(text);pdfs=[x for x in links(text,str(r.url)) if '.pdf' in x.lower() and host(x) in {'ppsmaroc.com','pps.ma'}];outs=[x for x in OUTCOME if x in clean(text)];valid_dates=[parse_dt(x) for x in ds if parse_dt(x)];precut=bool(valid_dates and max(valid_dates)<=CUTOFF);rec.update(status=r.status_code,title=title,timestamps=ds,precutoff=precut,pdf_links=pdfs,outcome_terms=outs,sha256=hashlib.sha256(r.content).hexdigest())
   for purl in pdfs:
    base=Path(urlparse(purl).path).name
    # legacy/current redirect can preserve basename; probe was keyed by attempted basename.
    hit=hits.get(base)
    if hit:
     relationships.append({'page_url':u,'page_title':title,'page_timestamps':ds,'page_precutoff':precut,'page_sha256':rec['sha256'],'pdf_url_on_page':purl,'pdf_filename':base,'probe_sha256':hit['sha256'],'probe_bytes':hit['bytes'],'pdf_outcome_terms':hit['pdf']['outcome_terms'],'mechanical_pass':bool(precut and not outs and not hit['pdf']['outcome_terms'])})
  except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
  pages.append(rec)
 # It is possible the official page points to ppsmaroc.com while current redirect
 # changed host only; basename is the identity key and content hash freezes bytes.
 passed=[x for x in relationships if x['mechanical_pass']]
 payload={'schema_version':'1.0','created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'cutoff_utc':CUTOFF.isoformat(),'category_pages':category_rows,'region_pages':pages,'relationships':relationships,'counts':{'probe_pdf_hits':len(hits),'region_pages_checked':len(pages),'linked_probe_pdfs':len({x['probe_sha256'] for x in relationships}),'mechanically_admissible_pdfs':len({x['probe_sha256'] for x in passed})},'status':'PASS_PARTIAL' if passed else 'FAIL_CLOSED','invariants':{'candidate_facts_parsed':False,'new_source_class_added':False,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 OUT.mkdir(parents=True,exist_ok=True);(OUT/'audit.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps({'status':payload['status'],'counts':payload['counts'],'passed':[{'title':x['page_title'],'pdf':x['pdf_filename'],'sha256':x['probe_sha256']} for x in passed]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
