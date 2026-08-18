#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data'/'goal100'/'e_reason'
OUT=ROOT/'data'/'goal100'/'agent_society_v2'/'audits'
OUT.mkdir(parents=True,exist_ok=True)

BUNDLES={
    '2016':E/'blind'/'development'/'blind_bundle.json',
    '2021':E/'blind'/'holdout'/'blind_bundle.json',
}
EXCLUDED={'BALLOT_LIST_PRESENT','EVIDENCE_COUNT','SOURCE_CLASS_MAX'}
DIRECTIONAL={
'INCUMBENT_SAME_PARTY_SAME_DISTRICT','INCUMBENT_SAME_PARTY_MOVED_DISTRICT','FORMER_MP','PARTY_SWITCH_IN','PARTY_SWITCH_OUT',
'LOCAL_EXECUTIVE_OFFICE','PROVINCIAL_OR_REGIONAL_OFFICE','NATIONAL_OR_REGIONAL_PARTY_OFFICE','FORMER_MINISTER_OR_NATIONAL_OFFICE',
'FORMAL_ENDORSEMENT','FORMAL_LIST_ALLIANCE','WITHDRAWN_OR_DISQUALIFIED','OFFICIAL_SANCTION_OR_INVESTIGATION','VERIFIED_DEATH_OR_INCAPACITY'
}


def read(p): return json.loads(p.read_text(encoding='utf-8'))

def valkey(v):
    if isinstance(v,(dict,list)): return json.dumps(v,sort_keys=True,ensure_ascii=False)
    return repr(v)

def audit(year,path):
    b=read(path)
    rows=[]; family_present=Counter(); family_discriminative=Counter(); family_true=Counter()
    for pkt in b['packets']:
        vals=defaultdict(list)
        statuses=defaultdict(Counter)
        for party in pkt['parties']:
            for f in party['features']:
                fid=f['feature_id']; statuses[fid][str(f.get('status'))]+=1
                if fid in EXCLUDED: continue
                if f.get('status')=='VERIFIED' and f.get('value') is not None and not f.get('conflict'):
                    vals[fid].append(f.get('value'))
        present=sorted(vals)
        discr=[]; truef=[]
        for fid,vs in vals.items():
            if len({valkey(v) for v in vs})>=2: discr.append(fid)
            if fid in DIRECTIONAL and any(v is True for v in vs): truef.append(fid)
            family_present[fid]+=1
            if fid in discr: family_discriminative[fid]+=1
            if fid in truef: family_true[fid]+=1
        rows.append({
            'anonymous_territory_id':pkt['anonymous_territory_id'],
            'present_nontrivial_families':present,
            'present_count':len(present),
            'discriminative_families':sorted(discr),
            'discriminative_count':len(discr),
            'directional_true_families':sorted(truef),
            'directional_true_count':len(truef),
        })
    return {
        'year':int(year),'territories':len(rows),'party_cells':sum(len(p['parties']) for p in b['packets']),
        'preregistered_context_gate_districts_ge_2_present':sum(r['present_count']>=2 for r in rows),
        'stronger_diagnostic_districts_ge_2_discriminative':sum(r['discriminative_count']>=2 for r in rows),
        'districts_ge_2_directional_true_families':sum(r['directional_true_count']>=2 for r in rows),
        'family_present_district_counts':dict(family_present.most_common()),
        'family_discriminative_district_counts':dict(family_discriminative.most_common()),
        'family_directional_true_district_counts':dict(family_true.most_common()),
        'territory_rows':rows,
    }

def main():
    result={
        'schema_version':'1.0','audit_id':'M26-ASV2-EXISTING-CONTEXT-POWER-AUDIT-V1',
        'target_outcomes_read':False,
        'note':'Preregistered ASV2 gate counts nontrivial VERIFIED feature families excluding only BALLOT_LIST_PRESENT/EVIDENCE_COUNT/SOURCE_CLASS_MAX. Stronger diagnostics additionally require within-territory cross-party variation and/or multiple directional true families; these diagnostics do not change the frozen gate.',
        'elections':{y:audit(y,p) for y,p in BUNDLES.items()},
    }
    result['preregistered_context_gate_pass_each_year']={y:x['preregistered_context_gate_districts_ge_2_present']>=50 for y,x in result['elections'].items()}
    (OUT/'existing_context_power_v1.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    compact={y:{k:v for k,v in x.items() if k not in {'territory_rows'}} for y,x in result['elections'].items()}
    print(json.dumps({'elections':compact,'gate_pass':result['preregistered_context_gate_pass_each_year']},ensure_ascii=False,indent=2))

if __name__=='__main__': main()
