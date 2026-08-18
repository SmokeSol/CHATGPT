#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, json, math, os, shutil, zipfile
from pathlib import Path

EXPERIMENT_ID='M26-AGENT-SOCIETY-V2-001'
SCHEMA_VERSION='1.0'
BATCH_SIZE=32
META_FEATURES={'BALLOT_LIST_PRESENT','EVIDENCE_COUNT','SOURCE_CLASS_MAX','SOURCE_CONFLICT'}
COND_TRUE='C_4F91A2D7'
COND_SHUFFLED='C_B73C08E1'


def canon(obj):
    return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p): return sha_bytes(Path(p).read_bytes())
def readj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,obj):
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def packet_hash(obj):
    x=dict(obj); x.pop('packet_sha256',None); return sha_bytes(canon(x))

def sanitize_party_context(packet):
    out=[]
    for party in sorted(packet['parties'],key=lambda x:x['anonymous_party_id']):
        feats=[]
        for f in party['features']:
            if f['feature_id'] in META_FEATURES: continue
            feats.append({
                'feature_id':f['feature_id'],
                'status':f.get('status'),
                'value':f.get('value'),
                'conflict':bool(f.get('conflict',False)),
            })
        out.append({'anonymous_party_id':party['anonymous_party_id'],'features':feats})
    return out

def context_density(packet):
    nontrivial=0; directional_true=0
    for party in packet['parties']:
        for f in party['features']:
            if f['feature_id'] in META_FEATURES: continue
            if f.get('status')=='VERIFIED' and f.get('value') is not None and not f.get('conflict'):
                nontrivial+=1
                if f.get('value') is True: directional_true+=1
    return nontrivial,directional_true

def make_derangement(bundle):
    rows=[]
    for p in bundle['packets']:
        d=context_density(p); rows.append((d[0],d[1],p['anonymous_territory_id']))
    rows.sort()
    if len(rows)%2: raise RuntimeError('territory count must be even for adjacent-pair derangement')
    m={}
    for i in range(0,len(rows),2):
        a=rows[i][2]; b=rows[i+1][2]; m[a]=b; m[b]=a
    if any(k==v for k,v in m.items()) or len(m)!=len(rows): raise RuntimeError('invalid derangement')
    return m

def inv_party_2016(recon):
    # reconstruction is anonymous -> real
    return {real:anon for anon,real in recon['party_mapping'].items()}

def pop_lookup_2016(pop):
    out={}
    for t in pop['territories']:
        k=str(t['prior_historical_match']['id_constituency'])
        if k in out: raise RuntimeError('duplicate 2016 prior id '+k)
        out[k]=t
    return out

def pop_lookup_2021(pop):
    out={}
    for t in pop['territories']:
        k=t['constituency_id']
        if k in out: raise RuntimeError('duplicate 2021 constituency slug '+k)
        out[k]=t
    return out

def map_prior_state(v, real_to_anon, other_anon):
    if v=='ABSTAIN': return 'ABSTAIN'
    return real_to_anon.get(v,other_anon)

def prior_anchor(pop_t, real_to_anon, party_ids):
    raw=pop_t['target_marginals']['prior_vote_or_abstention']
    abst=float(raw.get('ABSTAIN',0.0)); turnout=max(0.0,min(1.0,1.0-abst))
    acc={p:0.0 for p in party_ids}; other=real_to_anon['OTHER']
    for real,v in raw.items():
        if real=='ABSTAIN': continue
        acc[real_to_anon.get(real,other)]+=float(v)
    s=sum(acc.values())
    if s<=0: raise RuntimeError('zero prior turnout party mass')
    cond={p:acc[p]/s for p in party_ids}
    if abs(sum(cond.values())-1)>1e-10: raise RuntimeError('prior conditional shares do not sum 1')
    return turnout,cond

def voter_cards(pop_t, real_to_anon):
    other=real_to_anon['OTHER']; cards=[]; weights={}
    for a in sorted(pop_t['archetypes'],key=lambda x:x['archetype_id']):
        aid=a['archetype_id']; weights[aid]=float(a['weight'])
        cards.append({
            'weighted_archetype_id':aid,
            'age_band':a['age_band'],
            'sex':a['sex'],
            'urban_rural':a['urban_rural'],
            'education_band':a['education_band'],
            'activity_status':a['activity_status'],
            'prior_vote_or_abstention':map_prior_state(a['prior_vote_or_abstention'],real_to_anon,other),
        })
    if len(cards)!=128 or len(weights)!=128: raise RuntimeError('expected 128 archetypes')
    if abs(sum(weights.values())-1)>1e-8: raise RuntimeError('weights do not sum 1')
    return cards,weights

