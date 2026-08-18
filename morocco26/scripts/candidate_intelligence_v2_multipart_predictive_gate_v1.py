#!/usr/bin/env python3
from __future__ import annotations
import importlib.util, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "morocco26"
G = M / "data" / "goal100"
CI = G / "e_collect" / "candidate_intelligence_v2"
H = G / "historical"
CONTRACT = G / "e_collect" / "candidate_intelligence_v2_multipart_head_contract_v1.json"
POWER = CI / "candidate_intelligence_v2_multipart_head_power_gate_v3.json"
D16 = CI / "multipart" / "2016_head_prior_mp_features_v3.jsonl"
D21 = CI / "multipart" / "2021_head_prior_mp_features_v3.jsonl"
OUT = CI / "candidate_intelligence_v2_multipart_predictive_gate_v1.json"
RIDGE = [0.01, 0.1, 1.0, 10.0, 100.0]
SEED = 260818
NBOOT = 10000
EPS = 1e-9

spec = importlib.util.spec_from_file_location("hb", M / "scripts" / "e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hb)
PARTIES = hb.PARTIES

def rj(path): return json.loads(Path(path).read_text(encoding="utf-8"))
def jsonl(path): return [json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()]
def logit(p):
    p = np.clip(np.asarray(p, dtype=float), EPS, 1 - EPS); return np.log(p / (1 - p))
def logistic(z): return 1 / (1 + np.exp(-np.asarray(z, dtype=float)))
def shares(row):
    raw = row.get("votes", {}); vals = [float(raw.get(p, 0) or 0) for p in hb.CORE]; vals.append(sum(float(v or 0) for k, v in raw.items() if k not in hb.CORE)); arr = np.array(vals, dtype=float); return arr / arr.sum()
def load_hist(year):
    d = rj(H / f"tafra_legislative_{year}_canonical.json"); rows = [r for r in d["rows"] if str(r.get("list_type", "")).lower() in {"local", "locale"}]
    if len(rows) != 92: raise RuntimeError(f"expected 92 local rows for {year}, got {len(rows)}")
    return rows
def state_value(state): return 1.0 if state == "VERIFIED_TRUE" else (0.0 if state == "VERIFIED_FALSE" else None)
def build_cells(detail_path, eligible, bycid, base, obs):
    cells = []
    for r in jsonl(detail_path):
        vals = [state_value(r["feature_states"][f]) for f in eligible]
        if any(v is None for v in vals): continue
        party = r["party"]
        if party not in {"PJD", "RNI"}: continue
        cid = r["territory_id"]
        if cid not in bycid or cid not in base or cid not in obs: continue
        idx = PARTIES.index(party)
        cells.append({"party": party, "territory_id": cid, "region": bycid[cid]["region"], "x": np.array(vals, dtype=float), "base_share": float(base[cid][idx]), "obs_share": float(obs[cid][idx]), "party_index": idx})
    return cells
def apply_shift(base_vec, focal_index, delta):
    out = np.array(base_vec, dtype=float); p = float(out[focal_index]); q = float(logistic(logit(p) + delta)); denom = max(EPS, 1 - p); scale = (1 - q) / denom
    for i in range(len(out)): out[i] = q if i == focal_index else out[i] * scale
    out /= out.sum(); return out
def ridge_beta(X, y, alpha): return np.linalg.solve(X.T @ X + float(alpha) * np.eye(X.shape[1]), X.T @ y)
def xmeans(cells):
    return {p: np.mean(np.stack([c["x"] for c in cells if c["party"] == p]), axis=0) for p in ("PJD", "RNI")}
def enrich_y(cells):
    for c in cells: c["y"] = float(logit(c["obs_share"]) - logit(c["base_share"]))
    return cells
def design(cells, xm, ym):
    return np.stack([c["x"] - xm[c["party"]] for c in cells]), np.array([c["y"] - float(ym[c["party"]]) for c in cells], dtype=float)
def rmse(values):
    arr = np.asarray(values, dtype=float); return float(np.sqrt(np.mean(arr ** 2)))
def evaluate_cells(cells, base_vectors, beta, xm):
    rows = []
    for c in cells:
        delta = float((c["x"] - xm[c["party"]]) @ beta); pred = apply_shift(base_vectors[c["territory_id"]], c["party_index"], delta); p = float(pred[c["party_index"]]); b = c["base_share"]; o = c["obs_share"]
        rows.append({"party": c["party"], "territory_id": c["territory_id"], "delta_logit": delta, "pred_share": p, "base_share": b, "obs_share": o, "model_error": p - o, "base_error": b - o})
    return rows
def metric_block(rows):
    pm = rmse([r["model_error"] for r in rows]); pb = rmse([r["base_error"] for r in rows]); by = {}
    for party in ("PJD", "RNI"):
        rr = [r for r in rows if r["party"] == party]; m = rmse([r["model_error"] for r in rr]); b = rmse([r["base_error"] for r in rr]); by[party] = {"n": len(rr), "model_RMSE": m, "C0_RMSE": b, "relative_improvement": (b - m) / b}
    return {"n": len(rows), "pooled_model_RMSE": pm, "pooled_C0_RMSE": pb, "pooled_relative_improvement": (pb - pm) / pb, "pooled_model_MAE": float(np.mean([abs(r["model_error"]) for r in rows])), "pooled_C0_MAE": float(np.mean([abs(r["base_error"]) for r in rows])), "by_party": by}
def bootstrap(rows):
    rng = np.random.default_rng(SEED); n = len(rows); me = np.array([r["model_error"] ** 2 for r in rows], dtype=float); be = np.array([r["base_error"] ** 2 for r in rows], dtype=float); idx = rng.integers(0, n, size=(NBOOT, n)); mr = np.sqrt(me[idx].mean(axis=1)); br = np.sqrt(be[idx].mean(axis=1)); d = mr - br
    return {"replicates": NBOOT, "seed": SEED, "bootstrap_probability_model_better": float(np.mean(d < 0)), "percentile_95_interval_delta_model_minus_C0": [float(np.quantile(d, 0.025)), float(np.quantile(d, 0.975))]}
def main():
    contract = rj(CONTRACT); power = rj(POWER)
    if power["status"] != "PASS_MULTIPART_HEAD_POWER":
        out = {"schema_version": "1.0", "result_id": "M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-PREDICTIVE-GATE-V1", "contract_id": contract["contract_id"], "scientific_status": contract["scientific_status"], "power_gate_result_id": power.get("result_id"), "eligible_features": power.get("eligible_features", []), "terminal_interpretation": "NOT_RUN_POWER_GATE_FAILED", "terminal_decision": "NO_GO_E_REASON_V2_MULTIPART_POWER_INSUFFICIENT", "forecast_modified": False, "llm_invoked": False, "2021_is_blind_holdout": False}
        OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"terminal_interpretation": out["terminal_interpretation"], "terminal_decision": out["terminal_decision"]}, sort_keys=True)); return
    eligible = list(power["eligible_features"])
    if not eligible: raise RuntimeError("power gate passed without eligible features")
    consts = hb.load_constituencies(); bycid = {c["constituency_id"]: c for c in consts}; rows11 = hb.load_local(2011); rows16 = hb.load_local(2016); rows21 = load_hist(2021); m11 = hb.match_rows(consts, rows11); m16 = hb.match_rows(consts, rows16); m21 = hb.match_rows(consts, rows21)
    base16 = {c["constituency_id"]: shares(m11[c["constituency_id"]]) for c in consts}; bstar = hb.reproduce_bstar_v0(consts, rows11, rows16); base21 = {c["constituency_id"]: np.array([bstar[c["constituency_id"]]["mean"][p] for p in PARTIES], dtype=float) for c in consts}; obs16 = {c["constituency_id"]: shares(m16[c["constituency_id"]]) for c in consts}; obs21 = {c["constituency_id"]: shares(m21[c["constituency_id"]]) for c in consts}
    fit = enrich_y(build_cells(D16, eligible, bycid, base16, obs16)); val = enrich_y(build_cells(D21, eligible, bycid, base21, obs21)); required = contract["power_gate"]
    for name, cells in (("fit", fit), ("validation", val)):
        if len(cells) < required["minimum_known_head_cells_each_transition"]: raise RuntimeError(f"{name} cells below frozen coverage floor: {len(cells)}")
        for party in ("PJD", "RNI"):
            n = sum(c["party"] == party for c in cells)
            if n < required["minimum_known_head_cells_per_party_each_transition"]: raise RuntimeError(f"{name} {party} below frozen per-party floor: {n}")
    regions = sorted(set(c["region"] for c in fit)); cv = []
    for alpha in RIDGE:
        all_errors = []; folds = []
        for region in regions:
            train = [c for c in fit if c["region"] != region]; test = [c for c in fit if c["region"] == region]
            if not test: continue
            xm = xmeans(train); ym = {p: float(np.mean([c["y"] for c in train if c["party"] == p])) for p in ("PJD", "RNI")}; X, y = design(train, xm, ym); beta = ridge_beta(X, y, alpha); preds = evaluate_cells(test, base16, beta, xm); errs = [r["model_error"] for r in preds]; all_errors.extend(errs); folds.append({"region": region, "n": len(test), "pooled_RMSE": rmse(errs)})
        cv.append({"alpha": alpha, "pooled_heldout_RMSE": rmse(all_errors), "folds": folds})
    selected = sorted(cv, key=lambda z: (z["pooled_heldout_RMSE"], -z["alpha"]))[0]["alpha"]; xm = xmeans(fit); ym = {p: float(np.mean([c["y"] for c in fit if c["party"] == p])) for p in ("PJD", "RNI")}; X, y = design(fit, xm, ym); beta = ridge_beta(X, y, selected); fit_rows = evaluate_cells(fit, base16, beta, xm); val_rows = evaluate_cells(val, base21, beta, xm); fit_metrics = metric_block(fit_rows); val_metrics = metric_block(val_rows); boot = bootstrap(val_rows)
    pooled = val_metrics["pooled_relative_improvement"]; prob = boot["bootstrap_probability_model_better"]; favorable_both = all(val_metrics["by_party"][p]["relative_improvement"] > 0 for p in ("PJD", "RNI"))
    if pooled >= 0.005 and prob >= 0.90 and favorable_both: status, decision = "MATERIAL_RETROSPECTIVE_SIGNAL", "GO_E_REASON_V2_SPEC_FREEZE"
    elif pooled > 0: status, decision = "WEAK_RETROSPECTIVE_SIGNAL", "NO_GO_E_REASON_V2_CANDIDATE_LAYER_NOT_MATERIAL"
    else: status, decision = "NO_RETROSPECTIVE_PREDICTIVE_SIGNAL", "KILL_E_REASON_V2_CANDIDATE_LAYER"
    out = {"schema_version": "1.0", "result_id": "M26-CANDIDATE-INTELLIGENCE-V2-MULTIPART-PREDICTIVE-GATE-V1", "contract_id": contract["contract_id"], "scientific_status": contract["scientific_status"], "power_gate_result_id": power["result_id"], "eligible_features": eligible, "fit_cells": len(fit), "validation_cells": len(val), "fit_cells_by_party": {p: sum(c["party"] == p for c in fit) for p in ("PJD", "RNI")}, "validation_cells_by_party": {p: sum(c["party"] == p for c in val) for p in ("PJD", "RNI")}, "ridge_cv": cv, "selected_alpha": selected, "feature_means_2016_by_party": {p: {f: float(v) for f, v in zip(eligible, xm[p])} for p in ("PJD", "RNI")}, "target_residual_means_2016_by_party_removed_for_fit_only": ym, "beta": {f: float(v) for f, v in zip(eligible, beta)}, "fit_2011_TO_2016": fit_metrics, "validation_2016_TO_2021": val_metrics, "validation_bootstrap": boot, "terminal_interpretation": status, "terminal_decision": decision, "material_signal_gate": {"pooled_relative_improvement_ge_0_5pct": pooled >= 0.005, "bootstrap_probability_ge_0_90": prob >= 0.90, "both_parties_point_improve": favorable_both, "pass": status == "MATERIAL_RETROSPECTIVE_SIGNAL"}, "forecast_modified": False, "llm_invoked": False, "2021_is_blind_holdout": False, "implementation_note": "Party-specific national residual means are removed only during 2016 fitting; no party intercept or national swing is carried into 2021 validation. Feature means and coefficients are frozen from 2016 only."}
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"); print(json.dumps({"terminal_interpretation": status, "terminal_decision": decision, "eligible_features": eligible, "selected_alpha": selected, "beta": out["beta"], "fit_cells": len(fit), "validation_cells": len(val), "pooled_relative_improvement": pooled, "bootstrap_probability_model_better": prob, "PJD_relative_improvement": val_metrics["by_party"]["PJD"]["relative_improvement"], "RNI_relative_improvement": val_metrics["by_party"]["RNI"]["relative_improvement"]}, ensure_ascii=False, sort_keys=True))
if __name__ == "__main__": main()
