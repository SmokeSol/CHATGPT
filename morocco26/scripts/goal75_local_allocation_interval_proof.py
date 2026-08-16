#!/usr/bin/env python3
import json,math
from io import BytesIO
from pathlib import Path
import pandas as pd,requests
R=Path(__file__).resolve().parents[1];O=R/'data'/'goal75'
URL='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
UPPER=18000000

def alloc(v,s,n):
 q=n/s;base={p:math.floor(x/q) for p,x in v.items()};left=s-sum(base.values())
 if left<0:return None
 rem={p:v[p]-base[p]*q for p in v};a=dict(base)
 for p in sorted(v,key=lambda p:(-rem[p],-v[p],p)):
  if left<=0:break
  a[p]=a.get(p,0)+1;left-=1
 return {p:k for p,k in a.items() if k}
def candidate_ns(v,s,L,U):
 # Exact critical-point enumeration for integer N. Between quota-floor thresholds
 # and pairwise remainder crossings, allocation is constant.
 points={float(L),float(U)}
 for x in v.values():
  for k in range(1,s+1):
   z=x*s/k
   if L<=z<=U:points.add(z)
 base=sorted(points);extra=set()
 for lo,hi in zip(base,base[1:]):
  if hi-lo<=1e-12:continue
  mid=(lo+hi)/2;q=mid/s;k={p:math.floor(x/q) for p,x in v.items()}
  ps=list(v)
  for i,p in enumerate(ps):
   for r in ps[i+1:]:
    dk=k[p]-k[r]
    if dk==0:continue
    z=s*(v[p]-v[r])/dk
    if lo<z<hi:extra.add(z)
 crit=sorted(set(base)|extra);ints={L,U}
 for z in crit:
  f=math.floor(z);c=math.ceil(z)
  for n in (f-2,f-1,f,f+1,f+2,c-2,c-1,c,c+1,c+2):
   if L<=n<=U:ints.add(int(n))
 # Also one integer in every gap between adjacent critical real values.
 for a,b in zip(crit,crit[1:]):
  lo=math.floor(a)+1;hi=math.ceil(b)-1
  if lo<=hi:
   ints.add(lo);ints.add(hi);ints.add((lo+hi)//2)
 return sorted(ints),len(crit)
def main():
 r=requests.get(URL,timeout=60,headers={'User-Agent':'MOROCCO26 research'});r.raise_for_status();df=pd.read_excel(BytesIO(r.content),sheet_name='donnees');party=[c for c in df.columns if c not in META];loc=df[df['typeListe'].astype(str).str.lower().eq('locale')]
 rows=[];passed=0
 for _,row in loc.iterrows():
  votes={str(c):int(row[c]) for c in party if pd.notna(row[c]) and float(row[c])>0};s=int(row['nSieges']);L=sum(votes.values());target={p:1 for p in sorted(votes,key=lambda p:(-votes[p],p))[:s]};ns,ncrit=candidate_ns(votes,s,L,UPPER);outs={};bad=[]
  for n in ns:
   a=alloc(votes,s,n);key=json.dumps(a,sort_keys=True);outs.setdefault(key,{'allocation':a,'example_N':n})
   if a!=target:bad.append({'N':n,'allocation':a})
  ok=not bad;passed+=ok
  rows.append({'idCirconscription':str(row['idCirconscription']),'region':str(row['region']),'circonscription':str(row['circonscription']),'seats':s,'lower_bound_registered':L,'upper_bound_registered':UPPER,'target_topN_one_each':target,'critical_real_points':ncrit,'integer_test_points':len(ns),'distinct_allocations':[x for x in outs.values()],'invariant_to_topN_over_full_interval':ok,'first_counterexamples':bad[:10]})
 out={'logic':'Exact piecewise proof: quota floors change only at N=v*s/k; with floors fixed, remainders are linear in N and their ordering changes only at pairwise crossings. We evaluate all adjacent integer neighborhoods and one or more interior integers per critical interval. Thus allocation invariance over [valid-party-votes,18,000,000] is exhaustive for integer registered counts.','local_rows':len(rows),'invariant_full_interval':passed,'not_invariant':len(rows)-passed,'all_92_invariant':passed==92,'rows':rows}
 (O/'local_allocation_interval_proof.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'local_rows':len(rows),'invariant_full_interval':passed,'not_invariant':len(rows)-passed,'exceptions':[{'circonscription':x['circonscription'],'distinct_allocations':x['distinct_allocations'][:4]} for x in rows if not x['invariant_to_topN_over_full_interval']]},ensure_ascii=False,indent=2));raise SystemExit(0 if out['all_92_invariant'] else 2)
if __name__=='__main__':main()
