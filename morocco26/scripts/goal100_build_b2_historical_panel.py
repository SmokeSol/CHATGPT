#!/usr/bin/env python3
"""Build and certify the B2-3 same-cutoff historical feature panel.

This gate answers one question only: for the frozen fit transition 2011->2016
and the frozen validation transition 2016->2021, which features of
`b2_feature_dictionary_v1.json` are actually constructible from inputs that were
publicly knowable before the relevant historical election cutoff, and with what
coverage and support?

The builder is deterministic and offline. It performs no source discovery, no
semantic extraction and no LLM inference. Feature availability is *derived* from
an input inventory computed over the repository, never asserted. A feature whose
required historical inputs are absent stays NA: it is never silently zeroed, and
its coefficient stays exactly zero.

Post-outcome leakage guard: the 2021 elected-member roster is an election
outcome. It may establish incumbency for a *later* cutoff, never for the cycle
that produced it, and it is never used as a stand-in for a candidate roster.
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

PROTOCOL_PATH = G100 / "b2_protocol_v1.json"
DICTIONARY_PATH = G100 / "b2_feature_dictionary_v1.json"
CROSSWALK_PATH = G100 / "b2_identity_crosswalk.json"
IDENTITY_CERTIFICATE_PATH = G100 / "b2_identity_territory_certificate.json"
HISTORICAL_PATHS = {
    2011: G100 / "historical" / "tafra_legislative_2011_canonical.json",
    2016: G100 / "historical" / "tafra_legislative_2016_canonical.json",
    2021: G100 / "historical" / "tafra_legislative_2021_canonical.json",
}
GATES_PATH = G100 / "b2_gate_registry.json"
STATE_PATH = G100 / "b2_current_state.json"
EVIDENCE_DIR = G100 / "b2_evidence"
PANEL_PATH = G100 / "b2_historical_panel.json"
CERTIFICATE_PATH = G100 / "b2_historical_panel_certificate.json"
HISTORICAL_MEMBERS_PATH = G100 / "historical" / "b2_historical_elected_members.json"
ATTEMPTS_DIR = G100 / "b2_historical_panel_attempts"
EVENT_DIR = G100 / "fil_ariane_events"
JOURNAL = ROOT / "FIL_ARIANE.md"

# Frozen transitions from b2_feature_dictionary_v1.json.historical_calibration_contract.
TRANSITIONS = [
    {"transition_id": "2011_TO_2016", "prior_year": 2011, "target_year": 2016, "role": "FIT"},
    {"transition_id": "2016_TO_2021", "prior_year": 2016, "target_year": 2021, "role": "VALIDATION"},
]

# Each frozen evidence type resolves to exactly one historical input class.
# The mapping is structural, not discretionary: it restates what a record of
# that type must contain in order to become a historical feature cell.
EVIDENCE_TYPE_TO_INPUT = {
    "LIST_REGISTERED": "HISTORICAL_LIST_PRESENCE_TARGET_YEAR",
    "LIST_REJECTED": "HISTORICAL_LIST_REJECTION_TARGET_YEAR",
    "CANDIDATE_REGISTERED": "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR",
    "CANDIDATE_RANK": "HISTORICAL_CANDIDATE_RANK_TARGET_YEAR",
    "CANDIDATE_BIRTHDATE": "HISTORICAL_CANDIDATE_BIRTHDATE_TARGET_YEAR",
    "CANDIDATE_WITHDRAWN": "HISTORICAL_CANDIDATE_WITHDRAWAL_TARGET_YEAR",
    "CANDIDATE_DISQUALIFIED": "HISTORICAL_CANDIDATE_DISQUALIFICATION_TARGET_YEAR",
    "FORMAL_ALLIANCE": "HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR",
    "INCUMBENT_STATUS": "HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR",
    "PARTY_SWITCH": "HISTORICAL_PARTY_SWITCH_TARGET_YEAR",
    "ELECTED_OFFICE": "HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR",
    "PARTY_OFFICE": "HISTORICAL_PARTY_OFFICE_TARGET_YEAR",
    "FORMAL_ENDORSEMENT": "HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR",
    "FORMAL_DEFECTION": "HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR",
    "CAMPAIGN_LAUNCH": "HISTORICAL_CAMPAIGN_LAUNCH_TARGET_YEAR",
    "OFFICIAL_INVESTIGATION": "HISTORICAL_OFFICIAL_INVESTIGATION_TARGET_YEAR",
    "OFFICIAL_SANCTION": "HISTORICAL_OFFICIAL_SANCTION_TARGET_YEAR",
    "VERIFIED_CANDIDATE_DEATH_OR_INCAPACITY": "HISTORICAL_DEATH_OR_INCAPACITY_TARGET_YEAR",
}

# Excluded from input hashing: these record when an artifact was produced, not
# what it contains.
VOLATILE_INPUT_FIELDS = {"generated_at", "certified_at", "canonical_artifact_sha256"}

# Candidate-level column markers used to detect whether any ingested historical
# dataset carries a roster rather than aggregated list results.
CANDIDATE_ROSTER_MARKERS = {
    "candidate", "candidats", "candidate_name", "nom_candidat", "tete_de_liste",
    "head_candidate", "rank", "rang", "ordre", "idperson", "idcandidat",
    "birthdate", "date_naissance",
}


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_HISTORICAL_PANEL_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def repo_path(path: Path) -> str:
    """Repository-relative POSIX path, so artifacts are OS-independent."""
    return path.relative_to(REPO).as_posix()


def canonical_input_hash(path: Path) -> str:
    """Checkout-independent hash of a JSON input.

    Raw-byte hashing is not portable: a Windows checkout with core.autocrlf=true
    rewrites LF to CRLF, so the same committed content yields a different digest
    than it does in Linux CI. Hashing the canonical parsed JSON removes the line
    ending, indentation and key-order degrees of freedom entirely.

    Run timestamps are excluded so the digest tracks content: regenerating an
    input without changing it must not invalidate the panel, while any real
    change still does.
    """
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = {
            key: item for key, item in value.items()
            if key not in VOLATILE_INPUT_FIELDS
        }
    return canonical_sha256(value)


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_HISTORICAL_PANEL_FAIL: {message}")


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def count_claim_records() -> int:
    if not EVIDENCE_DIR.exists():
        return 0
    return sum(1 for path in EVIDENCE_DIR.rglob("*.json") if path.is_file())


def build_input_inventory(crosswalk: dict) -> dict:
    """Derive, from repository content only, which historical inputs exist.

    Availability is discovered by inspecting the ingested artifacts, so an
    absent input is a measured fact about the corpus rather than a claim.
    """
    list_years: dict[int, int] = defaultdict(int)
    for row in crosswalk["lists"]:
        if row["scope"] == "local":
            list_years[int(row["year"])] += 1

    elected_years: dict[int, int] = defaultdict(int)
    elected_territories: dict[int, set[str]] = defaultdict(set)
    for row in crosswalk["people_2021"]:
        if row["scope"] == "local":
            elected_years[2021] += 1
            if row.get("territory_id"):
                elected_territories[2021].add(row["territory_id"])

    # Legislatures recovered by deterministic acquisition, if the parser has run.
    elected_provenance = {"2021": "b2_identity_crosswalk.people_2021"}
    if HISTORICAL_MEMBERS_PATH.exists():
        members = load(HISTORICAL_MEMBERS_PATH)
        for year_key, entry in members["years"].items():
            year = int(year_key)
            resolved = [
                row for row in entry["rows"]
                if row["scope"] == "local" and row.get("territory_id")
            ]
            if not resolved:
                continue
            if year != 2021:
                elected_years[year] = len(resolved)
                elected_provenance[year_key] = repo_path(HISTORICAL_MEMBERS_PATH)
            elected_territories[year].update(row["territory_id"] for row in resolved)

    roster_years: dict[int, int] = {}
    observed_columns: dict[str, list[str]] = {}
    for year, path in sorted(HISTORICAL_PATHS.items()):
        data = load(path)
        columns: set[str] = set()
        for row in data["rows"]:
            columns.update(str(key).casefold() for key in row.keys())
        observed_columns[str(year)] = sorted(columns)
        if columns & CANDIDATE_ROSTER_MARKERS:
            roster_years[year] = len(data["rows"])

    inventory = {
        "HISTORICAL_LIST_PRESENCE_TARGET_YEAR": {
            "available_years": sorted(list_years),
            "instances_by_year": {str(year): list_years[year] for year in sorted(list_years)},
            "provenance": "b2_identity_crosswalk.lists (scope=local)",
            "semantics": "POSITIVE_VOTE_LIST_OBSERVED_IN_CANONICAL_RESULT",
            "absence_semantics": "NA_NOT_ZERO",
        },
        "HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR": {
            "available_years": sorted(elected_years),
            "instances_by_year": {str(year): elected_years[year] for year in sorted(elected_years)},
            "territories_by_year": {
                str(year): len(elected_territories[year]) for year in sorted(elected_territories)
            },
            "provenance_by_year": elected_provenance,
            "semantics": "ELECTION_OUTCOME_OF_ITS_OWN_CYCLE",
            "leakage_rule": "Admissible only as prior-cycle incumbency for a strictly later cutoff.",
        },
        "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR": {
            "available_years": sorted(roster_years),
            "instances_by_year": {str(year): value for year, value in sorted(roster_years.items())},
            "provenance": "scan of ingested TAFRA canonical rows for candidate-level columns",
            "observed_columns_by_year": observed_columns,
            "detection_markers": sorted(CANDIDATE_ROSTER_MARKERS),
        },
    }
    # Every other declared input class has no ingested provider at all.
    for input_class in sorted(set(EVIDENCE_TYPE_TO_INPUT.values())):
        inventory.setdefault(input_class, {
            "available_years": [],
            "instances_by_year": {},
            "provenance": None,
            "reason": "No ingested repository dataset provides this input class.",
        })
    return inventory


def required_inputs(feature: dict) -> list[str]:
    return sorted({EVIDENCE_TYPE_TO_INPUT[value] for value in feature["source_evidence_types"]})


def input_available(inventory: dict, input_class: str, transition: dict) -> bool:
    entry = inventory[input_class]
    years = set(entry["available_years"])
    if input_class.endswith("_PRIOR_YEAR"):
        return transition["prior_year"] in years
    return transition["target_year"] in years


def compute_ballot_presence(crosswalk: dict, target_year: int, territory_ids: list[str]) -> tuple[list[dict], dict]:
    """B2_M01: observed local ballot list presence for the target year."""
    rows = []
    per_territory: dict[str, int] = defaultdict(int)
    for row in crosswalk["lists"]:
        if row["scope"] != "local" or int(row["year"]) != target_year:
            continue
        rows.append({
            "territory_id": row["territory_id"],
            "party_code": row["party_code"],
            "value": 1,
            "list_id": row["list_id"],
        })
        per_territory[row["territory_id"]] += 1
    rows.sort(key=lambda item: (item["territory_id"], item["party_code"]))
    covered = [tid for tid in territory_ids if per_territory[tid] > 0]
    summary = {
        "territories_covered": len(covered),
        "coverage_fraction": round(len(covered) / len(territory_ids), 6),
        "positive_instances": len(rows),
        "distinct_parties": len({row["party_code"] for row in rows}),
        "min_lists_per_covered_territory": min((per_territory[tid] for tid in covered), default=0),
        "max_lists_per_covered_territory": max((per_territory[tid] for tid in covered), default=0),
    }
    return rows, summary


# Frozen deterministic constructors, keyed by feature_id. A feature is only
# built when its required inputs exist AND a constructor is registered here.
# Registering one is a versioned protocol act, never an inline improvisation.
CONSTRUCTORS: dict[str, object] = {}


def build_panel() -> tuple[dict, dict]:
    protocol = load(PROTOCOL_PATH)
    dictionary = load(DICTIONARY_PATH)
    crosswalk = load(CROSSWALK_PATH)
    identity_certificate = load(IDENTITY_CERTIFICATE_PATH)

    require(protocol["status"] == "FROZEN_PRE_COLLECTION", "B2 protocol is not frozen pre-collection")
    require(dictionary["status"] == "FROZEN_COEFFICIENTS_ZERO_PENDING_CALIBRATION", "feature dictionary is not frozen")
    require(identity_certificate["gate"] == "PASS", "B2-2 identity/territory gate is not PASS")
    require(crosswalk["gate"] == "PASS", "identity crosswalk is not PASS")
    require(
        crosswalk["canonical_crosswalk_sha256"] == identity_certificate["crosswalk_sha256"],
        "crosswalk hash does not match the certified identity crosswalk",
    )

    contract = dictionary["historical_calibration_contract"]
    require(contract["fit_transition"] == "2011_TO_2016", "frozen fit transition drift")
    require(contract["validation_transition"] == "2016_TO_2021", "frozen validation transition drift")
    minimum_coverage = float(contract["core_panel_minimum_coverage_each_transition"])
    minimum_support = int(contract["binary_feature_minimum_positive_instances"])

    territory_ids = sorted(row["constituency_id"] for row in crosswalk["territories"]["local"])
    require(len(territory_ids) == 92, f"expected 92 certified local territories, found {len(territory_ids)}")

    inventory = build_input_inventory(crosswalk)
    features = dictionary["features"]

    transitions_out = []
    matrix_rows = []
    diagnostics_out = []
    for transition in TRANSITIONS:
        # Measured independently of the gate: what the ingested corpus actually
        # shows about target-year list presence. This is a diagnostic, not a
        # feature. Observed positives prove ballot presence; they cannot prove
        # the absences that B2_M01 requires, so it never becomes B2_M01.
        diagnostic_rows, diagnostic_summary = compute_ballot_presence(
            crosswalk, transition["target_year"], territory_ids
        )
        diagnostics_out.append({
            "diagnostic_id": "OBSERVED_POSITIVE_LOCAL_LIST_PRESENCE",
            "transition_id": transition["transition_id"],
            "target_year": transition["target_year"],
            "satisfies_feature": None,
            "closest_feature": "B2_M01_BALLOT_LIST_PRESENT",
            "why_not_a_feature": (
                "B2_M01 requires a certified full-coverage authoritative ballot table so that "
                "rejected/absent lists can be set to 0. The corpus only carries positive vote "
                "observations, which establish presence but never absence."
            ),
            **diagnostic_summary,
        })
        # The cells are not copied here: they are already committed in
        # b2_identity_crosswalk.lists. The panel keeps the count and a hash so
        # the derivation is verifiable without duplicating upstream data.
        matrix_rows.extend(
            {
                "transition_id": transition["transition_id"],
                "diagnostic_id": "OBSERVED_POSITIVE_LOCAL_LIST_PRESENCE",
                "feature_id": None,
                "territory_id": row["territory_id"],
                "party_code": row["party_code"],
                "value": row["value"],
            }
            for row in diagnostic_rows
        )

        feature_rows = []
        for feature in features:
            needed = required_inputs(feature)
            missing = [value for value in needed if not input_available(inventory, value, transition)]
            identifiable = not missing

            entry = {
                "feature_id": feature["feature_id"],
                "entity": feature["entity"],
                "forecast_role": feature["forecast_role"],
                "source_evidence_types": feature["source_evidence_types"],
                "required_inputs": needed,
                "missing_inputs": missing,
                "identifiable": identifiable,
                "territories_covered": 0,
                "coverage_fraction": 0.0,
                "positive_instances": 0,
                "support_meets_minimum": False,
                "cells_na": len(territory_ids),
                "na_policy": "MISSING_IS_NA_NEVER_ZERO",
                "coefficient_state": feature.get("coefficient_state"),
            }

            if identifiable and feature["feature_id"] not in CONSTRUCTORS:
                # Every required input exists but no frozen deterministic
                # constructor is registered. Improvising one here would be an
                # unversioned protocol change, so the cell stays NA.
                entry["identifiable"] = False
                entry["missing_inputs"] = ["FROZEN_DETERMINISTIC_CONSTRUCTOR"]
            elif identifiable:
                rows, summary = CONSTRUCTORS[feature["feature_id"]](
                    crosswalk, transition["target_year"], territory_ids
                )
                entry.update({
                    "territories_covered": summary["territories_covered"],
                    "coverage_fraction": summary["coverage_fraction"],
                    "positive_instances": summary["positive_instances"],
                    "support_meets_minimum": summary["positive_instances"] >= minimum_support,
                    "cells_na": len(territory_ids) - summary["territories_covered"],
                    "detail": summary,
                })
                for row in rows:
                    matrix_rows.append({
                        "transition_id": transition["transition_id"],
                        "target_year": transition["target_year"],
                        "diagnostic_id": None,
                        "feature_id": feature["feature_id"],
                        "territory_id": row["territory_id"],
                        "party_code": row["party_code"],
                        "value": row["value"],
                        "source_list_id": row["list_id"],
                    })

            feature_rows.append(entry)

        mechanical = [row for row in feature_rows if row["forecast_role"] == "MECHANICAL"]
        predictive = [row for row in feature_rows if row["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION"]
        reporting = [row for row in feature_rows if row not in mechanical and row not in predictive]

        # The core panel is the predictive family: it is the only family whose
        # coverage can license a fitted coefficient.
        identifiable_predictive = [row for row in predictive if row["identifiable"]]
        core_coverage = (
            min(row["coverage_fraction"] for row in identifiable_predictive)
            if identifiable_predictive else 0.0
        )
        mechanical_identifiable = [row for row in mechanical if row["identifiable"]]
        mechanical_coverage = (
            min(row["coverage_fraction"] for row in mechanical_identifiable)
            if mechanical_identifiable else 0.0
        )

        transitions_out.append({
            "transition_id": transition["transition_id"],
            "role": transition["role"],
            "prior_year": transition["prior_year"],
            "target_year": transition["target_year"],
            "information_cutoff_rule": contract["feature_creation_cutoff"],
            "territories_in_scope": len(territory_ids),
            "features": feature_rows,
            "counts": {
                "features_total": len(feature_rows),
                "features_identifiable": sum(row["identifiable"] for row in feature_rows),
                "features_not_identifiable": sum(not row["identifiable"] for row in feature_rows),
                "mechanical_identifiable": len(mechanical_identifiable),
                "predictive_identifiable": len(identifiable_predictive),
                "reporting_identifiable": sum(row["identifiable"] for row in reporting),
            },
            "core_predictive_panel_coverage": round(core_coverage, 6),
            "mechanical_panel_coverage": round(mechanical_coverage, 6),
            "core_predictive_panel_meets_minimum": core_coverage >= minimum_coverage,
            "features_meeting_support_minimum": sorted(
                row["feature_id"] for row in feature_rows if row["support_meets_minimum"]
            ),
        })

    missing_input_classes = sorted({
        value
        for transition in transitions_out
        for row in transition["features"]
        for value in row["missing_inputs"]
    })

    failures = []
    for transition in transitions_out:
        if not transition["core_predictive_panel_meets_minimum"]:
            failures.append({
                "kind": "CORE_PREDICTIVE_PANEL_COVERAGE_BELOW_MINIMUM",
                "transition_id": transition["transition_id"],
                "observed_coverage": transition["core_predictive_panel_coverage"],
                "required_coverage": minimum_coverage,
                "identifiable_predictive_features": transition["counts"]["predictive_identifiable"],
            })
    claim_count = count_claim_records()
    if claim_count != 0:
        failures.append({"kind": "B2_CLAIM_RECORDS_EXIST_BEFORE_PANEL_GATE", "count": claim_count})

    generated_at = now_local()
    input_paths = {
        "protocol": PROTOCOL_PATH,
        "feature_dictionary": DICTIONARY_PATH,
        "identity_crosswalk": CROSSWALK_PATH,
        "identity_certificate": IDENTITY_CERTIFICATE_PATH,
        "historical_2011": HISTORICAL_PATHS[2011],
        "historical_2016": HISTORICAL_PATHS[2016],
        "historical_2021": HISTORICAL_PATHS[2021],
    }
    if HISTORICAL_MEMBERS_PATH.exists():
        input_paths["historical_elected_members"] = HISTORICAL_MEMBERS_PATH

    panel = {
        "schema_version": "1.0",
        "panel_id": "M26-GOAL100-B2-HISTORICAL-PANEL-V1",
        "protocol_id": protocol["protocol_id"],
        "dictionary_id": dictionary["dictionary_id"],
        "generated_at": generated_at,
        "gate": "PASS" if not failures else "FAIL",
        "determinism": {
            "llm_used": False,
            "network_access": False,
            "source_discovery": False,
            "extraction_method": "DETERMINISTIC_STRUCTURED_JOIN",
        },
        "calibration_contract": contract,
        "input_inventory": inventory,
        "evidence_type_to_input_class": EVIDENCE_TYPE_TO_INPUT,
        "transitions": transitions_out,
        "observed_diagnostics": diagnostics_out,
        "matrix": {
            "row_count": len(matrix_rows),
            "feature_cell_count": sum(row["feature_id"] is not None for row in matrix_rows),
            "diagnostic_cell_count": sum(row["diagnostic_id"] is not None for row in matrix_rows),
            "canonical_rows_sha256": canonical_sha256(matrix_rows),
            "storage": "DERIVED_NOT_DUPLICATED",
            "derivation": {
                "source_artifact": repo_path(CROSSWALK_PATH),
                "source_field": "lists",
                "filter": "scope == 'local' and year == transition.target_year",
                "emit": "one cell per (territory_id, party_code) with value 1",
                "sort": "lexicographic by (territory_id, party_code)",
                "absence_rule": "unobserved pairs are NA and are never emitted as 0",
                "rebuild_command": "python morocco26/scripts/goal100_build_b2_historical_panel.py",
            },
        },
        "leakage_controls": {
            "target_outcome_used_in_feature_creation": False,
            "elected_roster_used_as_candidate_roster": False,
            "elected_roster_used_for_own_cycle_incumbency": False,
            "absence_converted_to_zero": False,
            "note": (
                "people_2021 is the outcome of the 2021 cycle. It is never used to build a "
                "2016->2021 feature and is never treated as a candidate roster."
            ),
        },
        "missing_input_classes": missing_input_classes,
        "input_hash_method": "CANONICAL_JSON_SHA256",
        "input_hashes": {
            name: {"path": repo_path(path), "canonical_json_sha256": canonical_input_hash(path)}
            for name, path in sorted(input_paths.items())
        },
        "failures": failures,
    }
    panel_hash = canonical_sha256(panel)
    panel["canonical_panel_sha256"] = panel_hash

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-HISTORICAL-PANEL-CERTIFICATE-V1",
        "protocol_id": protocol["protocol_id"],
        "gate_id": "B2-3-HISTORICAL-FEATURE-PANEL",
        "certified_at": generated_at,
        "gate": "PASS" if not failures else "FAIL",
        "panel_path": repo_path(PANEL_PATH),
        "panel_sha256": panel_hash,
        "territories_in_scope": len(territory_ids),
        "minimum_coverage_required": minimum_coverage,
        "minimum_binary_support_required": minimum_support,
        "transitions": [
            {
                "transition_id": transition["transition_id"],
                "role": transition["role"],
                "features_total": transition["counts"]["features_total"],
                "features_identifiable": transition["counts"]["features_identifiable"],
                "mechanical_panel_coverage": transition["mechanical_panel_coverage"],
                "core_predictive_panel_coverage": transition["core_predictive_panel_coverage"],
                "core_predictive_panel_meets_minimum": transition["core_predictive_panel_meets_minimum"],
                "features_meeting_support_minimum": transition["features_meeting_support_minimum"],
            }
            for transition in transitions_out
        ],
        "observed_diagnostics": [
            {
                "diagnostic_id": row["diagnostic_id"],
                "transition_id": row["transition_id"],
                "territories_covered": row["territories_covered"],
                "coverage_fraction": row["coverage_fraction"],
                "positive_instances": row["positive_instances"],
                "satisfies_feature": row["satisfies_feature"],
            }
            for row in diagnostics_out
        ],
        "mechanical_sub_panel": "PASS" if all(
            transition["mechanical_panel_coverage"] >= minimum_coverage for transition in transitions_out
        ) else "FAIL",
        "predictive_sub_panel": "PASS" if all(
            transition["core_predictive_panel_meets_minimum"] for transition in transitions_out
        ) else "FAIL",
        "blocking_missing_input_classes": missing_input_classes,
        "coefficients_after_gate": "ALL_PREDICTIVE_COEFFICIENTS_REMAIN_EXACTLY_ZERO",
        "B2_claim_records_before_certificate": claim_count,
        "failures": failures,
        "scientific_boundary": (
            "This certificate reports which frozen features are constructible at the historical "
            "information cutoff, with measured coverage and support. It certifies no political "
            "effect, no coefficient and no 2026 quantity."
        ),
    }
    return panel, certificate


def append_event_and_transition(certificate: dict, panel: dict) -> None:
    if certificate["gate"] != "PASS":
        run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
        event_id = f"A023F{run_id}"
        event = {
            "event_id": event_id,
            "date": certificate["certified_at"],
            "title": "Panel historique B2-3 non identifiable en l'état",
            "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
            "gate": "B2-3-HISTORICAL-FEATURE-PANEL",
            "status": "FAIL",
            "machine_result": certificate,
            "scientific_decision": (
                "B2-3 stays OPEN. The measured non-identifiability is preserved as a result: no "
                "feature is improvised, no absence is converted to zero and every predictive "
                "coefficient remains exactly zero."
            ),
            "next_action_exact": (
                "Ingest the blocking historical input classes through the versioned historical "
                "ingest pipeline, or record the negative result and proceed with the mechanical "
                "sub-panel only. No coefficient may move either way."
            ),
        }
        dump(EVENT_DIR / f"{event_id}.json", event)

        gates = load(GATES_PATH)
        gate = next(row for row in gates["gates"] if row["id"] == "B2-3-HISTORICAL-FEATURE-PANEL")
        gate["status"] = "OPEN"
        gate["last_attempt"] = {
            "certified_at": certificate["certified_at"],
            "result": "FAIL",
            "certificate": repo_path(CERTIFICATE_PATH),
            "panel_sha256": certificate["panel_sha256"],
            "blocking_missing_input_classes": certificate["blocking_missing_input_classes"],
        }
        gates["as_of"] = certificate["certified_at"]
        dump(GATES_PATH, gates)

        state = load(STATE_PATH)
        state["as_of"] = certificate["certified_at"]
        state["historical_panel"] = {
            "status": "ATTEMPTED_NOT_IDENTIFIABLE",
            "certificate": repo_path(CERTIFICATE_PATH),
            "panel": repo_path(PANEL_PATH),
            "panel_sha256": certificate["panel_sha256"],
            "mechanical_sub_panel": certificate["mechanical_sub_panel"],
            "predictive_sub_panel": certificate["predictive_sub_panel"],
            "blocking_missing_input_classes": certificate["blocking_missing_input_classes"],
        }
        state["next_action_exact"] = (
            "Close B2-3 by ingesting the published blocking historical input classes under a "
            "versioned pipeline, or freeze the negative result; either way every predictive "
            "coefficient stays exactly zero and B2-4/B2-6 remain unmoved."
        )
        dump(STATE_PATH, state)
        return

    gates = load(GATES_PATH)
    gate = next(row for row in gates["gates"] if row["id"] == "B2-3-HISTORICAL-FEATURE-PANEL")
    gate["status"] = "CLOSED"
    gate["resolved_claim"] = (
        "The same-cutoff historical feature panel meets the frozen coverage and support minima "
        "for both the fit and validation transitions."
    )
    gates["as_of"] = certificate["certified_at"]
    gates["next_gate"] = "B2-4-2026-BALLOT-ROSTER"
    dump(GATES_PATH, gates)

    state = load(STATE_PATH)
    state["as_of"] = certificate["certified_at"]
    state["phase"] = "B2_HISTORICAL_PANEL_CERTIFIED_BALLOT_ROSTER_PENDING"
    state["historical_panel"] = {
        "status": "CERTIFIED",
        "certificate": repo_path(CERTIFICATE_PATH),
        "panel": repo_path(PANEL_PATH),
        "panel_sha256": certificate["panel_sha256"],
    }
    closed = state["gates"]["closed"]
    if "B2-3-HISTORICAL-FEATURE-PANEL" not in closed:
        closed.append("B2-3-HISTORICAL-FEATURE-PANEL")
    state["gates"]["open"] = [v for v in state["gates"]["open"] if v != "B2-3-HISTORICAL-FEATURE-PANEL"]
    state["next_action_exact"] = "Build the authoritative 2026 ballot roster gate B2-4."
    dump(STATE_PATH, state)

    event = {
        "event_id": "A023",
        "date": certificate["certified_at"],
        "title": "Certification du panel historique de features B2",
        "phase": "P7_B2_STRUCTURED_EVIDENCE_LAYER",
        "gate": "B2-3-HISTORICAL-FEATURE-PANEL",
        "status": "PASS",
        "machine_result": certificate,
        "scientific_decision": "Historical panel certified; coefficients remain zero until B2-6.",
        "next_action_exact": "Execute B2-4 authoritative 2026 ballot roster coverage.",
    }
    dump(EVENT_DIR / "A023.json", event)


def append_journal(certificate: dict, panel: dict) -> None:
    marker = "Entrée A023 — Panel historique de features B2 au même cutoff"
    text = JOURNAL.read_text(encoding="utf-8")
    if marker in text:
        return
    fit = certificate["transitions"][0]
    val = certificate["transitions"][1]
    blocking = ", ".join(f"`{value}`" for value in certificate["blocking_missing_input_classes"]) or "aucune"
    text += f"""

