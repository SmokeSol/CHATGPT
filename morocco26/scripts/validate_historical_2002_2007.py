#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, re
from datetime import date
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
HROOT=ROOT/'data'/'goal100'/'historical'
PRE_SCRIPT=ROOT/'scripts'/'historical_pre_election_2002_2007.py'
ALLOWED_XW={'EXACT','RENAMED','SPLIT','MERGED','PARTIAL','AMBIGUOUS','UNRESOLVED'}
EXPECTED={2002:91,2007:95}
PARTIES_CONTESTING={2002:26,2007:33}

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def dump(p,obj): Path(p).write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
def fail(msg): raise SystemExit('HISTORICAL_GATE_FAIL: '+msg)

def validate_manifest(outdir,name):
    m=rj(outdir/name)
    for e in m.get('files',[]):
        p=ROOT/e['path']
        if not p.exists(): fail(f'manifest missing {e["path"]}')
        if sha_file(p)!=e['sha256']: fail(f'manifest hash mismatch {e["path"]}')
    return True

def validate_snapshot(year):
    out=HROOT/str(year); snap=rj(out/'pre_election_snapshot.json'); src=rj(out/'source_inventory_snapshot.json'); cert=rj(out/'anti_leakage_certificate.json')
    cutoff=date.fromisoformat(snap['cutoff'])
    if snap.get('target_outcome_present') is not False: fail(f'{year} snapshot outcome flag')
    if snap.get('anti_leakage_assertion')!='TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT': fail(f'{year} snapshot assertion')
    if cert.get('assertion')!='TARGET_OUTCOME_NOT_USED_IN_PRE_ELECTION_SNAPSHOT' or cert.get('same_year_outcome_imported') is not False or cert.get('same_year_raw_xlsx_opened') is not False: fail(f'{year} certificate')
    if not PRE_SCRIPT.exists(): fail('pre-election generator missing')
    text=PRE_SCRIPT.read_text(encoding='utf-8')
    for token in ['older_history_probe','.xlsx','legislative_2002_outcome_canonical','legislative_2007_outcome_canonical']:
        if token in text: fail(f'pre-election generator forbidden dependency token: {token}')
    source_ids=set()
    req={'source_id','source_class','url','publication_date','archive_date','access_date','territory','party','candidate','fact','status','provenance'}
    temporal=[]
    for s in src.get('sources',[]):
        source_ids.add(s.get('source_id'))
        if set(s)!=req: fail(f'{year} source schema differs for {s.get("source_id")}')
        st=s.get('status')
        if st not in {'VERIFIED','AMBIGUOUS','MISSING'}: fail(f'{year} invalid source status')
        pub=s.get('publication_date')
        if st=='VERIFIED':
            if not pub: fail(f'{year} VERIFIED source missing publication date {s.get("source_id")}')
            if date.fromisoformat(pub)>cutoff: fail(f'{year} temporal leakage {s.get("source_id")} {pub}>{cutoff}')
            temporal.append(s['source_id'])
    for f in snap.get('verified_facts',[]):
        if f.get('source_id') not in source_ids: fail(f'{year} fact orphan source {f.get("fact_id")}')
    for u in snap.get('territory_snapshot',[]):
        for k,v in u.get('fields',{}).items():
            if v.get('status')=='MISSING' and v.get('value') is not None: fail(f'{year} missing coerced {u.get("territory")}:{k}')
            if v.get('status')=='MISSING' and v.get('value') in (0,False): fail(f'{year} missing converted to zero/false')
    validate_manifest(out,'snapshot_manifest.json')
    hashes=rj(out/'snapshot_hashes_sha256.json')['files']
    for fn,h in hashes.items():
        if sha_file(out/fn)!=h: fail(f'{year} snapshot hashes file mismatch {fn}')
    return {'temporal_verified_sources':len(temporal),'snapshot':snap,'sources':src}

