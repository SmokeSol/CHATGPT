#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, re, unicodedata, zipfile
from pathlib import Path
from collections import defaultdict
import numpy as np
import pandas as pd
import pyreadstat

N=256
SEED=260818
LEGACY_PARENT={
 'al fida mers sultan':'casablanca','ain chock':'casablanca','ain sebaa hay mohammadi':'casablanca','ben m sick':'casablanca','casablanca anfa':'casablanca','hay hassani':'casablanca','moulay rachid':'casablanca','sidi bernoussi':'casablanca',
 'aousserd':'oued ed dahab aousserd','oued eddahab':'oued ed dahab aousserd','assa zag':'tan tan assa zag','tan tan':'tan tan assa zag','es semara':'es semara tarfaya','tarfaya':'es semara tarfaya',
 'agadir ida outanan':'agadir ida outanane'}
SPLIT={
'fes-nord','fes-sud','taounate-tissa','karia-ghafsay','rabat-ocean','rabat-chellah','sale-medina','sale-el-jadida','kenitra','el-gharb','khemisset-oulmes','tiflet-rommani','bzou-ouaouizeght','azilal-demnate','medina-sidi-youssef','gueliz-nakhil','menara','taroudant-sud','taroudant-nord'}
EXPECTED={
'ind':'62dbbfc69073d52841fc3a7096113ce1342a3baec2e7e620e0f3309393fdda77',
'hh':'0c630cfaf65d02e1b2e37d8b81c0c2704f28db80115f13942d3ac0e75665319f',
'encdm':'6a3d6bbbde529254baa09a8a6171ea32c05aed1ca7e9568a3056eb69b8987dca',
'af6':'1ab8a01626244a094e97f874791576cc40270f21d135183d2e4b25ab41fa5a8d',
'af8':'5e0c8c70bb9e8488eb51866ca225a0babd5fcbf33bc0441238f8688e01a265f3'}
LABOR={2016:{'unemployment':.086,'urban_unemployment':None,'rural_unemployment':None,'youth_unemployment':.215,'female_unemployment':.099,'underemployment':.117,'activity':.472},
       2021:{'unemployment':.128,'urban_unemployment':.182,'rural_unemployment':.048,'youth_unemployment':.308,'female_unemployment':.159,'underemployment':.092,'activity':None}}

IND_COLS=['reg','pro','mil','MEN_PRO','NOR_MEN','LIEN_CM','sexe','AGE1','AGE5','E_MAT','ENF_VIV','NIV_ET_AGR','SEC_ENS','scol','LIR_ECR','EG_DIP_SGG','TY_ACT','PROF_GG','STAT_PROF','ACT_SECTEUR','TRAV_LIEU','TRAV_TRANS','NIV_ET','EG_DIP_GG_DET','PROF_SGG','ACT_SECTION','pds']
HH_COLS=['reg','pro','mil','MEN_PRO','taille','TYPE_LOG','murs','toit','sol','AGE_LOG','pieces','STAT_OCC','cuis','wc','bd','bloc','ECL_MODE','EAU_MODE','EAUX_US','dech','gaz','elec','char','bois','DEJ_ANIM','tele','radio','TEL_PORT','TEL_FIXE','net','pc','parab','frigo','cam','voit','tract','moto','ROUTE_DIST','MEN_TYPE','pds']
ENCDM_COLS=['Région_12','Milieu','Taille_ménage','Taille_agregée','Pauvre','Vulnérable','Deciles','Sexe_CM','Age_CM','Niveau_scolaire_agreg_CM','Type_activité_dominante_CM','Profession_agreg_CM','Secteur_activité_agreg_CM','Situation_profession_agreg_CM','DAM','DAM_G1','DAM_G3','DAM_G5','DAM_G6','DAM_G7']
AF6=['URBRUR','Q1','Q97','Q95','Q101','Q4A','Q4B','Q8A','Q8B','Q8E','Q14','Q30','Q41','Q52B','Q52E','Q53B','Q53D','Q66A','Q66B','Q66K','Q59B','Q92B']
AF8=['URBRUR','Q1','Q97','Q95A','Q101','Q4A','Q4B','Q7A','Q7B','Q7E','Q9','Q21','Q37','Q41B','Q41D','Q42B','Q42D','Q50A','Q50B','Q50J','Q38B','Q92I']

