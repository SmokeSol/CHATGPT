#!/usr/bin/env python3
from __future__ import annotations

import json, re, unicodedata
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
GEO=ROOT/'data'/'goal100'/'geometry_2026_certificate.json'
OUT=ROOT/'data'/'goal100'/'agent_society_v2'/'audits'
OUT.mkdir(parents=True,exist_ok=True)

def norm(s):
    x=unicodedata.normalize('NFKD',str(s or ''))
    x=''.join(c for c in x if not unicodedata.combining(c)).lower()
    x=x.replace('prefecture:','').replace('province:','')
    return re.sub(r'[^a-z0-9]+',' ',x).strip()

def main():
    g=json.loads(GEO.read_text(encoding='utf-8'))
    rows=g['local']['rows']
    by_admin=defaultdict(list)
    for r in rows:
        by_admin[norm(r['prefecture_or_province'])].append({
            'constituency_id':r['constituency_id'],
            'constituency_name':r['repo_name'],
            'prefecture_or_province':r['prefecture_or_province'],
            'seats':r['repo_seats'],
        })
    direct=[]; split=[]
    for k,rs in sorted(by_admin.items()):
        obj={'admin_key':k,'prefecture_or_province':rs[0]['prefecture_or_province'],'constituencies':rs,'constituency_count':len(rs),'seats':sum(x['seats'] for x in rs)}
        (direct if len(rs)==1 else split).append(obj)
    result={
        'schema_version':'1.0','audit_id':'M26-ASV2-GEO-CROSSWALK-FEASIBILITY-V1',
        'geometry_certificate_gate':g.get('gate'),
        'local_constituencies':len(rows),
        'distinct_prefecture_or_province_units':len(by_admin),
        'direct_whole_admin_constituencies_count':sum(len(x['constituencies']) for x in direct),
        'split_admin_constituencies_count':sum(len(x['constituencies']) for x in split),
        'direct_admin_units_count':len(direct),'split_admin_units_count':len(split),
        'direct_admin_units':direct,'split_admin_units':split,
        'interpretation':'Units with one electoral constituency can use the HCP province/prefecture aggregate as an exact administrative demographic source if the legal geometry confirms full-unit coverage. Multi-constituency units require an explicit commune/arrondissement composition crosswalk; no demographic split may be inferred from names alone.',
        'target_outcome_used':False,
    }
    (OUT/'geo_crosswalk_feasibility_v1.json').write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('direct_admin_units','split_admin_units')},ensure_ascii=False,indent=2))
    print('SPLIT UNITS')
    for x in split:
        print(x['prefecture_or_province'], '=>', [r['constituency_id'] for r in x['constituencies']])

if __name__=='__main__': main()
