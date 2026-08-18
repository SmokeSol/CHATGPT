#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent

def load_module(name,path):
 spec=importlib.util.spec_from_file_location(name,path);mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod

def main():
 v4=load_module('mpv4',HERE/'candidate_intelligence_v2_multipart_head_power_gate_v4.py');v4.main();power=json.loads(v4.OUT.read_text(encoding='utf-8'))
 pred2=load_module('predv2',HERE/'candidate_intelligence_v2_multipart_predictive_gate_v2.py');pred2.p.main();score=json.loads(pred2.p.OUT.read_text(encoding='utf-8'))
 term2=load_module('termv2',HERE/'candidate_intelligence_v2_terminal_certificate_v2.py');term2.main();terminal=json.loads(term2.OUT.read_text(encoding='utf-8'))
 ci=v4.CI;legacy_power=ci/'candidate_intelligence_v2_multipart_head_power_gate_v1.json';legacy16=ci/'multipart'/'2016_head_prior_mp_features_v1.jsonl';legacy21=ci/'multipart'/'2021_head_prior_mp_features_v1.jsonl';legacy_excluded=ci/'multipart'/'2021_unresolved_territory_heads_excluded_v1.json';shutil.copyfile(v4.D16,legacy16);shutil.copyfile(v4.D21,legacy21);dedup=json.loads(v4.DEDUP.read_text(encoding='utf-8'));legacy_excluded.write_text(json.dumps({'schema_version':'2.0','source_artifact':str(v4.DEDUP.relative_to(v4.mp.ROOT)),'unresolved_territory_rows_excluded':dedup.get('unresolved_territory_rows_excluded',[]),'same_candidate_duplicate_rows_dropped':dedup.get('same_candidate_duplicate_rows_dropped',[])},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8');bundle={**power,'schema_version':'terminal-bundle-1.0','result_id':'M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-TERMINAL-BUNDLE-V1','power_gate_v4':power,'predictive_gate_v2':score,'terminal_certificate_v2':terminal,'batch_terminal_status':terminal['terminal_status'],'batch_terminal_decision':terminal['terminal_decision']};legacy_power.write_text(json.dumps(bundle,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
 # TEMPORARY batch observability hooks for already-frozen F1 conventional audits.
 f1=load_module('f1baseline',HERE/'goal100_f1_baseline_rebuild_v1.py');f1.main();f1r=json.loads(f1.OUT_DEV.read_text(encoding='utf-8'));print('F1_OBSERVABLE_RESULT='+json.dumps({'status':f1r['status'],'eligible_candidate_count':f1r['eligible_candidate_count'],'selected_candidate':f1r['selected_candidate']},sort_keys=True))
 marg=load_module('f1marginal',HERE/'goal100_f1_party_marginal_transfer_v1.py');marg.main()
 nat=load_module('f1national',HERE/'goal100_f1_national_conditioning_v1.py');nat.main()
 surface=load_module('f1surface',HERE/'goal100_f1_national_scenario_surface_v1.py');surface.main()
if __name__=='__main__':main()
