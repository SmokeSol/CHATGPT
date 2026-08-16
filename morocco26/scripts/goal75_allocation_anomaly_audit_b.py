#!/usr/bin/env python3
import json,math
from pathlib import Path
import goal75_stage1 as g
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
def parse_robust(df):
    df=g.flatcols(df);vcs=[c for c in df.columns if 'Voix' in c and '%' not in c] or [c for c in df.columns if 'Voix' in c]
    if not vcs:raise RuntimeError(f'no raw vote column: {list(df.columns)}')
    vc=vcs[0];votes={};reg=exp=absn=None
    for _,r in df.iterrows():
        text=' | '.join(str(v) for v in r.tolist());nt=g.norm(text);v=g.nint(r[vc])
        if 'inscrits' in nt:reg=v;continue
        if 'exprimes' in nt:exp=v;continue
        if 'abstentions' in nt:absn=v;continue
        p=g.party(text)
        if p and v is not None:votes[p]=votes.get(p,0)+v
    observed=sum(votes.values());explicit=exp;exp=exp if exp is not None else observed;coverage=observed/explicit if explicit else (1.0 if observed else 0.0)
    return {'votes':votes,'registered':reg,'expressed':exp,'abstentions':absn,'vote_coverage':coverage,'explicit_expressed':explicit}
g.parse=parse_robust
acq=json.loads((O/'stage1_acquisition.json').read_text());rows=list(acq['development'])
for x in acq['holdout_inputs_2016']:
    a=g.acquire(x['name'],x['seats'],True);z=dict(x);z['2021']=a['2021'];z['source_url']=a['url'];rows.append(z)
an=[];allrows=[];direct_total=0;seat_total=0
for x in rows:
    y=x['2021'];v=y['votes'];reg=y.get('registered');exp=y.get('expressed');seats=x['seats'];vote_sum=sum(v.values());q=(reg/seats) if reg else None
    direct={p:math.floor(n/q) for p,n in v.items()} if q else {};ds=sum(direct.values());direct_total+=ds;seat_total+=seats
    rec={'constituency_id':x['constituency_id'],'name':x['name'],'seats':seats,'registered':reg,'expressed':exp,'recognized_vote_sum':vote_sum,'recognized_over_registered':vote_sum/reg if reg else None,'recognized_over_expressed':vote_sum/exp if exp else None,'quota':q,'direct_seat_sum':ds,'direct':{p:n for p,n in direct.items() if n},'vote_coverage':y.get('vote_coverage')};allrows.append(rec)
    if (not reg) or vote_sum>reg or (exp and exp>reg) or ds>seats or (exp and abs(vote_sum-exp)/exp>.03):an.append(rec)
out={'constituencies':len(rows),'configured_seats':seat_total,'direct_quota_seats_total':direct_total,'anomaly_count':len(an),'anomalies':an,'rows':allrows,'interpretation':'With q=registered/seats and coherent vote totals, sum(floor(v/q)) cannot exceed seats. Any such row proves parsing/source inconsistency rather than a need to alter the electoral law.'}
(O/'allocation_anomaly_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({'constituencies':len(rows),'configured_seats':seat_total,'direct_quota_seats_total':direct_total,'anomaly_count':len(an),'anomalies':an},ensure_ascii=False,indent=2))
