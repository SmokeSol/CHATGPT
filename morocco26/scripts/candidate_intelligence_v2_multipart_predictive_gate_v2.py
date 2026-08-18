#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('predv1',HERE/'candidate_intelligence_v2_multipart_predictive_gate_v1.py')
p=importlib.util.module_from_spec(spec);spec.loader.exec_module(p)
p.POWER=p.CI/'candidate_intelligence_v2_multipart_head_power_gate_v4.json'
p.D16=p.CI/'multipart'/'2016_head_prior_mp_features_v4.jsonl'
p.D21=p.CI/'multipart'/'2021_head_prior_mp_features_v4.jsonl'
p.OUT=p.CI/'candidate_intelligence_v2_multipart_predictive_gate_v2.json'
if __name__=='__main__':p.main()
