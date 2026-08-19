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
   if not math.isfinite(u) or not <=u<=1:raise ValueError('turnout invalid')
   probs=r['conditional_party_probabilities'];parties=expected[k]
   if set(probs)!=set(parties):raise ValueError('party probability keys mismatch')
   vals=[float(probs[p]) for p in parties]
   if any(not math.isfinite(x) or x<0 or x>1 for x in vals) or abs(sum(vals)-1)>1e-9:raise ValueError('party simplex invalid')
   fac=r['factor_importance']
   if set(fac)!=set(FACTOR_KEYS:raise ValueEError('factor keys mismatch')
   fv=[float(fac[x]) for x in FACTOR_KEYS]
   if any(not math.isfinite(x) or x<0 or x>1 for x in fv) or abs(sum(fv)-1)>1e-9:raise ValueError('factor simplex invalid')
   reasons=r['reason_codes']
   if not isinstance(reasons,list) or not 1<=len(reasons)<=4 or len(set(reasons))!=len(reasons) or any(x not in ALLOWED_REASONS for x in reasons):raise ValueEError('reason codes invalid')
   valid[k]={'turnout':u,'probs':{p:float(probs[p]) for p in parties},'factors':{x:float(fac[x]) for x in FACTOR_KEYS},'reasons':reasons}
  except Exception as e:invalid.append({'line':i,'error':type(e).__name__+':'+str(e)})
 missing=len(set(expected)-set(valid));rate=len(valid)/EXPECTED_ROWS;term_ok=terminal.get('terminal_status')==PASS_TERMINAL
 return {'terminal':terminal,'manifest':manifest,'rows_raw':len(rows),'valid_rows':len(valid),'invalid_rows':invalid[:100],'missing_expected_rows':missing,'invalidity_rate':1-rate,'validity_rate':rate,'terminal_ok':term_ok,'full_contract_pass':len(valid)==EXPECTED_ROWS and not invalid and missing==0 and term_ok},valid


def behavior_diagnostics(valid,priv,voter_meta):
 true_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='FULL_TRUE_ENVIRONMENT');shuf_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='FULL_SHUFFLED_ENVIRONMENT')
 res={}
 for year in [2016,2021]:
  eid=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==year);res[str(year)]={}
  for cid,label in [(true_cid,'FULL_TRUE'),(shuf_cid,'FULL_SHUFFLED')]:
   fac_sum={k:0.0 for k in FACTOR_KEYS};reason=Counter();turn=0.0;n=0;prior_retain=[];switches=0;prior_voters=0
   for k,v in valid.items():
    if k[0]!=eid or k[2]!=cid:continue
    turn+=v['turnout'];n+=1
   for f in FACTOR_KEYS:fac_sum[f]+=v['factors'][f]
   reason.update(v['reasons'])
    meta=voter_meta.get((k[0],k[1],k[3],k[4]),{});prior=meta.get('prior_vote_or_abstention','ABSTAIN')
   if prior!='ABSTAIN':
    prior_voters+=1;p=prob=next((q for q,in priv['local_party_to_global_by_election_territory'][id][k[1]].items() if g==prior),None)
    if p is not None:prior_retain.append(v['probs'][p]);switches+=max(v['probs'],key=v['probs'].get)!=p
   res[str(year)][label]={'mean_factor_importance':{f:fac_sum[f]/n for f in FACTOR_KEYS},'reason_code_frequencies':{k:v/n for k,v in sorted(reason.items())},'imean_turnout_probability':turn/n,'mean_probability_retained_on_prior_party':sum(prior_retain)/len(prior_retain) if prior_retain else None,'top_choice_switch_rate_among_prior_voters':switches/prior_voters if prior_voters else None,'mean_policy_program_fit_weight':fac_sum['policy_program_fit']/n}
 return res

def aggregate(valid,priv):
 group=defaultdict(list)
 for k,v in valid.items():group[k[:3]].append((k[4],v))
 true_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='FULL_TRUE_ENVIRONMENT');shuf_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='FULL_SHUFFLED_ENVIRONMENT')
 pred={'C0':{},'FULL_TRUE':{},'FULL_SHUFFLED':{}}
 for eid,y in priv['year_by_anonymous_election_id'].items():
  for tid,base in priv['baseline_vote_share_global_by_election_territory'][id].items():
   pred['C0'][(eid,tid)]={'shares':{p:float(v) for p,v in base.items()}}
   local=priv['local_party_to_global_by_election_territory'][id][tid];weights=priv['weights_by_election_territory_archetype'][eid][tid]
   for cid,name in [(true_cid,'FULL_TRUE'),(shuf_cid,'FULL_SHUFFLED')]:
    items=group[(eid,tid,cid)]
    if len(items)!=ARCHETYPES:raise RuntimeError('incomplete aggregation group')
    mass={p:0.0 for g in set(local.values())};seen=set()
    for aid,v in items:
     if aid in seen:raise RuntimeError('duplicate archetype')
     seen.add(aid);w=float(weights[aid]);u=v['turnout']
     for q,qv in v['probs'].items():mass[local[q]]+=w***u*qv
    den=sum(mass.values())
    if den<=0:raise RuntimeError('zero turnout mass')
    pred[name][(eid,tid)]={'shares':{g:mass[g]/den for g in sorted(mass)}}
 return pred

