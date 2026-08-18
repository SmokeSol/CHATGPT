#!/usr/bin/env python3
"""Generate frozen C1_RULE_ONLY judgments on the already-frozen blinded DEVELOPMENT bundle.

This script is outcome-blind by construction: it reads only the blinded packet bundle and the
frozen conditions contract. It never reads the anonymization mapping, 2016 outcomes, 2021
outcomes, Atlas, F0, or any post-event material.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
BUNDLE = E / "blind" / "development" / "blind_bundle.json"
CONDITIONS = E / "e_reason_conditions_v1.json"
OUTDIR = E / "judgments" / "development" / "c1_rule_only"

RUN_ID = "M26-E-REASON-C1-DEV-RULE-V1"
MODEL_ID = "DETERMINISTIC_C1_RULE_V1"


def canon_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha_obj(obj):
    return hashlib.sha256(canon_bytes(obj)).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def ordinal(raw):
    if raw <= -1.5:
        return -2
    if raw <= -0.25:
        return -1
    if raw < 0.25:
        return 0
    if raw < 1.5:
        return 1
    return 2


def main():
    bundle = read_json(BUNDLE)
    conditions = read_json(CONDITIONS)
    rule = conditions["C1_RULE_ONLY"]
    points = {k: float(v) for k, v in rule["feature_points"].items()}

    if bundle.get("packet_count") != 92 or bundle.get("party_cells") != 828:
        raise SystemExit("unexpected frozen bundle cardinality")
    if len(bundle.get("packets", [])) != 92:
        raise SystemExit("expected 92 frozen packets")

    created = datetime.now(timezone.utc).isoformat()
    finals = []
    packet_hashes = []
    score_counts = {str(k): 0 for k in (-2, -1, 0, 1, 2)}

    for packet in bundle["packets"]:
        parties = packet.get("parties", [])
        if len(parties) != 9:
            raise SystemExit("packet does not contain exactly nine parties")
        judgments = []
        for party in parties:
            features = {f["feature_id"]: f for f in party.get("features", [])}
            raw = 0.0
            cited = []
            contributions = []
            for feature_id, weight in points.items():
                f = features.get(feature_id)
                if not f:
                    continue
                if f.get("status") in {"MISSING", "NOT_FOUND", "UNVERIFIED", "DATA_BLOCKED", "AMBIGUOUS"}:
                    continue
                if bool(f.get("conflict")):
                    continue
                if f.get("value") is True:
                    raw += weight
                    cited.append(feature_id)
                    contributions.append({"feature_id": feature_id, "points": weight})
            z = ordinal(raw)
            score_counts[str(z)] += 1
            judgments.append({
                "anonymous_party_id": party["anonymous_party_id"],
                "ordinal_score": z,
                "evidence_feature_ids": sorted(cited),
                "abstain": z == 0,
                "confidence": 1.0,
                "brief_reason": "Deterministic frozen C1 feature-point rubric; raw_score=" + format(raw, ".6g"),
                "audit_raw_score": raw,
                "audit_contributions": contributions,
            })

        # Keep public-schema-compatible final object separate from extra audit details.
        public_judgments = []
        audit = []
        for x in judgments:
            public_judgments.append({k: x[k] for k in (
                "anonymous_party_id", "ordinal_score", "evidence_feature_ids", "abstain", "confidence", "brief_reason"
            )})
            audit.append({
                "anonymous_party_id": x["anonymous_party_id"],
                "raw_score": x["audit_raw_score"],
                "contributions": x["audit_contributions"],
            })

        obj = {
            "run_id": RUN_ID,
            "condition_id": "C1_RULE_ONLY",
            "anonymous_election_id": packet["anonymous_election_id"],
            "anonymous_territory_id": packet["anonymous_territory_id"],
            "packet_sha256": packet["packet_sha256"],
            "model_or_human_id": MODEL_ID,
            "judgments": public_judgments,
            "attempt_number": 1,
            "created_at": created,
        }
        finals.append(obj)
        packet_hashes.append(packet["packet_sha256"])

    if len(finals) != 92 or sum(len(x["judgments"]) for x in finals) != 828:
        raise SystemExit("C1 output cardinality failure")

    OUTDIR.mkdir(parents=True, exist_ok=True)
    judgments_path = OUTDIR / "c1_judgments.jsonl"
    judgments_path.write_text("".join(json.dumps(x, ensure_ascii=False, sort_keys=True) + "\n" for x in finals), encoding="utf-8")

    hashes = [sha_obj(x) for x in finals]
    manifest = {
        "schema_version": "1.0",
        "manifest_id": "M26-E-REASON-C1-DEV-JUDGMENT-MANIFEST-V1",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "run_id": RUN_ID,
        "condition_id": "C1_RULE_ONLY",
        "model_or_human_id": MODEL_ID,
        "bundle_sha256": bundle["bundle_sha256"],
        "packet_sha256_ordered": packet_hashes,
        "judgment_sha256_ordered": hashes,
        "counts": {
            "packets": 92,
            "party_cells": 828,
            "score_distribution": score_counts,
        },
        "outcomes_seen": False,
        "mapping_seen": False,
        "web_used": False,
        "tools_used": False,
        "generation_rule": "EXACT_FROZEN_C1_FEATURE_POINTS_AND_ORDINAL_THRESHOLDS",
        "status": "PASS_C1_JUDGMENTS_FROZEN_READY_FOR_2016_CALIBRATION",
    }
    manifest_path = OUTDIR / "c1_judgment_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    terminal = {
        "schema_version": "1.0",
        "report_id": "M26-E-REASON-C1-DEV-TERMINAL-REPORT-V1",
        "terminal_status": manifest["status"],
        "run_id": RUN_ID,
        "bundle_sha256": bundle["bundle_sha256"],
        "valid_final_judgments": "92/92",
        "outcomes_seen": False,
        "mapping_seen": False,
        "next_allowed_action": "UNSEAL_2016_AND_CALIBRATE_LAMBDA_C1_C2_USING_FROZEN_JUDGMENTS_ONLY",
    }
    (OUTDIR / "c1_terminal_report.json").write_text(json.dumps(terminal, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(manifest["status"])
    print(json.dumps(manifest["counts"], sort_keys=True))


if __name__ == "__main__":
    main()
