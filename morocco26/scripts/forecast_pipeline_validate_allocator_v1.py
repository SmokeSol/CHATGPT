#!/usr/bin/env python3
"""Replay legal allocators and compare them with independent official aggregate seat references."""
from __future__ import annotations
import importlib.util, json, re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; G=ROOT/'data'/'goal100'; HIST=G/'historical'; FP=G/'forecast_pipeline'
OUT=FP/'legal_allocator_historical_replay_v1.json'; REG=FP/'legal_regimes_v1.json'; REF=FP/'legal_reference_results_v1.json'
spec=importlib.util.spec_from_file_location('lsa',ROOT/'scripts'/'legal_seat_allocator.py')
lsa=importlib.util.module_from_spec(spec); spec.loader.exec_module(lsa)
CORE={'PJD','PI','RNI','PAM','USFP','MP','UC','PPS'}

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def discover():
    pat=re.compile(r'tafra_legislative_(\d{4})_canonical\.json$'); out={}
    for p in HIST.glob('tafra_legislative_*_canonical.json'):
        m=pat.match(p.name)
        if m: out[int(m.group(1))]=p
    return dict(sorted(out.items()))
def local(p):
    d=rj(p); return [x for x in d['rows'] if str(x.get('list_type','')).lower() in {'local','locale'}]

def reference_compare(year,aggregate,universe,references):
    ref=references.get(str(year))
    if not ref: return {'status':'NO_INDEPENDENT_REFERENCE_REGISTERED'}
    expected={str(k):int(v) for k,v in ref['local_seats_by_published_party_code'].items()}
    observed={str(k):int(v) for k,v in aggregate.items() if int(v)>0}
    keys=sorted(set(expected)|set(observed))
    deltas={k:observed.get(k,0)-expected.get(k,0) for k in keys if observed.get(k,0)!=expected.get(k,0)}
    missing=[k for k,v in expected.items() if v>0 and k not in universe]
    expected_core={k:v for k,v in expected.items() if k in CORE}
    observed_core={k:observed.get(k,0) for k in expected_core}
    exact=(not deltas and sum(observed.values())==int(ref['local_seats_total']))
    return {
      'status':'PASS_EXACT_AGGREGATE_REFERENCE' if exact else 'FAIL_AGGREGATE_REFERENCE_MISMATCH',
      'reference_local_seats_total':int(ref['local_seats_total']),
      'reference_source':ref['source'],
      'expected_local_seats_by_published_party_code':expected,
      'seat_deltas_model_minus_reference':deltas,
      'missing_or_unmapped_reference_winner_codes_in_canonical_vote_universe':sorted(missing),
      'canonical_vote_key_count':len(universe),
      'canonical_vote_key_universe':sorted(universe),
      'core_eight_exact_match':observed_core==expected_core,
      'expected_core_eight':expected_core,
      'observed_core_eight':observed_core,
      'interpretation':('Legal replay exactly reproduces the independent published local-seat totals.' if exact else
        'Current canonical votes plus the legal allocator do not reproduce the independent published totals. Treat exact seat conversion for this year as unvalidated; missing/unmapped winning party codes are a concrete data-universe warning, not something to patch from the target result.')
    }

def main():
    registry=rj(REG)['regimes']; references=rj(REF)['years']; years={}
    for year,path in discover().items():
        rule=registry.get(str(year),{}).get('local')
        if not rule: continue
        rows=local(path); aggregate=Counter(); universe=set(); ok=blocked=ties=unalloc=errors=0; examples=[]
        for r in rows:
            universe.update(str(k) for k in r.get('votes',{}))
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
        reference=reference_compare(year,aggregate,universe,references)
        years[str(year)]={
          'local_rows':len(rows),'expected_native_local_rows':registry[str(year)].get('native_local_constituencies'),
          'fully_allocated_without_unresolved_tie':ok,'blocked_missing_registered_voters':blocked,
          'tie_rows':ties,'unallocated_rows':unalloc,'error_rows':errors,
          'modelled_local_seat_total':sum(aggregate.values()),'modelled_local_seats_by_list':dict(aggregate.most_common()),
          'canonical_vote_key_count':len(universe),'canonical_vote_key_universe':sorted(universe),
          'independent_reference_validation':reference,'errors':examples,
          'validation_scope':'MECHANICAL_REPLAY_PLUS_INDEPENDENT_AGGREGATE_OFFICIAL_REFERENCE_WHEN_AVAILABLE'
        }
    pass_years=[y for y,v in years.items() if v['independent_reference_validation']['status']=='PASS_EXACT_AGGREGATE_REFERENCE']
    fail_years=[y for y,v in years.items() if v['independent_reference_validation']['status']=='FAIL_AGGREGATE_REFERENCE_MISMATCH']
    out={'schema_version':'1.1','result_id':'M26-LEGAL-ALLOCATOR-HISTORICAL-REPLAY-V1','years':years,
         'independent_reference_pass_years':pass_years,'independent_reference_fail_years':fail_years,
         'allocator_validation_status':('PARTIAL_PASS_WITH_EXPLICIT_DATA_BLOCKS' if pass_years else 'NO_INDEPENDENT_REFERENCE_PASS'),
         'interpretation':'Historical threshold-qualified regimes are replayed at native district geometry. A mechanical 305-seat sum is not sufficient: an election is independently validated only when its aggregate party seat distribution matches published reference totals. Registered-voter quotient years remain blocked where canonical registered counts are absent.',
         'F0_modified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'pass_reference_years':pass_years,'fail_reference_years':fail_years,'years':{y:{'rows':v['local_rows'],'blocked':v['blocked_missing_registered_voters']} for y,v in years.items()}},sort_keys=True))
if __name__=='__main__': main()
