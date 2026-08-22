from __future__ import annotations

"""Bridge V7: connect the V4 named-vintage (partial, UNKNOWN-aware) to the V6
named-2026 pipeline as a CURRENT_VINTAGE regime distinct from FINAL_BALLOT.

V4 already implements: OFFICIAL/DECLARED/REPORTED/UNKNOWN/NO_LIST states,
UNKNOWN as valid information with provenance gates, LOCAL+REGIONAL dual ballots
with split ticket, information diets, AgenticDelta (log-ratio) + lambda blend,
dated/hashed immutable snapshots. V6 named input requires VERIFIED_DOUBLE_ENTRY
for every ballot cell - correct for FINAL_BALLOT_2026 but impossible for a
current knowledge snapshot.

V7 adds: vintage_to_named_input() converting a V4 snapshot into a V6-compatible
named input where every cell carries its true state; UNKNOWN/NO_LIST cells are
explicit rows with candidate_name=None and verification_state=STATE_AS_OF_VINTAGE.
The FINAL_BALLOT gate remains unchanged for future use.
"""
import hashlib
from typing import Any, Mapping

from .contracts import CandidateState

try:
    from three_regime_core import ThreeRegimeError, validate_named_input
except ImportError:  # when imported from agent_society_v4 package context
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from three_regime_core import ThreeRegimeError, validate_named_input

CURRENT_VINTAGE = "P3_CURRENT_VINTAGE_2026"
FINAL_BALLOT = "FINAL_BALLOT_2026"

_STATE_TO_VERIFICATION = {
    CandidateState.OFFICIAL.value: "OFFICIAL_CONFIRMED",
    CandidateState.DECLARED.value: "DECLARED_BY_PARTY",
    CandidateState.REPORTED.value: "REPORTED_UNCONFIRMED",
    CandidateState.UNKNOWN.value: "UNKNOWN_AS_OF_SNAPSHOT",
    CandidateState.NO_LIST.value: "NO_LIST_EVIDENCED",
}


def classify_p3_gate(snapshot):
    """Two-gate P3 classification for a V4 named vintage snapshot."""
    unknown = int(snapshot.get("unknown_candidate_cells") or 0)
    total_cells = sum(
        len(contest.get("options") or [])
        for territory in snapshot.get("territories") or []
        for contest in (territory.get("ballots") or {}).values()
    )
    final_ballot_claim = bool(snapshot.get("final_ballot_claim"))
    return {
        "schema_version": "AGENT_SOCIETY_P3_GATE_V7",
        "P3_CURRENT_VINTAGE_2026": {
            "status": "PASS" if total_cells > 0 else "FAIL_EMPTY_SNAPSHOT",
            "rationale": (
                "Honest partial-as-of snapshot: UNKNOWN cells are explicit "
                "information, not fabrication."
            ),
            "unknown_candidate_cells": unknown,
            "total_ballot_cells": total_cells,
            "unknown_fraction": round(unknown / max(1, total_cells), 6),
            "silent_candidate_imputation": bool(snapshot.get("silent_candidate_imputation")),
        },
        "FINAL_BALLOT_2026": {
            "status": "PASS" if final_ballot_claim else "BLOCKED_NOT_A_FINAL_BALLOT",
            "rationale": "Requires certified definitive bulletins; unchanged from V6.",
        },
    }


def _vintage_state(option):
    return str((option.get("candidate") or {}).get("status") or "UNKNOWN")


