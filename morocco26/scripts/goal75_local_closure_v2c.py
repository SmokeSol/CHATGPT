#!/usr/bin/env python3
from difflib import SequenceMatcher

import goal75_local_closure_v2 as closure

closure.CONFIG_TO_TAFRA.update({
    "sale el jadida": "sale al jadida",
    "tiflet rommani": "tifelt rommani",
    "taroudant sud": "taroudannt al janoubia",
    "taroudant nord": "taroudannt al chamalia",
})
REGION_ALIAS = {
    "dakhla oued eddahab": "dakhla oued ed dahab",
}


def canonical_region(value: str) -> str:
    normalized = closure.norm(value)
    return REGION_ALIAS.get(normalized, normalized)


def strict_best_row(config_name: str, rows: list[dict]) -> dict:
    wanted = closure.CONFIG_TO_TAFRA.get(closure.norm(config_name), closure.norm(config_name))
    cfg = next(x for x in strict_best_row.config if x["name"] == config_name)
    region = canonical_region(cfg["region"])
    seats = int(cfg["seats"])
    candidates = [
        row for row in rows
        if canonical_region(row["region"]) == region and int(row["seats"]) == seats
    ]
    if not candidates:
        raise RuntimeError(f"no TAFRA candidates in region/magnitude bucket for {config_name}: {region}/{seats}")
    scored = [
        (
            SequenceMatcher(None, wanted, closure.norm(row["circonscription"])).ratio(),
            closure.norm(row["circonscription"]),
            row,
        )
        for row in candidates
    ]
    scored.sort(key=lambda item: (item[0], item[1]))
    best_score, _, best = scored[-1]
    second_score, _, second = scored[-2] if len(scored) > 1 else (-1.0, "", {})
    if best_score < 0.55:
        raise RuntimeError(f"no high-confidence TAFRA row for {config_name}: best={best_score:.3f} {best['circonscription']}")
    if len(scored) > 1 and best_score - second_score < 0.08:
        raise RuntimeError(
            f"ambiguous TAFRA identity for {config_name}: "
            f"{best_score:.3f} {best['circonscription']} vs {second_score:.3f} {second['circonscription']}"
        )
    return best


import csv
strict_best_row.config = list(csv.DictReader((closure.DATA / "constituencies_goal75.csv").open(encoding="utf-8")))
closure.best_row = strict_best_row

if __name__ == "__main__":
    raise SystemExit(closure.main())
