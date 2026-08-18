#!/usr/bin/env python3
from __future__ import annotations

import json, math
from pathlib import Path
import importlib.util
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
CONTRACT = G / "f1_baseline_rebuild_contract_v1.json"
OLD_CAL = G / "uncertainty_calibration_v2.json"
BALLOT = G / "b2_2026_ballot_certificate.json"
M24_MANIFEST = G / "e_collect" / "runs" / "medias24_db_32051248846_1" / "run_manifest.json"
OUT_PREFLIGHT = G / "f1_baseline_preflight_result_v1.json"
OUT_DEV = G / "f1_hierarchical_uncertainty_dev_v1.json"

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES = hb.PARTIES
K = len(PARTIES)
DRAWS = 2048
SEED = 26081826
FLOOR = 0.0005
COV80_FLOOR = 0.7182
COV95_FLOOR = 0.9054
NATIONAL_GRID = [0.5, 1.0, 1.5, 2.0]
TERR_GRID = [0.75, 1.0, 1.25, 1.5]


def rj(path: Path): return json.loads(path.read_text(encoding="utf-8"))

def load_local(year: int):
    d = rj(HIST / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in d["rows"] if str(r.get("list_type", "")).lower() in {"local", "locale"}]
    if len(rows) != 92: raise RuntimeError(f"{year}: expected 92 local rows, got {len(rows)}")
    return rows

def share(row):
    x = hb.bucket_counts(row)
    return x / x.sum()

def cclr(row): return hb.centre_clr(hb.clr(row))

def robust_project(s: np.ndarray, cap: float) -> np.ndarray:
    a = np.asarray(s, float)
    a = FLOOR + (1.0 - K * FLOOR) * a
    a = a / a.sum(axis=-1, keepdims=True)
    flat = a.reshape(-1, K)
    bad = np.max(flat, axis=1) > cap + 1e-12
    if np.any(bad):
        b = flat[bad]
        lo = np.zeros(len(b)); hi = np.ones(len(b))
        for _ in range(36):
            mid = (lo + hi) / 2.0
            p = np.power(b, mid[:, None]); p /= p.sum(axis=1, keepdims=True)
            mx = p.max(axis=1)
            # max grows with tau; if above cap, reduce tau.
            hi = np.where(mx > cap, mid, hi)
            lo = np.where(mx <= cap, mid, lo)
        tau = lo
        p = np.power(b, tau[:, None]); p /= p.sum(axis=1, keepdims=True)
        flat[bad] = p
    return flat.reshape(a.shape)

def transition(consts, prev_rows, next_rows):
    mp = hb.match_rows(consts, prev_rows); mn = hb.match_rows(consts, next_rows)
    cids = [c["constituency_id"] for c in consts]
    zp = np.stack([cclr(mp[c]) for c in cids])
    zn = np.stack([cclr(mn[c]) for c in cids])
    residual = hb.centre_clr(zn - zp)
    national = hb.centre_clr(residual.mean(axis=0))
    terr = hb.centre_clr(residual - national[None, :])
    actual = np.stack([share(mn[c]) for c in cids])
    prior = np.stack([share(mp[c]) for c in cids])
    return {"cids": cids, "prior_z": zp, "actual": actual, "prior_share": prior,
            "national": national, "territorial": terr}

def energy_sqrt(samples, y):
    xs = np.sqrt(samples); yy = np.sqrt(y)
    a = np.linalg.norm(xs - yy[None, :], axis=1).mean()
    b = np.linalg.norm(xs - np.roll(xs, 1, axis=0), axis=1).mean()
    return float(a - 0.5 * b)

def evaluate(train, held, ns, ts, cap, seed):
    rng = np.random.default_rng(seed)
    z_nat = rng.standard_normal(DRAWS)
    idx = rng.integers(0, len(train["territorial"]), size=(len(held["cids"]), DRAWS))
    covered80 = np.zeros((len(held["cids"]), K), bool)
    covered95 = np.zeros_like(covered80)
    widths80 = []; widths95 = []; energies = []; means = []
    for i in range(len(held["cids"])):
        shock = ns * z_nat[:, None] * train["national"][None, :] + ts * train["territorial"][idx[i]]
        z = hb.centre_clr(held["prior_z"][i][None, :] + shock)
        s = robust_project(hb.inv_clr(z), cap)
        y = held["actual"][i]
        q10, q90 = np.quantile(s, [.10, .90], axis=0)
        q025, q975 = np.quantile(s, [.025, .975], axis=0)
        covered80[i] = (y >= q10) & (y <= q90)
        covered95[i] = (y >= q025) & (y <= q975)
        widths80.append(q90-q10); widths95.append(q975-q025)
        energies.append(energy_sqrt(s, y)); means.append(s.mean(axis=0))
    cov80 = covered80.mean(axis=0); cov95 = covered95.mean(axis=0)
    means = np.stack(means); actual = held["actual"]
    return {
        "coverage80_by_party": {p: float(cov80[j]) for j,p in enumerate(PARTIES)},
        "coverage95_by_party": {p: float(cov95[j]) for j,p in enumerate(PARTIES)},
        "min_party_coverage80": float(cov80.min()),
        "min_party_coverage95": float(cov95.min()),
        "party_coverage_gate": bool(np.all(cov80 >= COV80_FLOOR) and np.all(cov95 >= COV95_FLOOR)),
        "calibration_abs_error": float(np.mean(np.abs(cov80-.80)) + np.mean(np.abs(cov95-.95))),
        "mean_energy_score": float(np.mean(energies)),
        "mean_interval_width80": float(np.mean(np.stack(widths80))),
        "mean_interval_width95": float(np.mean(np.stack(widths95))),
        "mean_share_rmse": float(np.sqrt(np.mean((means-actual)**2)))
    }

