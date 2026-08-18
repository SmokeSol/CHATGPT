#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, shutil
from pathlib import Path

HERE=Path(__file__).resolve().parent

def load_module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main():
    # Execute the already-frozen audited V4 power gate.
    v4=load_module('mpv4',HERE/'candidate_intelligence_v2_multipart_head_power_gate_v4.py')
    v4.main()
    power=json.loads(v4.OUT.read_text(encoding='utf-8'))

    # Execute deterministic predictive scoring only if the power gate authorizes it.
    pred2=load_module('predv2',HERE/'candidate_intelligence_v2_multipart_predictive_gate_v2.py')
    pred2.p.main()
    score=json.loads(pred2.p.OUT.read_text(encoding='utf-8'))

    # Produce the frozen terminal GO/KILL certificate.
    term2=load_module('termv2',HERE/'candidate_intelligence_v2_terminal_certificate_v2.py')
    term2.main()
    terminal=json.loads(term2.OUT.read_text(encoding='utf-8'))

    # The known legacy workflow stages these paths. Preserve a complete, auditable
    # terminal bundle there so one reliable runner can persist the final result.
    ci=v4.CI
    legacy_power=ci/'candidate_intelligence_v2_multipart_head_power_gate_v1.json'
    legacy16=ci/'multipart'/'2016_head_prior_mp_features_v1.jsonl'
    legacy21=ci/'multipart'/'2021_head_prior_mp_features_v1.jsonl'
    legacy_excluded=ci/'multipart'/'2021_unresolved_territory_heads_excluded_v1.json'
    shutil.copyfile(v4.D16,legacy16);shutil.copyfile(v4.D21,legacy21)
    dedup=json.loads(v4.DEDUP.read_text(encoding='utf-8'))
    legacy_excluded.write_text(json.dumps({'schema_version':'2.0','source_artifact':str(v4.DEDUP.relative_to(v4.mp.ROOT)),'unresolved_territory_rows_excluded':dedup.get('unresolved_territory_rows_excluded',[]),'same_candidate_duplicate_rows_dropped':dedup.get('same_candidate_duplicate_rows_dropped',[])},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    bundle={**power,'schema_version':'terminal-bundle-1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-TERMINAL-BUNDLE-V1','power_gate_v4':power,'predictive_gate_v2':score,'terminal_certificate_v2':terminal,'batch_terminal_status':terminal['terminal_status'],'batch_terminal_decision':terminal['terminal_decision'],'note':'Compatibility artifact written to the legacy staged path by the known runner; canonical logic is V4 power + V2 predictive + V2 terminal certificate.'}
    legacy_power.write_text(json.dumps(bundle,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'power_status':power['status'],'eligible_features':power.get('eligible_features',[]),'M1_positive_2021':power['2016_TO_2021']['features']['M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT']['positive'],'predictive_interpretation':score.get('terminal_interpretation'),'terminal_status':terminal['terminal_status'],'terminal_decision':terminal['terminal_decision']},ensure_ascii=False,sort_keys=True))

if __name__=='__main__':main()