def validate_outcome(year):
    out=HROOT/str(year); oc=rj(out/f'legislative_{year}_outcome_canonical.json'); xw=rj(out/'crosswalk_to_modern.json'); cov=rj(out/'coverage_outcome.json')
    rows=oc.get('local_rows',[])
    if len(rows)!=EXPECTED[year]: fail(f'{year} outcome row count {len(rows)}')
    if sum(int(r['magnitude']) for r in rows)!=295: fail(f'{year} magnitude sum')
    if oc.get('seat_arithmetic',{}).get('status')!='PASS': fail(f'{year} seat arithmetic')
    for r in xw.get('rows',[]):
        typ=r.get('mapping_type')
        if typ not in ALLOWED_XW: fail(f'{year} crosswalk type {typ}')
        if typ in {'UNRESOLVED','AMBIGUOUS'} and r.get('modern_targets'): fail(f'{year} unresolved has target')
        if typ=='EXACT' and len(r.get('modern_targets',[]))!=1: fail(f'{year} exact mapping target count')
    validate_manifest(out,'outcome_manifest.json')
    hashes=rj(out/'outcome_hashes_sha256.json')['files']
    for fn,h in hashes.items():
        if sha_file(out/fn)!=h: fail(f'{year} outcome hash mismatch {fn}')
    if year==2007 and oc['district_seat_reconstruction']['status']!='PASS_EXACT_OFFICIAL_AGGREGATE_MATCH':
        # Not fatal for source reconstruction, but blocks seat-complete PASS.
        pass
    return {'outcome':oc,'crosswalk':xw,'coverage':cov}

def validate_git_freeze_order(year):
    out=HROOT/str(year)
    snap_rel=str((out/'snapshot_manifest.json').relative_to(ROOT))
    outcome_rel=str((out/f'legislative_{year}_outcome_canonical.json').relative_to(ROOT))
    def first_add(path):
        txt=subprocess.check_output(['git','log','--diff-filter=A','--format=%H','--',path],cwd=ROOT,text=True).strip().splitlines()
        if not txt: fail(f'{year} no git add commit for {path}')
        return txt[-1]
    sc=first_add(snap_rel); oc=first_add(outcome_rel)
    r=subprocess.run(['git','merge-base','--is-ancestor',sc,oc],cwd=ROOT)
    if r.returncode!=0 or sc==oc: fail(f'{year} snapshot commit is not a strict ancestor of outcome commit')
    return {'status':'PASS','snapshot_freeze_commit':sc,'outcome_ingest_commit':oc}

