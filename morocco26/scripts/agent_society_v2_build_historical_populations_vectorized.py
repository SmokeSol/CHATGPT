#!/usr/bin/env python3
from __future__ import annotations

import math, re
import numpy as np
import agent_society_v2_build_historical_populations as base

DIMS=['age_band','sex','urban_rural','education_band','activity_status','prior_vote_or_abstention']


def robust_province_key(s):
    x=base.norm(s)
    x=re.sub(r'^(province|prefecture)\s+(d\s+arrondissements?\s+)?','',x).strip()
    x=re.sub(r'^d\s+arrondissements?\s+','',x).strip()
    repl={
        'taroudannt':'taroudant',
        'moulay yacoub':'moulay yaacoub',
        'agadir ida outanan':'agadir ida outanane',
        'agadir ida ou tanane':'agadir ida outanane',
        'oued ed dahab':'oued eddahab',
    }
    return repl.get(x,x)


def safe_float(v):
    if v is None:return 0.0
    if isinstance(v,(int,float)):return float(v)
    s=str(v).strip()
    if s in {'','-','–','—','…','..'}:return 0.0
    s=s.replace('\u00a0','').replace(' ','').replace(',','.')
    return float(s)


def safe_num(row,col1): return safe_float(row[col1-1])
def safe_pct(row,col1): return max(0.0,safe_float(row[col1-1]))/100.0


def proportional_make_support(pol,seed,attempt):
    positive=sorted([p for p,v in pol.items() if v>1e-15])
    ideal={p:float(pol[p])*base.TARGET_N for p in positive}
    counts={p:max(1,int(math.floor(ideal[p]))) for p in positive}
    while sum(counts.values())<base.TARGET_N:
        p=max(positive,key=lambda q:(ideal[q]-counts[q],pol[q],q)); counts[p]+=1
    while sum(counts.values())>base.TARGET_N:
        removable=[p for p in positive if counts[p]>1]
        if not removable:raise RuntimeError('cannot reconcile proportional support counts')
        p=max(removable,key=lambda q:(counts[q]-ideal[q],counts[q],q)); counts[p]-=1
    rng=np.random.default_rng(seed+attempt*100003)
    perm=np.arange(len(base.DEMO_COMBOS));rng.shuffle(perm)
    rows=[]
    for ip,p in enumerate(positive):
        n=counts[p]
        if n>len(perm):raise RuntimeError('political-state support exceeds unique demographic combinations')
        offset=(ip*37+attempt*11)%len(perm)
        chosen=[perm[(offset+j)%len(perm)] for j in range(n)]
        if len(set(chosen))<n:raise RuntimeError('support duplicate demographic rows within political state')
        for z in chosen:
            a,s,u,e,act=base.DEMO_COMBOS[int(z)]
            rows.append({'age_band':a,'sex':s,'urban_rural':u,'education_band':e,'activity_status':act,'prior_vote_or_abstention':p})
    if len(rows)!=base.TARGET_N:raise RuntimeError('support cardinality mismatch')
    return rows


def fast_rake(rows, targets, max_iter=250, tol=2e-10):
    w=np.ones(len(rows),dtype=float)/len(rows)
    idx={(d,cat):np.fromiter((i for i,r in enumerate(rows) if r[d]==cat),dtype=np.int64) for d in DIMS for cat in targets[d]}
    for _ in range(max_iter):
        for d in DIMS:
            for cat,t in targets[d].items():
                ii=idx[(d,cat)];cur=float(w[ii].sum()) if len(ii) else 0.0
                if t<=1e-18:
                    if cur and len(ii):w[ii]=0.0
                else:
                    if cur<=0:return None,None
                    w[ii]*=float(t)/cur
        s=float(w.sum())
        if s<=0:return None,None
        w/=s
        err=max(abs((float(w[idx[(d,cat)]].sum()) if len(idx[(d,cat)]) else 0.0)-float(t)) for d in DIMS for cat,t in targets[d].items())
        if err<=tol:return w,err
    return w,err


def fast_choose_population(demo,pol,seed):
    targets={**demo,'prior_vote_or_abstention':pol};best=None
    diagnostics=[]
    for attempt in range(8):
        rows=proportional_make_support(pol,seed,attempt);w,err=fast_rake(rows,targets)
        if w is None:
            diagnostics.append({'attempt':attempt,'reason':'IPF_STRUCTURAL_ZERO'});continue
        ess=float(1.0/np.sum(w*w));mw=float(w.max());dep=base.independence_diag(rows,w,targets)
        diagnostics.append({'attempt':attempt,'err':float(err),'ess':ess,'max_weight':mw,'dependence':float(dep)})
        if err<=5e-10 and ess>=64 and mw<=.10:
            cand=(dep,-ess,mw,attempt,rows,w,err)
            if best is None or cand[:4]<best[:4]:best=cand
    if best is None:raise RuntimeError('no corrected 128-archetype support satisfies all numerical gates; diagnostics='+str(diagnostics))
    dep,negess,mw,attempt,rows,w,err=best
    for i,(r,x) in enumerate(zip(rows,w),start=1):r['archetype_id']=f'A{i:03d}';r['weight']=float(x)
    return rows,{'raking_max_abs_error':float(err),'effective_archetype_count':float(-negess),'max_single_archetype_weight':mw,'max_demo_prior_joint_deviation_from_independence':float(dep),'support_attempt':attempt,'ipf_implementation':'PRECOMPUTED_CATEGORY_INDEX_V4_PROPORTIONAL_SUPPORT'}

base.province_key=robust_province_key
base.num=safe_num
base.pct=safe_pct
base.make_support=proportional_make_support
base.rake=fast_rake
base.choose_population=fast_choose_population

if __name__=='__main__':base.main()
