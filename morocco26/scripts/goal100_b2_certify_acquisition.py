#!/usr/bin/env python3
"""Certify what deterministic acquisition actually recovered, and why the rest is missing.

The decomposition is the point. "Missing" is never one thing, and the five
outcomes below have different scientific consequences:

  DATA_EXISTS_AND_PARSED                 recovered deterministically
  DATA_EXISTS_BUT_UNPARSABLE_NONAGENTIC  present in the corpus, needs semantic reading
  SOURCE_INACCESSIBLE                    access refused; says nothing about existence
  SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA   no permitted surface carries this input
  DETERMINISTIC_IDENTITY_UNRESOLVED      retrieved, but no certified identifier matches

Only the second category is a candidate for a later E_collect experiment, and
only the fourth licenses saying the frozen universe is exhausted.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"
RAW_MANIFEST_PATH = G100 / "b2_raw_acquisition_manifest.json"
PARSER_MANIFEST_PATH = G100 / "b2_parser_manifest.json"
MEMBERS_PATH = G100 / "historical" / "b2_historical_elected_members.json"
PANEL_PATH = G100 / "b2_historical_panel.json"
PANEL_CERT_PATH = G100 / "b2_historical_panel_certificate.json"
HISTORICAL_CERT_PATH = G100 / "b2_historical_acquisition_certificate.json"
WAVE1_CERT_PATH = G100 / "b2_current_wave1_acquisition_certificate.json"

TRANSITION_PRIOR_YEARS = [2011, 2016]
TRANSITION_TARGET_YEARS = [2016, 2021]


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_ACQ_CERT_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def classify_input_classes(panel: dict, surface: dict, raw: dict) -> list[dict]:
    """One verdict per declared historical input class, from measured artifacts."""
    inventory = panel["input_inventory"]
    supplied = {
        cls
        for row in surface["surfaces"]
        for cls in row.get("supplies_input_classes", []) or []
    }
    blocked_sources = {
        row["source_id"] for row in raw.get("entries", [])
        if row.get("state") == "BLOCKED_SOURCE"
    }
    surface_by_class: dict[str, list[str]] = {}
    for row in surface["surfaces"]:
        for cls in row.get("supplies_input_classes", []) or []:
            surface_by_class.setdefault(cls, []).append(row["source_id"])

    results = []
    for input_class in sorted(inventory):
        entry = inventory[input_class]
        years = set(entry.get("available_years") or [])
        needed_years = set(
            TRANSITION_PRIOR_YEARS if input_class.endswith("_PRIOR_YEAR") else TRANSITION_TARGET_YEARS
        )
        covered = sorted(needed_years & years)
        missing_years = sorted(needed_years - years)

        if not missing_years:
            verdict = "DATA_EXISTS_AND_PARSED"
            reason = "Every year required by the frozen transitions is present and parsed deterministically."
        elif input_class in supplied:
            routes = sorted(set(surface_by_class.get(input_class, [])))
            inaccessible = [route for route in routes if route in blocked_sources]
            if inaccessible:
                verdict = "SOURCE_INACCESSIBLE"
                reason = f"Permitted routes exist but access was refused: {inaccessible}."
            else:
                verdict = "DATA_EXISTS_BUT_UNPARSABLE_NONAGENTIC"
                reason = "A permitted route carries this class but no deterministic parser recovers the required years."
        else:
            verdict = "SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA"
            reason = (
                "No surface in either permitted family declares this input class. The frozen B2 registry "
                "is 2026-scoped and the historical provenance carries no such dataset."
            )

        results.append({
            "input_class": input_class,
            "years_required": sorted(needed_years),
            "years_available": sorted(years),
            "years_covered": covered,
            "years_missing": missing_years,
            "permitted_routes": sorted(set(surface_by_class.get(input_class, []))),
            "verdict": verdict,
            "reason": reason,
        })
    return results


def identity_unresolved(members: dict | None) -> dict:
    if not members:
        return {"available": False}
    rows = []
    for year_key, entry in sorted(members["years"].items(), key=lambda item: int(item[0])):
        unresolved = [row for row in entry["rows"] if row.get("territory_id") is None]
        labels = Counter(row["source_label"] for row in unresolved)
        rows.append({
            "election_year": int(year_key),
            "rows_total": entry["elected_rows"],
            "rows_unresolved": len(unresolved),
            "distinct_unresolved_labels": len(labels),
            "top_labels": [{"label": label, "count": count} for label, count in labels.most_common(3)],
            "interpretation": (
                "Non-territorial national-list seats carry no certified constituency and are correctly "
                "left unresolved."
                if len(labels) == 1 and "national" in next(iter(labels)).casefold()
                else "Labels belong to an older territorial geometry and resolve to no certified identifier."
            ),
        })
    return {"available": True, "by_year": rows}


def historical_certificate() -> dict:
    surface = load(SURFACE_PATH)
    panel = load(PANEL_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    raw = load(RAW_MANIFEST_PATH) if RAW_MANIFEST_PATH.exists() else {"entries": []}
    parsers = load(PARSER_MANIFEST_PATH) if PARSER_MANIFEST_PATH.exists() else {"parsers": []}
    members = load(MEMBERS_PATH) if MEMBERS_PATH.exists() else None

    classes = classify_input_classes(panel, surface, raw)
    tally = Counter(row["verdict"] for row in classes)

    recovered = [row["input_class"] for row in classes if row["verdict"] == "DATA_EXISTS_AND_PARSED"]
    unparsable = [row["input_class"] for row in classes if row["verdict"] == "DATA_EXISTS_BUT_UNPARSABLE_NONAGENTIC"]
    inaccessible = [row["input_class"] for row in classes if row["verdict"] == "SOURCE_INACCESSIBLE"]
    absent = [row["input_class"] for row in classes if row["verdict"] == "SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA"]

    predictive_ready = panel_cert["predictive_sub_panel"] == "PASS"
    if predictive_ready:
        outcome = "A_COVERAGE_REACHED_BACKTEST_UNLOCKED"
    elif unparsable or inaccessible:
        outcome = "B_DATA_BLOCKED_NONAGENTIC"
    else:
        outcome = "C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL"

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-HISTORICAL-ACQUISITION-CERTIFICATE-V1",
        "certified_at": now_local(),
        "surface_sha256": surface["canonical_surface_sha256"],
        "panel_sha256": panel["canonical_panel_sha256"],
        "determinism": {"llm_used": False, "source_discovery": False, "semantic_selection": False},
        "acquisition_runs": raw.get("runs", []),
        "parsers": parsers.get("parsers", []),
        "recovered_this_phase": {
            "input_classes": recovered,
            "elected_member_years": (
                sorted(int(year) for year in members["years"]) if members else []
            ),
            "elected_local_territories_by_year": (
                {
                    year: entry["local_territories_resolved"]
                    for year, entry in sorted(members["years"].items(), key=lambda item: int(item[0]))
                }
                if members else {}
            ),
        },
        "input_class_verdicts": classes,
        "verdict_tally": dict(sorted(tally.items())),
        "deterministic_identity_unresolved": identity_unresolved(members),
        "blocking_for_predictive_family": sorted({
            cls
            for transition in panel["transitions"]
            for feature in transition["features"]
            if feature["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION"
            for cls in feature["missing_inputs"]
        }),
        "decision_gate": {
            "outcome": outcome,
            "predictive_sub_panel": panel_cert["predictive_sub_panel"],
            "core_predictive_coverage": [
                {"transition_id": row["transition_id"], "coverage": row["core_predictive_panel_coverage"]}
                for row in panel_cert["transitions"]
            ],
            "residual_backtest_unlocked": predictive_ready,
            "blocking_machine_gate": None if predictive_ready else "B2-3-HISTORICAL-FEATURE-PANEL",
            "classification_rule": (
                "Zero coverage from absent inputs is UNIDENTIFIABLE, never a non-predictive finding. "
                "Only a executed residual backtest may classify a feature as non-predictive."
            ),
        },
        "reserved_for_e_collect": {
            "policy": "Unresolved cells are preserved, not filled by agentic research.",
            "input_classes": sorted(set(unparsable) | set(inaccessible) | set(absent)),
            "rationale": (
                "These are exactly the cells deterministic B2 could not recover. They form the controlled "
                "test set for a later E_collect experiment comparing agentic retrieval against this baseline."
            ),
        },
        "coefficients_after_certificate": "ALL_PREDICTIVE_COEFFICIENTS_REMAIN_EXACTLY_ZERO",
    }
    certificate["canonical_certificate_sha256"] = canonical_sha256(certificate)
    return certificate


TABLE_PATTERN = re.compile(r"<table.*?</table>", re.S | re.I)
ROW_PATTERN = re.compile(r"<tr", re.I)


def frozen_evidence_terms() -> list[str]:
    """The registry's own Q03 vocabulary. A dictionary match, not a judgment."""
    registry = load(G100 / "b2_source_registry.json")
    for template in registry["query_templates"]:
        groups = template.get("parameters", {}).get("fixed_evidence_term_groups")
        if groups:
            return sorted({term for group in groups for term in group})
    return []


