#!/usr/bin/env python3
"""Close the 92 local 2021 Article-84 replays without stale denominators.

Evidence ladder:
1. exact allocation invariance over every integer N in the legal interval;
2. independent contemporaneous registered-voter evidence for non-invariant rows;
3. exhaustive two-constituency province constraint for Kénitra / El Gharb.

The script records a diagnostic even when the final constrained case is not closed.
"""
from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "goal75"
OUT.mkdir(parents=True, exist_ok=True)

TAFRA_URL = (
    "https://open.africa/dataset/595d69a4-c7fc-4e9d-beeb-5d7fc9ec78e5/"
    "resource/cf341829-cd2c-4baa-b679-2b2ee1c1e333/download/"
    "parlement-elections-2021-1-0.xlsx"
)
META = {
    "idRegion", "idWilaya", "idPrefProv", "idSousPref", "idCirconscription",
    "region", "wilaya", "prefProv", "sousPref", "circonscription", "typeListe",
    "nSieges", "nInscrits", "txParticipation", "invalide", "repPctFemmes",
    "repAge34", "repAge3544", "repAge4554", "repAge55", "repEduSans",
    "repEdu1aire", "repEdu2aire", "repEduSup",
}

CONFIG_TO_TAFRA = {
    "rabat ocean": "rabat el mouhit",
    "rabat chellah": "rabat challah",
    "agadir ida outanane": "agadir ida ou tanane",
    "medina sidi youssef": "medina sidi youssef ben ali",
    "gueliz nakhil": "gueliz annakhil",
    "fes sud": "fes janoubia",
    "fes nord": "fes chamalia",
    "karia ghafsay": "karia rhafsai",
    "mohammedia": "mohammadia",
    "bzou ouaouizeght": "bzou ouaouizaght",
    "es semara": "es smara",
}


def norm(value: object) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        unicodedata.normalize("NFKD", str(value))
        .encode("ascii", "ignore")
        .decode()
        .lower(),
    ).strip()


def allocate(votes: dict[str, int], seats: int, registered: int) -> dict[str, int]:
    if registered <= 0 or seats <= 0:
        raise ValueError("registered and seats must be positive")
    quotient = registered / seats
    base = {p: math.floor(v / quotient) for p, v in votes.items()}
    left = seats - sum(base.values())
    if left < 0:
        raise ValueError(f"direct allocations exceed magnitude: {base}")
    remainder = {p: votes[p] - base[p] * quotient for p in votes}
    allocation = dict(base)
    for party in sorted(votes, key=lambda p: (-remainder[p], -votes[p], p)):
        if left == 0:
            break
        allocation[party] = allocation.get(party, 0) + 1
        left -= 1
    return {p: n for p, n in allocation.items() if n}


def same(a: dict[str, int], b: dict[str, int]) -> bool:
    return {k: v for k, v in a.items() if v} == {k: v for k, v in b.items() if v}


def compress_ints(values: list[int]) -> list[list[int]]:
    if not values:
        return []
    values = sorted(set(values))
    out: list[list[int]] = []
    start = prev = values[0]
    for value in values[1:]:
        if value == prev + 1:
            prev = value
            continue
        out.append([start, prev])
        start = prev = value
    out.append([start, prev])
    return out


def best_row(config_name: str, rows: list[dict]) -> dict:
    wanted = CONFIG_TO_TAFRA.get(norm(config_name), norm(config_name))
    exact = [r for r in rows if norm(r["circonscription"]) == wanted]
    if len(exact) == 1:
        return exact[0]
    wt = set(wanted.split())
    scored = []
    for row in rows:
        rt = set(norm(row["circonscription"]).split())
        inter = len(wt & rt)
        union = max(1, len(wt | rt))
        scored.append((inter / union, inter, row))
    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    if not scored or scored[0][1] == 0 or scored[0][0] < 0.45:
        raise RuntimeError(f"no TAFRA row for {config_name}: {scored[:3]}")
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        raise RuntimeError(f"ambiguous TAFRA row for {config_name}: {scored[:3]}")
    return scored[0][2]


