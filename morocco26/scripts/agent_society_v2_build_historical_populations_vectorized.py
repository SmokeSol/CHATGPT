#!/usr/bin/env python3
from __future__ import annotations

import math, re
import numpy as np
import agent_society_v2_build_historical_populations as base

DIMS=['age_band','sex','urban_rural','education_band','activity_status','prior_vote_or_abstention']
DEMO_DIMS=['age_band','sex','urban_rural','education_band','activity_status']
ORIGINAL_DEMO_MARGIN=base.demo_margin


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
        'mohammedia':'mohammadia',
        'ben m sick':'ben m sik',
        'ben msick':'ben m sik',
    }
    return repl.get(x,x)


def robust_hcp_tables(blob):
    """Read official HCP province, prefecture and Casablanca arrondissement-prefecture rows.

    The original parser only retained labels beginning `Province:` or `Préfecture:`.
    RGPH2014 encodes Casablanca sub-prefectures as `Préfecture d’Arrondissements ...`;
    dropping those rows caused nine false missing-admin failures. This parser changes only
    administrative row recognition; no demographic values or scientific thresholds change.
    """
    with base.tempfile.NamedTemporaryFile(suffix='.xlsx') as f:
        f.write(blob); f.flush(); wb=base.load_workbook(f.name,read_only=True,data_only=True)
        tabs={}
        for sn in ['Indic.Ensemble','Indic.Urbain','Indic.Rural']:
            ws=wb[sn]; rows={}
            for row in ws.iter_rows(min_row=4,values_only=True):
                label=row[7] if len(row)>7 else None
                nl=base.norm(label) if label else ''
                if re.match(r'^(province|prefecture)(\s+d\s+arrondissements?)?\b',nl):
                    rows[robust_province_key(label)]=row
            tabs[sn]=rows
    return tabs


def robust_demo_margin(province,tabs):
    """Prefer the exact HCP admin unit; use frozen hierarchical Casablanca parent fallback only if absent."""
    key=robust_province_key(province)
    try:
        demo,audit=ORIGINAL_DEMO_MARGIN(province,tabs)
        audit=dict(audit); audit['resolution']='DIRECT_HCP_ADMIN_UNIT'
        return demo,audit
    except RuntimeError as e:
        casablanca_children={
            'casablanca anfa','al fida mers sultan','ain sebaa hay mohammadi','hay hassani',
            'ain chock','sidi bernoussi','ben m sik','moulay rachid'
        }
        if key not in casablanca_children:
            raise
        demo,audit=ORIGINAL_DEMO_MARGIN('Casablanca',tabs)
        audit=dict(audit)
        audit['resolution']='HIERARCHICAL_PARENT_PREFECTURE_FALLBACK'
        audit['fallback_from']=key
        audit['fallback_to']='casablanca'
        return demo,audit


def safe_float(v):
    if v is None:return 0.0
    if isinstance(v,(int,float)):return float(v)
    s=str(v).strip()
    if s in {'','-','–','—','…','..'}:return 0.0
    s=s.replace('\u00a0','').replace(' ','').replace(',','.')
    return float(s)


def safe_num(row,col1): return safe_float(row[col1-1])
def safe_pct(row,col1): return max(0.0,safe_float(row[col1-1]))/100.0


def proportional_counts(pol):
    positive=sorted([p for p,v in pol.items() if v>1e-15])
    ideal={p:float(pol[p])*base.TARGET_N for p in positive}
    counts={p:max(1,int(math.floor(ideal[p]))) for p in positive}
    while sum(counts.values())<base.TARGET_N:
        p=max(positive,key=lambda q:(ideal[q]-counts[q],pol[q],q)); counts[p]+=1
    while sum(counts.values())>base.TARGET_N:
        removable=[p for p in positive if counts[p]>1]
        if not removable:raise RuntimeError('cannot reconcile proportional support counts')
        p=max(removable,key=lambda q:(counts[q]-ideal[q],counts[q],q)); counts[p]-=1
    return counts


def demo_product_weights(demo):
    w=[]
    for combo in base.DEMO_COMBOS:
        a,s,u,e,act=combo
        p=(float(demo['age_band'][a])*float(demo['sex'][s])*float(demo['urban_rural'][u])*
           float(demo['education_band'][e])*float(demo['activity_status'][act]))
        w.append(p)
    return np.asarray(w,dtype=float)