def sha(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def norm(s):
 s=unicodedata.normalize('NFKD',str(s)).encode('ascii','ignore').decode().lower().replace("'",' ')
 s=re.sub(r'[^a-z0-9]+',' ',s).strip()
 repl={'taroudannt':'taroudant','mohammedia':'mohammadia','moulay yacoub':'moulay yaacoub','agadir ida ou tanane':'agadir ida outanane','oued ed dahab':'oued eddahab'}
 return repl.get(s,s)

def resolve_parent(parent, available):
 p=norm(parent)
 if p in available:return p,'DIRECT_MICRODATA_ADMIN'
 q=LEGACY_PARENT.get(p)
 if q in available:return q,'PARENT_PROXY_LEGACY_2014_ADMIN'
 cand=[x for x in available if p in x or x in p]
 if len(cand)==1:return cand[0],'PARENT_PROXY_NAME_CONTAINMENT'
 return p,'UNRESOLVED'
def jsave(p,o):Path(p).write_text(json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def stable_int(*x):return int(hashlib.sha256('|'.join(map(str,x)).encode()).hexdigest()[:16],16)
def safe_int(x,default=0):
 try:
  v=float(x); return int(v) if math.isfinite(v) else default
 except:return default
def clean_num(x):
 try:
  v=float(x); return v if math.isfinite(v) else np.nan
 except:return np.nan
def code_label(meta,var,val):
 if pd.isna(val):return 'MISSING'
 d=(meta.variable_value_labels or {}).get(var,{})
 try: ks=(val,int(val) if float(val).is_integer() else val,float(val))
 except: ks=(val,)
 for k in ks:
  if k in d:return str(d[k])
 return str(int(val)) if isinstance(val,(int,float,np.number)) and float(val).is_integer() else str(val)
def age2014(row):
 a=clean_num(row.AGE1)
 if math.isfinite(a) and a<25:return int(a)
 lo=clean_num(row.AGE5)
 if not math.isfinite(lo):return None
 lo=int(lo);off=stable_int(row.pro,row.MEN_PRO,row.NOR_MEN)%5
 return min(99,lo+off)
def age_band(a):
 if a<25:return '18_24'
 if a<35:return '25_34'
 if a<45:return '35_44'
 if a<60:return '45_59'
 return '60_PLUS'
def edu_band(v):
 try:v=int(v)
 except:return 'MISSING'
 return {0:'NONE_OR_PRESCHOOL',1:'NONE_OR_PRESCHOOL',2:'PRIMARY',3:'SECONDARY',4:'SECONDARY',5:'HIGHER'}.get(v,'MISSING')
def act_band(v):
 try:v=int(v)
 except:return 'MISSING'
 if v==0:return 'ACTIVE_EMPLOYED'
 if v in (1,2):return 'UNEMPLOYED'
 return 'INACTIVE'
def sex_band(v):return 'M' if safe_int(v,-1)==1 else ('F' if safe_int(v,-1)==2 else 'MISSING')
def ur_band(v):return 'URBAN' if safe_int(v,-1)==1 else ('RURAL' if safe_int(v,-1)==2 else 'MISSING')
def labour_multiplier(activity,urban,year,base_rates):
 target=LABOR[year]
 if activity not in ('ACTIVE_EMPLOYED','UNEMPLOYED'):return 1.0
 t=target['urban_unemployment'] if urban=='URBAN' and target['urban_unemployment'] is not None else target['rural_unemployment'] if urban=='RURAL' and target['rural_unemployment'] is not None else target['unemployment']
 b=base_rates.get(urban,base_rates['ALL']);b=min(max(b,.001),.999);t=min(max(t,.001),.999)
 return (t/b) if activity=='UNEMPLOYED' else ((1-t)/(1-b))
def margins(frame,w):
 out={}
 for c in ['age_band','sex','urban_rural','education_band','activity_status']:
  s=defaultdict(float)
  for v,x in zip(frame[c],w):s[str(v)]+=float(x)
  z=sum(s.values());out[c]={k:v/z for k,v in sorted(s.items()) if v>1e-12}
 return out
def allocate_counts(target,n=N):
 cats=[k for k,v in target.items() if v>1e-12];ideal={k:target[k]*n for k in cats};cnt={k:max(1,int(math.floor(ideal[k]))) for k in cats}
 while sum(cnt.values())<n:
  k=max(cats,key=lambda q:(ideal[q]-cnt[q],target[q],q));cnt[k]+=1
 while sum(cnt.values())>n:
  rem=[k for k in cats if cnt[k]>1];k=max(rem,key=lambda q:(cnt[q]-ideal[q],cnt[q],q));cnt[k]-=1
 return cnt
def ipf(rows,targets,max_iter=600,tol=2e-8):
 w=np.ones(len(rows))/len(rows);dims=list(targets);idx={(d,k):np.flatnonzero(rows[d].astype(str).values==str(k)) for d in dims for k in targets[d]}
 for _ in range(max_iter):
  for d in dims:
   for k,t in targets[d].items():
    ii=idx[(d,k)];cur=w[ii].sum() if len(ii) else 0
    if t>1e-14 and cur<=0:return None,None
    if len(ii):w[ii]*=(t/cur if cur>0 else 0)
  w/=w.sum();err=max(abs((w[idx[(d,k)]].sum() if len(idx[(d,k)]) else 0)-t) for d in dims for k,t in targets[d].items())
  if err<tol:return w,float(err)
 return w,float(err)
def prior_assign(rows,prior,seed):
 cnt=allocate_counts(prior,len(rows));states=[]
 for k in sorted(cnt):states += [k]*cnt[k]
 rng=np.random.default_rng(seed);rng.shuffle(states);rows=rows.copy();rows['prior_vote_or_abstention']=states;return rows
def profile_asset(row):
 vals=[]
 for c in ['tele','radio','TEL_PORT','TEL_FIXE','net','pc','parab','frigo']:
  try:vals.append(1.0 if float(row[c])==1 else 0.0)
  except:pass
 for c in ['voit','moto','cam','tract']:
  try:vals.append(min(1.0,max(0.0,float(row[c]))))
  except:pass
 return float(np.mean(vals)) if vals else 0.0
def profile_services(row):
 vals=[]
 for c in ['cuis','wc','bd','bloc']:
  try:vals.append(1.0 if float(row[c])==1 else 0.0)
  except:pass
 for c in ['elec','EAU_MODE','ECL_MODE']:
  try:vals.append(1.0 if float(row[c]) not in (0,9,99) else 0.0)
  except:pass
 return float(np.mean(vals)) if vals else 0.0
def build_hh_comp(ind,year):
 a=ind['age2014'].to_numpy()+(2 if year==2016 else 7);g=ind[['pro','MEN_PRO']].copy();g['child']=(a<18).astype('int8');g['adult']=(a>=18).astype('int8');g['elderly']=(a>=65).astype('int8');ty=pd.to_numeric(ind['TY_ACT'],errors='coerce');g['worker']=(ty==0).astype('int8');g['unemployed']=ty.isin([1,2]).astype('int8');g['student']=(ty==4).astype('int8');return g.groupby(['pro','MEN_PRO'],sort=False)[['child','adult','elderly','worker','unemployed','student']].sum()
def donor_index_encdm(df):
 def eb(x):return min(5,max(0,safe_int(x,-1)))
 def ab(x):
  x=clean_num(x);return -1 if not math.isfinite(x) else 0 if x<30 else 1 if x<45 else 2 if x<60 else 3
 idx=defaultdict(list)
 for i,r in df.iterrows():
  key=(safe_int(r['Région_12'],-1),safe_int(r['Milieu'],-1),min(6,safe_int(r['Taille_ménage'],-1)),safe_int(r['Sexe_CM'],-1),ab(r['Age_CM']),eb(r['Niveau_scolaire_agreg_CM']));idx[key].append(i)
 return idx
def pick_encdm(df,idx,p,seed):
 reg=safe_int(p['reg'],-1);mil=safe_int(p['mil'],-1);size=min(6,max(1,safe_int(p.get('taille',1),1)));sx=safe_int(p.get('head_sex',p['sexe']),safe_int(p['sexe'],1));ha=clean_num(p.get('head_age_target',p['age_target']));ha=float(p['age_target']) if not math.isfinite(ha) else ha;ab=0 if ha<30 else 1 if ha<45 else 2 if ha<60 else 3;he=min(5,max(0,safe_int(p.get('head_edu',p['NIV_ET_AGR']),safe_int(p['NIV_ET_AGR'],0))));key=(reg,mil,size,sx,ab,he);cand=idx.get(key,[])
 if not cand:cand=df.index[(df['Région_12']==reg)&(df['Milieu']==mil)].tolist()
 if not cand:cand=df.index.tolist()
 return df.loc[cand[stable_int(seed,p['pro'],p['MEN_PRO'],p['NOR_MEN'])%len(cand)]]
def ses_features(r):
 dam=max(1.0,clean_num(r['DAM']) if math.isfinite(clean_num(r['DAM'])) else 1.0)
 def sh(c):
  x=clean_num(r[c]);return max(0.0,min(1.0,x/dam)) if math.isfinite(x) else None
 dec=clean_num(r['Deciles']);pau=clean_num(r['Pauvre']);vul=clean_num(r['Vulnérable'])
 return {'latent_ses_decile':None if not math.isfinite(dec) else dec/10.0,'latent_poverty_risk':None if not math.isfinite(pau) else float(pau==1),'latent_vulnerability_risk':None if not math.isfinite(vul) else float(vul==1),'latent_food_budget_share':sh('DAM_G1'),'latent_housing_energy_budget_share':sh('DAM_G3'),'latent_health_hygiene_budget_share':sh('DAM_G5'),'latent_transport_communications_budget_share':sh('DAM_G6'),'latent_education_culture_budget_share':sh('DAM_G7')}
def af_agebin(x):
 x=clean_num(x);return -1 if not math.isfinite(x) or x>110 else 0 if x<25 else 1 if x<35 else 2 if x<45 else 3 if x<60 else 4
def af_edubin(x):
 x=clean_num(x);return -1 if not math.isfinite(x) or x>20 else 0 if x<=1 else 1 if x<=3 else 2 if x<=5 else 3
def hcp_edubin(x):
 x=safe_int(x,-1);return 0 if x<=1 else 1 if x==2 else 2 if x in (3,4) else 3
def af_empbin(x):
 x=clean_num(x);return -1 if not math.isfinite(x) or x>4 else 0 if x==0 else 1 if x==1 else 2
def hcp_empbin(x):
 x=safe_int(x,-1);return 2 if x==0 else 1 if x in (1,2) else 0
def donor_index_af(df,year):
 emp='Q95' if year==2016 else 'Q95A';idx=defaultdict(list)
 for i,r in df.iterrows():
  try:key=(int(r.URBRUR),int(r.Q101),af_agebin(r.Q1),af_edubin(r.Q97),af_empbin(r[emp]));idx[key].append(i)
  except:pass
 return idx
def pick_af(df,idx,p,year,seed):
 key=(safe_int(p['mil'],-1),safe_int(p['sexe'],-1),af_agebin(p['age_target']),hcp_edubin(p['NIV_ET_AGR']),hcp_empbin(p['TY_ACT']));variants=[key,key[:4]+(-1,),key[:3]+(-1,-1),key[:2]+(-1,-1,-1)];cand=[]
 for k in variants:
  cand=idx.get(k,[])
  if cand:break
 if not cand:cand=df.index[(df.URBRUR==key[0])&(df.Q101==key[1])].tolist()
 if not cand:cand=df.index.tolist()
 return df.loc[cand[stable_int('AF',year,seed,p['pro'],p['MEN_PRO'],p['NOR_MEN'])%len(cand)]]
def scale(v,lo,hi,invalid=(8,9,98,99,-1)):
 x=clean_num(v)
 if not math.isfinite(x) or x in invalid:return None
 return max(0.0,min(1.0,(x-lo)/(hi-lo)))
def af_features(r,year):
 if year==2016:m={'economic_condition':('Q4A',1,5),'living_conditions':('Q4B',1,5),'food_deprivation':('Q8A',0,4),'water_deprivation':('Q8B',0,4),'cash_deprivation':('Q8E',0,4),'political_discussion':('Q14',0,2),'democracy_support':('Q30',1,3),'democracy_satisfaction':('Q41',0,4),'trust_parliament':('Q52B',0,3),'trust_local_government':('Q52E',0,3),'perceived_mp_corruption':('Q53B',0,3),'perceived_local_corruption':('Q53D',0,3),'government_economic_performance':('Q66A',1,4),'government_poverty_performance':('Q66B',1,4),'government_anticorruption_performance':('Q66K',1,4),'local_responsiveness':('Q59B',0,3),'internet_use':('Q92B',0,4)}
 else:m={'economic_condition':('Q4A',1,5),'living_conditions':('Q4B',1,5),'food_deprivation':('Q7A',0,4),'water_deprivation':('Q7B',0,4),'cash_deprivation':('Q7E',0,4),'political_discussion':('Q9',0,2),'democracy_support':('Q21',1,3),'democracy_satisfaction':('Q37',0,4),'trust_parliament':('Q41B',0,3),'trust_local_government':('Q41D',0,3),'perceived_mp_corruption':('Q42B',0,3),'perceived_local_corruption':('Q42D',0,3),'government_economic_performance':('Q50A',1,4),'government_poverty_performance':('Q50B',1,4),'government_anticorruption_performance':('Q50J',1,4),'local_responsiveness':('Q38B',0,3),'internet_use':('Q92I',0,4)}
 return {'latent_attitude_'+k:scale(r[q],lo,hi) for k,(q,lo,hi) in m.items()}
def fill_missing_attitudes(records):
 keys=sorted(k for k in records[0] if k.startswith('latent_attitude_'));med={k:float(np.nanmedian([r[k] if r[k] is not None else np.nan for r in records])) for k in keys}
 for r in records:
  for k in keys:
   if r[k] is None or not math.isfinite(float(r[k])):r[k]=med[k]
def effective_rank(records,fields):
 from sklearn.preprocessing import OneHotEncoder,StandardScaler
 from sklearn.compose import ColumnTransformer
 df=pd.DataFrame([{k:r.get(k) for k in fields} for r in records]);num=[c for c in df if pd.api.types.is_numeric_dtype(df[c])];cat=[c for c in df if c not in num];ct=ColumnTransformer([('num',StandardScaler(),num),('cat',OneHotEncoder(handle_unknown='ignore',sparse_output=False),cat)],sparse_threshold=0);X=np.asarray(ct.fit_transform(df),float);X=X[:,np.nanstd(X,axis=0)>1e-10]
 if X.shape[1]>700:
  rng=np.random.default_rng(SEED);X=X[:,rng.choice(X.shape[1],700,replace=False)]
 C=np.cov(X,rowvar=False);ev=np.linalg.eigvalsh(C);ev=ev[ev>1e-10];p=ev/ev.sum();return {'effective_rank':float(np.exp(-(p*np.log(p)).sum())),'encoded_columns':int(X.shape[1]),'nonzero_eigenvalues':int(len(ev))}
def main():
 ap=argparse.ArgumentParser()
 for n in ['ind','hh','encdm','af6','af8','pop2016','pop2021','outdir']:ap.add_argument('--'+n,required=True)
 a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 for k,p in [('ind',a.ind),('hh',a.hh),('encdm',a.encdm),('af6',a.af6),('af8',a.af8)]:
  s=sha(p)
  if s!=EXPECTED[k]:raise RuntimeError(f'{k} sha mismatch {s}')
 print('loading RGPH individual...');ind,im=pyreadstat.read_dta(a.ind,usecols=IND_COLS,apply_value_formats=False);ind['age2014']=[age2014(r) for r in ind.itertuples(index=False)];ind=ind[ind.age2014.notna()].copy();ind['age2014']=ind.age2014.astype(int);prolabels=(im.variable_value_labels or {}).get('pro',{});ind['pro_name']=ind['pro'].map(prolabels).fillna(ind['pro'].astype(str));ind['pro_norm']=ind.pro_name.map(norm)
 head=ind[pd.to_numeric(ind.LIEN_CM,errors='coerce')==0][['pro','MEN_PRO','sexe','age2014','NIV_ET_AGR','TY_ACT']].copy().drop_duplicates(['pro','MEN_PRO']).rename(columns={'sexe':'head_sex','age2014':'head_age2014','NIV_ET_AGR':'head_edu','TY_ACT':'head_activity'}).set_index(['pro','MEN_PRO']);comp={2016:build_hh_comp(ind,2016),2021:build_hh_comp(ind,2021)}
 print('loading household...');hh,hm=pyreadstat.read_dta(a.hh,usecols=HH_COLS,apply_value_formats=False);hh=hh.drop_duplicates(['pro','MEN_PRO']).set_index(['pro','MEN_PRO']);print('loading donor surveys...');enc,_=pyreadstat.read_sav(a.encdm,usecols=ENCDM_COLS,apply_value_formats=False);eidx=donor_index_encdm(enc);af6,_=pyreadstat.read_sav(a.af6,usecols=AF6,apply_value_formats=False);af8,_=pyreadstat.read_sav(a.af8,usecols=AF8,apply_value_formats=False);aidx={2016:donor_index_af(af6,2016),2021:donor_index_af(af8,2021)};af={2016:af6,2021:af8};pops={2016:json.load(open(a.pop2016)),2021:json.load(open(a.pop2021))};all_records=[];audits={}
 for year in [2016,2021]:
  delta=2 if year==2016 else 7;ind['age_target']=ind.age2014+delta;ind['age_band']=ind.age_target.map(age_band);ind['sex']=ind.sexe.map(sex_band);ind['urban_rural']=ind.mil.map(ur_band);ind['education_band']=ind.NIV_ET_AGR.map(edu_band);ind['activity_status']=ind.TY_ACT.map(act_band);eligible=ind[ind.age_target>=18].copy();base_rates={}
  for u in ['URBAN','RURAL','ALL']:
   q=eligible if u=='ALL' else eligible[eligible.urban_rural==u];ww=pd.to_numeric(q.pds,errors='coerce').fillna(1).clip(lower=0).to_numpy();aa=q.activity_status.to_numpy();den=ww[np.isin(aa,['ACTIVE_EMPLOYED','UNEMPLOYED'])].sum();num=ww[aa=='UNEMPLOYED'].sum();base_rates[u]=float(num/den) if den else .1
  territories=[];year_records=[];fail=[];available=set(eligible.pro_norm.drop_duplicates())
  for ti,t in enumerate(pops[year]['territories']):
   cid=t['constituency_id'];parent,geo0=resolve_parent(t['prefecture_or_province'],available);pool=eligible[eligible.pro_norm==parent]
   if len(pool)<N:fail.append({'constituency_id':cid,'reason':'INSUFFICIENT_PARENT_POOL','parent':parent,'rows':len(pool)});continue
   pw=pd.to_numeric(pool.pds,errors='coerce').fillna(1).clip(lower=.000001).to_numpy(float);lm=np.array([labour_multiplier(ac,u,year,base_rates) for ac,u in zip(pool.activity_status,pool.urban_rural)]);sw=pw*lm;tm=margins(pool,sw);prior=t['target_marginals']['prior_vote_or_abstention'];best=None
   for attempt in range(32):
    rng=np.random.default_rng(SEED+year*100000+ti*101+attempt);pick=rng.choice(len(pool),N,replace=False,p=sw/sw.sum());r=prior_assign(pool.iloc[pick].copy().reset_index(drop=True),prior,SEED+year+ti+attempt);targets={**tm,'prior_vote_or_abstention':prior};w,err=ipf(r,targets)
    if w is None:continue
    ess=float(1/(w*w).sum());mw=float(w.max());cand=(err,-ess,mw,r,w)
    if best is None or cand[:3]<best[:3]:best=cand
    if err<2e-8 and ess>=128 and mw<=.05:break
   if best is None or best[0]>5e-6 or -best[1]<128 or best[2]>.05:fail.append({'constituency_id':cid,'reason':'IPF_GATE','best':None if best is None else {'err':best[0],'ess':-best[1],'max_weight':best[2]}});continue
   err,negess,mw,r,w=best;records=[]
   for j,p in r.iterrows():
    key=(p['pro'],p['MEN_PRO']);h=hh.loc[key] if key in hh.index else pd.Series(dtype=object);c=comp[year].loc[key] if key in comp[year].index else pd.Series(dtype=object);hd=head.loc[key] if key in head.index else pd.Series(dtype=object)
    rec={'archetype_id':f'R{j+1:03d}','weight':float(w[j]),'prior_vote_or_abstention':str(p['prior_vote_or_abstention']),'age_years':int(p['age_target']),'age_band':p['age_band'],'sex':p['sex'],'urban_rural':p['urban_rural'],'marital_status':code_label(im,'E_MAT',p.E_MAT),'relationship_to_household_head':code_label(im,'LIEN_CM',p.LIEN_CM),'children_ever_living':None if pd.isna(p.ENF_VIV) or float(p.ENF_VIV)>=90 else int(p.ENF_VIV),'education_level':code_label(im,'NIV_ET_AGR',p.NIV_ET_AGR),'education_detailed':code_label(im,'NIV_ET',p.NIV_ET),'schooling_status':code_label(im,'scol',p.scol),'literacy_status':code_label(im,'LIR_ECR',p.LIR_ECR),'diploma_group':code_label(im,'EG_DIP_SGG',p.EG_DIP_SGG),'activity_status':p['activity_status'],'occupation_group':code_label(im,'PROF_GG',p.PROF_GG),'professional_status':code_label(im,'STAT_PROF',p.STAT_PROF),'industry_sector':code_label(im,'ACT_SECTEUR',p.ACT_SECTEUR),'industry_section':code_label(im,'ACT_SECTION',p.ACT_SECTION),'workplace_geography':code_label(im,'TRAV_LIEU',p.TRAV_LIEU),'commute_mode':code_label(im,'TRAV_TRANS',p.TRAV_TRANS),'household_size':safe_int(h.get('taille',1),1),'dwelling_type':code_label(hm,'TYPE_LOG',h.get('TYPE_LOG',np.nan)),'wall_material':code_label(hm,'murs',h.get('murs',np.nan)),'roof_material':code_label(hm,'toit',h.get('toit',np.nan)),'floor_material':code_label(hm,'sol',h.get('sol',np.nan)),'dwelling_age':code_label(hm,'AGE_LOG',h.get('AGE_LOG',np.nan)),'rooms':None if pd.isna(h.get('pieces',np.nan)) else safe_int(h.get('pieces')),'tenure_status':code_label(hm,'STAT_OCC',h.get('STAT_OCC',np.nan)),'kitchen_available':code_label(hm,'cuis',h.get('cuis',np.nan)),'toilet_available':code_label(hm,'wc',h.get('wc',np.nan)),'bath_shower_available':code_label(hm,'bd',h.get('bd',np.nan)),'local_bath_available':code_label(hm,'bloc',h.get('bloc',np.nan)),'lighting_mode':code_label(hm,'ECL_MODE',h.get('ECL_MODE',np.nan)),'water_supply_mode':code_label(hm,'EAU_MODE',h.get('EAU_MODE',np.nan)),'wastewater_mode':code_label(hm,'EAUX_US',h.get('EAUX_US',np.nan)),'waste_disposal_mode':code_label(hm,'dech',h.get('dech',np.nan)),'gas_cooking':code_label(hm,'gaz',h.get('gaz',np.nan)),'electric_cooking':code_label(hm,'elec',h.get('elec',np.nan)),'wood_cooking':code_label(hm,'bois',h.get('bois',np.nan)),'tv_owned':code_label(hm,'tele',h.get('tele',np.nan)),'radio_owned':code_label(hm,'radio',h.get('radio',np.nan)),'mobile_phone_owned':code_label(hm,'TEL_PORT',h.get('TEL_PORT',np.nan)),'fixed_phone_owned':code_label(hm,'TEL_FIXE',h.get('TEL_FIXE',np.nan)),'internet_owned':code_label(hm,'net',h.get('net',np.nan)),'computer_owned':code_label(hm,'pc',h.get('pc',np.nan)),'satellite_owned':code_label(hm,'parab',h.get('parab',np.nan)),'refrigerator_owned':code_label(hm,'frigo',h.get('frigo',np.nan)),'cars_count':safe_int(h.get('voit',0),0),'motorcycles_count':safe_int(h.get('moto',0),0),'trucks_count':safe_int(h.get('cam',0),0),'tractors_count':safe_int(h.get('tract',0),0),'paved_road_distance_km':None if pd.isna(h.get('ROUTE_DIST',np.nan)) else float(h.get('ROUTE_DIST')),'household_type':code_label(hm,'MEN_TYPE',h.get('MEN_TYPE',np.nan)),'household_children_count':safe_int(c.get('child',0),0),'household_adult_count':safe_int(c.get('adult',0),0),'household_elderly_count':safe_int(c.get('elderly',0),0),'household_worker_count':safe_int(c.get('worker',0),0),'household_unemployed_count':safe_int(c.get('unemployed',0),0),'household_student_count':safe_int(c.get('student',0),0),'dependency_ratio':float((c.get('child',0)+c.get('elderly',0))/max(1,c.get('adult',1))),'persons_per_room':float(safe_int(h.get('taille',1),1)/max(1,safe_int(h.get('pieces',1),1))),'asset_index':profile_asset(h),'basic_services_index':profile_services(h),'head_sex':sex_band(hd.get('head_sex',p.sexe)),'head_age_band':age_band(safe_int(hd.get('head_age2014',p.age2014),int(p.age2014))+delta),'head_education_band':edu_band(hd.get('head_edu',p.NIV_ET_AGR))}
    ep=pick_encdm(enc,eidx,{**p.to_dict(),**h.to_dict(),'head_sex':hd.get('head_sex',p.sexe),'head_age_target':safe_int(hd.get('head_age2014',p.age2014),int(p.age2014))+delta,'head_edu':hd.get('head_edu',p.NIV_ET_AGR)},SEED+year+ti);rec.update(ses_features(ep));rec.update(af_features(pick_af(af[year],aidx[year],p,year,SEED+ti),year));records.append(rec)
   fill_missing_attitudes(records);geo='PARENT_PROXY_SPLIT_CONSTITUENCY' if cid in SPLIT else geo0;q={'raking_max_abs_error':float(err),'effective_archetype_count':float(-negess),'max_single_archetype_weight':float(mw),'geography_confidence':geo,'observed_or_derived_voter_dimensions':len([k for k in records[0] if k not in ('archetype_id','weight','prior_vote_or_abstention')])};territories.append({'constituency_id':cid,'constituency_name':t['constituency_name'],'prefecture_or_province':t['prefecture_or_province'],'prior_election_year':t['prior_election_year'],'prior_historical_match':t['prior_historical_match'],'geography_confidence':geo,'target_core_marginals':targets,'quality':q,'archetypes':records});year_records += [{**rr,'year':year,'constituency_id':cid,'geography_confidence':geo} for rr in records]
  output={'schema_version':'1.0','population_id':f'M26-ASV2-RICH-{year}-POP-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','target_election_year':year,'status':'PASS' if not fail and len(territories)==92 else 'FAIL','archetypes_per_constituency':N,'target_outcome_used':False,'real_llm_outputs_used':False,'source_hashes':EXPECTED,'target_year_update':{'aging_years':delta,'labor_context':LABOR[year]},'territories':territories,'failures':fail};jsave(out/f'{year}_rich_population_v1.json',output);all_records+=year_records;audits[year]={'territories':len(territories),'failures':fail,'min_ess':min((t['quality']['effective_archetype_count'] for t in territories),default=0),'max_weight':max((t['quality']['max_single_archetype_weight'] for t in territories),default=1),'direct_geo':sum(t['geography_confidence']=='DIRECT_MICRODATA_ADMIN' for t in territories),'proxy_geo':sum(t['geography_confidence']!='DIRECT_MICRODATA_ADMIN' for t in territories)};print(year,audits[year])
 r0=['age_band','sex','urban_rural','education_level','activity_status','prior_vote_or_abstention'];rich=[k for k in all_records[0] if k not in {'archetype_id','weight','year','constituency_id','geography_confidence'}];rng=np.random.default_rng(SEED);sample=[all_records[i] for i in rng.choice(len(all_records),min(12000,len(all_records)),replace=False)];er0=effective_rank(sample,r0);err=effective_rank(sample,rich);ratio=err['effective_rank']/er0['effective_rank'];cert={'schema_version':'1.0','certificate_id':'M26-ASV2-RICH-DATA-POWER-CERTIFICATE-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','target_outcomes_used':False,'real_llm_outputs_used':False,'safe_feature_count':len(rich),'source_families':['RGPH_INDIVIDUAL','RGPH_HOUSEHOLD','RGPH_DERIVED_HOUSEHOLD','ENCDM_SES','AFROBAROMETER_PRE_ELECTION','PRIOR_ELECTION_ANCHOR','HCP_PRE_ELECTION_LABOUR'],'R0_effective_rank':er0,'RICH_effective_rank':err,'effective_rank_ratio':ratio,'year_audits':audits,'sensitive_or_direct_vote_features_included':False,'geography_robustness_rule':'Final historical scoring must report both ALL_92 and the dynamically resolved DIRECT_MICRODATA_ADMIN subset; any effect confined to proxy-geography constituencies is rejected.','gates':{'all_92_both_years':all(audits[y]['territories']==92 and not audits[y]['failures'] for y in [2016,2021]),'safe_dimensions_ge_60':len(rich)>=60,'source_families_ge_5':True,'effective_rank_ratio_ge_10':ratio>=10,'min_ess_ge_128':min(audits[y]['min_ess'] for y in [2016,2021])>=128,'max_weight_le_0_05':max(audits[y]['max_weight'] for y in [2016,2021])<=.05,'no_sensitive_or_direct_vote_features':True}};cert['overall_pass']=all(cert['gates'].values());cert['status']='ASV2_RICH_DATA_POWER_PASS' if cert['overall_pass'] else 'ASV2_RICH_DATA_POWER_INSUFFICIENT';jsave(out/'rich_data_power_certificate_v1.json',cert);print(json.dumps(cert,indent=2));
 if not cert['overall_pass']:raise SystemExit(2)
 with zipfile.ZipFile(out/'asv2-rich-populations-v1.zip','w',zipfile.ZIP_DEFLATED) as z:
  for fn in ['2016_rich_population_v1.json','2021_rich_population_v1.json','rich_data_power_certificate_v1.json']:z.write(out/fn,fn)
if __name__=='__main__':main()
