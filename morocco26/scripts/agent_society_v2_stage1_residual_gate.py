# -*- coding: utf-8 -*-
"""Outcome-free residual materiality gate for AS2 Stage-1.

Validates a 368-work-item fresh-context Opus-5 Stage-1 run against the frozen
selection manifest, compares it to the exact E0 work items, bootstraps over
184 election-territory pairs, and returns ADVANCE / KILL / STAGE1B / BLOCKED.
No mapping or election outcome is read.
"""
from __future__ import division
import argparse, hashlib, json, math, os, random

PASS = "PASS_AS2_STAGE1_FRESH_CONTEXT_OUTPUTS_FROZEN_READY_FOR_RESIDUAL_GATE"
EXPECTED_WORK_ITEMS = 368
EXPECTED_ROWS = 11776
THRESH = {"party_l1": 0.02, "turnout_abs": 0.01, "top_change": 0.05}
BOOTSTRAP_N = 10000
BOOTSTRAP_SEED = 260819


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh: return json.load(fh)


def read_jsonl(path):
    rows=[]
    with open(path,"r",encoding="utf-8") as fh:
        for n,line in enumerate(fh,1):
            if line.strip():
                try: rows.append(json.loads(line))
                except Exception as e: raise ValueError("%s:%d invalid json: %s"%(path,n,e))
    return rows


