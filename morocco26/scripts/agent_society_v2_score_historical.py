#!/usr/bin/env python3
from __future__ import annotations

import argparse, hashlib, io, json, math, random, statistics, tempfile, zipfile
from collections import defaultdict
from pathlib import Path

EXPECTED_ROWS=47104
EXPECTED_PACKETS=1472
BOOTSTRAP_REPS=10000
BOOTSTRAP_SEED=260818
REQUIRED_HANDOFF_SHA='9798dcb7c9b227322eb6b8158d4929e5536b8e0c4e41dc890d9b4cfeec063209'
REQUIRED_MANIFEST_SHA='fc019dabf0bb0a24302a119948fa68d06f6841608d748d31a500aa503283a92e'
PASS_TERMINAL='PASS_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING'


def sha_bytes(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def sha_file(p)->str:return sha_bytes(Path(p).read_bytes())
def readj(p):return json.loads(Path(p).read_text(encoding='utf-8'))
def writej(p,obj):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(obj,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')

def canon(obj):return json.dumps(obj,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')

def find_member_recursive(zip_path:Path,suffix:str):
    """Return bytes for the unique member whose path ends with suffix, searching one nested-zip level."""
    with zipfile.ZipFile(zip_path,'r') as z:
        hits=[n for n in z.namelist() if n.endswith(suffix)]
        if len(hits)==1:return z.read(hits[0])
        nested=[]
        for n in z.namelist():
            if n.lower().endswith('.zip'):
                try:
                    with zipfile.ZipFile(io.BytesIO(z.read(n)),'r') as nz:
                        hh=[m for m in nz.namelist() if m.endswith(suffix)]
                        for m in hh:nested.append(nz.read(m))
                except zipfile.BadZipFile:pass
        if len(nested)==1:return nested[0]
    raise RuntimeError(f'expected exactly one {suffix} in {zip_path}')

def load_json_member(zip_path,suffix):return json.loads(find_member_recursive(Path(zip_path),suffix))
def load_jsonl_member(zip_path,suffix):
    raw=find_member_recursive(Path(zip_path),suffix).decode('utf-8')
    return [json.loads(x) for x in raw.splitlines() if x.strip()]

def load_public_contract(public_zip:Path):
    if sha_file(public_zip)!=REQUIRED_HANDOFF_SHA:raise RuntimeError('public handoff SHA mismatch')
    with zipfile.ZipFile(public_zip,'r') as z:
        manifest=json.loads(z.read('handoff_manifest.json'))
        if sha_bytes(z.read('handoff_manifest.json'))!=REQUIRED_MANIFEST_SHA:raise RuntimeError('public manifest SHA mismatch')
        packet_names=sorted(n for n in z.namelist() if n.startswith('packets/') and n.endswith('.json'))
        if len(packet_names)!=EXPECTED_PACKETS:raise RuntimeError('public packet count mismatch')
        expected={}; prior={}; party_panel={}
        for n in packet_names:
            p=json.loads(z.read(n)); eid=p['anonymous_election_id'];tid=p['anonymous_territory_id'];cid=p['condition_id'];bid=p['batch_id']
            parties=tuple(sorted(p['available_party_ids']))
            key=(eid,tid)
            party_panel.setdefault(key,parties)
            if party_panel[key]!=parties:raise RuntimeError('party panel drift')
            pa=p['common_territory_card']['previous_election_conditional_party_shares']
            pt=float(p['common_territory_card']['previous_election_turnout_probability'])
            if abs(sum(float(pa[q]) for q in parties)-1)>1e-9:raise RuntimeError('prior simplex invalid')
            prior.setdefault(key,{'turnout':pt,'shares':{q:float(pa[q]) for q in parties}})
            for a in p['voter_archetypes']:
                t=(eid,tid,cid,bid,a['weighted_archetype_id'])
                if t in expected:raise RuntimeError('duplicate expected voter row')
                expected[t]=parties
        if len(expected)!=EXPECTED_ROWS:raise RuntimeError('expected voter-row count mismatch')
    return manifest,expected,prior,party_panel

def validate_outputs(opus_zip:Path,expected):
    terminal=load_json_member(opus_zip,'as2_terminal_report.json')
    manifest=load_json_member(opus_zip,'as2_output_manifest.json')
    rows=load_jsonl_member(opus_zip,'as2_all_outputs.jsonl')
    invalid=[];valid={}
    allowed_reasons={
      'PRIOR_VOTE_INERTIA','PRIOR_ABSTENTION_INERTIA','TURNOUT_TRANSITION','DEMOGRAPHIC_LATENT_PRIOR','INCUMBENCY','PARTY_SWITCH',
      'LOCAL_OR_REGIONAL_OFFICE','PARTY_OR_NATIONAL_OFFICE','FORMER_MP_OR_MINISTER','ENDORSEMENT_OR_ALLIANCE',
      'WITHDRAWAL_SANCTION_OR_INCAPACITY','OTHER_VERIFIED_CONTEXT','NO_DIRECTIONAL_EVIDENCE'}
    for i,r in enumerate(rows,1):
        try:
            t=(r['anonymous_election_id'],r['anonymous_territory_id'],r['condition_id'],r['batch_id'],r['weighted_archetype_id'])
            if t not in expected:raise ValueError('unexpected identifier tuple')
            if t in valid:raise ValueError('duplicate identifier tuple')
            u=float(r['turnout_probability'])
            if not math.isfinite(u) or not 0<=u<=1:raise ValueError('turnout outside [0,1]')
            probs=r['conditional_party_probabilities']; exp=set(expected[t])
            if set(probs)!=exp:raise ValueError('party simplex keys mismatch')
            vals=[float(probs[p]) for p in expected[t]]
            if any((not math.isfinite(x) or x<0 or x>1) for x in vals):raise ValueError('party probability invalid')
            if abs(sum(vals)-1)>1e-9:raise ValueError('party simplex sum mismatch')
            reasons=r['reason_codes']
            if not isinstance(reasons,list) or not 1<=len(reasons)<=3 or len(set(reasons))!=len(reasons) or any(x not in allowed_reasons for x in reasons):raise ValueError('reason_codes invalid')
            valid[t]={'turnout':u,'probs':{p:float(probs[p]) for p in expected[t]}}
        except Exception as e:invalid.append({'line':i,'error':type(e).__name__+':'+str(e)})
    missing=len(set(expected)-set(valid)); extra_count=max(0,len(rows)-len(valid))
    rate=len(valid)/EXPECTED_ROWS
    terminal_ok=terminal.get('terminal_status')==PASS_TERMINAL
    manifest_count=manifest.get('output_rows') or manifest.get('rows_total') or manifest.get('outputs_total') or manifest.get('archetype_rows')
    full=(len(rows)==EXPECTED_ROWS and len(valid)==EXPECTED_ROWS and not invalid and missing==0 and terminal_ok)
    return {'terminal':terminal,'manifest':manifest,'rows_raw':len(rows),'valid_rows':len(valid),'invalid_rows':invalid[:100],'missing_expected_rows':missing,'extra_or_duplicate_rows':extra_count,'validity_rate':rate,'terminal_ok':terminal_ok,'full_contract_pass':full},valid

def private_manifest(private_zip):return load_json_member(Path(private_zip),'private_orchestrator_manifest.json')

def aggregate(valid,priv,prior,party_panel):
    accum={}
    group=defaultdict(list)
    for t,v in valid.items():group[t[:3]].append((t[4],v))
    for (eid,tid,cid),items in group.items():
        weights=priv['weights_by_election_territory_archetype'][eid][tid]
        parties=party_panel[(eid,tid)]
        if len(items)!=128:raise RuntimeError('cannot aggregate incomplete territory-condition')
        tu=0.0;mass={p:0.0 for p in parties};seen=set()
        for aid,v in items:
            if aid in seen:raise RuntimeError('duplicate archetype aggregate');seen.add(aid)
            w=float(weights[aid]);u=v['turnout'];tu+=w*u
            for p in parties:mass[p]+=w*u*v['probs'][p]
        den=sum(mass.values())
        if den<=0:raise RuntimeError('zero predicted turnout mass')
        accum[(eid,tid,cid)]={'turnout':tu,'shares':{p:mass[p]/den for p in parties}}
    pred={'C0':{},'AS1':{},'AS2_TRUE':{},'AS2_SHUFFLED':{}}
    true_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='AS2_LLM_INDEPENDENT')
    shuf_cid=next(k for k,v in priv['condition_role_by_id'].items() if v=='AS2_SHUFFLED_CONTEXT')
    for eid,year in priv['year_by_anonymous_election_id'].items():
        for tid,base in priv['baseline_vote_share_by_election_territory'][eid].items():
            k=(eid,tid); parties=party_panel[k]
            b={p:float(base[p]) for p in parties};sb=sum(b.values())
            if abs(sb-1)>1e-6:raise RuntimeError('C0 baseline not normalized')
            pred['C0'][k]={'shares':b}
            pred['AS1'][k]=prior[k]
            pred['AS2_TRUE'][k]=accum[(eid,tid,true_cid)]
            pred['AS2_SHUFFLED'][k]=accum[(eid,tid,shuf_cid)]
    return pred

def outcome_maps(out16,out21,recon16,map21,pop21,priv):
    o16={str(r['id_constituency']):r for r in out16['rows'] if r.get('list_type')=='locale'}
    o21={str(r['id_constituency']):r for r in out21['rows'] if r.get('list_type')=='locale'}
    if len(o16)!=92 or len(o21)!=92:raise RuntimeError('canonical outcome territory count !=92')
    eid16=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2016)
    eid21=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==2021)
    tid16={anon:str(realid) for anon,realid in recon16['territory_mapping_anonymous_to_historical_id'].items()}
    real_to_anon16={real:anon for anon,real in recon16['party_mapping'].items()}
    slug_to_id={t['constituency_id']:str(t['prior_historical_match']['id_constituency']) for t in pop21['territories']}
    tid21={anon:slug_to_id[slug] for slug,anon in map21['territories'].items()}
    real_to_anon21=dict(map21['parties'])
    def build(eid,tid_map,party_map,rows):
        other=party_map['OTHER'];res={}
        for anon_tid,rid in tid_map.items():
            row=rows[rid];acc={p:0.0 for p in set(party_map.values())}
            for real,v in row['votes'].items():acc[party_map.get(real,other)]+=float(v)
            total=sum(acc.values())
            if total<=0:raise RuntimeError('zero target party mass')
            shares={p:acc[p]/total for p in sorted(acc)}
            res[(eid,anon_tid)]={'shares':shares,'turnout_rate_reported':row.get('turnout_rate_reported'),'id_constituency':rid}
        if len(res)!=92:raise RuntimeError('mapped target territory count !=92')
        return res
    res={};res.update(build(eid16,tid16,real_to_anon16,o16));res.update(build(eid21,tid21,real_to_anon21,o21));return res

