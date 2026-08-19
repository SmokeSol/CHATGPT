#!/usr/bin/env python3
"""Auto-discovered national/territorial decomposition across historical elections.

National transitions use each election's native district geometry. Territorial
transitions are computed only on a controlled common 2011-reference geography.
"""
from __future__ import annotations
import hashlib, importlib.util, json, re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]; G=ROOT/'data'/'goal100'; HIST=G/'historical'; FP=G/'forecast_pipeline'
OUT=FP/'national_territorial_decomposition_v1.json'; REG=FP/'legal_regimes_v1.json'
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
def native_rows(year,path,registry):
    d=rj(path); rows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
    exp=registry.get(str(year),{}).get('native_local_constituencies')
    if exp is not None and len(rows)!=int(exp): raise RuntimeError(f'{year}: expected {exp} native local rows, got {len(rows)}')
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
def national(rows):
    c=np.stack([counts(r) for r in rows]); n=c.sum(axis=0); n=n/n.sum(); return {'share':n,'z':clr(n)}
def reference_matrix(consts,rows,mode):
    if len(rows)!=92: return None
    m=hb.match_rows(consts,rows); cids=[c['constituency_id'] for c in consts]
    c=np.stack([counts(m[x]) for x in cids]); s=c/c.sum(axis=1,keepdims=True); n=c.sum(axis=0); n=n/n.sum()
    z=np.stack([clr(x) for x in c]); zn=clr(n)
    return {'shares':s,'national':n,'zn':zn,'rel':centre(z-zn[None,:]),'mode':mode}
def territorial(consts,year,rows):
    if year>=2011 and len(rows)==92: return reference_matrix(consts,rows,'DIRECT_2011_REFERENCE')
    bridge=FP/'geography_bridges'/f'{year}_to_2011_reference_v1.json'
    if not bridge.exists(): return None
    b=rj(bridge)
    if not b.get('forecast_eligible') or b.get('future_outcome_used') is not False or not b.get('harmonized_rows_path'): return None
    hp=ROOT/b['harmonized_rows_path']; d=rj(hp); hrows=[r for r in d['rows'] if str(r.get('list_type','')).lower() in {'local','locale'}]
    out=reference_matrix(consts,hrows,'FORECAST_ELIGIBLE_PRE_2011_BRIDGE')
    if out is None: raise RuntimeError(f'{year}: eligible bridge must produce 92 reference rows')
    out['bridge_path']=str(bridge.relative_to(ROOT)); out['bridge_sha256']=sha(bridge)
    return out

def main():
    files=discover(); years=list(files); registry=rj(REG)['regimes']; consts=hb.load_constituencies()
    rows={y:native_rows(y,files[y],registry) for y in years}; nat={y:national(rows[y]) for y in years}; terr={y:territorial(consts,y,rows[y]) for y in years}
    transitions=[]
    for a,b in zip(years[:-1],years[1:]):
        ns=centre(nat[b]['z']-nat[a]['z'])
        rec={'transition':f'{a}_TO_{b}','from_year':a,'to_year':b,
             'national_share_from':{p:float(nat[a]['share'][j]) for j,p in enumerate(PARTIES)},
             'national_share_to':{p:float(nat[b]['share'][j]) for j,p in enumerate(PARTIES)},
             'national_clr_swing':{p:float(ns[j]) for j,p in enumerate(PARTIES)},
             'national_status':'AVAILABLE_NATIVE_GEOMETRY','territorial_status':'BLOCKED_PENDING_FORECAST_ELIGIBLE_COMMON_GEOGRAPHY'}
        if terr.get(a) is not None and terr.get(b) is not None:
            ra,rb=terr[a]['rel'],terr[b]['rel']; x=ra.reshape(-1); y=rb.reshape(-1); den=float(np.dot(x,x))
            lam=float(np.clip(np.dot(x,y)/den if den else 0,0,1)); pred=inv(terr[b]['zn'][None,:]+lam*ra)
            rec.update({'territorial_status':'AVAILABLE_COMMON_REFERENCE_GEOGRAPHY',
                'territorial_geometry_modes':[terr[a]['mode'],terr[b]['mode']],
                'oracle_conditional_territorial_memory_lambda':lam,
                'conditional_geography_RMSE_at_oracle_lambda':float(np.sqrt(np.mean((pred-terr[b]['shares'])**2))),
                'relative_geography_correlation':{p:(float(np.corrcoef(ra[:,j],rb[:,j])[0,1]) if np.std(ra[:,j])>0 and np.std(rb[:,j])>0 else None) for j,p in enumerate(PARTIES)},
                'territorial_residual_change_sd':{p:float(np.std(centre(rb-ra)[:,j],ddof=1)) for j,p in enumerate(PARTIES)},
                'territories':92})
        transitions.append(rec)
    available=[x for x in transitions if x['territorial_status']=='AVAILABLE_COMMON_REFERENCE_GEOGRAPHY']
    result={'schema_version':'1.1','result_id':'M26-NATIONAL-TERRITORIAL-DECOMPOSITION-V1','scientific_status':'RETROSPECTIVE_DEVELOPMENT_ONLY',
      'detected_canonical_years':years,'party_order':list(PARTIES),
      'definition':{'national_layer':'Election-wide party swing in CLR space; valid at native election geometry.',
                    'territorial_layer':'Within-election territory-relative CLR deviation; fitted only on forecast-eligible common geography.',
                    'forecast_equation':'z_territory,target = z_national,target + lambda * relative_geography_previous + residual',
                    'interpretation':'Target national outcomes are used only for retrospective decomposition. A pre-2011 boundary mismatch never blocks the national layer and never authorizes fuzzy territorial matching.'},
      'transitions':transitions,
      'diagnostic':{'available_territorial_transition_count':len(available),
                    'territorial_lambdas':{x['transition']:x['oracle_conditional_territorial_memory_lambda'] for x in available},
                    'conclusion':'PARTIAL_TERRITORIAL_MEMORY_BUT_NATIONAL_AND_TERRITORIAL_DYNAMICS_MUST_BE_MODELED_SEPARATELY'},
      'dropin_behavior':'Any newly canonical historical year is included automatically. National decomposition activates immediately; territorial decomposition activates only if both adjacent elections have admissible common geometry.',
      'F0_modified':False}
    OUT.parent.mkdir(parents=True,exist_ok=True); OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    print(json.dumps({'years':years,'transitions':len(transitions),'territorial_available':len(available)},sort_keys=True))
if __name__=='__main__': main()
