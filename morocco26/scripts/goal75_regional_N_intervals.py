#!/usr/bin/env python3
import json,math,re,unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
import pandas as pd,requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75'
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
AFF={('casablanca settat','AFG'):'CNI'}
def norm(x):return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def alloc(v,s,n):
 q=n/s;base={p:math.floor(x/q) for p,x in v.items()};left=s-sum(base.values())
 if left<0:return None
 rem={p:v[p]-base[p]*q for p in v};a=dict(base)
 for p in sorted(v,key=lambda p:(-rem[p],-v[p],p)):
  if left<=0:break
  a[p]=a.get(p,0)+1;left-=1
 return {p:k for p,k in a.items() if k}
def aff(region,a):
 c=Counter();rk=norm(region)
 for p,n in (a or {}).items():c[AFF.get((rk,p),p)]+=n
 return dict(c)
def crit(v,s,L,U):
 pts={float(L),float(U+1)}
 for x in v.values():
  for k in range(1,s+1):
   z=x*s/k
   if L<=z<=U+1:pts.add(z)
 # pairwise remainder crossings, floors fixed per base interval
 base=sorted(pts);extra=set();ps=list(v)
 for lo,hi in zip(base,base[1:]):
  if hi-lo<1e-9:continue
  mid=(lo+hi)/2;q=mid/s;fl={p:math.floor(v[p]/q) for p in ps}
  for i,p in enumerate(ps):
   for r in ps[i+1:]:
    dk=fl[p]-fl[r]
    if dk==0:continue
    z=s*(v[p]-v[r])/dk
    if lo<z<hi:extra.add(z)
 return sorted(pts|extra)
def intervals(v,s,target,L,U):
 cs=crit(v,s,L,U);segments=[]
 bounds=sorted({L,U+1,*[max(L,min(U+1,x)) for x in cs]})
 for a,b in zip(bounds,bounds[1:]):
  lo=max(L,math.ceil(a));hi=min(U,math.ceil(b)-1)
  if lo>hi:continue
  probes={lo,hi,(lo+hi)//2}
  ok=all(aff('',{})=={} for _ in [0])
  allocations=[alloc(v,s,n) for n in probes]
  # allocation is constant in open critical interval by construction; endpoints represented by integer neighborhoods.
  segments.append((lo,hi,allocations[0]))
 # merge by target match after caller affiliation mapping
 return segments
def main():
 obs=json.loads((O/'observed_elected_2021.json').read_text())['regional'];obs={norm(k):v for k,v in obs.items()}
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();df=pd.read_excel(BytesIO(r.content),sheet_name='donnees');party=[c for c in df.columns if c not in META];reg=df[df['typeListe'].astype(str).str.lower().eq('regionale')]
 rows=[]
 for _,row in reg.iterrows():
  region=str(row['region']);s=int(row['nSieges']);v={str(c):int(row[c]) for c in party if pd.notna(row[c]) and float(row[c])>0};target=obs[norm(region)];L=sum(v.values());U=17509127
  # exhaustive integer breakpoints via direct candidate enumeration around all criticals + one representative in each interval, then build maximal ranges with same correctness.
  cs=crit(v,s,L,U);test={L,U}
  for z in cs:
   f=math.floor(z);c=math.ceil(z)
   for n in (f-2,f-1,f,f+1,f+2,c-2,c-1,c,c+1,c+2):
    if L<=n<=U:test.add(int(n))
  for a,b in zip(cs,cs[1:]):
   lo=max(L,math.floor(a)+1);hi=min(U,math.ceil(b)-1)
   if lo<=hi:test.update([lo,hi,(lo+hi)//2])
  test=sorted(test);states=[]
  for n in test:states.append((n,aff(region,alloc(v,s,n))==target))
  # Convert critical partition into exact integer intervals and evaluate representative.
  integer_breaks={L,U+1}
  for z in cs:
   integer_breaks.update([max(L,min(U+1,math.floor(z))),max(L,min(U+1,math.floor(z)+1)),max(L,min(U+1,math.ceil(z))),max(L,min(U+1,math.ceil(z)+1))])
  bb=sorted(integer_breaks);good=[]
  for a,b in zip(bb,bb[1:]):
   lo=max(L,int(a));hi=min(U,int(b)-1)
   if lo>hi:continue
   mid=(lo+hi)//2
   if aff(region,alloc(v,s,mid))==target:
    # verify endpoints
    if aff(region,alloc(v,s,lo))!=target or aff(region,alloc(v,s,hi))!=target:raise RuntimeError(('interval endpoint instability',region,lo,hi))
    if good and good[-1][1]+1==lo:good[-1][1]=hi
    else:good.append([lo,hi])
  rows.append({'region':region,'seats':s,'valid_vote_sum_lower_bound':L,'observed_affiliation':target,'good_registered_intervals':good,'good_span_total':sum(b-a+1 for a,b in good),'critical_points':len(cs)})
 out={'method':'exact piecewise Article-84 allocation intervals over all integer registered counts from valid-vote lower bound to 17,509,127; output uses observed elected only as target for diagnostic interval, not as denominator estimate','regions':12,'rows':rows}
 (O/'regional_registered_intervals.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'rows':[{'region':x['region'],'lower':x['valid_vote_sum_lower_bound'],'intervals':x['good_registered_intervals']} for x in rows]},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
