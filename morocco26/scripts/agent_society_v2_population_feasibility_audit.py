#!/usr/bin/env python3
from __future__ import annotations

import json, math
from pathlib import Path

import agent_society_v2_build_historical_populations_vectorized as v
import agent_society_v2_build_historical_populations as b

ROOT=Path(__file__).resolve().parents[1]
A=ROOT/'data'/'goal100'/'agent_society_v2'
GEO=ROOT/'data'/'goal100'/'geometry_2026_certificate.json'
OUT=A/'population_feasibility_audit_v1.json'


def dim_ess(m):
    return 1.0/sum(float(x)**2 for x in m.values() if float(x)>0)


def product_ess(targets):
    out=1.0
    dims={}
    for d,m in targets.items():
        e=dim_ess(m); dims[d]=e; out*=e
    return out,dims


def product_max_atom(targets):
    z=1.0
    for m in targets.values(): z*=max(float(x) for x in m.values())
    return z


def main():
    geo=json.loads(GEO.read_text(encoding='utf-8'))['local']['rows']
    raw=b.fetch_hcp(); tabs=v.base.hcp_tables(raw)
    result={'schema_version':'1.0','audit_id':'M26-ASV2-POPULATION-FEASIBILITY-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','purpose':'Distinguish intrinsic concentration of frozen marginals from 128-support compression failure. No target-election outcome is used.','target_outcomes_used':False,'frozen_gate_reference':{'effective_archetype_count_min':64,'max_single_archetype_weight':0.10},'elections':[]}
    for target,prior in [(2016,2011),(2021,2016)]:
        hrows=b.load_hist(prior); hmap,_=b.match_geometry_to_hist(geo,hrows)
        rows=[]; missing=[]
        for g in geo:
            cid=g['constituency_id']; prov=g['prefecture_or_province']
            try:
                demo=v.base.demo_margin(prov,tabs)[0]
                pol=b.political_margin(hmap[cid])
                targets={**demo,'prior_vote_or_abstention':pol}
                ess,dess=product_ess(targets); atom=product_max_atom(targets)
                rows.append({'constituency_id':cid,'prefecture_or_province':prov,'full_independent_product_ess':ess,'dimension_ess':dess,'full_product_max_atomic_weight':atom,'intrinsic_ess_gate_pass':ess>=64,'intrinsic_max_atom_gate_pass':atom<=0.10})
            except Exception as e:
                missing.append({'constituency_id':cid,'prefecture_or_province':prov,'error':type(e).__name__+':'+str(e)})
        vals=[r['full_independent_product_ess'] for r in rows]
        result['elections'].append({'target_year':target,'prior_year':prior,'territories_evaluated':len(rows),'territories_missing_demo':len(missing),'intrinsic_ess_pass_count':sum(r['intrinsic_ess_gate_pass'] for r in rows),'intrinsic_max_atom_pass_count':sum(r['intrinsic_max_atom_gate_pass'] for r in rows),'min_full_product_ess':min(vals) if vals else None,'median_full_product_ess':sorted(vals)[len(vals)//2] if vals else None,'max_full_product_ess':max(vals) if vals else None,'rows':rows,'missing':missing})
    result['interpretation_rule']='If most/full independent-product ESS values exceed 64 while the compressed 128-support builder fails ESS, the failure is engineering/support-design rather than intrinsic marginal concentration. Do not lower the frozen gate.'
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({y['target_year']:{k:y[k] for k in ['territories_evaluated','territories_missing_demo','intrinsic_ess_pass_count','min_full_product_ess','median_full_product_ess']} for y in result['elections']},indent=2))

if __name__=='__main__': main()
