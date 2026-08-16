#!/usr/bin/env python3
from difflib import SequenceMatcher

import goal75_local_closure_v2 as closure

closure.CONFIG_TO_TAFRA.update({
    "sale el jadida": "sale al jadida",
    "tiflet rommani": "tifelt rommani",
})


def strict_best_row(config_name: str, rows: list[dict]) -> dict:
    wanted = closure.CONFIG_TO_TAFRA.get(closure.norm(config_name), closure.norm(config_name))
    scored = sorted(
        (
            SequenceMatcher(None, wanted, closure.norm(row["circonscription"])).ratio(),
            row,
        )
        for row in rows
    )
    best_score, best = scored[-1]
    second_score = scored[-2][0]
    if best_score < 0.72:
        raise RuntimeError(f"no high-confidence TAFRA row for {config_name}: best={best_score:.3f} {best['circonscription']}")
    if best_score - second_score < 0.08:
        raise RuntimeError(
            f"ambiguous TAFRA identity for {config_name}: "
            f"{best_score:.3f} {best['circonscription']} vs {second_score:.3f} {scored[-2][1]['circonscription']}"
        )
    return best


closure.best_row = strict_best_row

if __name__ == "__main__":
    raise SystemExit(closure.main())