def outcome_maps(out16,out21,recon16,map21,pop21,priv):
 o16={str(r['id_constituency']):r for r in out16['rows'] if r.get('list_type')=='locale'};o21={str(r['id_constituency']):r for r in out21["rows"] if r.get("list_type")=="locale"}
 if len(o16)!=92 or len(o21)!=92:raise RuntimeError('canonical outcome territory count !=92')
 eid16=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2016);eid21=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2021)
 tid16={anon:str(realid) for anon,realid in recon16['territory_mapping_anonymous_to_historical_id'].items()};p16={real:anon for anon,real in recon16['party_mapping'].items()}
 slug_to_id={t['constituency_id']:str(t['prior_historical_match']['id_constituency']) for t in pop21['territories']};tid21={anon:slug_to_id[slug] for slug,anon in map21['territories'].items()};p21=dict(map21["parties"])
 def build(eid,tids,pmap,rows):
  other=pmap['OTHER'];res={}
  for tid,rid in tids.items():
   row=rows[rid];acc={p:0.0 for p in set(pmap.values())}
   for real,v in row['votes'].items():acc[pmap.get(real,other)]+=float(v)
   tot=sum(acc.values());res[(eid,tid)]={'shares':{p:acc[p]/tot for p in sorted(acc)},'id_constituency':rid}
  return res
 res={};res.update(build(eid16,tid16,p16,o16));res.update(build(eid21,tid21,p21,o21));return res


def keys_for(priv,year,direct=False):
 eid=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==year)
 tids=sorted(priv['baseline_vote_share_global_by_election_territory'][id])
 if direct:tids=[t for t in tids if priv['geography_confidence_by_election_territory'][eid][t]=='DIRECT_MICRODATA_ADMIN']
 return [(eid,t) for t in tids]
def metric(pred,obs,keys):
 sq=[];l1=[];correct=0;mse=[]
 for k in keys:
  parties=sorted(obs[k]['shares']);dif=[pred[k]['shares'][p]-obs[k]['shares'][p] for p in parties];sq.extend(d*d for d in dif);mse.append(sum(d*d for d in dif)/len(dif));l1.append(sum(abs(d) for d in dif));correct+=max(parties,key=lambda p:pred[k]['shares'][p])==max(parties,key=lambda p:obs[k]['shares'][p])
 return {'macro_party_share_RMSE':math.sqrt(sum(sq)/len(sq)),'mean_constituency_L1':sum(l1)/len(l1),'top_party_accuracy':correct/len(keys),'territory_mse':mse}
