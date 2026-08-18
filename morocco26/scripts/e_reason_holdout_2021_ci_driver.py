#!/usr/bin/env python3
"""Hermetic CI driver for the frozen E_reason 2021 holdout. Never reads target outcomes."""
from __future__ import annotations
import argparse, hashlib, json, shutil, subprocess, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
SCRIPTS = ROOT / "scripts"
HOLDOUT = E / "blind" / "holdout"
C1 = E / "judgments" / "holdout" / "c1_rule_only"
ROSTER = E / "evidence" / "2021_head_list_rank_enrichment" / "enriched_candidate_roster.json"

def die(msg): raise SystemExit(msg)
def read_json(p): return json.loads(p.read_text(encoding="utf-8"))
def sha_file(p):
    h=hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda:f.read(1024*1024),b""): h.update(c)
    return h.hexdigest()

def canonical_core_sha(p):
    b=read_json(p); declared=b.pop("bundle_sha256")
    got=hashlib.sha256(json.dumps(b,ensure_ascii=False,sort_keys=True,separators=(",",":")).encode()).hexdigest()
    if got!=declared: die(f"bundle canonical-core SHA mismatch: {got} != {declared}")
    return got,b

def validate_preconditions():
    f=read_json(E/"lambda_freeze_v1.json")
    if f.get("status")!="FROZEN_BEFORE_2021_JUDGMENTS": die("lambda freeze status invalid")
    if f.get("holdout_2021_outcome_seen_before_freeze") is not False: die("2021 outcome marked seen before lambda freeze")
    if f.get("lambda_C1")!=0.3 or f.get("lambda_C2")!=0.3: die("frozen lambdas are not 0.30 / 0.30")
    if (HOLDOUT/"outcome.json").exists(): die("forbidden holdout outcome exists inside blinded holdout directory")

def diagnose_roster_resolution():
    rows=read_json(ROSTER)
    counts=Counter(str(r.get("territory_resolution")) for r in rows if int(r.get("year",0) or 0)==2021)
    bad=[r for r in rows if int(r.get("year",0) or 0)==2021 and str(r.get("territory_resolution"))!="EXACT_NORMALIZED"]
    grouped=defaultdict(list)
    for r in bad:
        key=(str(r.get("district_source")),str(r.get("territory_id")),str(r.get("id_constituency")),str(r.get("constituency_canonical")),str(r.get("territory_resolution")),str(r.get("territory_match_score")))
        grouped[key].append(str(r.get("party_bucket")))
    print("HOLDOUT_ROSTER_RESOLUTION_COUNTS",json.dumps(dict(sorted(counts.items())),sort_keys=True))
    print("HOLDOUT_ROSTER_NONEXACT_ROWS",len(bad),"DISTRICTS",len(grouped))
    for key,parties in sorted(grouped.items()):
        print("HOLDOUT_ROSTER_NONEXACT",json.dumps({"district_source":key[0],"territory_id":key[1],"id_constituency":key[2],"constituency_canonical":key[3],"territory_resolution":key[4],"territory_match_score":key[5],"rows":len(parties),"parties":sorted(parties)},ensure_ascii=False,sort_keys=True))
    return bad

def validate_bundle():
    m=read_json(HOLDOUT/"bundle_manifest.json"); s=read_json(HOLDOUT/"mapping_seal.json")
    bundle_sha,core=canonical_core_sha(HOLDOUT/"blind_bundle.json"); prompt_sha=sha_file(E/"c2_prompt_v1.md")
    if m.get("status")!="FROZEN_BLIND_HOLDOUT_BUNDLE" or m.get("packets")!=92 or m.get("party_cells")!=828: die("holdout manifest invalid")
    if m.get("target_outcome_read") is not False or (m.get("leakage_scan") or {}).get("status")!="PASS": die("holdout leakage/outcome guard failed")
    if m.get("anonymization_independent_from_development") is not True: die("holdout anonymization not independent")
    if s.get("status")!="SEALED_BEFORE_ANY_HOLDOUT_PREDICTIVE_JUDGMENT" or s.get("mapping_material_committed") is not False or s.get("mapping_material_judge_access") is not False: die("mapping seal invalid")
    if bundle_sha!=m.get("bundle_sha256") or bundle_sha!=s.get("blind_bundle_sha256"): die("bundle SHA disagreement")
    if prompt_sha!=m.get("c2_prompt_sha256") or prompt_sha!=s.get("c2_prompt_sha256"): die("prompt SHA disagreement")
    packets=core.get("packets") or []
    if len(packets)!=92 or sum(len(p.get("parties") or []) for p in packets)!=828: die("bundle is not 92x9")
    return bundle_sha,prompt_sha

def cmd_build(secret_path):
    validate_preconditions()
    if (HOLDOUT/"bundle_manifest.json").exists(): validate_bundle(); print("HOLDOUT_BUNDLE_ALREADY_FROZEN"); return
    bad=diagnose_roster_resolution()
    if bad:
        die("holdout roster contains non-exact territory resolution; diagnostic emitted before builder invocation")
    secret_path.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([sys.executable,str(SCRIPTS/"e_reason_build_blind_holdout_bundle.py"),"--secret-mapping-output",str(secret_path)],cwd=ROOT.parent,check=True)
    if not secret_path.is_file() or (HOLDOUT/"holdout_mapping.json").exists(): die("secret mapping placement guard failed")
    a,b=validate_bundle(); print("HOLDOUT_BUNDLE_LEAKAGE_GUARD_PASS",a,b)