def weighted_without_replacement_indices(weights,n,rng):
    positive=np.flatnonzero(weights>1e-18)
    if n>len(positive):
        raise RuntimeError(f'need {n} unique demographic cells but only {len(positive)} have positive frozen product mass')
    # Gumbel-top-k is deterministic for the frozen seed and samples without replacement
    # proportionally to the frozen independent-product mass. No outcome information enters.
    g=-np.log(-np.log(np.clip(rng.random(len(positive)),1e-15,1-1e-15)))
    score=np.log(weights[positive])+g
    pick=positive[np.argpartition(score,-n)[-n:]]
    return pick[np.argsort(score[np.argpartition(score,-n)[-n:]])[::-1]]


def stratified_make_support(demo,pol,seed,attempt):
    """Create 128 unique archetypes from frozen product marginals without cloning rows.

    Political-state support counts are proportional to prior-election mass, which is the ESS-optimal
    allocation under equal within-state weights. Within each political state, demographic cells are
    sampled WITHOUT replacement from the frozen independent product. Multiple deterministic attempts
    are searched only for numerical feasibility/entropy; target-election outcomes are never read.
    """
    counts=proportional_counts(pol)
    dw=demo_product_weights(demo)
    rows=[]
    for ip,p in enumerate(sorted(counts)):
        n=counts[p]
        rng=np.random.default_rng(seed+attempt*100003+ip*7919)
        chosen=weighted_without_replacement_indices(dw,n,rng)
        for z in chosen:
            a,s,u,e,act=base.DEMO_COMBOS[int(z)]
            rows.append({'age_band':a,'sex':s,'urban_rural':u,'education_band':e,'activity_status':act,'prior_vote_or_abstention':p})
    if len(rows)!=base.TARGET_N:raise RuntimeError('support cardinality mismatch')
    if len({tuple(r[d] for d in DIMS) for r in rows})!=base.TARGET_N:
        raise RuntimeError('full archetype support is not unique')
    return rows


def fast_rake(rows, targets, max_iter=500, tol=2e-10):
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
    for attempt in range(64):
        try:
            rows=stratified_make_support(demo,pol,seed,attempt)
        except Exception as e:
            diagnostics.append({'attempt':attempt,'reason':type(e).__name__+':'+str(e)});continue
        w,err=fast_rake(rows,targets)
        if w is None:
            diagnostics.append({'attempt':attempt,'reason':'IPF_STRUCTURAL_ZERO'});continue
        ess=float(1.0/np.sum(w*w));mw=float(w.max());dep=base.independence_diag(rows,w,targets)
        diagnostics.append({'attempt':attempt,'err':float(err),'ess':ess,'max_weight':mw,'dependence':float(dep)})
        if err<=5e-10 and ess>=64 and mw<=.10:
            cand=(dep,-ess,mw,attempt,rows,w,err)
            if best is None or cand[:4]<best[:4]:best=cand
    if best is None:
        # compact diagnostics so a failure is auditable but does not explode logs
        ranked=sorted([d for d in diagnostics if 'ess' in d],key=lambda d:(-d['ess'],d['max_weight']))[:8]
        raise RuntimeError('no unique 128-archetype support satisfies frozen gates; best='+str(ranked))
    dep,negess,mw,attempt,rows,w,err=best
    for i,(r,x) in enumerate(zip(rows,w),start=1):r['archetype_id']=f'A{i:03d}';r['weight']=float(x)
    return rows,{'raking_max_abs_error':float(err),'effective_archetype_count':float(-negess),'max_single_archetype_weight':mw,'max_demo_prior_joint_deviation_from_independence':float(dep),'support_attempt':attempt,'ipf_implementation':'UNIQUE_PRODUCT_WEIGHTED_WITHOUT_REPLACEMENT_IPF_V5'}

base.province_key=robust_province_key
base.hcp_tables=robust_hcp_tables
base.demo_margin=robust_demo_margin
base.num=safe_num
base.pct=safe_pct
base.choose_population=fast_choose_population

if __name__=='__main__':base.main()
