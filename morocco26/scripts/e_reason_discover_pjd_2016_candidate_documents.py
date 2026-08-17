#!/usr/bin/env python3
"""Systematically inventory PJD 2016 candidate-document posts and attachments.

The current migrated CMS is discovery/provenance material only. This script
finds historical 2016 posts and PDF attachment addresses; it does not mark the
current responses as admissible candidate evidence and does not use outcomes.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason'
RID=os.environ.get('E_REASON_PJD_DISCOVERY_RUN_ID') or 'pjd2016_discovery_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/pjd_2016_candidate_discovery'/RID
RAW=OUT/'raw'
RAW.mkdir(parents=True,exist_ok=False)
S=requests.Session(); S.headers.update({'User-Agent':'Atlas395-EReason-PJDDiscovery/1.0','Accept':'application/json,text/html,*/*'})
API='https://www.pjd.ma/wp-json/wp/v2/posts'
AFTER='2016-07-01T00:00:00'
BEFORE='2016-10-07T00:00:00'
SEARCH_TERMS=['مرشحي','المرشحين','باقي مرشحي','لوائح','تزكية','7 أكتوبر']
PDF_HINTS=('مرشح','مرشحي','المرشحين','لائحة','لوائح','تزكي','انتخاب','أكتوبر')
OUTCOME_TERMS=('نتائج','فاز','الفائز','مقعدا','الأصوات')


def get_retry(url:str,*,params:dict[str,Any]|None=None,attempts:int=4,timeout=(7,35)):
    last=None
    for i in range(attempts):
        try:
            r=S.get(url,params=params,timeout=timeout,allow_redirects=True)
            if r.status_code not in {408,425,429,500,502,503,504}: return r
            last=requests.HTTPError(f'retryable HTTP {r.status_code}')
        except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as exc:
            last=exc
        if i+1<attempts: time.sleep(min(8,2**i))
    if last: raise last
    raise RuntimeError('request failed')


def freeze(body:bytes,suffix:str)->str:
    h=hashlib.sha256(body).hexdigest(); p=RAW/f'{h}{suffix}'
    if not p.exists(): p.write_bytes(body)
    return str(p.relative_to(ROOT))


def clean_text(value:str)->str:
    soup=BeautifulSoup(html.unescape(value or ''),'html.parser')
    return ' '.join(soup.get_text(' ',strip=True).split())


def pdf_links(rendered:str,base:str)->list[str]:
    text=html.unescape(rendered or '').replace('\\/','/')
    soup=BeautifulSoup(text,'html.parser'); out=set()
    for a in soup.find_all('a'):
        href=str(a.get('href') or '')
        if '.pdf' in href.casefold(): out.add(urljoin(base,href))
    for m in re.finditer(r'https?://[^\s\"\'<>]+\.pdf(?:\?[^\s\"\'<>]*)?',text,re.I): out.add(m.group(0))
    return sorted(out)


def relevant(post:dict[str,Any])->tuple[bool,list[str]]:
    title=clean_text((post.get('title') or {}).get('rendered',''))
    content=clean_text((post.get('content') or {}).get('rendered',''))
    excerpt=clean_text((post.get('excerpt') or {}).get('rendered',''))
    joined=' '.join((title,content,excerpt))
    hits=[x for x in PDF_HINTS if x in joined]
    return bool(hits),hits


def query_term(term:str)->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    posts=[]; diags=[]
    for page in range(1,11):
        params={'after':AFTER,'before':BEFORE,'search':term,'per_page':'100','page':str(page),'orderby':'date','order':'asc','_embed':'0'}
        diag={'term':term,'page':page,'status':None,'bytes':0,'rows':0,'total':None,'total_pages':None,'error':None}
        try:
            r=get_retry(API,params=params); diag.update(status=r.status_code,bytes=len(r.content),total=r.headers.get('X-WP-Total'),total_pages=r.headers.get('X-WP-TotalPages'))
            if r.status_code==400 and page>1: diags.append(diag); break
            r.raise_for_status(); data=r.json()
            if not isinstance(data,list): data=[]
            diag['rows']=len(data); posts.extend(x for x in data if isinstance(x,dict))
            diags.append(diag)
            if len(data)<100: break
        except Exception as exc:
            diag['error']=f'{type(exc).__name__}: {exc}'; diags.append(diag); break
    return posts,diags


def main():
    by_id={}; diagnostics=[]
    for term in SEARCH_TERMS:
        posts,diags=query_term(term); diagnostics.extend(diags)
        for p in posts:
            if isinstance(p.get('id'),int): by_id[p['id']]=p
    rows=[]; pdfs={}
    for pid,post in sorted(by_id.items(),key=lambda kv:(kv[1].get('date',''),kv[0])):
        ok,hits=relevant(post)
        title=clean_text((post.get('title') or {}).get('rendered',''))
        link=str(post.get('link') or '')
        content=(post.get('content') or {}).get('rendered','')
        links=pdf_links(content,link)
        if not ok and not links: continue
        body=json.dumps(post,ensure_ascii=False,sort_keys=True).encode('utf-8')
        raw_path=freeze(body,'.json')
        row={
            'post_id':pid,'date':post.get('date'),'date_gmt':post.get('date_gmt'),'slug':post.get('slug'),'link':link,'title':title,
            'candidate_keyword_hits':hits,'pdf_links':links,'current_cms_snapshot_path':raw_path,
            'current_cms_is_admissible_candidate_evidence':False,
            'post_cutoff_outcome_term_hits':[x for x in OUTCOME_TERMS if x in (title+' '+clean_text(content))],
        }
        rows.append(row)
        for u in links:
            pdfs.setdefault(u,{'url':u,'discovered_from':[]})['discovered_from'].append({'post_id':pid,'date':post.get('date'),'title':title})
    payload={
        'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'query_window':{'after':AFTER,'before':BEFORE},'search_terms':SEARCH_TERMS,'diagnostics':diagnostics,
        'unique_posts_scanned':len(by_id),'candidate_related_posts':len(rows),'unique_pdf_links':len(pdfs),
        'posts':rows,'pdf_inventory':sorted(pdfs.values(),key=lambda x:x['url']),
        'current_cms_is_admissible_candidate_evidence':False,
        'predictive_judgments_generated':False,'forecast_delta_generated':False,'outcomes_unsealed':False,'F1_created':False,
    }
    (OUT/'inventory.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (ER/'pjd_2016_candidate_discovery_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_inventory':str((OUT/'inventory.json').relative_to(ROOT))},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'run_id':RID,'unique_posts_scanned':len(by_id),'candidate_related_posts':len(rows),'unique_pdf_links':len(pdfs),'pdfs':[x['url'] for x in sorted(pdfs.values(),key=lambda x:x['url'])]},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
