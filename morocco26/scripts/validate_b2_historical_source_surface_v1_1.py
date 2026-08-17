#!/usr/bin/env python3
"""Enforce the V1.1 historical source-surface amendment contract.

Adversarial about the ways an amendment could quietly become a scientific
change rather than an acquisition-surface change: a widened feature set, a
softened threshold, a source admitted on outcome evidence, a root that is
neither in provenance nor an archive mirror, acquisition that ran before the
freeze, or an exhaustion claim resting on a truncated scan.

This validator is new, not a successor. The stale `validate_b2_protocol` and
`validate_b2_source_universe` remain untouched: they are evidence of the gate
state at which they were written.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"

SURFACE_PATH = G100 / "historical_source_surface_v1_1.json"
PROTOCOL_PATH = G100 / "historical_acquisition_protocol_v1_1.json"
CERTIFICATE_PATH = G100 / "historical_source_surface_certificate.json"
REGISTRY_V1_PATH = G100 / "b2_source_registry.json"
DICTIONARY_PATH = G100 / "b2_feature_dictionary_v1.json"
ACQ_MANIFEST_PATH = G100 / "b2_historical_v1_1_acquisition_manifest.json"
OUTCOME_PATH = G100 / "b2_v1_1_outcome_certificate.json"
STATE_PATH = G100 / "b2_current_state.json"

ELIGIBILITY_TESTS = {
    "ROOT_ALREADY_IN_REPOSITORY_PROVENANCE",
    "ARCHIVE_MIRROR_OF_DOMAIN_ALREADY_IN_FROZEN_REGISTRY",
}
EXHAUSTION_STATE = "B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_V1_1_SURFACE_VALIDATION_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_V1_1_SURFACE_VALIDATION_FAIL: {message}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_integrity(surface: dict, protocol: dict, certificate: dict) -> None:
    payload = {k: v for k, v in surface.items() if k != "canonical_surface_sha256"}
    require(canonical_sha256(payload) == surface["canonical_surface_sha256"], "surface hash drift")
    payload = {k: v for k, v in protocol.items() if k != "canonical_protocol_sha256"}
    require(canonical_sha256(payload) == protocol["canonical_protocol_sha256"], "protocol hash drift")
    payload = {k: v for k, v in certificate.items() if k != "canonical_certificate_sha256"}
    require(canonical_sha256(payload) == certificate["canonical_certificate_sha256"], "certificate hash drift")

    require(certificate["gate"] == "PASS", "source-surface certificate is not PASS")
    require(certificate["source_surface_sha256"] == surface["canonical_surface_sha256"],
            "certificate does not carry the frozen surface hash")
    require(certificate["acquisition_protocol_sha256"] == protocol["canonical_protocol_sha256"],
            "certificate does not carry the frozen protocol hash")
    require(certificate["frozen_before_acquisition"] is True, "amendment was not declared pre-acquisition")
    require(surface["status"] == "FROZEN_PRE_ACQUISITION", "surface is not frozen")


def validate_scope(surface: dict) -> None:
    require(surface["amendment_scope"] == "ACQUISITION_SURFACE_DEFINITIONS_ONLY",
            "amendment scope exceeds acquisition-surface definitions")

    registry = load(REGISTRY_V1_PATH)
    require(registry["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED", "V1 registry status changed")
    require(surface["amends"] == registry["registry_id"], "amendment does not reference V1 registry")

    dictionary = load(DICTIONARY_PATH)
    contract = dictionary["historical_calibration_contract"]
    require(dictionary["status"] == "FROZEN_COEFFICIENTS_ZERO_PENDING_CALIBRATION",
            "feature dictionary is no longer frozen")
    require(contract["core_panel_minimum_coverage_each_transition"] == 0.8, "coverage threshold changed")
    require(contract["binary_feature_minimum_positive_instances"] == 30, "support threshold changed")
    require(contract["fit_transition"] == "2011_TO_2016", "fit transition changed")
    require(contract["validation_transition"] == "2016_TO_2021", "validation transition changed")

    for entry in surface["immutable_under_this_amendment"]:
        require(isinstance(entry, str) and entry, "immutability list is malformed")


def validate_anti_overfit(surface: dict) -> None:
    declaration = surface["anti_overfit_declaration"]
    require(declaration["outcome_signals_consulted"] == [], "an outcome signal was consulted")
    require(declaration["residual_errors_consulted"] is False, "residual errors were consulted")
    require(declaration["party_results_consulted"] is False, "party results were consulted")
    require(declaration["feature_performance_consulted"] is False, "feature performance was consulted")
    require(declaration["selection_is_outcome_independent"] is True, "selection is not outcome-independent")
    require(declaration["roots_frozen_before_content_inspection"] is True,
            "roots were not frozen before content inspection")


def validate_sources(surface: dict) -> None:
    registry_domains = {
        domain
        for entry in load(REGISTRY_V1_PATH)["source_entries"]
        for domain in entry.get("allowed_domains", [])
    }
    require(bool(surface["sources"]), "amendment declares no source")

    for source in surface["sources"]:
        source_id = source["source_id"]
        basis = source["eligibility_basis"]
        require(basis in ELIGIBILITY_TESTS, f"{source_id} uses an undeclared eligibility test: {basis}")

        if basis == "ROOT_ALREADY_IN_REPOSITORY_PROVENANCE":
            evidence = source.get("provenance_evidence") or []
            require(bool(evidence), f"{source_id} claims provenance without citing an artifact")
            for path in evidence:
                require((REPO / path).exists(), f"{source_id} cites a missing provenance artifact: {path}")
        else:
            mirrored = set(source.get("mirrored_domains") or [])
            require(bool(mirrored), f"{source_id} is an archive mirror of nothing")
            stray = sorted(mirrored - registry_domains)
            require(not stray, f"{source_id} mirrors domains outside the frozen registry: {stray}")

        method = source["deterministic_enumeration_method"]
        require("selection_rule" in method, f"{source_id} declares no selection rule")
        require(bool(source.get("cutoff_rule")), f"{source_id} declares no cutoff rule")
        require(bool(source.get("years")), f"{source_id} declares no years")

    require(surface["extraction_rule"]["llm_used"] is False, "amendment permits LLM extraction")
    require(surface["extraction_rule"]["semantic_extraction_forbidden"] is True,
            "amendment permits semantic extraction")


def validate_time_contract(surface: dict) -> None:
    contract = surface["time_contract"]
    require(contract["failure_state"] == "UNKNOWN_AT_CUTOFF", "cutoff failure state drift")
    require(bool(contract["election_cutoffs"]), "no election cutoffs declared")
    for year, cutoff in contract["election_cutoffs"].items():
        require(cutoff.startswith(str(year)), f"cutoff for {year} does not fall in {year}")


def validate_acquisition_ordering(surface: dict) -> None:
    """Acquisition must have run against the frozen surface, never before it."""
    if not ACQ_MANIFEST_PATH.exists():
        return
    manifest = load(ACQ_MANIFEST_PATH)
    require(manifest["source_surface_sha256"] == surface["canonical_surface_sha256"],
            "acquisition ran against a different surface hash")
    require(manifest["run_at"] >= surface["frozen_at"], "acquisition predates the surface freeze")
    require(manifest["determinism"]["llm_used"] is False, "acquisition declares LLM use")
    require(manifest["determinism"]["semantic_selection"] is False, "acquisition declares semantic selection")


def validate_outcome() -> None:
    """An exhaustion claim may not rest on a truncated or blocked enumeration."""
    if not OUTCOME_PATH.exists():
        return
    outcome = load(OUTCOME_PATH)
    results = outcome["surface_results"]
    if outcome["termination_state"] == EXHAUSTION_STATE:
        for row in results:
            require(row["exhaustion_claimable"],
                    f"exhaustion claimed while {row['source_id']} was truncated or unreachable")
    require(outcome["reserved_for_e_collect"]["e_collect_executed"] is False, "E_collect was executed")
    require(outcome["b2_3"]["threshold_unchanged"] is True, "B2-3 threshold was weakened")
    require(outcome["invariants"]["coefficients_all_zero"] is True, "a predictive coefficient moved")

    state = load(STATE_PATH)
    require(state["anti_drift"]["agentic_experiment_locked"] is True, "agentic layer was unlocked")
    require(state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION",
            "state moved a predictive coefficient")


def main() -> None:
    surface = load(SURFACE_PATH)
    protocol = load(PROTOCOL_PATH)
    certificate = load(CERTIFICATE_PATH)

    validate_integrity(surface, protocol, certificate)
    validate_scope(surface)
    validate_anti_overfit(surface)
    validate_sources(surface)
    validate_time_contract(surface)
    validate_acquisition_ordering(surface)
    validate_outcome()

    print("B2_V1_1_SOURCE_SURFACE_VALIDATION_PASS")
    print(f"amendment={surface['amendment_id']}")
    print(f"surface_sha256={surface['canonical_surface_sha256']}")
    print(f"sources={len(surface['sources'])} scope={surface['amendment_scope']}")
    print(f"years_expressible={sorted({y for s in surface['sources'] for y in s['years']})}")
    print("thresholds=0.8/30 unchanged; feature dictionary frozen; V1 registry unedited")
    if OUTCOME_PATH.exists():
        outcome = load(OUTCOME_PATH)
        print(f"termination_state={outcome['termination_state']}")


if __name__ == "__main__":
    main()