def cmd_locator(artifact_id,run_id):
    bundle_sha,_=validate_bundle(); s=read_json(HOLDOUT/"mapping_seal.json")
    x={"schema_version":"1.0","locator_id":"M26-E-REASON-HOLDOUT-MAPPING-ARTIFACT-LOCATOR-V1","artifact_name":"e-reason-holdout-secret-mapping","artifact_id":str(artifact_id),"workflow_run_id":str(run_id),"mapping_sha256":s["mapping_sha256"],"blind_bundle_sha256":bundle_sha,"mapping_material_committed":False,"access_rule":"DO_NOT_DOWNLOAD_OR_EXPOSE_TO_C2_BEFORE_HOLDOUT_JUDGMENT_HASHES_FREEZE"}
    (HOLDOUT/"mapping_artifact_locator.json").write_text(json.dumps(x,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def validate_c1():
    x=read_json(C1/"c1_judgment_manifest.json"); c=x.get("counts") or {}
    if x.get("status")!="PASS_C1_HOLDOUT_JUDGMENTS_FROZEN_AWAITING_C2" or x.get("outcomes_seen") is not False or x.get("mapping_seen") is not False or c.get("packets")!=92 or c.get("party_cells")!=828: die("C1 holdout manifest invalid")
    return x

def cmd_c1():
    validate_bundle()
    if not (C1/"c1_judgment_manifest.json").exists(): subprocess.run([sys.executable,str(SCRIPTS/"e_reason_generate_c1_holdout.py")],cwd=ROOT.parent,check=True)
    x=validate_c1(); print("C1_HOLDOUT_FREEZE_GUARD_PASS",json.dumps((x.get("counts") or {}).get("score_distribution"),sort_keys=True))

def cmd_handoff(out):
    bundle_sha,prompt_sha=validate_bundle(); validate_c1()
    if out.exists(): shutil.rmtree(out)
    out.mkdir(parents=True)
    for p in [HOLDOUT/"blind_bundle.json",HOLDOUT/"bundle_manifest.json",HOLDOUT/"mapping_seal.json",E/"c2_prompt_v1.md",E/"e_reason_output_schema_v1.json",E/"e_reason_conditions_v1.json"]: shutil.copy2(p,out/p.name)
    start=f'''# OPUS 5 — E_reason C2 LOCKED HOLDOUT RUN — EXACT HANDOFF\n\nExecute the blinded C2 arm of `M26-GOAL100-E-REASON-V1`. Work ONLY inside this directory. No browsing/tools/repo/history/extra context/re-identification/remembered outcomes. Outcome and mapping are absent; if visible STOP `E_REASON_LEAKAGE_INVALIDATED`.\n\nUse `c2_prompt_v1.md` VERBATIM. Bundle SHA-256: `{bundle_sha}`. Prompt SHA-256: `{prompt_sha}`. Verify 92 packets / 828 cells. Judge independently with RUN_ID `M26-E-REASON-C2-HOLDOUT-OPUS5-V1`, MODEL_ID `OPUS-5`, ATTEMPT_NUMBER=1 initially, one PACKET_JSON at a time. Retry only schema-invalid JSON with identical input and no semantic feedback.\n\nWrite outputs/c2_judgments.jsonl, c2_all_attempts.jsonl, c2_judgment_manifest.json, c2_terminal_report.json. Freeze ordered packet/judgment SHA-256 hashes and state outcomes_seen=false, mapping_seen=false, web_used=false, tools_used=false. PASS only on 92/92 valid. STOP after hashes freeze: no outcome/scoring/lambda/F1/Atlas.\n'''
    (out/"START_HERE_OPUS5.md").write_text(start,encoding="utf-8")
    if any(any(t in p.name.lower() for t in ("outcome","result","holdout_mapping")) for p in out.iterdir()): die("forbidden handoff material")
    sums=[f"{sha_file(p)}  {p.name}" for p in sorted(out.iterdir()) if p.is_file() and p.name!="HANDOFF_SHA256SUMS.txt"]
    (out/"HANDOFF_SHA256SUMS.txt").write_text("\n".join(sums)+"\n",encoding="utf-8")
    print("OPUS5_HOLDOUT_HANDOFF_INTEGRITY_PASS",bundle_sha,prompt_sha)

def main():
    ap=argparse.ArgumentParser(); sub=ap.add_subparsers(dest="cmd",required=True)
    b=sub.add_parser("build"); b.add_argument("--secret-path",required=True)
    l=sub.add_parser("locator"); l.add_argument("--artifact-id",required=True); l.add_argument("--run-id",required=True)
    sub.add_parser("c1"); h=sub.add_parser("handoff"); h.add_argument("--out",required=True)
    a=ap.parse_args()
    if a.cmd=="build": cmd_build(Path(a.secret_path).resolve())
    elif a.cmd=="locator": cmd_locator(a.artifact_id,a.run_id)
    elif a.cmd=="c1": cmd_c1()
    else: cmd_handoff(Path(a.out).resolve())
if __name__=="__main__": main()
