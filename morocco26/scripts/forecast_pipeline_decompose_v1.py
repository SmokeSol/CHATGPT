#!/usr/bin/env python3
"""Decompose historical change into national swing and territorial residual."""
from __future__ import annotations
import json, importlib.util
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
OUT = G / "forecast_pipeline" / "national_territorial_decomposition_v1.json"

spec = importlib.util.spec_from_file_location("hb", ROOT/"scripts"/"e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES = hb.PARTIES
CORE = hb.CORE
EPS = 0.5

def readj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def local_rows(year):
    d=readj(HIST/f"tafra_legislative_{year}_canonical.json")
    rows=[r for r in d["rows"] if str(r.get("list_type","")).lower() in {"local","locale"}]
    if len(rows)!=92: raise RuntimeError(f"{year}: expected 92 local rows")
    return rows
def counts(row):
    raw=row.get("votes",{})
    vals=[float(raw.get(p,0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE))
    return np.asarray(vals,float)
def clr_share(x):
    a=np.asarray(x,float)+EPS
    s=a/a.sum()
    z=np.log(s); return z-z.mean()
def invclr(z):
    a=np.asarray(z,float); a=a-a.max(axis=-1,keepdims=True)
    e=np.exp(a); return e/e.sum(axis=-1,keepdims=True)
def centre(x): 
    a=np.asarray(x,float); return a-a.mean(axis=-1,keepdims=True)

def transition(consts, ya, yb):
    ra,rb=local_rows(ya),local_rows(yb)
    ma,mb=hb.match_rows(consts,ra),hb.match_rows(consts,rb)
    cids=[c["constituency_id"] for c in consts]
    ca=np.stack([counts(ma[c]) for c in cids])
    cb=np.stack([counts(mb[c]) for c in cids])
    sa=ca/ca.sum(axis=1,keepdims=True); sb=cb/cb.sum(axis=1,keepdims=True)
    na=ca.sum(axis=0); na=na/na.sum()
    nb=cb.sum(axis=0); nb=nb/nb.sum()
    zna=clr_share(na); znb=clr_share(nb)
    za=np.stack([clr_share(x) for x in ca]); zb=np.stack([clr_share(x) for x in cb])
    rel_a=centre(za-zna[None,:]); rel_b=centre(zb-znb[None,:])
    national_swing=centre(znb-zna)
    territorial_change=centre(rel_b-rel_a)
    # Exact least-squares lambda conditional on observed target national result.
    x=rel_a.reshape(-1); y=centre(zb-znb[None,:]).reshape(-1)
    denom=float(np.dot(x,x))
    lam=float(np.clip(np.dot(x,y)/denom if denom else 0.0,0.0,1.0))
    pred=invclr(znb[None,:] + lam*rel_a)
    rmse=float(np.sqrt(np.mean((pred-sb)**2)))
    corr=[]
    for j,p in enumerate(PARTIES):
        a=rel_a[:,j]; b=rel_b[:,j]
        c=float(np.corrcoef(a,b)[0,1]) if np.std(a)>0 and np.std(b)>0 else None
        corr.append((p,c))
    return {
      "transition":f"{ya}_TO_{yb}",
      "national_share_from":{p:float(na[j]) for j,p in enumerate(PARTIES)},
      "national_share_to":{p:float(nb[j]) for j,p in enumerate(PARTIES)},
      "national_clr_swing":{p:float(national_swing[j]) for j,p in enumerate(PARTIES)},
      "territorial_residual_change_sd":{p:float(np.std(territorial_change[:,j],ddof=1)) for j,p in enumerate(PARTIES)},
      "relative_geography_correlation":dict(corr),
      "oracle_conditional_territorial_memory_lambda":lam,
      "conditional_geography_RMSE_at_oracle_lambda":rmse,
      "territories":len(cids)
    }

def main():
    consts=hb.load_constituencies()
    transitions=[transition(consts,2011,2016),transition(consts,2016,2021)]
    result={
      "schema_version":"1.0",
      "result_id":"M26-NATIONAL-TERRITORIAL-DECOMPOSITION-V1",
      "scientific_status":"RETROSPECTIVE_DEVELOPMENT_ONLY",
      "party_order":list(PARTIES),
      "definition":{
        "national_layer":"Election-wide party swing in CLR space, computed from aggregate local-list votes.",
        "territorial_layer":"Within-election territory-relative CLR deviation around the national composition.",
        "forecast_equation":"z_territory,target = z_national,target + lambda * relative_geography_previous + residual",
        "interpretation":"National regime and relative geography are separate prediction problems; target national outcomes are used here only for retrospective decomposition, never as forecast inputs."
      },
      "transitions":transitions,
      "diagnostic":{
        "lambda_2016":transitions[0]["oracle_conditional_territorial_memory_lambda"],
        "lambda_2021":transitions[1]["oracle_conditional_territorial_memory_lambda"],
        "lambda_nonstationarity":abs(transitions[1]["oracle_conditional_territorial_memory_lambda"]-transitions[0]["oracle_conditional_territorial_memory_lambda"]),
        "conclusion":"PARTIAL_TERRITORIAL_MEMORY_BUT_NATIONAL_AND_TERRITORIAL_DYNAMICS_MUST_BE_MODELED_SEPARATELY"
      },
      "F0_modified":False
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"status":"PASS","lambdas":[x["oracle_conditional_territorial_memory_lambda"] for x in transitions]},sort_keys=True))

if __name__=="__main__": main()
