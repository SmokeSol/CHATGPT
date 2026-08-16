#!/usr/bin/env python3
import json,math,re,unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
import pandas as pd,requests
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
AFF={('casablanca settat','AFG'):'CNI'}

def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def alloc(v,s,n):
 q=n/s;base={p:math.floor(x/q) for p,x in v.items()};left=s-sum(base.values())
 if left<0:raise RuntimeError((s,n,q,base))
 rem={p:v[p]-base[p]*q for p in v};a=dict(base)
 for p in sorted(v,key=lambda p:(-rem[p],-v[p],p)):
  if left<=0:break
  a[p]=a.get(p,0)+1;left-=1
 return {p:k for p,k in a.items() if k}
def aff(region,a):
 c=Counter();rk=norm(region)
 for p,n in a.items():c[AFF.get((rk,p),p)]+=n
 return dict(c)
def main():
 cross=json.loads((O/'regional_registered_crossballot.json').read_text())['registered_by_region'];obs=json.loads((O/'observed_elected_2021.json').read_text())['regional']
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();df=pd.read_excel(BytesIO(r.content),sheet_name='donnees');party=[c for c in df.columns if c not in META];reg=df[df['typeListe'].astype(str).str.lower().eq('regionale')]
 rows=[];passes=0
 aliases={'beni mellal khenifra':'beni mellal khenifra','casablanca settat':'casablanca settat','dakhla oued ed dahab':'dakhla oued ed dahab','draa tafilalet':'draa tafilalet','fes meknes':'fes meknes','guelmim oued noun':'guelmim oued noun','laayoune sakia el hamra':'laayoune sakia el hamra','marrakech safi':'marrakech safi','oriental':'oriental','rabat sale kenitra':'rabat sale kenitra','souss massa':'souss massa','tanger tetouan al hoceima':'tanger tetouan al hoceima'}
 cross_norm={norm(k):v for k,v in cross.items()};obs_norm={norm(k):v for k,v in obs.items()}
 for _,row in reg.iterrows():
  region=str(row['region']);rk=norm(region);n=cross_norm.get(rk);expected=obs_norm.get(rk)
  if n is None or expected is None:raise RuntimeError({'region':region,'rk':rk,'cross_keys':sorted(cross_norm),'obs_keys':sorted(obs_norm)})
  votes={str(c):int(row[c]) for c in party if pd.notna(row[c]) and float(row[c])>0};s=int(row['nSieges']);a=alloc(votes,s,n);aa=aff(region,a);ok=aa==expected;passes+=ok
  rows.append({'region':region,'registered_external':n,'seats':s,'votes':votes,'legal_list_allocation':a,'parliamentary_affiliation_allocation':aa,'observed_independent':expected,'exact_match':ok,'quotient':n/s})
 out={'method':'TAFRA House regional votes + external same-day regional registered counts + LO 04-21 article 84; observed elected are independent TAFRA/Parliament member ground truth','regions':len(rows),'exact_matches':passes,'all_12_exact':passes==12,'rows':rows,'aggregate_registered_external':sum(x['registered_external'] for x in rows),'note':'Aggregate cross-ballot electorate is not asserted equal to HCP national roll; this test uses each regional denominator solely as an independently observed external input and judges it by exact out-of-sample legal reproduction.'}
 (O/'regional_exact_crossballot_test.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'regions':12,'exact_matches':passes,'all_12_exact':out['all_12_exact'],'rows':[{'region':x['region'],'N':x['registered_external'],'allocation':x['parliamentary_affiliation_allocation'],'observed':x['observed_independent'],'ok':x['exact_match']} for x in rows]},ensure_ascii=False,indent=2));raise SystemExit(0 if out['all_12_exact'] else 3)
if __name__=='__main__':main()
