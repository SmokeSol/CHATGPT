from __future__ import annotations
import hashlib
from typing import Any, Mapping, Sequence
from main_bridge_core import (
    BRIDGE_ID, SCHEMA_VERSION, BridgeError, assert_no_forbidden_keys, leak_scan,
)
from main_bridge_alignment import align_election_parties

META_FEATURES = {"BALLOT_LIST_PRESENT", "EVIDENCE_COUNT", "SOURCE_CLASS_MAX", "SOURCE_CONFLICT"}


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


def _semantic_feature(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "feature_id": str(raw.get("feature_id", "")),
        "status": raw.get("status"),
        "value": raw.get("value"),
        "conflict": bool(raw.get("conflict", False)),
    }


def assert_semantic_equivalence(
    env: Mapping[str, Any], candidate_cards: Sequence[Mapping[str, Any]],
    programme_cards: Sequence[Mapping[str, Any]], *, key: str,
) -> dict[str, int | str]:
    """Bridge V1 is provenance-only: it may not silently change model semantics."""
    env_candidate_cards = (env.get("common_territory_card") or {}).get("party_context_cards") or []
    env_by_q = {str(x.get("anonymous_party_id")): x for x in env_candidate_cards}
    bridge_by_q = {str(x.get("anonymous_party_id")): x for x in candidate_cards}
    expected_q = set(map(str, env.get("available_party_ids") or []))
    if set(env_by_q) != expected_q or set(bridge_by_q) != expected_q:
        raise BridgeError(f"candidate party panel mismatch during semantic equivalence audit for {key}")

    feature_cells = 0
    ignored_meta_cells = 0
    for qid in sorted(expected_q):
        env_features = {
            str(f.get("feature_id")): _semantic_feature(f)
            for f in env_by_q[qid].get("features") or []
        }
        bridge_features = {
            str(f.get("feature_id")): _semantic_feature(f)
            for f in bridge_by_q[qid].get("features") or []
            if str(f.get("feature_id")) not in META_FEATURES
        }
        ignored_meta_cells += sum(
            1 for f in bridge_by_q[qid].get("features") or []
            if str(f.get("feature_id")) in META_FEATURES
        )
        if set(env_features) != set(bridge_features):
            added = sorted(set(bridge_features) - set(env_features))
            missing = sorted(set(env_features) - set(bridge_features))
            raise BridgeError(
                f"Bridge V1 candidate feature-set drift for {key}|{qid}: added={added} missing={missing}; "
                "a semantic delta requires a new bridge protocol version"
            )
        for fid in sorted(env_features):
            feature_cells += 1
            if env_features[fid] != bridge_features[fid]:
                raise BridgeError(
                    f"Bridge V1 candidate semantic drift for {key}|{qid}|{fid}; "
                    "a changed value/status/conflict requires a new bridge protocol version"
                )

    env_programme = {
        str(x.get("anonymous_party_id")): {
            "government_status": x.get("government_status"),
            "program_priority_levels": x.get("program_priority_levels") or {},
        }
        for x in ((env.get("election_environment_card") or {}).get("party_offer_cards") or [])
    }
    bridge_programme = {
        str(x.get("anonymous_party_id")): {
            "government_status": x.get("government_status"),
            "program_priority_levels": x.get("program_priority_levels") or {},
        }
        for x in programme_cards
    }
    if env_programme != bridge_programme:
        raise BridgeError(
            f"Bridge V1 programme semantic drift for {key}; a programme change requires a new bridge protocol version"
        )
    return {
        "status": "PASS_SEMANTIC_EQUIVALENCE_ONLY",
        "candidate_feature_cells_verified_identical": feature_cells,
        "candidate_meta_cells_retained_for_provenance_only": ignored_meta_cells,
        "programme_party_cards_verified_identical": len(env_programme),
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
    equivalence_totals = {
        "candidate_feature_cells_verified_identical": 0,
        "candidate_meta_cells_retained_for_provenance_only": 0,
        "programme_party_cards_verified_identical": 0,
    }
    for eid in env_eids:
        bundle = by_eid[eid]
        ptoq, audit = align_election_parties(bundle, environment)
        audits[eid] = audit
        for packet in bundle["packets"]:
            tid = str(packet["anonymous_territory_id"])
            key = f"{eid}|{tid}"
            env = environment[key]
            cc = [
                candidate_card(eid, tid, ptoq[str(p["anonymous_party_id"])], p)
                for p in packet["parties"]
            ]
            cc.sort(key=lambda x: x["anonymous_party_id"])
            pc = [programme_card(env, q) for q in sorted(env["available_party_ids"])]
            eq = assert_semantic_equivalence(env, cc, pc, key=key)
            for name in equivalence_totals:
                equivalence_totals[name] += int(eq[name])
            items[key] = {
                "anonymous_election_id": eid,
                "anonymous_territory_id": tid,
                "candidate_offer": {
                    "status": "FROZEN_MAIN_BLIND_EVIDENCE_PROVENANCE_CONNECTED_SEMANTIC_EQUIVALENCE_VERIFIED",
                    "cards": cc,
                    "real_names_present": False,
                    "missingness_is_information": False,
                    "model_semantic_delta_v1": False,
                },
                "programme_offer": {
                    "status": "PRESERVED_EXISTING_FROZEN_ENVIRONMENT_LAYER",
                    "cards": pc,
                    "model_semantic_delta_v1": False,
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
        "model_semantic_delta_v1": False,
        "source_hashes": dict(sorted(source_hashes.items())),
        "historical_controls": controls,
        "party_alignment_audit": audits,
        "semantic_equivalence_audit": {
            "status": "PASS_SEMANTIC_EQUIVALENCE_ONLY",
            **equivalence_totals,
        },
        "item_count": len(items),
        "items": items,
        "public_leak_scan": {"status": "PASS", "violations": []},
    }
