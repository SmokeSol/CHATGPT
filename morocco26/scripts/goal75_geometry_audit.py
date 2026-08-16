#!/usr/bin/env python3
import csv,json,re,unicodedata
from io import StringIO
from pathlib import Path
import pandas as pd,requests
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
url='https://fr.wikipedia.org/wiki/Liste_des_circonscriptions_l%C3%A9gislatives_au_Maroc'
r=requests.get(url,headers={'User-Agent':'MOROCCO26-research/1.0'},timeout=30);r.raise_for_status();tables=pd.read_html(StringIO(r.text))
source=[]
for df in tables:
 cols=[str(c) for c in df.columns]
 if any('Nom de la circonscription' in c for c in cols) and any('Nombre de sièges' in c for c in cols):
  nc=next(c for c in df.columns if 'Nom de la circonscription' in str(c));sc=next(c for c in df.columns if 'Nombre de sièges' in str(c))
  for _,row in df.iterrows():
   try:s=int(row[sc])
   except:continue
   name=str(row[nc]);source.append({'name':name,'norm':norm(name),'seats':s})
rows=list(csv.DictReader(open(D/'constituencies_goal75.csv',encoding='utf-8')));diff=[];matched=[]
for x in rows:
 n=norm(x['name']);cand=next((z for z in source if z['norm']==n),None)
 if not cand:
  # conservative token-overlap fallback
  t=set(n.split());cand=max(source,key=lambda z:len(t&set(z['norm'].split()))/max(1,len(t|set(z['norm'].split()))))
 old=int(x['seats']);matched.append({'constituency_id':x['constituency_id'],'name':x['name'],'old_seats':old,'source_name':cand['name'],'source_seats':cand['seats']})
 if old!=cand['seats']:diff.append(matched[-1])
out={'source_url':url,'rows_in_source':len(source),'source_total_seats':sum(z['seats'] for z in source),'csv_rows':len(rows),'csv_total_seats':sum(int(x['seats']) for x in rows),'differences':diff,'matched':matched,'pass':len(source)==92 and sum(z['seats'] for z in source)==305 and len(diff)>0}
(O/'geometry_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2));raise SystemExit(0 if out['pass'] else 3)
