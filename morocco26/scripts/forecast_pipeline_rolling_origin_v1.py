#!/usr/bin/env python3
"""Strict rolling-origin harness with separate national and harmonized-territorial layers.

Native district geometry may change by election. National dynamics use every valid
historical year immediately. Territorial dynamics use only elections represented
on the controlled 2011-reference geography; pre-2011 years therefore require an
explicit admissible boundary bridge and are never fuzzy-forced into 92 rows.
"""
from __future__ import annotations
import hashlib, importlib.util, json, re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; G=ROOT/'data'/'goal100'; HIST=G/'historical'; FP=G/'forecast_pipeline'
OUT=FP/'rolling_origin_status_v1.json'; REG=FP/'legal_regimes_v1.json'
spec=importlib.util.spec_from_file_location('hb',ROOT/'scripts'/'e_reason_build_blind_holdout_bundle.py')
hb=importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES=hb.PARTIES; CORE=hb.CORE; EPS=.5

def rj(p): return json.loads(Path(p).read_text(encoding='utf-8'))
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(1<<20),b''): h.update(b)
    return h.hexdigest()
def discover():
    pat=re.compile(r'tafra_legislative_(\d{4})_canonical\.json$'); out={}
    for p in HIST.glob('tafra_legislative_*_canonical.json'):
        m=pat.match(p.name)
        if m: out[int(m.group(1))]=p
    return dict(sorted(out.items()))
def local_native(year,path,registry):
    d=rj(path); rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
    if not rows: raise RuntimeError(f'{year}: no local rows')
    exp=registry.get(str(year),{}).get('native_local_constituencies')
    if exp is not None and len(rows)!=int(exp): raise RuntimeError(f'{year}: expected native {exp} local rows, got {len(rows)}')
    ids=[str(r.get('id_constituency')) for r in rows]
    if len(ids)!=len(set(ids)): raise RuntimeError(f'{year}: duplicate native constituency ids')
    return rows
