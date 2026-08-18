#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
M26=ROOT/'morocco26'; G=M26/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
RAW=G/'b2_raw_acquisition'/'HF_CHAMBER_MEMBERS_MULTIYEAR'/'data'
OUT=CI/'identity_diagnostic_v1.json'
AR_DIACRITICS=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=AR_DIACRITICS.sub('',s)
 s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله')
 s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'\s+ي\b','ي',s); s=re.sub(r'اال','ال',s)
 s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def nlat(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKD',s); s=''.join(c for c in s if not unicodedata.combining(c)); s=s.lower()
 s=re.sub(r'\bmohamm?ed\b|\bmohamad\b','mohamed',s); s=re.sub(r'\babdellah\b|\babdallah\b|\babdullah\b','abdallah',s)
 s=re.sub(r'[^a-z0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def col(df,*names):
 m={str(c).lower():str(c) for c in df.columns}
 for n in names:
  if n.lower() in m:return m[n.lower()]
 raise KeyError(names)
def universe(df,parl):
 cp=col(df,'parlement'); cm=col(df,'motifentree','motif_entree')
 p=df[df[cp].astype(str).str.strip().eq(parl)].copy(); p=p[p[cm].astype(str).str.casefold().str.strip().eq('elu')].copy()
 assert len(p)==395
 return p

def diagnose(roster_path,parl,arabic):
 roster=json.loads(roster_path.read_text())['rows']; df=pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob('*.parquet'))],ignore_index=True); u=universe(df,parl)
 namecol=col(u,'prenomnomar','prenom_nom_ar') if arabic else col(u,'prenomnom','prenom_nom'); partycol=col(u,'parti','partipolitique','appartenancepolitique','formationpolitique'); terrcol=col(u,'circonscription')
 normal=nar if arabic else nlat; key='candidate_name_ar' if arabic else 'candidate_name_fr'
 out=[]
 for r in roster:
  q=normal(r[key]); ranked=[]
  for _,m in u.iterrows():
   z=normal(m[namecol]);
   if not z: continue
   seq=SequenceMatcher(None,q,z).ratio(); qt=set(q.split()); zt=set(z.split()); jac=len(qt&zt)/len(qt|zt) if qt|zt else 0
   score=.75*seq+.25*jac
   ranked.append((score,seq,jac,str(m[namecol]),str(m[partycol]),str(m[terrcol])))
  ranked.sort(reverse=True,key=lambda x:x[0]); b=ranked[0]; s=ranked[1]
  out.append({**r,'query_norm':q,'best':{'score':round(b[0],6),'sequence':round(b[1],6),'jaccard':round(b[2],6),'name':b[3],'party':b[4],'territory':b[5]},'runner_up_score':round(s[0],6),'gap':round(b[0]-s[0],6)})
 return out

def main():
 res={'2016':diagnose(CI/'2016'/'pjd_closed_roster_v1.json','2011-2016',True),'2021':diagnose(CI/'2021'/'pjd_closed_roster_v1.json','2016-2021',False)}
 OUT.write_text(json.dumps(res,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); print(json.dumps({'2016_rows':len(res['2016']),'2021_rows':len(res['2021'])}))
if __name__=='__main__':main()
