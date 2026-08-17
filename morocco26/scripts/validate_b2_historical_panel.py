#!/usr/bin/env python3
"""Enforce the B2-3 historical feature panel contract.

The validator is adversarial about the failure modes that would quietly buy
coverage: promoting a diagnostic into a feature, converting an absence into a
zero, using the 2021 outcome as a roster, closing the gate while the coverage
minimum is unmet, or moving a coefficient off zero before B2-6.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"

PROTOCOL_PATH = G100 / "b2_protocol_v1.json"
DICTIONARY_PATH = G100 / "b2_feature_dictionary_v1.json"
IDENTITY_CERTIFICATE_PATH = G100 / "b2_identity_territory_certificate.json"
PANEL_PATH = G100 / "b2_historical_panel.json"
CERTIFICATE_PATH = G100 / "b2_historical_panel_certificate.json"
GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"
EVIDENCE_DIR = G100 / "b2_evidence"

VOLATILE_INPUT_FIELDS = {"generated_at", "certified_at", "canonical_artifact_sha256"}
GATE_ID = "B2-3-HISTORICAL-FEATURE-PANEL"
FROZEN_TRANSITIONS = ["2011_TO_2016", "2016_TO_2021"]


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_HISTORICAL_PANEL_VALIDATION_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_HISTORICAL_PANEL_VALIDATION_FAIL: {message}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def count_claim_records() -> int:
    if not EVIDENCE_DIR.exists():
        return 0
    return sum(1 for path in EVIDENCE_DIR.rglob("*.json") if path.is_file())


def validate_parents(panel: dict, certificate: dict) -> dict:
    protocol = load(PROTOCOL_PATH)
    dictionary = load(DICTIONARY_PATH)
    identity = load(IDENTITY_CERTIFICATE_PATH)

    require(protocol["status"] == "FROZEN_PRE_COLLECTION", "B2 protocol is no longer frozen pre-collection")
    require(
        protocol["scientific_role"]["agentic_status"] == "PROHIBITED_AND_LOCKED",
        "agentic status is no longer locked",
    )
    require(
        dictionary["status"] == "FROZEN_COEFFICIENTS_ZERO_PENDING_CALIBRATION",
        "feature dictionary is no longer frozen",
    )
    require(identity["gate"] == "PASS", "parent identity/territory gate is not PASS")
    require(panel["protocol_id"] == protocol["protocol_id"], "panel is not linked to the frozen protocol")
    require(panel["dictionary_id"] == dictionary["dictionary_id"], "panel is not linked to the frozen dictionary")
    require(certificate["protocol_id"] == protocol["protocol_id"], "certificate protocol linkage drift")
    require(certificate["gate_id"] == GATE_ID, "certificate gate ID drift")
    return dictionary


def validate_integrity(panel: dict, certificate: dict) -> None:
    payload = dict(panel)
    recorded = payload.pop("canonical_panel_sha256", None)
    require(recorded is not None, "panel is missing its canonical hash")
    require(recorded == canonical_sha256(payload), "panel canonical hash drift")
    require(certificate["panel_sha256"] == recorded, "certificate does not carry the panel hash")
    require(certificate["panel_path"] == "morocco26/data/goal100/b2_historical_panel.json", "panel path drift")
    require("\\" not in json.dumps(panel["input_hashes"]), "panel input paths are not POSIX")
    require(
        panel["input_hash_method"] == "CANONICAL_JSON_SHA256",
        "input hashes must be checkout-independent; raw-byte digests break under CRLF checkouts",
    )

    for name, entry in panel["input_hashes"].items():
        path = REPO / entry["path"]
        require(path.exists(), f"declared input is missing: {entry['path']}")
        content = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(content, dict):
            content = {k: v for k, v in content.items() if k not in VOLATILE_INPUT_FIELDS}
        recomputed = canonical_sha256(content)
        require(recomputed == entry["canonical_json_sha256"], f"input content drift for {name}")


def validate_determinism(panel: dict) -> None:
    determinism = panel["determinism"]
    require(determinism["llm_used"] is False, "panel declares LLM use")
    require(determinism["network_access"] is False, "panel declares network access")
    require(determinism["source_discovery"] is False, "panel declares autonomous source discovery")

    leakage = panel["leakage_controls"]
    for flag in (
        "target_outcome_used_in_feature_creation",
        "elected_roster_used_as_candidate_roster",
        "elected_roster_used_for_own_cycle_incumbency",
        "absence_converted_to_zero",
    ):
        require(leakage[flag] is False, f"leakage control violated: {flag}")


def validate_contract(panel: dict, dictionary: dict) -> tuple[float, int]:
    frozen = dictionary["historical_calibration_contract"]
    require(panel["calibration_contract"] == frozen, "panel restates a modified calibration contract")

    observed = [row["transition_id"] for row in panel["transitions"]]
    require(observed == FROZEN_TRANSITIONS, f"transition set drift: {observed}")

    minimum_coverage = float(frozen["core_panel_minimum_coverage_each_transition"])
    minimum_support = int(frozen["binary_feature_minimum_positive_instances"])

    declared_features = {row["feature_id"] for row in dictionary["features"]}
    for transition in panel["transitions"]:
        panel_features = {row["feature_id"] for row in transition["features"]}
        require(
            panel_features == declared_features,
            f"{transition['transition_id']} feature set differs from the frozen dictionary",
        )
        for row in transition["features"]:
            require(row["na_policy"] == "MISSING_IS_NA_NEVER_ZERO", f"{row['feature_id']} NA policy drift")
            if not row["identifiable"]:
                require(
                    row["missing_inputs"],
                    f"{row['feature_id']} is not identifiable but publishes no blocking input",
                )
                require(
                    row["positive_instances"] == 0 and row["coverage_fraction"] == 0.0,
                    f"{row['feature_id']} is not identifiable yet reports coverage or support",
                )
            if row["support_meets_minimum"]:
                require(
                    row["positive_instances"] >= minimum_support,
                    f"{row['feature_id']} claims support below the frozen minimum",
                )

        # Recompute the headline coverage from the feature rows so a transition
        # cannot advertise coverage its own features do not support.
        predictive = [
            row for row in transition["features"]
            if row["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION" and row["identifiable"]
        ]
        mechanical = [
            row for row in transition["features"]
            if row["forecast_role"] == "MECHANICAL" and row["identifiable"]
        ]
        expected_core = min((row["coverage_fraction"] for row in predictive), default=0.0)
        expected_mechanical = min((row["coverage_fraction"] for row in mechanical), default=0.0)
        require(
            abs(transition["core_predictive_panel_coverage"] - expected_core) < 1e-9,
            f"{transition['transition_id']} core predictive coverage is not derived from its features",
        )
        require(
            abs(transition["mechanical_panel_coverage"] - expected_mechanical) < 1e-9,
            f"{transition['transition_id']} mechanical coverage is not derived from its features",
        )
        require(
            transition["core_predictive_panel_meets_minimum"] == (expected_core >= minimum_coverage),
            f"{transition['transition_id']} coverage verdict contradicts its own features",
        )
        require(
            transition["counts"]["features_identifiable"]
            == sum(row["identifiable"] for row in transition["features"]),
            f"{transition['transition_id']} identifiable count drift",
        )
    return minimum_coverage, minimum_support


def validate_diagnostics(panel: dict, dictionary: dict) -> None:
    declared_features = {row["feature_id"] for row in dictionary["features"]}
    for row in panel["observed_diagnostics"]:
        require(
            row["satisfies_feature"] is None,
            f"diagnostic {row['diagnostic_id']} claims to satisfy a frozen feature",
        )
        require(row["diagnostic_id"] not in declared_features, "a diagnostic reuses a frozen feature ID")

    diagnostic_ids = {row["diagnostic_id"] for row in panel["observed_diagnostics"]}
    matrix = panel["matrix"]
    require(matrix["storage"] == "DERIVED_NOT_DUPLICATED", "matrix storage contract drift")
    require(
        matrix["row_count"] == matrix["feature_cell_count"] + matrix["diagnostic_cell_count"],
        "matrix cell counts do not sum to the row count",
    )
    require(
        matrix["derivation"]["absence_rule"] == "unobserved pairs are NA and are never emitted as 0",
        "matrix absence rule drift",
    )

    # Rebuild the cells from the committed upstream artifact and confirm the
    # recorded hash. A stored copy is never trusted on its own.
    crosswalk = load(REPO / matrix["derivation"]["source_artifact"])
    rebuilt = []
    for transition in panel["transitions"]:
        cells = sorted(
            (
                {
                    "transition_id": transition["transition_id"],
                    "diagnostic_id": "OBSERVED_POSITIVE_LOCAL_LIST_PRESENCE",
                    "feature_id": None,
                    "territory_id": row["territory_id"],
                    "party_code": row["party_code"],
                    "value": 1,
                }
                for row in crosswalk[matrix["derivation"]["source_field"]]
                if row["scope"] == "local" and int(row["year"]) == transition["target_year"]
            ),
            key=lambda item: (item["territory_id"], item["party_code"]),
        )
        rebuilt.extend(cells)

    require(len(rebuilt) == matrix["row_count"], "rebuilt matrix row count differs from the panel")
    require(
        canonical_sha256(rebuilt) == matrix["canonical_rows_sha256"],
        "rebuilt matrix hash differs from the panel; the derivation is not reproducible",
    )
    require(all(row["value"] != 0 for row in rebuilt), "a matrix cell encodes an absence as zero")
    for row in rebuilt:
        require(row["diagnostic_id"] in diagnostic_ids, "matrix cell references an unpublished diagnostic")
        require(row["feature_id"] is None, "a diagnostic cell claims a frozen feature ID")

    declared_diagnostic_total = sum(row["positive_instances"] for row in panel["observed_diagnostics"])
    require(
        declared_diagnostic_total == matrix["diagnostic_cell_count"],
        "published diagnostic instance counts do not match the matrix",
    )


def validate_gate_consistency(panel: dict, certificate: dict, minimum_coverage: float) -> None:
    require(panel["gate"] == certificate["gate"], "panel and certificate disagree on the gate result")

    expected_predictive = all(
        transition["core_predictive_panel_coverage"] >= minimum_coverage
        for transition in panel["transitions"]
    )
    require(
        (certificate["predictive_sub_panel"] == "PASS") == expected_predictive,
        "predictive sub-panel verdict does not match measured coverage",
    )
    expected_gate = "PASS" if not panel["failures"] else "FAIL"
    require(certificate["gate"] == expected_gate, "gate verdict does not match published failures")
    if certificate["gate"] == "PASS":
        require(expected_predictive, "gate PASS while core predictive coverage is below the minimum")
        require(not certificate["blocking_missing_input_classes"], "gate PASS while inputs are still blocking")

    require(
        certificate["coefficients_after_gate"] == "ALL_PREDICTIVE_COEFFICIENTS_REMAIN_EXACTLY_ZERO",
        "certificate does not hold predictive coefficients at zero",
    )
    require(certificate["B2_claim_records_before_certificate"] == count_claim_records(), "claim record count drift")

    gates = load(GATES_PATH)
    gate = next(row for row in gates["gates"] if row["id"] == GATE_ID)
    if certificate["gate"] == "PASS":
        require(gate["status"] == "CLOSED", "gate PASS but registry does not record CLOSED")
    else:
        require(gate["status"] == "OPEN", "gate FAIL but registry does not keep the gate OPEN")
        require(gates.get("next_gate") == GATE_ID, "a failed B2-3 must remain the next gate")

    state = load(STATE_PATH)
    require(
        state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION",
        "state moved a predictive coefficient before B2-6",
    )
    require(state["anti_drift"]["LLM_semantic_evidence_forbidden"] is True, "anti-drift LLM flag was relaxed")
    require(state["anti_drift"]["missing_never_silently_zero"] is True, "anti-drift missingness flag was relaxed")
    require(state["anti_drift"]["agentic_experiment_locked"] is True, "agentic experiment was unlocked")
    if certificate["gate"] != "PASS":
        require(GATE_ID in state["gates"]["open"], "failed B2-3 is not listed as open in the state")
        require(GATE_ID not in state["gates"]["closed"], "failed B2-3 is listed as closed in the state")


def main() -> None:
    panel = load(PANEL_PATH)
    certificate = load(CERTIFICATE_PATH)

    dictionary = validate_parents(panel, certificate)
    validate_integrity(panel, certificate)
    validate_determinism(panel)
    minimum_coverage, minimum_support = validate_contract(panel, dictionary)
    validate_diagnostics(panel, dictionary)
    validate_gate_consistency(panel, certificate, minimum_coverage)

    fit, validation = panel["transitions"]
    print("B2_HISTORICAL_PANEL_VALIDATION_PASS")
    print(f"gate={certificate['gate']}")
    print(f"panel_sha256={certificate['panel_sha256']}")
    print(
        "features_identifiable="
        f"{fit['counts']['features_identifiable']}/{fit['counts']['features_total']} (fit), "
        f"{validation['counts']['features_identifiable']}/{validation['counts']['features_total']} (validation)"
    )
    print(
        "core_predictive_coverage="
        f"{fit['core_predictive_panel_coverage']} (fit), "
        f"{validation['core_predictive_panel_coverage']} (validation), "
        f"required={minimum_coverage}"
    )
    print(f"blocking_input_classes={len(certificate['blocking_missing_input_classes'])}")
    matrix = panel["matrix"]
    print(
        f"matrix_cells={matrix['row_count']} "
        f"feature_cells={matrix['feature_cell_count']} "
        f"diagnostic_cells={matrix['diagnostic_cell_count']} "
        f"rebuild_verified={matrix['canonical_rows_sha256'][:16]}"
    )
    print(f"predictive_coefficients=ZERO binary_support_minimum={minimum_support}")
    if certificate["gate"] != "PASS":
        print("result=B2-3 REMAINS OPEN; measured non-identifiability preserved")


if __name__ == "__main__":
    main()