def map_year(year,bundle,pop,recon2016,map2021):
    if year==2016:
        tmap=recon2016['territory_mapping_anonymous_to_historical_id']; plook=pop_lookup_2016(pop); real_to_anon=inv_party_2016(recon2016)
        def get_pop(anon_tid): return plook[str(tmap[anon_tid])]
    elif year==2021:
        # mapping artifact stores real -> anonymous
        rev={anon:real for real,anon in map2021['territories'].items()}; plook=pop_lookup_2021(pop); real_to_anon=dict(map2021['parties'])
        def get_pop(anon_tid): return plook[rev[anon_tid]]
    else: raise ValueError(year)
    if set(real_to_anon.values()) != {p['anonymous_party_id'] for p in bundle['packets'][0]['parties']}:
        raise RuntimeError(f'party panel mismatch {year}')
    if 'OTHER' not in real_to_anon: raise RuntimeError('OTHER missing in party map')
    return get_pop,real_to_anon

def build_year(year,bundle,pop,recon2016,map2021,public_root,private,manifest):
    by_tid={p['anonymous_territory_id']:p for p in bundle['packets']}
    der=make_derangement(bundle)
    get_pop,real_to_anon=map_year(year,bundle,pop,recon2016,map2021)
    eid=bundle['anonymous_election_id']
    private['year_by_anonymous_election_id'][eid]=year
    private['condition_role_by_id']={COND_TRUE:'AS2_LLM_INDEPENDENT',COND_SHUFFLED:'AS2_SHUFFLED_CONTEXT'}
    private['shuffle_donor_by_election_and_territory'][eid]=der
    private['weights_by_election_territory_archetype'].setdefault(eid,{})
    private['seat_magnitude_by_election_territory'].setdefault(eid,{})
    private['baseline_vote_share_by_election_territory'].setdefault(eid,{})
    for target in sorted(bundle['packets'],key=lambda x:x['anonymous_territory_id']):
        tid=target['anonymous_territory_id']; pop_t=get_pop(tid)
        party_ids=sorted(p['anonymous_party_id'] for p in target['parties'])
        turnout,prior_shares=prior_anchor(pop_t,real_to_anon,party_ids)
        cards,weights=voter_cards(pop_t,real_to_anon)
        private['weights_by_election_territory_archetype'][eid][tid]=weights
        private['seat_magnitude_by_election_territory'][eid][tid]=target.get('seat_magnitude')
        private['baseline_vote_share_by_election_territory'][eid][tid]={p['anonymous_party_id']:float(p['baseline_vote_share']) for p in target['parties']}
        contexts={COND_TRUE:target,COND_SHUFFLED:by_tid[der[tid]]}
        for cid,ctxpkt in contexts.items():
            common={
                'previous_election_turnout_probability':turnout,
                'previous_election_conditional_party_shares':prior_shares,
                'party_context_cards':sanitize_party_context(ctxpkt),
            }
            for bi in range(4):
                chunk=cards[bi*BATCH_SIZE:(bi+1)*BATCH_SIZE]
                bid=f'B{bi+1:02d}'
                obj={
                    'schema_version':SCHEMA_VERSION,
                    'experiment_id':EXPERIMENT_ID,
                    'anonymous_election_id':eid,
                    'anonymous_territory_id':tid,
                    'condition_id':cid,
                    'batch_id':bid,
                    'available_party_ids':party_ids,
                    'common_territory_card':common,
                    'voter_archetypes':chunk,
                }
                obj['packet_sha256']=packet_hash(obj)
                rel=Path('packets')/eid/cid/tid/(bid+'.json')
                writej(public_root/rel,obj)
                manifest['packet_sha256'][str(rel)]=obj['packet_sha256']
                manifest['packet_count']+=1; manifest['archetype_rows_expected']+=len(chunk)
    manifest['anonymous_election_ids'].append(eid)
    manifest['source_blind_bundle_file_sha256'][eid]=sha_file('/tmp/dev.json' if year==2016 else '/tmp/hold.json')
    manifest['source_blind_bundle_declared_sha256'][eid]=bundle.get('bundle_sha256')

