#!/usr/bin/env python3
"""Expand Le Matin/MAP's pre-election 2007 constituency corpus outcome-blind."""
from __future__ import annotations
import hashlib, html, json, re, subprocess, time
from collections import deque
from pathlib import Path
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'data'/'goal100'/'historical'/'2007_v2_research'; OUT.mkdir(parents=True,exist_ok=True)
BASE='2508256551f94ad67c23a39d7263e01202431bfe'; CUTOFF='2007-09-06'
SEEDS=[
 'https://lematin.ma/journal/2007/Legislatives-a-travers-les-regions_15-listes-locales-a-Laayoune-et-23-a-Meknes-Tafilelt/76043.html',
 'https://lematin.ma/journal/2007/Scrutin-du-7-septembre_Journal-de-campagne--716-plaintes-pour-violation-du-code-electoral/74300.html',
]
FORBIDDEN=[ROOT/'data'/'goal100'/'historical'/'2007'/'legislative_2007_outcome_canonical.json',ROOT/'data'/'goal100'/'historical'/'2007'/'historical_native_map_outcome_transcription.json']
MONTHS={'janvier':1,'février':2,'fevrier':2,'mars':3,'avril':4,'mai':5,'juin':6,'juillet':7,'août':8,'aout':8,'septembre':9,'octobre':10,'novembre':11,'décembre':12,'decembre':12}
DRE=re.compile(r'(\d{1,2})\s+('+'|'.join(map(re.escape,MONTHS))+r')\s+2007',re.I)
PATHRE=re.compile(r'/journal/2007/.+\.html$')
WORDS=('législ','legisl','circonscription','électoral','electoral','scrutin','listes','campagne','région','region')
S=requests.Session(); S.headers.update({'User-Agent':'MOROCCO26-historical-research/2.0','Accept-Language':'fr,ar;q=.8,en;q=.5'})
def norm(x): return re.sub(r'\s+',' ',html.unescape(x or '')).strip()
def hs(b): return hashlib.sha256(b).hexdigest()
def date(text):
 m=DRE.search(norm(text)[:9000]);
 if not m: return None
 return f"2007-{MONTHS[m.group(2).lower()]:02d}-{int(m.group(1)):02d}"
def guard():
 bad=[str(p.relative_to(ROOT)) for p in FORBIDDEN if p.exists()]
 if bad: raise SystemExit('LEAKAGE_GUARD_FAIL '+repr(bad))
 head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 if subprocess.run(['git','merge-base','--is-ancestor',BASE,head],cwd=ROOT).returncode: raise SystemExit('LEAKAGE_GUARD_FAIL ancestry')
 return {'base':BASE,'head':head,'derived_outcome_paths_present':bad}
def fetch(url):
 try:r=S.get(url,timeout=22,allow_redirects=True)
 except Exception as e:return {'url':url,'status':'FETCH_ERROR','error':repr(e)}
 rec={'url':url,'final_url':r.url,'http_status':r.status_code,'bytes':len(r.content),'sha256':hs(r.content)}
 if r.status_code!=200:return rec|{'status':'FETCH_ERROR'}
 soup=BeautifulSoup(r.text,'html.parser')
 for x in soup(['script','style','noscript','svg']):x.decompose()
 t=norm(soup.get_text(' ')); ti=norm(soup.title.string if soup.title and soup.title.string else ''); d=date(t)
 status='AMBIGUOUS_DATE' if not d else ('POST_CUTOFF_REJECTED' if d>CUTOFF else 'ELIGIBLE_PRE_ELECTION')
 links=[]
 for a in soup.find_all('a',href=True):
  u=urljoin(r.url,a['href']).split('#')[0]; lab=norm(a.get_text(' ')); p=urlparse(u)
  if 'lematin.ma' not in p.netloc.lower() or not PATHRE.search(p.path):continue
  if any(w in (lab+' '+u).lower() for w in WORDS):links.append({'url':u,'anchor':lab})
 return rec|{'title':ti,'publication_date':d,'status':status,'text':t,'election_related_links':links}
def contexts(rec):
 if rec.get('status')!='ELIGIBLE_PRE_ELECTION':return []
 t=rec['text']; out=[]; seen=set()
 for m in re.finditer(r'si[eè]ges?',t,re.I):
  lo=max(0,m.start()-500);hi=min(len(t),m.end()+500);c=t[lo:hi]
  if not re.search(r'circonscription|province|préfecture|listes|candidats',c,re.I):continue
  k=c[:200]
  if k in seen:continue
  seen.add(k);out.append({'url':rec['url'],'publication_date':rec['publication_date'],'source_title':rec['title'],'supporting_context':c,'status':'VERIFIED_SOURCE_CONTEXT'})
 return out
def main():
 lineage=guard();q=deque((u,0) for u in SEEDS);seen=set();arts=[];ctx=[];full=[]
 while q and len(seen)<180:
  u,dep=q.popleft()
  if u in seen:continue
  seen.add(u);r=fetch(u);ctx.extend(contexts(r));arts.append({k:v for k,v in r.items() if k!='text'})
  if r.get('status')=='ELIGIBLE_PRE_ELECTION':full.append({'url':r['url'],'publication_date':r['publication_date'],'sha256':r['sha256'],'title':r['title'],'text':r['text']})
  if dep<2 and r.get('status') in {'ELIGIBLE_PRE_ELECTION','AMBIGUOUS_DATE'}:
   for z in r.get('election_related_links',[]):
    if z['url'] not in seen:q.append((z['url'],dep+1))
  time.sleep(.1)
 p={'schema_version':'2.0','research_id':'M26-HIST-2007-LEMATIN-MAP-PRE-ELECTION-SERIES-V2','cutoff':CUTOFF,'outcome_used':False,'lineage':lineage,'seed_urls':SEEDS,'pages_seen':len(arts),'eligible_pages':sum(a.get('status')=='ELIGIBLE_PRE_ELECTION' for a in arts),'seat_context_count':len(ctx),'articles':arts,'seat_contexts':ctx}
 (OUT/'lematin_series_evidence_v2.json').write_text(json.dumps(p,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 (OUT/'lematin_eligible_text_v2.json').write_text(json.dumps({'schema_version':'2.0','pages':full},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 print(json.dumps({'pages_seen':len(arts),'eligible_pages':p['eligible_pages'],'seat_contexts':len(ctx),'linked_urls':sum(len(a.get('election_related_links',[])) for a in arts)}))
if __name__=='__main__':main()
