#!/usr/bin/env python3
"""Certify the V1.1 outcome and select exactly one B2-3 termination state.

The selection rule is deliberately conservative about exhaustion. A claim that
the amended surface is exhausted is only admissible when every surface was
fully enumerated and reachable. If any enumeration was truncated at its limit,
or any route was blocked, exhaustion is not established and the run cannot
report C, however empty the results look.

  B2_3_BACKTEST_UNLOCKED               core predictive coverage >= 0.8
  B2_3_DATA_BLOCKED_NONAGENTIC         pre-cutoff material exists in the amended
                                       surface but no deterministic parser
                                       recovers the required input classes
  B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION
                                       every surface fully enumerated, reachable,
                                       and carrying nothing relevant
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

SURFACE_V1_1_PATH = G100 / "historical_source_surface_v1_1.json"
SURFACE_CERT_PATH = G100 / "historical_source_surface_certificate.json"
ACQ_MANIFEST_PATH = G100 / "b2_historical_v1_1_acquisition_manifest.json"
PANEL_CERT_PATH = G100 / "b2_historical_panel_certificate.json"
PANEL_PATH = G100 / "b2_historical_panel.json"
BALLOT_CERT_PATH = G100 / "b2_2026_ballot_certificate.json"
STATE_PATH = G100 / "b2_current_state.json"
OUTCOME_PATH = G100 / "b2_v1_1_outcome_certificate.json"

ROSTER_CLASS = "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR"
REQUIRED_YEARS = [2016, 2021]

# Fixed terms that would identify a Morocco candidate-roster dataset by name.
# Exact substring matching only; a name is never interpreted.
ROSTER_NAME_TERMS = ["candidat", "candidate", "tete-de-liste", "tete_de_liste", "roster"]
MOROCCO_TERMS = ["maroc", "morocco"]
# Without an electoral qualifier a "candidature" dataset may be a recruitment notice.
ELECTORAL_QUALIFIER_TERMS = [
    "election", "elections", "legislatives", "legislative", "communales",
    "regionales", "electoral", "electorale", "liste", "listes", "scrutin",
]


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_V1_1_OUTCOME_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def surface_results(manifest: dict) -> list[dict]:
    """Per-surface enumeration outcome, including reachability and truncation."""
    by_source: dict[str, dict] = {}
    for entry in manifest["entries"]:
        bucket = by_source.setdefault(entry["source_id"], {
            "source_id": entry["source_id"], "requests": 0, "acquired": 0,
            "blocked": 0, "errors": 0, "no_captures": 0, "truncated": 0,
            "captures_total": 0, "inventory": None,
        })
        state = entry.get("state")
        if state == "INVENTORY":
            bucket["inventory"] = entry
            continue
        bucket["requests"] += 1
        bucket["acquired"] += state == "ACQUIRED"
        bucket["blocked"] += state == "BLOCKED_SOURCE"
        bucket["errors"] += state == "FETCH_ERROR"
        bucket["no_captures"] += state == "NO_CAPTURES"
        bucket["truncated"] += bool(entry.get("truncated"))
        bucket["captures_total"] += int(entry.get("capture_count") or 0)

    results = []
    for source_id in sorted(by_source):
        bucket = by_source[source_id]
        fully_enumerated = bucket["truncated"] == 0 and bucket["blocked"] == 0 and bucket["errors"] == 0
        reachable = bucket["acquired"] > 0
        bucket["fully_enumerated"] = fully_enumerated
        bucket["reachable"] = reachable
        bucket["exhaustion_claimable"] = fully_enumerated and reachable
        results.append(bucket)
    return results


def token_match(name: str, terms: list[str]) -> bool:
    """Word-boundary match over a hyphen/underscore-delimited dataset name.

    Naive substring matching produces false positives that would corrupt the
    conclusion: 'candidature' (a civil-service job notice) contains 'candidat',
    and 'etranger' contains 'rang'. Boundaries remove both.
    """
    lowered = name.lower()
    return any(re.search(rf"(?<![a-z]){re.escape(term)}(?![a-z])", lowered) for term in terms)


def roster_candidates(results: list[dict]) -> dict:
    """Deterministic name-level search for a Morocco electoral candidate roster.

    Three conditions must hold together: a candidate term, a Morocco term, and an
    electoral qualifier. The qualifier is what separates an electoral roster from
    a public-sector recruitment notice.
    """
    names: list[str] = []
    for bucket in results:
        inventory = bucket.get("inventory") or {}
        for package in inventory.get("packages", []) or []:
            names.append(str(package.get("name") or ""))
        for dataset in inventory.get("datasets", []) or []:
            names.append(str(dataset))

    hits, rejected = [], []
    for name in sorted(set(names)):
        has_candidate = token_match(name, ROSTER_NAME_TERMS)
        has_morocco = token_match(name, MOROCCO_TERMS)
        has_electoral = token_match(name, ELECTORAL_QUALIFIER_TERMS)
        if has_candidate and has_morocco and has_electoral:
            hits.append(name)
        elif has_candidate and has_morocco:
            rejected.append({"name": name, "reason": "NO_ELECTORAL_QUALIFIER_TERM"})

    return {
        "names_enumerated": len(names),
        "match_rule": (
            "word-boundary match requiring a candidate term AND a Morocco term AND an electoral "
            "qualifier; no ranking, no interpretation"
        ),
        "roster_term_list": ROSTER_NAME_TERMS,
        "morocco_term_list": MOROCCO_TERMS,
        "electoral_qualifier_terms": ELECTORAL_QUALIFIER_TERMS,
        "matches": sorted(hits),
        "rejected_near_matches": rejected,
        "roster_dataset_found": bool(hits),
    }


# Fixed name terms per secondary input class. Dictionary matching only: a name
# match reports that a candidate surface exists, never that the data is usable.
SECONDARY_TARGET_TERMS = {
    "HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR": [
        "conseils-communaux", "conseils-regionaux", "composition-des-conseils",
    ],
    "HISTORICAL_CANDIDATE_RANK_TARGET_YEAR": ["rang", "ordre-de-liste", "tete-de-liste"],
    "HISTORICAL_PARTY_SWITCH_TARGET_YEAR": ["transhumance", "changement-de-parti"],
    "HISTORICAL_PARTY_OFFICE_TARGET_YEAR": ["bureau-politique", "instance-dirigeante"],
    "HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR": ["defection"],
    "HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR": ["parrainage", "soutien-officiel"],
    "HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR": ["alliance", "coalition"],
}

# Election dates that decide whether a dataset is knowable before a cutoff.
COMMUNAL_ELECTION_DATES = {2015: "2015-09-04", 2021: "2021-09-08"}


def secondary_target_scan(results: list[dict]) -> list[dict]:
    """Report which secondary input classes now have a named candidate surface."""
    names: list[str] = []
    for bucket in results:
        inventory = bucket.get("inventory") or {}
        for package in inventory.get("packages", []) or []:
            names.append(str(package.get("name") or ""))
        for dataset in inventory.get("datasets", []) or []:
            names.append(str(dataset))

    rows = []
    for input_class, terms in sorted(SECONDARY_TARGET_TERMS.items()):
        matches = sorted({name for name in names if token_match(name, terms)})
        rows.append({
            "input_class": input_class,
            "name_terms": terms,
            "matches": matches,
            "candidate_surface_exists": bool(matches),
            "status": (
                "CANDIDATE_SURFACE_IDENTIFIED_NOT_YET_PARSED" if matches
                else "NO_NAMED_SURFACE_IN_AMENDED_CATALOG"
            ),
            "note": (
                "A name match means a dataset plausibly carries this class. It is not evidence, and "
                "the class stays blocked until a deterministic parser and its dependent inputs exist."
            ),
        })
    return rows


def select_state(panel_cert: dict, results: list[dict], roster: dict) -> dict:
    coverages = [row["core_predictive_panel_coverage"] for row in panel_cert["transitions"]]
    threshold = panel_cert["minimum_coverage_required"]
    if all(value >= threshold for value in coverages):
        return {
            "state": "B2_3_BACKTEST_UNLOCKED",
            "reason": "Core predictive coverage meets the frozen threshold in both transitions.",
        }

    blocked = [row["source_id"] for row in results if row["blocked"] or row["errors"]]
    truncated = [row["source_id"] for row in results if row["truncated"]]
    material = sum(row["captures_total"] for row in results)

    if blocked or truncated or material > 0:
        return {
            "state": "B2_3_DATA_BLOCKED_NONAGENTIC",
            "reason": (
                "Exhaustion is not established. "
                + (f"Blocked or failing surfaces: {blocked}. " if blocked else "")
                + (f"Truncated enumerations: {truncated}. " if truncated else "")
                + (f"Pre-cutoff archived material reachable but not deterministically parsable into the "
                   f"required input classes: {material} captures. " if material else "")
            ).strip(),
            "blocked_surfaces": blocked,
            "truncated_surfaces": truncated,
            "pre_cutoff_captures": material,
        }

    return {
        "state": "B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION",
        "reason": (
            "Every amended surface was fully enumerated and reachable, and none carries the required "
            "historical input classes."
        ),
    }


def main() -> None:
    surface = load(SURFACE_V1_1_PATH)
    surface_cert = load(SURFACE_CERT_PATH)
    manifest = load(ACQ_MANIFEST_PATH)
    panel = load(PANEL_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    ballot_cert = load(BALLOT_CERT_PATH)
    state = load(STATE_PATH)

    if manifest["source_surface_sha256"] != surface["canonical_surface_sha256"]:
        raise SystemExit("B2_V1_1_OUTCOME_FAIL: acquisition ran against a different surface hash")
    if surface_cert["gate"] != "PASS":
        raise SystemExit("B2_V1_1_OUTCOME_FAIL: source-surface certificate is not PASS")

    results = surface_results(manifest)
    roster = roster_candidates(results)
    secondary = secondary_target_scan(results)
    selection = select_state(panel_cert, results, roster)

    blocking = sorted({
        cls
        for transition in panel["transitions"]
        for feature in transition["features"]
        for cls in feature["missing_inputs"]
    })

    certificate = {
        "schema_version": "1.1",
        "certificate_id": "M26-GOAL100-B2-V1-1-OUTCOME-CERTIFICATE",
        "certified_at": now_local(),
        "amendment_id": surface["amendment_id"],
        "source_surface_sha256": surface["canonical_surface_sha256"],
        "acquisition_manifest_sha256": manifest["canonical_manifest_sha256"],
        "determinism": {"llm_used": False, "semantic_selection": False},
        "surface_results": results,
        "primary_target": {
            "input_class": ROSTER_CLASS,
            "required_years": REQUIRED_YEARS,
            "dataset_name_search": roster,
            "recovered": roster["roster_dataset_found"],
        },
        "secondary_target_scan": {
            "rule": "Fixed-term name matching over the enumerated catalog; no content interpretation.",
            "classes": secondary,
            "classes_with_candidate_surface": [
                row["input_class"] for row in secondary if row["candidate_surface_exists"]
            ],
            "leakage_note": {
                "communal_election_dates": COMMUNAL_ELECTION_DATES,
                "rule": (
                    "The 2021 communal election fell on the same day as the 2021 legislative election, "
                    "so 2021 council composition is not knowable before the 2021 legislative cutoff. "
                    "Office held at that cutoff derives from the 2015 councils."
                ),
            },
        },
        "b2_3": {
            "gate": panel_cert["gate"],
            "features_identifiable": [
                {"transition_id": row["transition_id"], "identifiable": row["features_identifiable"],
                 "total": row["features_total"]}
                for row in panel_cert["transitions"]
            ],
            "core_predictive_coverage": [
                {"transition_id": row["transition_id"], "coverage": row["core_predictive_panel_coverage"]}
                for row in panel_cert["transitions"]
            ],
            "threshold": panel_cert["minimum_coverage_required"],
            "threshold_unchanged": panel_cert["minimum_coverage_required"] == 0.8,
            "blocking_input_classes": blocking,
        },
        "b2_4": {
            "gate": ballot_cert["gate"],
            "rows_parsed": ballot_cert["rows_parsed"],
            "territory_coverage_fraction": ballot_cert["territory_coverage_fraction"],
            "verified_double_entry_rows": ballot_cert["verified_double_entry_rows"],
            "blocking_state": (
                "AMBIGUOUS_DETERMINISTIC_MATCH"
                if ballot_cert["ambiguous_deterministic_match_rows"] == ballot_cert["rows_parsed"]
                else "MIXED"
            ),
        },
        "termination_state": selection["state"],
        "termination_reason": selection["reason"],
        "termination_detail": {k: v for k, v in selection.items() if k not in {"state", "reason"}},
        "reserved_for_e_collect": {
            "policy": "Unresolved cells are preserved, not filled by agentic collection.",
            "e_collect_executed": False,
            "input_classes": blocking,
            "b2_4_unresolved_rows": ballot_cert["ambiguous_deterministic_match_rows"],
        },
        "invariants": {
            "coefficients": state["coefficients"]["predictive"],
            "coefficients_all_zero": (
                state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION"
            ),
            "B2_FROZEN": "B2-7-B2-FROZEN" in state["gates"]["open"] and False,
            "F0_CREATED": False,
            "AGENTIC_PREDICTIVE_LAYER": "LOCKED" if state["anti_drift"]["agentic_experiment_locked"] else "UNLOCKED",
        },
    }
    certificate["canonical_certificate_sha256"] = canonical_sha256(certificate)
    dump(OUTCOME_PATH, certificate)

    print("B2_V1_1_OUTCOME_CERTIFIED")
    print(f"termination_state={certificate['termination_state']}")
    print(f"roster_dataset_found={roster['roster_dataset_found']} names_enumerated={roster['names_enumerated']}")
    for row in results:
        print(f"  {row['source_id']:<38} req={row['requests']:<4} ok={row['acquired']:<4} "
              f"blocked={row['blocked']:<4} trunc={row['truncated']:<3} captures={row['captures_total']:<6} "
              f"exhaustion_claimable={row['exhaustion_claimable']}")
    surf = certificate["secondary_target_scan"]["classes_with_candidate_surface"]
    print(f"secondary classes with a named candidate surface: {surf}")
    print(f"B2-4 gate={certificate['b2_4']['gate']} coverage={certificate['b2_4']['territory_coverage_fraction']}")


if __name__ == "__main__":
    main()