def year_keys(priv,year):
    eid=next(e for e,y in priv['year_by_anonymous_election_id'].items() if int(y)==year)
    return sorted((eid,tid) for tid in priv['baseline_vote_share_by_election_territory'][eid])

def metric(pred,obs,keys):
    sq=[];l1=[];correct=0;territory_mse=[]
    for k in keys:
        parties=sorted(obs[k]['shares'])
        dif=[float(pred[k]['shares'][p])-float(obs[k]['shares'][p]) for p in parties]
        sq.extend(d*d for d in dif);territory_mse.append(sum(d*d for d in dif)/len(dif));l1.append(sum(abs(d) for d in dif))
        pp=max(parties,key=lambda p:(pred[k]['shares'][p],-parties.index(p)))
        oo=max(parties,key=lambda p:(obs[k]['shares'][p],-parties.index(p)))
        correct+=pp==oo
    return {'macro_party_share_RMSE':math.sqrt(sum(sq)/len(sq)),'mean_constituency_L1':sum(l1)/len(l1),'top_party_accuracy':correct/len(keys),'territory_mse':territory_mse}

def paired_bootstrap(mt,mc):
    if len(mt)!=len(mc):raise RuntimeError('bootstrap length mismatch')
    rng=random.Random(BOOTSTRAP_SEED);d=[];better=0;n=len(mt)
    for _ in range(BOOTSTRAP_REPS):
        idx=[rng.randrange(n) for _ in range(n)]
        rt=math.sqrt(sum(mt[i] for i in idx)/n);rc=math.sqrt(sum(mc[i] for i in idx)/n);x=rt-rc;d.append(x);better+=x<0
    d.sort();lo=d[int(.025*len(d))];hi=d[min(len(d)-1,int(.975*len(d)))]
    return {'replicates':BOOTSTRAP_REPS,'seed':BOOTSTRAP_SEED,'probability_treatment_better':better/BOOTSTRAP_REPS,'percentile_95_interval_delta_RMSE':[lo,hi]}

