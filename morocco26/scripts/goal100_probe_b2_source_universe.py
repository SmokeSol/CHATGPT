#!/usr/bin/env python3
"""Probe the frozen B2 source universe and close B2-1 only on evidence.

The source universe itself is frozen before this script executes. The script may
only append operational access results. Sources that are WAF-blocked, challenged
or otherwise non-reproducible become REFERENCE_ONLY/INACTIVE and cannot produce
B2 claims. No search snippet is accepted as evidence.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import socket
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
REGISTRY_PATH = G100 / "b2_source_registry.json"
PROBE_PATH = G100 / "b2_source_universe_probe.json"
CERT_PATH = G100 / "b2_source_universe_certificate.json"
GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"
EVENT_DIR = G100 / "fil_ariane_events"
JOURNAL = ROOT / "FIL_ARIANE.md"
EVIDENCE_DIR = G100 / "b2_evidence"
TZ = ZoneInfo("Africa/Casablanca")
MAX_BYTES = 5_000_000


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_SOURCE_PROBE_FAIL: {message}")


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def normalized_host(url: str) -> str:
    host = (urlparse(url).hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


def domain_allowed(final_url: str, allowed_domains: list[str]) -> bool:
    final_host = normalized_host(final_url)
    normalized_allowed = {
        domain[4:] if domain.lower().startswith("www.") else domain.lower()
        for domain in allowed_domains
    }
    return final_host in normalized_allowed


def content_type_base(value: str | None) -> str:
    return (value or "").split(";", 1)[0].strip().lower()


def frozen_universe_payload(registry: dict) -> dict:
    entries = []
    for source in registry["source_entries"]:
        row = copy.deepcopy(source)
        row.pop("operational_state", None)
        row.pop("probe_result", None)
        entries.append(row)
    return {
        "registry_id": registry["registry_id"],
        "protocol_id": registry["protocol_id"],
        "source_universe_frozen_at": registry["source_universe_frozen_at"],
        "in_scope_parties": registry["in_scope_parties"],
        "party_official_source_map": registry["party_official_source_map"],
        "source_entries": entries,
        "query_templates": registry["query_templates"],
        "prohibited_sources": registry["prohibited_sources"],
        "smoke_test_contract": registry["smoke_test_contract"],
        "closure_requirements": registry["closure_requirements"],
        "independence_rule": registry["independence_rule"],
        "archive_rule": registry["archive_rule"],
    }


def count_claim_records() -> int:
    if not EVIDENCE_DIR.exists():
        return 0
    return sum(1 for path in EVIDENCE_DIR.rglob("*.json") if path.is_file())


def fetch_bounded(session: requests.Session, source: dict, contract: dict) -> dict:
    started = datetime.now(TZ)
    probe_url = source["probe_url"]
    result = {
        "source_id": source["source_id"],
        "tier": source["tier"],
        "party_id": source.get("party_id"),
        "independence_cluster": source["independence_cluster"],
        "probe_url": probe_url,
        "retrieval_policy": source["retrieval_policy"],
        "status_code": None,
        "final_url": None,
        "final_domain_allowed": False,
        "content_type": None,
        "bytes_read": 0,
        "content_sha256": None,
        "challenge_marker": None,
        "exception": None,
        "access_class": "FAILED",
        "operational_state": "INACTIVE",
    }
    raw = bytearray()
    try:
        response = session.get(
            probe_url,
            timeout=(10, 35),
            allow_redirects=True,
            stream=True,
        )
        result["status_code"] = int(response.status_code)
        result["final_url"] = response.url
        result["final_domain_allowed"] = domain_allowed(response.url, source["allowed_domains"])
        result["content_type"] = content_type_base(response.headers.get("content-type"))
        for chunk in response.iter_content(chunk_size=65_536):
            if not chunk:
                continue
            remaining = MAX_BYTES - len(raw)
            if remaining <= 0:
                break
            raw.extend(chunk[:remaining])
        result["bytes_read"] = len(raw)
        result["content_sha256"] = hashlib.sha256(raw).hexdigest()
        sample = bytes(raw[:500_000]).decode("utf-8", errors="ignore").lower()
        for marker in contract["challenge_markers"]:
            if marker.lower() in sample:
                result["challenge_marker"] = marker
                break

        active = (
            result["status_code"] in contract["accepted_http_statuses_for_active"]
            and result["final_domain_allowed"]
            and result["bytes_read"] >= contract["minimum_response_bytes"]
            and result["content_type"] in contract["accepted_content_types"]
            and result["challenge_marker"] is None
        )
        reference_allowed = source["retrieval_policy"] in {
            "DIRECT_OR_REFERENCE_ONLY",
            "DIRECT_OR_DOCUMENTED_WAF_REFERENCE_ONLY",
        }
        reference_condition = (
            result["status_code"] in contract["reference_only_http_statuses"]
            or result["challenge_marker"] is not None
            or (
                result["status_code"] == 200
                and (
                    not result["final_domain_allowed"]
                    or result["bytes_read"] < contract["minimum_response_bytes"]
                    or result["content_type"] not in contract["accepted_content_types"]
                )
            )
        )
        if active:
            result["access_class"] = "DIRECT_REPRODUCIBLE"
            result["operational_state"] = "ACTIVE"
        elif reference_allowed and reference_condition:
            result["access_class"] = "REFERENCE_ONLY_NONREPRODUCIBLE"
            result["operational_state"] = "REFERENCE_ONLY"
        else:
            result["access_class"] = "FAILED_INACTIVE"
            result["operational_state"] = "INACTIVE"
    except (requests.RequestException, OSError, socket.timeout) as exc:
        result["exception"] = f"{type(exc).__name__}: {exc}"[:1000]
        if source["retrieval_policy"] in {
            "DIRECT_OR_REFERENCE_ONLY",
            "DIRECT_OR_DOCUMENTED_WAF_REFERENCE_ONLY",
        }:
            result["access_class"] = "REFERENCE_ONLY_REQUEST_FAILURE"
            result["operational_state"] = "REFERENCE_ONLY"
        else:
            result["access_class"] = "FAILED_REQUEST"
            result["operational_state"] = "INACTIVE"
    result["elapsed_seconds"] = round((datetime.now(TZ) - started).total_seconds(), 3)
    return result


def append_failure_event(probe: dict, certificate: dict) -> None:
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    event_id = f"A020F{run_id}"
    event_path = EVENT_DIR / f"{event_id}.json"
    if event_path.exists():
        return
    event = {
        "event_id": event_id,
        "date": probe["probed_at"],
        "title": "Échec du smoke test de l'univers de sources B2",
        "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
        "gate": "B2-1-SOURCE-UNIVERSE-FROZEN",
        "status": "FAIL",
        "source_universe_sha256": probe["source_universe_sha256"],
        "machine_result": certificate,
        "scientific_decision": "Collection remains locked. No source, query template, threshold or claim is changed automatically.",
        "next_action_exact": "Inspect the per-source access classes and version any genuine locator correction without lowering the frozen activity thresholds.",
    }
    dump(event_path, event)
    marker = f"Entrée {event_id} — Échec du smoke test de l’univers de sources B2"
    text = JOURNAL.read_text(encoding="utf-8")
    if marker not in text:
        text += f"""

