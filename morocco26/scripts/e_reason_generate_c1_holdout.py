#!/usr/bin/env python3
"""Generate C1_RULE_ONLY judgments on the already-frozen blinded HOLDOUT bundle.

No mapping or target-election outcome is read. Generation is deterministic and refuses to
run if the holdout bundle is not frozen or if outputs already exist.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
BUNDLE = E / "blind" / "holdout" / "blind_bundle.json"
MANIFEST = E / "blind" / "holdout" / "bundle_manifest.json"
CONDITIONS = E / "e_reason_conditions_v1.json"
LAMBDA = E / "lambda_freeze_v1.json"
OUTDIR = E / "judgments" / "holdout" / "c1_rule_only"
RUN_ID = "M26-E-REASON-C1-HOLDOUT-RULE-V1"
MODEL_ID = "DETERMINISTIC_C1_RULE_V1"


def canon_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha_obj(obj):
    return hashlib.sha256(canon_bytes(obj)).hexdigest()


def read_json(p):
    return json.loads(p.read_text(encoding="utf-8"))


def ordinal(raw):
    if raw <= -1.5: return -2
    if raw <= -0.25: return -1
    if raw < 0.25: return 0
    if raw < 1.5: return 1
    return 2


def main():
    if OUTDIR.exists():
        raise SystemExit("holdout C1 outputs already exist; refusing regeneration")
    bundle = read_json(BUNDLE)
    manifest = read_json(MANIFEST)
    conditions = read_json(CONDITIONS)
    lam = read_json(LAMBDA)
    if manifest.get("status") != "FROZEN_BLIND_HOLDOUT_BUNDLE":
        raise SystemExit("holdout bundle is not frozen")
    if lam.get("status") != "FROZEN_BEFORE_2021_JUDGMENTS":
        raise SystemExit("lambda is not frozen before holdout judgments")
    if bundle.get("bundle_sha256") != manifest.get("bundle_sha256"):
        raise SystemExit("holdout bundle/manifest hash mismatch")
    points = {k: float(v) for k,v in conditions["C1_RULE_ONLY"]["feature_points"].items()}
    created = "FROZEN_WITH_HOLDOUT_BUNDLE_" + manifest["bundle_sha256"][:16]
    finals=[]; score_counts={str(k):0 for k in (-2,-1,0,1,2)}
    for pkt in bundle["packets"]:
        js=[]
        for party in pkt["parties"]:
            feats={f["feature_id"]:f for f in party["features"]}
            raw=0.0; cited=[]
            for fid,w in points.items():
                f=feats.get(fid)
                if not f or f.get("status") in {"MISSING","NOT_FOUND","UNVERIFIED","DATA_BLOCKED","AMBIGUOUS"} or f.get("conflict"):
                    continue
                if f.get("value") is True:
                    raw += w; cited.append(fid)
            z=ordinal(raw); score_counts[str(z)]+=1
            js.append({
                "anonymous_party_id":party["anonymous_party_id"],
                "ordinal_score":z,
                "evidence_feature_ids":sorted(cited),
                "abstain":z==0,
                "confidence":1.0,
                "brief_reason":"Deterministic frozen C1 feature-point rubric; raw_score="+format(raw,".6g"),
            })
        obj={
            "run_id":RUN_ID,
            "condition_id":"C1_RULE_ONLY",
            "anonymous_election_id":pkt["anonymous_election_id"],
            "anonymous_territory_id":pkt["anonymous_territory_id"],
            "packet_sha256":pkt["packet_sha256"],
            "model_or_human_id":MODEL_ID,
            "judgments":js,
            "attempt_number":1,
            "created_at":created,
        }
        finals.append(obj)
    if len(finals)!=92 or sum(len(x["judgments"]) for x in finals)!=828:
        raise SystemExit("C1 holdout cardinality failure")
    OUTDIR.mkdir(parents=True)
    (OUTDIR/"c1_judgments.jsonl").write_text("".join(json.dumps(x,ensure_ascii=False,sort_keys=True)+"\n" for x in finals),encoding="utf-8")
    jhash=[sha_obj(x) for x in finals]
    mout={
        "schema_version":"1.0",
        "manifest_id":"M26-E-REASON-C1-HOLDOUT-JUDGMENT-MANIFEST-V1",
        "experiment_id":"M26-GOAL100-E-REASON-V1",
        "run_id":RUN_ID,
        "condition_id":"C1_RULE_ONLY",
        "model_or_human_id":MODEL_ID,
        "bundle_sha256":manifest["bundle_sha256"],
        "lambda_C1":lam["lambda_C1"],
        "packet_sha256_ordered":[p["packet_sha256"] for p in bundle["packets"]],
        "judgment_sha256_ordered":jhash,
        "counts":{"packets":92,"party_cells":828,"score_distribution":score_counts},
        "outcomes_seen":False,
        "mapping_seen":False,
        "web_used":False,
        "tools_used":False,
        "generation_rule":"EXACT_FROZEN_C1_FEATURE_POINTS_AND_ORDINAL_THRESHOLDS",
        "status":"PASS_C1_HOLDOUT_JUDGMENTS_FROZEN_AWAITING_C2",
    }
    (OUTDIR/"c1_judgment_manifest.json").write_text(json.dumps(mout,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    (OUTDIR/"c1_terminal_report.json").write_text(json.dumps({
        "schema_version":"1.0",
        "terminal_status":mout["status"],
        "run_id":RUN_ID,
        "bundle_sha256":manifest["bundle_sha256"],
        "valid_final_judgments":"92/92",
        "outcomes_seen":False,
        "mapping_seen":False,
        "next_allowed_action":"RUN_C2_OPUS5_ON_SAME_FROZEN_HOLDOUT_PACKETS_AND_FREEZE_HASHES_BEFORE_OUTCOME_UNSEAL",
    },sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":mout["status"],"scores":score_counts},sort_keys=True))

if __name__ == "__main__": main()
