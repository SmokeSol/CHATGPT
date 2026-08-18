#!/usr/bin/env python3
"""Hermetic CI driver for the frozen E_reason 2021 holdout. Never reads target outcomes."""
from __future__ import annotations
import argparse, csv, hashlib, importlib.util, json, shutil, sys, tempfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
E = ROOT / "data" / "goal100" / "e_reason"
SCRIPTS = ROOT / "scripts"
HOLDOUT = E / "blind" / "holdout"
C1 = E / "judgments" / "holdout" / "c1_rule_only"
SOURCE_ROSTER = E / "evidence" / "2021_head_list_rank_enrichment" / "enriched_candidate_roster.json"
SOURCE_GATE = E / "evidence" / "2021_head_list_rank_enrichment" / "gate.json"
RESOLUTION_GATE = E / "holdout_territory_resolution_gate_v1.json"
CONST = ROOT / "data" / "constituencies_goal75.csv"

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
    rg=read_json(RESOLUTION_GATE)
    if rg.get("status")!="FROZEN_BEFORE_2021_HOLDOUT_JUDGMENTS" or rg.get("target_outcome_seen") is not False or rg.get("mapping_seen") is not False:
        die("territory-resolution gate is not a valid pre-judgment freeze")

def prepare_effective_evidence(tmp: Path):
    rg=read_json(RESOLUTION_GATE); rows=read_json(SOURCE_ROSTER); sg=read_json(SOURCE_GATE)
    aliases=rg["accepted_aliases"]; exclusions=set(rg["ambiguous_exclusions"])
    with CONST.open(encoding="utf-8",newline="") as f: valid={r["constituency_id"] for r in csv.DictReader(f)}
    if len(valid)!=92 or len(rows)!=508: die("frozen constituency/roster cardinality changed")
    accepted=[]; counts=Counter(); excluded=0
    for r in rows:
        if int(r.get("year",0) or 0)!=2021: die("unexpected year in source holdout roster")
        src=str(r.get("district_source")); resolution=str(r.get("territory_resolution"))
        rr=dict(r)
        if resolution=="EXACT_NORMALIZED":
            cid=rr.get("territory_id"); counts["exact"]+=1
        elif src in aliases:
            cid=aliases[src]; rr["territory_id"]=cid; rr["territory_resolution"]="EXACT_NORMALIZED"; counts["alias"]+=1
        elif src in exclusions:
            excluded+=1; continue
        else:
            die(f"non-exact holdout territory not frozen in resolution gate: {src!r}")
        if cid not in valid: die(f"resolution gate produced invalid frozen constituency_id: {cid!r}")
        accepted.append(rr)
    expected=rg["expected_counts_after_gate"]
    districts={str(r["territory_id"]) for r in accepted}
    if counts["exact"]!=expected["accepted_exact_rows"] or counts["alias"]!=expected["accepted_alias_rows"] or len(accepted)!=expected["accepted_candidate_rows"] or excluded!=expected["excluded_ambiguous_rows"] or len(districts)!=expected["accepted_canonical_districts"]:
        die(f"resolution-gate derived counts diverged: exact={counts['exact']} alias={counts['alias']} accepted={len(accepted)} excluded={excluded} districts={len(districts)}")
    roster=tmp/"effective_enriched_candidate_roster.json"; roster.write_text(json.dumps(accepted,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    gate=dict(sg); gate["counts"]=dict(sg.get("counts") or {})
    gate["counts"]["explicit_rank_candidate_facts"]=len(accepted); gate["counts"]["resolved_canonical_districts"]=len(districts)
    gate["derived_for_locked_holdout_resolution_gate_sha256"]=sha_file(RESOLUTION_GATE)
    gpath=tmp/"effective_collection_gate.json"; gpath.write_text(json.dumps(gate,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    print("HOLDOUT_RESOLUTION_GATE_PASS",json.dumps({"exact":counts["exact"],"alias_promoted":counts["alias"],"accepted":len(accepted),"excluded_ambiguous":excluded,"canonical_districts":len(districts)},sort_keys=True))
    return roster,gpath

def run_frozen_builder(secret_path: Path, roster: Path, gate: Path):
    spec=importlib.util.spec_from_file_location("e_reason_frozen_holdout_builder",SCRIPTS/"e_reason_build_blind_holdout_bundle.py")
    mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod)
    mod.ROSTER=roster; mod.GATE=gate
    old=sys.argv[:]
    try:
        sys.argv=[str(SCRIPTS/"e_reason_build_blind_holdout_bundle.py"),"--secret-mapping-output",str(secret_path)]
        mod.main()
    finally: sys.argv=old

def patch_public_provenance(effective_roster: Path):
    rg=read_json(RESOLUTION_GATE); exp=rg["expected_counts_after_gate"]
    mp=HOLDOUT/"bundle_manifest.json"; m=read_json(mp)
    m["feature_input"]={
        "source_collection_gate_sha256":sha_file(SOURCE_GATE),
        "source_enriched_roster_sha256":sha_file(SOURCE_ROSTER),
        "territory_resolution_gate_sha256":sha_file(RESOLUTION_GATE),
        "effective_accepted_roster_sha256":sha_file(effective_roster),
        "source_candidate_facts":508,
        "accepted_candidate_facts":exp["accepted_candidate_rows"],
        "excluded_ambiguous_candidate_rows":exp["excluded_ambiguous_rows"],
        "resolved_districts":exp["accepted_canonical_districts"],
        "missing_unobserved_features":True,
        "resolution_policy":"FROZEN_EXACT_OR_EXPLICIT_ALIAS_ELSE_MISSING"
    }
    mp.write_text(json.dumps(m,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    sp=HOLDOUT/"mapping_seal.json"; s=read_json(sp); s["territory_resolution_gate_sha256"]=sha_file(RESOLUTION_GATE)
    sp.write_text(json.dumps(s,ensure_ascii=False,sort_keys=True,indent=2)+"\n",encoding="utf-8")

def validate_bundle():
    m=read_json(HOLDOUT/"bundle_manifest.json"); s=read_json(HOLDOUT/"mapping_seal.json")
    bundle_sha,core=canonical_core_sha(HOLDOUT/"blind_bundle.json"); prompt_sha=sha_file(E/"c2_prompt_v1.md"); rgsha=sha_file(RESOLUTION_GATE)
    if m.get("status")!="FROZEN_BLIND_HOLDOUT_BUNDLE" or m.get("packets")!=92 or m.get("party_cells")!=828: die("holdout manifest invalid")
    if m.get("target_outcome_read") is not False or (m.get("leakage_scan") or {}).get("status")!="PASS": die("holdout leakage/outcome guard failed")
    if m.get("anonymization_independent_from_development") is not True: die("holdout anonymization not independent")
    if s.get("status")!="SEALED_BEFORE_ANY_HOLDOUT_PREDICTIVE_JUDGMENT" or s.get("mapping_material_committed") is not False or s.get("mapping_material_judge_access") is not False: die("mapping seal invalid")
    if bundle_sha!=m.get("bundle_sha256") or bundle_sha!=s.get("blind_bundle_sha256"): die("bundle SHA disagreement")
    if prompt_sha!=m.get("c2_prompt_sha256") or prompt_sha!=s.get("c2_prompt_sha256"): die("prompt SHA disagreement")
    if (m.get("feature_input") or {}).get("territory_resolution_gate_sha256")!=rgsha or s.get("territory_resolution_gate_sha256")!=rgsha: die("resolution-gate provenance missing")
    packets=core.get("packets") or []
    if len(packets)!=92 or sum(len(p.get("parties") or []) for p in packets)!=828: die("bundle is not 92x9")
    return bundle_sha,prompt_sha

def cmd_build(secret_path):
    validate_preconditions()
    if (HOLDOUT/"bundle_manifest.json").exists(): validate_bundle(); print("HOLDOUT_BUNDLE_ALREADY_FROZEN"); return
    secret_path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="e_reason_holdout_resolution_") as td:
        roster,gate=prepare_effective_evidence(Path(td)); run_frozen_builder(secret_path,roster,gate); patch_public_provenance(roster)
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
    if not (C1/"c1_judgment_manifest.json").exists():
        spec=importlib.util.spec_from_file_location("e_reason_c1_holdout",SCRIPTS/"e_reason_generate_c1_holdout.py"); mod=importlib.util.module_from_spec(spec); assert spec.loader; spec.loader.exec_module(mod); mod.main()
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