def main() -> int:
    response = requests.get(TAFRA_URL, timeout=90, headers={"User-Agent": "MOROCCO26 research"})
    response.raise_for_status()
    frame = pd.read_excel(BytesIO(response.content), sheet_name="donnees")
    party_columns = [c for c in frame.columns if c not in META]
    local_frame = frame[frame["typeListe"].astype(str).str.lower().eq("locale")]
    local_rows = []
    for _, row in local_frame.iterrows():
        votes = {
            str(c): int(row[c])
            for c in party_columns
            if pd.notna(row[c]) and float(row[c]) > 0
        }
        local_rows.append(
            {
                "idCirconscription": str(int(row["idCirconscription"])),
                "circonscription": str(row["circonscription"]),
                "region": str(row["region"]),
                "seats": int(row["nSieges"]),
                "votes": votes,
                "valid_vote_sum": sum(votes.values()),
            }
        )
    if len(local_rows) != 92:
        raise RuntimeError(f"expected 92 TAFRA local rows, got {len(local_rows)}")

    config = list(csv.DictReader((DATA / "constituencies_goal75.csv").open(encoding="utf-8")))
    if len(config) != 92:
        raise RuntimeError(f"expected 92 configured constituencies, got {len(config)}")
    observed_raw = json.loads((OUT / "observed_elected_2021.json").read_text())
    observed = {norm(k): v for k, v in observed_raw["local"].items()}
    interval_proof = json.loads((OUT / "local_allocation_interval_proof.json").read_text())
    proof_by_id = {str(x["idCirconscription"]): x for x in interval_proof["rows"]}
    evidence = json.loads((DATA / "local_exception_registered_2021_goal75.json").read_text())
    direct = {x["constituency_id"]: x for x in evidence["direct"]}

    resolved: list[dict] = []
    unresolved: list[dict] = []
    matched_rows: dict[str, dict] = {}

    for cfg in config:
        row = best_row(cfg["name"], local_rows)
        matched_rows[cfg["constituency_id"]] = row
        observed_key = norm(row["circonscription"])
        target = observed.get(observed_key)
        if target is None:
            # Try the configured name and known aliases used in the member dataset.
            target = observed.get(CONFIG_TO_TAFRA.get(norm(cfg["name"]), norm(cfg["name"])))
        if target is None:
            raise RuntimeError(f"missing observed elected allocation for {cfg['name']} / {row['circonscription']}")
        if sum(target.values()) != int(cfg["seats"]):
            raise RuntimeError(f"observed magnitude mismatch for {cfg['name']}: {target}")

        proof = proof_by_id[row["idCirconscription"]]
        record = {
            "constituency_id": cfg["constituency_id"],
            "name": cfg["name"],
            "region": cfg["region"],
            "seats": int(cfg["seats"]),
            "tafra_id": row["idCirconscription"],
            "tafra_name": row["circonscription"],
            "valid_vote_sum": row["valid_vote_sum"],
            "observed_elected": target,
            "source_votes": TAFRA_URL,
        }

        if proof["invariant_to_topN_over_full_interval"]:
            invariant_target = proof["target_topN_one_each"]
            ok = same(invariant_target, target)
            record.update(
                {
                    "closure_method": "EXHAUSTIVE_DENOMINATOR_INTERVAL_INVARIANCE",
                    "registered_evidence": None,
                    "legal_allocation": invariant_target,
                    "gate_pass": ok,
                }
            )
            (resolved if ok else unresolved).append(record)
            continue

        if cfg["constituency_id"] in direct:
            ev = direct[cfg["constituency_id"]]
            allocation = allocate(row["votes"], int(cfg["seats"]), int(ev["registered"]))
            ok = same(allocation, target)
            record.update(
                {
                    "closure_method": "INDEPENDENT_CONTEMPORANEOUS_REGISTERED_COUNT",
                    "registered_evidence": ev,
                    "legal_allocation": allocation,
                    "gate_pass": ok,
                }
            )
            (resolved if ok else unresolved).append(record)
            continue

        # Kénitra is handled jointly with El Gharb after the first pass.
        if cfg["constituency_id"] == "kenitra":
            continue

        unresolved.append({**record, "closure_method": "NO_VALID_CLOSURE_PATH", "gate_pass": False})

    # Exhaustive province-sum proof for Kénitra / El Gharb.
    kenitra = matched_rows["kenitra"]
    gharb = matched_rows["el-gharb"]
    target_k = observed[norm(kenitra["circonscription"])]
    target_g = observed[norm(gharb["circonscription"])]
    constraint = evidence["constrained"][0]
    total = int(constraint["province_registered"])
    lower_k = kenitra["valid_vote_sum"]
    upper_k = total - gharb["valid_vote_sum"]
    if lower_k > upper_k:
        raise RuntimeError("Kénitra province constraint has no feasible integer split")

    pair_states: Counter[tuple] = Counter()
    both_match: list[int] = []
    for n_k in range(lower_k, upper_k + 1):
        n_g = total - n_k
        a_k = allocate(kenitra["votes"], 4, n_k)
        a_g = allocate(gharb["votes"], 3, n_g)
        key = (
            tuple(sorted(a_k.items())),
            tuple(sorted(a_g.items())),
        )
        pair_states[key] += 1
        if same(a_k, target_k) and same(a_g, target_g):
            both_match.append(n_k)

    constrained_record = {
        "constituency_id": "kenitra+el-gharb",
        "name": "Kénitra / El Gharb joint constraint",
        "region": "Rabat-Salé-Kénitra",
        "seats": 7,
        "closure_method": "EXHAUSTIVE_PROVINCE_SUM_CONSTRAINT",
        "province_registered": total,
        "kenitra_valid_vote_lower_bound": lower_k,
        "kenitra_feasible_upper_bound": upper_k,
        "feasible_integer_splits": upper_k - lower_k + 1,
        "matching_kenitra_N_intervals": compress_ints(both_match),
        "matching_splits": len(both_match),
        "all_feasible_splits_match": len(both_match) == (upper_k - lower_k + 1),
        "distinct_allocation_pairs": [
            {
                "kenitra": dict(k[0]),
                "el_gharb": dict(k[1]),
                "integer_splits": count,
            }
            for k, count in pair_states.most_common()
        ],
        "observed_kenitra": target_k,
        "observed_el_gharb": target_g,
        "registered_evidence": constraint,
    }
    constrained_record["gate_pass"] = constrained_record["all_feasible_splits_match"]
    if constrained_record["gate_pass"]:
        resolved.append(constrained_record)
    else:
        unresolved.append(constrained_record)

    result = {
        "schema_version": "2.0",
        "method": "81 exhaustive denominator-invariant rows + 10 independent registered counts + exhaustive Kénitra/El Gharb province-sum constraint",
        "local_constituencies": 92,
        "local_seats": 305,
        "invariant_rows": sum(r.get("closure_method") == "EXHAUSTIVE_DENOMINATOR_INTERVAL_INVARIANCE" for r in resolved),
        "direct_registered_rows": sum(r.get("closure_method") == "INDEPENDENT_CONTEMPORANEOUS_REGISTERED_COUNT" for r in resolved),
        "joint_constraint_pass": constrained_record["gate_pass"],
        "resolved_records": resolved,
        "unresolved_records": unresolved,
        "local_92_exact_gate_pass": len(unresolved) == 0,
        "forecast_status": "BLOCKED",
    }
    (OUT / "local_92_closure_v2.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            {
                "invariant_rows": result["invariant_rows"],
                "direct_registered_rows": result["direct_registered_rows"],
                "joint_constraint": constrained_record,
                "unresolved_count": len(unresolved),
                "local_92_exact_gate_pass": result["local_92_exact_gate_pass"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
