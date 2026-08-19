#!/usr/bin/env python3
"""Replay legal allocators on every discovered historical canonical outcome where inputs permit it."""
from __future__ import annotations
import importlib.util, json, re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; G=ROOT/'data'/'goal100'; HIST=G/'historical'; FP=G/'forecast_pipeline'
OUT=FP/'legal_allocator_historical_replay_v1.json'; REG=FP/'legal_regimes_v1.json'
spec=importlib.util.spec_from_file_location('lsa',ROOT/'scripts'/'legal_seat_allocator.py')
lsa=importlib.util.module_from_spec(spec); spec.loader.exec_module(lsa)

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def discover():
    pat=re.compile(r'tafra_legislative_(\d{4})_canonical\.json$'); out={}
    for p in HIST.glob('tafra_legislative_*_canonical.json'):
        m=pat.match(p.name)
        if m: out[int(m.group(1))]=p
    return dict(sorted(out.items()))
def local(p):
    d=rj(p); return [x for x in d['rows'] if str(x.get('list_type','')).lower() in {'local','locale'}]

def main():
    registry=rj(REG)['regimes']; years={}
    for year,path in discover().items():
        rule=registry.get(str(year),{}).get('local')
        if not rule: continue
        rows=local(path); aggregate=Counter(); ok=blocked=ties=unalloc=errors=0; examples=[]
        for r in rows:
            registered=r.get('registered_reported')
            if rule['quotient_mode']=='registered_voters_div_seats' and (registered is None or float(registered or 0)<=0):
                blocked+=1; continue
            try:
                a=lsa.allocate(r['votes'],int(r['seats']),year,tier='local',registered_voters=registered,strict_list_universe=True)
            except Exception as e:
                errors+=1
                if len(examples)<10: examples.append({'constituency':r.get('constituency'),'error':str(e)})
                continue
            if a['status']=='UNRESOLVED_LEGAL_TIE': ties+=1
            if a['unallocated_seats']: unalloc+=1
            if a['seats_allocated']==int(r['seats']) and a['status'] in {'ALLOCATED','ALLOCATED_SINGLE_ELIGIBLE_LIST'}: ok+=1
            for p,n in a['seats'].items(): aggregate[p]+=n
        years[str(year)]={
          'local_rows':len(rows),'expected_native_local_rows':registry[str(year)].get('native_local_constituencies'),
          'fully_allocated_without_unresolved_tie':ok,'blocked_missing_registered_voters':blocked,
          'tie_rows':ties,'unallocated_rows':unalloc,'error_rows':errors,
          'modelled_local_seat_total':sum(aggregate.values()),'modelled_local_seats_by_list':dict(aggregate.most_common()),
          'errors':examples,'validation_scope':'MECHANICAL_REPLAY_INVARIANTS_NOT_INDEPENDENT_OFFICIAL_SEAT_RESULT_VALIDATION'
        }
    out={'schema_version':'1.0','result_id':'M26-LEGAL-ALLOCATOR-HISTORICAL-REPLAY-V1','years':years,
         'interpretation':'All discovered regimes are replayed at native district geometry. Eligible-valid-vote regimes can be computed from full list vote counts; registered-voter quotient regimes are explicitly blocked where canonical registered counts are absent.',
         'F0_modified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({y:{k:v[k] for k in ('local_rows','fully_allocated_without_unresolved_tie','blocked_missing_registered_voters','modelled_local_seat_total')} for y,v in years.items()},sort_keys=True))
if __name__=='__main__': main()
