#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('v3',HERE/'candidate_intelligence_v2_multipart_head_power_gate_v3.py')
v3=importlib.util.module_from_spec(spec);spec.loader.exec_module(v3)
mp=v3.mp
CI=mp.CI
RES=CI/'multipart'/'2021_m1_identity_resolution_v1.json'
OUT=CI/'candidate_intelligence_v2_multipart_head_power_gate_v4.json'
D16=CI/'multipart'/'2016_head_prior_mp_features_v4.jsonl'
D21=CI/'multipart'/'2021_head_prior_mp_features_v4.jsonl'
DEDUP=CI/'multipart'/'2021_head_roster_dedup_v4.json'

mp.OUT=OUT; mp.DETAIL16=D16; mp.DETAIL21=D21; v3.DEDUP=DEDUP
orig_classify=mp.classify

def classify_with_resolution(cands,universe,script):
    rows=orig_classify(cands,universe,script)
    if script!='lat': return rows
    decisions=json.loads(RES.read_text(encoding='utf-8'))['decisions']
    by={(r['party'],r['territory_id']):r for r in rows}
    applied=[]
    for d in decisions:
        key=(d['party'],d['territory_id'])
        if key not in by: raise RuntimeError(f'resolution row missing: {key}')
        r=by[key]; st=r['feature_states']
        if st['M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT']!='UNKNOWN': raise RuntimeError(f'M1 resolution may only replace UNKNOWN: {key} -> {st}')
        if st['M2_HEAD_PRIOR_MP_SAME_PARTY_OTHER_SEAT']!='UNKNOWN' or st['M3_HEAD_PRIOR_MP_SWITCH_IN']!='UNKNOWN': raise RuntimeError(f'expected fully unresolved parliamentary classification before overlay: {key} -> {st}')
        r['feature_states']={'M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT':'VERIFIED_TRUE','M2_HEAD_PRIOR_MP_SAME_PARTY_OTHER_SEAT':'VERIFIED_FALSE','M3_HEAD_PRIOR_MP_SWITCH_IN':'VERIFIED_FALSE'}
        r['identity_method']='AUDITED_PRE_ELECTION_SAME_PARTY_SAME_CONSTITUENCY_OVERLAY'
        r['identity_resolution_overlay']=d
        applied.append(key)
    if len(applied)!=len(decisions): raise RuntimeError('not all M1 resolutions applied')
    return rows

mp.classify=classify_with_resolution

def main():
    v3.main()
    result=json.loads(OUT.read_text(encoding='utf-8'))
    result['schema_version']='1.4'; result['result_id']='M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-HEAD-POWER-GATE-V4'; result['identity_resolution_artifact']=str(RES.relative_to(mp.ROOT)); result['identity_resolutions_applied']=len(json.loads(RES.read_text(encoding='utf-8'))['decisions'])
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':result['status'],'eligible_features':result['eligible_features'],'known_2016':result['2011_TO_2016']['fully_known_all_features'],'known_2021':result['2016_TO_2021']['fully_known_all_features'],'M1_positive_2016':result['2011_TO_2016']['features']['M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT']['positive'],'M1_positive_2021':result['2016_TO_2021']['features']['M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT']['positive'],'resolutions_applied':result['identity_resolutions_applied']},sort_keys=True))
if __name__=='__main__':main()
