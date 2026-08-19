#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, importlib.util, json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G = ROOT / "data" / "goal100"
HIST = G / "historical"
LAB = G / "forecast_lab"
CONTRACT = LAB / "forecast_skill_contract_v1.json"

spec = importlib.util.spec_from_file_location("hb", ROOT / "scripts" / "e_reason_build_blind_holdout_bundle.py")
hb = importlib.util.module_from_spec(spec); spec.loader.exec_module(hb)
PARTIES = hb.PARTIES
CORE = hb.CORE

def rj(p): return json.loads(Path(p).read_text(encoding="utf-8"))
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open("rb") as f:
        for b in iter(lambda:f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

def load_prior(year):
    p=HIST/f"tafra_legislative_{year}_canonical.json"
    d=rj(p)
    rows=[r for r in d["rows"] if str(r.get("list_type","")).lower() in {"local","locale"}]
    if len(rows)!=92: raise RuntimeError(f"{year}: expected 92 local rows, got {len(rows)}")
    return p, rows

def counts(row):
    raw=row.get("votes",{})
    vals=[float(raw.get(p,0) or 0) for p in CORE]
    vals.append(sum(float(v or 0) for p,v in raw.items() if p not in CORE))
    a=np.asarray(vals,float)
    if np.any(a<0) or a.sum()<=0: raise RuntimeError("invalid vote vector")
    return a

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--target",type=int,choices=[2016,2021],required=True); args=ap.parse_args()
    target=args.target; prior={2016:2011,2021:2016}[target]
    contract=rj(CONTRACT)
    if contract.get("contract_id")!="M26-FORECAST-LAB-SKILL-FLOOR-V1": raise RuntimeError("wrong contract")
    consts=hb.load_constituencies()
    prior_path, prior_rows=load_prior(prior)
    mp=hb.match_rows(consts,prior_rows)
    cids=[c["constituency_id"] for c in consts]
    prior_counts=np.stack([counts(mp[c]) for c in cids])
    territory=prior_counts/prior_counts.sum(axis=1,keepdims=True)
    national=prior_counts.sum(axis=0); national=national/national.sum()
    models={
      "PERSIST": territory,
      "HALF_SHRINK": 0.5*territory + 0.5*national[None,:],
      "NATIONAL_ONLY": np.repeat(national[None,:],len(cids),axis=0)
    }
    for k,v in models.items(): models[k]=v/v.sum(axis=1,keepdims=True)
    LAB.mkdir(parents=True,exist_ok=True)
    snapshot={
      "schema_version":"1.0","snapshot_id":f"M26-PRE-ELECTION-SNAPSHOT-{target}-V1",
      "target_year":target,"as_if_date":f"PRE_{target}_ELECTION",
      "allowed_prior_result_year":prior,
      "inputs":[
        {"path":str(prior_path.relative_to(ROOT)),"sha256":sha_file(prior_path),"role":"PRIOR_ELECTION_RESULT"},
        {"path":"data/constituencies_goal75.csv","sha256":sha_file(ROOT/"data"/"constituencies_goal75.csv"),"role":"FROZEN_TERRITORY_METADATA"}
      ],
      "target_outcome_present":False,
      "forbidden_target_path":str((HIST/f"tafra_legislative_{target}_canonical.json").relative_to(ROOT)),
      "generator":"forecast_lab_generate_v1.py"
    }
    outrows=[]
    for i,c in enumerate(consts):
      outrows.append({
        "territory_id":c["constituency_id"],"territory_name":c["name"],"seats":int(c["seats"]),
        "models":{m:{p:float(models[m][i,j]) for j,p in enumerate(PARTIES)} for m in models}
      })
    fc={
      "schema_version":"1.0","forecast_id":f"M26-FORECAST-LAB-POINT-{target}-V1","contract_id":contract["contract_id"],
      "target_year":target,"prior_year":prior,"forecast_type":"POINT_SKILL_FLOOR",
      "models":list(models),"party_order":list(PARTIES),"rows":outrows,
      "target_outcome_used":False,"seat_probabilities_available":False,"probabilistic_calibration_available":False,
      "interpretation":"Strict pre-election point benchmark; target result is not accessible to this generator."
    }
    (LAB/f"pre_election_snapshot_{target}_v1.json").write_text(json.dumps(snapshot,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    (LAB/f"baseline_forecast_{target}_v1.json").write_text(json.dumps(fc,ensure_ascii=False,indent=2,sort_keys=True)+"\n",encoding="utf-8")
    print(json.dumps({"target":target,"prior":prior,"territories":len(outrows),"models":list(models)},sort_keys=True))
if __name__=="__main__": main()
