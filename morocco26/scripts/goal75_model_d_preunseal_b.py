#!/usr/bin/env python3
import goal75_model_d_preunseal as d

def dev_examples_strict(dev,seed):
    good=[]
    for x in dev:
        a=x.get('2016') or {};b=x.get('2021') or {}
        if a.get('vote_coverage',0)>=.9 and b.get('vote_coverage',0)>=.9 and a.get('registered') and b.get('registered'):
            good.append(x)
    good=sorted(good,key=lambda x:x['constituency_id']);step=max(1,len(good)//12);sel=good[::step][:12];out=[]
    for i,x in enumerate(sel):
        m=d.perm_for(seed+1000+i);out.append({'example':f'E{i+1:02d}','seats':x['seats'],'x2016':d.enc(d.normshares(x['2016']['votes']),m),'turnout2016':round(d.turnout(x['2016']),6),'y2021':d.enc(d.normshares(x['2021']['votes']),m),'turnout2021':round(d.turnout(x['2021']),6)})
    if len(out)<10:raise RuntimeError(f'insufficient complete development examples: {len(out)}')
    return out

d.dev_examples=dev_examples_strict
d.main()
