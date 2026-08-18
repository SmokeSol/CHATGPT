#!/usr/bin/env python3
"""Build the frozen blinded HOLDOUT packet bundle for E_reason V1.

Scientific boundaries:
- Requires the 2016-calibrated lambdas to be frozen before this script runs.
- Reproduces the frozen Bstar V0_PERSIST 2016->holdout structural forecast using ONLY
  2011 and 2016 outcomes and the frozen Bstar Monte-Carlo recipe.
- Reads only already-certified PRE-CUTOFF holdout evidence.
- NEVER reads the target holdout outcome file.
- Produces a complete 92 x 9 panel with explicit MISSING values.
- Uses an independently randomized anonymization mapping stored outside the repository.
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
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
HIST = ROOT / "data" / "goal100" / "historical"
CONST = ROOT / "data" / "constituencies_goal75.csv"
INFO = E / "e_reason_information_set_v1.json"
CONDS = E / "e_reason_conditions_v1.json"
PROMPT = E / "c2_prompt_v1.md"
LAMBDA_FREEZE = E / "lambda_freeze_v1.json"
CLOSURE = E / "evidence" / "historical_collection_closure" / "certificate.json"
GATE = E / "evidence" / "2021_head_list_rank_enrichment" / "gate.json"
ROSTER = E / "evidence" / "2021_head_list_rank_enrichment" / "enriched_candidate_roster.json"
DEV_BUNDLE = E / "blind" / "development" / "blind_bundle.json"

OUTDIR = E / "blind" / "holdout"
BUNDLE = OUTDIR / "blind_bundle.json"
MANIFEST = OUTDIR / "bundle_manifest.json"
SEAL = OUTDIR / "mapping_seal.json"

CORE = ("RNI", "PAM", "PI", "PJD", "USFP", "MP", "UC", "PPS")
PARTIES = (*CORE, "OTHER")
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

# Exact frozen Bstar V0 recipe constants from goal100_bstar_hindcast.py.
EPS_VOTES = 0.5
N_SAMPLES = 4096
SEED = 260816

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
    "taroudannt al janoubia": "taroudant sud",
    "taroudannt chamalia": "taroudant nord",
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
    return 0.58 * seq + 0.42 * j


def load_constituencies() -> list[dict[str, Any]]:
    with CONST.open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 92 or len({r["constituency_id"] for r in rows}) != 92:
        die("frozen constituency metadata must contain 92 unique rows")
    for r in rows:
        r["seats"] = int(r["seats"])
    return rows


def load_local(year: int) -> list[dict[str, Any]]:
    # CRITICAL: caller may request only 2011 or 2016. No target outcome path exists here.
    if year not in {2011, 2016}:
        die("holdout packet builder may open historical vote files only for 2011 and 2016")
    data = read_json(HIST / f"tafra_legislative_{year}_canonical.json")
    rows = [r for r in data["rows"] if str(r.get("list_type", "")).lower() in {"locale", "local"}]
    if len(rows) != 92:
        die(f"expected 92 local rows for {year}")
    return rows


def match_rows(consts: list[dict[str, Any]], hist: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    pairs = []
    for c in consts:
        cn = norm(c["name"])
        for h in hist:
            hn = norm(h.get("constituency"))
            score = sim(cn, hn)
            h_seats = h.get("seats", h.get("magnitude", h.get("seat_magnitude")))
            if h_seats not in (None, ""):
                try:
                    score += 0.06 if int(h_seats) == c["seats"] else -0.08
                except Exception:
                    pass
            pairs.append((score, c["constituency_id"], str(h["id_constituency"]), h))
    pairs.sort(key=lambda x: (-x[0], x[1], x[2]))
    used_c, used_h, out = set(), set(), {}
    for score, cid, hid, h in pairs:
        if cid in used_c or hid in used_h or score < 0.43:
            continue
        used_c.add(cid); used_h.add(hid); out[cid] = h
    if len(out) != 92:
        die(f"2016 baseline territory mapping is not 92/92: {len(out)}")
    return out


def bucket_counts(row: dict[str, Any]) -> np.ndarray:
    raw = row.get("votes", {})
    vals = [float(raw.get(p, 0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p, v in raw.items() if p not in CORE))
    arr = np.asarray(vals, dtype=float)
    if np.any(arr < 0) or arr.sum() <= 0:
        die("invalid vote vector")
    return arr


def clr(row: dict[str, Any]) -> np.ndarray:
    x = bucket_counts(row) + EPS_VOTES
    s = x / x.sum()
    z = np.log(s)
    return z - z.mean()


def centre_clr(x: np.ndarray) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    return a - a.mean(axis=-1, keepdims=True)


def inv_clr(z: np.ndarray) -> np.ndarray:
    z = np.asarray(z, dtype=float)
    z = z - np.max(z, axis=-1, keepdims=True)
    e = np.exp(z)
    return e / e.sum(axis=-1, keepdims=True)


def reproduce_bstar_v0(consts: list[dict[str, Any]], rows11: list[dict[str, Any]], rows16: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    m11 = match_rows(consts, rows11)
    m16 = match_rows(consts, rows16)
    cids = [c["constituency_id"] for c in consts]
    shift = {cid: centre_clr(clr(m16[cid]) - clr(m11[cid])) for cid in cids}
    residuals = np.stack([shift[cid] for cid in sorted(cids)])
    residuals = centre_clr(residuals - residuals.mean(axis=0, keepdims=True))
    rng = np.random.default_rng(SEED)
    draw_idx = rng.integers(0, len(cids), size=N_SAMPLES)
    # Consume the second draw exactly as the frozen Bstar implementation does, preserving RNG recipe auditability.
    _ = rng.integers(0, len(cids), size=N_SAMPLES)
    out = {}
    for cid in cids:
        pred_z = centre_clr(clr(m16[cid]))
        samples = inv_clr(pred_z + residuals[draw_idx])
        mean = samples.mean(axis=0)
        sd = samples.std(axis=0, ddof=1)
        q10 = np.quantile(samples, .10, axis=0)
        q90 = np.quantile(samples, .90, axis=0)
        out[cid] = {
            "mean": {p: float(mean[i]) for i,p in enumerate(PARTIES)},
            "sd": {p: float(sd[i]) for i,p in enumerate(PARTIES)},
            "q10": {p: float(q10[i]) for i,p in enumerate(PARTIES)},
            "q90": {p: float(q90[i]) for i,p in enumerate(PARTIES)},
        }
    return out


def random_id(prefix: str) -> str:
    return prefix + "_" + secrets.token_hex(8).upper()


def source_record_id(row: dict[str, Any]) -> str:
    safe_fingerprint = {
        "content_sha256": row.get("content_sha256"),
        "archive_timestamp": row.get("archive_timestamp"),
        "territory_id": row.get("territory_id"),
        "party_bucket": row.get("party_bucket"),
        "candidate_name_normalized": row.get("candidate_name_normalized"),
    }
    return "SRC_" + hashlib.sha256(canon_bytes(safe_fingerprint)).hexdigest()[:24]


def feature_row(fid: str, status="MISSING", value=None, source_class="NONE", ids=None, conflict=False):
    return {
        "feature_id": fid,
        "status": status,
        "value": value,
        "source_class": source_class,
        "source_record_ids": sorted(ids or []),
        "conflict": bool(conflict),
    }


def load_evidence(valid_cids: set[str]):
    gate = read_json(GATE)
    if gate.get("status") != "E_REASON_2021_COLLECTION_GATE_PASS" or not gate.get("counts", {}).get("gate_pass"):
        die("certified holdout evidence gate is not PASS")
    rows = read_json(ROSTER)
    if len(rows) != int(gate["counts"]["explicit_rank_candidate_facts"]):
        die("holdout enriched roster count does not match frozen gate")
    by = defaultdict(list)
    all_candidate_names = set()
    for r in rows:
        if r.get("year") != 2021:
            die("unexpected year in certified holdout roster")
        cid = r.get("territory_id")
        party = str(r.get("party_bucket") or "").upper()
        if cid not in valid_cids or party not in PARTIES:
            die("unresolved territory/party in certified holdout roster")
        if r.get("territory_resolution") != "EXACT_NORMALIZED":
            die("holdout roster contains non-exact territory resolution")
        if r.get("rank_evidence_status") != "EXPLICIT_CANDIDATS_TETES_DE_LISTE" or int(r.get("CANDIDATE_REGISTERED_RANK", -1)) != 1:
            die("holdout rank evidence is not explicit head-list rank=1")
        rr = dict(r)
        rr["_src_id"] = source_record_id(r)
        by[(cid, party)].append(rr)
        all_candidate_names.add(str(r.get("candidate_name_source") or ""))
        all_candidate_names.add(str(r.get("candidate_name_normalized") or ""))
    districts = {cid for cid,_ in by}
    if len(districts) != int(gate["counts"]["resolved_canonical_districts"]):
        die("holdout evidence district coverage diverges from frozen gate")
    return by, all_candidate_names


def build_features(cid: str, party: str, evidence, profiled_parties: set[str]):
    recs = evidence.get((cid, party), [])
    ids = [r["_src_id"] for r in recs]
    out = []
    for fid in FEATURES:
        if fid == "BALLOT_LIST_PRESENT":
            out.append(feature_row(fid, "VERIFIED", True, "M24", ids) if recs else feature_row(fid))
        elif fid == "CANDIDATE_REGISTERED_RANK":
            if recs:
                ranks = {int(r["CANDIDATE_REGISTERED_RANK"]) for r in recs}
                if len(ranks) != 1:
                    out.append(feature_row(fid, "AMBIGUOUS", None, "M24", ids, True))
                else:
                    out.append(feature_row(fid, "VERIFIED", min(ranks), "M24", ids))
            else:
                out.append(feature_row(fid))
        elif fid in {"INCUMBENT_SAME_PARTY_SAME_DISTRICT", "PARTY_SWITCH_IN"}:
            if recs:
                vals = [bool(r.get(fid, False)) for r in recs]
                # Multiple underlying candidates may live in the aggregate OTHER bucket. Any verified true fact is directional.
                out.append(feature_row(fid, "VERIFIED", any(vals), "M24", ids))
            else:
                out.append(feature_row(fid))
        elif fid == "PRINCIPAL_COMPETITOR_COUNT_WITH_VERIFIED_PROFILE":
            if profiled_parties:
                other = profiled_parties - {party}
                other_ids = [r["_src_id"] for q in other for r in evidence.get((cid,q), [])]
                out.append(feature_row(fid, "VERIFIED", len(other), "M24", other_ids))
            else:
                out.append(feature_row(fid))
        elif fid == "SOURCE_CONFLICT":
            out.append(feature_row(fid, "VERIFIED", False, "M24", ids) if recs else feature_row(fid))
        elif fid == "EVIDENCE_COUNT":
            out.append(feature_row(fid, "VERIFIED", len(recs), "M24", ids) if recs else feature_row(fid))
        elif fid == "SOURCE_CLASS_MAX":
            out.append(feature_row(fid, "VERIFIED", "M24", "M24", ids) if recs else feature_row(fid))
        else:
            out.append(feature_row(fid))
    return out


def leak_scan(bundle, consts, candidate_names, dev_bundle):
    text = json.dumps(bundle, ensure_ascii=False, sort_keys=True)
    violations = []
    forbidden = set(PARTIES)
    forbidden.update(c["constituency_id"] for c in consts)
    forbidden.update(c["name"] for c in consts)
    forbidden.update(c["region"] for c in consts)
    forbidden.update(candidate_names)
    forbidden.update({"2021", "2016", "Morocco", "Maroc", "medias24.com"})
    for s in forbidden:
        if s and json.dumps(s, ensure_ascii=False) in text:
            violations.append(s)
    if re.search(r"https?://|www\.", text, flags=re.I):
        violations.append("URL_PATTERN")
    if re.search(r"[\u0600-\u06ff]", text):
        violations.append("ARABIC_RAW_TEXT")
    old_ids = set()
    if dev_bundle:
        old_ids.add(dev_bundle.get("anonymous_election_id"))
        for pkt in dev_bundle.get("packets", []):
            old_ids.add(pkt.get("anonymous_territory_id")); old_ids.add(pkt.get("anonymous_region_id"))
            old_ids.update(p.get("anonymous_party_id") for p in pkt.get("parties", []))
    new_ids = {bundle["anonymous_election_id"]}
    for pkt in bundle["packets"]:
        new_ids.add(pkt["anonymous_territory_id"]); new_ids.add(pkt["anonymous_region_id"])
        new_ids.update(p["anonymous_party_id"] for p in pkt["parties"])
    old_ids.discard(None); new_ids.discard(None)
    if old_ids & new_ids:
        violations.append("ANONYMIZATION_NOT_INDEPENDENT_FROM_DEVELOPMENT")
    return {"status":"PASS" if not violations else "FAIL", "violations": sorted(set(violations)), "scan_version":"1.0"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--secret-mapping-output", required=True)
    args = ap.parse_args()
    secret_path = Path(args.secret_mapping_output).resolve()

    if BUNDLE.exists() or SEAL.exists():
        die("holdout bundle/seal already exists; refusing regeneration")
    freeze = read_json(LAMBDA_FREEZE)
    if freeze.get("status") != "FROZEN_BEFORE_2021_JUDGMENTS" or freeze.get("holdout_2021_outcome_seen_before_freeze") is not False:
        die("lambda freeze is not valid before holdout")
    if float(freeze["lambda_C1"]) != 0.3 or float(freeze["lambda_C2"]) != 0.3:
        die("unexpected frozen lambda values")
    closure = read_json(CLOSURE)
    if closure.get("status") != "PASS":
        die("historical evidence closure is not PASS")
    info = read_json(INFO)
    if tuple(x["id"] for x in info["allowed_candidate_and_event_features"]) != FEATURES:
        die("feature order diverges from frozen information set")
    if not PROMPT.exists():
        die("frozen C2 prompt missing")

    consts = load_constituencies()
    evidence, candidate_names = load_evidence({c["constituency_id"] for c in consts})
    baseline = reproduce_bstar_v0(consts, load_local(2011), load_local(2016))

    mapping = {
        "schema_version":"1.0",
        "experiment_id":"M26-GOAL100-E-REASON-V1",
        "real_election":2021,
        "anonymous_election_id":random_id("E"),
        "territories":{c["constituency_id"]:random_id("T") for c in consts},
        "regions":{r:random_id("R") for r in sorted({c["region"] for c in consts})},
        "parties":{p:random_id("P") for p in PARTIES},
        "created_for":"LOCKED_COMPONENT_HOLDOUT",
        "rule":"SECRET_MAPPING_DO_NOT_EXPOSE_TO_C1_C2_BEFORE_HOLDOUT_JUDGMENT_HASHES_FREEZE",
    }
    mapping_sha = sha_obj(mapping)
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    secret_path.write_bytes(canon_bytes(mapping))

    packets = []
    for c in sorted(consts, key=lambda x:mapping["territories"][x["constituency_id"]]):
        cid = c["constituency_id"]
        profiled = {p for p in PARTIES if evidence.get((cid,p))}
        mean = baseline[cid]["mean"]
        ranked = sorted(PARTIES, key=lambda p:(-mean[p], p))
        ranks = {p:i+1 for i,p in enumerate(ranked)}
        parties = []
        for p in PARTIES:
            feats = build_features(cid,p,evidence,profiled)
            observed = sum(f["status"] not in {"MISSING","NOT_FOUND","UNVERIFIED","DATA_BLOCKED"} for f in feats)
            parties.append({
                "anonymous_party_id":mapping["parties"][p],
                "baseline_vote_share":round(mean[p],12),
                "baseline_rank":ranks[p],
                "baseline_uncertainty_summary":{
                    "status":"AVAILABLE_FROZEN_BSTAR_V0",
                    "sd":round(baseline[cid]["sd"][p],12),
                    "q10":round(baseline[cid]["q10"][p],12),
                    "q90":round(baseline[cid]["q90"][p],12),
                    "monte_carlo_samples":N_SAMPLES,
                },
                "evidence_completeness":{
                    "observed_feature_count":observed,
                    "allowed_feature_count":len(FEATURES),
                    "missingness_explicit":True,
                },
                "features":feats,
            })
        parties.sort(key=lambda x:x["anonymous_party_id"])
        core = {
            "schema_version":"1.0",
            "experiment_id":"M26-GOAL100-E-REASON-V1",
            "condition_eligible":["C1_RULE_ONLY","C2_LLM_RESIDUAL"],
            "anonymous_election_id":mapping["anonymous_election_id"],
            "anonymous_territory_id":mapping["territories"][cid],
            "anonymous_region_id":mapping["regions"][c["region"]],
            "seat_magnitude":c["seats"],
            "parties":parties,
        }
        packet = dict(core); packet["packet_sha256"] = sha_obj(core); packets.append(packet)

    if len(packets)!=92 or sum(len(p["parties"]) for p in packets)!=828:
        die("holdout cardinality failure")
    core_bundle = {
        "schema_version":"1.0",
        "experiment_id":"M26-GOAL100-E-REASON-V1",
        "bundle_role":"BLINDED_COMPONENT_HOLDOUT_C1_C2_INPUT",
        "anonymous_election_id":mapping["anonymous_election_id"],
        "packet_count":92,
        "party_cells":828,
        "missingness_policy":"EXPLICIT_MISSING_NEVER_DROP_CELL",
        "baseline_policy":"FROZEN_BSTAR_V0_PERSIST_MONTE_CARLO_MEAN_FROM_2011_TO_2016_TRAINING_ONLY",
        "uncertainty_policy":"FROZEN_BSTAR_V0_MONTE_CARLO_SD_Q10_Q90",
        "packets":packets,
    }
    bundle_sha = sha_obj(core_bundle)
    bundle = dict(core_bundle); bundle["bundle_sha256"] = bundle_sha
    dev = read_json(DEV_BUNDLE) if DEV_BUNDLE.exists() else None
    scan = leak_scan(bundle,consts,candidate_names,dev)
    if scan["status"] != "PASS":
        die("holdout leakage scan failed: "+json.dumps(scan,ensure_ascii=False))

    OUTDIR.mkdir(parents=True,exist_ok=True)
    BUNDLE.write_text(json.dumps(bundle,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    manifest = {
        "schema_version":"1.0",
        "status":"FROZEN_BLIND_HOLDOUT_BUNDLE",
        "experiment_id":"M26-GOAL100-E-REASON-V1",
        "bundle_path":"morocco26/data/goal100/e_reason/blind/holdout/blind_bundle.json",
        "bundle_sha256":bundle_sha,
        "packets":92,
        "party_cells":828,
        "packet_sha256":[p["packet_sha256"] for p in packets],
        "leakage_scan":scan,
        "mapping_committed":False,
        "mapping_sha256":mapping_sha,
        "judge_must_not_receive_mapping":True,
        "anonymization_independent_from_development":True,
        "baseline_input":{
            "role":"frozen structural Bstar C0 holdout forecast",
            "model":"V0_PERSIST",
            "fit_transition":"2011_to_2016_only",
            "point":"Monte Carlo predictive mean",
            "uncertainty":"Monte Carlo sd/q10/q90",
            "target_outcome_read":False,
        },
        "feature_input":{
            "gate_sha256":sha_file(GATE),
            "enriched_roster_sha256":sha_file(ROSTER),
            "resolved_districts":82,
            "explicit_rank_candidate_facts":508,
            "missing_unobserved_features":True,
        },
        "lambda_freeze_sha256":sha_file(LAMBDA_FREEZE),
        "lambda_C1":freeze["lambda_C1"],
        "lambda_C2":freeze["lambda_C2"],
        "c2_prompt_sha256":sha_file(PROMPT),
        "target_outcome_read":False,
        "next_allowed_action":"FREEZE_C1_HOLDOUT_AND_RUN_C2_OPUS5_WITHOUT_OUTCOME_ACCESS",
    }
    MANIFEST.write_text(json.dumps(manifest,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    seal = {
        "schema_version":"1.0",
        "seal_id":"M26-E-REASON-HOLDOUT-MAPPING-SEAL-V1",
        "experiment_id":"M26-GOAL100-E-REASON-V1",
        "status":"SEALED_BEFORE_ANY_HOLDOUT_PREDICTIVE_JUDGMENT",
        "anonymous_election_id":mapping["anonymous_election_id"],
        "blind_bundle_sha256":bundle_sha,
        "blind_packet_count":92,
        "blind_party_cells":828,
        "mapping_sha256":mapping_sha,
        "mapping_material_committed":False,
        "mapping_material_judge_access":False,
        "c2_prompt_sha256":sha_file(PROMPT),
        "lambda_freeze_sha256":sha_file(LAMBDA_FREEZE),
        "leakage_scan":scan,
        "unseal_rule":"MAPPING_AND_TARGET_OUTCOME_MAY_NOT_BE_EXPOSED_TO_C2_BEFORE_HOLDOUT_JUDGMENT_HASHES_ARE_FROZEN",
    }
    SEAL.write_text(json.dumps(seal,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":manifest["status"],"bundle_sha256":bundle_sha,"mapping_sha256":mapping_sha,"packets":92,"cells":828,"leakage":"PASS"},sort_keys=True))


if __name__ == "__main__":
    main()
