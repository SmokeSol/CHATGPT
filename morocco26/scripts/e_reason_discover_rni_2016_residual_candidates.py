#!/usr/bin/env python3
"""Discover pre-cutoff official RNI pages for the final 2016 residual districts.

Discovery is performed only after rni.ma was qualified as T1_OFFICIAL_PARTY.
The query universe is fixed mechanically from the current combined-gate residual:
districts with exactly two already-verified identities. Only RNI posts whose
published AND modified timestamps are <= the frozen 2016 cutoff are eligible for
later candidate extraction. This script does not itself promote any identity.
"""
from __future__ import annotations
import hashlib,html,json,os,re,time,unicodedata
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import urlencode
import requests
from bs4 import BeautifulSoup
ROOT=Path(__file__).resolve().parents[2]
ER=ROOT/'morocco26/data/goal100/e_reason';REG=ER/'e_reason_source_registry_v1.json';RES=ER/'evidence/combined_2016_candidate_gate/residual.json';CROSS=ER/'evidence/arabic_2016_crosswalk/crosswalk.json'
RID=os.environ.get('E_REASON_RNI2016_RUN_ID') or 'rni2016_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
OUT=ER/'evidence/rni_2016_residual_discovery'/RID;RAW=OUT/'raw';RAW.mkdir(parents=True,exist_ok=False)
CUTOFF=datetime(2016,10,6,22,59,59,tzinfo=timezone.utc);AFTER='2016-07-01T00:00:00';BEFORE='2016-10-07T00:00:00'
S=requests.Session();S.headers.update({'User-Agent':'Atlas395-EReason-RNI2016/1.0','Accept':'application/json,text/html,*/*','Accept-Language':'ar,fr;q=0.8'})
CANDIDATE_TERMS=('مرشح','مرشحي','مرشحو','مرشحين','الترشيحات','لائحة','اللوائح','وكيل','انتخابات','تشريعية')
OUTCOME_TERMS=('النتائج','فاز','فوز','المقاعد المحصل','النواب المنتخبين','انتخب')
def qualified():
 d=json.loads(REG.read_text(encoding='utf-8'));return any(x.get('domain')=='rni.ma' and x.get('source_class')=='T1_OFFICIAL_PARTY' and x.get('qualification_status')=='QUALIFIED_BEFORE_EXTRACTION' for x in d.get('entries',[]))
def dt(x):
 try:
  v=datetime.fromisoformat(str(x).replace('Z','+00:00'));return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).astimezone(timezone.utc)
 except:return None
def get(u,params=None):
 last=None
 for i in range(4):
  try:
   r=S.get(u,params=params,timeout=(7,35),allow_redirects=True)
   if r.status_code not in {408,425,429,500,502,503,504}:return r
  except (requests.ConnectTimeout,requests.ReadTimeout,requests.ConnectionError) as e:last=e
  time.sleep(min(6,2**i))
 if last:raise last
 return r
def clean(x):return ' '.join(BeautifulSoup(html.unescape(x or ''),'html.parser').get_text(' ',strip=True).split())
def norm_ar(s):
 x=unicodedata.normalize('NFKC',clean(s)).replace('ـ','');x=x.translate(str.maketrans({'ی':'ي','ى':'ي','ک':'ك'}));x=re.sub(r'[أإآٱ]','ا',x);x=re.sub(r'[^\u0600-\u06FF0-9]+',' ',x);return ' '.join(x.split())
def freeze(body,suffix):
 h=hashlib.sha256(body).hexdigest();p=RAW/(h+suffix);p.write_bytes(body);return h,str(p.relative_to(ROOT))
