#!/usr/bin/env python3
import csv,json
from collections import defaultdict
from pathlib import Path
import goal75_p2_exact as p
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75';O.mkdir(exist_ok=True)
EXPECTED=17983490

def main():
 rows=list(csv.DictReader(open(D/'constituencies_goal75.csv',encoding='utf-8')));regional=defaultdict(int);items=[]
 for i,x in enumerate(rows,1):
  _,url=p.g.resolve(x['name']);t=p.tabs(url)[-1];q=p.parse_table(t,x['constituency_id']);reg=q['registered']
  if not reg:raise RuntimeError(f'missing registered {x["name"]}')
  regional[x['region']]+=reg;items.append({'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'registered':reg,'source_url':url});print(i,x['name'],reg,flush=True)
 total=sum(x['registered'] for x in items);out={'expected_national_registered':EXPECTED,'secondary_local_registered_sum':total,'delta':total-EXPECTED,'exact_match':total==EXPECTED,'regional_sums':dict(sorted(regional.items())),'constituencies':items}
 (O/'registered_national_audit.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));print(json.dumps({k:out[k] for k in ['expected_national_registered','secondary_local_registered_sum','delta','exact_match','regional_sums']},ensure_ascii=False,indent=2));raise SystemExit(0 if out['exact_match'] else 6)
if __name__=='__main__':main()
