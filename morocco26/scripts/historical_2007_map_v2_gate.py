#!/usr/bin/env python3
"""Fail-closed gate for the leakage-safe 2007 pre-election native-map recovery.

This script deliberately does NOT load the 2007 outcome. It merges only the
post-freeze research evidence files and refuses snapshot-v2 readiness unless all
95 native districts are independently supported by admissible pre-election
sources and their magnitudes sum to 295.
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
D = ROOT / "data" / "goal100" / "historical" / "2007"
BASE = D / "pre_election_map_recovery_v2_evidence.json"
DELTAS = sorted(D.glob("pre_election_map_recovery_v2_delta_*.json"))
OUT = D / "pre_election_map_recovery_v2_gate.json"
CUTOFF = dt.date(2007, 9, 6)
EXPECTED_IDS = {f"M26-2007-{i:03d}" for i in range(1, 96)}
FORBIDDEN_SOURCE_TOKENS = (
    "elections2007.gov.ma",
    "parlement-elections-2007",
    "legislative_2007_outcome",
    "historical_native_map_outcome_transcription",
)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def fail(message: str) -> None:
    raise SystemExit(f"HIST2007_MAP_V2_GATE_FAIL: {message}")


def parse_date(value: object, source_id: str) -> dt.date:
    if not isinstance(value, str):
        fail(f"verified source {source_id} has no exact publication_date")
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        fail(f"verified source {source_id} has invalid publication_date={value!r}")


def source_map(documents: list[tuple[Path, dict]]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for path, doc in documents:
        for source in doc.get("sources", []):
            sid = source.get("source_id")
            if not sid:
                fail(f"source without source_id in {path.name}")
            if sid in out and out[sid] != source:
                fail(f"conflicting duplicate source_id {sid}")
            url = str(source.get("url", "")).lower()
            if any(token in url for token in FORBIDDEN_SOURCE_TOKENS):
                fail(f"same-year outcome-like source forbidden: {sid} {url}")
            out[sid] = source
    return out


def verified_cells(documents: list[tuple[Path, dict]], sources: dict[str, dict]) -> dict[str, dict]:
    merged: dict[str, dict] = {}
    for path, doc in documents:
        cells = []
        # Base checkpoint uses `cells`; append-only deltas use `verified_cells`.
        cells.extend(doc.get("cells", []))
        cells.extend(doc.get("verified_cells", []))
        for cell in cells:
            status = cell.get("status")
            if status not in {"DIRECT_VERIFIED", "DERIVED_VERIFIED_PRE_ELECTION_ARITHMETIC"}:
                continue
            nid = cell.get("native_id")
            if nid not in EXPECTED_IDS:
                fail(f"unexpected native_id {nid!r} in {path.name}")
            try:
                magnitude = int(cell["magnitude"])
            except Exception:
                fail(f"verified cell {nid} lacks integer magnitude")
            if magnitude <= 0:
                fail(f"verified cell {nid} has nonpositive magnitude")
            source_ids = cell.get("source_ids") or []
            if not source_ids:
                fail(f"verified cell {nid} has no source_ids")
            for sid in source_ids:
                if sid not in sources:
                    fail(f"verified cell {nid} references missing source {sid}")
                published = parse_date(sources[sid].get("publication_date"), sid)
                if published > CUTOFF:
                    fail(f"temporal leakage {nid}: {sid} published {published}")
            if status == "DERIVED_VERIFIED_PRE_ELECTION_ARITHMETIC":
                if not cell.get("derivation") or not cell.get("derivation_inputs"):
                    fail(f"derived verified cell {nid} lacks explicit derivation inputs")
            previous = merged.get(nid)
            if previous and int(previous["magnitude"]) != magnitude:
                fail(f"conflicting verified magnitudes for {nid}")
            merged[nid] = cell
    return merged


def main() -> None:
    if not BASE.exists():
        fail(f"missing {BASE.relative_to(ROOT)}")
    documents = [(BASE, read_json(BASE))] + [(p, read_json(p)) for p in DELTAS]
    sources = source_map(documents)
    cells = verified_cells(documents, sources)
    verified_ids = set(cells)
    missing = sorted(EXPECTED_IDS - verified_ids)
    direct = sum(c.get("status") == "DIRECT_VERIFIED" for c in cells.values())
    derived = sum(c.get("status") == "DERIVED_VERIFIED_PRE_ELECTION_ARITHMETIC" for c in cells.values())
    seat_sum = sum(int(c["magnitude"]) for c in cells.values())
    ready = verified_ids == EXPECTED_IDS and seat_sum == 295
    gate = {
        "schema_version": "1.0",
        "gate_id": "M26-HIST-2007-PRE-ELECTION-MAP-V2-GATE",
        "cutoff": CUTOFF.isoformat(),
        "same_year_outcome_loaded": False,
        "documents": [str(p.relative_to(ROOT)) for p, _ in documents],
        "verified_constituencies": len(cells),
        "direct_verified": direct,
        "derived_verified": derived,
        "verified_seat_sum": seat_sum,
        "target_constituencies": 95,
        "target_local_seats": 295,
        "remaining_count": len(missing),
        "remaining_native_ids": missing,
        "temporal_leakage": "PASS",
        "outcome_isolation": "PASS",
        "unknown_discipline": "PASS",
        "status": "READY_FOR_CLEAN_SNAPSHOT_V2_LINEAGE" if ready else "BLOCKED_EVIDENCE_INCOMPLETE",
        "eligible_for_snapshot_v2": ready,
    }
    OUT.write_text(json.dumps(gate, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(gate, ensure_ascii=False, sort_keys=True))
    if ready:
        print("PASS_2007_PRE_ELECTION_MAP_V2_EVIDENCE")
    else:
        print(f"BLOCKED_2007_PRE_ELECTION_MAP_V2_REMAINING_{len(missing)}")


if __name__ == "__main__":
    main()
