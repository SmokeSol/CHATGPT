#!/usr/bin/env python3
import json,math
from pathlib import Path
import goal75_stage1 as g
import goal75_stage1b as gb
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
g.parse=gb.parse_robust
acq=json.loads((O/'stage1_acquisition.json').read_text());rows=list(acq['development'])
# Holdout is already unsealed by the frozen workflow; reacquisition now cannot contaminate prior predictions.
for x in acq['holdout_inputs_2016']:
    a=g.acquire(x['name'],x['seats'],True);z=dict(x);z['2021']=a['2021'];z['source_url']=a['url'];rows.append(z)
an=[];direct_total=0;seat_total=0
for x in rows:
    y=x['2021'];v=y['votes'];reg=y.get('registered');exp=y.get('expressed');seats=x['seats'];vote_sum=sum(v.values());q=(reg/seats) if reg else None
    direct={p:math.floor(n/q) for p,n in v.items()} if q else {};ds=sum(direct.values());direct_total+=ds;seat_total+=seats
    rec={'constituency_id':x['constituency_id'],'name':x['name'],'seats':seats,'registered':reg,'expressed':exp,'recognized_vote_sum':vote_sum,'recognized_over_registered':vote_sum/reg if reg else None,'recognized_over_expressed':vote_sum/exp if exp else None,'quota':q,'direct_seat_sum':ds,'direct':{p:n for p,n in direct.items() if n},'vote_coverage':y.get('vote_coverage')}
    if (not reg) or vote_sum>reg or (exp and exp>reg) or ds>seats or (exp and abs(vote_sum-exp)/exp>.03):an.append(rec)
out={'constituencies':len(rows),'configured_seats':seat_total,'direct_quota_seats_total':direct_total,'anomaly_count':len(an),'anomalies':an,'interpretation':'If direct_seat_sum exceeds configured seats, parsed registered/vote totals violate the mathematical bound sum(floor(v/q))<=seats and the parser/source must be audited before changing electoral law implementation.'}
(O/'allocation_anomaly_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps(out,ensure_ascii=False,indent=2))
raise SystemExit(0)
