from __future__ import annotations
import hashlib
from typing import Any, Mapping, Sequence
from main_bridge_core import (
    BRIDGE_ID, SCHEMA_VERSION, BridgeError, assert_no_forbidden_keys, leak_scan,
)
from main_bridge_alignment import align_election_parties

def candidate_card(eid: str, tid: str, qid: str, party: Mapping[str, Any]):
    features = []
    for raw in party.get("features") or []:
        fid = str(raw.get("feature_id", ""))
        if not fid:
            continue
        features.append({
            "feature_id": fid,
            "status": raw.get("status", "MISSING"),
            "value": raw.get("value"),
            "conflict": bool(raw.get("conflict", False)),
            "source_class": raw.get("source_class", "NONE"),
            "source_record_ids": list(raw.get("source_record_ids") or []),
        })
    features.sort(key=lambda x: x["feature_id"])
    fd = {x["feature_id"]: x for x in features}
    present = fd.get("BALLOT_LIST_PRESENT", {}).get("value")
    observed = sum(
        1 for x in features
        if x["status"] == "VERIFIED" and x["value"] is not None and not x["conflict"]
    )
    cid = "C_" + hashlib.sha256(
        f"{BRIDGE_ID}|{eid}|{tid}|{qid}".encode()
    ).hexdigest()[:16].upper()
    return {
        "anonymous_party_id": qid,
        "anonymous_candidate_id": cid,
        "candidate_role": "LOCAL_LIST_HEAD_OR_PRIMARY_CANDIDATE_CELL",
        "ballot_presence": (
            "VERIFIED_PRESENT" if present is True else
            ("VERIFIED_ABSENT" if present is False else "MISSING_OR_UNVERIFIED")
        ),
        "evidence_completeness": party.get("evidence_completeness") or {
            "observed_feature_count": observed,
            "missingness_explicit": True,
        },
        "features": features,
    }

def programme_card(env: Mapping[str, Any], qid: str):
    cards = ((env.get("election_environment_card") or {}).get("party_offer_cards") or [])
    for raw in cards:
        if str(raw.get("anonymous_party_id")) == qid:
            return {
                "anonymous_party_id": qid,
                "status": "PRESENT_IN_FROZEN_FULL_ENVIRONMENT",
                "provenance": "FROZEN_ENVIRONMENT_EXISTING_PROGRAMME_LAYER_NOT_REBUILT_BY_MAIN_BRIDGE_V1",
                "government_status": raw.get("government_status"),
                "program_priority_levels": raw.get("program_priority_levels") or {},
            }
    return {
        "anonymous_party_id": qid,
        "status": "MISSING",
        "provenance": "NO_PROGRAMME_CARD_IN_FROZEN_ENVIRONMENT",
        "government_status": None,
        "program_priority_levels": {},
    }

def build_overlay(
    *, main_sha: str, blind_bundles: Sequence[Mapping[str, Any]],
    environment: Mapping[str, Mapping[str, Any]], source_hashes: Mapping[str, str],
    controls: Mapping[str, Any],
):
    by_eid = {str(b["anonymous_election_id"]): b for b in blind_bundles}
    env_eids = sorted({k.split("|", 1)[0] for k in environment})
    if set(by_eid) != set(env_eids):
        raise BridgeError(
            f"blind/full-environment election ids differ: blind={sorted(by_eid)} env={env_eids}"
        )
    items, audits = {}, {}
    for eid in env_eids:
        bundle = by_eid[eid]
        ptoq, audit = align_election_parties(bundle, environment)
        audits[eid] = audit
        for packet in bundle["packets"]:
            tid = str(packet["anonymous_territory_id"])
            env = environment[f"{eid}|{tid}"]
            cc = [
                candidate_card(eid, tid, ptoq[str(p["anonymous_party_id"])], p)
                for p in packet["parties"]
            ]
            cc.sort(key=lambda x: x["anonymous_party_id"])
            pc = [programme_card(env, q) for q in sorted(env["available_party_ids"])]
            items[f"{eid}|{tid}"] = {
                "anonymous_election_id": eid,
                "anonymous_territory_id": tid,
                "candidate_offer": {
                    "status": "FROZEN_MAIN_BLIND_EVIDENCE_CONNECTED",
                    "cards": cc,
                    "real_names_present": False,
                    "missingness_is_information": False,
                },
                "programme_offer": {
                    "status": "PRESERVED_EXISTING_FROZEN_ENVIRONMENT_LAYER",
                    "cards": pc,
                    "main_bridge_v1_note": (
                        "Bridge V1 found no separately registered canonical full-manifesto corpus on main; "
                        "it preserves the already-frozen anonymous programme-priority cards and does not fabricate detail."
                    ),
                },
            }
    assert_no_forbidden_keys(items)
    findings = leak_scan(items)
    if findings:
        raise BridgeError(f"public overlay leakage scan failed: {findings}")
    return {
        "schema_version": SCHEMA_VERSION,
        "bridge_id": BRIDGE_ID,
        "status": "PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL",
        "main_commit_sha": main_sha,
        "target_outcomes_present": False,
        "real_identity_material_present": False,
        "floating_main_reads_allowed": False,
        "source_hashes": dict(sorted(source_hashes.items())),
        "historical_controls": controls,
        "party_alignment_audit": audits,
        "item_count": len(items),
        "items": items,
        "public_leak_scan": {"status": "PASS", "violations": []},
    }
