from __future__ import annotations
"""Bridge V2 alignment: territory-local party bijections.

The frozen full environment declares party_ids_territory_local=true: Q_* labels
are scoped per territory. Bridge V1 assumed one national P->Q bijection and
correctly failed closed. Bridge V2 reconstructs a deterministic per-territory
mapping from blind baseline signatures without identities or outcomes.
"""
import itertools
import hashlib
from typing import Any, Mapping, Sequence

from main_bridge_core import BridgeError

ALIGNMENT_TOLERANCE = 1e-8
AMBIGUITY_MARGIN = 1e-6


def _signature(values: Sequence[float]) -> list[float]:
    return [float(v) for v in values]


def align_territory_parties(
    packet: Mapping[str, Any],
    env_packet: Mapping[str, Any],
    *,
    tolerance: float = ALIGNMENT_TOLERANCE,
    ambiguity_margin: float = AMBIGUITY_MARGIN,
) -> tuple[dict[str, str], dict[str, Any]]:
    """Find the unique optimal P->Q bijection for ONE territory.

    Gates:
    - perfect panel match;
    - best assignment error <= tolerance;
    - second-best assignment error exceeds best by >= ambiguity_margin
      (no ambiguous alternative mapping).
    """
    eid = str(packet.get("anonymous_election_id", ""))
    tid = str(packet.get("anonymous_territory_id", ""))
    parties = {str(p["anonymous_party_id"]): float(p["baseline_vote_share"]) for p in packet["parties"]}
    shares = {
        str(k): float(v)
        for k, v in ((env_packet.get("common_territory_card") or {}).get("previous_election_conditional_party_shares") or {}).items()
    }
    if not parties or not shares:
        raise BridgeError(f"empty share panel for {eid}|{tid}")
    pids = sorted(parties)
    qids = sorted(shares)
    if len(pids) != len(qids) or set(pids) != set(qids) and len(pids) != len(set(qids)):
        pass  # namespaces differ by design (P_* vs Q_*)
    if len(pids) != len(qids):
        raise BridgeError(f"party-panel size mismatch for {eid}|{tid}")
    expected_q = set(map(str, env_packet.get("available_party_ids") or []))
    if set(qids) != expected_q:
        raise BridgeError(f"environment share panel != available_party_ids for {eid}|{tid}")

    best_error, second_error, best_map = None, None, None
    for perm in itertools.permutations(range(len(qids))):
        mapping = {p: qids[perm[i]] for i, p in enumerate(pids)}
        err = max(abs(parties[p] - shares[mapping[p]]) for p in pids)
        if best_error is None or err < best_error:
            second_error = best_error
            best_error, best_map = err, mapping
        elif second_error is None or err < second_error:
            second_error = err
    if best_error is None or best_error > tolerance:
        raise BridgeError(
            f"territory alignment error {best_error} exceeds tolerance {tolerance} for {eid}|{tid}; refuse to guess"
        )
    if second_error is not None and second_error - best_error < ambiguity_margin:
        raise BridgeError(
            f"ambiguous alignment for {eid}|{tid}: best={best_error} second={second_error}; "
            "a deterministic mapping requires a clear margin"
        )
    digest = hashlib.sha256(
        "&".join(f"{p}->{best_map[p]}" for p in pids).encode()
    ).hexdigest()
    audit = {
        "method": "TERRITORY_LOCAL_SIGNATURE_BIJECTION_V2",
        "identity_information_used": False,
        "target_outcomes_used": False,
        "max_abs_error": best_error,
        "second_best_error": second_error,
        "tolerance": tolerance,
        "ambiguity_margin": ambiguity_margin,
        "bijection": True,
        "mapping_sha256": digest,
    }
    return best_map, audit


def align_election_parties_v2(
    bundle: Mapping[str, Any],
    environment: Mapping[str, Mapping[str, Any]],
    *,
    tolerance: float = ALIGNMENT_TOLERANCE,
) -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    """Build per-territory mappings for a whole election bundle."""
    eid = str(bundle.get("anonymous_election_id", ""))
    packets = bundle.get("packets") or []
    if not eid or len(packets) != 92:
        raise BridgeError(f"blind bundle {eid or '<missing>'} must contain exactly 92 packets")
    env_for = {
        k.split("|", 1)[1]: v for k, v in environment.items() if k.startswith(eid + "|")
    }
    if len(env_for) != 92:
        raise BridgeError(f"full environment does not contain 92 territories for {eid}")
    mappings: dict[str, dict[str, str]] = {}
    audits: dict[str, Any] = {}
    errors = []
    for packet in sorted(packets, key=lambda x: x["anonymous_territory_id"]):
        tid = str(packet["anonymous_territory_id"])
        env_packet = env_for[tid]
        mapping, audit = align_territory_parties(packet, env_packet, tolerance=tolerance)
        mappings[tid] = mapping
        audits[tid] = audit
        errors.append(audit["max_abs_error"])
    global_max = max(errors)
    if global_max > tolerance:
        raise BridgeError(f"global V2 alignment error {global_max} exceeds tolerance")
    return mappings, {
        "method": "TERRITORY_LOCAL_SIGNATURE_BIJECTION_V2",
        "election_id": eid,
        "territories_aligned": len(mappings),
        "global_max_abs_error": global_max,
        "tolerance": tolerance,
        "identity_information_used": False,
        "target_outcomes_used": False,
        "per_territory_audits": audits,
    }
