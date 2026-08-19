#!/usr/bin/env python3
"""Expand the Assahraa 2007 pre-election constituency series without outcome inputs.

Starting only from independently discovered pre-election Assahraa articles, follow
same-site election-related links, recognize Moroccan Arabic publication dates, and
retain exact contexts mentioning constituencies/seats. No same-year outcome file is
read or used to formulate discovery targets.
"""
from __future__ import annotations

import hashlib, html, json, re, subprocess, time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'goal100'/'historical'/'2007_v2_research'
OUT.mkdir(parents=True,exist_ok=True)
CUTOFF='2007-09-06'
BASE='2508256551f94ad67c23a39d7263e01202431bfe'
SEEDS=['https://assahraa.ma/journal/2007/46530','https://assahraa.ma/journal/2007/46728']
DERIVED_FORBIDDEN=[
 ROOT/'data'/'goal100'/'historical'/'2007'/'legislative_2007_outcome_canonical.json',
 ROOT/'data'/'goal100'/'historical'/'2007'/'historical_native_map_outcome_transcription.json',
]
AR_MONTHS={'يناير':1,'فبراير':2,'مارس':3,'أبريل':4,'ابريل':4,'ماي':5,'يونيو':6,'يوليوز':7,'غشت':8,'شتنبر':9,'سبتمبر':9,'أكتوبر':10,'اكتوبر':10,'نونبر':11,'نوفمبر':11,'دجنبر':12,'ديسمبر':12}
DATE_RE=re.compile(r'(\d{1,2})\s+('+'|'.join(map(re.escape,AR_MONTHS))+r')\s+2007')
JOURNAL_RE=re.compile(r'/journal/2007/\d+/?$')
ELECTION_WORDS=('انتخاب','اللوائح','لوائح','دائرة','دوائر','تشريع','السابع من شتنبر')
SEAT_WORDS=('مقعد','مقاعد')

S=requests.Session(); S.headers.update({'User-Agent':'MOROCCO26-historical-research/2.0','Accept-Language':'ar,fr;q=0.9,en;q=0.5'})

def norm(s): return re.sub(r'\s+',' ',html.unescape(s or '')).strip()
def sha(b): return hashlib.sha256(b).hexdigest()

def parse_date(text):
 m=DATE_RE.search(norm(text)[:8000])
 if not m: return None
 return f"2007-{AR_MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"

def clean_guard():
 bad=[str(p.relative_to(ROOT)) for p in DERIVED_FORBIDDEN if p.exists()]
 if bad: raise SystemExit(f'LEAKAGE_GUARD_FAIL derived outcome exists: {bad}')
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if subprocess.run(['git','merge-base','--is-ancestor',BASE,head],cwd=ROOT).returncode:
  raise SystemExit('LEAKAGE_GUARD_FAIL base ancestry')
 return {'base':BASE,'head':head,'derived_outcome_paths_present':bad}

def fetch(url):
 try: r=S.get(url,timeout=25,allow_redirects=True)
 except Exception as e: return {'url':url,'status':'FETCH_ERROR','error':repr(e)}
 rec={'url':url,'final_url':r.url,'http_status':r.status_code,'bytes':len(r.content),'sha256':sha(r.content)}
 if r.status_code!=200: rec['status']='FETCH_ERROR'; return rec
 soup=BeautifulSoup(r.text,'html.parser')
 for x in soup(['script','style','noscript','svg']): x.decompose()
 text=norm(soup.get_text(' ')); title=norm(soup.title.string if soup.title and soup.title.string else '')
 date=parse_date(text)
 rec.update({'title':title,'publication_date':date,'text':text})
 if not date: rec['status']='AMBIGUOUS_DATE'
 elif date>CUTOFF: rec['status']='POST_CUTOFF_REJECTED'
 else: rec['status']='ELIGIBLE_PRE_ELECTION'
 links=[]
 for a in soup.find_all('a',href=True):
  href=urljoin(r.url,a['href']).split('#')[0]; host=urlparse(href).netloc.lower()
  if 'assahraa.ma' not in host or not JOURNAL_RE.search(urlparse(href).path): continue
  label=norm(a.get_text(' '))
  if any(w in label for w in ELECTION_WORDS): links.append({'url':href,'anchor':label})
 rec['election_related_links']=links
 return rec

def contexts(rec):
 if rec.get('status')!='ELIGIBLE_PRE_ELECTION': return []
 t=rec['text']; out=[]; seen=set()
 # Retain contexts where a seat term and an electoral-district term are close. We do
 # not force an entity parse here; a later audited normalizer can promote them.
 for m in re.finditer(r'مقاعد|مقعد',t):
  lo=max(0,m.start()-420); hi=min(len(t),m.end()+420); c=t[lo:hi]
  if not any(w in c for w in ('دائرة','دوائر','عمالة','إقليم','اقليم','ولاية')): continue
  key=c[:180]
  if key in seen: continue
  seen.add(key)
  out.append({'url':rec['url'],'publication_date':rec['publication_date'],'source_title':rec['title'],'supporting_context':c,'status':'VERIFIED_SOURCE_CONTEXT'})
 return out

def main():
 lineage=clean_guard(); q=deque((u,0) for u in SEEDS); seen=set(); articles=[]; ctx=[]
 while q and len(seen)<120:
  u,depth=q.popleft()
  if u in seen: continue
  seen.add(u); rec=fetch(u)
  ctx.extend(contexts(rec))
  articles.append({k:v for k,v in rec.items() if k!='text'})
  if depth<2 and rec.get('status') in {'ELIGIBLE_PRE_ELECTION','AMBIGUOUS_DATE'}:
   for link in rec.get('election_related_links',[]):
    if link['url'] not in seen: q.append((link['url'],depth+1))
  time.sleep(.12)
 eligible=[a for a in articles if a.get('status')=='ELIGIBLE_PRE_ELECTION']
 payload={'schema_version':'2.0','research_id':'M26-HIST-2007-ASSAHRAA-PRE-ELECTION-SERIES-V2','cutoff':CUTOFF,'outcome_used':False,'lineage':lineage,'seed_urls':SEEDS,'pages_seen':len(articles),'eligible_pages':len(eligible),'seat_context_count':len(ctx),'articles':articles,'seat_contexts':ctx}
 (OUT/'assahraa_series_evidence_v2.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 # Full text only for eligible pages, for auditable downstream extraction.
 full=[]
 for a in articles:
  if a.get('status')!='ELIGIBLE_PRE_ELECTION': continue
  r=fetch(a['url'])
  if r.get('status')=='ELIGIBLE_PRE_ELECTION': full.append({'url':r['url'],'publication_date':r['publication_date'],'sha256':r['sha256'],'title':r['title'],'text':r['text']})
 (OUT/'assahraa_eligible_text_v2.json').write_text(json.dumps({'schema_version':'2.0','pages':full},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'pages_seen':len(articles),'eligible_pages':len(eligible),'seat_contexts':len(ctx),'linked_urls':sum(len(a.get('election_related_links',[])) for a in articles)},ensure_ascii=False))
if __name__=='__main__': main()