def main():
    ap=argparse.ArgumentParser()
    for x in ['opuszip','publiczip','privatezip','outcome2016','outcome2021','recon2016','map2021','pop2021','contract','outdir']:ap.add_argument('--'+x,required=True)
    a=ap.parse_args();outdir=Path(a.outdir);outdir.mkdir(parents=True,exist_ok=True)
    contract=readj(a.contract)
    if contract['status']!='FROZEN_BEFORE_ANY_REAL_ASV2_LLM_OUTPUT_IS_INSPECTED':raise RuntimeError('scoring contract not frozen')
    manifest,expected,prior,party_panel=load_public_contract(Path(a.publiczip));validity,valid=validate_outputs(Path(a.opuszip),expected)
    result={'schema_version':'1.0','result_id':'M26-ASV2-HISTORICAL-SCORE-V1','experiment_id':'M26-AGENT-SOCIETY-V2-001','scoring_contract_sha256':sha_file(a.contract),'public_handoff_sha256':sha_file(a.publiczip),'opus_output_zip_sha256':sha_file(a.opuszip),'contract_validity':validity,'historical_role':'RETROSPECTIVE_SANITY_FILTER_ONLY_NOT_PRISTINE_PROOF','severe_2016_warning':'Formal context density passed, but zero 2016 districts had at least two cross-party discriminative context families.'}
    if not validity['full_contract_pass']:
        result['terminal_state']='ASV2_KILL_BEFORE_2026';result['gates']={'gate_1_contract':False};writej(outdir/'historical_score_v1.json',result);print(json.dumps(result,indent=2));return
    priv=private_manifest(a.privatezip)
    pred=aggregate(valid,priv,prior,party_panel)
    obs=outcome_maps(readj(a.outcome2016),readj(a.outcome2021),readj(a.recon2016),readj(a.map2021),readj(a.pop2021),priv)
    metrics={};boots={}
    for year in [2016,2021]:
        keys=year_keys(priv,year);metrics[str(year)]={}
        detailed={}
        for arm in ['C0','AS1','AS2_TRUE','AS2_SHUFFLED']:
            m=metric(pred[arm],obs,keys);detailed[arm]=m;metrics[str(year)][arm]={k:v for k,v in m.items() if k!='territory_mse'}
        for t,c in [('AS2_TRUE','C0'),('AS2_TRUE','AS2_SHUFFLED'),('AS1','C0')]:
            boots[f'{year}:{t}_VS_{c}']=paired_bootstrap(detailed[t]['territory_mse'],detailed[c]['territory_mse'])
    r16=metrics['2016'];r21=metrics['2021']
    imp16=(r16['C0']['macro_party_share_RMSE']-r16['AS2_TRUE']['macro_party_share_RMSE'])/r16['C0']['macro_party_share_RMSE']
    imp21=(r21['C0']['macro_party_share_RMSE']-r21['AS2_TRUE']['macro_party_share_RMSE'])/r21['C0']['macro_party_share_RMSE']
    gates={
      'gate_1_contract':validity['validity_rate']>=.99 and validity['terminal_ok'] and validity['full_contract_pass'],
      'gate_2_not_materially_worse_2016':r16['AS2_TRUE']['macro_party_share_RMSE']<=1.01*r16['C0']['macro_party_share_RMSE'],
      'gate_3_not_materially_worse_2021':r21['AS2_TRUE']['macro_party_share_RMSE']<=1.01*r21['C0']['macro_party_share_RMSE'],
      'gate_4_positive_signal':max(imp16,imp21)>=.01,
      'gate_5_negative_control_2016':r16['AS2_TRUE']['macro_party_share_RMSE']<=r16['AS2_SHUFFLED']['macro_party_share_RMSE'],
      'gate_6_negative_control_2021':r21['AS2_TRUE']['macro_party_share_RMSE']<=r21['AS2_SHUFFLED']['macro_party_share_RMSE'],
    }
    result.update({'metrics':metrics,'relative_improvement_AS2_TRUE_vs_C0':{'2016':imp16,'2021':imp21},'paired_bootstrap':boots,'gates':gates,'all_six_gates_pass':all(gates.values()),'terminal_state':'ASV2_HISTORICAL_SANITY_PASS_READY_FOR_2026_FREEZE' if all(gates.values()) else 'ASV2_KILL_BEFORE_2026'})
    writej(outdir/'historical_score_v1.json',result)
    cert={'schema_version':'1.0','certificate_id':'M26-ASV2-HISTORICAL-TERMINAL-CERTIFICATE-V1','experiment_id':result['experiment_id'],'historical_score_sha256':sha_file(outdir/'historical_score_v1.json'),'terminal_state':result['terminal_state'],'all_six_gates_pass':result.get('all_six_gates_pass',False),'severe_2016_warning':result['severe_2016_warning'],'next_allowed_action':'FREEZE_PROSPECTIVE_2026_AS2' if result['terminal_state'].endswith('READY_FOR_2026_FREEZE') else 'STOP_ASV2_DO_NOT_RUN_AS3_OR_2026'}
    writej(outdir/'historical_terminal_certificate_v1.json',cert);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
