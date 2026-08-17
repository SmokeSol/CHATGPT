#!/usr/bin/env python3
"""Bootstrap B2, the non-agentic structured-evidence layer, after frozen F-1.

The script is deliberately fail-closed:
- it verifies that an immutable 50k-draw F-1 is present and registered;
- it never fabricates 2026 candidate or event evidence;
- it creates schemas, ledgers, source policy, validation and freeze machinery;
- it may prepare B2 in BLOCKED state when F-1 proof is incomplete;
- it keeps every agentic gate locked.

B2 is an observation and deterministic feature layer. Forecast coefficients may
only be estimated on pre-2026 history under a separately frozen protocol; absent
historical identification implies a coefficient of zero, not expert judgement.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
B2 = G100 / "b2" / "v1"
SCRIPTS = ROOT / "scripts"
WORKFLOWS = ROOT.parent / ".github" / "workflows"
BRANCH = "morocco26-b2-structured-evidence"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load(path: Path, default: Any = None) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def repo_path(value: str) -> Path:
    candidate = ROOT.parent / value
    return candidate


def snapshot_ids(registry: dict[str, Any]) -> list[str]:
    values = registry.get("snapshots", []) if isinstance(registry, dict) else []
    result: list[str] = []
    for row in values:
        if isinstance(row, dict) and row.get("snapshot_id"):
            result.append(str(row["snapshot_id"]))
        elif isinstance(row, str):
            result.append(row)
    return result


def locate_manifest() -> Path | None:
    candidates = [
        G100 / "snapshots" / "F-1" / "manifest.json",
        G100 / "snapshots" / "F-1" / "snapshot_manifest.json",
        G100 / "forecasts" / "F-1" / "manifest.json",
        G100 / "forecasts" / "F-1" / "snapshot_manifest.json",
    ]
    return next((path for path in candidates if path.exists()), None)


def locate_forecast(manifest_path: Path, manifest: dict[str, Any]) -> Path | None:
    artifact_paths = manifest.get("artifact_paths", {}) if isinstance(manifest, dict) else {}
    declared = artifact_paths.get("forecast") if isinstance(artifact_paths, dict) else None
    candidates = []
    if declared:
        candidates.append(repo_path(str(declared)))
    candidates.extend(
        [
            manifest_path.parent / "forecast.json",
            G100 / "snapshots" / "F-1" / "forecast.json",
            G100 / "forecasts" / "F-1" / "forecast.json",
        ]
    )
    return next((path for path in candidates if path.exists()), None)


def verify_fminus1() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    registry_path = G100 / "forecast_registry.json"
    registry = load(registry_path, {})
    ids = snapshot_ids(registry)
    registered = ids.count("F-1") == 1
    checks.append({"id": "REGISTRY_SINGLE_F_MINUS_1", "pass": registered, "observed": ids})

    manifest_path = locate_manifest()
    checks.append({"id": "IMMUTABLE_MANIFEST_PRESENT", "pass": manifest_path is not None,
                   "observed": str(manifest_path.relative_to(ROOT.parent)) if manifest_path else None})
    manifest = load(manifest_path, {}) if manifest_path else {}
    draws = int(manifest.get("monte_carlo_draws", 0) or 0)
    checks.append({"id": "MONTE_CARLO_AT_LEAST_50000", "pass": draws >= 50_000, "observed": draws})

    forecast_path = locate_forecast(manifest_path, manifest) if manifest_path else None
    checks.append({"id": "FORECAST_ARTIFACT_PRESENT", "pass": forecast_path is not None,
                   "observed": str(forecast_path.relative_to(ROOT.parent)) if forecast_path else None})
    declared_hash = manifest.get("forecast_artifact_hash") or manifest.get("forecast_sha256")
    observed_hash = sha256(forecast_path) if forecast_path else None
    hash_ok = bool(declared_hash and observed_hash and str(declared_hash) == observed_hash)
    checks.append({"id": "FORECAST_HASH_MATCH", "pass": hash_ok,
                   "declared": declared_hash, "observed": observed_hash})

    simulation_candidates = [
        G100 / "simulation_certificate.json",
        manifest_path.parent / "simulation_certificate.json" if manifest_path else Path("/__missing__"),
    ]
    simulation_path = next((path for path in simulation_candidates if path.exists()), None)
    simulation = load(simulation_path, {}) if simulation_path else {}
    sim_pass = simulation.get("gate") in {"PASS", "PASS_MAIN_VERIFIED"}
    seats = simulation.get("national_seats_every_draw") or simulation.get("seat_total_every_draw")
    checks.append({"id": "SIMULATION_CERTIFICATE_PASS", "pass": sim_pass,
                   "observed": simulation.get("gate")})
    checks.append({"id": "ALL_DRAWS_SUM_395", "pass": int(seats or 0) == 395,
                   "observed": seats})

    registration_candidates = [
        G100 / "fminus1_registration_certificate.json",
        G100 / "fminus1_main_verification.json",
    ]
    registration_path = next((path for path in registration_candidates if path.exists()), None)
    registration = load(registration_path, {}) if registration_path else {}
    registration_gate = registration.get("gate") or registration.get("status")
    registration_ok = registration_gate in {
        "PASS", "PASS_REGISTERED", "PASS_MAIN_VERIFIED", "REGISTERED_IMMUTABLE"
    }
    # Registry + manifests are sufficient evidence on a pre-merge execution branch;
    # a main-verification certificate remains preferable and is reported separately.
    branch_frozen = registered and manifest_path is not None and draws >= 50_000 and hash_ok and sim_pass and int(seats or 0) == 395
    checks.append({"id": "REGISTRATION_CERTIFICATE", "pass": registration_ok,
                   "observed": registration_gate,
                   "advisory_when_branch_frozen": True})

    main_verification = load(G100 / "fminus1_main_verification.json", {})
    main_ok = main_verification.get("gate") == "PASS_MAIN_VERIFIED"
    checks.append({"id": "MAIN_VERIFICATION", "pass": main_ok,
                   "observed": main_verification.get("gate"), "required_for_merge_not_for_B2_SCAFFOLD": True})

    ready = branch_frozen
    return {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-B2-PREFLIGHT-V1",
        "checked_at": NOW,
        "ready_for_b2_non_agentic_scaffold": ready,
        "ready_for_b2_evidence_freeze": ready,
        "ready_for_main_merge": main_ok,
        "fminus1_registry_path": str(registry_path.relative_to(ROOT.parent)),
        "manifest_path": str(manifest_path.relative_to(ROOT.parent)) if manifest_path else None,
        "forecast_path": str(forecast_path.relative_to(ROOT.parent)) if forecast_path else None,
        "simulation_certificate_path": str(simulation_path.relative_to(ROOT.parent)) if simulation_path else None,
        "registration_certificate_path": str(registration_path.relative_to(ROOT.parent)) if registration_path else None,
        "checks": checks,
        "rule": "B2 may be scaffolded only from an immutable registered F-1 on the source branch; F0 and all agentic experiments remain locked until their own gates close."
    }


def protocol(preflight: dict[str, Any]) -> dict[str, Any]:
    status = "OPEN_FOR_STRUCTURED_COLLECTION" if preflight["ready_for_b2_non_agentic_scaffold"] else "BLOCKED_BY_F_MINUS_1"
    return {
        "schema_version": "1.0",
        "protocol_id": "M26-GOAL100-B2-PROTOCOL-V1",
        "frozen_at": NOW,
        "status": status,
        "north_star": "Measure whether structured, timestamped, non-agentic 2026 political evidence adds predictive information beyond immutable structural forecast F-1.",
        "baseline": {
            "snapshot_id": "F-1",
            "immutable": True,
            "manifest_path": preflight.get("manifest_path"),
            "forecast_path": preflight.get("forecast_path"),
            "rule": "B2 never rewrites, refits or conditions F-1. F0 is a new snapshot."
        },
        "non_agentic_contract": {
            "llm_extraction_allowed": False,
            "agentic_search_allowed": False,
            "agentic_reasoning_allowed": False,
            "manual_directional_adjustments_allowed": False,
            "expert_override_allowed": False,
            "narrative_quality_scientific_credit": 0,
            "permitted_ingestion": [
                "human-entered structured rows with primary-source citation",
                "deterministic parser with reproducible code and source hash",
                "official bulk data import"
            ]
        },
        "units": {
            "observation": "one atomic source-backed claim",
            "feature": "territory x legal-list x cutoff deterministic aggregation",
            "forecast_adjustment": "pre-2026 calibrated residual model only"
        },
        "evidence_families": [
            "LIST_AVAILABILITY",
            "CANDIDATE_IDENTITY_AND_RANK",
            "INCUMBENCY",
            "PARTY_SWITCH_OR_DEFECTION",
            "ENDORSEMENT_OR_ALLIANCE",
            "TERRITORIAL_OFFICEHOLDER_NETWORK",
            "VERIFIED_CAMPAIGN_OR_ORGANIZATIONAL_EVENT",
            "LEGAL_OR_GEOMETRY_CHANGE"
        ],
        "forbidden_inferences": [
            "absence of evidence treated as evidence of absence",
            "press tone converted directly into vote swing",
            "social engagement converted directly into vote share",
            "candidate prestige score chosen after seeing 2026 implications",
            "event severity assigned by free-form model judgement",
            "new party/list invented because a structural bucket exists"
        ],
        "missingness": {
            "default": "UNKNOWN",
            "zero_only_when": "an authoritative closed universe proves absence",
            "coverage_certificate_required": True,
            "no_hidden_imputation": True
        },
        "temporal_contract": {
            "observed_at_required": True,
            "effective_at_required": True,
            "source_published_at_required": True,
            "cutoff_specific_snapshots": True,
            "late_discovered_pre_cutoff_fact": "new evidence snapshot; no historical overwrite",
            "post_cutoff_fact": "excluded from that snapshot"
        },
        "forecast_bridge": {
            "F0_definition": "F-1 plus a frozen B2 feature snapshot evaluated through a pre-2026 calibrated residual model",
            "list_not_filed_effect": "legal zero only after authoritative filing closure",
            "candidate_or_event_coefficients": "fit only on pre-2026 history with nested temporal validation; otherwise fixed at zero",
            "unseen_event_taxonomy": "recorded for audit but forecast weight zero",
            "party_balance": "all composition adjustments are zero-sum in an explicit log-ratio space",
            "turnout": "separate model; no automatic vote-to-turnout coupling"
        },
        "calibration_contract": {
            "training_data": "pre-2026 elections only",
            "model_family": "ridge-regularized residual model with frozen feature dictionary",
            "selection": "nested leave-one-election-out or temporal backtest",
            "comparison": "F-1/B* versus B2 using the same cutoff and proper scores",
            "minimum_improvement": "must be preregistered before fitting",
            "failure_policy": "B2 coefficient vector remains zero and F0 equals F-1 apart from legally certain list availability"
        },
        "gates": {
            "B2_SCHEMA_VALID": "all rows validate and every claim has provenance",
            "B2_COVERAGE_CERTIFIED": "coverage matrix published; unknowns remain explicit",
            "B2_RESIDUAL_BACKTEST": "pre-2026 calibration and incremental proper-score comparison published",
            "B2_FROZEN": "data, features, parameters, cutoff and hashes frozen append-only",
            "F0_ELIGIBLE": "B2_FROZEN plus all legal/list availability gates required by the selected cutoff"
        },
        "agentic_boundary": {
            "status": "LOCKED",
            "unlock_after": ["F-1 immutable", "B2 frozen", "F0 or same-cutoff B2 forecast frozen", "agentic experiments separately preregistered"],
            "future_arms": ["E_collect", "E_reason", "E_full"]
        }
    }


def source_policy() -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "policy_id": "M26-GOAL100-B2-SOURCE-POLICY-V1",
        "frozen_at": NOW,
        "tiers": {
            "A_OFFICIAL": {
                "examples": ["Ministry or election authority", "Official Gazette/SGG", "Parliament", "official party filing or communiqué"],
                "may_establish": ["legal change", "filed list", "candidate identity/rank", "official endorsement", "office held"]
            },
            "B_PRIMARY": {
                "examples": ["verified candidate or party account", "candidate declaration", "official local officeholder page"],
                "may_establish": ["declared candidacy", "declared party switch", "declared endorsement"],
                "corroboration": "Tier A required when a legal filing consequence is claimed"
            },
            "C_REPUTABLE_REPORTING": {
                "examples": ["named-journalist reporting with attributable sources"],
                "may_establish": ["event occurrence pending primary confirmation"],
                "corroboration": "two independent reports or one embedded primary document"
            },
            "D_UNVERIFIED": {
                "examples": ["anonymous social post", "aggregation without provenance", "commentary or prediction"],
                "forecast_eligible": False
            }
        },
        "precedence": ["A_OFFICIAL", "B_PRIMARY", "C_REPUTABLE_REPORTING", "D_UNVERIFIED"],
        "conflict_rule": "retain all claims, mark conflict, and use the highest-tier latest effective authoritative claim; never delete the superseded row",
        "archiving": {
            "source_url_required": True,
            "retrieved_at_required": True,
            "content_sha256_required": True,
            "quote_optional_max_words": 25,
            "raw_copy_policy": "store only when legally permitted; otherwise store hash and metadata"
        },
        "domain_seed_registry": [
            {"source_id": "MA_INTERIOR", "tier": "A_OFFICIAL", "domain": "interieur.gov.ma", "status": "DISCOVERY_REQUIRED"},
            {"source_id": "MA_SGG", "tier": "A_OFFICIAL", "domain": "sgg.gov.ma", "status": "ACTIVE"},
            {"source_id": "MA_PARLIAMENT", "tier": "A_OFFICIAL", "domain": "chambredesrepresentants.ma", "status": "ACTIVE_WITH_WAF_LIMITATION"},
            {"source_id": "PARTY_OFFICIAL_SITES", "tier": "A_OFFICIAL", "domain": "PER_PARTY_REGISTRY", "status": "TO_POPULATE_DETERMINISTICALLY"}
        ]
    }


def evidence_schema() -> dict[str, Any]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "M26-GOAL100-B2-EVIDENCE-SCHEMA-V1",
        "title": "Atomic B2 evidence row",
        "type": "object",
        "additionalProperties": False,
        "required": [
            "evidence_id", "claim_type", "territory_scope", "party_or_list_id",
            "subject_id", "value", "source_id", "source_tier", "source_url",
            "source_published_at", "retrieved_at", "effective_at", "content_sha256",
            "extractor_mode", "confidence", "status"
        ],
        "properties": {
            "evidence_id": {"type": "string", "pattern": "^B2E-[A-Z0-9-]{8,80}$"},
            "claim_type": {"enum": [
                "LIST_FILED", "LIST_NOT_FILED", "CANDIDATE_IDENTITY", "CANDIDATE_RANK",
                "INCUMBENT_RUNNING", "INCUMBENT_NOT_RUNNING", "PARTY_SWITCH_IN",
                "PARTY_SWITCH_OUT", "ENDORSEMENT", "ALLIANCE", "OFFICE_HELD",
                "NETWORK_LINK", "CAMPAIGN_EVENT", "ORGANIZATIONAL_EVENT",
                "LEGAL_CHANGE", "GEOMETRY_CHANGE"
            ]},
            "territory_scope": {"type": "string", "minLength": 1},
            "party_or_list_id": {"type": ["string", "null"]},
            "subject_id": {"type": ["string", "null"]},
            "value": {"type": ["string", "number", "integer", "boolean", "null"]},
            "source_id": {"type": "string", "minLength": 1},
            "source_tier": {"enum": ["A_OFFICIAL", "B_PRIMARY", "C_REPUTABLE_REPORTING", "D_UNVERIFIED"]},
            "source_url": {"type": "string", "pattern": "^https://"},
            "source_published_at": {"type": "string", "format": "date-time"},
            "retrieved_at": {"type": "string", "format": "date-time"},
            "effective_at": {"type": "string", "format": "date-time"},
            "content_sha256": {"type": "string", "pattern": "^[0-9a-f]{64}$"},
            "extractor_mode": {"enum": ["HUMAN_STRUCTURED", "DETERMINISTIC_PARSER", "OFFICIAL_BULK_IMPORT"]},
            "extractor_version": {"type": ["string", "null"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "status": {"enum": ["ACTIVE", "SUPERSEDED", "CONFLICT", "REJECTED", "PENDING_CORROBORATION"]},
            "supersedes_evidence_id": {"type": ["string", "null"]},
            "notes": {"type": ["string", "null"], "maxLength": 1000}
        }
    }


def feature_dictionary() -> dict[str, Any]:
    features = [
        ("LIST_FILED_OFFICIAL", "binary", "official closed-universe filing status", "legal_constraint"),
        ("HEAD_CANDIDATE_INCUMBENT", "binary", "incumbent MP is head candidate", "calibrated_or_zero"),
        ("INCUMBENT_COUNT_ON_LIST", "count", "verified incumbents on list", "calibrated_or_zero"),
        ("DEFECTION_IN_COUNT", "count", "verified incumbent/local notable switches into list", "calibrated_or_zero"),
        ("DEFECTION_OUT_COUNT", "count", "verified switches out of list", "calibrated_or_zero"),
        ("MUNICIPAL_OFFICEHOLDER_SUPPORT", "seat_weighted_count", "verified local officeholders endorsing list", "calibrated_or_zero"),
        ("FORMAL_ALLIANCE_SUPPORT", "binary", "official alliance/endorsement", "calibrated_or_zero"),
        ("CAMPAIGN_DISRUPTION_EVENT", "taxonomy_count", "predefined verified disruption events", "calibrated_or_zero"),
        ("LEGAL_ELIGIBILITY_BLOCK", "binary", "official exclusion/ineligibility", "legal_constraint"),
        ("EVIDENCE_COVERAGE", "ratio", "observed/required fields for territory-list", "diagnostic_only"),
    ]
    return {
        "schema_version": "1.0",
        "dictionary_id": "M26-GOAL100-B2-FEATURE-DICTIONARY-V1",
        "frozen_at": NOW,
        "features": [
            {"feature_id": name, "unit": unit, "definition": definition, "forecast_role": role,
             "missing_value": "UNKNOWN", "direction_not_hardcoded": role == "calibrated_or_zero"}
            for name, unit, definition, role in features
        ],
        "aggregation": {
            "key": ["cutoff", "territory_id", "party_or_list_id"],
            "deterministic": True,
            "conflicts": "highest-tier latest-effective active claim; conflict flag retained",
            "unknown_not_zero": True
        },
        "coefficient_rule": "No 2026 row may determine a coefficient. A feature lacking pre-2026 identification has coefficient exactly zero."
    }


def write_csv(path: Path, header: list[str]) -> None:
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(header)


def validator_source() -> str:
    return r'''#!/usr/bin/env python3
"""Fail-closed validator for the non-agentic B2 structured-evidence layer."""
from __future__ import annotations
import hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100'
B=G/'b2'/'v1'

def load(path): return json.loads(path.read_text(encoding='utf-8'))
def req(c,m):
    if not c: raise SystemExit('B2_VALIDATION_FAIL: '+m)
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

protocol=load(B/'b2_protocol_v1.json')
preflight=load(B/'b2_preflight.json')
schema=load(B/'b2_evidence_schema_v1.json')
policy=load(B/'b2_source_policy_v1.json')
features=load(B/'b2_feature_dictionary_v1.json')
req(protocol['protocol_id']=='M26-GOAL100-B2-PROTOCOL-V1','protocol ID drift')
req(protocol['non_agentic_contract']['llm_extraction_allowed'] is False,'LLM extraction unlocked')
req(protocol['non_agentic_contract']['agentic_search_allowed'] is False,'agentic search unlocked')
req(protocol['non_agentic_contract']['manual_directional_adjustments_allowed'] is False,'manual swing allowed')
req(protocol['agentic_boundary']['status']=='LOCKED','agentic boundary unlocked')
req(features['coefficient_rule'].endswith('exactly zero.'),'coefficient zero fallback drift')
req(set(policy['tiers'])=={'A_OFFICIAL','B_PRIMARY','C_REPUTABLE_REPORTING','D_UNVERIFIED'},'source tiers drift')

required=set(schema['required'])
allowed=set(schema['properties'])
ids=set(); active=0; rejected=0
ledger=B/'evidence_ledger.ndjson'
req(ledger.exists(),'evidence ledger missing')
for number,line in enumerate(ledger.read_text(encoding='utf-8').splitlines(),1):
    if not line.strip(): continue
    row=json.loads(line)
    req(set(row)<=allowed,f'line {number}: extra fields {sorted(set(row)-allowed)}')
    req(required<=set(row),f'line {number}: missing {sorted(required-set(row))}')
    eid=row['evidence_id']; req(eid not in ids,f'duplicate evidence_id {eid}'); ids.add(eid)
    req(re.fullmatch(r'B2E-[A-Z0-9-]{8,80}',eid) is not None,f'bad evidence_id {eid}')
    req(row['extractor_mode'] in {'HUMAN_STRUCTURED','DETERMINISTIC_PARSER','OFFICIAL_BULK_IMPORT'},f'forbidden extractor {eid}')
    req(row['source_tier'] in policy['tiers'],f'unknown source tier {eid}')
    req(str(row['source_url']).startswith('https://'),f'non-HTTPS source {eid}')
    req(re.fullmatch(r'[0-9a-f]{64}',row['content_sha256']) is not None,f'bad source hash {eid}')
    req(0<=float(row['confidence'])<=1,f'bad confidence {eid}')
    if row['source_tier']=='D_UNVERIFIED': req(row['status'] in {'REJECTED','PENDING_CORROBORATION'},f'unverified row forecast-active {eid}')
    active += row['status']=='ACTIVE'; rejected += row['status']=='REJECTED'

freeze=B/'b2_freeze_certificate.json'
if freeze.exists():
    cert=load(freeze); req(cert['gate']=='PASS','freeze certificate not PASS')
    for item in cert['artifacts']:
        path=ROOT.parent/item['path']; req(path.exists(),f'frozen artifact missing {item["path"]}')
        req(sha(path)==item['sha256'],f'frozen hash mismatch {item["path"]}')

print('B2_VALIDATION_PASS')
print(f"preflight_ready={preflight['ready_for_b2_non_agentic_scaffold']}")
print(f'evidence_rows={len(ids)} active={active} rejected={rejected}')
print('agentic=LOCKED manual_swing=FORBIDDEN unknown_is_not_zero=TRUE')
'''


def freeze_source() -> str:
    return r'''#!/usr/bin/env python3
"""Freeze an append-only B2 evidence/feature snapshot after validation."""
from __future__ import annotations
import hashlib, json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
G=ROOT/'data'/'goal100'; B=G/'b2'/'v1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def req(c,m):
    if not c: raise SystemExit('B2_FREEZE_FAIL: '+m)
subprocess.run(['python',str(ROOT/'scripts'/'goal100_validate_b2_v1.py')],check=True)
cutoff=os.environ.get('B2_CUTOFF','').strip()
req(cutoff,'B2_CUTOFF ISO timestamp is required')
try: datetime.fromisoformat(cutoff.replace('Z','+00:00'))
except ValueError as exc: raise SystemExit('B2_FREEZE_FAIL: invalid B2_CUTOFF') from exc
pre=json.loads((B/'b2_preflight.json').read_text(encoding='utf-8'))
req(pre['ready_for_b2_evidence_freeze'] is True,'F-1 prerequisite not certified')
paths=[
 B/'b2_protocol_v1.json', B/'b2_source_policy_v1.json', B/'b2_evidence_schema_v1.json',
 B/'b2_feature_dictionary_v1.json', B/'source_registry.json', B/'entity_registry.json',
 B/'evidence_ledger.ndjson', B/'candidate_registry.csv', B/'list_availability.csv',
 B/'territorial_networks.csv', B/'events.csv', B/'coverage_matrix.csv'
]
req(all(path.exists() for path in paths),'one or more B2 artifacts missing')
ledger_rows=sum(bool(x.strip()) for x in (B/'evidence_ledger.ndjson').read_text(encoding='utf-8').splitlines())
cert={
 'schema_version':'1.0','certificate_id':'M26-GOAL100-B2-FREEZE-V1',
 'frozen_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
 'cutoff':cutoff,'gate':'PASS','evidence_rows':ledger_rows,
 'epistemic_status':'STRUCTURED_NON_AGENTIC_EVIDENCE_SNAPSHOT',
 'artifacts':[{'path':str(path.relative_to(ROOT.parent)),'sha256':sha(path)} for path in paths],
 'agentic_status':'LOCKED','forecast_status':'NO_F0_CREATED_BY_THIS_FREEZE',
 'rule':'A later correction or source creates a new B2 snapshot; this certificate is never overwritten.'
}
out=B/'b2_freeze_certificate.json'
req(not out.exists(),'freeze certificate already exists; create a new version/snapshot')
out.write_text(json.dumps(cert,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(cert,ensure_ascii=False,indent=2))
'''


def workflow_source() -> str:
    return '''name: morocco26-b2-structured-evidence\n\non:\n  push:\n    branches: [morocco26-b2-structured-evidence]\n    paths:\n      - 'morocco26/data/goal100/b2/v1/**'\n      - 'morocco26/scripts/goal100_validate_b2_v1.py'\n      - 'morocco26/scripts/goal100_freeze_b2_v1.py'\n      - 'morocco26/FIL_D_ARIANE.md'\n      - 'morocco26/FIL_ARIANE.md'\n      - '.github/workflows/morocco26-b2-structured-evidence.yml'\n  workflow_dispatch:\n\npermissions:\n  contents: read\n\njobs:\n  validate:\n    runs-on: ubuntu-latest\n    timeout-minutes: 10\n    steps:\n      - uses: actions/checkout@v4\n        with:\n          ref: morocco26-b2-structured-evidence\n      - uses: actions/setup-python@v5\n        with:\n          python-version: '3.12'\n      - name: Preserve Goal75\n        run: python morocco26/scripts/validate_anti_drift.py\n      - name: Validate B2 contract and evidence ledger\n        run: python morocco26/scripts/goal100_validate_b2_v1.py\n'''


def append_journal(preflight: dict[str, Any]) -> str:
    candidates = [ROOT / "FIL_D_ARIANE.md", ROOT / "FIL_ARIANE.md"]
    path = next((candidate for candidate in candidates if candidate.exists()), candidates[0])
    if not path.exists():
        path.write_text("# MOROCCO//26 — FIL D’ARIANE\n", encoding="utf-8")
    marker = "B2-A001 — Ouverture de la couche structurée non agentique"
    text = path.read_text(encoding="utf-8")
    if marker not in text:
        state = "OUVERTE" if preflight["ready_for_b2_non_agentic_scaffold"] else "PRÉPARÉE MAIS BLOQUÉE"
        text += f'''\n\n### {NOW} — {marker}\n\n- **État :** {state}.\n- **Baseline intangible :** `F-1`; aucun artefact F-1 n’est modifié.\n- **Objet :** candidats, listes, changements de parti, endorsements, réseaux territoriaux et événements vérifiés sous forme atomique, horodatée et sourcée.\n- **Interdits :** extraction LLM, recherche agentique, swing manuel, absence→zéro, coefficient choisi sur implications 2026.\n- **Règle de poids :** calibration pré-2026 ou coefficient nul.\n- **Agentique :** reste `LOCKED`.\n- **Preflight F-1 :** `{preflight['ready_for_b2_non_agentic_scaffold']}`; vérification main : `{preflight['ready_for_main_merge']}`.\n- **Prochaine action exacte :** peupler le registre de sources officielles, puis produire les premiers événements atomiques et la matrice de couverture sans générer F0.\n'''
        path.write_text(text, encoding="utf-8")
    return str(path.relative_to(ROOT.parent))


def update_tracking(preflight: dict[str, Any]) -> None:
    gates_path = G100 / "gate_registry.json"
    gates = load(gates_path, {})
    if isinstance(gates, dict):
        agentic = gates.setdefault("agentic_unlock", [])
        b2_gate = next((row for row in agentic if row.get("id") == "B2-FROZEN"), None)
        if b2_gate is None:
            b2_gate = {"id": "B2-FROZEN"}
            agentic.insert(0, b2_gate)
        b2_gate.update({
            "status": "OPEN" if preflight["ready_for_b2_non_agentic_scaffold"] else "LOCKED",
            "reason": "B2 protocol and evidence collection opened after immutable F-1; closure requires a freeze certificate." if preflight["ready_for_b2_non_agentic_scaffold"] else "F-1 immutability/registration proof incomplete.",
            "required_artifact": "morocco26/data/goal100/b2/v1/b2_freeze_certificate.json"
        })
        for row in agentic:
            if row.get("id") != "B2-FROZEN":
                row["status"] = "LOCKED"
        gates["as_of"] = NOW
        dump(gates_path, gates)

    state_path = G100 / "current_state.json"
    state = load(state_path, {})
    if isinstance(state, dict):
        state["as_of"] = NOW
        if preflight["ready_for_b2_non_agentic_scaffold"]:
            state["program_phase"] = "P7_B2_STRUCTURED_NON_AGENTIC_EVIDENCE"
        state["B2"] = {
            "status": "OPEN_COLLECTION_NOT_FROZEN" if preflight["ready_for_b2_non_agentic_scaffold"] else "BLOCKED_BY_F_MINUS_1",
            "protocol": "morocco26/data/goal100/b2/v1/b2_protocol_v1.json",
            "preflight": "morocco26/data/goal100/b2/v1/b2_preflight.json",
            "evidence_rows": 0,
            "forecast_generated": False,
            "agentic": False,
            "next_gate": "B2_SCHEMA_VALID"
        }
        anti = state.setdefault("anti_drift", {})
        anti["B2_may_not_rewrite_F_minus_1"] = True
        anti["B2_manual_swing_forbidden"] = True
        anti["unknown_evidence_must_not_be_zero_imputed"] = True
        anti["agentic_layer_remains_locked_during_B2"] = True
        dump(state_path, state)


def main() -> None:
    preflight = verify_fminus1()
    B2.mkdir(parents=True, exist_ok=True)
    dump(B2 / "b2_preflight.json", preflight)
    dump(B2 / "b2_protocol_v1.json", protocol(preflight))
    dump(B2 / "b2_source_policy_v1.json", source_policy())
    dump(B2 / "b2_evidence_schema_v1.json", evidence_schema())
    dump(B2 / "b2_feature_dictionary_v1.json", feature_dictionary())
    dump(B2 / "source_registry.json", {"schema_version": "1.0", "sources": source_policy()["domain_seed_registry"]})
    dump(B2 / "entity_registry.json", {"schema_version": "1.0", "candidates": [], "parties_and_lists": [], "officeholders": [], "aliases": []})
    if not (B2 / "evidence_ledger.ndjson").exists():
        (B2 / "evidence_ledger.ndjson").write_text("", encoding="utf-8")
    write_csv(B2 / "candidate_registry.csv", ["candidate_id", "canonical_name", "aliases_json", "birth_date", "birth_date_source_evidence_id", "status"])
    write_csv(B2 / "list_availability.csv", ["cutoff", "territory_id", "party_or_list_id", "availability", "head_candidate_id", "evidence_id", "status"])
    write_csv(B2 / "territorial_networks.csv", ["cutoff", "territory_id", "source_entity_id", "target_party_or_list_id", "link_type", "weight_raw", "evidence_id", "status"])
    write_csv(B2 / "events.csv", ["cutoff", "territory_id", "party_or_list_id", "event_type", "event_value", "effective_at", "evidence_id", "status"])
    write_csv(B2 / "coverage_matrix.csv", ["cutoff", "territory_id", "party_or_list_id", "required_field", "coverage_status", "evidence_count", "certified_closed_universe"])

    (SCRIPTS / "goal100_validate_b2_v1.py").write_text(validator_source(), encoding="utf-8")
    (SCRIPTS / "goal100_freeze_b2_v1.py").write_text(freeze_source(), encoding="utf-8")
    (WORKFLOWS / "morocco26-b2-structured-evidence.yml").parent.mkdir(parents=True, exist_ok=True)
    (WORKFLOWS / "morocco26-b2-structured-evidence.yml").write_text(workflow_source(), encoding="utf-8")

    readme = f'''# MOROCCO//26 — B2 structured evidence v1\n\nStatus: **{protocol(preflight)['status']}**\n\nB2 is the non-agentic observation layer between immutable F-1 and preliminary F0.\nIt stores atomic source-backed facts; it does not produce free-form political swings.\n\n## Immediate workflow\n\n1. Populate `source_registry.json` with exact official party and election-source endpoints.\n2. Add atomic rows to `evidence_ledger.ndjson`.\n3. Run `python morocco26/scripts/goal100_validate_b2_v1.py`.\n4. Build deterministic entity/list/network/event tables and coverage matrix.\n5. Calibrate the residual model only on pre-2026 history; unidentified weights remain zero.\n6. Freeze B2 with an explicit cutoff; only then construct a new F0 snapshot.\n\nAgentic collection and reasoning remain locked.\n'''
    (B2 / "README.md").write_text(readme, encoding="utf-8")
    journal_path = append_journal(preflight)
    update_tracking(preflight)
    dump(B2 / "b2_bootstrap_status.json", {
        "schema_version": "1.0",
        "bootstrap_id": "M26-GOAL100-B2-BOOTSTRAP-V1",
        "created_at": NOW,
        "branch": BRANCH,
        "status": "PASS_SCAFFOLD_READY" if preflight["ready_for_b2_non_agentic_scaffold"] else "PASS_SCAFFOLD_BLOCKED_BY_F_MINUS_1",
        "journal_path": journal_path,
        "preflight": "morocco26/data/goal100/b2/v1/b2_preflight.json",
        "protocol": "morocco26/data/goal100/b2/v1/b2_protocol_v1.json",
        "evidence_rows": 0,
        "F0_created": False,
        "agentic_status": "LOCKED",
        "next_action": "Populate exact official source registry and ingest first atomic evidence rows; do not freeze B2 or create F0 yet."
    })
    print(json.dumps(load(B2 / "b2_bootstrap_status.json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
