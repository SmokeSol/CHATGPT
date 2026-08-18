#!/usr/bin/env python3
from __future__ import annotations

import numpy as np
import agent_society_v2_build_historical_populations as base

DIMS=['age_band','sex','urban_rural','education_band','activity_status','prior_vote_or_abstention']


def fast_rake(rows, targets, max_iter=800, tol=2e-12):
    w=np.ones(len(rows),dtype=float)/len(rows)
    idx={}
    for d in DIMS:
        for cat in targets[d]:
            idx[(d,cat)]=np.fromiter((i for i,r in enumerate(rows) if r[d]==cat),dtype=np.int64)
    for _ in range(max_iter):
        for d in DIMS:
            for cat,t in targets[d].items():
                ii=idx[(d,cat)]
                cur=float(w[ii].sum()) if len(ii) else 0.0
                if t<=1e-18:
                    if cur and len(ii): w[ii]=0.0
                else:
                    if cur<=0: return None,None
                    w[ii]*=float(t)/cur
        s=float(w.sum())
        if s<=0:return None,None
        w/=s
        err=0.0
        for d in DIMS:
            for cat,t in targets[d].items():
                ii=idx[(d,cat)]
                cur=float(w[ii].sum()) if len(ii) else 0.0
                err=max(err,abs(cur-float(t)))
        if err<tol:return w,err
    return w,err


def fast_choose_population(demo,pol,seed):
    targets={**demo,'prior_vote_or_abstention':pol}; best=None
    for attempt in range(8):
        rows=base.make_support(pol,seed,attempt)
        w,err=fast_rake(rows,targets)
        if w is None: continue
        ess=float(1.0/np.sum(w*w)); mw=float(w.max()); dep=base.independence_diag(rows,w,targets)
        if err<=5e-10 and ess>=64 and mw<=.10:
            cand=(dep,-ess,mw,attempt,rows,w,err)
            if best is None or cand[:4]<best[:4]: best=cand
    if best is None:
        raise RuntimeError('no 128-archetype support among eight frozen deterministic candidates satisfies all numerical gates')
    dep,negess,mw,attempt,rows,w,err=best
    for i,(r,x) in enumerate(zip(rows,w),start=1):
        r['archetype_id']=f'A{i:03d}'; r['weight']=float(x)
    return rows,{
        'raking_max_abs_error':float(err),
        'effective_archetype_count':float(-negess),
        'max_single_archetype_weight':mw,
        'max_demo_prior_joint_deviation_from_independence':float(dep),
        'support_attempt':attempt,
        'ipf_implementation':'PRECOMPUTED_CATEGORY_INDEX_V2'
    }

base.rake=fast_rake
base.choose_population=fast_choose_population

if __name__=='__main__':
    base.main()
