#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, io, json, math, random, zipfile
from collections import defaultdict, Counter
from pathlib import Path

EXPECTED_ROWS=94208
EXPECTED_WORK_ITEMS=2944
EXPECTED_TERRITORIES=92
EXPECTED_DIRECT=58
ARCHETYPES=256
BOOTSTRAP_REPS=10000
BOOTSTRAP_SEED=260819
REQUIRED_PUBLIC_ZIP_SHA='e8acad28dea5a531c21171db570b60d612993edd91db8f893e58c187c226696a'
REQUIRED_MANIFEST_SHA='f572170432bab6973309a188161a34a34f13d244e22b1598b3979d2a0097a5b3'
REQUIRED_WORK_MANIFEST_SHA='f0c625462a68f78c0cc6d8cb4c585add9ac6b82b7162317f69f4032c09db5e43'
REQUIRED_CONTRACT_SHA='68bb9822cce4b450b17cd2edec76036c257c83f3c8cef37a2e807b96a225992e'
PASS_TERMINAL='PASS_FULL_ENV_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING'
PASS_STATE='ASV2_FULL_ENV_HISTORICAL_SANITY_PASS_READY_FOR_2026_FREEZE'
FAIL_STATE='ASV2_FULL_ENV_KILL_BEFORE_2026'
FACTOR_KEYS=(
 'prior_vote_inertia','turnout_habit','personal_economic_conditions','employment_and_income',
 'social_protection_and_public_services','policy_program_fit','governance_and_institutions',
 'territorial_rural_fit','government_reward_punishment','local_candidate_context','other_verified_context')
ALLOWED_REASONS={
 'PRIOR_VOTE_INERTIA','PRIOR_ABSTENTION_INERTIA','TURNOUT_HABIT','ECONOMIC_SELF_INTEREST',
 'EMPLOYMENT_INCOME_FIT','SOCIAL_PROTECTION_PUBLIC_SERVICES_FIT','POLICY_PROGRAM_FIT',
 'GOVERNANCE_INSTITUTIONAL_FIT','TERRITORIAL_RURAL_FIT','GOVERNMENT_REWARD','GOVERNMENT_PUNISHMENT',
 'LOCAL_CANDIDATE_STRENGTH','LOCAL_CANDIDATE_WEAKNESS','ATTITUDE_POSTERIOR','OTHER_VERIFIED_CONTEXT',
 'NO_DIRECTIONAL_EVIDENCE'}


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p)->str:
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,obj):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def find_member_recursive(zip_path:Path,suffix:str):
 with zipfile.ZipFile(zip_path,'r') as z:
  hits=[n for n in z.namelist() if n.endswith(suffix)]
  if len(hits)==1:return z.read(hits[0])
  nested=[]
  for n in z.namelist():
   if n.lower().endswith('.zip'):
    try:
     with zipfile.ZipFile(io.BytesIO(z.read(n)),'r') as nz:
      hh=[m for m in nz.namelist() if m.endswith(suffix)]
      nested += [nz.read(m) for m in hh]
    except zipfile.BadZipFile:pass
  if len(nested)==1:return nested[0]
 raise RuntimeError(f'expected exactly one {suffix}')
def load_json_member(z,suffix):return json.loads(find_member_recursive(Path(z),suffix))
def load_jsonl_member(z,suffix):return [json.loads(x) for x in find_member_recursive(Path(z),suffix).decode().splitlines() if x.strip()]


def load_public_contract(public_zip, work_manifest_override=None, skip_zip_sha=False):
 if not skip_zip_sha and sha_file(public_zip)!=REQUIRED_PUBLIC_ZIP_SHA:raise RuntimeError('public handoff ZIP SHA mismatch')
 with zipfile.ZipFile(public_zip,'r') as z:
  manifest=json.loads(z.read('handoff_manifest.json'))
  if sha_bytes(z.read('handoff_manifest.json'))!=REQUIRED_MANIFEST_SHA:raise RuntimeError('public manifest SHA mismatch')
  if manifest.get('public_environment_id')!='ENV_4D19B3E7':raise RuntimeError('environment extension mismatch')
  if manifest.get('target_outcomes_present') is not False or manifest.get('mapping_material_present') is not False:raise RuntimeError('public contamination flag')
  if work_manifest_override:
   work=readj(work_manifest_override)
  else:
   if sha_bytes(z.read('work_manifest.json'))!=REQUIRED_WORK_MANIFEST_SHA:raise RuntimeError('work manifest SHA mismatch')
   work=json.loads(z.read('work_manifest.json'))
  if len(work['work_items'])!=EXPECTED_WORK_ITEMS:raise RuntimeError('work item count mismatch')
  expected={}; party_panel={}; voter_meta={}; context_cache={}; batch_cache={}
  for wi in work['work_items']:
   eid,tid,cid,bid=wi['anonymous_election_id'],wi['anonymous_territory_id'],wi['condition_id'],wi['batch_id']
   cpath=wi['context_path'];bpath=wi['voter_batch_path']
   if cpath not in context_cache:
    c=json.loads(z.read(cpath));
    if c.get('schema_version')!='2.0':raise RuntimeError('context schema version mismatch')
    if 'election_environment_card' not in c:raise RuntimeError('missing election environment card')
    cards=c['election_environment_card'].get('party_offer_cards',[])
    if len(cards)!=9 or {x['anonymous_party_id'] for x in cards}!=set(c['available_party_ids']):raise RuntimeError('offer card panel mismatch')
    context_cache[cpath]=tuple(sorted(c['available_party_ids']))
   parties=context_cache[cpath];party_panel.setdefault((eid,tid),parties)
   if party_panel[(eid,tid)]!=parties:raise RuntimeError('party panel drift')
   if bpath not in batch_cache:
    b=json.loads(z.read(bpath));
    if b.get('anonymous_election_id')!=eid or b.get('anonymous_territory_id')!=tid or b.get('batch_id')!=bid:raise RuntimeError('batch identity mismatch')
    rows=b['voter_archetypes']
    if len(rows)!=32:raise RuntimeError('voter batch !=32')
    batch_cache[bpath]=rows
   for a in batch_cache[bpath]:
    aid=a['weighted_archetype_id'];key=(eid,tid,cid,bid,aid)
    if key in expected:raise RuntimeError('duplicate expected row')
    expected[key]=parties
    voter_meta[(eid,tid,bid,aid)]={'prior_vote_or_abstention':a.get('prior_vote_or_abstention','ABSTAIN')}
  if len(expected)!=EXPECTED_ROWS:raise RuntimeError('expected row count mismatch')
  if len(voter_meta)!=EXPECTED_ROWS//2:raise RuntimeError('voter metadata count mismatch')
 return manifest,expected,party_panel,work,voter_meta


