#!/usr/bin/env python3
"""Validate B2 identity V1.1 and reuse every structural V1 gate check."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import validate_b2_identity_crosswalk as legacy

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
BASE_PATH = G100 / "b2_identity_protocol_v1.json"
AMENDMENT_PATH = G100 / "b2_identity_protocol_v1_1.json"
CROSSWALK_PATH = G100 / "b2_identity_crosswalk.json"
CERTIFICATE_PATH = G100 / "b2_identity_territory_certificate.json"
ARCHIVE_PATH = G100 / "b2_identity_failures" / "run_32003523080" / "manifest.json"
FAILED_COMMIT = "7b08117b1fb987cdc2925e882527c5d3920ccc78"
FAILED_HASH = "92d4d75bc1f2ca2e4e9873e8dddc0b0e9e7e4b0ec247c060e3e3ddb6311e6b13"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_IDENTITY_V1_1_FAIL: missing {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_IDENTITY_V1_1_FAIL: {message}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def git_blob_sha(path: Path) -> str:
    try:
        return subprocess.check_output(["git", "hash-object", str(path)], cwd=REPO, text=True).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"B2_IDENTITY_V1_1_FAIL: cannot hash base protocol: {exc}")


def git_bytes(commit: str, path: str) -> bytes:
    try:
        return subprocess.check_output(["git", "show", f"{commit}:{path}"], cwd=REPO)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"B2_IDENTITY_V1_1_FAIL: failed artifact unavailable in Git history: {exc}")


def validate_amendment(base: dict, amendment: dict) -> None:
    require(amendment["schema_version"] == "1.1", "amendment schema version drift")
    require(amendment["protocol_id"] == "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1.1", "amendment protocol ID drift")
    require(amendment["supersedes"] == base["protocol_id"] == "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1", "supersession chain drift")
    require(amendment["base_protocol_path"] == "morocco26/data/goal100/b2_identity_protocol_v1.json", "base protocol path drift")
    require(amendment["base_protocol_git_blob_sha"] == git_blob_sha(BASE_PATH), "base protocol Git-blob hash drift")
    require(amendment["status"] == base["status"] == "FROZEN_PRE_EXECUTION", "pre-execution freeze status drift")
    require(amendment["parent_protocol_id"] == base["parent_protocol_id"], "parent B2 protocol drift")
    require(amendment["purpose"] == base["purpose"], "identity purpose changed")
    require(amendment["scope"] == base["scope"], "identity scope changed")
    require(amendment["normalization"] == base["normalization"], "normalization rules changed")
    require(amendment["party_identity"] == base["party_identity"], "party identity rules changed")
    require(amendment["person_identity"] == base["person_identity"], "person identity rules changed")
    require(amendment["list_identity"] == base["list_identity"], "list identity rules changed")
    require(amendment["inputs"] == base["inputs"], "identity inputs changed")
    require(amendment["gate_pass_conditions"] == base["gate_pass_conditions"], "gate pass conditions changed")
    require(amendment["outputs"] == base["outputs"], "identity outputs changed")
    require(amendment["failure_rule"] == base["failure_rule"], "identity failure rule changed")

    base_territory = dict(base["territory_identity"])
    amendment_territory = dict(amendment["territory_identity"])
    base_regional_id = base_territory.pop("regional_id")
    amendment_regional_id = amendment_territory.pop("regional_id")
    require(amendment_territory == base_territory, "territory identity rules changed beyond ID wording")
    require(base_regional_id.startswith("Prefix reg-"), "unexpected base regional-ID rule")
    require("Oriental" in amendment_regional_id, "reviewed Oriental convention missing")

    expected_aliases = copy.deepcopy(base["reviewed_aliases"])
    expected_aliases["regional"]["dakhla oued eddahab"] = "reg-dakhla-oued-ed-dahab"
    require(amendment["reviewed_aliases"] == expected_aliases, "V1.1 contains an alias change beyond exact Dakhla amendment")

    delta = amendment["amendment"]
    require(delta["trigger"] == "B2-2 failed run 32003523080", "amendment trigger drift")
    require(delta["failed_commit"] == FAILED_COMMIT, "amendment failed commit drift")
    require(delta["failed_crosswalk_canonical_sha256"] == FAILED_HASH, "amendment failed hash drift")
    require(delta["failure_class"] == "UNRESOLVED_REGION" and int(delta["failure_count"]) == 2, "amendment failure class/count drift")
    require(delta["exact_source_label"] == "Dakhla-Oued Eddahab", "source alias label drift")
    require(delta["authoritative_target_label"] == "Dakhla-Oued Ed-Dahab", "authoritative target label drift")
    require(delta["reviewed_normalized_alias"] == "dakhla oued eddahab", "normalized alias drift")
    require(delta["canonical_target_id"] == "reg-dakhla-oued-ed-dahab", "canonical alias target drift")
    for field in ("scientific_change", "model_change", "threshold_change", "claim_change", "coefficient_change"):
        require(delta[field] == "NONE", f"amendment declares material change in {field}")


def validate_failure_archive(archive: dict) -> None:
    payload = dict(archive)
    recorded = payload.pop("canonical_manifest_sha256")
    require(recorded == canonical_sha256(payload), "failure-archive canonical hash drift")
    require(archive["failed_run_id"] == 32003523080, "failure archive run ID drift")
    require(archive["failed_commit"] == FAILED_COMMIT, "failure archive commit drift")
    require(archive["failed_crosswalk_canonical_sha256"] == FAILED_HASH, "failure archive crosswalk hash drift")
    require(len(archive["failure_classes"]) == 2, "failure archive failure count drift")
    require(all(row["kind"] == "UNRESOLVED_REGION" for row in archive["failure_classes"]), "failure archive class drift")
    require(archive["counts_at_failure"]["legacy_2026_candidate_records_admitted"] == 0, "failed attempt admitted legacy candidates")
    require(archive["counts_at_failure"]["unreviewed_fuzzy_matches"] == 0, "failed attempt used fuzzy matching")
    for artifact in archive["artifacts"].values():
        raw = git_bytes(FAILED_COMMIT, artifact["path"])
        require(hashlib.sha256(raw).hexdigest() == artifact["sha256"], f"failed artifact SHA drift: {artifact['path']}")
        require(len(raw) == artifact["bytes"], f"failed artifact byte count drift: {artifact['path']}")


def main() -> None:
    base = load(BASE_PATH)
    amendment = load(AMENDMENT_PATH)
    actual_crosswalk = load(CROSSWALK_PATH)
    actual_certificate = load(CERTIFICATE_PATH)
    archive = load(ARCHIVE_PATH)
    validate_amendment(base, amendment)
    validate_failure_archive(archive)

    require(actual_crosswalk["protocol_id"] == amendment["protocol_id"], "crosswalk is not linked to protocol V1.1")
    require(actual_certificate["protocol_id"] == amendment["protocol_id"], "certificate is not linked to protocol V1.1")
    require(actual_crosswalk["crosswalk_id"] == "M26-GOAL100-B2-IDENTITY-CROSSWALK-V1.1", "crosswalk version ID drift")
    require(actual_certificate["certificate_id"] == "M26-GOAL100-B2-IDENTITY-TERRITORY-CERTIFICATE-V1.1", "certificate version ID drift")
    require(actual_crosswalk["gate"] == actual_certificate["gate"] == "PASS", "V1.1 crosswalk/certificate not PASS")
    require(actual_crosswalk["failures"] == actual_certificate["failures"] == [], "V1.1 failures are non-empty")

    # Reuse every detailed structural V1 check through compatibility views.
    original_load = legacy.load
    original_hash = legacy.canonical_sha256

    def compatibility_load(name: str):
        if name == "b2_identity_protocol_v1.json":
            value = copy.deepcopy(amendment)
            value["protocol_id"] = "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1"
            return value
        if name == "b2_identity_crosswalk.json":
            value = copy.deepcopy(actual_crosswalk)
            value["protocol_id"] = "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1"
            return value
        if name == "b2_identity_territory_certificate.json":
            value = copy.deepcopy(actual_certificate)
            value["protocol_id"] = "M26-GOAL100-B2-IDENTITY-PROTOCOL-V1"
            return value
        return original_load(name)

    def compatibility_hash(value):
        if isinstance(value, dict) and value.get("crosswalk_id") == "M26-GOAL100-B2-IDENTITY-CROSSWALK-V1.1":
            restored = copy.deepcopy(value)
            restored["protocol_id"] = amendment["protocol_id"]
            return original_hash(restored)
        return original_hash(value)

    legacy.load = compatibility_load
    legacy.canonical_sha256 = compatibility_hash
    legacy.main()

    event = load(G100 / "fil_ariane_events" / "A022.json")
    require(event["event_id"] == "A022", "A022 event missing")
    require(event["failed_crosswalk_canonical_sha256"] == FAILED_HASH, "A022 failed hash drift")
    require(event["amendment"]["protocol_id"] == amendment["protocol_id"], "A022 protocol linkage drift")
    journal = (ROOT / "FIL_ARIANE.md").read_text(encoding="utf-8")
    require("Entrée A022 — Amendement exact de l’alias régional Dakhla" in journal, "A022 journal entry missing")

    print("B2_IDENTITY_TERRITORY_V1_1_PASS")
    print(f"protocol={amendment['protocol_id']}")
    print(f"failed_attempt_archive={archive['canonical_manifest_sha256']}")
    print(f"crosswalk_sha256={actual_crosswalk['canonical_crosswalk_sha256']}")
    print("reviewed_aliases_added=1 fuzzy_matches=0 legacy_2026_admitted=0")
    print("next=B2-3-HISTORICAL-FEATURE-PANEL")


if __name__ == "__main__":
    main()
