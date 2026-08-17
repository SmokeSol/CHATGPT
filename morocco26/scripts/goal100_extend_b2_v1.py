#!/usr/bin/env python3
"""Extend B2 with deterministic feature construction and residual backtesting.

No current political fact is created by this script. It defines the transformation
from source-backed evidence to features and the only admissible path from those
features to a forecast residual. A missing historical feature panel blocks model
fitting and leaves all non-legal coefficients at exactly zero.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
B2 = G100 / "b2" / "v1"
SCRIPTS = ROOT / "scripts"
NOW = datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def dump(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def feature_build_protocol() -> dict:
    return {
        "schema_version": "1.0",
        "protocol_id": "M26-GOAL100-B2-FEATURE-BUILD-PROTOCOL-V1",
        "frozen_at": NOW,
        "input": "atomic evidence rows passing B2 evidence schema and cutoff",
        "output_key": ["cutoff", "territory_id", "party_or_list_id"],
        "source_precedence": {"A_OFFICIAL": 4, "B_PRIMARY": 3, "C_REPUTABLE_REPORTING": 2, "D_UNVERIFIED": 1},
        "active_statuses": ["ACTIVE"],
        "non_forecast_statuses": ["SUPERSEDED", "CONFLICT", "REJECTED", "PENDING_CORROBORATION"],
        "closed_universe_rule": {
            "LIST_NOT_FILED": "may equal 1 only when an A_OFFICIAL closed-universe filing source is cited",
            "candidate_absence": "UNKNOWN unless an official final list proves absence",
            "zero_imputation": False
        },
        "deterministic_features": {
            "LIST_FILED_OFFICIAL": {"claims": ["LIST_FILED"], "aggregation": "latest_highest_tier_boolean"},
            "LEGAL_ELIGIBILITY_BLOCK": {"claims": ["LEGAL_CHANGE"], "aggregation": "latest_highest_tier_boolean_explicit_only"},
            "HEAD_CANDIDATE_INCUMBENT": {"claims": ["CANDIDATE_RANK", "INCUMBENT_RUNNING"], "aggregation": "join_on_subject_rank_1"},
            "INCUMBENT_COUNT_ON_LIST": {"claims": ["INCUMBENT_RUNNING"], "aggregation": "unique_subject_count"},
            "DEFECTION_IN_COUNT": {"claims": ["PARTY_SWITCH_IN"], "aggregation": "unique_subject_count"},
            "DEFECTION_OUT_COUNT": {"claims": ["PARTY_SWITCH_OUT"], "aggregation": "unique_subject_count"},
            "MUNICIPAL_OFFICEHOLDER_SUPPORT": {"claims": ["OFFICE_HELD", "ENDORSEMENT"], "aggregation": "unique_verified_subject_count"},
            "FORMAL_ALLIANCE_SUPPORT": {"claims": ["ALLIANCE", "ENDORSEMENT"], "aggregation": "latest_highest_tier_boolean"},
            "CAMPAIGN_DISRUPTION_EVENT": {"claims": ["CAMPAIGN_EVENT", "ORGANIZATIONAL_EVENT"], "aggregation": "predefined_taxonomy_count"},
            "EVIDENCE_COVERAGE": {"claims": ["ALL"], "aggregation": "required_fields_observed_ratio"}
        },
        "conflicts": {
            "retain_all_rows": True,
            "resolved_value": "highest source tier, then latest effective_at, then latest retrieved_at",
            "same_rank_disagreement": "UNKNOWN plus conflict flag",
            "manual_override": False
        },
        "provenance": {
            "feature_to_evidence_ids_required": True,
            "feature_build_code_hash_required": True,
            "input_ledger_hash_required": True,
            "cutoff_required": True
        }
    }


def backtest_protocol() -> dict:
    return {
        "schema_version": "1.0",
        "protocol_id": "M26-GOAL100-B2-RESIDUAL-BACKTEST-PROTOCOL-V1",
        "frozen_at": NOW,
        "question": "Does deterministic B2 evidence improve predictions beyond the persistence-first structural baseline without using 2026 outcomes?",
        "unit": "territory x party/list x election cutoff",
        "target": {
            "vote": "observed next-election log-ratio innovation relative to the structural persistence mean",
            "turnout": "observed next-election logit-turnout innovation relative to structural persistence",
            "seats": "derived through the same legal allocator; never fit directly by hand"
        },
        "historical_inputs": {
            "required_panel": "morocco26/data/goal100/b2/v1/historical_b2_feature_panel.csv",
            "minimum_elections": 2,
            "minimum_complete_transitions": 2,
            "current_status": "MISSING_UNTIL_SOURCE_BACKFILL"
        },
        "model_family": {
            "vote": "multivariate ridge residual in explicit log-ratio coordinates",
            "turnout": "ridge residual on logit turnout",
            "intercept": False,
            "standardization": "fit within each training fold only",
            "lambda_grid": [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0],
            "feature_interactions": [],
            "nonlinear_terms": [],
            "manual_sign_constraints": False,
            "unidentified_feature_weight": 0.0
        },
        "validation": {
            "outer": "strict temporal leave-one-election-transition-out",
            "inner": "training-only temporal or grouped territorial cross-validation",
            "same_cutoff_baseline": "F-1/B*",
            "proper_scores": ["energy_score_vote_composition", "CRPS_turnout", "log_score_seat_distribution"],
            "secondary": ["Brier seat-event probabilities", "MAE expected seats", "interval coverage"],
            "paired_uncertainty": "territory-block bootstrap with fixed seed",
            "bootstrap_seed": 26092371,
            "bootstrap_replicates": 10000
        },
        "selection": {
            "primary": "mean paired improvement in vote Energy Score",
            "guardrails": [
                "turnout CRPS may not materially worsen",
                "seat log score may not materially worsen",
                "coverage may not be purchased by unbounded intervals"
            ],
            "minimum_incremental_value": {
                "preregister_before_fit": True,
                "default_exploratory_threshold": 0.0,
                "production_threshold": "must be frozen after historical power analysis and before 2026 scoring"
            }
        },
        "failure_policy": {
            "missing_historical_panel": "BLOCKED; all calibrated_or_zero coefficients remain zero",
            "no_out_of_sample_improvement": "B2 forecast residual is zero except hard legal list constraints",
            "unstable_sign_or_fold_variance": "feature removed only in a new protocol version; never post-hoc in V1",
            "2026_information_used_for_tuning": "experiment invalid"
        },
        "outputs": [
            "all fold predictions",
            "all lambda candidate scores",
            "selected coefficients and uncertainty",
            "paired score differences",
            "coverage diagnostics",
            "zero-weight features and reasons",
            "machine gate certificate"
        ]
    }


def collection_plan() -> dict:
    return {
        "schema_version": "1.0",
        "plan_id": "M26-GOAL100-B2-COLLECTION-PLAN-V1",
        "created_at": NOW,
        "mode": "NON_AGENTIC_DETERMINISTIC_OR_HUMAN_STRUCTURED",
        "waves": [
            {
                "wave": 1,
                "name": "LEGAL_LIST_UNIVERSE",
                "priority": "CRITICAL",
                "claims": ["LIST_FILED", "LIST_NOT_FILED", "CANDIDATE_IDENTITY", "CANDIDATE_RANK"],
                "preferred_sources": ["A_OFFICIAL"],
                "completion": "all 92 local and 12 regional contests have a cutoff-specific universe certificate"
            },
            {
                "wave": 2,
                "name": "INCUMBENCY_AND_SWITCHES",
                "priority": "HIGH",
                "claims": ["INCUMBENT_RUNNING", "INCUMBENT_NOT_RUNNING", "PARTY_SWITCH_IN", "PARTY_SWITCH_OUT"],
                "preferred_sources": ["A_OFFICIAL", "B_PRIMARY"],
                "completion": "every identified incumbent has a source-backed 2026 status or explicit UNKNOWN"
            },
            {
                "wave": 3,
                "name": "TERRITORIAL_NETWORKS",
                "priority": "MEDIUM",
                "claims": ["OFFICE_HELD", "ENDORSEMENT", "ALLIANCE", "NETWORK_LINK"],
                "preferred_sources": ["A_OFFICIAL", "B_PRIMARY"],
                "completion": "coverage matrix reports the observable local-officeholder universe and its gaps"
            },
            {
                "wave": 4,
                "name": "VERIFIED_EVENTS",
                "priority": "MEDIUM",
                "claims": ["CAMPAIGN_EVENT", "ORGANIZATIONAL_EVENT"],
                "preferred_sources": ["A_OFFICIAL", "B_PRIMARY", "C_REPUTABLE_REPORTING"],
                "completion": "only frozen taxonomy events; novel narratives are logged with forecast weight zero"
            },
            {
                "wave": 5,
                "name": "HISTORICAL_BACKFILL",
                "priority": "SCIENTIFIC_CRITICAL",
                "claims": ["all B2 feature families for pre-2026 elections"],
                "preferred_sources": ["A_OFFICIAL", "archived primary sources"],
                "completion": "historical feature panel supports the frozen temporal backtest or B2 remains coefficient-zero"
            }
        ],
        "stop_conditions": [
            "official final filing universe is not yet published: retain UNKNOWN and continue source watch",
            "historical panel cannot identify a feature: keep coefficient zero",
            "source conflict unresolved at same tier: mark conflict, do not choose narratively",
            "agentic tool required: stop; that belongs to a later preregistered arm"
        ]
    }


def coverage_protocol() -> dict:
    return {
        "schema_version": "1.0",
        "protocol_id": "M26-GOAL100-B2-COVERAGE-PROTOCOL-V1",
        "frozen_at": NOW,
        "dimensions": ["territory", "party_or_list", "required_field", "cutoff"],
        "statuses": ["OBSERVED", "AUTHORITATIVE_ABSENT", "UNKNOWN", "CONFLICT", "NOT_APPLICABLE"],
        "denominators": {
            "local_contests": 92,
            "regional_contests": 12,
            "seat_weighted": True,
            "party_list_universe": "cutoff-specific authoritative filing universe when available; otherwise 2021 observed universe labelled provisional"
        },
        "F0_minimums": {
            "official_list_universe": 1.0,
            "head_candidate_identity_seat_weighted": 0.9,
            "incumbent_status_seat_weighted": 0.8,
            "source_hash_and_timestamp": 1.0,
            "conflict_rate_max": 0.02
        },
        "below_threshold": "B2 diagnostic may freeze, but no adjusted F0 is issued; F0 equals F-1 only if explicitly labelled no-adjustment",
        "unknown_rule": "UNKNOWN remains in denominator and never becomes zero evidence"
    }


def feature_builder_source() -> str:
    return r'''#!/usr/bin/env python3
"""Compile deterministic B2 features at an explicit cutoff; no model weights."""
from __future__ import annotations
import csv, hashlib, json, os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data'/'goal100'/'b2'/'v1'
TIER={'A_OFFICIAL':4,'B_PRIMARY':3,'C_REPUTABLE_REPORTING':2,'D_UNVERIFIED':1}

def req(c,m):
    if not c: raise SystemExit('B2_FEATURE_BUILD_FAIL: '+m)
def parse(s): return datetime.fromisoformat(s.replace('Z','+00:00'))
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
cutoff=os.environ.get('B2_CUTOFF','').strip(); req(cutoff,'B2_CUTOFF required'); cutoff_dt=parse(cutoff)
rows=[]
for line_no,line in enumerate((B/'evidence_ledger.ndjson').read_text(encoding='utf-8').splitlines(),1):
    if not line.strip(): continue
    row=json.loads(line); row['_line']=line_no
    if row['status']!='ACTIVE' or parse(row['effective_at'])>cutoff_dt or parse(row['source_published_at'])>cutoff_dt: continue
    if row['source_tier']=='D_UNVERIFIED': continue
    rows.append(row)

def key(row): return (row['territory_scope'],row.get('party_or_list_id') or '')
groups=defaultdict(list)
for row in rows: groups[key(row)].append(row)
out=[]; provenance={}
for (territory,party), evidence in sorted(groups.items()):
    claims=defaultdict(list)
    for row in evidence: claims[row['claim_type']].append(row)
    def ordered(claim):
        return sorted(claims.get(claim,[]),key=lambda r:(TIER[r['source_tier']],parse(r['effective_at']),parse(r['retrieved_at'])),reverse=True)
    def latest_bool(claim):
        values=ordered(claim)
        if not values: return ''
        top=values[0]; rank=(TIER[top['source_tier']],top['effective_at'])
        tied=[r for r in values if (TIER[r['source_tier']],r['effective_at'])==rank]
        distinct={json.dumps(r['value'],sort_keys=True) for r in tied}
        return top['value'] if len(distinct)==1 else 'UNKNOWN_CONFLICT'
    subjects=lambda claim:{r['subject_id'] for r in claims.get(claim,[]) if r.get('subject_id')}
    filed=latest_bool('LIST_FILED')
    rank1={r['subject_id'] for r in claims.get('CANDIDATE_RANK',[]) if str(r.get('value'))=='1'}
    incumbents=subjects('INCUMBENT_RUNNING')
    feature={
      'cutoff':cutoff,'territory_id':territory,'party_or_list_id':party,
      'LIST_FILED_OFFICIAL':filed,
      'LEGAL_ELIGIBILITY_BLOCK':latest_bool('LEGAL_CHANGE'),
      'HEAD_CANDIDATE_INCUMBENT':('' if not rank1 else int(bool(rank1 & incumbents))),
      'INCUMBENT_COUNT_ON_LIST':len(incumbents),
      'DEFECTION_IN_COUNT':len(subjects('PARTY_SWITCH_IN')),
      'DEFECTION_OUT_COUNT':len(subjects('PARTY_SWITCH_OUT')),
      'MUNICIPAL_OFFICEHOLDER_SUPPORT':len(subjects('ENDORSEMENT') & subjects('OFFICE_HELD')),
      'FORMAL_ALLIANCE_SUPPORT':latest_bool('ALLIANCE'),
      'CAMPAIGN_DISRUPTION_EVENT':len(claims.get('CAMPAIGN_EVENT',[]))+len(claims.get('ORGANIZATIONAL_EVENT',[])),
      'EVIDENCE_COVERAGE':'',
      'CONFLICT_FLAG':int(any(r['status']=='CONFLICT' for r in evidence)),
      'EVIDENCE_COUNT':len(evidence)
    }
    out.append(feature)
    provenance[f'{territory}|{party}']=sorted(r['evidence_id'] for r in evidence)
columns=['cutoff','territory_id','party_or_list_id','LIST_FILED_OFFICIAL','LEGAL_ELIGIBILITY_BLOCK','HEAD_CANDIDATE_INCUMBENT','INCUMBENT_COUNT_ON_LIST','DEFECTION_IN_COUNT','DEFECTION_OUT_COUNT','MUNICIPAL_OFFICEHOLDER_SUPPORT','FORMAL_ALLIANCE_SUPPORT','CAMPAIGN_DISRUPTION_EVENT','EVIDENCE_COVERAGE','CONFLICT_FLAG','EVIDENCE_COUNT']
path=B/'features_current.csv'
with path.open('w',encoding='utf-8',newline='') as f:
    w=csv.DictWriter(f,fieldnames=columns); w.writeheader(); w.writerows(out)
cert={'schema_version':'1.0','certificate_id':'M26-GOAL100-B2-FEATURE-BUILD-V1','gate':'PASS','cutoff':cutoff,'evidence_rows_used':len(rows),'feature_rows':len(out),'ledger_sha256':sha(B/'evidence_ledger.ndjson'),'feature_sha256':sha(path),'provenance':provenance,'forecast_coefficients_applied':False,'agentic':False}
(B/'feature_build_certificate.json').write_text(json.dumps(cert,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(cert,ensure_ascii=False,indent=2))
'''


def backtest_source() -> str:
    return r'''#!/usr/bin/env python3
"""Fail-closed B2 residual backtest entry point.

