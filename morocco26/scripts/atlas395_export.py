#!/usr/bin/env python3
"""Build read-only Atlas 395 product views from frozen MOROCCO//26 artifacts.

This script NEVER mutates scientific artifacts. Its only write target is
morocco26/web/data/.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

M26 = Path(__file__).resolve().parents[1]
GOAL100 = M26 / "data" / "goal100"
WEB_DATA = M26 / "web" / "data"
CORE = ["RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS"]
BUCKETS = CORE + ["OTHER"]


def load_json(path: Path, optional: bool = False) -> dict[str, Any]:
    if optional and not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def dump_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def norm(s: str | None) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower().replace("’", "'")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def entropy_bits(probs: list[float]) -> float:
    return -sum(p * math.log2(p) for p in probs if p and p > 0)


def compact_dist(d: dict[str, Any] | None) -> dict[str, Any] | None:
    if not d:
        return None
    keys = ["mean", "sd", "q025", "q10", "q25", "q50", "q75", "q90", "q975"]
    return {k: d.get(k) for k in keys if k in d}


def seat_payload(d: dict[str, Any] | None) -> dict[str, Any]:
    d = d or {}
    pk = [float(x) for x in d.get("P_seats_k", [])]
    p0 = pk[0] if pk else None
    p1 = pk[1] if len(pk) > 1 else None
    return {
        "expected_seats": d.get("expected_seats"),
        "p_ge_1": None if p0 is None else max(0.0, min(1.0, 1.0 - p0)),
        "p_ge_2": None if p0 is None or p1 is None else max(0.0, min(1.0, 1.0 - p0 - p1)),
        "p_seats_k": pk,
        "marginal_entropy_bits": entropy_bits(pk),
        "mc_standard_error_expected": d.get("mc_standard_error_expected"),
    }


def historical_indexes(year_payload: dict[str, Any]) -> tuple[dict[int, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_id: dict[int, dict[str, Any]] = {}
    by_name: dict[str, dict[str, Any]] = {}
    for row in year_payload.get("rows", []):
        if row.get("list_type") != "locale":
            continue
        rid = row.get("id_constituency")
        if isinstance(rid, int):
            by_id[rid] = row
        by_name[norm(row.get("constituency"))] = row
    return by_id, by_name


def history_row(row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return {"status": "UNKNOWN"}
    votes = row.get("votes", {}) or {}
    total = float(row.get("party_vote_sum") or sum(votes.values()) or 0)
    bucket_votes = {b: float(votes.get(b, 0)) for b in CORE}
    bucket_votes["OTHER"] = max(0.0, total - sum(bucket_votes.values()))
    return {
        "status": "AVAILABLE",
        "turnout_rate_reported": row.get("turnout_rate_reported"),
        "party_vote_sum": row.get("party_vote_sum"),
        "vote_share": {b: (bucket_votes[b] / total if total > 0 else None) for b in BUCKETS},
    }


def aggregate_history(year_payload: dict[str, Any]) -> dict[str, Any]:
    bucket_votes = {b: 0.0 for b in BUCKETS}
    total = 0.0
    rows = 0
    for row in year_payload.get("rows", []):
        if row.get("list_type") != "locale":
            continue
        votes = row.get("votes", {}) or {}
        row_total = float(row.get("party_vote_sum") or sum(votes.values()) or 0)
        core_sum = 0.0
        for b in CORE:
            v = float(votes.get(b, 0))
            bucket_votes[b] += v
            core_sum += v
        bucket_votes["OTHER"] += max(0.0, row_total - core_sum)
        total += row_total
        rows += 1
    return {
        "rows": rows,
        "total_party_votes": total,
        "vote_share": {b: (bucket_votes[b] / total if total > 0 else None) for b in BUCKETS},
    }


def classify_uncertainty(value: float, cuts: tuple[float, float]) -> str:
    lo, hi = cuts
    if value >= hi:
        return "HIGH"
    if value >= lo:
        return "MEDIUM"
    return "LOW"


def quantile_cut(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    xs = sorted(values)
    pos = (len(xs) - 1) * q
    lo = math.floor(pos)
    hi = math.ceil(pos)
    if lo == hi:
        return xs[lo]
    return xs[lo] * (hi - pos) + xs[hi] * (pos - lo)


def build(snapshot: str = "F-1") -> list[Path]:
    forecast_path = GOAL100 / "forecasts" / snapshot / "forecast.json"
    snapshot_manifest_path = GOAL100 / "forecasts" / snapshot / "snapshot_manifest.json"
    forecast = load_json(forecast_path)
    manifest = load_json(snapshot_manifest_path)
    b2 = load_json(GOAL100 / "b2_current_state.json", optional=True)
    wave = load_json(GOAL100 / "b2_current_wave1_acquisition_certificate.json", optional=True)
    history = {
        y: load_json(GOAL100 / "historical" / f"tafra_legislative_{y}_canonical.json", optional=True)
        for y in (2011, 2016, 2021)
    }
    hidx = {y: historical_indexes(p) for y, p in history.items() if p}

    expected_hash = manifest.get("forecast_artifact_hash")
    actual_hash = sha256_file(forecast_path)
    if expected_hash and expected_hash != actual_hash:
        raise SystemExit(f"FROZEN_FORECAST_HASH_MISMATCH expected={expected_hash} actual={actual_hash}")

    local = forecast.get("local_92", [])
    regional = forecast.get("regional_12", [])
    if len(local) != 92:
        raise SystemExit(f"Expected 92 local constituencies, got {len(local)}")
    if len(regional) != 12:
        raise SystemExit(f"Expected 12 regional constituencies, got {len(regional)}")

    raw_unc = []
    for c in local:
        raw_unc.append(sum(entropy_bits((c.get("seat_distribution", {}).get(b) or {}).get("P_seats_k", [])) for b in BUCKETS))
    cuts = (quantile_cut(raw_unc, 1 / 3), quantile_cut(raw_unc, 2 / 3))

    constituency_cards = []
    for c, unc in zip(local, raw_unc):
        cid = c.get("historical_id")
        cname = c.get("name")
        hist = {}
        for y in (2011, 2016, 2021):
            pair = hidx.get(y)
            if not pair:
                hist[str(y)] = {"status": "UNKNOWN"}
                continue
            by_id, by_name = pair
            hist[str(y)] = history_row(by_id.get(cid) or by_name.get(norm(cname)))
        parties = {}
        for b in BUCKETS:
            p = seat_payload(c.get("seat_distribution", {}).get(b))
            p["vote_share"] = compact_dist(c.get("vote_share_distribution", {}).get(b))
            parties[b] = p
        top = sorted(
            ({"party": b, **parties[b]} for b in BUCKETS),
            key=lambda x: (x.get("expected_seats") is not None, x.get("expected_seats") or -1),
            reverse=True,
        )
        constituency_cards.append({
            "constituency_id": c.get("constituency_id"),
            "historical_id": cid,
            "name": cname,
            "region": c.get("region"),
            "magnitude": c.get("magnitude"),
            "parties": parties,
            "top_parties": top[:5],
            "turnout_distribution": compact_dist(c.get("turnout_distribution")),
            "registered_N_distribution": compact_dist(c.get("registered_N_distribution")),
            "valid_vote_distribution": compact_dist(c.get("valid_vote_distribution")),
            "uncertainty": {
                "metric": "SUM_PARTY_MARGINAL_SEAT_ENTROPY_BITS",
                "value": unc,
                "label": classify_uncertainty(unc, cuts),
                "note": "Relative F-1 uncertainty indicator from published marginal seat distributions; not joint allocation entropy.",
            },
            "evidence_2026": {
                "candidate_roster": "UNKNOWN",
                "head_candidate": "UNKNOWN",
                "party_switch": "UNKNOWN",
                "model_state": "STRUCTURAL_ONLY",
                "forecast_impact": "F-1_ONLY",
            },
            "history": hist,
        })

    national = forecast.get("national_395", {})
    national_buckets = national.get("bucket_seat_distribution", {})
    national_projection = {
        "snapshot_id": snapshot,
        "snapshot_class": forecast.get("snapshot_class"),
        "draws": forecast.get("draws"),
        "total_seats": 395,
        "local_seats": sum(int(c.get("magnitude") or 0) for c in local),
        "regional_seats": sum(int(r.get("magnitude") or 0) for r in regional),
        "parties": [],
        "first_place_probability": {
            "status": "NOT_PUBLISHED_IN_F_MINUS_1",
            "value": None,
            "reason": "The frozen public artifact exposes national marginal seat distributions, not party-rank probabilities. Atlas does not reconstruct unsupported joint ranks.",
        },
    }
    for b in BUCKETS:
        d = national_buckets.get(b, {})
        national_projection["parties"].append({"party": b, **(compact_dist(d) if d else {})})
    national_projection["parties"].sort(key=lambda x: x.get("mean") or -1, reverse=True)

    party_cards = []
    hist_aggs = {str(y): aggregate_history(p) for y, p in history.items() if p}
    for b in BUCKETS:
        strengths = sorted(
            ({
                "constituency_id": c["constituency_id"],
                "name": c["name"],
                "region": c["region"],
                "expected_seats": c["parties"][b]["expected_seats"],
                "p_ge_1": c["parties"][b]["p_ge_1"],
            } for c in constituency_cards),
            key=lambda x: (x["expected_seats"] is not None, x["expected_seats"] or -1),
            reverse=True,
        )[:10]
        uncertain = sorted(
            ({
                "constituency_id": c["constituency_id"],
                "name": c["name"],
                "region": c["region"],
                "entropy_bits": c["parties"][b]["marginal_entropy_bits"],
            } for c in constituency_cards),
            key=lambda x: x["entropy_bits"],
            reverse=True,
        )[:10]
        party_cards.append({
            "party": b,
            "national_seats": compact_dist(national_buckets.get(b, {})),
            "p_first": None,
            "p_first_status": "NOT_PUBLISHED_IN_F_MINUS_1",
            "strongest_territories": strengths,
            "most_uncertain_territories": uncertain,
            "historical_local_vote_share": {y: agg["vote_share"].get(b) for y, agg in hist_aggs.items()},
        })

    per_source = wave.get("per_source_states", {}) if wave else {}
    evidence_events = []
    pjd = ((wave.get("format_inventory") or {}).get("by_source") or {}).get("T1_PJD_OFFICIAL", {}) if wave else {}
    if pjd.get("largest_matching_table_rows"):
        evidence_events.append({
            "id": "PJD_ROSTER_SURFACE_WAVE1",
            "as_of": wave.get("certified_at"),
            "source": "T1_PJD_OFFICIAL",
            "status": "DETECTED_NOT_ADMITTED",
            "summary": f"{pjd.get('largest_matching_table_rows')} structured roster-like rows detected on an official PJD source.",
            "forecast_impact": "NONE",
            "reason": "No B2 claim admitted: frozen critical verification/double-entry requirements are not satisfied.",
        })
    evidence_index = {
        "as_of": b2.get("as_of") or wave.get("certified_at"),
        "parent_snapshot": (b2.get("parent_snapshot") or {}).get("snapshot_id", snapshot),
        "collection": b2.get("collection", {}),
        "wave1": {
            "documents_acquired": wave.get("documents_acquired"),
            "documents_blocked": wave.get("documents_blocked"),
            "documents_error": wave.get("documents_error"),
            "b2_claim_records_created": wave.get("b2_claim_records_created"),
            "sources_claim_eligible": wave.get("sources_claim_eligible"),
            "structured_states_available": wave.get("structured_states_available", []),
        },
        "sources": [{"source": s, "states": states} for s, states in per_source.items()],
        "events": evidence_events,
        "blocking_historical_input_classes": (b2.get("historical_panel") or {}).get("blocking_missing_input_classes", []),
        "forecast_change": "NONE",
        "forecast_change_reason": "B2 predictive coefficients remain exactly zero; F-1 remains the current frozen forecast.",
    }

    current_snapshot = {
        "product": "ATLAS 395",
        "snapshot_id": snapshot,
        "snapshot_class": manifest.get("snapshot_class"),
        "created_at": manifest.get("created_at"),
        "data_cutoff": manifest.get("data_cutoff"),
        "protocol_id": manifest.get("protocol_id"),
        "forecast_sha256": actual_hash,
        "status": "FROZEN",
        "draws": manifest.get("monte_carlo_draws") or forecast.get("draws"),
        "geometry": {"local_constituencies": len(local), "local_seats": 305, "regional_constituencies": len(regional), "regional_seats": 90, "total_seats": 395},
        "evidence_state": {
            "candidate": manifest.get("candidate_evidence_state"),
            "event": manifest.get("event_evidence_state"),
            "registered_N": manifest.get("registered_N_state"),
        },
        "timeline": [
            {"id": "F-1", "status": "FROZEN", "created_at": manifest.get("created_at"), "class": manifest.get("snapshot_class"), "sha256": actual_hash},
            {"id": "F0", "status": "NOT_CREATED"},
            {"id": "E_collect", "status": "LOCKED"},
            {"id": "E_reason", "status": "LOCKED"},
            {"id": "E_full", "status": "LOCKED"},
        ],
        "known_limitations": manifest.get("known_limitations", []),
        "read_only_contract": True,
    }

    methodology = {
        "snapshot": current_snapshot,
        "model": {
            "forecast_label": forecast.get("forecast_label"),
            "calibration_status": forecast.get("calibration_status"),
            "party_buckets": forecast.get("party_buckets", BUCKETS),
            "national_projection_origin": "Aggregation of territorial Monte Carlo simulations in frozen F-1 artifact.",
        },
        "certification": {
            "forecast_hash_verified": actual_hash == expected_hash if expected_hash else None,
            "forecast_sha256": actual_hash,
            "expected_forecast_sha256": expected_hash,
            "draws": forecast.get("draws"),
            "local_constituencies": len(local),
            "regional_constituencies": len(regional),
            "total_seats": 395,
        },
        "b2": {
            "phase": b2.get("phase"),
            "closed_gates": (b2.get("gates") or {}).get("closed", []),
            "open_gates": (b2.get("gates") or {}).get("open", []),
            "locked_gates": (b2.get("gates") or {}).get("locked", []),
            "predictive_coefficients": (b2.get("coefficients") or {}).get("predictive"),
        },
        "scientific_separation": {
            "atlas_views_are_model_inputs": False,
            "atlas_writes_scientific_artifacts": False,
            "unknown_preserved": True,
            "f_minus_1_mutable": False,
        },
    }

    change_log = {
        "entries": [
            {"at": manifest.get("created_at"), "type": "MODEL_SNAPSHOT", "snapshot": "F-1", "evidence": "STRUCTURAL_ONLY", "model_change": "F-1_FROZEN"},
            *[{"at": e["as_of"], "type": "NEW_EVIDENCE", "source": e["source"], "summary": e["summary"], "model_change": "NONE", "reason": e["reason"]} for e in evidence_events],
        ]
    }

    outputs = {
        "current_snapshot.json": current_snapshot,
        "national_projection.json": national_projection,
        "constituency_cards.json": {"snapshot_id": snapshot, "count": len(constituency_cards), "constituencies": constituency_cards},
        "party_cards.json": {"snapshot_id": snapshot, "parties": party_cards},
        "evidence_index.json": evidence_index,
        "change_log.json": change_log,
        "methodology_state.json": methodology,
    }
    written = []
    for name, payload in outputs.items():
        path = WEB_DATA / name
        dump_json(path, payload)
        written.append(path)

    public_manifest = {
        "product": "ATLAS 395",
        "generated_from": {
            "snapshot_id": snapshot,
            "forecast_path": str(forecast_path.relative_to(M26)),
            "forecast_sha256": actual_hash,
            "snapshot_manifest_path": str(snapshot_manifest_path.relative_to(M26)),
        },
        "read_only_contract": True,
        "outputs": {p.name: sha256_file(p) for p in written},
    }
    pm = WEB_DATA / "snapshot_manifest.json"
    dump_json(pm, public_manifest)
    written.append(pm)
    return written


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", default="F-1")
    args = ap.parse_args()
    paths = build(args.snapshot)
    print(f"ATLAS395_EXPORT_OK files={len(paths)} output={WEB_DATA}")


if __name__ == "__main__":
    main()