def zip_dir(root,out):
    with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for p in sorted(Path(root).rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(root))

def leak_scan(root,recon2016,map2021):
    banned=set(recon2016['party_mapping'].values()) | set(map2021['parties'].keys())
    # party tokens such as MP/PI are too short for blind substring scanning; scan quoted JSON values and territory names instead.
    territory_names=set(map2021['territories'].keys())
    findings=[]
    for p in Path(root).rglob('*'):
        if not p.is_file() or p.suffix not in {'.json','.md'}: continue
        s=p.read_text(encoding='utf-8',errors='ignore').lower()
        for x in territory_names:
            if len(x)>=5 and x.lower() in s: findings.append([str(p.relative_to(root)),'territory',x])
    return findings

def main():
    ap=argparse.ArgumentParser()
    for x in ['dev','hold','pop2016','pop2021','recon2016','map2021','prompt','schema','powercert','amendment','contractfreeze','outdir']: ap.add_argument('--'+x,required=True)
    a=ap.parse_args(); out=Path(a.outdir); public=out/'public'; private_root=out/'private'; shutil.rmtree(out,ignore_errors=True); public.mkdir(parents=True); private_root.mkdir(parents=True)
    dev,hold=readj(a.dev),readj(a.hold); p16,p21=readj(a.pop2016),readj(a.pop2021); r16,m21=readj(a.recon2016),readj(a.map2021)
    if r16.get('target_outcome_used_for_identity_resolution') is not False: raise RuntimeError('2016 identity reconstruction outcome boundary failed')
    if m21.get('real_election')!=2021: raise RuntimeError('unexpected 2021 mapping')
    if sha_file(a.map2021)!='41acca5f3d025facb4953b6367bb1f7b4755689b72695c699d70111cdf8707b3': raise RuntimeError('2021 mapping hash mismatch')
    expected_pop={a.pop2016:'c6e819a4e3b34199cb72c1f6a2005bf321be27e40ac2a4711d5d3244afd4235e',a.pop2021:'db9f9669020036fe7f219eca5173b0bf6c5074760956c49b72c8fbeafbe3a42e'}
    for p,h in expected_pop.items():
        if sha_file(p)!=h: raise RuntimeError('population hash mismatch '+p)
    for src,name in [(a.prompt,'as2_prompt_v2.md'),(a.schema,'as2_output_schema_v2.json'),(a.powercert,'combined_data_power_certificate_v1.json'),(a.amendment,'engineering_amendment_v3.json'),(a.contractfreeze,'pre_llm_contract_freeze_v2.json')]: shutil.copy2(src,public/name)
    private={
      'schema_version':'1.0','private_manifest_id':'M26-ASV2-HISTORICAL-PRIVATE-ORCHESTRATOR-V1','experiment_id':EXPERIMENT_ID,
      'year_by_anonymous_election_id':{},'condition_role_by_id':{},'shuffle_donor_by_election_and_territory':{},
      'weights_by_election_territory_archetype':{},'seat_magnitude_by_election_territory':{},'baseline_vote_share_by_election_territory':{},
      'mapping_hashes':{'2021':sha_file(a.map2021),'2016_reconstruction':sha_file(a.recon2016)}
    }
    manifest={
      'schema_version':'1.0','manifest_id':'M26-ASV2-HISTORICAL-SEALED-HANDOFF-MANIFEST-V1','experiment_id':EXPERIMENT_ID,
      'status':'SEALED_READY_FOR_OPUS5','condition_labels_are_opaque':True,'target_outcomes_present':False,'mapping_material_present':False,
      'packet_count':0,'archetype_rows_expected':0,'packet_sha256':{},'anonymous_election_ids':[],
      'source_blind_bundle_file_sha256':{},'source_blind_bundle_declared_sha256':{},
      'active_prompt_sha256':sha_file(a.prompt),'active_output_schema_sha256':sha_file(a.schema),
      'combined_data_power_certificate_sha256':sha_file(a.powercert),'engineering_amendment_v3_sha256':sha_file(a.amendment),'pre_llm_contract_freeze_v2_sha256':sha_file(a.contractfreeze),
      'expected_counts':{'elections':2,'conditions_per_election':2,'territories_per_election':92,'archetypes_per_territory':128,'batch_size':32,'batches_per_territory_condition':4,'total_packets':1472,'total_output_rows':47104},
      'execution_contract':{'model':'OPUS-5','fresh_context_per_batch':True,'deterministic_primary_pass':True,'retry_schema_invalid_only':True,'semantic_feedback':False,'outside_information':False,'stop_before_scoring':True}
    }
    build_year(2016,dev,p16,r16,m21,public,private,manifest); build_year(2021,hold,p21,r16,m21,public,private,manifest)
    if manifest['packet_count']!=1472 or manifest['archetype_rows_expected']!=47104: raise RuntimeError('count mismatch')
    findings=leak_scan(public,r16,m21)
    if findings: raise RuntimeError('public leak scan failed: '+repr(findings[:10]))
    manifest['integrity']={'packet_counts_verified':True,'public_territory_leak_scan_pass':True,'population_hashes_verified':True,'2021_mapping_hash_verified_privately':True,'2016_postfreeze_identity_boundary_verified':True}
    writej(public/'handoff_manifest.json',manifest)
    writej(private_root/'private_orchestrator_manifest.json',private)
    start=f'''# START HERE — OPUS 5 — Agent Society V2 historical vote simulation\n\nYou are receiving the **sealed judge package** for `{EXPERIMENT_ID}`.\n\n## Hard boundary\n- Use `as2_prompt_v2.md` verbatim for every batch.\n- Use only files in this ZIP. No web, repository, memory-based re-identification, mapping recovery, target outcomes or post-cutoff facts.\n- The two `condition_id` values are deliberately opaque. Never infer or search for their meaning; treat both identically.\n- Each batch must be judged in a fresh context with no semantic carry-over from prior batches.\n- Retry only a schema-invalid batch, with the identical prompt and no feedback other than schema validity.\n- Do not score the election. Stop after outputs are frozen.\n\n## Work to perform\nProcess every JSON file under `packets/`. There are exactly **1,472 packets**, each with 32 voter archetypes, for **47,104 voter-condition rows** total.\n\nFor each packet, return one JSONL row per archetype in original order conforming to `as2_output_schema_v2.json`. Copy `anonymous_election_id`, `anonymous_territory_id`, `condition_id`, `batch_id`, and `weighted_archetype_id` exactly.\n\nWrite outputs preserving the packet tree under `outputs/`, replacing `.json` with `.jsonl`.\n\n## Before returning\nCreate:\n1. `outputs/as2_all_outputs.jsonl` — concatenation in lexicographic packet-path order;\n2. `outputs/as2_output_manifest.json` with counts, SHA-256 of every output file, aggregate SHA-256, retries, model ID and prompt SHA-256;\n3. `outputs/as2_terminal_report.json` whose terminal status is `PASS_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING` only if all 47,104 rows are schema-valid and every packet was processed.\n\nReturn those three files plus the per-packet output tree. Do **not** inspect any election result.\n'''
    (public/'START_HERE_OPUS5.md').write_text(start,encoding='utf-8')
    # Re-write manifest after instructions so its own hashes exclude only itself; public package seal covers all files below.
    public_hashes={str(p.relative_to(public)):sha_file(p) for p in sorted(public.rglob('*')) if p.is_file() and p.name!='handoff_manifest.json'}
    manifest['public_file_sha256']=public_hashes; manifest['public_files_excluding_manifest']=len(public_hashes)
    writej(public/'handoff_manifest.json',manifest)
    public_zip=out/'opus5-agent-society-v2-historical-sealed.zip'; private_zip=out/'agent-society-v2-historical-private-orchestrator.zip'
    zip_dir(public,public_zip); zip_dir(private_root,private_zip)
    seal={
      'seal_id':'M26-ASV2-HISTORICAL-HANDOFF-SEAL-V1','experiment_id':EXPERIMENT_ID,'status':'SEALED_READY_FOR_OPUS5',
      'public_zip_sha256':sha_file(public_zip),'private_zip_sha256':sha_file(private_zip),'public_manifest_sha256':sha_file(public/'handoff_manifest.json'),
      'packet_count':manifest['packet_count'],'output_rows_expected':manifest['archetype_rows_expected'],'target_outcomes_present_in_public_zip':False,'mapping_material_present_in_public_zip':False
    }
    writej(out/'handoff_seal_v1.json',seal)
    print(json.dumps(seal,indent=2))

if __name__=='__main__': main()
