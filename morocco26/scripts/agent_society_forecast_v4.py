#!/usr/bin/env python3
from __future__ import annotations

import argparse,json,pathlib,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]; sys.path.insert(0,str(ROOT))
from morocco26.agent_society_v4.main_adapter import GitSnapshotReader,source_inventory,candidate_records
from morocco26.agent_society_v4.vintage import build_named_vintage,diff_vintages
from morocco26.agent_society_v4.electorate import calibrate_to_registered_totals
from morocco26.agent_society_v4.forecast import aggregate_cells,combine
from morocco26.agent_society_v4.calibration import fit_2016,score_2021
from morocco26.agent_society_v4.contracts import LambdaCalibration
from morocco26.agent_society_v4.historical import register_surface,pairing_index


def load(path): return json.loads(pathlib.Path(path).read_text())
def write(path,value): pathlib.Path(path).parent.mkdir(parents=True,exist_ok=True); pathlib.Path(path).write_text(json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+"\n")

def main(argv=None):
    ap=argparse.ArgumentParser(description="MOROCCO//26 Agent Society V4 architecture"); sub=ap.add_subparsers(dest="cmd",required=True)
    p=sub.add_parser("inventory-main"); p.add_argument("--repo-root",type=pathlib.Path,default=ROOT); p.add_argument("--main-ref",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("adapt-candidates"); p.add_argument("--repo-root",type=pathlib.Path,default=ROOT); p.add_argument("--main-ref",required=True); p.add_argument("--as-of",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("build-vintage"); p.add_argument("--spec",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("diff-vintages"); p.add_argument("--old",required=True); p.add_argument("--new",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("calibrate-electorate"); p.add_argument("--cells",required=True); p.add_argument("--registered-totals",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("aggregate-delta"); p.add_argument("--cells",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("fit-lambda-2016"); p.add_argument("--rows",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("score-2021"); p.add_argument("--rows",required=True); p.add_argument("--lambda-freeze",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("combine"); p.add_argument("--structural",required=True); p.add_argument("--delta",required=True); p.add_argument("--calibration",required=True); p.add_argument("--output",required=True)
    p=sub.add_parser("pair-regimes"); p.add_argument("--rich",required=True); p.add_argument("--blind",required=True); p.add_argument("--output",required=True)
    args=ap.parse_args(argv)
    if args.cmd=="inventory-main": write(args.output,source_inventory(GitSnapshotReader(args.repo_root,args.main_ref)))
    elif args.cmd=="adapt-candidates":
        reader=GitSnapshotReader(args.repo_root,args.main_ref); records,unresolved=candidate_records(reader,as_of=args.as_of); write(args.output,{"main_commit_sha":reader.commit_sha,"as_of":args.as_of,"records":[{"territory_id":r.territory_id,"party_id":r.party_id,"ballot":r.ballot.value,"state":r.state.value,"candidate_name":r.candidate_name,"known_at":r.known_at,"sources":list(r.sources),"attributes":dict(r.attributes)} for r in records],"unresolved":unresolved,"silent_imputation":False})
    elif args.cmd=="build-vintage": write(args.output,build_named_vintage(load(args.spec)))
    elif args.cmd=="diff-vintages": write(args.output,diff_vintages(load(args.old),load(args.new)))
    elif args.cmd=="calibrate-electorate": write(args.output,{"cells":calibrate_to_registered_totals(load(args.cells).get("cells",load(args.cells)),load(args.registered_totals).get("registered_totals",load(args.registered_totals)))})
    elif args.cmd=="aggregate-delta": write(args.output,aggregate_cells(load(args.cells).get("cells",load(args.cells))))
    elif args.cmd=="fit-lambda-2016": write(args.output,fit_2016(load(args.rows).get("rows",load(args.rows))))
    elif args.cmd=="score-2021": write(args.output,score_2021(load(args.rows).get("rows",load(args.rows)),load(args.lambda_freeze)))
    elif args.cmd=="combine":
        c=load(args.calibration); cal=LambdaCalibration(**(c.get("calibration") or c)); write(args.output,combine(load(args.structural),load(args.delta),cal))
    elif args.cmd=="pair-regimes": write(args.output,pairing_index(load(args.rich).get("rows",load(args.rich)),load(args.blind).get("rows",load(args.blind))))
    print(f"PASS_AGENT_SOCIETY_V4_{args.cmd.upper().replace('-','_')}"); return 0
if __name__=="__main__": raise SystemExit(main())
