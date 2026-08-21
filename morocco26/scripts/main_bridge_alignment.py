from __future__ import annotations
from typing import Any, Mapping
from main_bridge_core import BridgeError

def align_election_parties(
    blind_bundle: Mapping[str, Any],
    environment: Mapping[str, Mapping[str, Any]],
    *,
    tolerance: float = 1e-8,
):
    eid = str(blind_bundle.get("anonymous_election_id", ""))
    packets = blind_bundle.get("packets") or []
    if not eid or len(packets) != 92:
        raise BridgeError(f"blind bundle {eid or '<missing>'} must contain exactly 92 packets")
    env_packets = {
        k.split("|", 1)[1]: v for k, v in environment.items()
        if k.startswith(eid + "|")
    }
    if len(env_packets) != 92:
        raise BridgeError(f"full environment does not contain 92 territories for {eid}")
    pids = sorted(str(p["anonymous_party_id"]) for p in packets[0]["parties"])
    qids = sorted(str(x) for x in next(iter(env_packets.values()))["available_party_ids"])
    if len(pids) != len(qids):
        raise BridgeError(f"party-panel size mismatch for {eid}")
    blind_by_tid = {str(p["anonymous_territory_id"]): p for p in packets}
    tids = sorted(blind_by_tid)
    if set(tids) != set(env_packets):
        raise BridgeError(f"territory namespace mismatch for {eid}")
    psig = {p: [] for p in pids}
    qsig = {q: [] for q in qids}
    for tid in tids:
        bp = {
            str(x["anonymous_party_id"]): float(x["baseline_vote_share"])
            for x in blind_by_tid[tid]["parties"]
        }
        shares = ((env_packets[tid].get("common_territory_card") or {})
                  .get("previous_election_conditional_party_shares") or {})
        if set(bp) != set(pids) or set(map(str, shares)) != set(qids):
            raise BridgeError(f"share panel mismatch at {eid}|{tid}")
        for p in pids:
            psig[p].append(bp[p])
        for q in qids:
            qsig[q].append(float(shares[q]))
    candidates = []
    for p in pids:
        for q in qids:
            candidates.append((max(abs(a-b) for a,b in zip(psig[p], qsig[q])), p, q))
    mapping, errors, usedp, usedq = {}, {}, set(), set()
    for err, p, q in sorted(candidates):
        if p in usedp or q in usedq:
            continue
        mapping[p] = q
        errors[p] = err
        usedp.add(p)
        usedq.add(q)
    if len(mapping) != len(pids):
        raise BridgeError(f"could not build bijective party alignment for {eid}")
    maxerr = max(errors.values(), default=0.0)
    if maxerr > tolerance:
        raise BridgeError(
            f"anonymous party alignment error {maxerr:.3g} exceeds tolerance {tolerance}; refuse to guess"
        )
    return mapping, {
        "method": "BLIND_BASELINE_SIGNATURE_BIJECTION",
        "identity_information_used": False,
        "target_outcomes_used": False,
        "max_abs_error": maxerr,
        "tolerance": tolerance,
        "bijection": True,
    }
