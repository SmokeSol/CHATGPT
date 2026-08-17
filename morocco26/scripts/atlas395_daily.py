#!/usr/bin/env python3
"""Atlas 395 Daily edition builder.

Reads already-derived Atlas product views and creates an immutable daily edition.
It never writes to MOROCCO//26 scientific artifacts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
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
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def now_local() -> datetime:
    return datetime.now(TZ)


def select_snapshot(goal100: Path) -> str:
    registry = load(goal100 / "forecast_registry.json")
    snapshots = registry.get("snapshots") or []
    if not snapshots:
        raise SystemExit("ATLAS395_DAILY_FAIL: forecast registry contains no registered snapshot")
    for row in reversed(snapshots):
        sid = row.get("snapshot_id")
        root = goal100 / "forecasts" / str(sid)
        forecast = root / "forecast.json"
        manifest = root / "snapshot_manifest.json"
        if not sid or not forecast.exists() or not manifest.exists():
            continue
        m = load(manifest)
        expected = m.get("forecast_artifact_hash") or row.get("forecast_artifact_hash")
        if expected and sha(forecast) != expected:
            continue
        if row.get("forecast_artifact_hash") and expected != row.get("forecast_artifact_hash"):
            continue
        print(sid)
        return sid
    raise SystemExit("ATLAS395_DAILY_FAIL: no registered snapshot passed physical/hash validation")


def party_means(national: dict[str, Any]) -> dict[str, float]:
    return {str(p.get("party")): float(p.get("mean") or 0.0) for p in national.get("parties", [])}


def constituency_index(cards: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(c.get("constituency_id")): c for c in cards.get("constituencies", [])}


def constituency_vector(c: dict[str, Any]) -> dict[str, float]:
    return {str(code): float((p or {}).get("expected_seats") or 0.0) for code, p in (c.get("parties") or {}).items()}


def diff_numeric(a: float, b: float, eps: float = 1e-9) -> float:
    d = b - a
    return 0.0 if abs(d) < eps else d


def compare(previous_dir: Path | None, data_dir: Path) -> dict[str, Any]:
    current_nat = load(data_dir / "national_projection.json")
    current_cards = load(data_dir / "constituency_cards.json")
    current_evidence = load(data_dir / "evidence_index.json")
    if previous_dir is None:
        return {
            "state": "INITIAL_EDITION", "previous_edition": None, "projection_changed": False,
            "national_party_seat_delta": {}, "territories_changed": 0, "territory_changes": [],
            "new_documented_signals": len(current_evidence.get("events") or []), "documents_acquired_delta": 0,
            "summary_fr": "Première édition quotidienne d’Atlas 395. La projection de référence est enregistrée comme point de comparaison pour les éditions suivantes."
        }
    prev_nat = load(previous_dir / "national_projection.json")
    prev_cards = load(previous_dir / "constituency_cards.json")
    prev_evidence = load(previous_dir / "evidence_index.json")
    a, b = party_means(prev_nat), party_means(current_nat)
    national_delta = {k: diff_numeric(a.get(k, 0.0), b.get(k, 0.0)) for k in sorted(set(a) | set(b))}
    national_delta = {k: v for k, v in national_delta.items() if v != 0.0}
    pa, pb = constituency_index(prev_cards), constituency_index(current_cards)
    territory_changes = []
    for cid in sorted(set(pa) | set(pb)):
        if cid not in pa or cid not in pb:
            territory_changes.append({"constituency_id": cid, "state": "ADDED_OR_REMOVED"})
            continue
        va, vb = constituency_vector(pa[cid]), constituency_vector(pb[cid])
        changes = {k: diff_numeric(va.get(k, 0.0), vb.get(k, 0.0)) for k in sorted(set(va) | set(vb))}
        changes = {k: v for k, v in changes.items() if v != 0.0}
        if changes:
            territory_changes.append({"constituency_id": cid, "name": pb[cid].get("name"), "region": pb[cid].get("region"), "expected_seat_delta": changes})
    prev_events = {str(e.get("id")) for e in (prev_evidence.get("events") or []) if e.get("id")}
    curr_events = {str(e.get("id")) for e in (current_evidence.get("events") or []) if e.get("id")}
    acq_prev = int((prev_evidence.get("wave1") or {}).get("documents_acquired") or 0)
    acq_curr = int((current_evidence.get("wave1") or {}).get("documents_acquired") or 0)
    projection_changed = bool(national_delta or territory_changes)
    new_signals = len(curr_events - prev_events)
    if projection_changed:
        summary = f"La projection évolue dans {len(territory_changes)} territoire(s) depuis l’édition précédente."
    elif new_signals:
        summary = f"{new_signals} nouveau(x) signal(aux) documenté(s) depuis l’édition précédente, sans modification chiffrée de la projection."
    else:
        summary = "Aucune évolution chiffrée de la projection depuis l’édition précédente."
    return {"state": "COMPARED_WITH_PREVIOUS", "previous_edition": previous_dir.name, "projection_changed": projection_changed,
            "national_party_seat_delta": national_delta, "territories_changed": len(territory_changes), "territory_changes": territory_changes[:25],
            "new_documented_signals": new_signals, "documents_acquired_delta": acq_curr - acq_prev, "summary_fr": summary}


def product_version(release_manifest: Path | None) -> str:
    if release_manifest and release_manifest.exists():
        return str(load(release_manifest).get("current_version") or "V0.5")
    return "V0.5"


def build_edition(data_dir: Path, editions_dir: Path, science_ref: str, edition_date: str | None, release_manifest: Path | None) -> None:
    now = now_local()
    edition_date = edition_date or now.date().isoformat()
    for name in VIEW_FILES:
        if not (data_dir / name).exists():
            raise SystemExit(f"ATLAS395_DAILY_FAIL: missing derived view {name}")
    index_path = editions_dir / "index.json"
    index = load(index_path, optional=True) or {"schema_version": "1.0", "editions": []}
    prior_rows = [r for r in index.get("editions", []) if r.get("edition_id") != edition_date]
    prior_rows.sort(key=lambda r: r.get("edition_id", ""))
    previous_id = prior_rows[-1].get("edition_id") if prior_rows else None
    previous_dir = editions_dir / previous_id if previous_id else None
    delta = compare(previous_dir if previous_dir and previous_dir.exists() else None, data_dir)
    edition_dir = editions_dir / edition_date
    staged_hashes = {name: sha(data_dir / name) for name in VIEW_FILES}
    existing_manifest = load(edition_dir / "edition.json", optional=True) if edition_dir.exists() else None
    if existing_manifest:
        if (existing_manifest.get("files") or {}) != staged_hashes:
            raise SystemExit("ATLAS395_DAILY_IMMUTABILITY_FAIL: today's official edition already exists with different content")
    else:
        edition_dir.mkdir(parents=True, exist_ok=False)
        for name in VIEW_FILES:
            shutil.copy2(data_dir / name, edition_dir / name)
    snapshot = load(data_dir / "current_snapshot.json")
    evidence = load(data_dir / "evidence_index.json")
    edition_manifest = {
        "schema_version": "1.0", "edition_id": edition_date, "product_version": product_version(release_manifest),
        "published_at": now.isoformat(timespec="seconds"), "science_ref": science_ref, "forecast_snapshot": snapshot.get("snapshot_id"),
        "source_data_cutoff": snapshot.get("data_cutoff"), "projection_changed_since_previous": delta["projection_changed"],
        "territories_changed_since_previous": delta["territories_changed"], "new_documented_signals_since_previous": delta["new_documented_signals"],
        "evidence_as_of": evidence.get("as_of"), "files": staged_hashes,
        "immutability": "OFFICIAL_EDITION_FILES_ARE_APPEND_ONLY_AND_NEVER_OVERWRITTEN"
    }
    edition_manifest["canonical_sha256"] = canonical({k:v for k,v in edition_manifest.items() if k != "canonical_sha256"})
    if not existing_manifest:
        dump(edition_dir / "edition.json", edition_manifest)
        dump(edition_dir / "daily_update.json", delta)
    dump(data_dir / "daily_update.json", delta)
    dump(editions_dir / "current.json", {"edition_id": edition_date, "product_version": edition_manifest["product_version"],
         "published_at": edition_manifest["published_at"], "science_ref": science_ref, "forecast_snapshot": edition_manifest["forecast_snapshot"],
         "path": f"/editions/{edition_date}/", "daily_update_path": "/data/daily_update.json"})
    new_row = {"edition_id": edition_date, "product_version": edition_manifest["product_version"], "published_at": edition_manifest["published_at"],
               "forecast_snapshot": edition_manifest["forecast_snapshot"], "projection_changed": delta["projection_changed"],
               "territories_changed": delta["territories_changed"], "new_documented_signals": delta["new_documented_signals"], "summary_fr": delta["summary_fr"]}
    rows = [r for r in index.get("editions", []) if r.get("edition_id") != edition_date] + [new_row]
    rows.sort(key=lambda r: r.get("edition_id", ""))
    dump(index_path, {"schema_version": "1.0", "current_edition": edition_date, "editions": rows})
    print(f"ATLAS395_DAILY_OK edition={edition_date} version={edition_manifest['product_version']} snapshot={edition_manifest['forecast_snapshot']}")


def main() -> None:
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="command", required=True)
    sel = sub.add_parser("select-snapshot"); sel.add_argument("--goal100-root", required=True, type=Path)
    build = sub.add_parser("build-edition"); build.add_argument("--data-dir", required=True, type=Path); build.add_argument("--editions-dir", required=True, type=Path)
    build.add_argument("--science-ref", required=True); build.add_argument("--edition-date"); build.add_argument("--release-manifest", type=Path)
    args = ap.parse_args()
    if args.command == "select-snapshot": select_snapshot(args.goal100_root)
    else: build_edition(args.data_dir, args.editions_dir, args.science_ref, args.edition_date, args.release_manifest)

if __name__ == "__main__": main()