def counts(row):
    raw=row.get('votes',{}); vals=[float(raw.get(p,0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE)); return np.asarray(vals,float)
def clr(x):
    a=np.asarray(x,float)+EPS; s=a/a.sum(); z=np.log(s); return z-z.mean()
def inv(z):
    a=np.asarray(z,float); a=a-a.max(axis=-1,keepdims=True); e=np.exp(a); return e/e.sum(axis=-1,keepdims=True)
def centre(x):
    a=np.asarray(x,float); return a-a.mean(axis=-1,keepdims=True)
def national_matrix(rows):
    c=np.stack([counts(r) for r in rows]); n=c.sum(axis=0); n=n/n.sum(); return {'national':n,'zn':clr(n)}
def direct_territorial_matrix(consts,rows):
    if len(rows)!=92: return None
    m=hb.match_rows(consts,rows); cids=[c['constituency_id'] for c in consts]
    c=np.stack([counts(m[x]) for x in cids]); s=c/c.sum(axis=1,keepdims=True)
    n=c.sum(axis=0); n=n/n.sum(); z=np.stack([clr(x) for x in c]); zn=clr(n)
    return {'cids':cids,'shares':s,'national':n,'zn':zn,'rel':centre(z-zn[None,:]),'geometry_mode':'DIRECT_2011_REFERENCE'}
def bridge_territorial_matrix(consts,year):
    bridge=FP/'geography_bridges'/f'{year}_to_2011_reference_v1.json'
    if not bridge.exists(): return None
    b=rj(bridge)
    if not b.get('forecast_eligible') or b.get('future_outcome_used') is not False: return None
    hp=b.get('harmonized_rows_path')
    if not hp: return None
    path=ROOT/hp; d=rj(path); rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
    if len(rows)!=92: raise RuntimeError(f'{year}: eligible bridge harmonized rows must be 92')
    out=direct_territorial_matrix(consts,rows)
    if out is None: raise RuntimeError(f'{year}: bridge failed reference mapping')
    out['geometry_mode']='ELIGIBLE_PRE_2011_BRIDGE'; out['bridge_path']=str(bridge.relative_to(ROOT)); out['bridge_sha256']=sha(bridge)
    return out
def territorial_matrix(consts,year,rows):
    if year>=2011 and len(rows)==92: return direct_territorial_matrix(consts,rows)
    return bridge_territorial_matrix(consts,year)
def fit_national(national,years_before_target):
    pairs=list(zip(years_before_target[:-1],years_before_target[1:]))
    if not pairs: return None
    shifts=[centre(national[b]['zn']-national[a]['zn']) for a,b in pairs]
    return {'mean_shift':np.mean(np.stack(shifts),axis=0),'training_transitions':[f'{a}_TO_{b}' for a,b in pairs],'n':len(shifts)}
def fit_lambda(territorial,years_before_target):
    pairs=[]; xs=[]; ys=[]
    for a,b in zip(years_before_target[:-1],years_before_target[1:]):
        if territorial.get(a) is None or territorial.get(b) is None: continue
        pairs.append((a,b)); xs.append(territorial[a]['rel'].reshape(-1)); ys.append(territorial[b]['rel'].reshape(-1))
    if not pairs: return None
    x=np.concatenate(xs); y=np.concatenate(ys); den=float(np.dot(x,x)); lam=float(np.clip(np.dot(x,y)/den if den else 0,0,1))
    return {'lambda':lam,'training_transitions':[f'{a}_TO_{b}' for a,b in pairs],'n':len(pairs)}
def arrhash(a): return hashlib.sha256(np.asarray(a,dtype='<f8',order='C').tobytes(order='C')).hexdigest()
def rmse(a,b): return float(np.sqrt(np.mean((np.asarray(a)-np.asarray(b))**2)))

def main():
    files=discover(); years=list(files); registry=rj(REG)['regimes']; consts=hb.load_constituencies()
    if len(years)<2: raise RuntimeError('need at least two historical years')
    folds=[]
    for idx,target in enumerate(years[1:],start=1):
        prior_year=years[idx-1]; prior_years=[y for y in years if y<target]
        # GENERATOR: open only strictly prior outcomes.
        rows_prior={y:local_native(y,files[y],registry) for y in prior_years}
        national={y:national_matrix(rows_prior[y]) for y in prior_years}
        territorial={y:territorial_matrix(consts,y,rows_prior[y]) for y in prior_years}
        nf=fit_national(national,prior_years); lf=fit_lambda(territorial,prior_years)
        national_forecasts={'PREVIOUS_NATIONAL':national[prior_year]['national'].copy()}
        if nf is not None: national_forecasts['LEARNED_MEAN_NATIONAL_SWING']=inv(centre(national[prior_year]['zn']+nf['mean_shift']))
        territory_forecasts={}
        pterr=territorial.get(prior_year)
        if pterr is not None:
            territory_forecasts['PERSIST_REFERENCE_GEOGRAPHY']=pterr['shares'].copy()
            nn=np.repeat(national[prior_year]['national'][None,:],92,axis=0)
            territory_forecasts['NATIONAL_ONLY_REFERENCE_GEOGRAPHY']=nn
            half=.5*pterr['shares']+.5*nn; half/=half.sum(axis=1,keepdims=True)
            territory_forecasts['HALF_SHRINK_FIXED_DIAGNOSTIC']=half
            if nf is not None and lf is not None:
                zn_pred=centre(national[prior_year]['zn']+nf['mean_shift'])
                territory_forecasts['LEARNED_TWO_LAYER']=inv(zn_pred[None,:]+lf['lambda']*pterr['rel'])
        hashes={'national':{k:arrhash(v) for k,v in sorted(national_forecasts.items())},'territorial':{k:arrhash(v) for k,v in sorted(territory_forecasts.items())}}
        freeze_payload=json.dumps({'target':target,'allowed':prior_years,'hashes':hashes,
            'national_fit':None if nf is None else {'transitions':nf['training_transitions'],'n':nf['n']},
            'territorial_fit':None if lf is None else {'transitions':lf['training_transitions'],'n':lf['n'],'lambda':lf['lambda']}},
            sort_keys=True,separators=(',',':')).encode(); freeze_sha=hashlib.sha256(freeze_payload).hexdigest()
        inputs=[{'year':y,'path':str(files[y].relative_to(ROOT)),'sha256':sha(files[y])} for y in prior_years]
        # SCORER: target opens only after all forecast hashes above exist.
        target_rows=local_native(target,files[target],registry); target_nat=national_matrix(target_rows); target_terr=territorial_matrix(consts,target,target_rows)
        nat_scores={k:rmse(v,target_nat['national']) for k,v in national_forecasts.items()}
        terr_scores={}
        if target_terr is not None:
            for k,v in territory_forecasts.items(): terr_scores[k]=rmse(v,target_terr['shares'])
        fold={
          'target_year':target,'prior_year':prior_year,'generator_allowed_outcome_years':prior_years,
          'generator_forbidden_target_path':str(files[target].relative_to(ROOT)),'generator_inputs':inputs,
          'target_outcome_used_by_generator':False,'forecast_freeze_sha256_before_target_open':freeze_sha,
          'forecast_model_hashes':hashes,'national_scores_party_share_RMSE':nat_scores,'territorial_scores_party_share_RMSE':terr_scores,
          'national_training_transitions':[] if nf is None else nf['training_transitions'],
          'territorial_training_transitions':[] if lf is None else lf['training_transitions'],
          'lambda_fitted_from_prior_harmonized_transitions':None if lf is None else lf['lambda'],
          'target_territorial_geometry_status':'AVAILABLE_REFERENCE_GEOGRAPHY' if target_terr is not None else 'BLOCKED_MISSING_FORECAST_ELIGIBLE_GEOGRAPHY_BRIDGE',
          'full_two_layer_status':('SCORED_AFTER_PRE_TARGET_FREEZE' if 'LEARNED_TWO_LAYER' in terr_scores else
                                   'BLOCKED_NO_TARGET_REFERENCE_GEOGRAPHY' if target_terr is None else
                                   'BLOCKED_NO_PRIOR_HARMONIZED_TERRITORIAL_TRANSITION'),
          'uncertainty_calibration_status':('NO_PRIOR_NATIONAL_TRANSITION' if nf is None else 'ONE_PRIOR_TRANSITION_INSUFFICIENT_FOR_STABILITY' if nf['n']==1 else 'MULTIPLE_PRIOR_TRANSITIONS_AVAILABLE_FOR_RESIDUAL_CALIBRATION'),
          'scorer_target_sha256':sha(files[target])}
        folds.append(fold)
    has2007=2007 in years; has2002=2002 in years
    out={'schema_version':'1.1','harness_id':'M26-ROLLING-ORIGIN-HARNESS-V1','status':'READY_FOR_2007_DROPIN' if not has2007 else '2007_DETECTED_PIPELINE_ACTIVE',
      'scientific_status':'RETROSPECTIVE_ROLLING_ORIGIN_DEVELOPMENT_METHOD_DESIGNED_IN_2026','detected_canonical_years':years,'folds':folds,
      'temporal_guarantee':'Target outcome content is opened only after national/territorial forecasts for the fold are generated and hashed. Strictly earlier outcomes only train the generator.',
      'geometry_guarantee':'Native 91/95-district pre-2011 outcomes are never fuzzy-forced to 92. National information activates immediately; territorial information requires an explicit forecast-eligible bridge to the 2011 reference geometry.',
      'what_2007_unlocks':{'immediate':'adds 2007 to national-swing rolling training and legal replay at native 95-district geometry','territorial':'2007→2011 activates only after controlled 2007-to-2011 geography bridge is built','2021':'adds one more strictly prior national transition; territorial contribution depends on bridge'},
      'what_2002_unlocks':{'immediate':'adds 2002 to national and legal history at native 91-district geometry','territorial':'adds 2002→2007 only after controlled bridges/harmonization','uncertainty':'provides an additional independent transition for stability/residual estimation'},
      'seat_scoring_status':{'bucketed_vote_model':'cannot be converted exactly because it contains OTHER','exact_allocator':'ready separately at real list level','post_2021_extra_input':'registered voters required'},
      'historical_2007_present':has2007,'historical_2002_present':has2002,'F0_modified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(out,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'status':out['status'],'years':years,'folds':len(folds)},sort_keys=True))
if __name__=='__main__': main()
