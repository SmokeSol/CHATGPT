#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

M26 = Path(__file__).resolve().parents[1]
DATA = M26 / "web" / "data"
GOAL100 = M26 / "data" / "goal100"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(cond, msg):
    if not cond:
        raise SystemExit(f"ATLAS395_VALIDATION_FAIL: {msg}")


def main():
    snap = load("current_snapshot.json")
    nat = load("national_projection.json")
    cards = load("constituency_cards.json")
    parties = load("party_cards.json")
    ev = load("evidence_index.json")
    meth = load("methodology_state.json")
    man = load("snapshot_manifest.json")

    require(snap["snapshot_id"] == "F-1", "V0 must be derived from F-1")
    require(snap["status"] == "FROZEN", "F-1 must remain frozen")
    require(snap["read_only_contract"] is True, "read-only contract missing")
    require(snap["geometry"] == {"local_constituencies": 92, "local_seats": 305, "regional_constituencies": 12, "regional_seats": 90, "total_seats": 395}, "geometry mismatch")
    require(nat["total_seats"] == 395 and nat["local_seats"] == 305 and nat["regional_seats"] == 90, "national seat accounting mismatch")
    require(cards["count"] == 92 and len(cards["constituencies"]) == 92, "constituency count mismatch")
    require(sum(int(c["magnitude"]) for c in cards["constituencies"]) == 305, "local magnitude sum != 305")
    require(len(parties["parties"]) == 9, "party buckets != 9")
    require(ev["forecast_change"] == "NONE", "B2 must not silently change F-1")
    require(meth["scientific_separation"]["atlas_views_are_model_inputs"] is False, "Atlas cannot become model input")
    require(meth["scientific_separation"]["atlas_writes_scientific_artifacts"] is False, "Atlas cannot write science artifacts")

    unknowns = 0
    for c in cards["constituencies"]:
        require(c["evidence_2026"]["candidate_roster"] == "UNKNOWN", f"UNKNOWN collapsed in {c['constituency_id']}")
        unknowns += 1
        for p in c["parties"].values():
            for key in ("p_ge_1", "p_ge_2"):
                if p[key] is not None:
                    require(-1e-12 <= p[key] <= 1 + 1e-12, f"invalid probability {key}")
            if p["p_seats_k"]:
                require(abs(sum(p["p_seats_k"]) - 1.0) < 1e-6, "seat distribution does not sum to 1")
    require(unknowns == 92, "UNKNOWN preservation incomplete")

    frozen = GOAL100 / "forecasts" / "F-1" / "forecast.json"
    require(sha(frozen) == snap["forecast_sha256"], "frozen source hash mismatch")
    for name, expected in man["outputs"].items():
        require(sha(DATA / name) == expected, f"public output hash mismatch {name}")

    print("ATLAS395_VALIDATION_OK constituencies=92 seats=395 unknown_preserved=92 read_only=true")


if __name__ == "__main__":
    main()