def load_public_contract_from_workmanifest(work_path,priv):
 work=readj(work_path)
 if sha_file(work_path)!=REQUIRED_WORK_MANIFEST_SHA:raise RuntimeError('work manifest SHA mismatch')
 expected={};party_panel={};voter_meta={}
 # Dry-run work-manifest-only mode cannot recover full voter priors; derive IDs and use ABSTAIN.
 for wi in work['work_items']:
  eid,tid,cid,bid=wi['anonymous_election_id'],wi['anonymous_territory_id'],wi['condition_id'],wi['batch_id']
  parties=tuple(sorted(priv['local_party_to_global_by_election_territory'][eid][tid]));party_panel[(eid,tid)]=parties
  bi=int(bid[1:])
  for i in range((bi-1)*32+1,bi*32+1):
   aid=f'A{i:03d}';expected[(eid,tid,cid,bid,aid)]=parties;voter_meta.setdefault((eid,tid,bid,aid),{'prior_vote_or_abstention':'ABSTAIN'})
 if len(expected)!=EXPECTED_ROWS:raise RuntimeError('expected rows dryrun mismatch')
 return {'status':'DRYRUN_MANIFEST_ONLY'},expected,party_panel,work,voter_meta


def validate_outputs(opus_zip,expected):
 terminal=load_json_member(opus_zip,'as2_full_environment_terminal_report.json')
 manifest=load_json_member(opus_zip,'as2_full_environment_output_manifest.json')
 rows=load_jsonl_member(opus_zip,'as2_full_environment_all_outputs.jsonl')
 valid={};invalid=[]
 for i,r in enumerate(rows,1):
  try:
   k=(r['anonymous_election_id'],r['anonymous_territory_id'],r['condition_id'],r['batch_id'],r['weighted_archetype_id'])
   if k not in expected:raise ValueError('unexpected identifier tuple')
   if k in valid:raise ValueError('duplicate row')
   if set(r)!={'anonymous_election_id','anonymous_territory_id','condition_id','batch_id','weighted_archetype_id','turnout_probability','conditional_party_probabilities','factor_importance','reason_codes'}:raise ValueError('output keys mismatch')
   u=float(r['turnout_probability'])
   if not math.isfinite(u) or not 0<=u<=1:raise ValueError('turnout invalid')
   probs=r['conditional_party_probabilities'];parties=expected[k]
   if set(probs)!=set(parties):raise ValueError('party probability keys mismatch')
   vals=[float(probs[p]) for p in parties]
   if any(not math.isfinite(x) or x<0 or x>1 for x in vals) or abs(sum(vals)-1)>1e-9:raise ValueError('party simplex invalid')
   fac=r['factor_importance']
   if set(fac)!=set(FACTOR_KEYS):raise ValueError('factor keys mismatch')
   fv=[float(fac[x]) for x in FACTOR_KEYS]
   if any(not math.isfinite(x) or x<0 or x>1 for x in fv) or abs(sum(fv)-1)>1e-9:raise ValueError('factor simplex invalid')
   reasons=r['reason_codes']
   if not isinstance(reasons,list) or not 1<=len(reasons)<=4 or len(set(reasons))!=len(reasons) or any(x not in ALLOWED_REASONS for x in reasons):raise ValueError('reason codes invalid')
   valid[k]={'turnout':u,'probs':{p:float(probs[p]) for p in parties},'factors':{x:float(fac[x]) for x in FACTOR_KEYS},'reasons':reasons}
  except Exception as e:invalid.append({'line':i,'error':type(e).__name__+':'+str(e)})
 missing=len(set(expected)-set(valid));rate=len(valid)/EXPECTED_ROWS;terminal_ok=terminal.get('terminal_status')==PASS_TERMINAL;full=(len(rows)==EXPECTED_ROWS and len(valid)==EXPECTED_ROWS and not invalid and missing==0 and terminal_ok)
 return {'rows_raw':len(rows),'