def acceptance(year,snapshot_result,outcome_result):
    out=HROOT/str(year); freeze_order=validate_git_freeze_order(year); sc=rj(out/'coverage_snapshot.json'); oc=outcome_result['coverage']; amb_s=rj(out/'ambiguities_snapshot.json'); amb_o=rj(out/'ambiguities_outcome.json')
    facts=rj(out/'pre_election_snapshot.json')['verified_facts']
    inc=[f for f in facts if f.get('fact_type') in {'incumbency','incumbent_head'} and f.get('status')=='VERIFIED']
    switches=[f for f in facts if f.get('fact_type')=='party_switch' and f.get('status')=='VERIFIED']
    local=[f for f in facts if f.get('fact_type')=='local_office' and f.get('status')=='VERIFIED']
    total_amb=len(amb_s.get('ambiguities',[]))+len(amb_o.get('ambiguities',[]))
    source_inv=rj(out/'source_inventory_snapshot.json')['sources']+rj(out/'source_inventory_outcome.json')['sources']
    classes={}
    for s in source_inv: classes[s['source_class']]=classes.get(s['source_class'],0)+1
    outcome_matrix=oc['local_vote_matrix_status']
    map_cov=float(sc['native_map_pre_election_coverage_pct'])
    allocator=oc['district_seat_allocation_status']
    if year==2007 and map_cov==100.0 and outcome_matrix.startswith('OFFICIAL') and allocator=='PASS_EXACT_OFFICIAL_AGGREGATE_MATCH': status='PASS_FOR_ROLLING_ORIGIN_BACKTEST'
    elif year==2007 and outcome_matrix.startswith('OFFICIAL'):
        status='PARTIAL_PRE_ELECTION_SNAPSHOT'
    elif year==2002:
        status='PARTIAL_PRE_ELECTION_SNAPSHOT'
    else: status='BLOCKED'
    gate={
      'schema_version':'1.0','year':year,'scientific_status':status,
      'real_constituency_count':EXPECTED[year],
      'outcome_covered_pct':oc['outcome_territory_coverage_pct'],
      'outcome_coverage_definition':'share of native local constituencies with a result row; matrix completeness is reported separately',
      'local_vote_matrix_status':outcome_matrix,
      'crosswalk_exact_pct':oc['crosswalk_EXACT_pct'],'crosswalk_approx_pct':oc['crosswalk_APPROX_pct'],'crosswalk_unresolved_pct':oc['crosswalk_UNRESOLVED_pct'],
      'parties_contesting_reported':PARTIES_CONTESTING[year],
      'party_vote_columns_documented':oc['party_columns_documented'],
      'candidate_coverage_pct':sc.get('candidate_coverage_pct'),'candidate_names_verified_count':sc.get('candidate_names_verified_count'),'candidate_denominator_documented':sc.get('candidate_denominator_documented'),
      'incumbent_coverage_pct':None,'incumbent_verified_facts':len(inc),'incumbent_coverage_reason':'MISSING_COMPLETE_PRE_ELECTION_INCUMBENT_ROSTER',
      'party_switch_coverage_pct':None,'party_switch_verified_facts':len(switches),'party_switch_coverage_reason':'MISSING_COMPLETE_SWITCH_DENOMINATOR',
      'local_office_coverage_pct':None,'local_office_verified_facts':len(local),'local_office_coverage_reason':'MISSING_COMPLETE_LOCAL_OFFICE_DENOMINATOR',
      'facts_VERIFIED':sc['facts_VERIFIED'],'facts_AMBIGUOUS':sc['facts_AMBIGUOUS'],'facts_MISSING':sc['facts_MISSING'],
      'unresolved_contradictions':total_amb,'source_quality_counts':classes,
      'district_seat_allocation_status':allocator,
      'sufficient_for_backtest':('2007 local outcome is materially complete, but strict rolling-origin requires a frozen full pre-election native map/candidate surface; current snapshot is partial.' if year==2007 and status!='PASS_FOR_ROLLING_ORIGIN_BACKTEST' else
                                 '2002 provides a full pre-election technical map and useful raw facts, but its detailed local party-vote matrix is explicitly incomplete; it cannot support a full vote-share rolling-origin fold.' if year==2002 else 'yes'),
      'not_sufficient_for':('Full 2002 target vote-share scoring across all parties and reliable district seat reconstruction.' if year==2002 else 'Strict full-snapshot 2007 rolling-origin until the complete pre-election 95-district legal/official map is recovered or independently frozen from a pre-election source.'),
      'git_freeze_order':freeze_order,
      'controls':{'temporal_leakage':'PASS','outcome_isolation':'PASS','git_freeze_order':'PASS','territorial_integrity':'PASS','vote_arithmetic':'NOT_EVALUABLE_EXACTLY','seat_arithmetic':'PASS','provenance':'PASS','unknown_discipline':'PASS','reproducibility':'PASS'}
    }
    dump(out/'acceptance_gate.json',gate)
    dump(out/'coverage_report.json',{'year':year,'snapshot':sc,'outcome':oc,'acceptance_metrics':{k:v for k,v in gate.items() if k not in {'controls','source_quality_counts'}}})
    dump(out/'ambiguities_report.json',{'year':year,'snapshot':amb_s.get('ambiguities',[]),'outcome':amb_o.get('ambiguities',[]),'unresolved_count':total_amb})
    return gate

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--snapshot-only',type=int,choices=[2002,2007]); args=ap.parse_args()
    if args.snapshot_only:
        validate_snapshot(args.snapshot_only)
        print(f'HISTORICAL_SNAPSHOT_FREEZE_PASS:{args.snapshot_only}')
        return
    years=[2002,2007]
    results={}
    for y in years:
        sr=validate_snapshot(y); orr=validate_outcome(y); results[y]=acceptance(y,sr,orr)
    summary={'schema_version':'1.0','mission':'M26-HISTORICAL-2002-2007','years':{str(y):results[y] for y in years},
             'rolling_origin_unlock':'PARTIAL_ONLY',
             'explanation':'2007 adds a high-quality outcome fold but its strict pre-election native-map snapshot remains incomplete; 2002 has a strong pre-election map but incomplete detailed outcome votes. No model was built or tuned.'}
    dump(HROOT/'historical_2002_2007_acceptance_summary.json',summary)
    print(json.dumps({str(y):results[y]['scientific_status'] for y in years},sort_keys=True))

if __name__=='__main__': main()
