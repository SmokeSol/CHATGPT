#!/usr/bin/env python3
from difflib import SequenceMatcher

import goal75_local_closure_v2 as closure

closure.CONFIG_TO_TAFRA.update({
    "sale el jadida": "sale al jadida",
    "tiflet rommani": "tifelt rommani",
})


def strict_best_row(config_name: str, rows: list[dict]) -> dict:
    wanted = closure.CONFIG_TO_TAFRA.get(closure.norm(config_name), closure.norm(config_name))
    scored = [
        (
            SequenceMatcher(None, wanted, closure.norm(row["circonscription"])).ratio(),
            closure.norm(row["circonscription"]),
            row,
        )
        for row in rows
    ]
    scored.sort(key=lambda item: (item[0], item[1]))
    best_score, _, best = scored[-1]
    second_score, _, second = scored[-2]
    if best_score < 0.72:
        raise RuntimeError(f"no high-confidence TAFRA row for {config_name}: best={best_score:.3f} {best['circonscription']}")
    if best_score - second_score < 0.08:
        raise RuntimeError(
            f"ambiguous TAFRA identity for {config_name}: "
            f"{best_score:.3f} {best['circonscription']} vs {second_score:.3f} {second['circonscription']}"
        )
    return best


closure.best_row = strict_best_row

if __name__ == "__main__":
    raise SystemExit(closure.main())
