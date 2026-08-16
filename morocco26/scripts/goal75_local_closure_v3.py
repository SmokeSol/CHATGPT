#!/usr/bin/env python3
import csv,json
from io import BytesIO
from pathlib import Path
import pandas as pd, requests
import goal75_local_closure_v2c as w
c=w.closure
ROOT=Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; OUT=DATA/'goal75'

def same(a,b): return {k:int(v) for k,v in a.items() if int(v)}=={k:int(v) for k,v in b.items() if int(v)}
def main():
    r=requests.get(c.TAFRA_URL,timeout=90,headers={'User-Agent':'MOROCCO26 research'}); r.raise_for_status(); frame=pd.read_excel(BytesIO(r.content),sheet_name='donnees')
    party=[x for x in frame.columns if x not in c.META]; lf=frame[frame['typeListe'].astype(str).str.lower().eq('locale')]; rows=[]
    for _,z in lf.iterrows():
        votes={str(x):int(z[x]) for x in party if pd.notna(z[x]) and float(z[x])>0}; rows.append({'idCirconscription':str(int(z['idCirconscription'])),'circonscription':str(z['circonscription']),'region':str(z['region']),'seats':int(z['nSieges']),'votes':votes,'valid_vote_sum':sum(votes.values())})
    cfg=list(csv.DictReader((DATA/'constituencies_goal75.csv').open(encoding='utf-8'))); obs0=json.loads((OUT/'observed_elected_2021.json').read_text())['local']; obs={c.norm(k):v for k,v in obs0.items()}; proof={str(x['idCirconscription']):x for x in json.loads((OUT/'local_allocation_interval_proof.json').read_text())['rows']}; ev={x['constituency_id']:x for x in json.loads((DATA/'local_exception_registered_2021_goal75.json').read_text())['direct']}
    resolved=[]; inv=0; direct=0
    for x in cfg:
        row=w.strict_best_row(x['name'],rows); key=c.norm(row['circonscription']); target=obs.get(key) or obs.get(c.CONFIG_TO_TAFRA.get(c.norm(x['name']),c.norm(x['name'])))
        if target is None: raise RuntimeError(f'missing observed {x["name"]}/{row["circonscription"]}')
        p=proof[row['idCirconscription']]
        if p['invariant_to_topN_over_full_interval']:
            alloc=p['target_topN_one_each']; tier='A_DENOMINATOR_FREE_EXACT_INTERVAL_PROOF'; registered=None; source='mathematical full-integer interval proof'; inv+=1
        else:
            if x['constituency_id'] not in ev: raise RuntimeError(f'missing sensitive denominator {x["constituency_id"]}')
            e=ev[x['constituency_id']]; registered=int(e['registered']); alloc=c.allocate(row['votes'],int(x['seats']),registered); tier='B_QUARANTINED_DENOMINATOR_REPRODUCTION'; source=e['source']; direct+=1
        if not same(alloc,target): raise RuntimeError(f'local mismatch {x["name"]}: {alloc} != {target}')
        resolved.append({'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'seats':int(x['seats']),'tafra_name':row['circonscription'],'legal_allocation':alloc,'observed_elected':target,'evidence_tier':tier,'registered_used':registered,'source':source,'forecast_unlock_eligible':False if registered is not None else None})
    out={'audit_id':'M26-LOCAL-92-TIERED-V3','local_constituencies':len(resolved),'local_seats':sum(x['seats'] for x in resolved),'invariant_exact_rows':inv,'denominator_sensitive_reproduced_rows':direct,'all_92_empirically_reproduced':len(resolved)==92 and inv==81 and direct==11,'primary_denominator_complete':False,'forecast_status':'BLOCKED','rows':resolved}
    (OUT/'local_92_closure_v3.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=False,indent=2)); raise SystemExit(0 if out['all_92_empirically_reproduced'] and out['local_seats']==305 else 9)
if __name__=='__main__': main()
