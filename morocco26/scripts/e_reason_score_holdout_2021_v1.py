#!/usr/bin/env python3
from __future__ import annotations
import hashlib, importlib.util, json, os
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
E=ROOT/'data/goal100/e_reason'; H=ROOT/'data/goal100/historical'
MAPPING=Path(os.environ['MAPPING_PATH'])
OUT=Path(os.environ.get('E_REASON_SCORE_OUTPUT','/tmp/e_reason_score_v1.json'))

def read_json(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha_file(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

spec=importlib.util.spec_from_file_location('holdout_builder',ROOT/'scripts/e_reason_build_blind_holdout_bundle.py')
hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=hb.PARTIES; CORE=hb.CORE
scoring=read_json(E/'e_reason_scoring_contract_v1.json')
promotion=read_json(E/'e_reason_promotion_criteria_v1.json')
freeze=read_json(E/'lambda_freeze_v1.json')
receipt=read_json(E/'judgments/holdout/c2_opus5/preunseal_receipt.json')
bundle=read_json(E/'blind/holdout/blind_bundle.json')
bmanifest=read_json(E/'blind/holdout/bundle_manifest.json')
c1manifest=read_json(E/'judgments/holdout/c1_rule_only/c1_judgment_manifest.json')
mapping=read_json(MAPPING)
assert scoring['primary_metric']['name']=='macro_party_share_RMSE'
assert scoring['uncertainty_test']=={'method':'paired bootstrap by constituency','replicates':10000,'seed':260817,'statistic':'difference in primary RMSE','reported':['point_delta','relative_delta','bootstrap_probability_treatment_better','percentile_95_interval']}
assert freeze['status']=='FROZEN_BEFORE_2021_JUDGMENTS' and float(freeze['lambda_C1'])==float(freeze['lambda_C2'])==0.3
assert receipt['status']=='PASS_C2_HOLDOUT_FROZEN_READY_FOR_OUTCOME_UNSEAL' and receipt['recorded_before_outcome_unseal'] is True
assert receipt['integrity']['c2_judgments_file_sha256']=='03b630c5a6c07ca32443a4fc3ba43ff30cb08d32c0f7634e78a34752f8e06446'
assert bundle['bundle_sha256']==bmanifest['bundle_sha256']==receipt['bundle_sha256']==c1manifest['bundle_sha256']
assert mapping['real_election']==2021 and mapping['anonymous_election_id']==bundle['anonymous_election_id']
assert sha_file(MAPPING)==bmanifest['mapping_sha256']

consts=hb.load_constituencies(); order=[c['constituency_id'] for c in consts]
y21raw=read_json(H/'tafra_legislative_2021_canonical.json')
y21rows=[r for r in y21raw['rows'] if str(r.get('list_type','')).lower() in {'locale','local'}]
assert len(y21rows)==92
m21=hb.match_rows(consts,y21rows)

def obs_share(row):
    raw=row.get('votes',{}); total=sum(float(v or 0) for v in raw.values()); assert total>0
    d={p:float(raw.get(p,0) or 0)/total for p in CORE}
    d['OTHER']=sum(float(v or 0) for k,v in raw.items() if k not in CORE)/total
    return np.array([d[p] for p in PARTIES],float)

c1=[json.loads(s) for s in (E/'judgments/holdout/c1_rule_only/c1_judgments.jsonl').read_text().splitlines() if s.strip()]
assert len(c1)==92
c1_by={x['anonymous_territory_id']:x for x in c1}; pkt_by={x['anonymous_territory_id']:x for x in bundle['packets']}
preds={k:{} for k in ('C0','C1','C2')}; obs={}; audit={'c1':{'0':0,'1':0,'2':0},'c2':{'0':0,'1':0,'2':0},'different_cells':0}
z_by_cid={}
for c in consts:
    cid=c['constituency_id']; tid=mapping['territories'][cid]; pkt=pkt_by[tid]
    parties={x['anonymous_party_id']:x for x in pkt['parties']}; js={j['anonymous_party_id']:j for j in c1_by[tid]['judgments']}
    base=np.zeros(9); z1=np.zeros(9)
    for i,p in enumerate(PARTIES):
        aid=mapping['parties'][p]; base[i]=float(parties[aid]['baseline_vote_share']); z1[i]=float(js[aid]['ordinal_score'])
        audit['c1'][str(int(z1[i]))]=audit['c1'].get(str(int(z1[i])),0)+1
    z2=(z1>0).astype(float)
    for v in z2: audit['c2'][str(int(v))]=audit['c2'].get(str(int(v)),0)+1
    audit['different_cells']+=int(np.sum(z1!=z2)); z_by_cid[cid]=(z1,z2)
    def adj(z,lam):
        cen=z-z.mean(); a=base*np.exp(float(lam)*cen); return a/a.sum()
    preds['C0'][cid]=base; preds['C1'][cid]=adj(z1,0.3); preds['C2'][cid]=adj(z2,0.3); obs[cid]=obs_share(m21[cid])
assert audit=={'c1':{'0':769,'1':12,'2':47},'c2':{'0':769,'1':59,'2':0},'different_cells':47}

def metrics(P):
    e=[]; l1=[]; top=[]; mse=[]
    for cid in order:
        d=P[cid]-obs[cid]; e.extend(d.tolist()); l1.append(float(np.abs(d).sum())); top.append(int(np.argmax(P[cid])==np.argmax(obs[cid]))); mse.append(float(np.mean(d*d)))
    return {'macro_party_share_RMSE':float(np.sqrt(np.mean(np.square(e)))),'mean_constituency_L1':float(np.mean(l1)),'top_party_accuracy':float(np.mean(top)),'mse':mse}
met={k:metrics(v) for k,v in preds.items()}
rng=np.random.default_rng(260817); idx=rng.integers(0,92,size=(10000,92)); sq={k:np.array(v['mse']) for k,v in met.items()}; br={k:np.sqrt(sq[k][idx].mean(axis=1)) for k in sq}
def cmp(t,c):
    delta=br[t]-br[c]; point=met[t]['macro_party_share_RMSE']-met[c]['macro_party_share_RMSE']; rel=(met[c]['macro_party_share_RMSE']-met[t]['macro_party_share_RMSE'])/met[c]['macro_party_share_RMSE']
    return {'treatment':t,'control':c,'point_delta_RMSE_treatment_minus_control':float(point),'relative_improvement':float(rel),'bootstrap_probability_treatment_better':float(np.mean(delta<0)),'percentile_95_interval_delta':[float(np.quantile(delta,.025)),float(np.quantile(delta,.975))]}
comps={'C1_MINUS_C0':cmp('C1','C0'),'C2_MINUS_C0':cmp('C2','C0'),'C2_MINUS_C1':cmp('C2','C1')}

# Recreate frozen Bstar V0 uncertainty draws exactly, then apply the same residual transform drawwise.
rows11=hb.load_local(2011); rows16=hb.load_local(2016); m11=hb.match_rows(consts,rows11); m16=hb.match_rows(consts,rows16)
shift={cid:hb.centre_clr(hb.clr(m16[cid])-hb.clr(m11[cid])) for cid in order}; residuals=np.stack([shift[cid] for cid in sorted(order)]); residuals=hb.centre_clr(residuals-residuals.mean(axis=0,keepdims=True))
erng=np.random.default_rng(hb.SEED); di1=erng.integers(0,92,size=hb.N_SAMPLES); di2=erng.integers(0,92,size=hb.N_SAMPLES)
def energy(a,y,b):
    aa=np.sqrt(np.clip(a,0,1)); bb=np.sqrt(np.clip(b,0,1)); yy=np.sqrt(np.clip(y,0,1)); return float(np.linalg.norm(aa-yy,axis=1).mean()-.5*np.linalg.norm(aa-bb,axis=1).mean())
escores={k:[] for k in preds}; mean_match=0.0
for cid in order:
    z1,z2=z_by_cid[cid]; pz=hb.centre_clr(hb.clr(m16[cid])); s1=hb.inv_clr(pz+residuals[di1]); s2=hb.inv_clr(pz+residuals[di2]); mean_match=max(mean_match,float(np.max(np.abs(s1.mean(axis=0)-preds['C0'][cid]))))
    for k,z,lam in [('C0',np.zeros(9),0.0),('C1',z1,0.3),('C2',z2,0.3)]:
        fac=np.exp(lam*(z-z.mean())); a=s1*fac; a/=a.sum(axis=1,keepdims=True); b=s2*fac; b/=b.sum(axis=1,keepdims=True); escores[k].append(energy(a,obs[cid],b))
assert mean_match<2e-10,mean_match
prob={k:{'mean_energy_score':float(np.mean(v))} for k,v in escores.items()}; prob['C2']['relative_degradation_vs_C0']=(prob['C2']['mean_energy_score']-prob['C0']['mean_energy_score'])/prob['C0']['mean_energy_score']; prob['C2']['relative_degradation_vs_C1']=(prob['C2']['mean_energy_score']-prob['C1']['mean_energy_score'])/prob['C1']['mean_energy_score']

g=promotion['predictive_gates_for_C2']; gates={'vs_C0_relative_improvement_pass':comps['C2_MINUS_C0']['relative_improvement']>=g['vs_C0_primary_relative_improvement_min'],'vs_C0_bootstrap_probability_pass':comps['C2_MINUS_C0']['bootstrap_probability_treatment_better']>=g['vs_C0_bootstrap_probability_better_min'],'vs_C1_relative_improvement_pass':comps['C2_MINUS_C1']['relative_improvement']>=g['vs_C1_primary_relative_improvement_min'],'vs_C1_bootstrap_probability_pass':comps['C2_MINUS_C1']['bootstrap_probability_treatment_better']>=g['vs_C1_bootstrap_probability_better_min'],'top_party_accuracy_degradation_pass':met['C0']['top_party_accuracy']-met['C2']['top_party_accuracy']<=g['top_party_accuracy_absolute_degradation_max'],'energy_degradation_vs_C0_pass':prob['C2']['relative_degradation_vs_C0']<=g['mean_energy_score_relative_degradation_max']}
primary=all(gates[k] for k in ('vs_C0_relative_improvement_pass','vs_C0_bootstrap_probability_pass','vs_C1_relative_improvement_pass','vs_C1_bootstrap_probability_pass'))
result={'schema_version':'1.0','result_id':'M26-E-REASON-HOLDOUT-2021-SCORE-V1','outcome_year':2021,'outcome_unsealed_after_c2_freeze':True,'mapping_sha256':sha_file(MAPPING),'outcome_file_sha256':sha_file(H/'tafra_legislative_2021_canonical.json'),'bundle_sha256':bundle['bundle_sha256'],'c2_judgments_preunseal_sha256':receipt['integrity']['c2_judgments_file_sha256'],'lambda_C1':0.3,'lambda_C2':0.3,'panel':{'territories':92,'party_cells':828},'z_audit':audit,'metrics':{k:{x:y for x,y in v.items() if x!='mse'} for k,v in met.items()},'comparisons':comps,'probabilistic':prob,'promotion_gates_evaluated':gates,'mandatory_primary_C2_gates_all_pass':primary,'terminal_decision_determined_by_primary_gates':'E_REASON_NO_PROMOTION' if not primary else 'PENDING_REMAINING_SECONDARY_SEAT_GATE','implementation_note':'Mechanical execution of preregistered metrics, lambdas, paired-bootstrap replicate count and seed; no post-outcome tuning.'}
OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'C0_RMSE':met['C0']['macro_party_share_RMSE'],'C1_RMSE':met['C1']['macro_party_share_RMSE'],'C2_RMSE':met['C2']['macro_party_share_RMSE'],'C2_vs_C0_relative':comps['C2_MINUS_C0']['relative_improvement'],'C2_vs_C1_relative':comps['C2_MINUS_C1']['relative_improvement'],'C2_vs_C0_p':comps['C2_MINUS_C0']['bootstrap_probability_treatment_better'],'C2_vs_C1_p':comps['C2_MINUS_C1']['bootstrap_probability_treatment_better'],'primary_all_pass':primary},sort_keys=True))
