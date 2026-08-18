#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, pathlib
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder

IND_FEATURES=['mil','AGE5','sexe','LIEN_CM','E_MAT','NIV_ET_AGR','SEC_ENS','scol','LIR_ECR','LANG1','LANG2','EG_DIP_SGG','LANG_LOC1','TY_ACT','PROF_GG','STAT_PROF','ACT_SECTEUR','TRAV_LIEU','TRAV_TRANS','NIV_ET','EG_DIP_GG_DET','PROF_SGG','ACT_SECTION']
HH_FEATURES=['taille','TYPE_LOG','murs','toit','sol','AGE_LOG','pieces','STAT_OCC','cuis','wc','bd','bloc','ECL_MODE','EAU_MODE','EAU_DIST','EAU_DUR','EAUX_US','dech','gaz','elec','char','bois','DEJ_ANIM','tele','radio','TEL_PORT','TEL_FIXE','net','pc','parab','frigo','cam','voit','tract','moto','ROUTE_DIST','MEN_TYPE']
R0=['mil','AGE5','sexe','NIV_ET_AGR','TY_ACT'];JOIN=['reg','pro','MEN_PRO'];HELP=['AGE1','NOR_MEN','pds'];NUMERIC_TO_BIN=['taille','pieces','EAU_DIST','EAU_DUR','cam','voit','tract','moto','ROUTE_DIST']

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for b in iter(lambda:f.read(1024*1024),b''):h.update(b)
 return h.hexdigest()
def adult(df):
 a=pd.to_numeric(df['AGE1'],errors='coerce');g=pd.to_numeric(df['AGE5'],errors='coerce');return ((a>=18)&(a<=24))|(a==98)|(g>=20)
def deterministic_sample(df,mod=23):
 h=sum(pd.to_numeric(df[c],errors='coerce').fillna(-1).astype('int64')*m for c,m in [('reg',1000003),('pro',1000033),('MEN_PRO',1000037),('NOR_MEN',1000081)]);return (h.abs()%mod)==0
def bin_numeric(s):
 x=pd.to_numeric(s,errors='coerce');ok=x.notna();out=pd.Series(['__MISS__']*len(s),index=s.index,dtype='object')
 if ok.sum()<20:return out
 try:out.loc[ok]=pd.qcut(x[ok],q=min(10,int(x[ok].nunique())),duplicates='drop').astype(str)
 except Exception:out.loc[ok]=x[ok].astype(str)
 return out
def encoded(df,cols):
 z=pd.DataFrame(index=df.index)
 for c in cols:z[c]=bin_numeric(df[c]) if c in NUMERIC_TO_BIN else df[c].astype('object').where(df[c].notna(),'__MISS__').astype(str)
 enc=OneHotEncoder(handle_unknown='ignore',min_frequency=25,sparse_output=True,dtype=np.float64);X=enc.fit_transform(z);return X
def effective_rank(X,w):
 w=np.asarray(w,float);w=np.where(np.isfinite(w)&(w>0),w,1.0);w=w/w.sum();mu=np.asarray(X.T@w).ravel();Xw=X.multiply(np.sqrt(w)[:,None]);second=(Xw.T@Xw).toarray();cov=second-np.outer(mu,mu);var=np.clip(np.diag(cov),0,None);keep=var>1e-10;cov=cov[np.ix_(keep,keep)];var=var[keep]
 if len(var)==0:return {'effective_rank':0.0,'encoded_columns':int(X.shape[1]),'nonzero_variance_columns':0}
 sd=np.sqrt(var);corr=cov/(sd[:,None]*sd[None,:]);corr=(corr+corr.T)/2;eig=np.linalg.eigvalsh(corr);eig=eig[eig>1e-9];p=eig/eig.sum();return {'effective_rank':float(np.exp(-(p*np.log(p)).sum())),'encoded_columns':int(X.shape[1]),'nonzero_variance_columns':int(len(eig)),'largest_eigenvalue_share':float(eig.max()/eig.sum())}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--individual',required=True);ap.add_argument('--household',required=True);ap.add_argument('--out',required=True);a=ap.parse_args()
 hhcols=list(dict.fromkeys(JOIN+HH_FEATURES));hh=pd.read_stata(a.household,columns=hhcols,convert_categoricals=False,preserve_dtypes=False)
 for c in JOIN:hh[c]=pd.to_numeric(hh[c],errors='coerce').astype('Int64')
 hh=hh.drop_duplicates(JOIN,keep='first');use=list(dict.fromkeys(JOIN+HELP+IND_FEATURES));parts=[];seen=adult_seen=0
 for ch in pd.read_stata(a.individual,columns=use,convert_categoricals=False,preserve_dtypes=False,chunksize=200000):
  seen+=len(ch);mask=adult(ch);adult_seen+=int(mask.sum());ch=ch.loc[mask];ch=ch.loc[deterministic_sample(ch)];parts.append(ch)
 ind=pd.concat(parts,ignore_index=True)
 for c in JOIN:ind[c]=pd.to_numeric(ind[c],errors='coerce').astype('Int64')
 joined=ind.merge(hh,on=JOIN,how='left',indicator=True);join_rate=float((joined['_merge']=='both').mean());joined=joined[joined['_merge']=='both'].copy();w=pd.to_numeric(joined['pds'],errors='coerce').fillna(1.0).to_numpy(float)
 e0=effective_rank(encoded(joined,R0),w);e1=effective_rank(encoded(joined,IND_FEATURES+HH_FEATURES),w);ratio=e1['effective_rank']/e0['effective_rank'];miss={c:float(joined[c].isna().mean()) for c in IND_FEATURES+HH_FEATURES};over80=sorted(c for c,v in miss.items() if v>0.8)
 gates={'join_rate_ge_0_99':join_rate>=0.99,'observed_fields_ge_60':len(IND_FEATURES+HH_FEATURES)>=60,'surface_ratio_ge_10':len(IND_FEATURES+HH_FEATURES)/len(R0)>=10,'no_qualifying_field_over_80pct_missing':len(over80)==0,'R1_effective_rank_ge_20':e1['effective_rank']>=20,'effective_rank_ratio_ge_3':ratio>=3};result={'schema_version':'1.1','audit_id':'M26-ASV2-RICH-MICROFOUNDATION-INFORMATION-AUDIT-V1','status':'PASS' if all(gates.values()) else 'FAIL','individual_sha256':sha(a.individual),'household_sha256':sha(a.household),'records_seen':seen,'adult_records_seen':adult_seen,'deterministic_adult_sample_before_join':len(ind),'joined_sample_rows':len(joined),'join_rate':join_rate,'R0_social_raw_fields':len(R0),'R1_qualifying_observed_raw_fields':len(IND_FEATURES+HH_FEATURES),'surface_ratio':len(IND_FEATURES+HH_FEATURES)/len(R0),'R0_effective_rank':e0,'R1_effective_rank':e1,'effective_rank_ratio':ratio,'missingness_fraction':miss,'qualifying_fields_over_80pct_missing':over80,'gates':gates,'target_outcomes_loaded':False,'real_llm_outputs_loaded':False}
 pathlib.Path(a.out).write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
