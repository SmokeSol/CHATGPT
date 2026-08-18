#!/usr/bin/env python3
"""Build the frozen blinded DEVELOPMENT packet bundle for E_reason V1.

Scientific boundaries:
- Reads ONLY pre-development structural inputs (2011 votes), frozen constituency metadata,
  and the already-certified pre-cutoff 2016 evidence layers enumerated by the strict gate.
- NEVER reads the 2016 or 2021 outcome files.
- Produces a complete 92 x 9 panel with explicit MISSING values.
- Generates a cryptographically random real->anonymous mapping outside the repository output.
- Commits only the mapping SHA-256 and blinded packets; the mapping itself must stay outside judge access.

This script is intentionally DEVELOPMENT-only. Holdout packet generation is a separate step after
2016 judgments and lambda calibration are frozen.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import secrets
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
HIST = ROOT / "data" / "goal100" / "historical"
CONST = ROOT / "data" / "constituencies_goal75.csv"
STRICT_GATE = E / "evidence" / "strict_2016_integrity_gate" / "gate.json"
CLOSURE = E / "evidence" / "historical_collection_closure" / "certificate.json"
INFO = E / "e_reason_information_set_v1.json"
PROMPT = E / "c2_prompt_v1.md"

OUTDIR = E / "blind" / "development"
BUNDLE = OUTDIR / "blind_bundle.json"
MANIFEST = OUTDIR / "bundle_manifest.json"
SEAL = OUTDIR / "mapping_seal.json"
PROMPT_FREEZE = OUTDIR / "c2_prompt_freeze.json"

CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
PARTIES = (*CORE, "OTHER")

# The ordering is inherited from the frozen information-set contract. Every feature is emitted for every cell.
FEATURES = (
    "BALLOT_LIST_PRESENT",
    "CANDIDATE_REGISTERED_RANK",
    "INCUMBENT_SAME_PARTY_SAME_DISTRICT",
    "INCUMBENT_SAME_PARTY_MOVED_DISTRICT",
    "FORMER_MP",
    "PARTY_SWITCH_IN",
    "PARTY_SWITCH_OUT",
    "LOCAL_EXECUTIVE_OFFICE",
    "PROVINCIAL_OR_REGIONAL_OFFICE",
    "NATIONAL_OR_REGIONAL_PARTY_OFFICE",
    "FORMER_MINISTER_OR_NATIONAL_OFFICE",
    "FORMAL_ENDORSEMENT",
    "FORMAL_LIST_ALLIANCE",
    "WITHDRAWN_OR_DISQUALIFIED",
    "OFFICIAL_SANCTION_OR_INVESTIGATION",
    "VERIFIED_DEATH_OR_INCAPACITY",
    "PRINCIPAL_COMPETITOR_COUNT_WITH_VERIFIED_PROFILE",
    "SOURCE_CONFLICT",
    "EVIDENCE_COUNT",
    "SOURCE_CLASS_MAX",
)

# Label normalization is used internally only; real labels never enter the blind bundle.
ALIASES = {
    "rabat el mouhit": "rabat ocean",
    "rabat al mouhit": "rabat ocean",
    "rabat challah": "rabat chellah",
    "rabat chellah": "rabat chellah",
    "fes janoubia": "fes sud",
    "fes chamalia": "fes nord",
    "fes shamalia": "fes nord",
    "marrakech medina": "medina sidi youssef",
    "marrakech gueliz ennakhil": "gueliz nakhil",
    "marrakech gueliz nakhil": "gueliz nakhil",
    "marrakech menara": "menara",
    "moulay yaacoub": "moulay yaacoub",
    "moulay yacoub": "moulay yaacoub",
    "m diq fnideq": "m diq fnideq",
}


def die(msg: str) -> None:
    raise SystemExit(msg)


def canon_bytes(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")


def sha_obj(obj: Any) -> str:
    return hashlib.sha256(canon_bytes(obj)).hexdigest()


def sha_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(s: Any) -> str:
    x = unicodedata.normalize("NFKD", str(s or ""))
    x = "".join(ch for ch in x if not unicodedata.combining(ch))
    x = x.lower().replace("’", "'")
    x = re.sub(r"[^a-z0-9]+", " ", x)
    x = re.sub(r"\s+", " ", x).strip()
    return ALIASES.get(x, x)


def sim(a: str, b: str) -> float:
    if a == b:
        return 1.0
    sa, sb = set(a.split()), set(b.split())
    j = len(sa & sb) / max(1, len(sa | sb))
    seq = SequenceMatcher(None, a, b).ratio()
    # Token overlap matters more than punctuation/transliteration detail.
    return 0.58 * seq + 0.42 * j


def load_constituencies() -> list[dict[str, Any]]:
    with CONST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 92:
        die(f"expected 92 constituencies, got {len(rows)}")
    ids = [r["constituency_id"] for r in rows]
    if len(set(ids)) != 92:
        die("constituency_id is not unique")
    for r in rows:
        r["seats"] = int(r["seats"])
    return rows


def load_2011_local_rows() -> list[dict[str, Any]]:
    # CRITICAL: this is the ONLY historical vote-result file this builder may open.
    # 2016/2021 outcome files are deliberately absent from the code path.
    path = HIST / "tafra_legislative_2011_canonical.json"
    data = read_json(path)
    rows = [r for r in data["rows"] if str(r.get("list_type", "")).lower() in {"locale", "local"}]
    if len(rows) != 92:
        die(f"expected 92 local rows in 2011 baseline input, got {len(rows)}")
    return rows


def match_baseline_rows(consts: list[dict[str, Any]], hist: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """One-to-one label match without consulting target-election outcomes."""
    c_norm = {r["constituency_id"]: norm(r["name"]) for r in consts}
    h_norm = {str(r["id_constituency"]): norm(r.get("constituency")) for r in hist}

    pairs = []
    for c in consts:
        cid = c["constituency_id"]
        for h in hist:
            hid = str(h["id_constituency"])
            score = sim(c_norm[cid], h_norm[hid])
            # Seat magnitude, if available in the source row, is a pre-development structural discriminator.
            h_seats = h.get("seats", h.get("magnitude", h.get("seat_magnitude")))
            if h_seats not in (None, ""):
                try:
                    if int(h_seats) == int(c["seats"]):
                        score += 0.06
                    else:
                        score -= 0.08
                except Exception:
                    pass
            pairs.append((score, cid, hid, c, h))

    pairs.sort(key=lambda z: (-z[0], z[1], z[2]))
    assigned_c: set[str] = set()
    assigned_h: set[str] = set()
    out: dict[str, dict[str, Any]] = {}
    audit: list[dict[str, Any]] = []
    for score, cid, hid, c, h in pairs:
        if cid in assigned_c or hid in assigned_h:
            continue
        if score < 0.43:
            continue
        assigned_c.add(cid)
        assigned_h.add(hid)
        out[cid] = h
        audit.append({
            "constituency_id": cid,
            "constituency_name": c["name"],
            "historical_id": hid,
            "historical_name": h.get("constituency"),
            "match_score": round(float(score), 6),
        })

    if len(out) != 92:
        missing_c = [r["constituency_id"] for r in consts if r["constituency_id"] not in out]
        missing_h = [str(r["id_constituency"]) + ":" + str(r.get("constituency")) for r in hist if str(r["id_constituency"]) not in assigned_h]
        die("baseline territory matching did not reach 92/92\nmissing current=" + repr(missing_c) + "\nmissing historical=" + repr(missing_h))

    # Guard weak or ambiguous matches. A weak label match is worse than an explicit failure.
    weak = [a for a in audit if a["match_score"] < 0.50]
    if weak:
        die("weak baseline territory matches require explicit audit aliases: " + json.dumps(weak, ensure_ascii=False))
    return out, audit


def bucket_shares(row: dict[str, Any]) -> dict[str, float]:
    votes = row.get("votes") or {}
    vals = {p: float(votes.get(p, 0) or 0) for p in CORE}
    vals["OTHER"] = sum(float(v or 0) for p, v in votes.items() if p not in CORE)
    total = sum(vals.values())
    if not math.isfinite(total) or total <= 0:
        die(f"invalid 2011 vote baseline for historical id {row.get('id_constituency')}")
    return {p: vals[p] / total for p in PARTIES}


def walk_dicts(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk_dicts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk_dicts(v)


def source_class_short(v: Any, default: str = "T1") -> str:
    x = str(v or "").upper()
    if x.startswith("T0"):
        return "T0"
    if x.startswith("T1"):
        return "T1"
    if "M24" in x or "MEDIAS24" in x:
        return "M24"
    return default


def load_safe_2016_evidence(valid_cids: set[str]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    gate = read_json(STRICT_GATE)
    if gate.get("status") != "E_REASON_2016_STRICT_INTEGRITY_GATE_PASS":
        die("strict 2016 integrity gate is not PASS")
    specs = gate.get("source_artifacts") or {}
    records: dict[tuple[str, str], dict[str, dict[str, Any]]] = defaultdict(dict)

    for key, rel in specs.items():
        uk = str(key).upper()
        if "DIAGNOSTIC" in uk or "CERTIFICATE" in uk:
            continue
        if not isinstance(rel, str) or not rel.endswith(".json"):
            continue
        path = ROOT.parent / rel if rel.startswith("morocco26/") else ROOT / rel
        if not path.exists():
            die(f"certified strict-gate source missing: {rel}")
        fallback_party = "PJD" if uk.startswith("PJD") else ("PPS" if uk.startswith("PPS") else None)
        doc = read_json(path)
        for d in walk_dicts(doc):
            cid = d.get("constituency_id")
            if cid not in valid_cids:
                continue
            party = str(d.get("party") or d.get("party_bucket") or fallback_party or "").upper()
            if party not in PARTIES:
                continue
            yr = d.get("year", d.get("cycle"))
            if yr not in (None, "", 2016, "2016"):
                continue

            fv = d.get("feature_values") if isinstance(d.get("feature_values"), dict) else {}
            explicit_endorsement = d.get("FORMAL_ENDORSEMENT") is True or fv.get("FORMAL_ENDORSEMENT") is True
            explicit_features = set()
            for feat in FEATURES:
                if d.get(feat) is True or fv.get(feat) is True:
                    explicit_features.add(feat)
            if explicit_endorsement:
                explicit_features.add("FORMAL_ENDORSEMENT")

            # Keep one anonymizable record per distinct certified object. No raw text or names leave this function.
            rid_material = {"source": rel, "cid": cid, "party": party, "features": sorted(explicit_features), "object": d}
            rid = hashlib.sha256(canon_bytes(rid_material)).hexdigest()[:24]
            records[(cid, party)][rid] = {
                "record_id": "SRC_" + rid,
                "source_class": source_class_short(d.get("source_class"), "T1"),
                "explicit_features": explicit_features,
            }

    return {k: list(v.values()) for k, v in records.items()}


def feature_row(feature_id: str, *, status: str = "MISSING", value: Any = None, source_class: str = "NONE", record_ids: list[str] | None = None, conflict: bool = False) -> dict[str, Any]:
    return {
        "feature_id": feature_id,
        "status": status,
        "value": value,
        "source_class": source_class,
        "source_record_ids": sorted(record_ids or []),
        "conflict": bool(conflict),
    }


def strongest_class(classes: list[str]) -> str:
    order = {"NONE": 0, "M24": 1, "T1": 2, "T0": 3}
    return max(classes, key=lambda x: order.get(x, 0), default="NONE")


def random_id(prefix: str, nbytes: int = 8) -> str:
    return prefix + "_" + secrets.token_hex(nbytes).upper()


def make_mapping(consts: list[dict[str, Any]], baseline_match_audit: list[dict[str, Any]]) -> dict[str, Any]:
    regions = sorted({r["region"] for r in consts})
    mapping = {
        "schema_version": "1.0",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "real_election": 2016,
        "anonymous_election_id": random_id("E"),
        "territories": {r["constituency_id"]: random_id("T") for r in consts},
        "regions": {r: random_id("R") for r in regions},
        "parties": {p: random_id("P") for p in PARTIES},
        "baseline_territory_match_audit": baseline_match_audit,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "rule": "SECRET_MAPPING_DO_NOT_EXPOSE_TO_C1_C2_H1_BEFORE_JUDGMENTS_FREEZE",
    }
    return mapping


def build_party_features(cid: str, party: str, evidence: dict[tuple[str, str], list[dict[str, Any]]], territory_profile_parties: set[str]) -> list[dict[str, Any]]:
    recs = evidence.get((cid, party), [])
    ids = [r["record_id"] for r in recs]
    classes = [r["source_class"] for r in recs]
    srcmax = strongest_class(classes)
    explicit = set().union(*(r["explicit_features"] for r in recs)) if recs else set()
    out: list[dict[str, Any]] = []

    for feat in FEATURES:
        if feat == "BALLOT_LIST_PRESENT":
            if recs:
                out.append(feature_row(feat, status="VERIFIED", value=True, source_class=srcmax, record_ids=ids))
            else:
                out.append(feature_row(feat))
        elif feat == "FORMAL_ENDORSEMENT":
            if feat in explicit:
                endorsing = [r for r in recs if feat in r["explicit_features"]]
                out.append(feature_row(feat, status="VERIFIED", value=True, source_class=strongest_class([r["source_class"] for r in endorsing]), record_ids=[r["record_id"] for r in endorsing]))
            else:
                out.append(feature_row(feat))
        elif feat == "PRINCIPAL_COMPETITOR_COUNT_WITH_VERIFIED_PROFILE":
            if territory_profile_parties:
                competitor_ids = []
                for q in territory_profile_parties:
                    if q != party:
                        competitor_ids.extend(r["record_id"] for r in evidence.get((cid, q), []))
                out.append(feature_row(feat, status="VERIFIED", value=max(0, len(territory_profile_parties - {party})), source_class=strongest_class([r["source_class"] for q in territory_profile_parties for r in evidence.get((cid, q), [])]), record_ids=competitor_ids))
            else:
                out.append(feature_row(feat))
        elif feat == "SOURCE_CONFLICT":
            if recs:
                out.append(feature_row(feat, status="VERIFIED", value=False, source_class=srcmax, record_ids=ids))
            else:
                out.append(feature_row(feat))
        elif feat == "EVIDENCE_COUNT":
            if recs:
                out.append(feature_row(feat, status="VERIFIED", value=len(recs), source_class=srcmax, record_ids=ids))
            else:
                out.append(feature_row(feat))
        elif feat == "SOURCE_CLASS_MAX":
            if recs:
                out.append(feature_row(feat, status="VERIFIED", value=srcmax, source_class=srcmax, record_ids=ids))
            else:
                out.append(feature_row(feat))
        elif feat in explicit:
            # Generic path for any directional feature that was ALREADY explicitly structured in a certified source.
            supporting = [r for r in recs if feat in r["explicit_features"]]
            out.append(feature_row(feat, status="VERIFIED", value=True, source_class=strongest_class([r["source_class"] for r in supporting]), record_ids=[r["record_id"] for r in supporting]))
        else:
            out.append(feature_row(feat))
    if len(out) != len(FEATURES):
        die("feature panel construction error")
    return out


def no_leak_scan(bundle: dict[str, Any], consts: list[dict[str, Any]], mapping: dict[str, Any]) -> dict[str, Any]:
    text = json.dumps(bundle, ensure_ascii=False, sort_keys=True)
    violations = []

    # Real labels are forbidden in C2 packets. We scan values, not repository paths.
    forbidden_exact = set(PARTIES)
    forbidden_exact.update(r["constituency_id"] for r in consts)
    forbidden_exact.update(r["name"] for r in consts)
    forbidden_exact.update(r["region"] for r in consts)
    forbidden_exact.update({"2016", "2021", "Morocco", "Maroc", "medias24.com", "pps.ma", "pjd.ma"})

    for s in forbidden_exact:
        if not s:
            continue
        # Exact JSON string-token scan avoids false positives such as generic English words containing a party acronym.
        if json.dumps(s, ensure_ascii=False) in text:
            violations.append(s)
    if re.search(r"https?://|www\.", text, flags=re.I):
        violations.append("URL_PATTERN")
    # Candidate evidence is intentionally reduced to structured features, so Arabic script is not expected in blind packets.
    if re.search(r"[\u0600-\u06ff]", text):
        violations.append("ARABIC_RAW_TEXT")

    # Mapping-side sanity: all anonymous IDs must be unique and absent from real labels.
    anon_ids = [mapping["anonymous_election_id"], *mapping["territories"].values(), *mapping["regions"].values(), *mapping["parties"].values()]
    if len(anon_ids) != len(set(anon_ids)):
        violations.append("ANON_ID_COLLISION")

    return {"status": "PASS" if not violations else "FAIL", "violations": violations, "scan_version": "1.0"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret-mapping-output", required=True, help="Path OUTSIDE the repository for the secret real->anonymous mapping")
    ap.add_argument("--force", action="store_true", help="Only for CI repair before any judgment exists")
    args = ap.parse_args()
    secret_path = Path(args.secret_mapping_output).resolve()

    closure = read_json(CLOSURE)
    if closure.get("status") != "PASS" or closure.get("collection_phase") != "CLOSED_PASS":
        die("historical collection closure is not PASS")
    if closure.get("invariants", {}).get("outcomes_unsealed") is not False:
        die("outcomes are already unsealed; historical packet regeneration forbidden")
    if closure.get("invariants", {}).get("predictive_judgments_generated") is not False:
        die("predictive judgments already exist; packet regeneration forbidden")

    if (BUNDLE.exists() or SEAL.exists()) and not args.force:
        die("development bundle/seal already exists; refusing regeneration")

    info = read_json(INFO)
    allowed = [x["id"] for x in info["allowed_candidate_and_event_features"]]
    if tuple(allowed) != FEATURES:
        die("builder feature order diverges from frozen information-set contract")
    if not PROMPT.exists():
        die("frozen C2 prompt must exist before packet generation")

    consts = load_constituencies()
    hist11 = load_2011_local_rows()
    baseline_rows, match_audit = match_baseline_rows(consts, hist11)
    evidence = load_safe_2016_evidence({r["constituency_id"] for r in consts})

    # Confirm evidence coverage still matches the already-certified gate at the territory level.
    evidence_districts = {cid for cid, _ in evidence}
    if len(evidence_districts) < 70:
        die(f"safe evidence extraction unexpectedly covers only {len(evidence_districts)} districts")

    mapping = make_mapping(consts, match_audit)
    mapping_sha = sha_obj(mapping)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_bytes(canon_bytes(mapping))

    packets = []
    for c in sorted(consts, key=lambda r: mapping["territories"][r["constituency_id"]]):
        cid = c["constituency_id"]
        base = bucket_shares(baseline_rows[cid])
        ranked = sorted(PARTIES, key=lambda p: (-base[p], p))
        rank = {p: i + 1 for i, p in enumerate(ranked)}
        profiled_parties = {p for p in PARTIES if evidence.get((cid, p))}

        party_objs = []
        for p in PARTIES:
            feats = build_party_features(cid, p, evidence, profiled_parties)
            observed_feature_count = sum(1 for f in feats if f["status"] not in {"MISSING", "NOT_FOUND", "UNVERIFIED", "DATA_BLOCKED"})
            party_objs.append({
                "anonymous_party_id": mapping["parties"][p],
                "baseline_vote_share": round(float(base[p]), 12),
                "baseline_rank": int(rank[p]),
                "baseline_uncertainty_summary": {
                    "status": "MISSING",
                    "reason_code": "NO_PRE_DEVELOPMENT_CALIBRATED_UNCERTAINTY",
                },
                "evidence_completeness": {
                    "observed_feature_count": observed_feature_count,
                    "allowed_feature_count": len(FEATURES),
                    "missingness_explicit": True,
                },
                "features": feats,
            })
        party_objs.sort(key=lambda x: x["anonymous_party_id"])

        packet_core = {
            "schema_version": "1.0",
            "experiment_id": "M26-GOAL100-E-REASON-V1",
            "condition_eligible": ["C1_RULE_ONLY", "C2_LLM_RESIDUAL"],
            "anonymous_election_id": mapping["anonymous_election_id"],
            "anonymous_territory_id": mapping["territories"][cid],
            "anonymous_region_id": mapping["regions"][c["region"]],
            "seat_magnitude": int(c["seats"]),
            "parties": party_objs,
        }
        packet_sha = sha_obj(packet_core)
        packet = dict(packet_core)
        packet["packet_sha256"] = packet_sha
        packets.append(packet)

    if len(packets) != 92 or sum(len(p["parties"]) for p in packets) != 828:
        die("panel cardinality failure")

    bundle_core = {
        "schema_version": "1.0",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "bundle_role": "BLINDED_DEVELOPMENT_C1_C2_INPUT",
        "anonymous_election_id": mapping["anonymous_election_id"],
        "packet_count": 92,
        "party_cells": 828,
        "missingness_policy": "EXPLICIT_MISSING_NEVER_DROP_CELL",
        "baseline_policy": "OUTCOME_FREE_PRE_DEVELOPMENT_PERSISTENCE_BASELINE",
        "uncertainty_policy": "EXPLICIT_MISSING_WHERE_NO_PRE_DEVELOPMENT_CALIBRATED_UNCERTAINTY_EXISTS",
        "packets": packets,
    }
    bundle_sha = sha_obj(bundle_core)
    bundle = dict(bundle_core)
    bundle["bundle_sha256"] = bundle_sha

    scan = no_leak_scan(bundle, consts, mapping)
    if scan["status"] != "PASS":
        die("blind-bundle leakage scan failed: " + json.dumps(scan, ensure_ascii=False))

    OUTDIR.mkdir(parents=True, exist_ok=True)
    BUNDLE.write_text(json.dumps(bundle, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    prompt_sha = sha_file(PROMPT)
    prompt_freeze = {
        "schema_version": "1.0",
        "status": "FROZEN_BEFORE_C2_JUDGMENT",
        "prompt_path": "morocco26/data/goal100/e_reason/c2_prompt_v1.md",
        "prompt_sha256": prompt_sha,
        "output_schema_path": "morocco26/data/goal100/e_reason/e_reason_output_schema_v1.json",
        "conditions_path": "morocco26/data/goal100/e_reason/e_reason_conditions_v1.json",
        "semantic_edits_after_freeze": "FORBIDDEN_WITHOUT_NEW_EXPERIMENT_VERSION",
    }
    PROMPT_FREEZE.write_text(json.dumps(prompt_freeze, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    manifest = {
        "schema_version": "1.0",
        "status": "FROZEN_BLIND_DEVELOPMENT_BUNDLE",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "bundle_path": "morocco26/data/goal100/e_reason/blind/development/blind_bundle.json",
        "bundle_sha256": bundle_sha,
        "packets": 92,
        "party_cells": 828,
        "packet_sha256": [p["packet_sha256"] for p in packets],
        "leakage_scan": scan,
        "baseline_input": {
            "role": "pre-development structural C0",
            "method": "normalized 2011 local vote shares in frozen nine-party buckets",
            "target_outcome_read": False,
            "target_outcome_files_read": [],
        },
        "feature_input": {
            "strict_gate_sha256": sha_file(STRICT_GATE),
            "historical_collection_closure_sha256": sha_file(CLOSURE),
            "missing_unobserved_features": True,
            "unsafe_layers_excluded_by_upstream_gate": closure["gates"]["2016"].get("unsafe_layers_excluded", []),
        },
        "c2_prompt_sha256": prompt_sha,
        "mapping_sha256": mapping_sha,
        "mapping_committed": False,
        "judge_must_not_receive_mapping": True,
    }
    MANIFEST.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    seal = {
        "schema_version": "1.0",
        "seal_id": "M26-E-REASON-DEVELOPMENT-MAPPING-SEAL-V1",
        "status": "SEALED_BEFORE_ANY_PREDICTIVE_JUDGMENT",
        "experiment_id": "M26-GOAL100-E-REASON-V1",
        "anonymous_election_id": mapping["anonymous_election_id"],
        "mapping_sha256": mapping_sha,
        "mapping_material_committed": False,
        "mapping_material_judge_access": False,
        "blind_bundle_sha256": bundle_sha,
        "blind_packet_count": 92,
        "blind_party_cells": 828,
        "c2_prompt_sha256": prompt_sha,
        "leakage_scan": scan,
        "unseal_rule": "MAPPING_MATERIAL_MAY_NOT_BE_EXPOSED_TO_C2_BEFORE_CORRESPONDING_JUDGMENT_HASHES_ARE_FROZEN",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    SEAL.write_text(json.dumps(seal, sort_keys=True, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        "status": "PASS",
        "bundle": str(BUNDLE.relative_to(ROOT.parent)),
        "bundle_sha256": bundle_sha,
        "mapping_sha256": mapping_sha,
        "prompt_sha256": prompt_sha,
        "packets": 92,
        "cells": 828,
        "evidence_districts": len(evidence_districts),
        "secret_mapping_output": str(secret_path),
    }, indent=2))


if __name__ == "__main__":
    main()