def main():
 if not qualified():raise RuntimeError('rni.ma must be T1-qualified before extraction')
 residual=json.loads(RES.read_text(encoding='utf-8'));cross=json.loads(CROSS.read_text(encoding='utf-8'));by={x['source_2026_constituency_id']:x for x in cross['records']}
 targets=[x for x in residual['residual_with_any_candidate_below_three'] if x.get('verified_distinct_candidate_identities')==2 and x['constituency_id'] in by]
 query_rows=[];posts={}
 for t in targets:
  cid=t['constituency_id'];r=by[cid];terms=[]
  for v in (r.get('name_ar'),r.get('name_ar_source_form'),r.get('name_ar_match_key')):
   n=norm_ar(v)
   if n and n not in terms:terms.append(n)
  for term in terms[:3]:
   rec={'constituency_id':cid,'historical_constituency':r.get('historical_constituency'),'term':term,'status':None,'rows':0,'error':None}
   try:
    resp=get('https://rni.ma/wp-json/wp/v2/posts',params={'after':AFTER,'before':BEFORE,'search':term,'per_page':100,'orderby':'date','order':'asc','_fields':'id,date,date_gmt,modified,modified_gmt,slug,link,title,excerpt,content'})
    rec['status']=resp.status_code;data=resp.json() if resp.ok else [];data=data if isinstance(data,list) else [];rec['rows']=len(data)
    for p in data:
     pid=p.get('id');key=str(pid)
     if not isinstance(pid,int):continue
     published=dt(p.get('date_gmt') or p.get('date'));modified=dt(p.get('modified_gmt') or p.get('modified'));title=clean((p.get('title') or {}).get('rendered',''));content=clean((p.get('content') or {}).get('rendered',''));excerpt=clean((p.get('excerpt') or {}).get('rendered',''));text=' '.join((title,excerpt,content));body=json.dumps(p,ensure_ascii=False,sort_keys=True).encode('utf-8');sha,path=freeze(body,'.json')
     row=posts.setdefault(key,{'post_id':pid,'date':published.isoformat() if published else None,'modified':modified.isoformat() if modified else None,'slug':p.get('slug'),'link':p.get('link'),'title':title,'sha256':sha,'raw_path':path,'candidate_term_hits':[x for x in CANDIDATE_TERMS if x in text],'outcome_term_hits':[x for x in OUTCOME_TERMS if x in text],'matched_target_queries':[]})
     row['matched_target_queries'].append({'constituency_id':cid,'term':term})
   except Exception as e:rec['error']=f'{type(e).__name__}: {e}'
   query_rows.append(rec)
 eligible=[]
 for p in posts.values():
  pd=dt(p['date']);md=dt(p['modified']);p['published_pre_cutoff']=bool(pd and pd<=CUTOFF);p['modified_pre_cutoff']=bool(md and md<=CUTOFF);p['candidate_context']=bool(p['candidate_term_hits']);p['no_outcome_terms']=not p['outcome_term_hits'];p['eligible_for_candidate_extraction']=bool(p['published_pre_cutoff'] and p['modified_pre_cutoff'] and p['candidate_context'] and p['no_outcome_terms'])
  if p['eligible_for_candidate_extraction']:eligible.append(p)
 payload={'schema_version':'1.0','run_id':RID,'created_at':datetime.now(timezone.utc).isoformat(timespec='seconds'),'cutoff_utc':CUTOFF.isoformat(),'source_class':'T1_OFFICIAL_PARTY','qualified_domain':'rni.ma','target_rule':'CURRENT_COMBINED_GATE_DISTRICTS_WITH_EXACTLY_TWO_VERIFIED_IDENTITIES','targets':[{'constituency_id':x['constituency_id'],'historical_constituency':by[x['constituency_id']].get('historical_constituency'),'current_identities':x['verified_distinct_candidate_identities']} for x in targets],'queries':query_rows,'posts':sorted(posts.values(),key=lambda x:(x.get('date') or '',x['post_id'])),'eligible_posts':eligible,'counts':{'targets':len(targets),'queries':len(query_rows),'unique_posts':len(posts),'eligible_pre_cutoff_unmodified_candidate_posts':len(eligible)},'invariants':{'candidate_identities_promoted':False,'search_snippets_used_as_evidence':False,'post_cutoff_modified_pages_rejected':True,'outcomes_unsealed':False,'predictive_judgments_generated':False,'F1_created':False}}
 (OUT/'discovery.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');(ER/'rni_2016_residual_discovery_latest.json').write_text(json.dumps({'schema_version':'1.0','latest_run_id':RID,'latest_discovery':str((OUT/'discovery.json').relative_to(ROOT))},indent=2)+'\n',encoding='utf-8');print(json.dumps({'counts':payload['counts'],'eligible_posts':[{'id':x['post_id'],'date':x['date'],'modified':x['modified'],'title':x['title'],'targets':x['matched_target_queries']} for x in eligible]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
