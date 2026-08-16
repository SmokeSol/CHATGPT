#!/usr/bin/env python3
import csv,hashlib,json,math,re,statistics,time,unicodedata
from collections import defaultdict
from io import StringIO
from pathlib import Path
from urllib.parse import urljoin,unquote
import pandas as pd, requests
from bs4 import BeautifulSoup
R=Path(__file__).resolve().parents[1]; D=R/'data'; O=D/'goal75';O.mkdir(parents=True,exist_ok=True)
S=requests.Session();S.headers['User-Agent']='MOROCCO26-research/1.0 (aggregate election research)'
P=['RNI','PAM','PI','PJD','USFP','MP','UC','PPS']; K=P+['OTHER']; INDEX=None
NAMES={'rassemblement national des independants':'RNI','parti authenticite et modernite':'PAM',"parti de l istiqlal":'PI','parti de la justice et du developpement':'PJD','union socialiste des forces populaires':'USFP','mouvement populaire':'MP','union constitutionnelle':'UC','parti du progres et du socialisme':'PPS','front des forces democratiques':'FFD','alliance de la federation de gauche':'AGD','federation de la gauche democratique':'FGD','parti socialiste unifie':'PSU','mouvement democratique et social':'MDS'}
def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def party(x):
 m=re.search(r'\(([A-Z][A-Z0-9-]{1,7})\)',str(x))
 if m:return m.group(1)
 n=norm(x)
 for k,v in NAMES.items():
  if k in n:return v
 return None
def nint(x):
 s=re.sub('[^0-9]','',str(x));return int(s) if s else None