def vintage_to_named_input(snapshot, *, parties, programmes, source_records,
                           voter_population, conditions, national_context,
                           artifact_id=None):
    """Convert a V4 named vintage into a V6-compatible named input."""
    as_of = str(snapshot.get("as_of") or "")
    if not as_of:
        raise ThreeRegimeError("vintage missing as_of")
    main_sha = str(snapshot.get("source_main_commit") or "")
    party_ids = {str(p["party_id"]) for p in parties}
    programme_ids = {str(p.get("party_id")) for p in programmes}
    if not programme_ids.issubset(party_ids):
        raise ThreeRegimeError("programmes reference parties outside the panel")
    source_ids = {str(s["source_record_id"]) for s in source_records}

    territories_out = []
    candidacies = []
    expected_pairs = set()
    state_counts = {}

    for territory in snapshot.get("territories") or []:
        tid = str(territory["territory_id"])
        local = (territory.get("ballots") or {}).get("LOCAL") or {}
        options = local.get("options") or []
        if len(options) < 2:
            raise ThreeRegimeError(f"territory {tid} has fewer than two LOCAL options")
        ballot_party_ids = []
        for option in options:
            pid = str(option["party_id"])
            if pid not in party_ids:
                raise ThreeRegimeError(f"ballot party {pid} outside declared panel")
            ballot_party_ids.append(pid)
            raw = option.get("candidate") or {}
            state = _vintage_state(option)
            state_counts[state] = state_counts.get(state, 0) + 1
            verification = _STATE_TO_VERIFICATION.get(state)
            if verification is None:
                raise ThreeRegimeError(f"unhandled candidate state {state}")
            name = raw.get("candidate_name")
            known_at = raw.get("known_at") or as_of
            sources = [str(src.get("source_id")) for src in (raw.get("sources") or [])]
            sources = [s for s in sources if s in source_ids][:2] or ["VINTAGE_" + as_of]
            cell_id = hashlib.sha256((tid + "|" + pid).encode()).hexdigest()[:12].upper()
            row = {
                "territory_id": tid,
                "party_id": pid,
                "candidate_id": f"CAND_{cell_id}",
                "candidate_name": name,
                "verification_state": verification,
                "known_as_of": known_at,
                "source_record_ids": sources,
                "verified_profile": option.get("attributes") or {},
                "public_familiarity_band": None,
                "local_viability_band": None,
            }
            if state == CandidateState.UNKNOWN.value:
                row["candidate_id"] = f"UNKNOWN_{cell_id}"
                row["candidate_name"] = None
            elif state == CandidateState.NO_LIST.value:
                row["candidate_id"] = f"NO_LIST_{cell_id}"
                row["candidate_name"] = None
            elif not name:
                raise ThreeRegimeError(f"{state} candidacy without candidate_name at {tid}|{pid}")
            candidacies.append(row)
            expected_pairs.add((tid, pid))
        territories_out.append({
            "territory_id": tid,
            "territory_name": str(territory.get("territory_name") or tid),
            "region_name": territory.get("region_name"),
            "ballot_party_ids": ballot_party_ids,
            "verified_context": {
                "registered_electorate": territory.get("registered_electorate"),
                "region_id": territory.get("region_id"),
            },
        })

    result = {
        "schema_version": "1.0",
        "artifact_id": artifact_id or f"M26_CURRENT_VINTAGE_{as_of}",
        "main_commit_sha": main_sha,
        "snapshot_known_as_of": as_of,
        "regime_gate": CURRENT_VINTAGE,
        "national_context": national_context,
        "territories": territories_out,
        "parties": parties,
        "candidacies": candidacies,
        "programmes": programmes,
        "source_records": source_records,
        "voter_population": voter_population,
        "conditions": conditions,
        "coverage": {
            "all_intended_ballot_cells_verified": False,
            "intended_ballot_cells": len(expected_pairs),
            "verification_note": (
                "CURRENT_VINTAGE: cells verified to their true as-of state "
                "(OFFICIAL/DECLARED/REPORTED/UNKNOWN/NO_LIST), not to a final ballot."
            ),
        },
        "state_census": state_counts,
        "vintage_snapshot_sha256": snapshot.get("snapshot_sha256"),
    }
    return result