### {certificate['certified_at'][:10]} — {marker}

**Question/gate traité :** `B2-3-HISTORICAL-FEATURE-PANEL` — quelles features du dictionnaire gelé sont réellement constructibles au cutoff historique, avec quelle couverture et quel support ?

**Hypothèse avant test :** le panel candidat/liste doit couvrir au moins `{certificate['minimum_coverage_required']}` des 92 territoires locaux sur `2011→2016` et `2016→2021`, et tout binaire promu doit atteindre `{certificate['minimum_binary_support_required']}` instances positives.

**Résultat machine :** `{certificate['gate']}` — features totales `{fit['features_total']}` ; identifiables `{fit['features_identifiable']}` (fit) et `{val['features_identifiable']}` (validation). Couverture mécanique `{fit['mechanical_panel_coverage']}` / `{val['mechanical_panel_coverage']}` ; couverture prédictive centrale `{fit['core_predictive_panel_coverage']}` / `{val['core_predictive_panel_coverage']}`. Panel mécanique `{certificate['mechanical_sub_panel']}`, panel prédictif `{certificate['predictive_sub_panel']}`.

**Classes d'entrée bloquantes :** {blocking}

**Cellules mesurées :** `{panel['matrix']['row_count']}` dont `{panel['matrix']['feature_cell_count']}` cellules de feature et `{panel['matrix']['diagnostic_cell_count']}` cellules de diagnostic ; hash canonique `{panel['matrix']['canonical_rows_sha256'][:16]}…`

