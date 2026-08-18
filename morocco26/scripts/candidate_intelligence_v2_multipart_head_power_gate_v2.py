#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('mpv1',HERE/'candidate_intelligence_v2_multipart_head_power_gate.py')
mp=importlib.util.module_from_spec(spec);spec.loader.exec_module(mp)

def load_candidates21_resolved_only():
    rows=json.loads(mp.HEAD21.read_text(encoding='utf-8'));out=[];seen=set();excluded=[]
    for r in rows:
        if r.get('party_bucket') not in {'PJD','RNI'}:continue
        if int(r.get('CANDIDATE_REGISTERED_RANK') or 0)!=1 or r.get('rank_evidence_status')!='EXPLICIT_CANDIDATS_TETES_DE_LISTE':continue
        if not r.get('territory_id'):
            excluded.append({'party':r.get('party_bucket'),'candidate_name':r.get('candidate_name_source'),'district_source':r.get('district_source'),'reason':'UNRESOLVED_TERRITORY_NOT_A_PARTY_X_TERRITORY_CELL'})
            continue
        key=(r['party_bucket'],r['territory_id'])
        if key in seen:raise RuntimeError(f'duplicate certified 2021 head after territory resolution {key}')
        seen.add(key);out.append({'transition':'2016_TO_2021','year':2021,'party':r['party_bucket'],'territory_id':r['territory_id'],'candidate_name_lat':r['candidate_name_source'],'candidate_name_ar':None,'source_class':'CERTIFIED_EXPLICIT_HEAD_ROSTER_RESOLVED_TERRITORY','prior_link_corroborated':bool(r.get('prior_elected_person_id')),'existing_same_party_same_district':bool(r.get('INCUMBENT_SAME_PARTY_SAME_DISTRICT')),'existing_switch_in':bool(r.get('PARTY_SWITCH_IN')),'incumbent_match_score':r.get('incumbent_match_score')})
    (mp.CI/'multipart'/'2021_unresolved_territory_heads_excluded_v1.json').write_text(json.dumps({'count':len(excluded),'rows':excluded},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return out

mp.load_candidates21=load_candidates21_resolved_only
if __name__=='__main__':mp.main()
