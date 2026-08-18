#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]; G=ROOT/'morocco26'/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
A=CI/'2021'/'pjd_reconciled_head_prior_mp_v1.jsonl'; BR=CI/'2021'/'pjd_arabic_identity_bridge_74_v1.json'; RAW=G/'b2_raw_acquisition'/'HF_CHAMBER_MEMBERS_MULTIYEAR'/'data'; OUT=CI/'2021'/'pjd_mp_unknown_arabic_diagnostic_v1.json'
DIAC=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')
def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=DIAC.sub('',s); s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله'); s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def first_col(df,*names):
 low={str(c).lower():str(c) for c in df.columns}
 for n in names:
  if n.lower() in low:return low[n.lower()]
 raise KeyError(names)
def main():
 frames=[pd.read_parquet(p) for p in sorted(RAW.glob('*.parquet'))]; df=pd.concat(frames,ignore_index=True); pc=first_col(df,'parlement'); rc=first_col(df,'motifentree','motif_entree'); ac=first_col(df,'prenomnomar','prenom_nom_ar'); lc=first_col(df,'prenomnom','prenom_nom'); tc=first_col(df,'circonscription')
 party=None
 for c in ('parti','partipolitique','appartenancepolitique','formationpolitique'):
  try: party=first_col(df,c); break
  except KeyError: pass
 u=df[df[pc].astype(str).str.strip().eq('2016-2021')].copy(); u=u[u[rc].astype(str).str.casefold().str.strip().eq('elu')].copy()
 if len(u)!=395: raise RuntimeError(f'expected 395 prior members, got {len(u)}')
 bridge={x['territory_id']:x for x in json.loads(BR.read_text(encoding='utf-8'))['rows']}; unknown=[json.loads(x) for x in A.read_text(encoding='utf-8').splitlines() if x.strip() and json.loads(x).get('feature_state')=='UNKNOWN' and json.loads(x).get('territory_id') in bridge]
 idx=defaultdict(list)
 for i,r in u.iterrows():
  n=nar(r.get(ac,''))
  if n: idx[n].append(r)
 universe_names=list(idx); out=[]
 for x in unknown:
  b=bridge[x['territory_id']]; q=nar(b['candidate_name_ar']); exact=idx.get(q,[]); ranked=[]
  for n in universe_names:
   sc=SequenceMatcher(None,q,n).ratio()
   if sc>=.65: ranked.append((sc,n,idx[n]))
  ranked.sort(key=lambda z:z[0],reverse=True)
  top=[]
  for sc,n,rs in ranked[:4]:
   rr=rs[0]; top.append({'score':round(sc,6),'name_ar':str(rr.get(ac,'')),'name_lat':str(rr.get(lc,'')),'territory':str(rr.get(tc,'')),'party':None if party is None else str(rr.get(party,''))})
  item={'territory_id':x['territory_id'],'candidate_name_fr':x['candidate_name_fr'],'candidate_name_ar':b['candidate_name_ar'],'exact_arabic_match_count':len(exact),'top_candidates':top}; out.append(item)
  print('MPAR21\t'+x['territory_id']+'\t'+x['candidate_name_fr']+'\t'+b['candidate_name_ar']+'\tEXACT='+str(len(exact))+'\tTOP='+(json.dumps(top[0],ensure_ascii=False) if top else '-'))
 OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print('UNKNOWN_IN_BRIDGE='+str(len(out)))
if __name__=='__main__':main()
