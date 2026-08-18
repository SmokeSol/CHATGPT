#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data'/'goal100'/'e_reason'/'evidence'
A=ROOT/'data'/'goal100'/'agent_society_v2'
G=ROOT/'data'/'goal100'/'geometry_2026_certificate.json'
WAVES=[A/'acquisition'/'2016_candidate_party_augmented_wave1.json',A/'acquisition'/'2016_candidate_party_augmented_wave2.json']
OUT=A/'audits';OUT.mkdir(parents=True,exist_ok=True)
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    canonical={r['constituency_id'] for r in read(G)['local']['rows']};by=defaultdict(set);invalid=[];n=0
    for d in read(E/'strict_2016_integrity_gate'/'gate.json')['districts']:
        for x in d.get('candidate_keys',[]):
            if x.get('party'):by[d['constituency_id']].add(str(x['party']).upper())
    for wp in WAVES:
        w=read(wp)
        for r in w['records']:
            n+=1;cid=r['constituency_id'];p=str(r['party']).upper()
            if cid not in canonical: invalid.append({'wave':wp.name,'record':r,'reason':'UNKNOWN_CONSTITUENCY'});continue
            if not r.get('candidate') or not r.get('source_url') or not r.get('published'):invalid.append({'wave':wp.name,'record':r,'reason':'MISSING_REQUIRED_FIELD'});continue
            if str(r['published'])>='2016-10-07':invalid.append({'wave':wp.name,'record':r,'reason':'NOT_PRE_ELECTION'});continue
            by[cid].add(p)
    rows=[]
    for cid in sorted(canonical):
        ps=sorted(by[cid]);rows.append({'constituency_id':cid,'verified_candidate_parties':ps,'party_count':len(ps),'pass_ge_3':len(ps)>=3})
    passed=[r for r in rows if r['pass_ge_3']];res=[r for r in rows if not r['pass_ge_3']]
    out={'schema_version':'1.0','audit_id':'M26-ASV2-2016-CANDIDATE-PARTY-COMBINED-WAVE2-AUDIT','target_outcome_used':False,'threshold_required':70,'augmented_record_count':n,'invalid_records':invalid,'districts_ge_3_parties':len(passed),'gate_pass':len(passed)>=70,'residual_distribution':{str(k):sum(r['party_count']==k for r in res) for k in sorted({r['party_count'] for r in res})},'passed':passed,'residual':res,'status':'PASS' if len(passed)>=70 and not invalid else 'FAIL'}
    (OUT/'candidate_party_combined_wave2_audit.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ('passed','residual')},ensure_ascii=False,indent=2));print('RESIDUAL');
    for r in res:print(r['constituency_id'],r['party_count'],','.join(r['verified_candidate_parties']))
if __name__=='__main__':main()
