#!/usr/bin/env python3
"""Deterministic wrapper around the Goal75 v2 reconciler.

It removes an implementation ambiguity in sourced-denominator lookup: display
labels are matched directly, while an internal row index is never treated as
part of a constituency name. All scientific gates and thresholds remain those
of v2.
"""
from __future__ import annotations

import goal75_reconcile_finalize_v2 as engine


def registered_for(name, rows):
    mapping = {}
    for row in rows:
        label = row.get("name") or row.get("circonscription") or row.get("constituency")
        if label is not None:
            mapping[str(label)] = row
    key = engine.best_key(name, mapping)
    return mapping[key]


engine.registered_for = registered_for

if __name__ == "__main__":
    engine.main()
