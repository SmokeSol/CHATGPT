#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data'/'goal100'/'e_reason'/'blind'
OUT=ROOT/'data'/'goal100'/'agent_society_v2'/'bundle_schema_probe_v1.json'

def probe(path):
    b=json.loads(path.read_text(encoding='utf-8'))
    pkt=b['packets'][0]; party=pkt['parties'][0]; feat=party['features'][0]
    def types(d): return {k:type(v).__name__ for k,v in d.items()}
    return {
      'bundle_keys':sorted(b.keys()), 'packet_keys':sorted(pkt.keys()),
      'party_keys':sorted(party.keys()), 'feature_keys':sorted(feat.keys()),
      'bundle_types':types(b),'packet_types':types(pkt),'party_types':types(party),'feature_types':types(feat),
      'packets':len(b['packets']), 'party_cells':sum(len(p['parties']) for p in b['packets'])
    }

def main():
    out={'schema_version':'1.0','target_outcomes_read':False,'development_2016':probe(E/'development'/'blind_bundle.json'),'holdout_2021':probe(E/'holdout'/'blind_bundle.json')}
    OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
