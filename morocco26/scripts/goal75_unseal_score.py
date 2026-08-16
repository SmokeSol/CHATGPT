#!/usr/bin/env python3
import json,math,re,statistics
from collections import Counter
from io import StringIO
from pathlib import Path
import pandas as pd
import goal75_stage1 as g
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
K=['RNI','PAM','PI','PJD','USFP','MP','UC','PPS','OTHER']; AL=list('ABCDEFGHI')
LOCAL_EXPECTED={'RNI':86,'PAM':75,'PI':68,'USFP':23,'MP':20,'PPS':12,'UC':13,'PJD':4,'MDS':3,'FFD':1}
REG_EXPECTED={'RNI':16,'PAM':12,'PI':13,'USFP':11,'MP':8,'PPS':10,'UC':5,'PJD':9,'MDS':2,'FFD':2,'FGD':1,'PSU':1}
REGIONS=[('Rabat-Salé-Kénitra',10),('Laâyoune-Sakia El Hamra',5),('Dakhla-Oued Eddahab',3),('Drâa-Tafilalet',6),('Casablanca-Settat',12),('Souss-Massa',7),('Guelmim-Oued Noun',5),('Marrakech-Safi',10),('Tanger-Tétouan-Al Hoceïma',8),('Oriental',7),('Fès-Meknès',10),('Béni Mellal-Khénifra',7)]
def load(p):return json.loads(Path(p).read_text())
def parse(df):
 df=g.flatcols(df);vcs=[c for c in df.columns if 'Voix' in c and '%' not in c] or [c for c in df.columns if 'Voix' in c]
 if not vcs:raise RuntimeError('no raw vote column')
 vc=vcs[0];votes={};reg=exp=absn=None
 for _,r in df.iterrows():
  text=' | '.join(str(v) for v in r.tolist());nt=g.norm(text);v=g.nint(r[vc])
  if 'inscrits' in nt:reg=v;continue
  if 'exprimes' in nt:exp=v;continue
  if 'abstentions' in nt:absn=v;continue
  p=g.party(text)
  if p and v is not None:votes[p]=votes.get(p,0)+v
 obs=sum(votes.values());explicit=exp;exp=exp if exp is not None else obs;cov=obs/explicit if explicit else (1 if obs else 0)
 return {'votes':votes,'registered':reg,'expressed':exp,'abstentions':absn,'vote_coverage':cov}
g.parse=parse
def normshares(v):
 z=sum(v.values()) or 1;d={k:v.get(k,0)/z for k in K[:-1]};d['OTHER']=max(0,1-sum(d.values()));return d
def turnout(x):return x['expressed']/x['registered']
def winners(shares,n):return set(sorted(shares,key=shares.get,reverse=True)[:n])
def jac(a,b):
 u=a|b;return len(a&b)/len(u) if u else 1
def score(preds,actual):
 sq=[];te=[];js=[]
 for cid,p in preds.items():
  a=actual[cid];sq += [((p['shares'].get(k,0)-a['shares'].get(k,0))*100)**2 for k in K];te.append(abs(p['turnout']-a['turnout'])*100);js.append(jac(winners(p['shares'],a['seats']),a['winner_set']))
 rmse=math.sqrt(sum(sq)/len(sq));mae=sum(te)/len(te);mj=sum(js)/len(js);return {'party_share_RMSE_pp':rmse,'turnout_MAE_pp':mae,'winner_set_Jaccard':mj,'frozen_score':rmse+.25*mae+5*(1-mj)}
def agg_alloc(rows):
 c=Counter()
 for x in rows:
  for p,n in x['legal_replay'].items():c[p]+=n
 return dict(sorted(c.items()))
