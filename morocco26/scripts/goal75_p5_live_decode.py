#!/usr/bin/env python3
import hashlib,json,math
from collections import Counter,defaultdict
from pathlib import Path
R=Path(__file__).resolve().parents[1];D=R/'data';O=D/'goal75';O.mkdir(exist_ok=True)

def load(p):return json.loads(Path(p).read_text())
def dump_hash(x):return hashlib.sha256(json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def read_jsonl(p):return [json.loads(x) for x in Path(p).read_text().splitlines() if x.strip()]

def tier(margin,expressed):
    pct=100*margin/max(1,expressed)
    if margin<=500 or pct<=0.5:return 'ULTRA_MARGINAL_2021'
    if margin<=1500 or pct<=1.5:return 'MARGINAL_2021'
    if margin<=4000 or pct<=4:return 'COMPETITIVE_2021'
    return 'BUFFERED_2021'

def main():
    p2=load(O/'p2_exact_audit.json')
    assert p2['local']['constituencies']==92 and p2['local']['seats']==305
    assert p2['regional']['constituencies']==12 and p2['regional']['seats']==90
    assert p2['total']['exact_official_match'] is True
    margins=load(O/'seat_margin_92.json');events=read_jsonl(D/'events_2026_goal75.jsonl');coverage=load(D/'candidate_coverage_2026.json')
    assert len(margins)==92
    byid={x['constituency_id']:x for x in margins}
    localized=defaultdict(list);national=[];unmatched=[]
    for e in events:
        assert e.get('quantified_effect') is None, f"event effect was quantified without evidence: {e['event_id']}"
        if e.get('geography_type')=='constituency':
            for cid in e.get('geographies',[]):
                if cid not in byid:unmatched.append({'event_id':e['event_id'],'geography':cid})
                else:localized[cid].append(e)
        elif e.get('geography_type')=='national':national.append(e)
    assert not unmatched, unmatched
    rows=[]
    for x in margins:
        margin=int(x['raw_margin_votes']);expressed=int(x['expressed']);pct=100*margin/max(1,expressed);ev=localized.get(x['constituency_id'],[])
        rows.append({
            'constituency_id':x['constituency_id'],'name':x['name'],'region':x['region'],'seats':x['seats'],
            'baseline_2021':{'raw_last_seat_margin_votes':margin,'margin_pct_expressed':pct,'last_rank_party':x['last_rank_party'],'first_nonwinner':x['first_nonwinner'],'sensitivity_tier':tier(margin,expressed),'source_url':x['source_url']},
            'localized_2026_events':[{'event_id':e['event_id'],'title':e['title'],'observed_at':e['observed_at'],'parties':e['parties'],'mechanism_tags':e['mechanism_tags'],'evidence_level':e['evidence_level'],'source_ids':e['source_ids'],'effect_direction':'UNKNOWN_UNQUANTIFIED','seat_consequence':'NOT_INFERRED','falsification_question':e['falsification_question']} for e in ev],
            'research_priority_only':{'has_local_event':bool(ev),'priority_basis':'historical cutoff sensitivity + existence of sourced local event; NOT probability of winning or seat forecast'}
        })
    order={'ULTRA_MARGINAL_2021':0,'MARGINAL_2021':1,'COMPETITIVE_2021':2,'BUFFERED_2021':3}
    watch=sorted(rows,key=lambda r:(0 if r['localized_2026_events'] else 1,order[r['baseline_2021']['sensitivity_tier']],r['baseline_2021']['raw_last_seat_margin_votes'],r['constituency_id']))
    party_cov={x['party']:x for x in coverage['parties']}
    required=['RNI','PAM','PI','PJD','PPS']
    candidate_gate=all(p in party_cov and party_cov[p]['represented_local_slots']>0 for p in required)
    tiers=Counter(r['baseline_2021']['sensitivity_tier'] for r in rows)
    output={
      'as_of':coverage['as_of'],'mode':'PROSPECTIVE_DECODING_NOT_FORECAST','p2_parent_hash':dump_hash(p2),
      'territorial_coverage':{'local_constituencies':92,'regional_constituencies':12,'local_seats':305,'regional_seats':90},
      'historical_sensitivity_distribution':dict(tiers),'localized_event_constituencies':len(localized),'localized_event_count':sum(len(v) for v in localized.values()),'national_context_events':len(national),
      'candidate_coverage':{'required_parties':required,'gate_pass':candidate_gate,'source_as_of':coverage['as_of'],'method_note':coverage['method_note'],'parties':{p:party_cov[p] for p in required}},
      'rules':[
        '2021 cutoff sensitivity is historical structure, not a 2026 win probability.',
        'No event receives a directional or quantitative vote effect without empirical evidence.',
        'Research-priority ordering is not a seat-risk forecast.',
        'National forecast remains blocked by project constitution.'
      ],
      'constituencies':rows,'investigation_watchlist':watch
    }
    forbidden=('projected_seats','win_probability','seat_probability','forecast_share','predicted_winner')
    blob=json.dumps(output,ensure_ascii=False).lower()
    no_forecast=all(k not in blob for k in forbidden)
    gates={
      'p2_exact_parent':True,'92_local_rows':len(rows)==92,'all_rows_have_provenance':all(r['baseline_2021']['source_url'] for r in rows),
      'localized_events_geocoded':not unmatched,'localized_event_minimum':sum(len(v) for v in localized.values())>=4,'candidate_coverage_required_parties':candidate_gate,
      'no_quantified_event_effects':all(e.get('quantified_effect') is None for e in events),'no_forecast_fields':no_forecast,
      'forecast_status_remains_blocked':p2.get('forecast_status')=='BLOCKED'
    }
    gate_pass=all(gates.values());summary={'gate_pass':gate_pass,'gates':gates,'scientific_credit_if_pass_points':10,'mode':'PROSPECTIVE_DECODING_NOT_FORECAST','rows':92,'localized_event_count':sum(len(v) for v in localized.values()),'tiers':dict(tiers)}
    output['snapshot_hash']=dump_hash(output);summary['snapshot_hash']=output['snapshot_hash']
    (O/'live_decoding_2026.json').write_text(json.dumps(output,ensure_ascii=False,indent=2));(O/'p5_live_gate.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False,indent=2));raise SystemExit(0 if gate_pass else 7)
if __name__=='__main__':main()