The implementation refuses to estimate any coefficient until a versioned
historical B2 feature panel exists. This prevents the current 2026 evidence from
being used to choose signs, features or shrinkage.
"""
from __future__ import annotations
import csv, hashlib, json
from datetime import datetime, timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
B=ROOT/'data'/'goal100'/'b2'/'v1'
panel=B/'historical_b2_feature_panel.csv'
out=B/'b2_residual_backtest.json'
protocol=json.loads((B/'b2_residual_backtest_protocol_v1.json').read_text(encoding='utf-8'))
if not panel.exists():
    result={'schema_version':'1.0','audit_id':'M26-GOAL100-B2-RESIDUAL-BACKTEST-V1','created_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'gate':'BLOCKED_MISSING_HISTORICAL_FEATURE_PANEL','protocol_id':protocol['protocol_id'],'required_panel':str(panel.relative_to(ROOT.parent)),'coefficients':{f['feature_id']:0.0 for f in json.loads((B/'b2_feature_dictionary_v1.json').read_text(encoding='utf-8'))['features'] if f['forecast_role']=='calibrated_or_zero'},'2026_data_used_for_fit':False,'F0_unlocked':False,'next_action':'Backfill source-backed historical B2 features under the same schema; do not tune on 2026 implications.'}
    out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(2)
required={'election_year','transition_id','territory_id','party_or_list_id','target_vote_residual','target_turnout_residual'}
with panel.open(encoding='utf-8',newline='') as f:
    reader=csv.DictReader(f); columns=set(reader.fieldnames or []); rows=list(reader)
if not required<=columns: raise SystemExit('B2_BACKTEST_FAIL: missing historical columns '+str(sorted(required-columns)))
transitions=sorted({row['transition_id'] for row in rows})
if len(transitions)<2: raise SystemExit('B2_BACKTEST_FAIL: at least two historical transitions required')
# Numerical fitting is intentionally not silently improvised here. A separately
# reviewed implementation version must consume this now-validated panel while
# preserving the frozen folds, lambda grid and outputs.
result={'schema_version':'1.0','audit_id':'M26-GOAL100-B2-RESIDUAL-BACKTEST-V1','created_at':datetime.now(timezone.utc).replace(microsecond=0).isoformat(),'gate':'BLOCKED_IMPLEMENTATION_REVIEW_REQUIRED','protocol_id':protocol['protocol_id'],'historical_panel_sha256':hashlib.sha256(panel.read_bytes()).hexdigest(),'rows':len(rows),'transitions':transitions,'2026_data_used_for_fit':False,'F0_unlocked':False,'next_action':'Implement and independently review the frozen ridge temporal backtest; no coefficient exists yet.'}
out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(result,ensure_ascii=False,indent=2)); raise SystemExit(2)
'''


def append_journal() -> None:
    candidates=[ROOT/'FIL_D_ARIANE.md',ROOT/'FIL_ARIANE.md']
    path=next((p for p in candidates if p.exists()),candidates[0])
    marker='B2-A002 — Compilateur déterministe et contrat de backtest résiduel'
    text=path.read_text(encoding='utf-8') if path.exists() else '# MOROCCO//26 — FIL D’ARIANE\n'
    if marker not in text:
        text += f'''\n\n### {NOW} — {marker}\n\n- Le dictionnaire B2 est désormais compilable sans coefficient ni jugement narratif.\n- Le cutoff, les sources retenues, les conflits et les evidence IDs restent traçables jusqu’à chaque feature.\n- Le backtest résiduel est gelé en famille ridge et validation temporelle stricte.\n- Tant que `historical_b2_feature_panel.csv` manque, le certificat doit être `BLOCKED_MISSING_HISTORICAL_FEATURE_PANEL` et tous les poids non juridiques valent zéro.\n- Aucun F0 n’est créé à cette étape ; l’agentique reste verrouillée.\n- Prochaine action exacte : établir le registre de sources officielles puis lancer Wave 1 `LEGAL_LIST_UNIVERSE`, en parallèle du backfill historique.\n'''
        path.write_text(text,encoding='utf-8')


def main() -> None:
    if not B2.exists():
        raise SystemExit('B2_EXTEND_FAIL: B2 scaffold does not exist on this branch')
    dump(B2/'b2_feature_build_protocol_v1.json',feature_build_protocol())
    dump(B2/'b2_residual_backtest_protocol_v1.json',backtest_protocol())
    dump(B2/'b2_collection_plan_v1.json',collection_plan())
    dump(B2/'b2_coverage_protocol_v1.json',coverage_protocol())
    (SCRIPTS/'goal100_build_b2_features_v1.py').write_text(feature_builder_source(),encoding='utf-8')
    (SCRIPTS/'goal100_backtest_b2_residual_v1.py').write_text(backtest_source(),encoding='utf-8')
    append_journal()
    dump(B2/'b2_extension_status.json',{
        'schema_version':'1.0','extension_id':'M26-GOAL100-B2-EXTENSION-V1','created_at':NOW,
        'status':'PASS_PROTOCOLS_AND_COMPILER_READY','feature_builder':'morocco26/scripts/goal100_build_b2_features_v1.py',
        'backtest_entrypoint':'morocco26/scripts/goal100_backtest_b2_residual_v1.py',
        'historical_panel_status':'MISSING_EXPECTED_BLOCK','F0_created':False,'agentic_status':'LOCKED',
        'next_action':'Wave 1 official source discovery and atomic list/candidate evidence; historical backfill in parallel.'
    })
    print((B2/'b2_extension_status.json').read_text(encoding='utf-8'))

if __name__=='__main__': main()
