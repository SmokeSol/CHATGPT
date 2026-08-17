#!/usr/bin/env python3
"""Build immutable Atlas 395 daily editions from derived product views."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Africa/Casablanca")
VIEW_FILES = (
    "current_snapshot.json",
    "national_projection.json",
    "constituency_cards.json",
    "party_cards.json",
    "evidence_index.json",
    "methodology_state.json",
    "change_log.json",
    "snapshot_manifest.json",
)


def load(path: Path, optional: bool = False) -> Any:
    if optional and not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8", newline="\n")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> datetime:
    return datetime.now(TZ)


def select_snapshot(goal100: Path) -> str:
    registry = load(goal100 / "forecast_registry.json")
    snapshots = registry.get("snapshots") or []
    if not snapshots:
        raise SystemExit("ATLAS395_DAILY_FAIL: forecast registry contains no registered snapshot")
    for row in reversed(snapshots):
        snapshot_id = row.get("snapshot_id")
        root = goal100 / "forecasts" / str(snapshot_id)
        forecast = root / "forecast.json"
        manifest = root / "snapshot_manifest.json"
        if not snapshot_id or not forecast.exists() or not manifest.exists():
            continue
        snapshot_manifest = load(manifest)
        expected = snapshot_manifest.get("forecast_artifact_hash") or row.get("forecast_artifact_hash")
        if expected and sha(forecast) != expected:
            continue
        if row.get("forecast_artifact_hash") and expected != row.get("forecast_artifact_hash"):
            continue
        print(snapshot_id)
        return str(snapshot_id)
    raise SystemExit("ATLAS395_DAILY_FAIL: no registered snapshot passed physical/hash validation")


def party_means(national: dict[str, Any]) -> dict[str, float]:
    return {str(party.get("party")): float(party.get("mean") or 0.0) for party in national.get("parties", [])}


def constituency_index(cards: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(card.get("constituency_id")): card for card in cards.get("constituencies", [])}


def constituency_vector(card: dict[str, Any]) -> dict[str, float]:
    return {
        str(code): float((party or {}).get("expected_seats") or 0.0)
        for code, party in (card.get("parties") or {}).items()
    }


def diff_numeric(previous: float, current: float, epsilon: float = 1e-9) -> float:
    delta = current - previous
    return 0.0 if abs(delta) < epsilon else delta


def evidence_document_count(evidence: dict[str, Any]) -> int:
    reader = evidence.get("reader_scope") or {}
    if "documents_acquired" in reader:
        return int(reader.get("documents_acquired") or 0)
    return int((evidence.get("wave1") or {}).get("documents_acquired") or 0)


def evidence_source_count(evidence: dict[str, Any]) -> int:
    reader = evidence.get("reader_scope") or {}
    if "authorized_sources" in reader:
        return int(reader.get("authorized_sources") or 0)
    return len(evidence.get("sources") or [])


def compare(previous_dir: Path | None, data_dir: Path) -> dict[str, Any]:
    current_national = load(data_dir / "national_projection.json")
    current_cards = load(data_dir / "constituency_cards.json")
    current_evidence = load(data_dir / "evidence_index.json")
    current_policy = (current_evidence.get("source_policy") or {}).get("policy_id")

    if previous_dir is None:
        return {
            "state": "INITIAL_EDITION",
            "previous_edition": None,
            "projection_changed": False,
            "national_party_seat_delta": {},
            "territories_changed": 0,
            "territory_changes": [],
            "new_documented_signals": len(current_evidence.get("events") or []),
            "signals_removed_by_policy": 0,
            "documents_acquired_delta": 0,
            "authorized_sources_delta": 0,
            "source_policy_changed": bool(current_policy),
            "source_policy_id": current_policy,
            "summary_fr": "Première édition quotidienne d’Atlas 395. La projection de référence est enregistrée comme point de comparaison pour les éditions suivantes.",
        }

    previous_national = load(previous_dir / "national_projection.json")
    previous_cards = load(previous_dir / "constituency_cards.json")
    previous_evidence = load(previous_dir / "evidence_index.json")
    previous_policy = (previous_evidence.get("source_policy") or {}).get("policy_id")

    previous_means, current_means = party_means(previous_national), party_means(current_national)
    national_delta = {
        code: diff_numeric(previous_means.get(code, 0.0), current_means.get(code, 0.0))
        for code in sorted(set(previous_means) | set(current_means))
    }
    national_delta = {code: value for code, value in national_delta.items() if value != 0.0}

    previous_index, current_index = constituency_index(previous_cards), constituency_index(current_cards)
    territory_changes = []
    for constituency_id in sorted(set(previous_index) | set(current_index)):
        if constituency_id not in previous_index or constituency_id not in current_index:
            territory_changes.append({"constituency_id": constituency_id, "state": "ADDED_OR_REMOVED"})
            continue
        previous_vector = constituency_vector(previous_index[constituency_id])
        current_vector = constituency_vector(current_index[constituency_id])
        changes = {
            code: diff_numeric(previous_vector.get(code, 0.0), current_vector.get(code, 0.0))
            for code in sorted(set(previous_vector) | set(current_vector))
        }
        changes = {code: value for code, value in changes.items() if value != 0.0}
        if changes:
            territory_changes.append({
                "constituency_id": constituency_id,
                "name": current_index[constituency_id].get("name"),
                "region": current_index[constituency_id].get("region"),
                "expected_seat_delta": changes,
            })

    previous_events = {str(event.get("id")) for event in previous_evidence.get("events") or [] if event.get("id")}
    current_events = {str(event.get("id")) for event in current_evidence.get("events") or [] if event.get("id")}
    new_signals = len(current_events - previous_events)
    removed_signals = len(previous_events - current_events)
    policy_changed = previous_policy != current_policy
    projection_changed = bool(national_delta or territory_changes)

    documents_delta = evidence_document_count(current_evidence) - evidence_document_count(previous_evidence)
    sources_delta = evidence_source_count(current_evidence) - evidence_source_count(previous_evidence)
    if projection_changed:
        summary = f"La projection évolue dans {len(territory_changes)} territoire(s) depuis l’édition précédente."
    elif policy_changed:
        summary = "Périmètre des sources mis à jour : seules les sources institutionnelles, les publications officielles et Médias24 sont désormais retenus."
    elif new_signals:
        summary = f"{new_signals} nouveau(x) signal(aux) documenté(s) depuis l’édition précédente, sans modification chiffrée de la projection."
    else:
        summary = "Aucune évolution chiffrée de la projection depuis l’édition précédente."

    return {
        "state": "COMPARED_WITH_PREVIOUS",
        "previous_edition": previous_dir.name,
        "projection_changed": projection_changed,
        "national_party_seat_delta": national_delta,
        "territories_changed": len(territory_changes),
        "territory_changes": territory_changes[:25],
        "new_documented_signals": new_signals,
        "signals_removed_by_policy": removed_signals if policy_changed else 0,
        "documents_acquired_delta": documents_delta,
        "authorized_sources_delta": sources_delta,
        "source_policy_changed": policy_changed,
        "previous_source_policy_id": previous_policy,
        "source_policy_id": current_policy,
        "summary_fr": summary,
    }


def product_version(release_manifest: Path | None) -> str:
    if release_manifest and release_manifest.exists():
        return str(load(release_manifest).get("current_version") or "V0.5")
    return "V0.5"


def row_published_at(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("published_at") or ""), str(row.get("edition_id") or "")


def manifest_matches(directory: Path, staged_hashes: dict[str, str]) -> bool:
    manifest = load(directory / "edition.json", optional=True)
    return bool(manifest and (manifest.get("files") or {}) == staged_hashes)


def next_edition_id(editions_dir: Path, base_date: str) -> tuple[str, int]:
    base = editions_dir / base_date
    if not base.exists():
        return base_date, 0
    correction = 1
    while (editions_dir / f"{base_date}-c{correction}").exists():
        correction += 1
    return f"{base_date}-c{correction}", correction


def build_edition(
    data_dir: Path,
    editions_dir: Path,
    science_ref: str,
    edition_date: str | None,
    release_manifest: Path | None,
) -> None:
    now = now_local()
    base_date = edition_date or now.date().isoformat()
    for name in VIEW_FILES:
        if not (data_dir / name).exists():
            raise SystemExit(f"ATLAS395_DAILY_FAIL: missing derived view {name}")

    index_path = editions_dir / "index.json"
    index = load(index_path, optional=True) or {"schema_version": "1.1", "editions": []}
    rows = sorted(index.get("editions") or [], key=row_published_at)
    staged_hashes = {name: sha(data_dir / name) for name in VIEW_FILES}

    for row in reversed(rows):
        directory = editions_dir / str(row.get("edition_id"))
        if directory.exists() and manifest_matches(directory, staged_hashes):
            daily = load(directory / "daily_update.json")
            dump(data_dir / "daily_update.json", daily)
            dump(editions_dir / "current.json", {
                "edition_id": row.get("edition_id"),
                "edition_date": row.get("edition_date") or str(row.get("edition_id", ""))[:10],
                "product_version": row.get("product_version"),
                "published_at": row.get("published_at"),
                "science_ref": row.get("science_ref") or science_ref,
                "forecast_snapshot": row.get("forecast_snapshot"),
                "source_policy_id": row.get("source_policy_id"),
                "path": f"/editions/{row.get('edition_id')}/",
                "daily_update_path": "/data/daily_update.json",
            })
            print(f"ATLAS395_DAILY_REUSE edition={row.get('edition_id')}")
            return

    previous_row = rows[-1] if rows else None
    previous_id = str(previous_row.get("edition_id")) if previous_row else None
    previous_dir = editions_dir / previous_id if previous_id else None
    delta = compare(previous_dir if previous_dir and previous_dir.exists() else None, data_dir)

    edition_id, correction_number = next_edition_id(editions_dir, base_date)
    edition_dir = editions_dir / edition_id
    edition_dir.mkdir(parents=True, exist_ok=False)
    for name in VIEW_FILES:
        shutil.copy2(data_dir / name, edition_dir / name)

    snapshot = load(data_dir / "current_snapshot.json")
    evidence = load(data_dir / "evidence_index.json")
    source_policy_id = (evidence.get("source_policy") or {}).get("policy_id")
    same_day_correction = bool(previous_row and (previous_row.get("edition_date") or str(previous_id)[:10]) == base_date)
    edition_manifest = {
        "schema_version": "1.1",
        "edition_id": edition_id,
        "edition_date": base_date,
        "correction_number": correction_number,
        "supersedes_edition_id": previous_id if same_day_correction else None,
        "product_version": product_version(release_manifest),
        "published_at": now.isoformat(timespec="seconds"),
        "science_ref": science_ref,
        "forecast_snapshot": snapshot.get("snapshot_id"),
        "source_data_cutoff": snapshot.get("data_cutoff"),
        "source_policy_id": source_policy_id,
        "projection_changed_since_previous": delta["projection_changed"],
        "territories_changed_since_previous": delta["territories_changed"],
        "new_documented_signals_since_previous": delta["new_documented_signals"],
        "source_policy_changed_since_previous": delta.get("source_policy_changed", False),
        "evidence_as_of": evidence.get("as_of"),
        "files": staged_hashes,
        "immutability": "OFFICIAL_EDITION_FILES_ARE_APPEND_ONLY_AND_NEVER_OVERWRITTEN",
    }
    edition_manifest["canonical_sha256"] = canonical({key: value for key, value in edition_manifest.items() if key != "canonical_sha256"})
    dump(edition_dir / "edition.json", edition_manifest)
    dump(edition_dir / "daily_update.json", delta)
    dump(data_dir / "daily_update.json", delta)

    current_pointer = {
        "edition_id": edition_id,
        "edition_date": base_date,
        "product_version": edition_manifest["product_version"],
        "published_at": edition_manifest["published_at"],
        "science_ref": science_ref,
        "forecast_snapshot": edition_manifest["forecast_snapshot"],
        "source_policy_id": source_policy_id,
        "path": f"/editions/{edition_id}/",
        "daily_update_path": "/data/daily_update.json",
    }
    dump(editions_dir / "current.json", current_pointer)

    new_row = {
        "edition_id": edition_id,
        "edition_date": base_date,
        "correction_number": correction_number,
        "supersedes_edition_id": edition_manifest["supersedes_edition_id"],
        "product_version": edition_manifest["product_version"],
        "published_at": edition_manifest["published_at"],
        "science_ref": science_ref,
        "forecast_snapshot": edition_manifest["forecast_snapshot"],
        "source_policy_id": source_policy_id,
        "projection_changed": delta["projection_changed"],
        "territories_changed": delta["territories_changed"],
        "new_documented_signals": delta["new_documented_signals"],
        "source_policy_changed": delta.get("source_policy_changed", False),
        "summary_fr": delta["summary_fr"],
    }
    rows.append(new_row)
    rows.sort(key=row_published_at)
    dump(index_path, {
        "schema_version": "1.1",
        "current_edition": edition_id,
        "current_edition_date": base_date,
        "editions": rows,
    })
    print(
        "ATLAS395_DAILY_OK "
        f"edition={edition_id} version={edition_manifest['product_version']} "
        f"snapshot={edition_manifest['forecast_snapshot']} policy={source_policy_id}"
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    select = sub.add_parser("select-snapshot")
    select.add_argument("--goal100-root", required=True, type=Path)
    build = sub.add_parser("build-edition")
    build.add_argument("--data-dir", required=True, type=Path)
    build.add_argument("--editions-dir", required=True, type=Path)
    build.add_argument("--science-ref", required=True)
    build.add_argument("--edition-date")
    build.add_argument("--release-manifest", type=Path)
    args = parser.parse_args()
    if args.command == "select-snapshot":
        select_snapshot(args.goal100_root)
    else:
        build_edition(args.data_dir, args.editions_dir, args.science_ref, args.edition_date, args.release_manifest)


if __name__ == "__main__":
    main()
