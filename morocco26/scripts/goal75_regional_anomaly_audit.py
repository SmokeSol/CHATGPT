#!/usr/bin/env python3
import json,math
from io import StringIO
from pathlib import Path
from urllib.parse import quote
import pandas as pd
import goal75_stage1 as g
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75'
REGIONS=[('Rabat-Salé-Kénitra',10),('Laâyoune-Sakia El Hamra',5),('Dakhla-Oued Eddahab',3),('Drâa-Tafilalet',6),('Casablanca-Settat',12),('Souss-Massa',7),('Guelmim-Oued Noun',5),('Marrakech-Safi',10),('Tanger-Tétouan-Al Hoceïma',8),('Oriental',7),('Fès-Meknès',10),('Béni Mellal-Khénifra',7)]
SLUG={'Dakhla-Oued Eddahab':'Circonscription_de_Dakhla-Oued_Ed-Dahab','Oriental':"Circonscription_d%27Oriental"}
def parse(df):
 df=g.flatcols(df);vcs=[c for c in df.columns if 'Voix' in c and '%' not in c] or [c for c in df.columns if 'Voix' in c]
 vc=vcs[0];votes={};reg=exp=None
 for _,r in df.iterrows():
  text=' | '.join(str(v) for v in r.tolist());nt=g.norm(text);v=g.nint(r[vc])
  if 'inscrits' in nt:reg=v;continue
  if 'exprimes' in nt:exp=v;continue
  p=g.party(text)
  if p and v is not None:votes[p]=votes.get(p,0)+v
 return votes,reg,exp
def main():
 rows=[]
 for name,seats in REGIONS:
  slug=SLUG.get(name,'Circonscription_de_'+quote(name.replace(' ','_'),safe="_()'-"));url='https://fr.wikipedia.org/wiki/'+slug;html=g.get(url).text;tabs=[d for d in pd.read_html(StringIO(html)) if 'Parti' in ' '.join(map(str,d.columns)) and 'Voix' in ' '.join(map(str,d.columns))];votes,reg,exp=parse(tabs[-1]);s=sum(votes.values());q=reg/seats if reg else None;direct={p:math.floor(v/q) for p,v in votes.items()} if q else {};rows.append({'region':name,'seats':seats,'registered':reg,'expressed':exp,'recognized_vote_sum':s,'recognized_over_registered':s/reg if reg else None,'recognized_over_expressed':s/exp if exp else None,'direct_seat_sum':sum(direct.values()),'direct':{p:n for p,n in direct.items() if n},'source_url':url,'anomaly':(not reg) or s>reg or (exp and exp>reg) or sum(direct.values())>seats or (exp and abs(s-exp)/exp>.03)})
 out={'regions':12,'configured_seats':sum(x[1] for x in REGIONS),'anomaly_count':sum(r['anomaly'] for r in rows),'rows':rows};(O/'regional_anomaly_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
main()
