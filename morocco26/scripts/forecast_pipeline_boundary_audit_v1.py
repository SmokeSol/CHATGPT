#!/usr/bin/env python3
"""Audit historical boundary compatibility before any territorial rolling-origin fit."""
from __future__ import annotations
import json, re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100'; HIST=G/'historical'; FP=G/'forecast_pipeline'
OUT=FP/'boundary_compatibility_v1.json'; REG=FP/'legal_regimes_v1.json'

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))

def discover():
    pat=re.compile(r'tafra_legislative_(\d{4})_canonical\.json$'); out={}
    for p in HIST.glob('tafra_legislative_*_canonical.json'):
        m=pat.match(p.name)
        if m: out[int(m.group(1))]=p
    return dict(sorted(out.items()))

def local_rows(p):
    d=rj(p); return [x for x in d['rows'] if str(x.get('list_type','')).lower() in {'local','locale'}]

def main():
    reg=rj(REG)['regimes']; files=discover(); years={}
    for y,p in files.items():
        rows=local_rows(p); native=len(rows); expected=reg.get(str(y),{}).get('native_local_constituencies')
        bridge=FP/'geography_bridges'/f'{y}_to_2011_reference_v1.json'
        bridge_meta=rj(bridge) if bridge.exists() else None
        direct=(native==92 and y>=2011)
        years[str(y)]={
          'native_local_rows':native,'expected_native_local_rows':expected,
          'native_count_matches_registry':expected is None or native==int(expected),
          'direct_2011_reference_geometry_candidate':direct,
          'bridge_path':str(bridge.relative_to(ROOT)),
          'bridge_present':bridge.exists(),
          'bridge_forecast_eligible':None if bridge_meta is None else bool(bridge_meta.get('forecast_eligible')),
          'territorial_status':('DIRECT_92_REFERENCE_COMPATIBLE' if direct else
                                'BRIDGE_FORECAST_ELIGIBLE' if bridge_meta and bridge_meta.get('forecast_eligible') else
                                'BRIDGE_REQUIRED_BEFORE_TERRITORIAL_USE')
        }
    transitions=[]
    ys=list(files)
    for a,b in zip(ys[:-1],ys[1:]):
        A=years[str(a)]; B=years[str(b)]
        transitions.append({
          'transition':f'{a}_TO_{b}',
          'native_counts':[A['native_local_rows'],B['native_local_rows']],
          'same_reference_territorial_fit_available':
            A['territorial_status'] in {'DIRECT_92_REFERENCE_COMPATIBLE','BRIDGE_FORECAST_ELIGIBLE'} and
            B['territorial_status'] in {'DIRECT_92_REFERENCE_COMPATIBLE','BRIDGE_FORECAST_ELIGIBLE'},
          'status':'READY' if (
            A['territorial_status'] in {'DIRECT_92_REFERENCE_COMPATIBLE','BRIDGE_FORECAST_ELIGIBLE'} and
            B['territorial_status'] in {'DIRECT_92_REFERENCE_COMPATIBLE','BRIDGE_FORECAST_ELIGIBLE'}
          ) else 'BLOCKED_PENDING_GEOGRAPHY_BRIDGE'
        })
    out={'schema_version':'1.0','audit_id':'M26-HISTORICAL-BOUNDARY-COMPATIBILITY-V1',
         'stable_reference':'2011+ 92 local constituency geometry','years':years,'transitions':transitions,
         'rule':'Boundary mismatch never triggers fuzzy row dropping/duplication. National layer remains usable independently.',
         'F0_modified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'years':{y:v['native_local_rows'] for y,v in years.items()},
                      'blocked_transitions':[x['transition'] for x in transitions if x['status']!='READY']},sort_keys=True))
if __name__=='__main__': main()
