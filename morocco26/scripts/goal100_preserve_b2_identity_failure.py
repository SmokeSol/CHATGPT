#!/usr/bin/env python3
"""Create a compact immutable manifest for failed B2 identity run 32003523080.

The failed 52k-line crosswalk remains in Git history at commit 7b08117. Duplicating
it in the current tree would add no evidentiary value. This manifest hashes the
exact blobs from that commit and preserves their canonical failure identifiers.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
OUT = ROOT / "data" / "goal100" / "b2_identity_failures" / "run_32003523080" / "manifest.json"
FAILED_COMMIT = "7b08117b1fb987cdc2925e882527c5d3920ccc78"
FAILED_RUN = 32003523080
PATHS = {
    "crosswalk": "morocco26/data/goal100/b2_identity_crosswalk.json",
    "certificate": "morocco26/data/goal100/b2_identity_territory_certificate.json",
    "event": "morocco26/data/goal100/fil_ariane_events/A021F32003523080.json",
    "journal": "morocco26/FIL_ARIANE.md",
}
EXPECTED_CANONICAL_HASH = "92d4d75bc1f2ca2e4e9873e8dddc0b0e9e7e4b0ec247c060e3e3ddb6311e6b13"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"B2_IDENTITY_FAILURE_ARCHIVE_FAIL: {message}")


def git_bytes(path: str) -> bytes:
    try:
        return subprocess.check_output(["git", "show", f"{FAILED_COMMIT}:{path}"], cwd=REPO)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"B2_IDENTITY_FAILURE_ARCHIVE_FAIL: cannot read {path} at failed commit: {exc}")


def git_blob_sha(path: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", f"{FAILED_COMMIT}:{path}"],
            cwd=REPO,
            text=True,
        ).strip()
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"B2_IDENTITY_FAILURE_ARCHIVE_FAIL: cannot resolve blob {path}: {exc}")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def main() -> None:
    if OUT.exists():
        existing = json.loads(OUT.read_text(encoding="utf-8"))
        require(existing["failed_commit"] == FAILED_COMMIT, "existing archive commit drift")
        require(existing["failed_crosswalk_canonical_sha256"] == EXPECTED_CANONICAL_HASH, "existing archive canonical hash drift")
        print("B2_IDENTITY_FAILURE_ARCHIVE_ALREADY_PRESENT")
        return

    artifacts = {}
    decoded = {}
    for name, path in PATHS.items():
        raw = git_bytes(path)
        artifacts[name] = {
            "path": path,
            "git_blob_sha": git_blob_sha(path),
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        if path.endswith(".json"):
            decoded[name] = json.loads(raw.decode("utf-8"))

    certificate = decoded["certificate"]
    crosswalk = decoded["crosswalk"]
    event = decoded["event"]
    require(certificate["gate"] == "FAIL", "archived certificate is not FAIL")
    require(certificate["crosswalk_sha256"] == EXPECTED_CANONICAL_HASH, "archived certificate canonical hash drift")
    require(crosswalk["canonical_crosswalk_sha256"] == EXPECTED_CANONICAL_HASH, "archived crosswalk canonical hash drift")
    require(event["event_id"] == "A021F32003523080", "archived failure event ID drift")
    failures = certificate["failures"]
    require(len(failures) == 2, "archived failure count != 2")
    require(all(row["kind"] == "UNRESOLVED_REGION" for row in failures), "archived failure class drift")
    require(all(row["raw"] == "Dakhla-Oued Eddahab" for row in failures), "archived failure label drift")

    manifest = {
        "schema_version": "1.0",
        "archive_id": "M26-GOAL100-B2-IDENTITY-FAILURE-32003523080",
        "failed_run_id": FAILED_RUN,
        "failed_commit": FAILED_COMMIT,
        "status": "IMMUTABLE_GIT_HISTORY_REFERENCE",
        "failed_crosswalk_canonical_sha256": EXPECTED_CANONICAL_HASH,
        "failure_classes": failures,
        "counts_at_failure": {
            "local_territories": certificate["local_territories"],
            "regional_territories": certificate["regional_territories"],
            "historical_local_rows_mapped": certificate["historical_local_rows_mapped"],
            "historical_regional_rows_mapped": certificate["historical_regional_rows_mapped"],
            "party_codes": certificate["party_codes"],
            "historical_list_ids": certificate["historical_list_ids"],
            "elected_member_rows": certificate["elected_member_rows"],
            "legacy_2026_candidate_records_admitted": certificate["legacy_2026_candidate_records_admitted"],
            "unreviewed_fuzzy_matches": certificate["unreviewed_fuzzy_matches"],
        },
        "artifacts": artifacts,
        "preservation_rule": "The failed artifacts are retrieved from the exact Git commit; future PASS artifacts may overwrite working-tree paths but cannot rewrite this commit or manifest.",
    }
    manifest["canonical_manifest_sha256"] = canonical_sha256(manifest)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("B2_IDENTITY_FAILURE_ARCHIVE_PASS")
    print(f"archive_sha256={manifest['canonical_manifest_sha256']}")


if __name__ == "__main__":
    main()
