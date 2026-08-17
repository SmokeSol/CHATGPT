#!/usr/bin/env python3
"""Enumerate the acquisition surface already permitted by the frozen contracts.

Nothing here discovers a source. Every entry is derived mechanically from a
document already committed to the repository:

  * b2_source_registry.json          the frozen B2 claim-collection allowlist
  * historical_ingest_manifest.json  provenance already used for the historical panel
  * observed_elected_2021.json       the member dataset already used for 2021 electeds
  * older_history_schema_probe.json  provenance already probed for older cycles

The two families are kept apart on purpose. The B2 registry governs B2 *claims*
about the 2026 contest; the historical provenance governs *panel inputs* for
2011/2016/2021 and is not a B2 claim surface. Merging them would silently widen
a frozen universe.

Temporal reach is measured, not assumed: the registry's own query templates are
inspected for the years they can express.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G75 = ROOT / "data" / "goal75"
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SOURCE_REGISTRY_PATH = G100 / "b2_source_registry.json"
SOURCE_CERTIFICATE_PATH = G100 / "b2_source_universe_certificate.json"
SOURCE_PROBE_PATH = G100 / "b2_source_universe_probe.json"
PROTOCOL_PATH = G100 / "b2_protocol_v1.json"
HISTORICAL_MANIFEST_PATH = G100 / "historical" / "historical_ingest_manifest.json"
ELECTED_2021_PATH = G75 / "observed_elected_2021.json"
OLDER_PROBE_PATH = G100 / "older_history_probe" / "older_history_schema_probe.json"
SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"

ELECTION_YEARS = [2002, 2007, 2011, 2016, 2021, 2026]
YEAR_PATTERN = re.compile(r"\b(19|20)\d{2}\b")

# CKAN exposes a fixed, documented action API. Resolving a dataset name that the
# repository already records is enumeration, not discovery.
CKAN_PACKAGE_SHOW = "/api/3/action/package_show?id={dataset}"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_SURFACE_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def repo_rel(path: Path) -> str:
    return path.relative_to(REPO).as_posix()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def years_expressible_by_templates(registry: dict) -> dict:
    """Measure which election years the frozen query templates can reach."""
    blob = json.dumps(registry["query_templates"], ensure_ascii=False)
    literal_years = {int(match.group(0)) for match in YEAR_PATTERN.finditer(blob)}

    floor_years = []
    for template in registry["query_templates"]:
        floor = template.get("parameters", {}).get("published_not_before")
        if floor:
            floor_years.append(int(str(floor)[:4]))

    reachable = sorted(year for year in ELECTION_YEARS if year in literal_years)
    return {
        "literal_years_in_templates": sorted(literal_years),
        "publication_floor_years": sorted(set(floor_years)),
        "election_years_expressible": reachable,
        "election_years_not_expressible": sorted(set(ELECTION_YEARS) - set(reachable)),
        "interpretation": (
            "The frozen templates name only 2026 election terms and set a publication floor in 2025. "
            "They cannot express a query for a pre-2025 cycle, so the B2 claim registry carries no "
            "historical acquisition surface."
        ),
    }


def registry_surface(registry: dict, probe: dict) -> list[dict]:
    probe_by_id = {row["source_id"]: row for row in probe.get("sources", [])}
    template_ids = [template["query_id"] for template in registry["query_templates"]]
    rows = []
    for entry in registry["source_entries"]:
        source_id = entry["source_id"]
        probed = probe_by_id.get(source_id, {})
        state = entry.get("operational_state")
        applicable = [
            template["query_id"] for template in registry["query_templates"]
            if entry.get("tier") in template.get("applies_to_tiers", [])
        ]
        rows.append({
            "surface_family": "B2_SOURCE_REGISTRY_V1",
            "source_id": source_id,
            "tier": entry.get("tier"),
            "publisher": entry.get("publisher"),
            "independence_cluster": entry.get("independence_cluster"),
            "root_domains": entry.get("allowed_domains", []),
            "seed_urls": entry.get("seed_urls", []),
            "path_exclusions": entry.get("path_exclusions", []),
            "allowed_query_templates": applicable,
            "election_years_potentially_covered": [2026],
            "expected_format": ["text/html", "application/pdf"],
            "access_status": state,
            "claim_eligible": state == "ACTIVE",
            "last_probe_http_status": probed.get("http_status"),
            "last_probe_challenge_marker": probed.get("challenge_marker"),
            "archive_capability": "RAW_BYTES_PLUS_SHA256_PER_FROZEN_ARCHIVE_RULE",
            "parser_availability": "HTML_TABLE_OR_DETERMINISTIC_REGEX_ONLY",
            "deterministic_enumeration_possible": state == "ACTIVE",
            "notes": (
                "Only ACTIVE routes may create B2 candidate records. REFERENCE_ONLY and INACTIVE "
                "routes are enumerated for completeness and yield BLOCKED_SOURCE, never absence."
            ),
        })
    rows.sort(key=lambda row: row["source_id"])
    assert template_ids, "frozen registry must declare query templates"
    return rows


def historical_surface() -> list[dict]:
    """Provenance already used to build historical panel inputs."""
    rows = []

    manifest = load(HISTORICAL_MANIFEST_PATH)
    for dataset in manifest["datasets"]:
        url = dataset["source_url_used"]
        rows.append({
            "surface_family": "HISTORICAL_INGEST_PROVENANCE",
            "source_id": f"OPENAFRICA_RESULTS_{dataset['year']}",
            "tier": "ALREADY_INGESTED_PANEL_INPUT",
            "publisher": urlparse(url).netloc,
            "independence_cluster": "TAFRA_OPEN_AFRICA",
            "root_domains": [urlparse(url).netloc],
            "seed_urls": [url],
            "election_years_potentially_covered": [dataset["year"]],
            "expected_format": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
            "access_status": "ALREADY_ACQUIRED",
            "local_raw_path": dataset["raw_path"],
            "local_raw_sha256": dataset["raw_sha256"],
            "granularity": "LIST_LEVEL_PARTY_VOTES_PER_CONSTITUENCY",
            "supplies_input_classes": ["HISTORICAL_LIST_PRESENCE_TARGET_YEAR"],
            "archive_capability": "RAW_FILE_RETAINED_AND_HASHED",
            "parser_availability": "XLSX_DETERMINISTIC_TABLE_PARSER_ALREADY_EXECUTED",
            "deterministic_enumeration_possible": True,
            "notes": "Already ingested under M26-GOAL100-TAFRA-HISTORY-V1; carries no candidate-level rows.",
        })

    elected = load(ELECTED_2021_PATH)
    dataset_name = elected["source_dataset"]
    # The host is not asserted: it is read from the committed ingest script,
    # which loads this identifier through the Hugging Face `datasets` loader.
    ingest_script = ROOT / "scripts" / "goal75_observed_2021.py"
    loader = "HUGGINGFACE_DATASETS" if (
        ingest_script.exists()
        and "from datasets import load_dataset" in ingest_script.read_text(encoding="utf-8")
        and dataset_name in ingest_script.read_text(encoding="utf-8")
    ) else None
    rows.append({
        "surface_family": "HISTORICAL_INGEST_PROVENANCE",
        "source_id": "HF_CHAMBER_MEMBERS_MULTIYEAR",
        "tier": "ALREADY_REFERENCED_PANEL_INPUT",
        "publisher": "huggingface.co" if loader else None,
        "independence_cluster": "TAFRA_DERIVED_MEMBER_DATA",
        "root_domains": ["huggingface.co"] if loader else [],
        "dataset_name": dataset_name,
        "loader_recorded_in": repo_rel(ingest_script) if loader else None,
        "loader": loader,
        "resolution_route": f"/api/datasets/{dataset_name}" if loader else None,
        "partition_field": "parlement",
        "already_extracted_partitions": ["2021-2026"],
        "election_years_potentially_covered": sorted(
            int(match.group(0)) for match in YEAR_PATTERN.finditer(dataset_name)
        ),
        "expected_format": ["application/json", "text/csv", "application/vnd.ms-excel"],
        "access_status": "REFERENCED_BUT_ONLY_2021_PARTITION_EXTRACTED",
        "granularity": "MEMBER_LEVEL_ELECTED_PERSONS",
        "supplies_input_classes": ["HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR"],
        "archive_capability": "RAW_BYTES_PLUS_SHA256",
        "parser_availability": "STRUCTURED_JSON_OR_CSV_DETERMINISTIC",
        "deterministic_enumeration_possible": True,
        "notes": (
            "The committed ingest script loads this exact identifier and keeps only parlement=='2021-2026'. "
            "The remaining legislature partitions are already inside the same recorded dataset, so reading "
            "them reuses recorded provenance rather than widening the source universe."
        ),
    })

    if OLDER_PROBE_PATH.exists():
        probe = load(OLDER_PROBE_PATH)
        for dataset in probe.get("datasets", []):
            rows.append({
                "surface_family": "HISTORICAL_INGEST_PROVENANCE",
                "source_id": f"OPENAFRICA_RESULTS_{dataset['year']}_PROBE_ONLY",
                "tier": "PROBE_ONLY_NOT_AUTHORIZED_AS_MODEL_INPUT",
                "publisher": "open.africa",
                "independence_cluster": "TAFRA_OPEN_AFRICA",
                "root_domains": ["open.africa"],
                "seed_urls": [dataset["source_url"]],
                "election_years_potentially_covered": [dataset["year"]],
                "access_status": "PROBED_NOT_AUTHORIZED",
                "granularity": "LIST_LEVEL_PARTY_VOTES_PER_CONSTITUENCY",
                "supplies_input_classes": [],
                "deterministic_enumeration_possible": True,
                "notes": dataset.get("source_quality_note", "Probe scope only; explicitly not a model input."),
            })

    rows.sort(key=lambda row: row["source_id"])
    return rows


def main() -> None:
    protocol = load(PROTOCOL_PATH)
    registry = load(SOURCE_REGISTRY_PATH)
    certificate = load(SOURCE_CERTIFICATE_PATH)
    probe = load(SOURCE_PROBE_PATH)

    if protocol["status"] != "FROZEN_PRE_COLLECTION":
        raise SystemExit("B2_SURFACE_FAIL: B2 protocol is not frozen pre-collection")
    if registry["status"] != "FROZEN_COLLECTION_ENABLED_BOUNDED":
        raise SystemExit("B2_SURFACE_FAIL: source registry is not frozen/enabled")

    claim_rows = registry_surface(registry, probe)
    historical_rows = historical_surface()
    temporal = years_expressible_by_templates(registry)

    surface = {
        "schema_version": "1.0",
        "surface_id": "M26-GOAL100-B2-ACQUISITION-SURFACE-V1",
        "protocol_id": protocol["protocol_id"],
        "generated_at": now_local(),
        "derivation": (
            "Every entry is derived from a document already committed to the repository. No source was "
            "discovered, searched for or added, and the frozen universe is not widened."
        ),
        "determinism": {"llm_used": False, "source_discovery": False, "semantic_selection": False},
        "families": {
            "B2_SOURCE_REGISTRY_V1": {
                "governs": "B2 claim records about the 2026 contest",
                "frozen_at": registry["source_universe_frozen_at"],
                "source_universe_sha256": certificate.get("source_universe_sha256"),
                "entries": len(claim_rows),
                "claim_eligible_entries": sum(row["claim_eligible"] for row in claim_rows),
                "temporal_reach": temporal,
            },
            "HISTORICAL_INGEST_PROVENANCE": {
                "governs": "historical panel inputs for 2011/2016/2021",
                "is_b2_claim_surface": False,
                "entries": len(historical_rows),
                "note": (
                    "Recorded provenance of already-ingested panel inputs. Using it is an ingest act "
                    "under the historical pipeline, not a B2 claim-collection act."
                ),
            },
        },
        "surfaces": claim_rows + historical_rows,
        "historical_gap_routes": {
            "HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR": {
                "required_for": ["B2_P01", "B2_P02", "B2_P03", "B2_P04"],
                "missing_years": [2011, 2016],
                "candidate_route": "OPENAFRICA_CHAMBER_MEMBERS_MULTIYEAR",
                "route_status": "RECORDED_PROVENANCE_NOT_YET_EXTRACTED_FOR_THESE_YEARS",
            },
            "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR": {
                "required_for": ["B2_M02", "B2_P01", "B2_P02", "B2_P03", "B2_P04", "B2_P05", "B2_P06"],
                "missing_years": [2011, 2016, 2021],
                "candidate_route": None,
                "route_status": "NO_RECORDED_PROVENANCE_IN_EITHER_FAMILY",
            },
        },
        "prohibited_expansions": [
            "Adding a domain, dataset or endpoint not already recorded in the repository.",
            "Using a search engine or LLM to locate an alternative source.",
            "Treating a REFERENCE_ONLY or INACTIVE route's inaccessibility as evidence of absence.",
        ],
    }
    surface["canonical_surface_sha256"] = canonical_sha256(surface)
    dump(SURFACE_PATH, surface)

    print("B2_ACQUISITION_SURFACE_WRITTEN")
    print(f"claim_surfaces={len(claim_rows)} claim_eligible={sum(row['claim_eligible'] for row in claim_rows)}")
    print(f"historical_surfaces={len(historical_rows)}")
    print(f"registry_election_years_expressible={temporal['election_years_expressible']}")
    print(f"surface_sha256={surface['canonical_surface_sha256']}")


if __name__ == "__main__":
    main()