def sha256_file(path):
    h=hashlib.sha256()
    with open(path,"rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()


def is_opus5(x):
    return isinstance(x,str) and x.strip().lower().startswith("claude-opus-5")


def validate_rows(rows, item, label):
    if len(rows)!=32: raise ValueError("%s expected 32 rows; got %d"%(label,len(rows)))
    seen=[]
    for i,r in enumerate(rows):
        for key in ("anonymous_election_id","anonymous_territory_id","condition_id","batch_id","weighted_archetype_id","turnout_probability","conditional_party_probabilities","factor_importance","reason_codes"):
            if key not in r: raise ValueError("%s row %d missing %s"%(label,i,key))
        for key in ("anonymous_election_id","anonymous_territory_id","condition_id","batch_id"):
            expected=item[key]
            if r[key]!=expected: raise ValueError("%s row %d %s identity mismatch"%(label,i,key))
        aid=str(r["weighted_archetype_id"]); seen.append(aid)
        t=float(r["turnout_probability"])
        if not 0<=t<=1: raise ValueError("%s row %d turnout invalid"%(label,i))
        p=r["conditional_party_probabilities"]
        if not isinstance(p,dict) or not p: raise ValueError("%s row %d party simplex missing"%(label,i))
        if any(float(v)<0 for v in p.values()) or abs(sum(float(v) for v in p.values())-1)>1e-8:
            raise ValueError("%s row %d party simplex invalid"%(label,i))
        f=r["factor_importance"]
        if not isinstance(f,dict) or not f or any(float(v)<0 for v in f.values()) or abs(sum(float(v) for v in f.values())-1)>1e-8:
            raise ValueError("%s row %d factor simplex invalid"%(label,i))
    if len(set(seen))!=32: raise ValueError("%s duplicate archetype ids"%label)
    return seen


def aggregate(rows):
    keys=sorted(rows[0]["conditional_party_probabilities"])
    n=float(len(rows))
    return {
        "party":{k:sum(float(r["conditional_party_probabilities"][k]) for r in rows)/n for k in keys},
        "turnout":sum(float(r["turnout_probability"]) for r in rows)/n,
    }


def l1(a,b): return sum(abs(float(a[k])-float(b[k])) for k in a)


def row_metrics(e0, op):
    if [r["weighted_archetype_id"] for r in e0] != [r["weighted_archetype_id"] for r in op]:
        raise ValueError("archetype row order differs E0 vs Opus")
    vals=[]
    for a,b in zip(e0,op):
        pa=a["conditional_party_probabilities"]; pb=b["conditional_party_probabilities"]
        if set(pa)!=set(pb): raise ValueError("party ids differ E0 vs Opus")
        fa=a["factor_importance"]; fb=b["factor_importance"]
        if set(fa)!=set(fb): raise ValueError("factor ids differ E0 vs Opus")
        ra=set(a.get("reason_codes") or []); rb=set(b.get("reason_codes") or [])
        union=len(ra|rb); jac=1.0-(len(ra&rb)/float(union) if union else 1.0)
        vals.append({
            "party_l1":l1(pa,pb),
            "turnout_abs":abs(float(a["turnout_probability"])-float(b["turnout_probability"])),
            "factor_l1":l1(fa,fb),
            "reason_jaccard_distance":jac,
            "top_change":1.0 if max(pa,key=pa.get)!=max(pb,key=pb.get) else 0.0,
        })
    return vals


def percentile(xs,q):
    ys=sorted(xs)
    if not ys: return None
    pos=(len(ys)-1)*q; lo=int(math.floor(pos)); hi=int(math.ceil(pos))
    if lo==hi:return ys[lo]
    return ys[lo]*(hi-pos)+ys[hi]*(pos-lo)


def bootstrap_pairs(cells):
    pairs={}
    for c in cells:
        k=(c["election"],c["territory"])
        pairs.setdefault(k,[]).append(c)
    if len(pairs)!=184 or any(len(v)!=2 for v in pairs.values()):
        raise ValueError("expected 184 paired election-territory units with 2 opaque conditions")
    units=list(pairs.values()); rng=random.Random(BOOTSTRAP_SEED)
    out={m:[] for m in ("party_l1","turnout_abs","top_change")}
    for _ in range(BOOTSTRAP_N):
        picked=[units[rng.randrange(len(units))] for __ in range(len(units))]
        flat=[c for u in picked for c in u]
        for m in out: out[m].append(sum(c[m] for c in flat)/len(flat))
    return {m:{"low":percentile(v,.025),"high":percentile(v,.975)} for m,v in out.items()}


def provenance_gate(run_root):
    tp=os.path.join(run_root,"outputs","as2_stage1_terminal_report.json")
    mp=os.path.join(run_root,"outputs","as2_stage1_output_manifest.json")
    if not os.path.isfile(tp) or not os.path.isfile(mp): raise ValueError("missing Stage-1 terminal report or manifest")
    t=read_json(tp); m=read_json(mp)
    if t.get("terminal_status")!=PASS: raise ValueError("Stage-1 terminal status is not PASS")
    tc=t.get("execution_contract_compliance") or {}; mg=m.get("generated_by") or {}
    model=tc.get("model") or mg.get("model_id")
    if not is_opus5(model): raise ValueError("Stage-1 model is not Claude Opus 5 family")
    if tc.get("fresh_model_context_per_work_item") is not True or mg.get("fresh_model_context_per_work_item") is not True:
        raise ValueError("fresh_model_context_per_work_item must be true in terminal and manifest")
    if tc.get("deterministic_engine_or_emulator_substitution") not in (False,None):
        raise ValueError("deterministic engine substitution reported")
    counts=t.get("counts") or {}
    if counts.get("work_items_processed")!=EXPECTED_WORK_ITEMS or counts.get("rows_emitted")!=EXPECTED_ROWS:
        raise ValueError("terminal Stage-1 counts mismatch")
    return {"terminal_sha256":sha256_file(tp),"manifest_sha256":sha256_file(mp),"model":model}


def evaluate(stage1_root, opus_run_root, e0_root):
    prov=provenance_gate(opus_run_root)
    wm=read_json(os.path.join(stage1_root,"work_manifest.json"))
    if wm.get("counts",{}).get("work_items")!=EXPECTED_WORK_ITEMS: raise ValueError("Stage-1 work manifest count mismatch")
    cells=[]; row_acc={m:0.0 for m in ("party_l1","turnout_abs","factor_l1","reason_jaccard_distance","top_change")}; row_n=0
    for item in wm["work_items"]:
        ep=os.path.join(e0_root,item["output_path"]); op=os.path.join(opus_run_root,item["output_path"])
        e0=read_jsonl(ep); oo=read_jsonl(op)
        validate_rows(e0,item,"E0 "+item["output_path"]); validate_rows(oo,item,"OPUS "+item["output_path"])
        rms=row_metrics(e0,oo)
        for r in rms:
            for m in row_acc: row_acc[m]+=r[m]
            row_n+=1
        ae=aggregate(e0); ao=aggregate(oo)
        if set(ae["party"])!=set(ao["party"]): raise ValueError("aggregate party ids mismatch")
        cells.append({
            "election":item["anonymous_election_id"],"territory":item["anonymous_territory_id"],"condition":item["condition_id"],"batch":item["batch_id"],
            "party_l1":l1(ae["party"],ao["party"]),
            "turnout_abs":abs(ae["turnout"]-ao["turnout"]),
            "top_change":1.0 if max(ae["party"],key=ae["party"].get)!=max(ao["party"],key=ao["party"].get) else 0.0,
        })
    if row_n!=EXPECTED_ROWS or len(cells)!=EXPECTED_WORK_ITEMS: raise ValueError("validated count mismatch")
    point={m:sum(c[m] for c in cells)/len(cells) for m in ("party_l1","turnout_abs","top_change")}
    ci=bootstrap_pairs(cells)
    advance=(point["party_l1"]>=THRESH["party_l1"] or point["turnout_abs"]>=THRESH["turnout_abs"] or point["top_change"]>=THRESH["top_change"])
    kill=(ci["party_l1"]["high"]<THRESH["party_l1"] and ci["turnout_abs"]["high"]<THRESH["turnout_abs"] and ci["top_change"]["high"]<THRESH["top_change"])
    decision="ADVANCE_AS2" if advance else ("KILL_AS2_EXPANSION" if kill else "STAGE1B_SECOND_CLUSTER_REQUIRED")
    return {
      "schema_version":"AS2_STAGE1_RESIDUAL_GATE_RESULT_V1","decision":decision,"uses_outcomes":False,"uses_mapping":False,
      "provenance":prov,"validated":{"work_items":len(cells),"rows":row_n},
      "cell_point_estimates":point,"cell_bootstrap_95":ci,"thresholds":THRESH,
      "row_level_descriptives":{m:row_acc[m]/row_n for m in row_acc},
      "bootstrap":{"replicates":BOOTSTRAP_N,"seed":BOOTSTRAP_SEED,"unit":"anonymous election-territory pair carrying both opaque conditions"}
    }


def main(argv=None):
    ap=argparse.ArgumentParser(); ap.add_argument("stage1_handoff_root"); ap.add_argument("opus_run_root"); ap.add_argument("e0_run_root"); ap.add_argument("output_json")
    a=ap.parse_args(argv)
    try:
        result=evaluate(a.stage1_handoff_root,a.opus_run_root,a.e0_run_root)
    except Exception as exc:
        result={"schema_version":"AS2_STAGE1_RESIDUAL_GATE_RESULT_V1","decision":"BLOCKED","uses_outcomes":False,"uses_mapping":False,"error":str(exc)}
    with open(a.output_json,"w",encoding="utf-8",newline="\n") as f: json.dump(result,f,ensure_ascii=False,sort_keys=True,indent=2); f.write("\n")
    print(result["decision"], result.get("cell_point_estimates",{}))
    if result["decision"]=="BLOCKED": raise SystemExit(2)

if __name__=="__main__": main()
