#!/usr/bin/env python3
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data'/'goal100'/'e_reason'/'evidence'
OUT=ROOT/'data'/'goal100'/'agent_society_v2'/'audits'; OUT.mkdir(parents=True,exist_ok=True)

def read(p): return json.loads(p.read_text(encoding='utf-8'))

def audit2016():
    g=read(E/'strict_2016_integrity_gate'/'gate.json')
    rows=[]
    for d in g['districts']:
        parties=sorted({str(x.get('party') or '').upper() for x in d.get('candidate_keys',[]) if x.get('party')})
        rows.append({'constituency_id':d['constituency_id'],'verified_candidate_parties':parties,'party_count':len(parties),'identity_count':d.get('verified_distinct_candidate_identities',0)})
    return {'districts_total':len(rows),'districts_ge_3_parties':sum(r['party_count']>=3 for r in rows),'districts_ge_3_identities':sum(r['identity_count']>=3 for r in rows),'max_verified_parties_in_one_district':max((r['party_count'] for r in rows),default=0),'party_count_distribution':{str(k):sum(r['party_count']==k for r in rows) for k in sorted({r['party_count'] for r in rows})},'rows':rows}

def audit2021():
    gate=read(E/'2021_head_list_rank_enrichment'/'gate.json')
    roster=read(E/'2021_head_list_rank_enrichment'/'enriched_candidate_roster.json')
    by=defaultdict(set)
    for r in roster:
        cid=r.get('territory_id'); p=str(r.get('party_bucket') or '').upper()
        if cid and p and r.get('rank_evidence_status')=='EXPLICIT_CANDIDATS_TETES_DE_LISTE': by[cid].add(p)
    rows=[{'constituency_id':cid,'verified_candidate_parties':sorted(ps),'party_count':len(ps)} for cid,ps in sorted(by.items())]
    return {'gate_status':gate['status'],'districts_total':len(rows),'districts_ge_3_parties':sum(r['party_count']>=3 for r in rows),'max_verified_parties_in_one_district':max((r['party_count'] for r in rows),default=0),'party_count_distribution':{str(k):sum(r['party_count']==k for r in rows) for k in sorted({r['party_count'] for r in rows})},'rows':rows}

def main():
    out={'schema_version':'1.0','audit_id':'M26-ASV2-CANDIDATE-PARTY-COVERAGE-V1','target_outcomes_used':False,'required_districts_ge_3_parties':70,'2016':audit2016(),'2021':audit2021()}
    out['pass_by_year']={y:out[y]['districts_ge_3_parties']>=70 for y in ('2016','2021')}
    out['status']='PASS' if all(out['pass_by_year'].values()) else 'FAIL'
    (OUT/'candidate_party_coverage_v1.json').write_text(json.dumps(out,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({y:{k:v for k,v in out[y].items() if k!='rows'} for y in ('2016','2021')},ensure_ascii=False,indent=2)); print('PASS',out['pass_by_year'])

if __name__=='__main__': main()
