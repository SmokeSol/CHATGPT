#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data'/'goal100'/'e_reason'/'evidence'
A=ROOT/'data'/'goal100'/'agent_society_v2'
G=ROOT/'data'/'goal100'/'geometry_2026_certificate.json'
AUG=A/'acquisition'/'2016_candidate_party_augmented_wave1.json'
OUT=A/'audits';OUT.mkdir(parents=True,exist_ok=True)

def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    geo=read(G); canonical={r['constituency_id'] for r in geo['local']['rows']}
    strict=read(E/'strict_2016_integrity_gate'/'gate.json')
    by=defaultdict(set); source_count=defaultdict(int)
    for d in strict['districts']:
        for x in d.get('candidate_keys',[]):
            if x.get('party'):by[d['constituency_id']].add(str(x['party']).upper())
    aug=read(AUG)
    invalid=[]
    for r in aug['records']:
        cid=r['constituency_id'];p=str(r['party']).upper()
        if cid not in canonical:invalid.append({'record':r,'reason':'UNKNOWN_CONSTITUENCY'});continue
        if not r.get('candidate') or not r.get('source_url') or not r.get('published'):invalid.append({'record':r,'reason':'MISSING_REQUIRED_FIELD'});continue
        if str(r['published'])>='2016-10-07':invalid.append({'record':r,'reason':'NOT_PRE_ELECTION'});continue
        by[cid].add(p);source_count[r['source_url']]+=1
    rows=[]
    for cid in sorted(canonical):
        ps=sorted(by[cid]);rows.append({'constituency_id':cid,'verified_candidate_parties':ps,'party_count':len(ps),'pass_ge_3':len(ps)>=3})
    passed=[r for r in rows if r['pass_ge_3']]
    residual=[r for r in rows if not r['pass_ge_3']]
    out={'schema_version':'1.0','audit_id':'M26-ASV2-2016-CANDIDATE-PARTY-AUGMENTED-WAVE1-AUDIT','target_outcome_used':False,'threshold_required':70,'invalid_augmented_records':invalid,'augmented_record_count':len(aug['records']),'source_record_counts':dict(source_count),'districts_ge_3_parties':len(passed),'gate_pass':len(passed)>=70,'passed':passed,'residual':residual,'residual_distribution':{str(k):sum(r['party_count']==k for r in residual) for k in sorted({r['party_count'] for r in residual})}}
    out['status']='PASS' if out['gate_pass'] and not invalid else 'FAIL'
    (OUT/'candidate_party_augmented_wave1_audit.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('passed','residual')},ensure_ascii=False,indent=2))
    print('PASSED',len(passed));print('RESIDUAL')
    for r in residual:print(r['constituency_id'],r['party_count'],','.join(r['verified_candidate_parties']))
if __name__=='__main__':main()
