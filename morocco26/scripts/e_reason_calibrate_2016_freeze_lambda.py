#!/usr/bin/env python3
"""Post-judgment DEVELOPMENT unseal and lambda calibration for E_reason V1.

Order invariant:
- C1 and C2 judgments were frozen before this script existed/runs.
- Anonymous identity reconstruction uses ONLY the blinded 2011 baseline signatures.
- 2016 outcomes are opened only after identity reconstruction is complete.
- C2 development scores are certified cellwise identical to C1 by the pre-unseal receipt,
  therefore the frozen lambda selection is mathematically identical for C1 and C2.
- This script never reads any 2021 outcome file.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
H = ROOT / "data" / "goal100" / "historical"
BUNDLE = E / "blind" / "development" / "blind_bundle.json"
CONDS = E / "e_reason_conditions_v1.json"
C1 = E / "judgments" / "development" / "c1_rule_only" / "c1_judgments.jsonl"
C1_MANIFEST = E / "judgments" / "development" / "c1_rule_only" / "c1_judgment_manifest.json"
EQ = E / "judgments" / "development" / "c1_c2_preunseal_equivalence_receipt_v1.json"
C2_RECEIPT = E / "judgments" / "development" / "c2_opus5_freeze_receipt_v1.json"
OUTDIR = E / "calibration" / "development_2016"

CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
PARTIES = (*CORE, "OTHER")
MATCH_TOL = 1e-9


def read_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def load_rows(year: int):
    x = read_json(H / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in x["rows"] if str(r.get("list_type", "")).lower() in {"locale", "local"}]
    if len(rows) != 92:
        raise SystemExit(f"expected 92 local rows for {year}, got {len(rows)}")
    return {str(r["id_constituency"]): r for r in rows}


def bucket_share(row):
    raw = row.get("votes", {})
    total = sum(float(v or 0) for v in raw.values())
    if total <= 0:
        raise SystemExit("invalid zero vote total")
    out = {p: float(raw.get(p, 0) or 0) / total for p in CORE}
    out["OTHER"] = sum(float(v or 0) for k, v in raw.items() if k not in CORE) / total
    return out


def load_judgments(path: Path):
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def reconstruct_identity(bundle, y11):
    anon_party_ids = sorted({p["anonymous_party_id"] for pkt in bundle["packets"] for p in pkt["parties"]})
    if len(anon_party_ids) != 9:
        raise SystemExit("expected nine anonymous parties")

    real11 = {cid: bucket_share(r) for cid, r in y11.items()}
    anon_dist = {
        aid: sorted(next(p["baseline_vote_share"] for p in pkt["parties"] if p["anonymous_party_id"] == aid)
                    for pkt in bundle["packets"])
        for aid in anon_party_ids
    }
    real_dist = {p: sorted(real11[cid][p] for cid in real11) for p in PARTIES}

    party_map = {}
    party_match_error = {}
    used = set()
    for aid in anon_party_ids:
        cand = []
        for p in PARTIES:
            err = max(abs(a-b) for a,b in zip(anon_dist[aid], real_dist[p]))
            cand.append((err, p))
        cand.sort()
        err, p = cand[0]
        if err > MATCH_TOL or p in used:
            raise SystemExit(f"party mapping not unique for {aid}: {cand[:2]}")
        party_map[aid] = p
        party_match_error[aid] = {"best_max_abs_error": err, "second_best_max_abs_error": cand[1][0]}
        used.add(p)
    if used != set(PARTIES):
        raise SystemExit("party mapping is not bijective")

    real_vec = {cid: np.array([real11[cid][p] for p in PARTIES], dtype=float) for cid in real11}
    territory_map = {}
    territory_audit = {}
    used_cids = set()
    for pkt in bundle["packets"]:
        vals = {party_map[p["anonymous_party_id"]]: float(p["baseline_vote_share"]) for p in pkt["parties"]}
        v = np.array([vals[p] for p in PARTIES], dtype=float)
        cand = sorted((float(np.max(np.abs(v-rv))), cid) for cid,rv in real_vec.items())
        err, cid = cand[0]
        if err > MATCH_TOL or cid in used_cids:
            raise SystemExit(f"territory mapping not unique for {pkt['anonymous_territory_id']}: {cand[:2]}")
        territory_map[pkt["anonymous_territory_id"]] = cid
        territory_audit[pkt["anonymous_territory_id"]] = {
            "best_id_constituency": cid,
            "best_max_abs_error": err,
            "second_best_max_abs_error": cand[1][0],
            "margin": cand[1][0]-err,
        }
        used_cids.add(cid)
    if len(used_cids) != 92:
        raise SystemExit("territory mapping not 92/92 bijective")
    return party_map, territory_map, party_match_error, territory_audit


def predict(bundle, judgments_by_tid, party_map, territory_map, lam):
    out = {}
    for pkt in bundle["packets"]:
        tid = pkt["anonymous_territory_id"]
        cid = territory_map[tid]
        base = np.zeros(9, dtype=float)
        z = np.zeros(9, dtype=float)
        for x in pkt["parties"]:
            base[PARTIES.index(party_map[x["anonymous_party_id"]])] = float(x["baseline_vote_share"])
        for j in judgments_by_tid[tid]["judgments"]:
            z[PARTIES.index(party_map[j["anonymous_party_id"]])] = float(j["ordinal_score"])
        centered = z - z.mean()
        raw = base * np.exp(float(lam) * centered)
        out[cid] = raw / raw.sum()
    return out


def metrics(preds, obs):
    cell_errors = []
    l1 = []
    top = []
    for cid in sorted(obs):
        d = preds[cid] - obs[cid]
        cell_errors.extend(d.tolist())
        l1.append(float(np.sum(np.abs(d))))
        top.append(int(np.argmax(preds[cid]) == np.argmax(obs[cid])))
    return {
        "macro_party_share_RMSE": float(np.sqrt(np.mean(np.square(cell_errors)))),
        "mean_constituency_L1": float(np.mean(l1)),
        "top_party_accuracy": float(np.mean(top)),
    }


def main():
    bundle = read_json(BUNDLE)
    conds = read_json(CONDS)
    eq = read_json(EQ)
    c2_receipt = read_json(C2_RECEIPT)
    c1_manifest = read_json(C1_MANIFEST)

    assert eq["stage"] == "BEFORE_2016_OUTCOME_UNSEAL"
    assert eq["comparison"]["cellwise_ordinal_score_equivalence"] is True
    assert eq["comparison"]["ordinal_score_cells_identical"] == 828
    assert c2_receipt["terminal_status"] == "PASS_C2_JUDGMENTS_FROZEN_READY_FOR_2016_CALIBRATION"
    assert c1_manifest["status"] == "PASS_C1_JUDGMENTS_FROZEN_READY_FOR_2016_CALIBRATION"

    # Identity unseal uses 2011 only. 2016 is deliberately not loaded before this finishes.
    y11 = load_rows(2011)
    party_map, territory_map, party_audit, territory_audit = reconstruct_identity(bundle, y11)

    identity_certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-E-REASON-DEV-IDENTITY-RECONSTRUCTION-POSTFREEZE-V1",
        "method": "UNIQUE_MATCH_FROM_FROZEN_2011_BASELINE_SIGNATURES_ONLY",
        "target_outcome_used_for_identity_resolution": False,
        "party_mapping_bijective_9_of_9": True,
        "territory_mapping_bijective_92_of_92": True,
        "party_mapping": party_map,
        "territory_mapping_anonymous_to_historical_id": territory_map,
        "max_party_best_error": max(v["best_max_abs_error"] for v in party_audit.values()),
        "max_territory_best_error": max(v["best_max_abs_error"] for v in territory_audit.values()),
        "min_territory_second_best_margin": min(v["margin"] for v in territory_audit.values()),
        "match_tolerance": MATCH_TOL,
        "status": "PASS_UNIQUE_POSTFREEZE_IDENTITY_RECONSTRUCTION",
    }

    # Development outcome unseal starts here, after identity is fixed.
    y16 = load_rows(2016)
    if set(y16) != set(y11):
        raise SystemExit("2011/2016 historical IDs differ")
    obs16 = {cid: np.array([bucket_share(r)[p] for p in PARTIES], dtype=float) for cid,r in y16.items()}

    c1 = load_judgments(C1)
    if len(c1) != 92:
        raise SystemExit("expected 92 C1 judgments")
    j_by_tid = {x["anonymous_territory_id"]: x for x in c1}
    lambdas = [float(x) for x in conds["residual_transform"]["lambda_grid"]]
    grid = []
    for lam in lambdas:
        m = metrics(predict(bundle, j_by_tid, party_map, territory_map, lam), obs16)
        grid.append({"lambda": lam, **m})

    best = min(grid, key=lambda x: (x["macro_party_share_RMSE"], x["lambda"]))
    base = next(x for x in grid if x["lambda"] == 0.0)
    rel = (base["macro_party_share_RMSE"] - best["macro_party_share_RMSE"]) / base["macro_party_share_RMSE"]

    result = {
        "schema_version": "1.0",
        "result_id": "M26-E-REASON-DEVELOPMENT-2016-CALIBRATION-V1",
        "development_year": 2016,
        "outcome_unsealed_after_c1_c2_freeze": True,
        "identity_reconstruction_status": identity_certificate["status"],
        "primary_metric": "macro_party_share_RMSE",
        "lambda_grid_results": grid,
        "C0_lambda_zero_metrics": base,
        "selected_lambda_C1": best["lambda"],
        "selected_lambda_C2": best["lambda"],
        "selection_reason_C2": "C2 development ordinal residuals are frozen cellwise-identical to C1 on all 828 cells; same baseline, transform, grid and tie rule imply same selected lambda.",
        "selected_metrics": best,
        "relative_RMSE_improvement_vs_C0": rel,
        "holdout_2021_outcome_read": False,
        "status": "PASS_DEVELOPMENT_CALIBRATION_LAMBDA_SELECTED",
    }

    freeze = {
        "schema_version": "1.0",
        "freeze_id": "M26-E-REASON-LAMBDA-FREEZE-V1",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "lambda_C1": best["lambda"],
        "lambda_C2": best["lambda"],
        "lambda_grid": lambdas,
        "selection_metric": "2016 macro_party_share_RMSE",
        "tie_breaker": "smaller lambda",
        "development_calibration_result_status": result["status"],
        "C2_prompt_sha256": c2_receipt["c2_prompt_sha256"],
        "C2_judgment_manifest_sha256": c2_receipt["received_file_sha256_raw"]["c2_judgment_manifest.json"],
        "holdout_2021_outcome_seen_before_freeze": False,
        "all_judgment_generation_rules_frozen": True,
        "next_allowed_action": "BUILD_FREEZE_2021_BLINDED_PACKETS_THEN_RUN_C1_C2_WITH_FROZEN_RULES",
        "status": "FROZEN_BEFORE_2021_JUDGMENTS",
    }

    OUTDIR.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "identity_reconstruction_postfreeze_v1.json").write_text(json.dumps(identity_certificate, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    (OUTDIR / "calibration_2016_v1.json").write_text(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    (E / "lambda_freeze_v1.json").write_text(json.dumps(freeze, ensure_ascii=False, sort_keys=True, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "selected_lambda_C1": best["lambda"],
        "selected_lambda_C2": best["lambda"],
        "C0_RMSE": base["macro_party_share_RMSE"],
        "selected_RMSE": best["macro_party_share_RMSE"],
        "relative_improvement": rel,
        "max_identity_match_error": identity_certificate["max_territory_best_error"],
        "min_second_best_margin": identity_certificate["min_territory_second_best_margin"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