### {probe['probed_at'][:10]} — {marker}

**Question/gate traité :** `B2-1-SOURCE-UNIVERSE-FROZEN`.

**Hypothèse avant test :** l’allowlist figée doit fournir au moins 2 sources T0 actives, 5 partis T1 actifs, 3 clusters T2 actifs et 10 sources actives au total, sans aucun claim préalable.

**Résultat machine :** `FAIL`. T0 actifs = `{certificate['active_T0_sources']}` ; partis T1 actifs = `{certificate['active_T1_parties']}` ; clusters T2 actifs = `{certificate['active_T2_independence_clusters']}` ; total actif = `{certificate['total_active_sources']}` ; claims préexistants = `{certificate['claim_records_before_pass']}`.

**Décision scientifique :** la collecte reste verrouillée. Aucun seuil n’est abaissé et aucune source inaccessible n’est traitée comme preuve.

**Prochaine action exacte :** analyser `data/goal100/b2_source_universe_probe.json`, puis versionner uniquement les corrections réelles de locator avant un nouveau test.
"""
        JOURNAL.write_text(text, encoding="utf-8")


def apply_pass_transition(registry: dict, probe: dict, certificate: dict) -> None:
    by_id = {row["source_id"]: row for row in probe["sources"]}
    for source in registry["source_entries"]:
        result = by_id[source["source_id"]]
        source["operational_state"] = result["operational_state"]
        source["probe_result"] = {
            "access_class": result["access_class"],
            "status_code": result["status_code"],
            "final_url": result["final_url"],
            "final_domain_allowed": result["final_domain_allowed"],
            "content_type": result["content_type"],
            "bytes_read": result["bytes_read"],
            "content_sha256": result["content_sha256"],
            "challenge_marker": result["challenge_marker"],
            "exception": result["exception"],
        }
    registry["status"] = "FROZEN_COLLECTION_ENABLED_BOUNDED"
    registry["collection_allowed"] = True
    registry["smoke_test"] = {
        "gate": "PASS",
        "probed_at": probe["probed_at"],
        "source_universe_sha256": probe["source_universe_sha256"],
        "certificate_path": "morocco26/data/goal100/b2_source_universe_certificate.json",
        "probe_path": "morocco26/data/goal100/b2_source_universe_probe.json",
        "active_T0_sources": certificate["active_T0_sources"],
        "represented_T1_parties": certificate["represented_T1_parties"],
        "active_T1_parties": certificate["active_T1_parties"],
        "active_T2_independence_clusters": certificate["active_T2_independence_clusters"],
        "total_active_sources": certificate["total_active_sources"],
        "reference_only_sources": certificate["reference_only_sources"],
        "inactive_sources": certificate["inactive_sources"],
        "claim_records_before_pass": certificate["claim_records_before_pass"],
    }
    dump(REGISTRY_PATH, registry)

    gates = load(GATES_PATH)
    gate = next(row for row in gates["gates"] if row["id"] == "B2-1-SOURCE-UNIVERSE-FROZEN")
    gate["status"] = "CLOSED"
    gate["required_artifact"] = "morocco26/data/goal100/b2_source_universe_certificate.json"
    gate["resolved_claim"] = "The pre-collection source/domain/document allowlist and deterministic query templates are frozen; only sources that passed direct smoke access are active for claims, while blocked/challenged routes are explicitly reference-only or inactive."
    gates["as_of"] = probe["probed_at"]
    gates["next_gate"] = "B2-2-IDENTITY-TERRITORY-CROSSWALK"
    dump(GATES_PATH, gates)

    state = load(STATE_PATH)
    state["as_of"] = probe["probed_at"]
    state["phase"] = "B2_SOURCE_UNIVERSE_FROZEN_COLLECTION_ENABLED"
    state["collection"].update({
        "status": "ENABLED_BOUNDED",
        "reason": "B2-1 source universe smoke test PASS; only ACTIVE allowlisted routes may create candidate records.",
        "evidence_records": 0,
        "admissible_records": 0,
        "conflicted_records": 0,
        "evidence_cutoff": None,
        "source_universe_sha256": probe["source_universe_sha256"],
        "active_sources": certificate["total_active_sources"],
        "reference_only_sources": certificate["reference_only_sources"],
        "inactive_sources": certificate["inactive_sources"],
    })
    closed = state["gates"]["closed"]
    if "B2-1-SOURCE-UNIVERSE-FROZEN" not in closed:
        closed.append("B2-1-SOURCE-UNIVERSE-FROZEN")
    state["gates"]["open"] = [
        value for value in state["gates"]["open"]
        if value != "B2-1-SOURCE-UNIVERSE-FROZEN"
    ]
    state["next_action_exact"] = "Build and certify the deterministic party/list/candidate/incumbent/territory identity crosswalk before admitting any predictive feature matrix or mechanical ballot constraint."
    dump(STATE_PATH, state)

    event = {
        "event_id": "A020",
        "date": probe["probed_at"],
        "title": "Gel de l’univers de sources B2",
        "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
        "gate": "B2-1-SOURCE-UNIVERSE-FROZEN",
        "status": "PASS",
        "question": "L'allowlist figée fournit-elle un univers de collecte reproductible suffisant sans utiliser de snippets ni de sources silencieusement inaccessibles ?",
        "pre_test_hypothesis": "PASS si les seuils T0/T1/T2/total sont atteints, si les huit partis sont représentés, si zéro claim précède le test et si chaque source non reproductible est déclassée.",
        "machine_result": certificate,
        "scientific_decision": "B2 collection is enabled only for sources marked ACTIVE. REFERENCE_ONLY and INACTIVE sources cannot create claim records. Predictive coefficients remain exactly zero.",
        "next_action_exact": "Close B2-2 by building the deterministic identity/territory crosswalk, then start structured collection under the frozen source/query universe."
    }
    dump(EVENT_DIR / "A020.json", event)

    marker = "Entrée A020 — Gel de l’univers de sources B2"
    text = JOURNAL.read_text(encoding="utf-8")
    if marker not in text:
        active_ids = [row["source_id"] for row in probe["sources"] if row["operational_state"] == "ACTIVE"]
        reference_ids = [row["source_id"] for row in probe["sources"] if row["operational_state"] == "REFERENCE_ONLY"]
        inactive_ids = [row["source_id"] for row in probe["sources"] if row["operational_state"] == "INACTIVE"]
        text += f"""

