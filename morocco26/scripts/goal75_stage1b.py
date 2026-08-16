#!/usr/bin/env python3
"""Robust Stage-1 adapter: fixes merged-cell Wikipedia election tables without changing the sealed protocol."""
import math, statistics
from collections import defaultdict
import goal75_stage1 as g

def parse_robust(df):
    df=g.flatcols(df)
    vote_cols=[c for c in df.columns if 'Voix' in c and '%' not in c]
    if not vote_cols:
        vote_cols=[c for c in df.columns if 'Voix' in c]
    if not vote_cols:
        raise RuntimeError(f'no raw vote column: {list(df.columns)}')
    vc=vote_cols[0]
    votes={};reg=exp=absn=None
    for _,r in df.iterrows():
        text=' | '.join(str(v) for v in r.tolist())
        nt=g.norm(text);v=g.nint(r[vc])
        if 'inscrits' in nt:
            reg=v;continue
        if 'exprimes' in nt:
            exp=v;continue
        if 'abstentions' in nt:
            absn=v;continue
        p=g.party(text)
        if p and v is not None:
            votes[p]=votes.get(p,0)+v
    observed=sum(votes.values())
    explicit_exp=exp
    if exp is None: exp=observed
    coverage=(observed/explicit_exp) if explicit_exp and explicit_exp>0 else (1.0 if observed>0 else 0.0)
    return {'votes':votes,'registered':reg,'expressed':exp,'abstentions':absn,'vote_coverage':coverage,'explicit_expressed':explicit_exp}

def freeze_strict(dev,hold):
    sh={k:[] for k in g.K};rh=defaultdict(lambda:{k:[] for k in g.K});td=[];rtd=defaultdict(list);used=[]
    for x in dev:
        a,b=x.get('2016'),x.get('2021')
        if not a or not b or a.get('vote_coverage',0)<.90 or b.get('vote_coverage',0)<.90: continue
        c1,c2=g.clr(g.vec(a['votes'])),g.clr(g.vec(b['votes']))
        for k in g.K:
            d=c2[k]-c1[k];sh[k].append(d);rh[x['region']][k].append(d)
        if a.get('registered') and b.get('registered'):
            d=g.lg(a['expressed']/a['registered']);e=g.lg(b['expressed']/b['registered'])-d;td.append(e);rtd[x['region']].append(e)
        used.append(x['constituency_id'])
    glob={k:g.med(v) for k,v in sh.items()};gt=g.med(td);pred=[]
    for h in hold:
        a=h.get('2016')
        if not a or a.get('vote_coverage',0)<.90 or not a.get('registered'): continue
        c=g.clr(g.vec(a['votes']));nn=len(rtd[h['region']]);w=nn/(nn+5);rr={k:g.med(rh[h['region']][k]) if rh[h['region']][k] else glob[k] for k in g.K};bp=g.inv({k:c[k]+glob[k] for k in g.K});cp=g.inv({k:c[k]+glob[k]+w*(rr[k]-glob[k]) for k in g.K});t=a['expressed']/a['registered'];rt=g.med(rtd[h['region']]) if rtd[h['region']] else gt
        pred.append({'constituency_id':h['constituency_id'],'name':h['name'],'region':h['region'],'seats':h['seats'],'B':{'shares':bp,'turnout':g.il(g.lg(t)+gt),'winner_set':sorted(bp,key=bp.get,reverse=True)[:h['seats']]},'C_eval':{'shares':cp,'turnout':g.il(g.lg(t)+gt+w*(rt-gt)),'winner_set':sorted(cp,key=cp.get,reverse=True)[:h['seats']]}})
    z={'method_B':'global median CLR 2016→2021 shift from complete development tables only','method_C_eval':'region-shrunk CLR transition from complete development tables only','training':sorted(used),'training_n':len(used),'global_shift':glob,'turnout_shift':gt,'predictions':pred};z['freeze_hash']=g.digest(z);return z

g.parse=parse_robust
g.freeze=freeze_strict
raise SystemExit(g.main())