def format_inventory(raw: dict) -> dict:
    """Measure, structurally, what a non-agentic parser could read in the corpus.

    A table whose text contains a frozen evidence term is a *candidate* for
    deterministic extraction. It is not evidence, and nothing here reads meaning
    from the page.
    """
    terms = frozen_evidence_terms()
    by_source: dict[str, dict] = {}
    parsable = []
    for row in raw.get("entries", []):
        if row.get("state") != "ACQUIRED" or not row.get("stored_path"):
            continue
        path = REPO / row["stored_path"]
        if not path.exists():
            continue
        bucket = by_source.setdefault(row["source_id"], {
            "documents": 0, "tables": 0, "tables_matching_frozen_terms": 0,
            "largest_matching_table_rows": 0, "content_types": set(),
        })
        bucket["documents"] += 1
        bucket["content_types"].add((row.get("content_type") or "").split(";")[0])
        text = path.read_bytes()[:3_000_000].decode("utf-8", "ignore")
        for index, table in enumerate(TABLE_PATTERN.findall(text)):
            bucket["tables"] += 1
            lowered = table.lower()
            matched = sorted({term for term in terms if term.lower() in lowered})
            if not matched:
                continue
            rows = len(ROW_PATTERN.findall(lowered))
            bucket["tables_matching_frozen_terms"] += 1
            bucket["largest_matching_table_rows"] = max(bucket["largest_matching_table_rows"], rows)
            parsable.append({
                "source_id": row["source_id"],
                "stored_path": row["stored_path"],
                "table_index": index,
                "table_rows": rows,
                "matched_frozen_terms": matched,
                "extraction_status": "DETERMINISTICALLY_PARSABLE_TABLE_PENDING_GATE_B2_4",
            })
    for bucket in by_source.values():
        bucket["content_types"] = sorted(value for value in bucket["content_types"] if value)
    parsable.sort(key=lambda item: (item["source_id"], item["table_index"]))
    return {
        "frozen_evidence_terms_used": terms,
        "method": "STRUCTURAL_COUNT_PLUS_FROZEN_DICTIONARY_MATCH",
        "llm_used": False,
        "by_source": dict(sorted(by_source.items())),
        "deterministically_parsable_tables": parsable,
        "interpretation": (
            "A matching table means a deterministic parser could read it. It does not mean a claim "
            "exists: the frozen critical-double-entry rule still requires two matching parses or one "
            "authoritative T0 structured table, and a T1 party page is not authoritative."
        ),
    }