def validate_current_vintage_input(value):
    """Structural validation for a current-vintage named input.

    Checks dates <= snapshot, panel/ballot/candidacy consistency, and coverage
    honesty. Does NOT require 92 territories (sub-scale pilots are valid) and
    does NOT require final-balllot verification states.
    """
    if value.get("regime_gate") != CURRENT_VINTAGE:
        raise ThreeRegimeError("input is not tagged as P3_CURRENT_VINTAGE_2026")
    import datetime as dt

    def _date(v, label):
        try:
            return dt.date.fromisoformat(str(v)[:10])
        except (ValueError, TypeError) as exc:
            raise ThreeRegimeError(f"invalid date {label}: {v}") from exc

    snapshot_date = _date(value.get("snapshot_known_as_of"), "snapshot_known_as_of")
    main_sha = str(value.get("main_commit_sha") or "")
    if len(main_sha) != 40 or any(c not in "0123456789abcdef" for c in main_sha.lower()):
        raise ThreeRegimeError("main_commit_sha must be exact 40-hex SHA")

    party_ids = {str(p.get("party_id")) for p in value.get("parties") or []}
    if len(party_ids) < 2:
        raise ThreeRegimeError("fewer than two parties")

    territory_ids = set()
    for t in value.get("territories") or []:
        tid = str(t.get("territory_id") or "")
        if not tid or tid in territory_ids:
            raise ThreeRegimeError(f"territory_id missing/duplicate: {tid}")
        territory_ids.add(tid)
        bp = t.get("ballot_party_ids") or []
        if len(bp) < 2 or not set(bp).issubset(party_ids):
            raise ThreeRegimeError(f"invalid ballot_party_ids for {tid}")

    seen_pairs = set()
    for c in value.get("candidacies") or []:
        pair = (str(c.get("territory_id")), str(c.get("party_id")))
        if pair[0] not in territory_ids or pair[1] not in party_ids:
            raise ThreeRegimeError(f"candidacy outside panel: {pair}")
        if pair in seen_pairs:
            raise ThreeRegimeError(f"duplicate candidacy: {pair}")
        seen_pairs.add(pair)
        kd = _date(c.get("known_as_of"), f"candidacy[{pair}].known_as_of")
        if kd > snapshot_date:
            raise ThreeRegimeError(f"candidacy[{pair}] known_as_of after snapshot")
        vs = str(c.get("verification_state") or "")
        allowed = set(_STATE_TO_VERIFICATION.values())
        if vs not in allowed:
            raise ThreeRegimeError(f"candidacy[{pair}] invalid verification_state: {vs}")
        state_name = c.get("candidate_name")
        needs_name = vs in ("OFFICIAL_CONFIRMED", "DECLARED_BY_PARTY", "REPORTED_UNCONFIRMED")
        if needs_name and not state_name:
            raise ThreeRegimeError(f"candidacy[{pair}] {vs} requires candidate_name")
        if not needs_name and state_name:
            raise ThreeRegimeError(f"candidacy[{pair}] {vs} must have candidate_name=None")

    # Coverage honesty
    declared_cells = int((value.get("coverage") or {}).get("intended_ballot_cells") or 0)
    ballot_cells = sum(
        len(t.get("ballot_party_ids") or []) for t in value.get("territories") or []
    )
    if declared_cells != ballot_cells:
        raise ThreeRegimeError(
            f"coverage.intended_ballot_cells {declared_cells} != ballot cells {ballot_cells}"
        )
    if len(seen_pairs) != ballot_cells:
        raise ThreeRegimeError(
            f"candidacies {len(seen_pairs)} != ballot cells {ballot_cells}"
        )

    return {
        "status": "PASS_CURRENT_VINTAGE_INPUT_READY",
        "validation_mode": CURRENT_VINTAGE,
        "coverage_declared_final": False,
        "territories": len(territory_ids),
        "parties": len(party_ids),
        "candidacies": len(seen_pairs),
        "state_census": dict(value.get("state_census") or {}),
        "snapshot_known_as_of": str(value.get("snapshot_known_as_of")),
    }