**Frontière scientifique :** `people_2021` est un résultat électoral ; il n'est jamais utilisé comme roster de candidats ni comme incumbency de son propre cycle. Aucune absence n'est convertie en zéro.

**Décision scientifique :** {'panel certifié' if certificate['gate'] == 'PASS' else "B2-3 reste OPEN ; la non-identifiabilité mesurée est conservée comme résultat et aucun coefficient ne bouge"}.

**Prochaine action exacte :** {'exécuter B2-4 (roster de bulletin 2026 autoritatif).' if certificate['gate'] == 'PASS' else "ingérer les classes d'entrée bloquantes publiées via un pipeline historique versionné, ou geler le résultat négatif ; dans les deux cas les coefficients prédictifs restent exactement nuls."}
"""
    JOURNAL.write_text(text, encoding="utf-8")


def preserve_prior_attempt() -> dict | None:
    """Archive an existing panel/certificate pair before it is replaced.

    A gate attempt is evidence. Reruns append a new archived attempt keyed by
    the prior panel hash; they never destroy the earlier result.
    """
    if not (PANEL_PATH.exists() and CERTIFICATE_PATH.exists()):
        return None
    prior_panel = load(PANEL_PATH)
    prior_certificate = load(CERTIFICATE_PATH)
    prior_hash = prior_panel.get("canonical_panel_sha256")
    if not prior_hash:
        return None
    archive_dir = ATTEMPTS_DIR / f"panel_{prior_hash[:16]}"
    if (archive_dir / "manifest.json").exists():
        return None
    dump(archive_dir / "b2_historical_panel.json", prior_panel)
    dump(archive_dir / "b2_historical_panel_certificate.json", prior_certificate)
    manifest = {
        "schema_version": "1.0",
        "archived_at": now_local(),
        "prior_panel_sha256": prior_hash,
        "prior_gate": prior_certificate.get("gate"),
        "prior_certified_at": prior_certificate.get("certified_at"),
        "prior_features_identifiable": [
            {"transition_id": row["transition_id"], "features_identifiable": row["features_identifiable"]}
            for row in prior_certificate.get("transitions", [])
        ],
        "reason": "Superseded by a later B2-3 execution; retained because a gate attempt is evidence.",
    }
    dump(archive_dir / "manifest.json", manifest)
    return manifest


def main() -> None:
    panel, certificate = build_panel()
    preserve_prior_attempt()
    dump(PANEL_PATH, panel)
    dump(CERTIFICATE_PATH, certificate)
    append_event_and_transition(certificate, panel)
    append_journal(certificate, panel)
    print("B2_HISTORICAL_PANEL_PASS" if certificate["gate"] == "PASS" else "B2_HISTORICAL_PANEL_FAIL")
    print(json.dumps(certificate, ensure_ascii=False, indent=2))
    raise SystemExit(0 if certificate["gate"] == "PASS" else 3)


if __name__ == "__main__":
    main()