def canon(x):return json.dumps(x,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def digest(x):return hashlib.sha256(canon(x).encode()).hexdigest()
def get(url):
 last=None
 for i in range(7):
  try:
   r=S.get(url,timeout=35,allow_redirects=True);last=r
   if r.status_code==200 and len(r.text)>1000:return r
   if r.status_code not in (429,403,408,500,502,503,504):r.raise_for_status()
  except Exception as e:last=e
  time.sleep(min(8,0.75*(2**i)))
 raise RuntimeError(f'GET failed {url}: {last}')
def build_index():
 global INDEX
 if INDEX is not None:return INDEX
 anchor='https://fr.wikipedia.org/wiki/Circonscription_de_Casablanca-Settat'
 soup=BeautifulSoup(get(anchor).text,'html.parser');idx={}
 for a in soup.find_all('a',href=True):
  href=a.get('href','');txt=a.get_text(' ',strip=True)
  if not href.startswith('/wiki/Circonscription_') or not txt:continue
  url=urljoin('https://fr.wikipedia.org',href);key=norm(txt)
  if key and key not in idx:idx[key]=(txt,url)
 # deterministic aliases for punctuation/orthography found in nav labels
 aliases={'agadir ida outanane':'agadir ida outanan','beni mellal':'beni mellal','m diq fnideq':'m diq fnideq','ain sebaa hay mohammadi':'ain sebaa hay mohammadi'}
 for want,have in aliases.items():
  if have in idx:idx[want]=idx[have]
 INDEX=idx
 if len(idx)<90:raise RuntimeError(f'constituency link index unexpectedly small: {len(idx)}')
 return idx
def resolve(name):
 idx=build_index();n=norm(name)
 if n in idx:return idx[n]
 target=set(n.split());best=None;score=(-1,-1)
 for k,v in idx.items():
  toks=set(k.split());inter=len(target&toks);union=max(1,len(target|toks));s=(inter/union,inter)
  if s>score:score=s;best=v
 if best and score[1]>=1 and score[0]>=0.45:return best
 raise RuntimeError(f'no indexed page for {name}; best_score={score} best={best}')
def flatcols(df):
 df=df.copy();df.columns=[' '.join(str(z) for z in c if 'Unnamed' not in str(z)) if isinstance(c,tuple) else str(c) for c in df.columns];return df
def parse(df):
 df=flatcols(df); pc=next((c for c in df.columns if 'Parti' in c),None);vc=next((c for c in df.columns if 'Voix' in c),None)
 if not pc or not vc:raise RuntimeError('bad table')
 votes={};reg=exp=absn=None
 for _,r in df.iterrows():
  a=str(r[pc]); na=norm(a);v=nint(r[vc])
  if na=='inscrits':reg=v;continue
  if na=='exprimes':exp=v;continue
  if na=='abstentions':absn=v;continue
  p=party(a)
  if p and v is not None:votes[p]=votes.get(p,0)+v
 if exp is None:exp=sum(votes.values())
 return {'votes':votes,'registered':reg,'expressed':exp,'abstentions':absn}
def acquire(name,seats,need21):
 title,url=resolve(name);html=get(url).text;tabs=[]
 for df in pd.read_html(StringIO(html)):
  cols=' '.join(map(str,df.columns))
  if 'Parti' in cols and 'Voix' in cols:tabs.append(df)
 if not tabs:raise RuntimeError(f'no election tables: {title}')
 out={'title':title,'url':url,'2016':parse(tabs[-2]) if len(tabs)>=2 else None}
 if need21:out['2021']=parse(tabs[-1])
 return out
def alloc(v,s,r):
 q=r/s;b={p:math.floor(x/q) for p,x in v.items()};a=b.copy();rem={p:v[p]-b[p]*q for p in v};left=s-sum(b.values())
 for p in sorted(v,key=lambda p:(-rem[p],-v[p],p)):
  if left<=0:break
  a[p]=a.get(p,0)+1;left-=1
 return {p:x for p,x in a.items() if x}
def vec(v):
 z=max(1,sum(v.values()));d={p:v.get(p,0)/z for p in P};d['OTHER']=max(0,1-sum(d.values()));return d
def clr(v):
 x={k:math.log(v[k]+1e-5) for k in K};m=sum(x.values())/len(K);return {k:x[k]-m for k in K}
def inv(c):
 x={k:math.exp(c[k]) for k in K};z=sum(x.values());return {k:x[k]/z for k in K}
def lg(x):x=min(max(x,1e-6),1-1e-6);return math.log(x/(1-x))
def il(x):return 1/(1+math.exp(-x))
def med(x):return statistics.median(x) if x else 0
def freeze(dev,hold):
 sh={k:[] for k in K};rh=defaultdict(lambda:{k:[] for k in K});td=[];rtd=defaultdict(list);used=[]
 for x in dev:
  a,b=x.get('2016'),x.get('2021')
  if not a or not b:continue
  c1,c2=clr(vec(a['votes'])),clr(vec(b['votes']))
  for k in K:
   d=c2[k]-c1[k];sh[k].append(d);rh[x['region']][k].append(d)
  if a['registered'] and b['registered']:
   d=lg(b['expressed']/b['registered'])-lg(a['expressed']/a['registered']);td.append(d);rtd[x['region']].append(d)
  used.append(x['constituency_id'])
 g={k:med(v) for k,v in sh.items()};gt=med(td);pred=[]
 for h in hold:
  if not h.get('2016') or not h['2016'].get('registered'):continue
  c=clr(vec(h['2016']['votes']));nn=len(rtd[h['region']]);w=nn/(nn+5);rr={k:med(rh[h['region']][k]) if rh[h['region']][k] else g[k] for k in K};bp=inv({k:c[k]+g[k] for k in K});cp=inv({k:c[k]+g[k]+w*(rr[k]-g[k]) for k in K});t=h['2016']['expressed']/h['2016']['registered'];rt=med(rtd[h['region']]) if rtd[h['region']] else gt
  pred.append({'constituency_id':h['constituency_id'],'name':h['name'],'region':h['region'],'seats':h['seats'],'B':{'shares':bp,'turnout':il(lg(t)+gt),'winner_set':sorted(bp,key=bp.get,reverse=True)[:h['seats']]},'C_eval':{'shares':cp,'turnout':il(lg(t)+gt+w*(rt-gt)),'winner_set':sorted(cp,key=cp.get,reverse=True)[:h['seats']]}})
 z={'method_B':'global median CLR 2016→2021 shift, development only','method_C_eval':'region-shrunk CLR transition; stronger non-LLM comparator distinct from Phase-2 causal C','training':sorted(used),'global_shift':g,'turnout_shift':gt,'predictions':pred};z['freeze_hash']=digest(z);return z
def main():
 rows=list(csv.DictReader(open(D/'constituencies_goal75.csv',encoding='utf-8')));hold=json.load(open(D/'territorial_holdout_v1.json'));hn={norm(x['name']) for x in hold['constituencies']};dev=[];hi=[];err=[]
 build_index()
 for i,r in enumerate(rows,1):
  try:
   h=norm(r['name']) in hn;a=acquire(r['name'],int(r['seats']),not h);x={'constituency_id':r['constituency_id'],'name':r['name'],'region':r['region'],'seats':int(r['seats']),'source_url':a['url'],'2016':a['2016']}
   if h:x['holdout_role']='SEALED_2021_OUTCOME';hi.append(x)
   else:
    x['2021']=a['2021'];y=x['2021'];x['legal_replay']=alloc(y['votes'],x['seats'],y['registered']) if y['registered'] else None;x['rank_winners']=sorted(y['votes'],key=y['votes'].get,reverse=True)[:x['seats']];x['legal_vs_rank_match']=set(x['legal_replay'] or {})==set(x['rank_winners']);dev.append(x)
   print(i,r['name'],'ok',flush=True);time.sleep(.25)
  except Exception as e:err.append({'name':r['name'],'holdout':norm(r['name']) in hn,'error':repr(e)});print(i,r['name'],'ERROR',e,flush=True);time.sleep(.75)
 f=freeze(dev,hi);m=[]
 for x in dev:
  y=x['2021'];rr=sorted(y['votes'].items(),key=lambda z:(-z[1],z[0]))
  if len(rr)>x['seats']:
   a,b=rr[x['seats']-1],rr[x['seats']];m.append({'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'seats':x['seats'],'last_winner':a[0],'last_winner_votes':a[1],'first_nonwinner':b[0],'first_nonwinner_votes':b[1],'margin_votes':a[1]-b[1],'registered':y['registered'],'source_url':x['source_url']})
 pkg={'stage':'PRE_UNSEAL','holdout_2021_outcomes_accessed':False,'development':dev,'holdout_inputs_2016':hi,'errors':err};(O/'stage1_acquisition.json').write_text(json.dumps(pkg,ensure_ascii=False,indent=2));(O/'bc_freeze.json').write_text(json.dumps(f,ensure_ascii=False,indent=2));(O/'seat_margin_pre_holdout.json').write_text(json.dumps(m,ensure_ascii=False,indent=2))
 ev=[x for x in dev if x.get('legal_replay')];ok=sum(x['legal_vs_rank_match'] for x in ev);rep={'development_target':80,'development_acquired':len(dev),'holdout_inputs_2016_only':len(hi),'holdout_2021_outcomes_accessed':False,'errors':err,'legal_replay_evaluable':len(ev),'legal_vs_rank_matches':ok,'legal_vs_rank_match_rate':ok/max(1,len(ev)),'seat_margin_records':len(m),'bc_predictions_frozen':len(f['predictions']),'bc_freeze_hash':f['freeze_hash'],'ready_to_unseal':len(dev)>=75 and len(hi)==12 and len(f['predictions'])==12 and len(ev)>=70 and ok/max(1,len(ev))>=.95};(O/'stage1_report.json').write_text(json.dumps(rep,ensure_ascii=False,indent=2));print(json.dumps(rep,ensure_ascii=False,indent=2));return 0 if rep['ready_to_unseal'] else 2
if __name__=='__main__':raise SystemExit(main())
