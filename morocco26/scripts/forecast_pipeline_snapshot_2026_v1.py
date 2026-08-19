#!/usr/bin/env python3
"""Build a versioned current 2026 pre-election evidence snapshot.

This is deliberately a manifest over source layers, not a synthetic merged ballot.
Cross-script / cross-language candidate identity is never inferred here.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
E = G / "e_collect"
OUT = G / "forecast_pipeline" / "snapshot_2026_current_v1.json"
PJD = G / "b2_2026_ballot_roster.json"
ARX = E / "arabic_territory_crosswalk_v1.json"
B2CERT = G / "b2_2026_ballot_certificate.json"
CHECKPOINT = E / "candidate_intelligence_v2_checkpoint_20260818.json"


def rj(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def parse_iso(x):
    if not x:
        return None
    return datetime.fromisoformat(str(x).replace("Z", "+00:00"))


def latest_medias24_run() -> tuple[Path, dict]:
    candidates = []
    for d in (E / "runs").glob("medias24_db_*"):
        manifest = d / "run_manifest.json"
        ledger = d / "candidate_ledger.json"
        if manifest.exists() and ledger.exists():
            m = rj(manifest)
            candidates.append((parse_iso(m.get("created_at")) or datetime.min, d, m))
    if not candidates:
        raise RuntimeError("no archived Medias24 structured candidate run found")
    _, d, m = sorted(candidates, key=lambda x: x[0])[-1]
    return d, m


def main():
    m24_run, manifest = latest_medias24_run()
    m24_ledger_path = m24_run / "candidate_ledger.json"
    m24 = rj(m24_ledger_path)
    pjd = rj(PJD)
    arx = rj(ARX)
    b2 = rj(B2CERT)
    checkpoint = rj(CHECKPOINT) if CHECKPOINT.exists() else None

    # Medias24 is kept as its own source layer. No Arabic/Latin identity merge.
    m24_resolved = [
        r for r in m24
        if r.get("territory_resolution_status") == "RESOLVED" and r.get("constituency_id")
    ]
    m24_party_territories = defaultdict(set)
    m24_cell_claims = defaultdict(int)
    for r in m24_resolved:
        party = str(r.get("party") or "").upper()
        tid = str(r["constituency_id"])
        if party:
            m24_party_territories[party].add(tid)
            m24_cell_claims[(tid, party)] += 1

    # The controller-accepted Arabic crosswalk is identity-only and maps all 92
    # PJD rows to the frozen local-constituency universe.
    cross = {int(r["row_index"]): r for r in arx["records"]}
    official_pjd_territories = []
    for row in pjd["rows"]:
        x = cross.get(int(row["row_index"]))
        if x is None:
            raise RuntimeError(f"missing Arabic crosswalk row {row['row_index']}")
        official_pjd_territories.append(x["constituency_id"])
    if len(official_pjd_territories) != 92 or len(set(official_pjd_territories)) != 92:
        raise RuntimeError("official PJD layer is not a strict 92/92 local mapping")

    m24_territories = {r["constituency_id"] for r in m24_resolved}
    evidence_union = m24_territories | set(official_pjd_territories)
    if len(evidence_union) != 92:
        raise RuntimeError(f"current local evidence union expected 92/92, got {len(evidence_union)}")

    multi_claim_cells = [
        {"territory_id": tid, "party": party, "claim_count": n}
        for (tid, party), n in sorted(m24_cell_claims.items()) if n > 1
    ]

    inputs = [
        {"path": str(m24_ledger_path.relative_to(ROOT)), "sha256": sha(m24_ledger_path),
         "role": "MEDIAS24_STRUCTURED_CANDIDATE_CLAIMS"},
        {"path": str(m24_run.joinpath("run_manifest.json").relative_to(ROOT)),
         "sha256": sha(m24_run / "run_manifest.json"), "role": "MEDIAS24_RUN_MANIFEST"},
        {"path": str(PJD.relative_to(ROOT)), "sha256": sha(PJD),
         "role": "PARTY_OFFICIAL_PJD_HEAD_LIST_ROSTER"},
        {"path": str(ARX.relative_to(ROOT)), "sha256": sha(ARX),
         "role": "IDENTITY_ONLY_ARABIC_TERRITORY_CROSSWALK"},
        {"path": str(B2CERT.relative_to(ROOT)), "sha256": sha(B2CERT),
         "role": "LEGACY_BALLOT_GATE_STATUS_NOT_CURRENT_COVERAGE"},
    ]
    if checkpoint is not None:
        inputs.append({"path": str(CHECKPOINT.relative_to(ROOT)), "sha256": sha(CHECKPOINT),
                       "role": "PRIOR_RECONCILED_CANDIDATE_SURFACE_CHECKPOINT_REFERENCE_ONLY"})

    result = {
        "schema_version": "1.0",
        "snapshot_id": "M26-PRE-ELECTION-2026-CURRENT-V1",
        "status": "SHADOW_PRE_ELECTION_EVIDENCE_SNAPSHOT_NOT_FINAL_BALLOT",
        "F0_modified": False,
        "forecast_effect_authorized": False,
        "temporal_boundary": (
            "All inputs are pre-election evidence. This current snapshot is re-frozen as sources evolve; "
            "a separate final pre-poll snapshot must be frozen after legally accepted candidacies are available."
        ),
        "source_timestamps": {
            "medias24_run_created_at": manifest.get("created_at"),
            "pjd_roster_generated_at": pjd.get("generated_at"),
            "arabic_crosswalk_created_at": arx.get("created_at"),
        },
        "inputs": inputs,
        "layers": {
            "medias24": {
                "candidate_claim_records": int(manifest["counts"]["candidates"]),
                "resolved_candidate_records": len(m24_resolved),
                "local_territories_with_candidate_records": len(m24_territories),
                "parties": int(manifest["counts"]["parties"]),
                "territory_coverage_by_party": {
                    p: len(tids) for p, tids in sorted(m24_party_territories.items())
                },
                "multi_claim_party_territory_cells": len(multi_claim_cells),
                "legal_status": "MEDIA_REPORTED_OR_PARTY_ANNOUNCED_NOT_FINAL_ACCEPTED_BALLOT",
            },
            "official_pjd": {
                "party": "PJD",
                "roster_rows": len(pjd["rows"]),
                "crosswalk_resolved_rows": int(arx["counts"]["resolved"]),
                "local_territories_covered": len(set(official_pjd_territories)),
                "legal_status": "PARTY_OFFICIAL_ANNOUNCEMENT_NOT_FINAL_ACCEPTED_BALLOT",
            },
        },
        "coverage": {
            "local_constituencies_with_any_candidate_evidence": len(evidence_union),
            "local_constituencies_total": 92,
            "local_coverage_fraction": len(evidence_union) / 92,
            "regional_constituency_candidate_roster_status": "NOT_YET_CANONICALLY_CAPTURED_IN_THIS_SNAPSHOT",
            "regional_constituencies_total": 12,
        },
        "identity_safety": {
            "cross_language_candidate_identity_merged_here": False,
            "unified_unique_candidate_count": None,
            "reason": (
                "Medias24 Latin-script claims and official Arabic PJD names remain separate source layers; "
                "this snapshot does not infer person identity across scripts."
            ),
            "prior_checkpoint_reported_reconciled_surface": (
                None if checkpoint is None else checkpoint.get("current_2026_candidate_surface")
            ),
        },
        "legacy_gate_context": {
            "b2_gate": b2.get("gate"),
            "interpretation": (
                "The older B2 FAIL reflects its former corroboration/matching gate and is not evidence that "
                "current source coverage is 0/92; the later accepted Arabic crosswalk resolves the PJD roster 92/92."
            ),
        },
        "seat_forecast_prerequisites": {
            "exact_local_list_universe": "IN_PROGRESS_NOT_FINAL_BALLOT",
            "registered_voters_by_local_constituency": "MISSING_FROM_CURRENT_FORECAST_PIPELINE",
            "regional_list_universe": "MISSING_FROM_CURRENT_CANONICAL_SNAPSHOT",
            "rule": "No exact 2026 seat forecast until these inputs are present and frozen pre-poll.",
        },
        "final_freeze_gate": [
            "Legally accepted local list universe captured at list level (no aggregate OTHER).",
            "Regional list universe captured for all 12 regional constituencies.",
            "Registered-voter counts available for each legal seat-allocation unit.",
            "Every input archived/hashed and timestamped before election outcome availability.",
        ],
        "diagnostic_multi_claim_cells_preview": multi_claim_cells[:20],
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "status": result["status"],
        "m24_candidates": result["layers"]["medias24"]["candidate_claim_records"],
        "m24_territories": result["layers"]["medias24"]["local_territories_with_candidate_records"],
        "official_pjd_territories": result["layers"]["official_pjd"]["local_territories_covered"],
        "union_local_territories": result["coverage"]["local_constituencies_with_any_candidate_evidence"],
        "unique_candidate_count": None,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
