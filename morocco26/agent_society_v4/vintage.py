from __future__ import annotations

import copy
import hashlib
import json
from typing import Any, Mapping, Sequence

from .contracts import BallotType, CandidateRecord, CandidateState, ContractError, parse_date


class VintageError(ContractError):
    pass


def _hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(raw).hexdigest()


def _validate_source(source: Mapping[str, Any], as_of: str) -> None:
    if not str(source.get("source_id") or ""):
        raise VintageError("source_id required")
    known = str(source.get("known_at") or "")[:10]
    if not known:
        raise VintageError("source known_at required")
    if parse_date(known) > parse_date(as_of):
        raise VintageError("future source cannot enter a vintage")


def build_named_vintage(spec: Mapping[str, Any]) -> dict[str, Any]:
    """Build an immutable as-of 2026 election surface.

    Missing candidate identity is represented by UNKNOWN. It is never imputed.
    Every territory must carry distinct LOCAL and REGIONAL contests.
    """
    as_of = str(spec.get("as_of") or "")[:10]
    parse_date(as_of)
    main_sha = str(spec.get("source_main_commit") or "")
    if len(main_sha) != 40 or any(c not in "0123456789abcdef" for c in main_sha.lower()):
        raise VintageError("source_main_commit must be an exact 40-char SHA")
    territories = copy.deepcopy(spec.get("territories") or [])
    if not territories:
        raise VintageError("vintage requires at least one territory")
    seen_territories: set[str] = set()
    unknown_count = 0
    for territory in territories:
        tid = str(territory.get("territory_id") or "")
        if not tid or tid in seen_territories:
            raise VintageError("territory_id missing or duplicate")
        seen_territories.add(tid)
        if not str(territory.get("territory_name") or ""):
            raise VintageError("named 2026 territory requires territory_name")
        if float(territory.get("registered_electorate") or 0) <= 0:
            raise VintageError("registered_electorate must be positive")
        ballots = territory.get("ballots") or {}
        if set(ballots) != {"LOCAL", "REGIONAL"}:
            raise VintageError("every territory requires LOCAL and REGIONAL ballots")
        for ballot_name, contest in ballots.items():
            contest.setdefault("contest_id", f"{ballot_name}::{tid if ballot_name == 'LOCAL' else territory.get('region_id')}")
            options = contest.get("options") or []
            if len(options) < 2:
                raise VintageError("each ballot requires at least two options")
            parties: set[str] = set()
            for option in options:
                party = str(option.get("party_id") or "")
                if not party or party in parties:
                    raise VintageError("party_id missing or duplicate on ballot")
                parties.add(party)
                if not str(option.get("party_name") or ""):
                    raise VintageError("named 2026 option requires party_name")
                raw = option.get("candidate") or {"status": "UNKNOWN", "candidate_name": None, "known_at": None, "sources": [], "attributes": {}, "unknown_reason": "NOT_VERIFIED_AS_OF_VINTAGE"}
                state = CandidateState(str(raw.get("status") or "UNKNOWN"))
                if state is CandidateState.UNKNOWN:
                    raw.setdefault("candidate_name", None)
                    raw.setdefault("unknown_reason", "NOT_VERIFIED_AS_OF_VINTAGE")
                    unknown_count += 1
                candidate = CandidateRecord(
                    territory_id=tid,
                    party_id=party,
                    ballot=BallotType(ballot_name),
                    state=state,
                    candidate_name=raw.get("candidate_name"),
                    known_at=raw.get("known_at"),
                    sources=tuple(raw.get("sources") or ()),
                    attributes=raw.get("attributes") or {},
                )
                candidate.validate(as_of=as_of)
                option["candidate"] = {**raw, "status": state.value}
                for source in option.get("program_sources") or []:
                    _validate_source(source, as_of)
    payload = {
        "schema_version": "AGENT_SOCIETY_NAMED_2026_VINTAGE_V4",
        "status": "PARTIAL_AS_OF_VINTAGE_READY" if unknown_count else "CANDIDATE_IDENTITIES_COMPLETE_NOT_YET_FINAL_BALLOT_CERTIFIED",
        "snapshot_id": str(spec.get("snapshot_id") or f"M26_{as_of}"),
        "as_of": as_of,
        "source_main_commit": main_sha.lower(),
        "regime": "NAMED_REALISTIC_2026",
        "territories": territories,
        "unknown_candidate_cells": unknown_count,
        "silent_candidate_imputation": False,
        "outcomes_present": False,
        "final_ballot_claim": False,
    }
    payload["snapshot_sha256"] = _hash(payload)
    return payload


def diff_vintages(old: Mapping[str, Any], new: Mapping[str, Any]) -> dict[str, Any]:
    if parse_date(str(new["as_of"])[:10]) <= parse_date(str(old["as_of"])[:10]):
        raise VintageError("new vintage must have a later as_of")
    def index(snapshot: Mapping[str, Any]) -> dict[tuple[str, str, str], Mapping[str, Any]]:
        result = {}
        for territory in snapshot.get("territories") or []:
            for ballot, contest in (territory.get("ballots") or {}).items():
                for option in contest.get("options") or []:
                    result[(str(territory["territory_id"]), ballot, str(option["party_id"]))] = option
        return result
    a, b = index(old), index(new)
    affected: set[tuple[str, str]] = set()
    changes = []
    for key in sorted(set(a) | set(b)):
        before, after = a.get(key), b.get(key)
        if before != after:
            affected.add((key[0], key[1]))
            changes.append({"territory_id": key[0], "ballot": key[1], "party_id": key[2], "before_sha256": _hash(before), "after_sha256": _hash(after)})
    return {"schema_version": "AGENT_SOCIETY_VINTAGE_DIFF_V4", "old_snapshot_id": old.get("snapshot_id"), "new_snapshot_id": new.get("snapshot_id"), "changes": changes, "affected_contests": [{"territory_id": t, "ballot": b} for t, b in sorted(affected)], "full_national_rerun_required": False}