### {probe['probed_at'][:10]} — {marker}

**Question/gate traité :** `B2-1-SOURCE-UNIVERSE-FROZEN` — vérifier l’allowlist et les cinq requêtes déterministes avant le premier claim.

**Hypothèse avant test :** au moins 2 T0 actives, 8 partis officiellement représentés dont 5 T1 directement actifs, 3 clusters T2 actifs, 10 sources actives au total et zéro claim préexistant.

**Actions et artefacts :** smoke test HTTP borné sur les 19 routes figées ; SHA-256 du payload de source `{probe['source_universe_sha256']}` ; `b2_source_universe_probe.json` et `b2_source_universe_certificate.json`.

**Résultat machine :** `PASS` — T0 actives `{certificate['active_T0_sources']}`, partis T1 représentés `{certificate['represented_T1_parties']}`, partis T1 actifs `{certificate['active_T1_parties']}`, clusters T2 actifs `{certificate['active_T2_independence_clusters']}`, total actif `{certificate['total_active_sources']}`, reference-only `{certificate['reference_only_sources']}`, inactives `{certificate['inactive_sources']}`, claims avant PASS `{certificate['claim_records_before_pass']}`.

**Sources ACTIVE :** `{active_ids}`.

**Sources REFERENCE_ONLY :** `{reference_ids}`.

