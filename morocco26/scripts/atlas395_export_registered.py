#!/usr/bin/env python3
"""Export the latest registered MOROCCO//26 snapshot into read-only Atlas views.

F0 may be a registered identity counterfactual that references the immutable
F-1 distribution instead of duplicating its 5.2M contest draws. This adapter
materializes that reference only in memory for the reader export, preserves the
F0 artifact hash as the scientific provenance anchor, and never writes into the
scientific tree outside morocco26/web/data/.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import atlas395_export as base


def load(path: Path, optional: bool = False):
    return base.load_json(path, optional=optional)


def dump(path: Path, value) -> None:
    base.dump_json(path, value)


def materialized_forecast(snapshot: str, raw: dict) -> dict:
    counter = raw.get("counterfactual_distribution") or {}
    if snapshot != "F0" or counter.get("distribution_equivalence") != "EXACT":
        return raw
    parent = raw.get("parent_distribution") or {}
    parent_id = str(parent.get("snapshot_id") or "F-1")
    parent_path = base.GOAL100 / "forecasts" / parent_id / "forecast.json"
    parent_forecast = base.load_json(parent_path)
    merged = dict(parent_forecast)
    merged.update(raw)
    for key in ("local_92", "regional_12", "national_395", "party_buckets"):
        if key not in raw and key in parent_forecast:
            merged[key] = parent_forecast[key]
    merged["draws"] = raw.get("monte_carlo_draws") or parent_forecast.get("draws") or 50000
    return merged


def postprocess_f0(snapshot: str, forecast_path: Path, manifest_path: Path) -> None:
    if snapshot != "F0":
        return
    raw = base.load_json(forecast_path)
    counter = raw.get("counterfactual_distribution") or {}
    if counter.get("distribution_equivalence") != "EXACT":
        return

    manifest = base.load_json(manifest_path)
    parent = raw.get("parent_distribution") or {}
    parent_id = str(parent.get("snapshot_id") or "F-1")
    parent_forecast_path = base.GOAL100 / "forecasts" / parent_id / "forecast.json"
    parent_manifest_path = base.GOAL100 / "forecasts" / parent_id / "snapshot_manifest.json"
    parent_manifest = base.load_json(parent_manifest_path)
    parent_sha = base.sha256_file(parent_forecast_path)
    f0_sha = base.sha256_file(forecast_path)

    gate_registry = base.load_json(base.GOAL100 / "b2_gate_registry.json", optional=True)
    agentic = {str(row.get("id")): row for row in gate_registry.get("agentic_gates", [])}

    current_path = base.WEB_DATA / "current_snapshot.json"
    current = base.load_json(current_path)
    current["distribution_sha256"] = counter.get("distribution_sha256")
    current["distribution_equivalence_to_parent"] = "EXACT"
    current["timeline"] = [
        {
            "id": parent_id,
            "status": "FROZEN",
            "created_at": parent_manifest.get("created_at"),
            "class": parent_manifest.get("snapshot_class"),
            "sha256": parent_sha,
        },
        {
            "id": "F0",
            "status": "FROZEN",
            "created_at": manifest.get("created_at"),
            "class": manifest.get("snapshot_class"),
            "sha256": f0_sha,
            "distribution_equivalence_to_parent": "EXACT",
        },
        {
            "id": "E_collect",
            "status": (agentic.get("E-COLLECT-PREREGISTERED") or {}).get("status", "OPEN"),
        },
        {
            "id": "E_reason",
            "status": (agentic.get("E-REASON-PREREGISTERED") or {}).get("status", "LOCKED"),
        },
        {
            "id": "E_full",
            "status": (agentic.get("E-FULL-PREREGISTERED") or {}).get("status", "LOCKED"),
        },
    ]
    dump(current_path, current)

    evidence_path = base.WEB_DATA / "evidence_index.json"
    evidence = base.load_json(evidence_path)
    evidence["forecast_snapshot"] = "F0"
    evidence["forecast_change"] = "NONE"
    evidence["forecast_change_reason"] = (
        "F0 is the registered B2 fail-closed identity counterfactual: zero admissible mechanical constraints, "
        "zero promoted predictive features, and exact distribution equivalence to F-1."
    )
    dump(evidence_path, evidence)

    cards_path = base.WEB_DATA / "constituency_cards.json"
    cards = base.load_json(cards_path)
    for card in cards.get("constituencies", []):
        uncertainty = card.get("uncertainty") or {}
        uncertainty["note"] = (
            "Relative uncertainty indicator from the registered F0 distribution, which is exactly equivalent to F-1."
        )
        evidence_2026 = card.get("evidence_2026") or {}
        evidence_2026["model_state"] = "F0_FAIL_CLOSED_IDENTITY"
        evidence_2026["forecast_impact"] = "NONE_EXACT_PARENT_EQUIVALENCE"
        card["evidence_2026"] = evidence_2026
    dump(cards_path, cards)

    parties_path = base.WEB_DATA / "party_cards.json"
    parties = base.load_json(parties_path)
    for party in parties.get("parties", []):
        if party.get("p_first_status") == "NOT_PUBLISHED_IN_F_MINUS_1":
            party["p_first_status"] = "NOT_PUBLISHED_IN_REGISTERED_F0_DISTRIBUTION"
    dump(parties_path, parties)

    methodology_path = base.WEB_DATA / "methodology_state.json"
    methodology = base.load_json(methodology_path)
    methodology.setdefault("model", {})["national_projection_origin"] = (
        "Registered F0 identity counterfactual over the immutable F-1 distribution; B2 admitted no mechanical "
        "constraint and promoted no predictive feature."
    )
    certification = methodology.setdefault("certification", {})
    certification["distribution_sha256"] = counter.get("distribution_sha256")
    certification["distribution_equivalence_to_parent"] = "EXACT"
    certification["parent_snapshot"] = parent_id
    certification["parent_forecast_sha256"] = parent_sha
    certification["b2_freeze_certificate_sha256"] = (raw.get("b2_application") or {}).get("freeze_certificate", {}).get("sha256")
    dump(methodology_path, methodology)

    change_path = base.WEB_DATA / "change_log.json"
    change = base.load_json(change_path)
    old_entries = [row for row in change.get("entries", []) if row.get("type") != "MODEL_SNAPSHOT"]
    change["entries"] = [
        {
            "at": parent_manifest.get("created_at"),
            "type": "MODEL_SNAPSHOT",
            "snapshot": parent_id,
            "evidence": "STRUCTURAL_ONLY",
            "model_change": "REGISTERED_IMMUTABLE_PARENT",
        },
        {
            "at": manifest.get("created_at"),
            "type": "MODEL_SNAPSHOT",
            "snapshot": "F0",
            "evidence": "B2_FAIL_CLOSED",
            "model_change": "EXACT_IDENTITY_TO_F_MINUS_1",
        },
        *old_entries,
    ]
    dump(change_path, change)

    public_manifest_path = base.WEB_DATA / "snapshot_manifest.json"
    public_manifest = base.load_json(public_manifest_path)
    for name in list((public_manifest.get("outputs") or {}).keys()):
        path = base.WEB_DATA / name
        if path.exists():
            public_manifest["outputs"][name] = base.sha256_file(path)
    dump(public_manifest_path, public_manifest)


def build(snapshot: str) -> None:
    forecast_path = base.GOAL100 / "forecasts" / snapshot / "forecast.json"
    manifest_path = base.GOAL100 / "forecasts" / snapshot / "snapshot_manifest.json"
    raw_forecast = base.load_json(forecast_path)
    materialized = materialized_forecast(snapshot, raw_forecast)

    original_load = base.load_json

    def adapted_load(path: Path, optional: bool = False):
        if Path(path) == forecast_path:
            return materialized
        return original_load(path, optional=optional)

    base.load_json = adapted_load
    try:
        base.build(snapshot)
    finally:
        base.load_json = original_load

    postprocess_f0(snapshot, forecast_path, manifest_path)
    print(f"ATLAS395_REGISTERED_EXPORT_OK snapshot={snapshot}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--snapshot", default="F-1")
    args = parser.parse_args()
    build(args.snapshot)


if __name__ == "__main__":
    main()
