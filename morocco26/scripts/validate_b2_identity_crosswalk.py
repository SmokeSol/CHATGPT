#!/usr/bin/env python3
"""Fail-closed validation of the B2 identity/party/list/territory crosswalk."""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
EVIDENCE_DIR = G100 / "b2_evidence"
CORE = {"RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS"}


def load(name: str):
    path = G100 / name
    if not path.exists():
        raise SystemExit(f"B2_IDENTITY_VALIDATION_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_IDENTITY_VALIDATION_FAIL: {message}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def claim_count() -> int:
    if not EVIDENCE_DIR.exists():
        return 0
    return sum(1 for path in EVIDENCE_DIR.rglob("*.json") if path.is_file())


def validate_alias_uniqueness(rows: list[dict], id_field: str, label: str) -> None:
    owners: dict[str, str] = {}
    for row in rows:
        target = row[id_field]
        require(row["normalized_aliases"], f"{label} {target} has no normalized aliases")
        for alias in row["normalized_aliases"]:
            previous = owners.get(alias)
            require(previous in {None, target}, f"{label} alias collision {alias!r}: {previous} vs {target}")
            owners[alias] = target


def main() -> None:
    protocol = load("b2_identity_protocol_v1.json")
    crosswalk = load("b2_identity_crosswalk.json")
    certificate = load("b2_identity_territory_certificate.json")
    gates = load("b2_gate_registry.json")
    state = load("b2_current_state.json")
    features = load("b2_feature_dictionary_v1.json")
    source_certificate = load("b2_source_universe_certificate.json")
    source_registry = load("b2_source_registry.json")
    f1_certificate = load("fminus1_registration_certificate.json")
    event = load("fil_ariane_events/A021.json")

    require(protocol["status"] == "FROZEN_PRE_EXECUTION", "identity protocol status drift")
    require(protocol["protocol_id"] == "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1", "identity protocol ID drift")
    require(source_certificate["gate"] == "PASS", "B2 source universe not certified")
    require(source_registry["status"] == "FROZEN_COLLECTION_ENABLED_BOUNDED", "source registry not bounded-enabled")
    require(f1_certificate["gate"] == "PASS", "F-1 registration certificate not PASS")
    require(f1_certificate["forecast_artifact_sha256"] == "de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1", "F-1 hash drift")

    require(crosswalk["gate"] == certificate["gate"] == "PASS", "crosswalk/certificate gate not PASS")
    require(crosswalk["protocol_id"] == certificate["protocol_id"] == protocol["protocol_id"], "identity protocol linkage drift")
    require(crosswalk["failures"] == certificate["failures"] == [], "identity failures are non-empty")
    payload = dict(crosswalk)
    recorded_hash = payload.pop("canonical_crosswalk_sha256")
    expected_hash = canonical_sha256(payload)
    require(recorded_hash == expected_hash, "crosswalk canonical hash drift")
    require(certificate["crosswalk_sha256"] == expected_hash, "certificate crosswalk hash drift")
    require(certificate["crosswalk_path"] == "morocco26/data/goal100/b2_identity_crosswalk.json", "crosswalk path drift")

    local_rows = crosswalk["territories"]["local"]
    regional_rows = crosswalk["territories"]["regional"]
    local_ids = {row["constituency_id"] for row in local_rows}
    region_ids = {row["region_id"] for row in regional_rows}
    require(len(local_rows) == len(local_ids) == certificate["local_territories"] == 92, "local identity count != 92")
    require(sum(int(row["seats"]) for row in local_rows) == certificate["local_seats"] == 305, "local seat sum != 305")
    require(len(regional_rows) == len(region_ids) == certificate["regional_territories"] == 12, "regional identity count != 12")
    require(sum(int(row["seats"]) for row in regional_rows) == certificate["regional_seats"] == 90, "regional seat sum != 90")
    require("reg-oriental" in region_ids and "reg-l-oriental" not in region_ids, "reviewed Oriental regional ID convention drift")
    require(all(row["region_id"] in region_ids for row in local_rows), "a local territory references an unknown region")
    validate_alias_uniqueness(local_rows, "constituency_id", "local")
    validate_alias_uniqueness(regional_rows, "region_id", "regional")
    require(crosswalk["territories"]["unreviewed_fuzzy_matches"] == certificate["unreviewed_fuzzy_matches"] == 0, "fuzzy match count nonzero")
    require(certificate["territory_alias_collisions"] == 0, "territory alias collision count nonzero")

    parties = crosswalk["parties"]
    party_codes = {row["party_code"] for row in parties}
    require(len(parties) == len(party_codes) == certificate["party_codes"], "party-code count/uniqueness drift")
    require(CORE.issubset(party_codes), "one or more core party codes missing")
    require(certificate["core_party_codes"] == 8, "core party count != 8")
    require(certificate["party_alias_collisions"] == 0, "party alias collision count nonzero")
    for row in parties:
        expected_bucket = row["party_code"] if row["party_code"] in CORE else "OTHER"
        require(row["reporting_bucket"] == expected_bucket, f"party reporting bucket drift for {row['party_code']}")
        require(row["aliases"], f"party {row['party_code']} has no aliases")
        if row["party_code"] in CORE:
            require(row["full_name_fr"] and row["full_name_ar"], f"core party {row['party_code']} lacks frozen names")
        else:
            require(row["identity_status"] == "OBSERVED_CODE_FULL_LABEL_UNRESOLVED", f"non-core code {row['party_code']} was guessed into a label")

    lists = crosswalk["lists"]
    list_ids = [row["list_id"] for row in lists]
    require(len(lists) == len(set(list_ids)) == certificate["historical_list_ids"], "historical list ID count/uniqueness drift")
    require(all(int(row["year"]) in {2011, 2016, 2021} for row in lists), "unexpected list year or a 2026 list was admitted")
    require(all(row["party_code"] in party_codes for row in lists), "a list references an unknown party code")
    for row in lists:
        if row["scope"] == "local":
            require(row["territory_id"] in local_ids, f"local list references unknown territory: {row['list_id']}")
        elif row["scope"] == "regional":
            require(row["territory_id"] in region_ids, f"regional list references unknown territory: {row['list_id']}")
        else:
            require(False, f"invalid list scope: {row['scope']}")
        expected_id = f"list:{row['year']}:{row['scope']}:{row['territory_id']}:{row['party_code']}"
        require(row["list_id"] == expected_id, f"non-deterministic list ID: {row['list_id']}")
        require(row["presence_semantics"] == "POSITIVE_VOTE_LIST_OBSERVED_IN_CANONICAL_RESULT", "historical list presence semantics drift")

    people = crosswalk["people_2021"]
    seat_ids = {row["seat_id"] for row in people}
    stable_person_ids = {row["person_id"] for row in people}
    require(len(people) == certificate["elected_member_rows"] == 395, "elected-member row count != 395")
    require(len(seat_ids) == certificate["unique_seat_ids"] == 395, "unique seat count != 395")
    require(len(stable_person_ids) == certificate["unique_stable_person_ids"], "stable person count drift")
    require(sum(row["scope"] == "local" for row in people) == certificate["elected_local_rows"] == 305, "local elected-member count != 305")
    require(sum(row["scope"] == "regional" for row in people) == certificate["elected_regional_rows"] == 90, "regional elected-member count != 90")
    require(all(row["party_code_2021"] in party_codes for row in people), "elected person references unknown party code")
    require(all(row["territory_id"] in (local_ids if row["scope"] == "local" else region_ids) for row in people), "elected person has unresolved/invalid territory")
    require(all(row["person_id"] == f"tafra-person:{row['tafra_idperson']}" for row in people), "person ID format drift")
    require(all(row["seat_id"] == f"tafra-seat:{row['tafra_idsiege']}" for row in people), "seat ID format drift")
    require(all(row["identity_basis"] == "TAFRA_STABLE_PERSON_ID" for row in people), "person identity basis drift")

    collision_groups = crosswalk["identity_collisions"]["normalized_name_collision_groups"]
    computed: dict[str, set[str]] = defaultdict(set)
    for row in people:
        computed[row["normalized_name"]].add(row["person_id"])
    computed_groups = {
        name: tuple(sorted(person_ids))
        for name, person_ids in computed.items()
        if len(person_ids) > 1
    }
    reported_groups = {
        row["normalized_name"]: tuple(sorted(row["person_ids"]))
        for row in collision_groups
    }
    require(reported_groups == computed_groups, "normalized-name collision groups are incomplete or altered")
    require(len(collision_groups) == certificate["normalized_name_collision_groups"], "collision-group count drift")
    require(all(row["resolution"] == "RETAIN_SEPARATE_STABLE_IDS_NO_NAME_MERGE" for row in collision_groups), "a name collision was merged")

    historical = crosswalk["historical_mapping"]
    require(historical["local_rows_mapped"] == certificate["historical_local_rows_mapped"] == 276, "historical local mapping coverage != 276")
    require(historical["regional_rows_mapped"] == certificate["historical_regional_rows_mapped"], "historical regional mapping count drift")
    require(historical["by_year"]["2011"]["local_rows"] == 92, "2011 local row count != 92")
    require(historical["by_year"]["2016"]["local_rows"] == 92, "2016 local row count != 92")
    require(historical["by_year"]["2021"]["local_rows"] == 92, "2021 local row count != 92")
    require(historical["by_year"]["2021"]["regional_rows"] == 12, "2021 regional row count != 12")

    legacy = crosswalk["legacy_2026_candidate_leads"]
    require(legacy["status"] == "LEAD_ONLY_REVALIDATION_REQUIRED", "legacy candidate summary status drift")
    require(legacy["reported_total_candidate_records"] == certificate["legacy_2026_candidate_records_reported"] == 414, "legacy candidate count drift")
    require(legacy["admitted_B2_candidate_records"] == certificate["legacy_2026_candidate_records_admitted"] == 0, "legacy candidate records were admitted")
    require(legacy["mechanical_effect"] == "NONE" and float(legacy["predictive_effect"]) == 0.0, "legacy candidate summary acquired forecast effect")
    require(claim_count() == certificate["B2_claim_records_before_certificate"] == 0, "B2 claims existed before identity certification")

    gate = next(row for row in gates["gates"] if row["id"] == "B2-2-IDENTITY-TERRITORY-CROSSWALK")
    require(gate["status"] == "CLOSED", "B2-2 gate is not CLOSED")
    require(gate["required_artifact"] == "morocco26/data/goal100/b2_identity_territory_certificate.json", "B2-2 artifact path drift")
    require(gates["next_gate"] == "B2-3-HISTORICAL-FEATURE-PANEL", "next B2 gate is not B2-3")
    require(all(row["status"] == "LOCKED" for row in gates["agentic_gates"]), "agentic gate unlocked")
    require(next(row for row in gates["gates"] if row["id"] == "B2-8-F0-COUNTERFACTUAL-SIMULATION")["status"] == "LOCKED", "F0 gate unlocked")

    require(state["phase"] == "B2_IDENTITY_TERRITORY_CERTIFIED_HISTORICAL_PANEL_PENDING", "B2 identity-certified phase drift")
    require(state["identity_crosswalk"]["status"] == "CERTIFIED", "B2 state identity status drift")
    require(state["identity_crosswalk"]["crosswalk_sha256"] == expected_hash, "B2 state crosswalk hash drift")
    require(state["identity_crosswalk"]["legacy_2026_candidate_records_admitted"] == 0, "B2 state admitted legacy candidates")
    require(state["collection"]["status"] == "ENABLED_BOUNDED", "B2 bounded collection state lost")
    require(state["collection"]["evidence_records"] == 0, "B2 evidence count changed during identity gate")
    require(state["coefficients"]["predictive"] == "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION", "predictive coefficient lock drift")
    predictive = [row for row in features["features"] if row["forecast_role"] == "PREDICTIVE_AFTER_CALIBRATION"]
    require(all(row["coefficient_state"] == "LOCKED_ZERO_UNTIL_HISTORICAL_CALIBRATION_PASS" for row in predictive), "predictive feature coefficient unlocked")

    require(event["event_id"] == "A021" and event["status"] == "PASS", "A021 event invalid")
    require(event["machine_result"]["crosswalk_sha256"] == expected_hash, "A021 crosswalk hash drift")
    journal = (ROOT / "FIL_ARIANE.md").read_text(encoding="utf-8")
    require("Entrée A021 — Certification du crosswalk identité-parti-liste-territoire B2" in journal, "A021 journal entry missing")

    print("B2_IDENTITY_TERRITORY_PASS")
    print(f"crosswalk_sha256={expected_hash}")
    print("territories=92_local+12_regional seats=305+90")
    print(f"party_codes={certificate['party_codes']} historical_lists={certificate['historical_list_ids']}")
    print(f"people_2021={certificate['elected_member_rows']} stable_people={certificate['unique_stable_person_ids']}")
    print(f"name_collision_groups={certificate['normalized_name_collision_groups']} merged=0")
    print("legacy_2026_reported=414 admitted=0 fuzzy_matches=0")
    print("next=B2-3-HISTORICAL-FEATURE-PANEL")
    print("predictive_coefficients=ALL_ZERO F0=LOCKED agentic=ALL_LOCKED")


if __name__ == "__main__":
    main()