def exact(a,b):return {k:v for k,v in a.items() if v}=={k:v for k,v in b.items() if v}
def main():
 s1=load(O/'stage1_report.json');acq=load(O/'stage1_acquisition.json');fr=load(O/'bc_freeze.json');dp=load(O/'model_d_preunseal.json');ds=load(O/'model_d_preunseal_summary.json');man=load(D/'model_d_goal75_manifest.json')
 assert s1['ready_to_unseal'] and fr['freeze_hash']==man['parent_freeze_hash']==dp['summary']['bc_freeze_hash'];assert not acq['holdout_2021_outcomes_accessed'] and not dp['summary']['holdout_2021_outcomes_accessed']
 # irreversible holdout unseal only after B/C and D predictions exist
 hold=[]
 for x in acq['holdout_inputs_2016']:
  a=g.acquire(x['name'],x['seats'],True);y=a['2021'];assert y['registered'] and y['vote_coverage']>=.98
  z=dict(x);z['2021']=y;z['source_url']=a['url'];z['legal_replay']=g.alloc(y['votes'],z['seats'],y['registered']);hold.append(z)
 local=acq['development']+hold
 for x in local:
  y=x['2021'];assert y['registered'] and y['vote_coverage']>=.98
  if not x.get('legal_replay'):x['legal_replay']=g.alloc(y['votes'],x['seats'],y['registered'])
 local_agg=agg_alloc(local);local_exact=exact(local_agg,LOCAL_EXPECTED)
 # regional lists: exact quota + largest remainder, independently aggregated to published 90-seat totals
 regs=[]
 for name,seats in REGIONS:
  a=g.acquire(name,seats,True);y=a['2021'];assert y['registered'] and y['vote_coverage']>=.98
  regs.append({'region':name,'seats':seats,'source_url':a['url'],'2021':y,'legal_replay':g.alloc(y['votes'],seats,y['registered'])})
 reg_agg=agg_alloc(regs);reg_exact=exact(reg_agg,REG_EXPECTED)
 # actual holdout
 actual={}
 for x in hold:
  y=x['2021'];actual[x['constituency_id']]={'shares':normshares(y['votes']),'turnout':turnout(y),'seats':x['seats'],'winner_set':set(x['legal_replay'])}
 # frozen B/C
 B={};C={}
 for p in fr['predictions']:
  B[p['constituency_id']]={'shares':p['B']['shares'],'turnout':p['B']['turnout']};C[p['constituency_id']]={'shares':p['C_eval']['shares'],'turnout':p['C_eval']['turnout']}
 sb,sc=score(B,actual),score(C,actual)
 # D aggregate median across every pre-unseal run, reverse anonymous mapping
 Dr={};coverage=[]
 for did,mp in dp['anonymization_maps'].items():
  cid=mp['constituency_id'];vals=[]
  for r in dp['runs']:
   if did in r['parsed']:
    q=r['parsed'][did];real={mp['alias_to_real'][a]:q['shares'][a] for a in AL};vals.append({'shares':real,'turnout':q['turnout']})
  coverage.append(len(vals))
  if vals:Dr[cid]={'shares':{k:statistics.median(v['shares'][k] for v in vals) for k in K},'turnout':statistics.median(v['turnout'] for v in vals)}
 sd=score(Dr,actual) if len(Dr)==12 else {'frozen_score':float('inf')}
 retain=bool(ds['pre_unseal_gates_pass'] and len(Dr)==12 and sd['frozen_score']<sb['frozen_score'] and sd['frozen_score']<sc['frozen_score'])
 # full seat margin map now permitted
 margins=[]
 for x in local:
  rr=sorted(x['2021']['votes'].items(),key=lambda z:(-z[1],z[0]));n=x['seats'];a,b=rr[n-1],rr[n];margins.append({'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'seats':n,'last_rank_party':a[0],'last_rank_votes':a[1],'first_nonwinner':b[0],'first_nonwinner_votes':b[1],'raw_margin_votes':a[1]-b[1],'registered':x['2021']['registered'],'legal_winners':x['legal_replay'],'source_url':x['source_url']})
 out={'unsealed_after_freezes':True,'bc_freeze_hash':fr['freeze_hash'],'model_d_preunseal_gate':ds,'local_92':{'count':len(local),'allocated_seats':sum(local_agg.values()),'aggregate':local_agg,'expected':LOCAL_EXPECTED,'aggregate_exact_match':local_exact},'regional_12':{'count':len(regs),'allocated_seats':sum(reg_agg.values()),'aggregate':reg_agg,'expected':REG_EXPECTED,'aggregate_exact_match':reg_exact},'holdout':{'count':12,'B':sb,'C':sc,'D':sd,'D_records_per_district':coverage,'decision':'RETAIN_D' if retain else 'KILL_D_FOR_CURRENT_ARCHITECTURE'},'forecast_status':'BLOCKED'}
 (O/'unsealed_holdout_2021.json').write_text(json.dumps(hold,ensure_ascii=False,indent=2));(O/'regional_2021_replay.json').write_text(json.dumps(regs,ensure_ascii=False,indent=2));(O/'seat_margin_92.json').write_text(json.dumps(margins,ensure_ascii=False,indent=2));(O/'goal75_scoring.json').write_text(json.dumps(out,ensure_ascii=False,indent=2,default=list));print(json.dumps(out,indent=2,default=list))
 if not local_exact or not reg_exact or len(local)!=92 or len(regs)!=12:raise SystemExit(3)
if __name__=='__main__':main()
