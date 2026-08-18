#!/usr/bin/env python3
from __future__ import annotations
import json,re,unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
M26=ROOT/'morocco26'; G=M26/'data'/'goal100'; CI=G/'e_collect'/'candidate_intelligence_v2'
RAW=G/'b2_raw_acquisition'/'HF_CHAMBER_MEMBERS_MULTIYEAR'/'data'
BASE16=CI/'2016'/'pjd_closed_universe_incumbency_v1.jsonl'; BASE21=CI/'2021'/'pjd_closed_universe_incumbency_v1.jsonl'
CLAIM16=CI/'2016'/'pjd_explicit_prior_mp_claims_v1.json'; CLAIM21=CI/'2021'/'pjd_explicit_prior_mp_claims_v1.json'
OVR=CI/'identity_overrides_v1.json'; OUT=CI/'candidate_intelligence_v2_reconciled_power_gate_v1.json'
DET16=CI/'2016'/'pjd_reconciled_head_prior_mp_v1.jsonl'; DET21=CI/'2021'/'pjd_reconciled_head_prior_mp_v1.jsonl'
MIN_TERR=74; MIN_POS=30
AR_DIACRITICS=re.compile(r'[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed]')

def nar(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKC',s).replace('ـ',''); s=AR_DIACRITICS.sub('',s)
 s=re.sub(r'[إأآٱ]','ا',s).replace('ى','ي').replace('ؤ','و').replace('ئ','ي').replace('هللا','الله')
 s=re.sub(r'\bامل','الم',s); s=re.sub(r'\bاإل','ال',s); s=re.sub(r'اال','ال',s); s=re.sub(r'\s+ي\b','ي',s)
 s=re.sub(r'[^\u0621-\u063a\u0641-\u064a0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def nlat(x):
 s='' if x is None else str(x); s=unicodedata.normalize('NFKD',s); s=''.join(c for c in s if not unicodedata.combining(c)); s=s.lower().replace('’',"'")
 repl=[(r'\bmohamm?ed\b|\bmohamad\b','mohamed'),(r'\bmostafa\b|\bmostapha\b|\bmustafa\b','mustapha'),(r'\bbrahim\b','ibrahim'),(r'\bsaad eddine\b|\bsaadeddine\b','saadeddine'),(r'\botmani\b','othmani'),(r'\bharris\b','haris'),(r'\belharti\b','el harti'),(r'\btoufall?a\b','toufla'),(r'\bmarzouk\b','merzouk'),(r'\babdellah\b|\babdallah\b|\babdullah\b','abdallah')]
 for a,b in repl:s=re.sub(a,b,s)
 s=re.sub(r'[^a-z0-9]+',' ',s).strip(); return re.sub(r'\s+',' ',s)
def read_jsonl(p):return [json.loads(x) for x in p.read_text(encoding='utf-8').splitlines() if x.strip()]
def col(df,*names):
 m={str(c).lower():str(c) for c in df.columns}
 for n in names:
  if n.lower() in m:return m[n.lower()]
 raise KeyError(names)
def load_u(parl):
 df=pd.concat([pd.read_parquet(p) for p in sorted(RAW.glob('*.parquet'))],ignore_index=True)
 cp=col(df,'parlement'); ce=col(df,'motifentree','motif_entree'); cl=col(df,'prenomnom','prenom_nom'); ca=col(df,'prenomnomar','prenom_nom_ar'); cparty=col(df,'parti','partipolitique','appartenancepolitique','formationpolitique'); ct=col(df,'circonscription')
 u=df[df[cp].astype(str).str.strip().eq(parl)].copy(); u=u[u[ce].astype(str).str.casefold().str.strip().eq('elu')].copy(); assert len(u)==395
 return u,{'lat':cl,'ar':ca,'party':cparty,'territory':ct}
def exact_prior(u,c,prior_name,arabic):
 norm=nar if arabic else nlat; nc=c['ar'] if arabic else c['lat']; q=norm(prior_name)
 hits=u[u[nc].fillna('').astype(str).map(norm).eq(q)]
 return hits.iloc[0] if len(hits)==1 else None
def best_pjd(u,c,name,arabic):
 norm=nar if arabic else nlat; nc=c['ar'] if arabic else c['lat']; p=u[u[c['party']].astype(str).str.upper().str.contains('PJD',na=False)].copy()
 q=norm(name); ranked=[]
 for _,r in p.iterrows():
  z=norm(r[nc]);
  if not z:continue
  seq=SequenceMatcher(None,q,z).ratio(); qt=set(q.split()); zt=set(z.split()); jac=len(qt&zt)/len(qt|zt) if qt|zt else 0.; score=.78*seq+.22*jac
  ranked.append((score,seq,jac,r))
 ranked.sort(reverse=True,key=lambda x:x[0]); return ranked[:2]
def corroborate_claim(u,c,name,arabic):
 ranked=best_pjd(u,c,name,arabic)
 if not ranked:return None,{'status':'NO_PJD_PRIOR'}
 b=ranked[0]; second=ranked[1][0] if len(ranked)>1 else 0.; gap=b[0]-second
 # The source claim already states outgoing-MP status. This matcher is only identity corroboration.
 if b[1]>=0.72 and b[0]>=0.72 and gap>=0.04:
  return b[3],{'status':'CORROBORATED','score':round(b[0],6),'sequence':round(b[1],6),'jaccard':round(b[2],6),'gap':round(gap,6)}
 return None,{'status':'UNRESOLVED','score':round(b[0],6),'sequence':round(b[1],6),'jaccard':round(b[2],6),'gap':round(gap,6),'best_name':str(b[3][c['ar'] if arabic else c['lat']])}
def reconcile(base,claims,overrides,u,c,arabic,name_key):
 byname={r[name_key]:dict(r) for r in base}; claimmap={r[name_key]:r for r in claims['claims']}
 # audited 2016 aliases
 for o in overrides:
  cur=o['current_name']; r=byname.get(cur)
  if not r:continue
  if o['status']=='CONFIRMED_NO_ALIAS':
   r['feature_state']='VERIFIED_FALSE'; r['reconciliation']='AUDITED_NO_ALIAS_CLOSED_UNIVERSE'
  elif o['status']=='SAFE_ALIAS':
   m=exact_prior(u,c,o['prior_name'],arabic)
   if m is not None:
    r['feature_state']='VERIFIED_TRUE'; r['reconciliation']='AUDITED_SAFE_ALIAS_TO_CLOSED_UNIVERSE'; r['prior_member_name']=str(m[c['ar'] if arabic else c['lat']]); r['prior_member_party']=str(m[c['party']]); r['prior_member_territory']=str(m[c['territory']])
 # explicit pre-election MP claims + closed-universe corroboration
 for cur,claim in claimmap.items():
  r=byname.get(cur)
  if not r:continue
  if r.get('feature_state')=='VERIFIED_TRUE':
   r['explicit_prior_mp_claim']=True; continue
  m,diag=corroborate_claim(u,c,cur,arabic)
  r['explicit_prior_mp_claim']=True; r['claim_corroboration']=diag
  if m is not None:
   r['feature_state']='VERIFIED_TRUE'; r['reconciliation']='EXPLICIT_PRE_ELECTION_MP_CLAIM_PLUS_CLOSED_UNIVERSE'; r['prior_member_name']=str(m[c['ar'] if arabic else c['lat']]); r['prior_member_party']=str(m[c['party']]); r['prior_member_territory']=str(m[c['territory']])
 return list(byname.values())
def summ(rows):
 st=Counter(r['feature_state'] for r in rows); known=st['VERIFIED_TRUE']+st['VERIFIED_FALSE']; terr=len({r['territory_id'] for r in rows if r['feature_state'] in ('VERIFIED_TRUE','VERIFIED_FALSE')})
 return {'rows':len(rows),'territories_known':terr,'states':dict(sorted(st.items())),'positive_instances':st['VERIFIED_TRUE'],'coverage_gate':terr>=MIN_TERR,'support_gate':st['VERIFIED_TRUE']>=MIN_POS,'gate_pass':terr>=MIN_TERR and st['VERIFIED_TRUE']>=MIN_POS}
def write(p,rows):p.write_text('\n'.join(json.dumps(x,ensure_ascii=False,sort_keys=True) for x in rows)+'\n',encoding='utf-8')
def main():
 u11,c11=load_u('2011-2016'); u16,c16=load_u('2016-2021'); base16=read_jsonl(BASE16); base21=read_jsonl(BASE21); cl16=json.loads(CLAIM16.read_text()); cl21=json.loads(CLAIM21.read_text()); o=json.loads(OVR.read_text())
 r16=reconcile(base16,cl16,o['2016'],u11,c11,True,'candidate_name_ar'); r21=reconcile(base21,cl21,o['2021'],u16,c16,False,'candidate_name_fr'); write(DET16,r16); write(DET21,r21)
 s16=summ(r16); s21=summ(r21); passed=s16['gate_pass'] and s21['gate_pass']
 result={'schema_version':'1.0','gate_id':'M26-CANDIDATE-INTEL-V2-RECONCILED-DATA-POWER-GATE-V1','status':'PASS_RECONCILED_HEAD_PRIOR_MP_DATA_POWER' if passed else 'FAIL_RECONCILED_HEAD_PRIOR_MP_DATA_POWER','thresholds':{'minimum_known_territories_each_transition':MIN_TERR,'minimum_positive_instances_each_transition':MIN_POS},'2011_TO_2016':s16,'2016_TO_2021':s21,'feature_id':'V2_HEAD_PRIOR_CYCLE_MP','coefficient_authorized':False,'forecast_modified':False,'reasoner_identifiability':'NOT_YET_PASSED_SINGLE_FEATURE_ONLY','note':'This gate establishes data power for one head-of-list incumbency feature only. It does not establish predictive value or LLM-reasoner value.'}
 OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8'); print(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True))
if __name__=='__main__':main()
