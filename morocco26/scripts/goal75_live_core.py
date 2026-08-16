#!/usr/bin/env python3
import json,statistics
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75'
def load(p):return json.loads(Path(p).read_text())
def events(path):return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]
def bucket(pp):
 if pp<=.25:return 'ULTRA_TIGHT'
 if pp<=.75:return 'TIGHT'
 if pp<=2:return 'WATCH'
 return 'WIDE'
def main():
 score=load(O/'goal75_scoring.json');m=load(O/'seat_margin_92.json');dev=load(O/'stage1_acquisition.json');hold=load(O/'unsealed_holdout_2021.json');cc=load(D/'candidate_coverage_2026.json');ev=events(D/'events_2026_goal75.jsonl')
 assert score['local_92']['aggregate_exact_match'] and score['regional_12']['aggregate_exact_match']
 truth={x['constituency_id']:x['2021'] for x in dev['development']};truth.update({x['constituency_id']:x['2021'] for x in hold})
 local_events={}
 for e in ev:
  if e['geography_type']=='constituency':
   for cid in e['geographies']:local_events.setdefault(cid,[]).append(e)
 rows=[]
 for x in m:
  y=truth[x['constituency_id']];pp=100*x['raw_margin_votes']/y['expressed'];rp=100*x['raw_margin_votes']/y['registered']
  es=[]
  for e in local_events.get(x['constituency_id'],[]):
   es.append({'event_id':e['event_id'],'title':e['title'],'mechanism_tags':e['mechanism_tags'],'parties':e['parties'],'evidence_level':e['evidence_level'],'source_ids':e['source_ids'],'falsification_question':e['falsification_question'],'directional_party_effect':None,'quantified_effect':None})
  rows.append({'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'seats':x['seats'],'registered_2021':y['registered'],'expressed_2021':y['expressed'],'raw_margin_votes':x['raw_margin_votes'],'margin_pp_expressed':pp,'margin_pp_registered':rp,'fragility_bucket':bucket(pp),'legal_winners_2021':x['legal_winners'],'candidate_evidence_status':'PARTY_LEVEL_COVERAGE_SNAPSHOT_NO_LOCAL_IMPUTATION','mapped_2026_events':es,'interpretation_label':'SENSITIVITY_NOT_FORECAST'})
 counts={k:sum(r['fragility_bucket']==k for r in rows) for k in ['ULTRA_TIGHT','TIGHT','WATCH','WIDE']};local=[e for e in ev if e['geography_type']=='constituency'];mapped={q['event_id'] for r in rows for q in r['mapped_2026_events']};national=[e for e in ev if e['geography_type']=='national']
 out={'as_of':'2026-08-16','publication_status':'SENSITIVITY_NOT_FORECAST','north_star_use':'Prospective territorial decoder: observed 2021 cutoff sensitivity + sourced 2026 mechanisms. No party effect is inferred without empirical quantification.','constituencies':rows,'summary':{'constituencies':len(rows),'fragility_counts':counts,'median_margin_votes':statistics.median(r['raw_margin_votes'] for r in rows),'median_margin_pp_expressed':statistics.median(r['margin_pp_expressed'] for r in rows),'events_total':len(ev),'local_events':len(local),'local_events_mapped':len(mapped),'national_context_events':len(national),'candidate_records':cc['total_candidate_records'],'candidate_method_note':cc['method_note']},'national_context':[{'event_id':e['event_id'],'title':e['title'],'mechanism_tags':e['mechanism_tags'],'source_ids':e['source_ids'],'directional_party_effect':None} for e in national]}
 gates={'exact_92_local_truth':len(rows)==92,'exact_12_regional_audit':score['regional_12']['aggregate_exact_match'],'all_rows_have_registered_and_expressed':all(r['registered_2021'] and r['expressed_2021'] for r in rows),'all_rows_labeled_not_forecast':all(r['interpretation_label']=='SENSITIVITY_NOT_FORECAST' for r in rows),'candidate_snapshot_no_imputation':'not imputed' in cc['method_note'].lower(),'event_ledger_has_provenance':all(e.get('source_ids') and e.get('falsification_question') for e in ev),'all_local_events_mapped':len(mapped)==len(local),'no_invented_directional_effect':all(q['directional_party_effect'] is None and q['quantified_effect'] is None for r in rows for q in r['mapped_2026_events']),'national_events_are_context_only':all(x['directional_party_effect'] is None for x in out['national_context']),'forecast_still_blocked':score['forecast_status']=='BLOCKED'}
 gate={'status':'PASS' if all(gates.values()) else 'FAIL','gates':gates,'p5_scientific_credit_points':10 if all(gates.values()) else 0,'credit_scope':'P5 partial: full territorial sensitivity substrate + current sourced event-mechanism ledger; does NOT claim full live automation, calibrated 2026 party effects, or forecast.'}
 (O/'live_2026_mechanism_map.json').write_text(json.dumps(out,ensure_ascii=False,indent=2));(O/'goal75_live_gate.json').write_text(json.dumps(gate,ensure_ascii=False,indent=2));print(json.dumps({'summary':out['summary'],'gate':gate},ensure_ascii=False,indent=2));raise SystemExit(0 if all(gates.values()) else 4)
if __name__=='__main__':main()