def vault_integrity(raw: dict) -> dict:
    """Re-hash every archived object against the digest recorded at retrieval.

    This is the check that catches a checkout mangling the archive: any
    line-ending translation of a stored document changes its bytes and is
    reported here rather than silently accepted.
    """
    checked = matched = missing = mismatched = 0
    failures = []
    for row in raw.get("entries", []):
        stored = row.get("stored_path")
        if not stored or not row.get("sha256"):
            continue
        checked += 1
        path = REPO / stored
        if not path.exists():
            missing += 1
            failures.append({"stored_path": stored, "problem": "MISSING_FROM_VAULT"})
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual == row["sha256"]:
            matched += 1
        else:
            mismatched += 1
            failures.append({
                "stored_path": stored,
                "problem": "BYTES_DIFFER_FROM_RETRIEVAL_DIGEST",
                "recorded_sha256": row["sha256"],
                "actual_sha256": actual,
            })
    return {
        "objects_checked": checked,
        "objects_matching_retrieval_digest": matched,
        "objects_missing": missing,
        "objects_mismatched": mismatched,
        "verdict": "INTACT" if checked and not (missing or mismatched) else "DEGRADED",
        "failures": failures[:20],
        "note": (
            "The vault is declared binary in .gitattributes. A mismatch usually means a checkout "
            "translated line endings and corrupted the archived bytes."
        ),
    }


