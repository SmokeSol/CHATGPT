from __future__ import annotations
import hashlib,io,json,math,zipfile
from pathlib import Path
EXPECTED_ROWS=94208;EXPECTED_WORK_ITEMS=2944;ARCHETYPES=256
REQUIRED_PUBLIC_ZIP_SHA='ab710f494ecff8b0935d6f86618a153f24276362f9a74e9c77c10ade841977ed'
REQUIRED_MANIFEST_SHA='66a85f2b295eb0f81b2b19d71d38e5e296724bacfdb88feedd46e30541e895e1'
REQUIRED_WORK_MANIFEST_SHA='9d30b102d70a473dd8b7c63124e6cd3d50bbf77a8cb48c8e36a1a476a638c0bf'
REQUIRED_CONTRACT_SHA='c8ce5080e48cfb23010548795279f3ee67cdf92ae23e69db9fa7e1a9d04f8d25'
REQUIRED_PRIVATE_MANIFEST_SHA='d3e3809d498f0a48d361023bffd48e7589a4cfbb57212410bf9ca0698f92e6a9'
PASS_TERMINAL='PASS_RICH_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING'
ALLOWED_REASONS={'PRIOR_VOTE_INERTIA','PRIOR_ABSTENTION_INERTIA','TURNOUT_TRANSITION','DEMOGRAPHIC_HOUSEHOLD_PRIOR','SOCIOECONOMIC_LATENT_PRIOR','ATTITUDE_POSTERIOR','INCUMBENCY','PARTY_SWITCH','LOCAL_OR_REGIONAL_OFFICE','PARTY_OR_NATIONAL_OFFICE','FORMER_MP_OR_MINISTER','ENDORSEMENT_OR_ALLIANCE','WITHDRAWAL_SANCTION_OR_INCAPACITY','OTHER_VERIFIED_CONTEXT','NO_DIRECTIONAL_EVIDENCE'}
def sha_bytes(b):return hashlib.sha256(b).hexdigest()
def sha_file(p):
 h=hashlib.sha256()
 with open(p,'rb') as f:
  for b in iter(lambda:f.read(1<<20),b''):h.update(b)
 return h.hexdigest()
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,o):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(o,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
def find_member(zp,suffix):
 with zipfile.ZipFile(zp) as z:
  h=[n for n in z.namelist() if n.endswith(suffix)]
  if len(h)==1:return z.read(h[0])
  nested=[]
  for n in z.namelist():
   if n.lower().endswith('.zip'):
    try:
     with zipfile.ZipFile(io.BytesIO(z.read(n))) as nz:
      nested += [nz.read(m) for m in nz.namelist() if m.endswith(suffix)]
    except zipfile.BadZipFile:pass
  if len(nested)==1:return nested[0]
 raise RuntimeError('expected exactly one '+suffix)
def load_json_member(z,s):return json.loads(find_member(z,s))
def load_jsonl_member(z,s):return [json.loads(x) for x in find_member(z,s).decode().splitlines() if x.strip()]
def expected_from_work(work,priv=None,z=None):
 if len(work['work_items'])!=EXPECTED_WORK_ITEMS:raise RuntimeError('work item count mismatch')
 expected={};panels={};cache={}
 for wi in work['work_items']:
  eid,tid,cid,bid=wi['anonymous_election_id'],wi['anonymous_territory_id'],wi['condition_id'],wi['batch_id']
  if priv is not None: parties=tuple(sorted(priv['local_party_to_global_by_election_territory'][eid][tid]))
  else:
   cp=wi['context_path']
   if cp not in cache: cache[cp]=tuple(sorted(json.loads(z.read(cp))['available_party_ids']))
   parties=cache[cp]
  panels.setdefault((eid,tid),parties)
  if panels[(eid,tid)]!=parties:raise RuntimeError('party panel drift')
  bi=int(bid[1:])
  for i in range((bi-1)*32+1,bi*32+1):expected[(eid,tid,cid,bid,f'A{i:03d}')]=parties
 if len(expected)!=EXPECTED_ROWS:raise RuntimeError('expected row count mismatch')
 return expected,panels
def load_contract(publiczip=None,workmanifest=None,priv=None):
 if publiczip:
  if sha_file(publiczip)!=REQUIRED_PUBLIC_ZIP_SHA:raise RuntimeError('public ZIP SHA mismatch')
  z=zipfile.ZipFile(publiczip);m=json.loads(z.read('handoff_manifest.json'))
  if sha_bytes(z.read('handoff_manifest.json'))!=REQUIRED_MANIFEST_SHA:raise RuntimeError('manifest SHA mismatch')
  if sha_bytes(z.read('work_manifest.json'))!=REQUIRED_WORK_MANIFEST_SHA:raise RuntimeError('work SHA mismatch')
  w=json.loads(z.read('work_manifest.json'));e,p=expected_from_work(w,z=z);z.close();return m,w,e,p
 if sha_file(workmanifest)!=REQUIRED_WORK_MANIFEST_SHA:raise RuntimeError('work SHA mismatch')
 w=readj(workmanifest);e,p=expected_from_work(w,priv=priv);return {'status':'DRYRUN_MANIFEST_ONLY'},w,e,p
def validate_outputs(opuszip,expected):
 term=load_json_member(opuszip,'as2_rich_terminal_report.json');man=load_json_member(opuszip,'as2_rich_output_manifest.json');rows=load_jsonl_member(opuszip,'as2_rich_all_outputs.jsonl');valid={};bad=[]
 for i,r in enumerate(rows,1):
  try:
   k=(r['anonymous_election_id'],r['anonymous_territory_id'],r['condition_id'],r['batch_id'],r['weighted_archetype_id'])
   if k not in expected or k in valid:raise ValueError('identifier/duplicate')
   u=float(r['turnout_probability']);probs=r['conditional_party_probabilities'];exp=set(expected[k])
   if not math.isfinite(u) or not 0<=u<=1 or set(probs)!=exp:raise ValueError('turnout/party keys')
   vals={p:float(probs[p]) for p in expected[k]}
   if any(not math.isfinite(x) or not 0<=x<=1 for x in vals.values()) or abs(sum(vals.values())-1)>1e-9:raise ValueError('simplex')
   rs=r['reason_codes']
   if not isinstance(rs,list) or not 1<=len(rs)<=3 or len(set(rs))!=len(rs) or any(x not in ALLOWED_REASONS for x in rs):raise ValueError('reason codes')
   valid[k]={'turnout':u,'probs':vals}
  except Exception as e:bad.append({'line':i,'error':type(e).__name__+':'+str(e)})
 missing=len(set(expected)-set(valid));full=len(rows)==EXPECTED_ROWS and len(valid)==EXPECTED_ROWS and not bad and missing==0 and term.get('terminal_status')==PASS_TERMINAL
 return {'rows_raw':len(rows),'valid_rows':len(valid),'invalid_rows':bad[:100],'missing_expected_rows':missing,'validity_rate':len(valid)/EXPECTED_ROWS,'terminal_ok':term.get('terminal_status')==PASS_TERMINAL,'full_contract_pass':full,'terminal':term,'manifest':man},valid
