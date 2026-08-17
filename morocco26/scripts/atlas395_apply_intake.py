#!/usr/bin/env python3
"""Apply Atlas Intake detections to the reader evidence view.

This layer is product-only. It enforces the Atlas source policy, removes
unauthorized sources from the reader surface, and is incapable of changing a
forecast value.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_policy(policy: dict) -> set[str]:
    allowed = {str(x) for x in policy.get("authorized_source_ids") or []}
    media = {str(x) for x in policy.get("authorized_media_source_ids") or []}
    if policy.get("default_decision") != "DENY":
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: default decision must be DENY")
    if media != {"T2_MEDIAS24"}:
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: Médias24 must be the sole authorized media source")
    if any(source.startswith("T2_") and source not in media for source in allowed):
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: unauthorized media in reader allowlist")
    return allowed


def role(source_id: str) -> str:
    if source_id.startswith("T0_"):
        return "SOURCE_INSTITUTIONNELLE_OFFICIELLE"
    if source_id.startswith("T1_"):
        return "PUBLICATION_OFFICIELLE_D_UN_PARTI_DECLARATION_INTERESSEE"
    if source_id == "T2_MEDIAS24":
        return "MEDIA_AUTORISE_VEILLE_ET_CORROBORATION_UNIQUEMENT"
    return "SOURCE_NON_AUTORISEE"


def source_counts(sources: list[dict]) -> dict:
    totals = {"ACQUIRED": 0, "BLOCKED_SOURCE": 0, "FETCH_ERROR": 0}
    for source in sources:
        for state, count in (source.get("states") or {}).items():
            if state in totals:
                totals[state] += int(count or 0)
    return totals


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--intake", required=True)
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--policy", required=True)
    parser.add_argument("--public-manifest")
    args = parser.parse_args()

    intake_path = Path(args.intake)
    evidence_path = Path(args.evidence)
    policy = load(Path(args.policy))
    allowed = validate_policy(policy)
    evidence = load(evidence_path)
    intake = load(intake_path) if intake_path.exists() else {"detections": []}

    intake_allowed = set(intake.get("authorized_source_ids") or allowed)
    if intake_allowed != allowed:
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: intake and reader policies disagree")
    if any(detection.get("source_id") not in allowed for detection in intake.get("detections", [])):
        raise SystemExit("ATLAS395_SOURCE_POLICY_FAIL: intake contains a disallowed source")

    original_sources = list(evidence.get("sources") or [])
    filtered_sources = [source for source in original_sources if source.get("source") in allowed]
    forbidden_source_ids = sorted({str(source.get("source")) for source in original_sources if source.get("source") not in allowed})

    original_events = list(evidence.get("events") or [])
    filtered_events = [
        event for event in original_events
        if not event.get("source") or event.get("source") in allowed
    ]
    removed_event_ids = sorted({str(event.get("id")) for event in original_events if event not in filtered_events and event.get("id")})

    seen = {event.get("id") for event in filtered_events}
    added = 0
    for detection in intake.get("detections", []):
        if detection.get("id") in seen:
            continue
        source_id = str(detection.get("source_id"))
        filtered_events.append({
            "id": detection.get("id"),
            "source": source_id,
            "source_role": role(source_id),
            "status": "DETECTED_BY_DAILY_WATCH",
            "verification_status": "PENDING",
            "summary": detection.get("title") or "Information électorale détectée dans la veille quotidienne",
            "reason": (
                "Signal repéré automatiquement dans une source autorisée. Il reste hors du calcul tant qu'il n'a pas "
                "satisfait les critères de validation scientifique et de corroboration applicables."
            ),
            "forecast_impact": "NONE",
            "url": detection.get("url"),
            "retrieved_at": detection.get("retrieved_at"),
            "content_sha256": detection.get("content_sha256"),
            "intake_relevance_score": detection.get("relevance_score"),
            "intake_status": detection.get("status"),
        })
        seen.add(detection.get("id"))
        added += 1

    counts = source_counts(filtered_sources)
    evidence["sources"] = filtered_sources
    evidence["events"] = filtered_events
    evidence["source_policy"] = {
        "policy_id": policy.get("policy_id"),
        "policy_sha256": canonical_sha256(policy),
        "effective_date": policy.get("effective_date"),
        "default_decision": "DENY",
        "authorized_source_ids": sorted(allowed),
        "authorized_media_source_ids": ["T2_MEDIAS24"],
        "sole_authorized_media_label": "Médias24",
        "scientific_registry_unchanged": True,
        "removed_from_reader_source_ids": forbidden_source_ids,
        "removed_from_reader_event_ids": removed_event_ids,
        "reader_rule_fr": "Sources institutionnelles et officielles uniquement ; Médias24 est le seul média autorisé.",
    }
    evidence["reader_scope"] = {
        "authorized_sources": len(filtered_sources),
        "authorized_institutional_sources": sum(1 for source in filtered_sources if str(source.get("source", "")).startswith("T0_")),
        "authorized_official_party_sources": sum(1 for source in filtered_sources if str(source.get("source", "")).startswith("T1_")),
        "authorized_media_sources": sum(1 for source in filtered_sources if source.get("source") == "T2_MEDIAS24"),
        "documents_acquired": counts["ACQUIRED"],
        "documents_blocked": counts["BLOCKED_SOURCE"],
        "documents_error": counts["FETCH_ERROR"],
        "documented_signals": len(filtered_events),
    }
    evidence["daily_watch"] = {
        "run_id": intake.get("run_id"),
        "run_at": intake.get("run_at"),
        "source_policy_id": intake.get("source_policy_id") or policy.get("policy_id"),
        "authorized_sources_scanned": intake.get("authorized_sources_scanned", 0),
        "detections": intake.get("detection_count", 0),
        "probe_count": intake.get("probe_count", 0),
        "probe_failures": intake.get("probe_failures", 0),
        "contract": "VEILLE_PRODUIT_SEULEMENT_AUCUNE_INCIDENCE_AUTOMATIQUE_SUR_LA_PROJECTION",
    }
    evidence["forecast_change"] = "NONE" if evidence.get("forecast_change") == "NONE" else evidence.get("forecast_change")
    dump(evidence_path, evidence)
    if args.public_manifest:
        manifest_path = Path(args.public_manifest)
        manifest = load(manifest_path)
        manifest.setdefault("outputs", {})[evidence_path.name] = hashlib.sha256(evidence_path.read_bytes()).hexdigest()
        manifest["source_policy"] = {
            "policy_id": policy.get("policy_id"),
            "policy_sha256": canonical_sha256(policy),
            "reader_evidence_file": evidence_path.name,
        }
        dump(manifest_path, manifest)
    print(
        "ATLAS395_INTAKE_MERGE_OK "
        f"policy={policy.get('policy_id')} allowed_sources={len(filtered_sources)} "
        f"removed_sources={len(forbidden_source_ids)} added_events={added} total_events={len(filtered_events)}"
    )


if __name__ == "__main__":
    main()