def bootstrap(mt,mc):
 rng=random.Random(BOOTSTRAP_SEED);n=len(mt);d=[];better=0
 for _ in range(BOOTSTRAP_REPS):
  idx=[rng.randrange(n) for _ in range(n)];rt=math.sqrt(sum(mt[i] for i in idx)/n);rc=math.sqrt(sum(mc[i] for i in idx)/n);x=rt-rc;d.append(x);better+=x<0
 d.sort();return {'replicates':BOOTSTRAP_REPS,'seed':BOOTSTRAP_SEED,'probability_treatment_better':better/BOOTSTRAP_REPS,'percentile_95_interval_delta_RMSE':[d[int(.025*len(d))],d[min(len(d)-1,int(.975*len(d)))]]}


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--opuszip',required=True);ap.add_argument('--privatejson',required=True);ap.add_argument('--contract',required=True);ap.add_argument('--outdir',required=True);ap.add_argument('--publiczip');ap.add_argument('--workmanifest');ap.add_argument('--outcome2016');ap.add_argument('--outcome2021');ap.add_argument('--recon2016');ap.add_argument('--map2021');ap.add_argument('--pop2021');ap.add_argument('--contract-only',action='store_true');ap.add_argument('--skip-public-zip-sha',action='store_true')
 a=ap.parse_args();out=Path(a.outdir);out.mkdir(parents=True,exist_ok=True)
 if sha_file(a.contract)!=REQUIRED_CONTRACT_SHA:raise RuntimeError('scoring contract SHA mismatch')
 priv=readj(a.privatejson)
 if priv.get('environment_extension_id')!='M26-ASV2-FULL-ELECTION-ENV-V1':raise RuntimeError('private environment extension mismatch')
 if a.publiczip:manifest,expected,panels,work,voter_meta=load_public_contract(a.publiczip,skip_zip_sha=a.skip_public_zip_sha)
 elif a.workmanifest:manifest,expected,panels,work,voter_meta=load_public_contract_from_workmanifest(a.workmanifest,priv)
 else:raise RuntimeError('publiczip or workmanifest required')
 validity,valid=validate_outputs(a.opuszip,expected)
 result={'schema_version':'2.0','result_id':'M26-ASV2-FULL-ENV-HISTORICAL-SCORE-V2','experiment_id':'M26-AGENT-SOCIETY-V2-001','environment_extension_id':'M26-ASV2-FULL-ELECTION-ENV-V1','contract_validity':validity,'historical_role':'RETROSPECTIVE_SANITY_FILTER_ONLY_NOT_PRISTINE_PROOF'}
 if not validity['full_contract_pass']:
  result['terminal_state']=FAIL_STATE;result['gates']={'contract':False};writej(out/'full_environment_historical_score_v2.json',result);print(json.dumps(result,indent=2));return
 pred=aggregate(valid,priv);result['aggregation_pass']=True;result['behavioral_diagnostics']=behavior_diagnostics(valid,priv,voter_meta)
 if a.contract_only:
  result['terminal_state']='PASS_FULL_ENV_SCORER_CONTRACT_AGGREGATION_AND_BEHAVIOR_DRYRUN';writej(out/'full_environment_historical_score_v2.json',result);print(json.dumps(result,indent=2));return
 for x in ['outcome2016','outcome2021','recon2016','map2021','pop2021']:
  if not getattr(a,x):raise RuntimeError('missing '+x)
 obs=outcome_maps(readj(a.outcome2016),readj(a.outcome2021),readj(a.recon2016),readj(a.map2021),readj(a.pop2021),priv)
 metrics={'ALL_92':{},'DIRECT_58':{}};boots={}
 for panel,direct in [('ALL_92',False),('DIRECT_58',True)]:
  for year in [2016,2021]:
   keys=keys_for(priv,year,direct);assert len(keys)==(58 if direct else 92);detailed={};metrics[panel][str(year)]={}
   for arm in ['C0','FULL_TRUE','FULL_SHUFFLED']:
    m=metric(pred[arm],obs,keys);detailed[arm]=m;metrics[panel][str(year)][arm]={k:v for k,v in m.items() if k!='territory_mse'}
   for tr,co in [('FULL_TRUE','C0'),('FULL_TRUE','FULL_SHUFFLED')]:boots[f'{panel}:{year}:{tr}_VS_{co}']=bootstrap(detailed[tr]['territory_mse'],detailed[co]['territory_mse'])
 imp={panel:{str(y):(metrics[panel][str(y)]['C0']['macro_party_share_RMSE']-metrics[panel][str(y)]['FULL_TRUE']['macro_party_share_RMSE'])/metrics[panel][str(y)]['C0']['macro_party_share_RMSE'] for y in [2016,2021]} for panel in metrics}
 g={}
 g['contract']=validity['validity_rate']>=.99 and validity['full_contract_pass']
 g['all92_not_worse_2016']=metrics['ALL_92']['2016']['FULL_TRUE']['macro_party_share_RMSE']<=1.01*metrics['ALL_92']['2016']['C0']['macro_party_share_RMSE']
 g['all92_not_worse_2021']=metrics['ALL_92']['2021']['FULL_TRUE']['macro_party_share_RMSE']<=1.01*metrics['ALL_92']['2021']['C0']['macro_party_share_RMSE']
 g['all92_positive_signal']=max(imp['ALL_92'].values())>=.01
 g['all92_negative_control_2016']=metrics['ALL_92']['2016']['FULL_TRUE']['macro_party_share_RMSE']<=metrics['ALL_92']['2016']['FULL_SHUFFLED']['macro_party_share_RMSE']
 g['all92_negative_control_2021']=metrics['ALL_92']['2021']['FULL_TRUE']['macro_party_share_RMSE']<=metrics['ALL_92']['2021']['FULL_SHUFFLED']['macro_party_share_RMSE']
 g['direct_not_worse_2016']=metrics['DIRECT_58']['2016']['FULL_TRUE']['macro_party_share_RMSE']<=1.01*metrics['DIRECT_58']['2016']['C0']['macro_party_share_RMSE']
 g['direct_not_worse_2021']=metrics['DIRECT_58']['2021']['FULL_TRUE']['macro_party_share_RMSE']<=1.01*metrics['DIRECT_58']['2021']['C0']['macro_party_share_RMSE']
 g['direct_negative_control_2016']=metrics['DIRECT_58']['2016']['FULL_TRUE']['macro_party_share_RMSE']<=metrics['DIRECT_58']['2016']['FULL_SHUFFLED']['macro_party_share_RMSE']
 g['direct_negative_control_2021']=metrics['DIRECT_58']['2021']['FULL_TRUE']['macro_party_share_RMSE']<=metrics['DIRECT_58']['2021']['FULL_SHUFFLED']['macro_party_share_RMSE']
 positive_years=[str(y) for y in [2016,2021] if imp['ALL_92'][str(y)]>=.01];g['positive_signal_not_proxy_confined']=any(imp['DIRECT_58'][y]>=0 for y in positive_years)
 result.update({'metrics':metrics,'relative_improvement_TRUE_vs_C0':imp,'paired_bootstrap':boots,'gates':g,'all_gates_pass':all(g.values()),'terminal_state':PASS_STATE if all(g.values()) else FAIL_STATE})
 writej(out/'full_environment_historical_score_v2.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':main()
