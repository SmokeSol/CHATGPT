#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[2]
CI = ROOT / "morocco26" / "data" / "goal100" / "e_collect" / "candidate_intelligence_v2"
POWER = CI / "candidate_intelligence_v2_multipart_head_power_gate_v3.json"
SCORE = CI / "candidate_intelligence_v2_multipart_predictive_gate_v1.json"
PJD_ONLY = CI / "candidate_intelligence_v2_predictive_gate_v1.json"
FEATURE_C = CI / "candidate_intelligence_v2_feature_c_power_gate_v1.json"
OUT = CI / "candidate_intelligence_v2_terminal_certificate_v1.json"
def rj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def main():
    power = rj(POWER); pjd = rj(PJD_ONLY) if PJD_ONLY.exists() else None; fc = rj(FEATURE_C) if FEATURE_C.exists() else None
    if power["status"] != "PASS_MULTIPART_HEAD_POWER": status, decision, score = "TERMINAL_NO_GO", "NO_GO_E_REASON_V2_MULTIPART_POWER_INSUFFICIENT", None
    else:
        score = rj(SCORE); decision = score["terminal_decision"]; status = "TERMINAL_GO" if decision == "GO_E_REASON_V2_SPEC_FREEZE" else "TERMINAL_NO_GO"
    out = {"schema_version": "1.0", "certificate_id": "M26-CANDIDATE-INTELLIGENCE-V2-TERMINAL-CERTIFICATE-V1", "purpose": "Close the post-E_reason-V1 candidate-intelligence investigation with a deterministic GO/KILL decision before any LLM reasoning layer.", "power_gate": {"status": power["status"], "eligible_features": power.get("eligible_features", []), "known_2016": power["2011_TO_2016"]["fully_known_all_features"], "known_2021": power["2016_TO_2021"]["fully_known_all_features"]}, "multipart_predictive_gate": None if score is None else {"terminal_interpretation": score["terminal_interpretation"], "terminal_decision": score["terminal_decision"], "fit_cells": score.get("fit_cells"), "validation_cells": score.get("validation_cells"), "selected_alpha": score.get("selected_alpha"), "beta": score.get("beta"), "pooled_relative_improvement": score.get("validation_2016_TO_2021", {}).get("pooled_relative_improvement"), "bootstrap_probability_model_better": score.get("validation_bootstrap", {}).get("bootstrap_probability_model_better"), "PJD_relative_improvement": score.get("validation_2016_TO_2021", {}).get("by_party", {}).get("PJD", {}).get("relative_improvement"), "RNI_relative_improvement": score.get("validation_2016_TO_2021", {}).get("by_party", {}).get("RNI", {}).get("relative_improvement")}, "prior_diagnostics": {"PJD_only_terminal_interpretation": None if pjd is None else pjd.get("terminal_interpretation"), "PJD_only_validation_PJD_relative_improvement": None if pjd is None else pjd.get("validation_comparisons", {}).get("PJD_RMSE", {}).get("relative_improvement"), "feature_C_status": None if fc is None else fc.get("status")}, "terminal_status": status, "terminal_decision": decision, "llm_invoked": False, "F0_modified": False, "scientific_interpretation": "If GO: candidate-level parliamentary continuity has material retrospective territorial signal on a standardized two-party head-of-list panel, so a separately frozen E_reason V2 reasoning specification may be justified. If NO_GO: variation/coverage alone is not enough; do not invoke Opus on this candidate layer, and do not modify F0.", "next_action": "Freeze a prospective E_reason V2 specification before any LLM call; 2021 remains retrospective and cannot become blind again." if decision == "GO_E_REASON_V2_SPEC_FREEZE" else "Stop E_reason V2 on this candidate-intelligence layer. Preserve the data as descriptive/exploratory evidence only; keep F0 unchanged."}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"terminal_status": status, "terminal_decision": decision, "power_status": power["status"], "predictive_interpretation": None if score is None else score["terminal_interpretation"], "next_action": out["next_action"]}, ensure_ascii=False, sort_keys=True))
if __name__ == "__main__": main()
