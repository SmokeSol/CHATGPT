#!/usr/bin/env python3
import json,re,unicodedata
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'goal75'
def load(p): return json.loads(Path(p).read_text())
def norm(x): return re.sub('[^a-z0-9]+',' ',unicodedata.normalize('NFKD',str(x)).encode('ascii','ignore').decode().lower()).strip()

def main():
    proxy=load(OUT/'regional_exact_crossballot_test.json'); intervals=load(OUT/'regional_registered_intervals.json'); observed=load(OUT/'observed_elected_2021.json')
    rows=proxy['rows']; ir={norm(x['region']):x for x in intervals['rows']}; audited=[]; exact=0; unresolved=[]; agg=Counter()
    for row in rows:
        region=row['region']; key=norm(region); obs={k:int(v) for k,v in row['observed_independent'].items()}; agg.update(obs)
        interval=ir.get(key)
        if interval is None: raise RuntimeError(f'missing registered interval for {region}')
        if row['exact_match']:
            exact+=1; tier='A_PROXY_DENOMINATOR_REPRODUCES_OBSERVED_REGIONAL_OUTCOME'; status='REPRODUCED_WITH_QUARANTINED_EXTERNAL_N'
        else:
            tier='C_COMPLETE_VOTE_AND_OBSERVED_OUTCOME_LEGAL_DENOMINATOR_UNRESOLVED'; status='STRICT_LEGAL_REPLAY_UNRESOLVED'; unresolved.append(region)
        audited.append({'region':region,'seats':int(row['seats']),'vote_table_complete':True,'observed_elected':obs,'observed_seat_sum':sum(obs.values()),'evidence_tier':tier,'replay_status':status,'external_N_tested':int(row['registered_external']),'external_N_exact_match':bool(row['exact_match']),'observed_compatible_registered_intervals':interval['good_registered_intervals'],'forecast_unlock_eligible':False})
    expected_unresolved={'casablanca settat','marrakech safi'}
    if {norm(x) for x in unresolved}!=expected_unresolved: raise RuntimeError(f'unexpected unresolved regions {unresolved}')
    if len(audited)!=12 or sum(x['observed_seat_sum'] for x in audited)!=90 or exact!=10: raise RuntimeError('regional graph counts failed')
    if observed['regional_seats_observed']!=90 or observed['official_total_exact_match'] is not True: raise RuntimeError('independent member ground truth failed')
    # This audit deliberately certifies graph completeness, NOT exact legal replay.
    out={'audit_id':'M26-REGIONAL-GRAPH-V4','regions':12,'observed_seats':90,'vote_tables_complete':12,'proxy_N_exact_reproductions':exact,'strict_legal_replay_unresolved_regions':unresolved,'strict_legal_replay_complete':False,'empirical_graph_complete_for_held_out_testing':True,'independent_member_ground_truth_exact':True,'observed_regional_party_affiliation_aggregate':dict(sorted(agg.items())),'forecast_unlock_eligible':False,'forecast_status':'BLOCKED','epistemic_boundary':'Casablanca-Settat and Marrakech-Safi retain unresolved primary House denominator/list-affiliation mechanics; no post-hoc bridge is used to call them legal replays.','rows':audited}
    (OUT/'regional_graph_v4.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)); print(json.dumps({k:v for k,v in out.items() if k!='rows'},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
