#!/usr/bin/env python3
import json, math, re, unicodedata
from io import BytesIO
from pathlib import Path
import pandas as pd, requests

ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OUT=DATA/'goal75'; OUT.mkdir(exist_ok=True)
TAFRA='https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/parlement-elections-2021-1-0.xlsx'
META={'idRegion','idWilaya','idPrefProv','idSousPref','idCirconscription','region','wilaya','prefProv','sousPref','circonscription','typeListe','nSieges','nInscrits','txParticipation','invalide','repPctFemmes','repAge34','repAge3544','repAge4554','repAge55','repEduSans','repEdu1aire','repEdu2aire','repEduSup'}
K=['RNI','PAM','PI','PJD','USFP','MP','UC','PPS','OTHER']
ALIASES={'tarfaya':'tarfaya','aousserd':'aousserd','zagora':'zagora','nouaceur':'nouaceur','sidi bennour':'sidi bennour','tata':'tata','assa zag':'assa zag','youssoufia':'youssoufia','fahs anjra':'fahs anjra','figuig':'figuig','boulemane':'boulemane','khenifra':'khenifra'}
def load(p): return json.loads(Path(p).read_text())
def norm(x): return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()
def shares(v):
    z=sum(v.values()) or 1
    d={k:v.get(k,0)/z for k in K[:-1]}; d['OTHER']=max(0.0,1-sum(d.values())); return d
def winners(d,n): return set(sorted(d,key=lambda k:(-d[k],k))[:n])
def jaccard(a,b):
    u=a|b; return len(a&b)/len(u) if u else 1.0
def score(pred,actual):
    sq=[]; te=[]; js=[]
    for cid,a in actual.items():
        p=pred[cid]
        sq.extend([((float(p['shares'].get(k,0))-float(a['shares'].get(k,0)))*100)**2 for k in K])
        te.append(abs(float(p['turnout'])-float(a['turnout']))*100)
        js.append(jaccard(winners(p['shares'],a['seats']),a['winner_set']))
    rmse=math.sqrt(sum(sq)/len(sq)); mae=sum(te)/len(te); mj=sum(js)/len(js)
    return {'party_share_RMSE_pp':rmse,'turnout_MAE_pp':mae,'winner_set_Jaccard':mj,'frozen_score':rmse+0.25*mae+5*(1-mj)}

def main():
    hold=load(DATA/'territorial_holdout_v1.json'); fr=load(OUT/'bc_freeze.json'); obs=load(OUT/'observed_elected_2021.json'); kill=load(OUT/'model_d_kill_preunseal.json')
    if kill['decision_stage']!='PRE_HOLDOUT_UNSEAL' or kill['holdout_2021_outcomes_accessed'] is not False: raise RuntimeError('D kill was not clean pre-unseal')
    r=requests.get(TAFRA,timeout=60,headers={'User-Agent':'MOROCCO26 research'}); r.raise_for_status(); df=pd.read_excel(BytesIO(r.content),sheet_name='donnees')
    party=[c for c in df.columns if c not in META]
    loc=df[df['typeListe'].astype(str).str.lower().eq('locale')].copy()
    byname={norm(row['circonscription']):row for _,row in loc.iterrows()}
    observed={norm(k):v for k,v in obs['local'].items()}
    preds={p['constituency_id']:p for p in fr['predictions']}
    actual={}; rows=[]
    for h in hold['constituencies']:
        cid=norm(h['name']).replace(' ','-'); target=ALIASES[norm(h['name'])]
        candidates=[(n,row) for n,row in byname.items() if n==target or target in n or n in target]
        if len(candidates)!=1: raise RuntimeError(f'ambiguous TAFRA holdout row {h}: {[x[0] for x in candidates]}')
        n,row=candidates[0]; votes={str(c):int(row[c]) for c in party if pd.notna(row[c]) and float(row[c])>0}; sh=shares(votes); seats=int(row['nSieges']); turnout=float(row['txParticipation'])
        ok=[(k,v) for k,v in observed.items() if norm(k)==n or norm(k)==target or target in norm(k) or norm(k) in target]
        if len(ok)!=1: raise RuntimeError(f'ambiguous observed holdout {h}: {[x[0] for x in ok]}')
        winner=set(ok[0][1]); actual[cid]={'shares':sh,'turnout':turnout,'seats':seats,'winner_set':winner}
        rows.append({'constituency_id':cid,'name':h['name'],'seats':seats,'turnout_actual':turnout,'winner_set_actual':sorted(winner),'source':'TAFRA Elections.ma-derived legislative workbook + independent Parliament member file'})
    # frozen file uses same normalized slug convention; map explicitly by slug
    B={};C={}
    for cid in actual:
        if cid not in preds: raise RuntimeError(f'frozen prediction missing {cid}; available={sorted(preds)}')
        p=preds[cid]; B[cid]={'shares':p['B']['shares'],'turnout':p['B']['turnout']}; C[cid]={'shares':p['C_eval']['shares'],'turnout':p['C_eval']['turnout']}
    sb,sc=score(B,actual),score(C,actual)
    out={'audit_id':'M26-HOLDOUT-BC-CLEAN-001','holdout_id':hold['holdout_id'],'frozen_before_outcome_access':True,'training_n':fr['training_n'],'holdout_n':len(actual),'B':sb,'C':sc,'C_beats_B':sc['frozen_score']<sb['frozen_score'],'no_post_unseal_tuning':True,'model_D_status':kill['decision'],'rows':rows,'forecast_status':'BLOCKED'}
    (OUT/'holdout_bc_score_clean.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps(out,ensure_ascii=False,indent=2))
    if len(actual)!=12: raise SystemExit(7)
if __name__=='__main__': main()