**Sources INACTIVE :** `{inactive_ids}`.

**Décision scientifique :** seules les routes `ACTIVE` peuvent produire des records B2. Une route WAF/challenge ne reçoit aucun crédit par snippet. Tous les coefficients prédictifs restent à zéro.

**Prochaine action exacte :** construire et certifier le crosswalk déterministe identité/parti/liste/territoire (`B2-2`) avant l’admission d’une feature ou d’une contrainte mécanique.
"""
        JOURNAL.write_text(text, encoding="utf-8")


def main() -> None:
    registry = load(REGISTRY_PATH)
    if registry["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED":
        require(CERT_PATH.exists() and load(CERT_PATH)["gate"] == "PASS", "enabled source registry lacks PASS certificate")
        print("B2_SOURCE_UNIVERSE_ALREADY_FROZEN")
        return
    require(registry["status"] == "FROZEN_PENDING_SMOKE_TEST", "source registry not in frozen pending-smoke state")
    require(registry["collection_allowed"] is False, "collection enabled before smoke test")
    require(registry["smoke_test"] is None, "pending registry already contains smoke result")

    claim_records = count_claim_records()
    universe_payload = frozen_universe_payload(registry)
    universe_hash = canonical_sha256(universe_payload)
    contract = registry["smoke_test_contract"]
    session = requests.Session()
    session.headers.update({
        "User-Agent": "MOROCCO26-B2-SourceAudit/1.0 (+https://github.com/SmokeSol/CHATGPT)",
        "Accept": "text/html,application/xhtml+xml,application/pdf,application/xml;q=0.9,*/*;q=0.5",
        "Accept-Language": "ar,fr;q=0.9,en;q=0.6",
        "Cache-Control": "no-cache",
    })

    results = [fetch_bounded(session, source, contract) for source in registry["source_entries"]]
    active = [row for row in results if row["operational_state"] == "ACTIVE"]
    active_t0 = [row for row in active if row["tier"] == "T0"]
    represented_t1 = len(registry["party_official_source_map"])
    active_t1_parties = sorted({row["party_id"] for row in active if row["tier"] == "T1" and row.get("party_id")})
    active_t2_clusters = sorted({row["independence_cluster"] for row in active if row["tier"] == "T2"})
    reference_only = [row for row in results if row["operational_state"] == "REFERENCE_ONLY"]
    inactive = [row for row in results if row["operational_state"] == "INACTIVE"]

    checks = {
        "active_T0_threshold": len(active_t0) >= contract["minimum_active_T0_sources"],
        "represented_T1_threshold": represented_t1 >= contract["minimum_represented_T1_parties"],
        "active_T1_threshold": len(active_t1_parties) >= contract["minimum_active_T1_parties"],
        "active_T2_cluster_threshold": len(active_t2_clusters) >= contract["minimum_active_T2_independence_clusters"],
        "total_active_threshold": len(active) >= contract["minimum_total_active_sources"],
        "zero_claim_records_before_pass": claim_records == 0,
        "source_entry_probe_coverage": len(results) == len(registry["source_entries"]),
    }
    gate_pass = all(checks.values())
    probed_at = now_local()
    probe = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-B2-SOURCE-UNIVERSE-PROBE-V1",
        "probed_at": probed_at,
        "gate": "PASS" if gate_pass else "FAIL",
        "source_universe_sha256": universe_hash,
        "source_count": len(registry["source_entries"]),
        "query_template_count": len(registry["query_templates"]),
        "sources": results,
        "checks": checks,
    }
    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-SOURCE-UNIVERSE-CERTIFICATE-V1",
        "gate": "PASS" if gate_pass else "FAIL",
        "certified_at": probed_at,
        "protocol_id": registry["protocol_id"],
        "source_universe_sha256": universe_hash,
        "source_count": len(results),
        "query_template_count": len(registry["query_templates"]),
        "active_T0_sources": len(active_t0),
        "active_T0_source_ids": sorted(row["source_id"] for row in active_t0),
        "represented_T1_parties": represented_t1,
        "active_T1_parties": len(active_t1_parties),
        "active_T1_party_ids": active_t1_parties,
        "active_T2_independence_clusters": len(active_t2_clusters),
        "active_T2_cluster_ids": active_t2_clusters,
        "total_active_sources": len(active),
        "active_source_ids": sorted(row["source_id"] for row in active),
        "reference_only_sources": len(reference_only),
        "reference_only_source_ids": sorted(row["source_id"] for row in reference_only),
        "inactive_sources": len(inactive),
        "inactive_source_ids": sorted(row["source_id"] for row in inactive),
        "claim_records_before_pass": claim_records,
        "checks": checks,
        "collection_rule": "Only ACTIVE sources may create B2 claim records. REFERENCE_ONLY and INACTIVE routes remain in the frozen universe but have zero evidentiary authority until a later versioned access correction.",
    }
    dump(PROBE_PATH, probe)
    dump(CERT_PATH, certificate)

    if gate_pass:
        apply_pass_transition(registry, probe, certificate)
        print("B2_SOURCE_UNIVERSE_PASS")
    else:
        append_failure_event(probe, certificate)
        print("B2_SOURCE_UNIVERSE_FAIL")
    print(json.dumps(certificate, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
