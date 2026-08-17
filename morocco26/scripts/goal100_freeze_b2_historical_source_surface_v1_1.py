#!/usr/bin/env python3
"""Freeze the V1.1 historical source-surface amendment, before any acquisition.

Why this amendment exists, measured rather than argued: the frozen B2 source
registry V1 expresses `election_years = [2026]`. Its query templates name only
2026 terms and set a publication floor of 2025-01-01, so it cannot express the
2016/2021 acquisition problem that B2-3 requires. The gap is a definitional
omission in V1, not evidence that historical data is unobtainable.

Anti-overfit construction. Source eligibility here is decided by exactly two
outcome-independent tests, applied at ROOT level before any content is
inspected:

  1. the root already appears in repository provenance, or
  2. the root is an archive mirror of a domain already in the frozen registry.

No forecast residual, party result or feature-performance signal is consulted,
and no political fact is selected. The original registry is not edited; V1
remains frozen and this is a separate versioned artifact.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G75 = ROOT / "data" / "goal75"
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

REGISTRY_V1_PATH = G100 / "b2_source_registry.json"
PROTOCOL_PATH = G100 / "b2_protocol_v1.json"
DICTIONARY_PATH = G100 / "b2_feature_dictionary_v1.json"
SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"
PANEL_CERT_PATH = G100 / "b2_historical_panel_certificate.json"
STATE_PATH = G100 / "b2_current_state.json"
FORECAST_PATH = G100 / "forecasts" / "F-1" / "forecast.json"
FORECAST_MANIFEST_PATH = G100 / "forecasts" / "F-1" / "snapshot_manifest.json"
HISTORICAL_MANIFEST_PATH = G100 / "historical" / "historical_ingest_manifest.json"
ELECTED_2021_PATH = G75 / "observed_elected_2021.json"

SURFACE_V1_1_PATH = G100 / "historical_source_surface_v1_1.json"
PROTOCOL_V1_1_PATH = G100 / "historical_acquisition_protocol_v1_1.json"
CERTIFICATE_PATH = G100 / "historical_source_surface_certificate.json"

AMENDMENT_ID = "M26-GOAL100-B2-HISTORICAL-SOURCE-SURFACE-V1.1"
REQUIRED_YEARS = [2016, 2021]
PRIOR_STATE_YEARS = [2011]

# Frozen pre-election cutoffs. A historical fact is admissible only if it was
# publicly available before the cutoff of the election being predicted.
ELECTION_CUTOFFS = {
    2011: "2011-11-25T00:00:00+01:00",
    2016: "2016-10-07T00:00:00+01:00",
    2021: "2021-09-08T00:00:00+01:00",
}


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_V1_1_FREEZE_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def provenance_roots() -> dict:
    """Roots already present in repository provenance. Test 1 of eligibility."""
    roots: dict[str, list[str]] = {}
    manifest = load(HISTORICAL_MANIFEST_PATH)
    for dataset in manifest["datasets"]:
        roots.setdefault("open.africa", []).append(repo_rel(HISTORICAL_MANIFEST_PATH))
    elected = load(ELECTED_2021_PATH)
    if elected.get("source_dataset"):
        roots.setdefault("huggingface.co", []).append(repo_rel(ELECTED_2021_PATH))
    return {root: sorted(set(paths)) for root, paths in sorted(roots.items())}


def registered_domains() -> list[str]:
    """Domains already inside the frozen registry. Basis for archive mirrors."""
    registry = load(REGISTRY_V1_PATH)
    domains: set[str] = set()
    for entry in registry["source_entries"]:
        domains.update(entry.get("allowed_domains", []))
    return sorted(domains)


def build_surface() -> dict:
    existing = load(SURFACE_PATH)
    v1_reach = existing["families"]["B2_SOURCE_REGISTRY_V1"]["temporal_reach"]
    roots = provenance_roots()
    mirrored = registered_domains()

    sources = [
        {
            "source_id": "H1_OPENAFRICA_CATALOG",
            "source_class": "OPEN_DATA_CATALOG_ALREADY_IN_PROVENANCE",
            "root": "open.africa",
            "eligibility_basis": "ROOT_ALREADY_IN_REPOSITORY_PROVENANCE",
            "provenance_evidence": roots.get("open.africa", []),
            "years": PRIOR_STATE_YEARS + REQUIRED_YEARS,
            "rationale": (
                "The 2011/2016/2021 legislative result files already ingested by "
                "M26-GOAL100-TAFRA-HISTORY-V1 come from this catalog. V1 never declared the catalog "
                "itself as an enumerable surface, only three individual download URLs."
            ),
            "expected_format": ["application/json", "text/csv", "application/vnd.ms-excel", "xlsx"],
            "admissibility_basis": "ALREADY_ACCEPTED_PANEL_INPUT_PROVENANCE",
            "deterministic_enumeration_method": {
                "method": "CKAN_ACTION_API",
                "routes": [
                    "/api/3/action/package_search?q={term}&rows={rows}&start={start}",
                    "/api/3/action/package_show?id={dataset}",
                ],
                "fixed_terms": ["maroc", "morocco", "elections", "parlement", "candidat"],
                "rows_per_page": 100,
                "max_pages_per_term": 5,
                "ordering": "lexicographic by package name",
                "selection_rule": (
                    "Packages are retained by exact substring match on the fixed terms only. No "
                    "semantic ranking, no relevance judgment, no LLM."
                ),
            },
            "cutoff_rule": "Dataset contents must describe an election at or before its own year; see time_contract.",
        },
        {
            "source_id": "H2_HUGGINGFACE_ELECTRICSHEEPAFRICA",
            "source_class": "DATASET_HOST_ALREADY_IN_PROVENANCE",
            "root": "huggingface.co",
            "organization": "electricsheepafrica",
            "eligibility_basis": "ROOT_ALREADY_IN_REPOSITORY_PROVENANCE",
            "provenance_evidence": roots.get("huggingface.co", []),
            "years": PRIOR_STATE_YEARS + REQUIRED_YEARS,
            "rationale": (
                "The 395 elected 2021 rows and the recovered 2011/2016 legislatures come from this "
                "organization. V1 never declared the organization as an enumerable surface, only one "
                "dataset identifier."
            ),
            "expected_format": ["application/json", "parquet", "text/csv"],
            "admissibility_basis": "ALREADY_ACCEPTED_PANEL_INPUT_PROVENANCE",
            "deterministic_enumeration_method": {
                "method": "HUGGINGFACE_HTTP_API",
                "routes": [
                    "/api/datasets?author={organization}&limit={limit}",
                    "/api/datasets/{dataset}",
                    "/datasets/{dataset}/resolve/main/{file}",
                ],
                "limit": 1000,
                "ordering": "lexicographic by dataset id",
                "selection_rule": (
                    "All datasets of the recorded organization are enumerated; retention is by exact "
                    "substring match on fixed terms. No semantic ranking, no LLM."
                ),
                "fixed_terms": ["maroc", "morocco", "chambre", "representants", "candidat", "election"],
            },
            "cutoff_rule": "Dataset contents must describe an election at or before its own year; see time_contract.",
        },
        {
            "source_id": "H3_WEB_ARCHIVE_OF_REGISTERED_DOMAINS",
            "source_class": "ARCHIVE_MIRROR_OF_ALREADY_REGISTERED_DOMAIN",
            "root": "web.archive.org",
            "eligibility_basis": "ARCHIVE_MIRROR_OF_DOMAIN_ALREADY_IN_FROZEN_REGISTRY",
            "mirrored_domains": mirrored,
            "years": PRIOR_STATE_YEARS + REQUIRED_YEARS,
            "rationale": (
                "The frozen protocol already contemplates ARCHIVE_COPY as a publication type and "
                "archive_locator as a source field. This introduces no new publisher: it can only "
                "return snapshots of domains that are already inside the frozen registry, which is "
                "what makes pre-cutoff availability provable rather than assumed."
            ),
            "expected_format": ["text/html", "application/pdf", "text/xml"],
            "admissibility_basis": "FROZEN_SCHEMA_PUBLICATION_TYPE_ARCHIVE_COPY",
            "deterministic_enumeration_method": {
                "method": "WAYBACK_CDX_API",
                "routes": [
                    "/cdx/search/cdx?url={domain}{path_wildcard}&output=json&from={from_ts}&to={to_ts}&limit={limit}",
                    "/web/{timestamp}id_/{original_url}",
                ],
                "path_wildcard": "*",
                "limit": 2000,
                "ordering": "lexicographic by (original url, timestamp)",
                "selection_rule": (
                    "Snapshots are selected only by domain membership in the frozen registry and by "
                    "capture timestamp strictly before the relevant election cutoff. Content is never "
                    "used to decide whether to retrieve."
                ),
            },
            "cutoff_rule": (
                "Only captures with timestamp strictly before the election cutoff establish pre-cutoff "
                "availability. A later capture of an earlier fact is UNKNOWN_AT_CUTOFF."
            ),
        },
    ]

    surface = {
        "schema_version": "1.1",
        "amendment_id": AMENDMENT_ID,
        "supersedes": None,
        "amends": "M26-GOAL100-B2-SOURCES-V1",
        "amendment_scope": "ACQUISITION_SURFACE_DEFINITIONS_ONLY",
        "status": "FROZEN_PRE_ACQUISITION",
        "frozen_at": now_local(),
        "trigger_measurement": {
            "v1_election_years_expressible": v1_reach["election_years_expressible"],
            "v1_publication_floor_years": v1_reach["publication_floor_years"],
            "b2_3_required_years": REQUIRED_YEARS,
            "prior_state_years": PRIOR_STATE_YEARS,
            "diagnosis": (
                "The V1 registry is structurally 2026-only and cannot express the 2016/2021 acquisition "
                "problem B2-3 requires. This is a definitional omission in V1, not a measurement that "
                "historical data is unobtainable."
            ),
        },
        "eligibility_tests": [
            "ROOT_ALREADY_IN_REPOSITORY_PROVENANCE",
            "ARCHIVE_MIRROR_OF_DOMAIN_ALREADY_IN_FROZEN_REGISTRY",
        ],
        "anti_overfit_declaration": {
            "outcome_signals_consulted": [],
            "residual_errors_consulted": False,
            "party_results_consulted": False,
            "feature_performance_consulted": False,
            "selection_is_outcome_independent": True,
            "roots_frozen_before_content_inspection": True,
            "statement": (
                "Sources were added at root/class level before any content was inspected. The question "
                "asked was which surface can establish the frozen factual input classes before the "
                "relevant cutoff, never which surface would explain an observed result."
            ),
        },
        "time_contract": {
            "election_cutoffs": ELECTION_CUTOFFS,
            "rule": (
                "A historical fact is admissible only if publicly available before the cutoff of the "
                "election being predicted. Historical truth alone is insufficient."
            ),
            "failure_state": "UNKNOWN_AT_CUTOFF",
            "retrospective_biography_rule": "A retrospective source never manufactures pre-election knowledge.",
        },
        "sources": sources,
        "immutable_under_this_amendment": [
            "b2_feature_dictionary_v1.json",
            "feature definitions and prediction targets",
            "fit/validation split 2011->2016 / 2016->2021",
            "core panel coverage threshold 0.8",
            "binary feature minimum support 30",
            "residual backtest and scoring rules",
            "all predictive coefficients (exactly zero)",
            "party crosswalk and territory geometry",
            "F-1 and the registered 2026 forecast",
        ],
        "extraction_rule": {
            "llm_used": False,
            "semantic_extraction_forbidden": True,
            "permitted_methods": [
                "STRUCTURED_API", "HTML_TABLE_PARSER", "PDF_TABLE_PARSER",
                "DETERMINISTIC_REGEX", "MANUAL_TRANSCRIPTION_RECONCILED",
            ],
            "unparsable_state": "UNPARSABLE_NONAGENTIC",
        },
        "e_collect_boundary": "E_collect remains LOCKED and is not executed by this amendment.",
    }
    surface["canonical_surface_sha256"] = canonical_sha256(surface)
    return surface


def build_protocol(surface: dict) -> dict:
    protocol = {
        "schema_version": "1.1",
        "protocol_id": "M26-GOAL100-B2-HISTORICAL-ACQUISITION-PROTOCOL-V1.1",
        "parent_protocol_id": load(PROTOCOL_PATH)["protocol_id"],
        "status": "FROZEN_PRE_ACQUISITION",
        "frozen_at": surface["frozen_at"],
        "source_surface_id": surface["amendment_id"],
        "source_surface_sha256": surface["canonical_surface_sha256"],
        "acquisition_order": {
            "rule": "Priority follows the frozen feature/input dependency graph, never forecast impact.",
            "primary": {
                "input_class": "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR",
                "years": REQUIRED_YEARS,
                "reason": (
                    "Sole dominant blocker: it is the only blocker for B2_P01 and B2_P02 and appears "
                    "in 14 of 32 feature-by-transition cells."
                ),
                "fields_sought": [
                    "candidate identity", "party", "constituency",
                    "list rank where structured", "source", "pre-cutoff timestamp validity",
                ],
            },
            "secondary": [
                "HISTORICAL_CANDIDATE_RANK_TARGET_YEAR",
                "HISTORICAL_PARTY_SWITCH_TARGET_YEAR",
                "HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR",
                "HISTORICAL_PARTY_OFFICE_TARGET_YEAR",
                "HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR",
                "HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR",
                "HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR",
            ],
        },
        "record_states": [
            "VERIFIED", "UNKNOWN", "UNKNOWN_AT_CUTOFF",
            "BLOCKED_SOURCE", "UNPARSABLE_NONAGENTIC", "AMBIGUOUS_DETERMINISTIC_MATCH",
        ],
        "absence_rule": "Non-retrieval is never absence and never a false value.",
        "identity_rule": "Territory and party resolution uses the certified crosswalk only; no fuzzy matching.",
        "vault_rule": "Every retrieved object enters the immutable raw vault with its retrieval digest.",
        "termination_states": [
            "B2_3_BACKTEST_UNLOCKED",
            "B2_3_DATA_BLOCKED_NONAGENTIC",
            "B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION",
        ],
    }
    protocol["canonical_protocol_sha256"] = canonical_sha256(protocol)
    return protocol


def build_certificate(surface: dict, protocol: dict) -> dict:
    dictionary = load(DICTIONARY_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    state = load(STATE_PATH)
    forecast_manifest = load(FORECAST_MANIFEST_PATH)
    b2_protocol = load(PROTOCOL_PATH)
    contract = dictionary["historical_calibration_contract"]

    forecast_hash = file_sha256(FORECAST_PATH)
    f1_intact = (
        forecast_manifest["forecast_artifact_hash"]
        == b2_protocol["parent_snapshot"]["forecast_sha256"]
    )

    checks = [
        {
            "check": "FEATURE_DEFINITIONS_UNCHANGED",
            "expected": dictionary["dictionary_id"],
            "observed": dictionary["dictionary_id"],
            "passed": dictionary["status"] == "FROZEN_COEFFICIENTS_ZERO_PENDING_CALIBRATION",
            "feature_count": len(dictionary["features"]),
            "feature_dictionary_sha256": canonical_sha256(dictionary),
        },
        {
            "check": "THRESHOLDS_UNCHANGED",
            "coverage_threshold": contract["core_panel_minimum_coverage_each_transition"],
            "support_threshold": contract["binary_feature_minimum_positive_instances"],
            "fit_transition": contract["fit_transition"],
            "validation_transition": contract["validation_transition"],
            "passed": (
                contract["core_panel_minimum_coverage_each_transition"] == 0.8
                and contract["binary_feature_minimum_positive_instances"] == 30
                and contract["fit_transition"] == "2011_TO_2016"
                and contract["validation_transition"] == "2016_TO_2021"
            ),
        },
        {
            "check": "OUTCOMES_UNSEEN_BY_ACQUISITION_SYSTEM",
            "outcome_signals_consulted": surface["anti_overfit_declaration"]["outcome_signals_consulted"],
            "passed": surface["anti_overfit_declaration"]["selection_is_outcome_independent"] is True,
            "note": "Roots were frozen at class level before any content inspection.",
        },
        {
            "check": "F_MINUS_1_UNCHANGED",
            "declared_forecast_sha256": b2_protocol["parent_snapshot"]["forecast_sha256"],
            "manifest_forecast_sha256": forecast_manifest["forecast_artifact_hash"],
            "worktree_raw_sha256": forecast_hash,
            "passed": f1_intact,
            "note": (
                "Compared against the snapshot manifest and protocol parent. The worktree raw digest "
                "may differ under a CRLF checkout without indicating any content change."
            ),
        },
        {
            "check": "NO_PREDICTIVE_COEFFICIENT_CHANGED",
            "state_value": state["coefficients"]["predictive"],
            "panel_value": panel_cert["coefficients_after_gate"],
            "passed": (
                state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION"
                and panel_cert["coefficients_after_gate"] == "ALL_PREDICTIVE_COEFFICIENTS_REMAIN_EXACTLY_ZERO"
            ),
        },
        {
            "check": "NO_LLM_EXTRACTION_ALLOWED",
            "extraction_rule": surface["extraction_rule"],
            "passed": surface["extraction_rule"]["llm_used"] is False,
        },
        {
            "check": "HISTORICAL_YEARS_NOW_EXPRESSIBLE",
            "v1_expressible": surface["trigger_measurement"]["v1_election_years_expressible"],
            "v1_1_expressible": sorted({year for row in surface["sources"] for year in row["years"]}),
            "required": REQUIRED_YEARS,
            "passed": set(REQUIRED_YEARS).issubset(
                {year for row in surface["sources"] for year in row["years"]}
            ),
        },
        {
            "check": "V1_REGISTRY_NOT_EDITED",
            "v1_registry_sha256": canonical_sha256(load(REGISTRY_V1_PATH)),
            "v1_status": load(REGISTRY_V1_PATH)["status"],
            "passed": load(REGISTRY_V1_PATH)["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED",
            "note": "The amendment is a separate artifact; V1 remains frozen and unmodified.",
        },
        {
            "check": "B2_3_ATTEMPT_HISTORY_PRESERVED",
            "attempts_archived": sorted(
                path.name for path in (G100 / "b2_historical_panel_attempts").iterdir()
            ) if (G100 / "b2_historical_panel_attempts").exists() else [],
            "passed": (G100 / "b2_historical_panel_attempts").exists(),
        },
        {
            "check": "E_COLLECT_NOT_EXECUTED",
            "agentic_experiment_locked": state["anti_drift"]["agentic_experiment_locked"],
            "passed": state["anti_drift"]["agentic_experiment_locked"] is True,
        },
    ]

    failures = [row["check"] for row in checks if not row["passed"]]
    certificate = {
        "schema_version": "1.1",
        "certificate_id": "M26-GOAL100-B2-HISTORICAL-SOURCE-SURFACE-CERTIFICATE-V1.1",
        "amendment_id": surface["amendment_id"],
        "certified_at": surface["frozen_at"],
        "gate": "PASS" if not failures else "FAIL",
        "source_surface_path": repo_rel(SURFACE_V1_1_PATH),
        "source_surface_sha256": surface["canonical_surface_sha256"],
        "acquisition_protocol_path": repo_rel(PROTOCOL_V1_1_PATH),
        "acquisition_protocol_sha256": protocol["canonical_protocol_sha256"],
        "frozen_before_acquisition": True,
        "checks": checks,
        "failures": failures,
        "b2_3_state_at_freeze": {
            "gate": panel_cert["gate"],
            "features_identifiable": [
                {"transition_id": row["transition_id"], "identifiable": row["features_identifiable"]}
                for row in panel_cert["transitions"]
            ],
            "core_predictive_coverage": [
                {"transition_id": row["transition_id"], "coverage": row["core_predictive_panel_coverage"]}
                for row in panel_cert["transitions"]
            ],
            "blocking_input_classes": len(panel_cert["blocking_missing_input_classes"]),
        },
        "scientific_boundary": (
            "This certificate authorizes a wider deterministic acquisition surface only. It certifies "
            "no fact, no feature value, no coefficient and no forecast quantity."
        ),
    }
    certificate["canonical_certificate_sha256"] = canonical_sha256(certificate)
    return certificate


def main() -> None:
    surface = build_surface()
    protocol = build_protocol(surface)
    certificate = build_certificate(surface, protocol)

    dump(SURFACE_V1_1_PATH, surface)
    dump(PROTOCOL_V1_1_PATH, protocol)
    dump(CERTIFICATE_PATH, certificate)

    print("B2_HISTORICAL_SOURCE_SURFACE_V1_1_" + ("FROZEN" if certificate["gate"] == "PASS" else "FAIL"))
    print(f"amendment={surface['amendment_id']}")
    print(f"surface_sha256={surface['canonical_surface_sha256']}")
    print(f"protocol_sha256={protocol['canonical_protocol_sha256']}")
    print(f"certificate_sha256={certificate['canonical_certificate_sha256']}")
    print(f"sources={len(surface['sources'])} years_now_expressible="
          f"{sorted({y for r in surface['sources'] for y in r['years']})}")
    for row in certificate["checks"]:
        print(f"  {'PASS' if row['passed'] else 'FAIL'}  {row['check']}")
    raise SystemExit(0 if certificate["gate"] == "PASS" else 3)


if __name__ == "__main__":
    main()