def wave1_certificate() -> dict:
    surface = load(SURFACE_PATH)
    raw = load(RAW_MANIFEST_PATH) if RAW_MANIFEST_PATH.exists() else {"entries": [], "runs": []}

    registry_ids = {
        row["source_id"] for row in surface["surfaces"]
        if row["surface_family"] == "B2_SOURCE_REGISTRY_V1"
    }
    entries = [row for row in raw.get("entries", []) if row.get("source_id") in registry_ids]

    per_source = {}
    for row in entries:
        bucket = per_source.setdefault(row["source_id"], Counter())
        bucket[row.get("state") or "UNKNOWN"] += 1

    inventory = format_inventory(raw)
    claim_eligible = {
        row["source_id"] for row in surface["surfaces"]
        if row["surface_family"] == "B2_SOURCE_REGISTRY_V1" and row.get("claim_eligible")
    }
    attempted = sorted(per_source)
    acquired_sources = sorted(sid for sid, counts in per_source.items() if counts.get("ACQUIRED"))
    blocked_sources = sorted(sid for sid, counts in per_source.items() if not counts.get("ACQUIRED"))

    certificate = {
        "schema_version": "1.0",
        "certificate_id": "M26-GOAL100-B2-WAVE1-ACQUISITION-CERTIFICATE-V1",
        "certified_at": now_local(),
        "surface_sha256": surface["canonical_surface_sha256"],
        "scope": "2026 contest; frozen B2 source registry V1 only",
        "determinism": {"llm_used": False, "source_discovery": False, "semantic_selection": False},
        "query_templates_used": ["Q01_FIXED_SEED", "Q02_SITEMAP_PROBE"],
        "sources_in_registry": len(registry_ids),
        "sources_claim_eligible": len(claim_eligible),
        "sources_attempted": len(attempted),
        "sources_with_acquired_content": acquired_sources,
        "sources_without_acquired_content": blocked_sources,
        "per_source_states": {sid: dict(sorted(counts.items())) for sid, counts in sorted(per_source.items())},
        "documents_acquired": sum(row.get("state") == "ACQUIRED" for row in entries),
        "documents_blocked": sum(row.get("state") == "BLOCKED_SOURCE" for row in entries),
        "documents_error": sum(row.get("state") == "FETCH_ERROR" for row in entries),
        "b2_claim_records_created": 0,
        "claim_creation_policy": (
            "Acquisition stores raw documents only. A B2 claim record additionally requires a "
            "deterministic parser, critical double entry and the frozen verification rule; no parser for "
            "2026 candidate rosters exists, so this phase creates zero claims."
        ),
        "absence_rule": "BLOCKED_SOURCE and FETCH_ERROR describe access, never absence or a false value.",
        "structured_states_available": [
            "VERIFIED", "UNKNOWN", "BLOCKED_SOURCE", "UNPARSABLE_NONAGENTIC", "AMBIGUOUS_DETERMINISTIC_MATCH",
        ],
        "vault_integrity": vault_integrity(raw),
        "format_inventory": inventory,
        "extractability_summary": {
            "documents_with_parsable_candidate_tables": len({
                row["stored_path"] for row in inventory["deterministically_parsable_tables"]
            }),
            "sources_with_parsable_candidate_tables": sorted({
                row["source_id"] for row in inventory["deterministically_parsable_tables"]
            }),
            "largest_parsable_table_rows": max(
                (row["table_rows"] for row in inventory["deterministically_parsable_tables"]), default=0
            ),
            "verdict": (
                "DETERMINISTIC_ROSTER_SURFACE_EXISTS_FOR_2026"
                if inventory["deterministically_parsable_tables"]
                else "NO_DETERMINISTIC_ROSTER_SURFACE_FOUND_IN_ACQUIRED_2026_CORPUS"
            ),
        },
        "environment": (raw.get("runs") or [{}])[-1].get("environment"),
    }
    certificate["canonical_certificate_sha256"] = canonical_sha256(certificate)
    return certificate


def main() -> None:
    historical = historical_certificate()
    dump(HISTORICAL_CERT_PATH, historical)
    wave1 = wave1_certificate()
    dump(WAVE1_CERT_PATH, wave1)

    print("B2_ACQUISITION_CERTIFIED")
    print(f"outcome={historical['decision_gate']['outcome']}")
    print(f"recovered={historical['recovered_this_phase']['input_classes']}")
    for verdict, count in historical["verdict_tally"].items():
        print(f"  {verdict:<38} {count}")
    print(f"blocking_predictive={historical['blocking_for_predictive_family']}")
    print(f"wave1 acquired={wave1['documents_acquired']} blocked={wave1['documents_blocked']} "
          f"claims={wave1['b2_claim_records_created']}")


if __name__ == "__main__":
    main()
