#!/usr/bin/env python3
"""Multi-regime Moroccan House seat allocator.

The allocator is deliberately list-level. Exact seat conversion must never be run
on the forecast lab's aggregate OTHER bucket.
"""
from __future__ import annotations
import argparse, json, math
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "data" / "goal100" / "forecast_pipeline" / "legal_regimes_v1.json"

class AllocationError(ValueError):
    pass

def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))

def _clean_votes(votes: Mapping[str, float]) -> dict[str, float]:
    if not votes:
        raise AllocationError("votes_by_list is empty")
    out = {}
    for k, v in votes.items():
        x = float(v or 0)
        if x < 0 or not math.isfinite(x):
            raise AllocationError(f"invalid vote count for {k}")
        out[str(k)] = x
    if sum(out.values()) <= 0:
        raise AllocationError("vote total must be positive")
    return out

def _assert_full_list_universe(votes: Mapping[str, float]) -> None:
    bad = [k for k in votes if str(k).upper() in {"OTHER", "OTHERS", "AUTRES"}]
    if bad:
        raise AllocationError("Exact legal allocation rejects aggregate OTHER/AUTRES buckets; provide each competing list separately.")

def allocate_from_shares(shares_by_list: Mapping[str, float], seats: int, year: int, tier: str = "local") -> dict[str, Any]:
    registry = load_registry(); rule = registry["regimes"][str(year)][tier]
    if rule["quotient_mode"] == "registered_voters_div_seats":
        raise AllocationError(f"{year} {tier}: shares alone are insufficient because the quotient depends on registered voters; absolute votes are required.")
    shares = _clean_votes(shares_by_list); total = sum(shares.values())
    return allocate({k:v/total for k,v in shares.items()}, seats, year, tier=tier)

def allocate(votes_by_list: Mapping[str, float], seats: int, year: int, *, tier: str="local", registered_voters: float|None=None, strict_list_universe: bool=True) -> dict[str, Any]:
    if seats <= 0: raise AllocationError("seats must be positive")
    votes = _clean_votes(votes_by_list)
    if strict_list_universe: _assert_full_list_universe(votes)
    registry = load_registry()
    try: rule = registry["regimes"][str(year)][tier]
    except KeyError as exc: raise AllocationError(f"unsupported regime/tier: {year}/{tier}") from exc
    segment_counts = rule.get("independent_segment_seat_counts")
    if segment_counts and seats not in set(int(x) for x in segment_counts):
        raise AllocationError(f"{year} {tier}: exact allocation is defined independently for seat segments {segment_counts}; call the allocator once per segment rather than pooling them.")

    total_valid = sum(votes.values()); threshold=float(rule.get("threshold_fraction_valid_votes",0.0))
    eligible={k:v for k,v in votes.items() if v+1e-12 >= threshold*total_valid}; excluded=sorted(set(votes)-set(eligible))
    if not eligible:
        return {"year":year,"tier":tier,"seats_requested":seats,"seats_allocated":0,"seats":{k:0 for k in votes},"eligible_lists":[],"excluded_lists":excluded,"quotient":None,"status":"NO_ELIGIBLE_LIST","unallocated_seats":seats,"tie_groups":[]}

    mode=rule["quotient_mode"]
    if mode=="eligible_valid_votes_div_seats": qbase=sum(eligible.values())
    elif mode=="registered_voters_div_seats":
        if registered_voters is None or float(registered_voters)<=0: raise AllocationError(f"{year} {tier}: registered_voters is required and must be positive")
        registered_voters=float(registered_voters); qbase=registered_voters
    else: raise AllocationError(f"unknown quotient mode {mode}")
    quotient=qbase/seats

    if len(eligible)==1 and rule.get("single_eligible_list_gets_all_seats"):
        winner=next(iter(eligible)); out={k:0 for k in votes}; out[winner]=seats
        return {"year":year,"tier":tier,"seats_requested":seats,"seats_allocated":seats,"seats":out,"eligible_lists":[winner],"excluded_lists":excluded,"threshold_fraction_valid_votes":threshold,"quotient_mode":mode,"quotient":quotient,"status":"ALLOCATED_SINGLE_ELIGIBLE_LIST","unallocated_seats":0,"tie_groups":[]}

    if mode=="registered_voters_div_seats" and len(eligible)==1:
        min_frac=rule.get("single_list_min_registered_fraction")
        if min_frac is not None and next(iter(eligible.values()))+1e-12 < float(min_frac)*registered_voters:
            return {"year":year,"tier":tier,"seats_requested":seats,"seats_allocated":0,"seats":{k:0 for k in votes},"eligible_lists":list(eligible),"excluded_lists":excluded,"threshold_fraction_valid_votes":threshold,"quotient_mode":mode,"quotient":quotient,"status":"UNIQUE_LIST_BELOW_REGISTERED_VOTER_MINIMUM","unallocated_seats":seats,"tie_groups":[]}

    seat_map={k:0 for k in votes}; remainders={}
    for k,v in eligible.items():
        initial=int(math.floor((v+1e-12)/quotient)); seat_map[k]=initial; remainders[k]=v-initial*quotient
    allocated=sum(seat_map.values())
    if allocated>seats: raise AllocationError("initial quotient allocation exceeds district magnitude")
    remaining=seats-allocated; ranked=sorted(remainders.items(),key=lambda kv:(-kv[1],kv[0]))
    tie_groups=[]; i=0
    while i<len(ranked):
        j=i+1
        while j<len(ranked) and abs(ranked[j][1]-ranked[i][1])<=1e-12: j+=1
        if j-i>1: tie_groups.append([k for k,_ in ranked[i:j]])
        i=j
    awarded=0; cutoff_tie=None
    for pos,(k,rem) in enumerate(ranked):
        if awarded>=remaining: break
        if pos+1==remaining and pos+1<len(ranked) and abs(rem-ranked[pos+1][1])<=1e-12:
            cutoff_tie=[x for x,r in ranked if abs(r-rem)<=1e-12]; break
        seat_map[k]+=1; awarded+=1
    allocated=sum(seat_map.values()); unallocated=seats-allocated
    status="UNRESOLVED_LEGAL_TIE" if cutoff_tie else "UNALLOCATED_LEGAL_EDGE_CASE" if unallocated else "ALLOCATED"
    return {"year":year,"tier":tier,"seats_requested":seats,"seats_allocated":allocated,"seats":seat_map,"eligible_lists":sorted(eligible),"excluded_lists":excluded,"threshold_fraction_valid_votes":threshold,"quotient_mode":mode,"quotient":quotient,"remainders":remainders,"tie_groups":tie_groups,"cutoff_tie":cutoff_tie,"unallocated_seats":unallocated,"status":status}

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--year",type=int,required=True,choices=[2002,2007,2011,2016,2021,2026]); ap.add_argument("--tier",default="local",choices=["local","national","regional"]); ap.add_argument("--seats",type=int,required=True); ap.add_argument("--votes-json",required=True); ap.add_argument("--registered-voters",type=float); args=ap.parse_args()
    print(json.dumps(allocate(json.loads(args.votes_json),args.seats,args.year,tier=args.tier,registered_voters=args.registered_voters),ensure_ascii=False,sort_keys=True))
if __name__=="__main__": main()
