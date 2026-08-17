#!/usr/bin/env python3
"""Structural capacity diagnostic for E_reason's >=3-identity district gate."""
from __future__ import annotations
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HIST=ROOT/'morocco26/data/goal100/historical'
ER=ROOT/'morocco26/data/goal100/e_reason'
OUT=ER/'evidence/identity_gate_capacity'
OUT.mkdir(parents=True,exist_ok=True)

summary={"schema_version":"1.0","created_at":datetime.now(timezone.utc).isoformat(timespec='seconds'),"years":{},"predictive_judgments_generated":False,"forecast_delta_generated":False,"outcomes_unsealed":False,"F1_created":False}
for year in (2016,2021):
    data=json.loads((HIST/f'tafra_legislative_{year}_canonical.json').read_text(encoding='utf-8'))
    rows=[r for r in data['rows'] if r.get('list_type')=='locale']
    dist=Counter(int(r['seats']) for r in rows if r.get('seats') is not None)
    ge3=[r for r in rows if int(r.get('seats') or 0)>=3]
    lt3=[r for r in rows if int(r.get('seats') or 0)<3]
    summary['years'][str(year)]={
        'local_constituencies':len(rows),
        'seat_magnitude_distribution':{str(k):v for k,v in sorted(dist.items())},
        'districts_with_seat_magnitude_at_least_3':len(ge3),
        'districts_with_seat_magnitude_below_3':len(lt3),
        'single_complete_party_slate_can_meet_70_identity_gate':len(ge3)>=70,
        'additional_below_3_districts_needed_if_under_70':max(0,70-len(ge3)),
        'below_3_districts':[{'id_constituency':r['id_constituency'],'region':r['region'],'constituency':r['constituency'],'seats':r['seats']} for r in lt3],
    }
path=OUT/'capacity.json'
path.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False,indent=2))