def main():
    contract = rj(CONTRACT); old = rj(OLD_CAL); ballot = rj(BALLOT); m24 = rj(M24_MANIFEST)
    if contract.get("status") != "FROZEN_BEFORE_F1_HIERARCHICAL_UNCERTAINTY_EXECUTION": raise RuntimeError("F1 contract not frozen")
    consts = hb.load_constituencies(); r11=load_local(2011); r16=load_local(2016); r21=load_local(2021)
    t16=transition(consts,r11,r16); t21=transition(consts,r16,r21)
    allshares=[]
    for rows in (r11,r16,r21):
        m=hb.match_rows(consts,rows)
        allshares.extend(share(m[c["constituency_id"]]) for c in consts)
    histmax=float(np.max(np.stack(allshares))); cap=float(min(.85,histmax+.05))
    preflight={
      "schema_version":"1.0","audit_id":"M26-GOAL100-F1-PREFLIGHT-V1","contract_id":contract["contract_id"],
      "F0_role":"IMMUTABLE_PRELIMINARY_PARENT_NOT_FINAL_BASELINE","mean_model_hindcast":"V0_PERSIST retained; transported global/regional CLR shift models were worse in Bstar hindcast.",
      "F0_uncertainty_caveat":{"selected_scale":2.0,"aggregate_coverage80":.7717391304347826,"aggregate_coverage95":.9118357487922706,"mean_width95":.5445930074002108,"party80_min":.29347826086956524,"party95_min":.6739130434782609,"verdict":"AGGREGATE_PASS_BUT_PARTY_CALIBRATION_FAIL"},
      "ballot_certificate_status":ballot.get("global_verdict",ballot.get("status","UNKNOWN")),
      "medias24_discovery_surface":{"candidate_records":m24.get("candidate_records"),"party_count":m24.get("parties"),"territories":m24.get("territories")},
      "sequence_correction":"E_reason promotion suspended until conventional F1 mean/uncertainty and 2026 ballot support are correctly specified.",
      "preflight_verdict":"F1_BASELINE_REBUILD_REQUIRED"
    }
    OUT_PREFLIGHT.write_text(json.dumps(preflight,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    candidates=[]
    ci=0
    for ns in NATIONAL_GRID:
      for ts in TERR_GRID:
        f16=evaluate(t21,t16,ns,ts,cap,SEED+1000+ci)
        f21=evaluate(t16,t21,ns,ts,cap,SEED+2000+ci)
        eligible=f16["party_coverage_gate"] and f21["party_coverage_gate"]
        candidates.append({"national_scale":ns,"territorial_scale":ts,"heldout_2011_TO_2016":f16,"heldout_2016_TO_2021":f21,
          "eligible":eligible,"selection_calibration_error":float((f16["calibration_abs_error"]+f21["calibration_abs_error"])/2),
          "selection_energy":float((f16["mean_energy_score"]+f21["mean_energy_score"])/2),
          "selection_width95":float((f16["mean_interval_width95"]+f21["mean_interval_width95"])/2)})
        ci+=1
    elig=[x for x in candidates if x["eligible"]]
    if elig:
      selected=sorted(elig,key=lambda x:(x["selection_calibration_error"],x["selection_energy"],x["selection_width95"],x["national_scale"]+x["territorial_scale"]))[0]
      sharp=selected["selection_width95"] < .5445930074002108
      status="F1_HIERARCHICAL_UNCERTAINTY_READY_FOR_REFIT" if sharp else "F1_HIERARCHICAL_UNCERTAINTY_FAIL_SHARPNESS"
    else:
      selected=None; sharp=False; status="F1_HIERARCHICAL_UNCERTAINTY_NOT_READY_PARTY_CALIBRATION"
    result={
      "schema_version":"1.0","result_id":"M26-GOAL100-F1-HIERARCHICAL-UNCERTAINTY-DEV-V1","contract_id":contract["contract_id"],
      "scientific_status":"POST_2021_DEVELOPMENT_2026_UNTOUCHED","historical_max_bucket_share":histmax,"robust_simplex_cap":cap,
      "coverage_floors":{"80":COV80_FLOOR,"95":COV95_FLOOR},"candidates":candidates,"eligible_candidate_count":len(elig),"selected_candidate":selected,
      "sharpness_improves_over_F0_v2":sharp,"status":status,"F0_modified":False,"E_reason_reopened":False,
      "next_action":("Refit the selected hierarchical uncertainty family on both historical transitions, then wait for/certify the 2026 legal ballot before a frozen seat forecast." if status=="F1_HIERARCHICAL_UNCERTAINTY_READY_FOR_REFIT" else "Do not widen intervals or reopen E_reason. Enrich the conventional uncertainty family (party-specific/hierarchical marginal scaling) under a new frozen contract.")
    }
    OUT_DEV.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    compact={"preflight":preflight["preflight_verdict"],"status":status,"eligible":len(elig),"selected":None if selected is None else {"national_scale":selected["national_scale"],"territorial_scale":selected["territorial_scale"],"calibration_error":selected["selection_calibration_error"],"energy":selected["selection_energy"],"width95":selected["selection_width95"],"fold16_min80":selected["heldout_2011_TO_2016"]["min_party_coverage80"],"fold16_min95":selected["heldout_2011_TO_2016"]["min_party_coverage95"],"fold21_min80":selected["heldout_2016_TO_2021"]["min_party_coverage80"],"fold21_min95":selected["heldout_2016_TO_2021"]["min_party_coverage95"]}}
    print(json.dumps(compact,sort_keys=True))

if __name__=="__main__": main()
