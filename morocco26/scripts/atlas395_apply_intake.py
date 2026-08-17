#!/usr/bin/env python3
"""Merge Atlas Intake detections into the product evidence view only.

This is deliberately incapable of changing forecast values. It enriches the
reader-facing watch layer with detected public-source signals, each explicitly
marked as unverified/no forecast impact.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--intake", required=True)
    ap.add_argument("--evidence", required=True)
    args = ap.parse_args()
    intake_path, ev_path = Path(args.intake), Path(args.evidence)
    ev = load(ev_path)
    intake = load(intake_path) if intake_path.exists() else {"detections":[]}

    existing = list(ev.get("events") or [])
    seen = {x.get("id") for x in existing}
    added = 0
    for d in intake.get("detections", []):
        if d.get("id") in seen:
            continue
        existing.append({
            "id": d.get("id"),
            "source": d.get("source_id"),
            "status": "DETECTED_BY_DAILY_WATCH",
            "summary": d.get("title") or "Information électorale détectée dans la veille quotidienne",
            "reason": "Signal repéré automatiquement dans une source publique suivie. Il reste hors du calcul tant qu'il n'a pas satisfait les critères de validation scientifique.",
            "forecast_impact": "NONE",
            "url": d.get("url"),
            "retrieved_at": d.get("retrieved_at"),
            "content_sha256": d.get("content_sha256"),
            "intake_relevance_score": d.get("relevance_score"),
            "intake_status": d.get("status"),
        })
        seen.add(d.get("id")); added += 1

    # The watch layer may grow; the scientific state is untouched and authoritative.
    ev["events"] = existing
    ev["daily_watch"] = {
        "run_at": intake.get("run_at"),
        "active_sources_scanned": intake.get("active_sources_scanned", 0),
        "detections": intake.get("detection_count", 0),
        "probe_count": intake.get("probe_count", 0),
        "probe_failures": intake.get("probe_failures", 0),
        "contract": "VEILLE_PRODUIT_SEULEMENT_AUCUNE_INCIDENCE_AUTOMATIQUE_SUR_LA_PROJECTION",
    }
    dump(ev_path, ev)
    print(f"ATLAS395_INTAKE_MERGE_OK added={added} total_events={len(existing)}")

if __name__ == "__main__":
    main()
