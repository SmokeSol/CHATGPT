#!/usr/bin/env python3
"""Audit the binding-tie structure of the unregistered F-1 V1.1 candidate.

The audit replays the frozen latent streams into an ignored working-tree directory
and records the vote levels inside every binding remainder group. It does not
modify or register F-1.
"""
from __future__ import annotations

import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

import goal100_run_fminus1 as engine
import goal100_fminus1_runtime_v4 as runtime

# Keep temporary manifests under the repository root because the preserved base
# engine records repo-relative paths. The workflow never stages this directory.
TMP = Path(__file__).resolve().parents[2] / ".tmp" / "morocco26-fminus1-age-prior-audit"
HISTOGRAM = Counter()
BY_MAGNITUDE = defaultdict(Counter)
EXAMPLES = []
ORIGINAL_RESOLVE = runtime.resolve_binding_tie_by_exchangeable_age


def audited_resolve(votes: np.ndarray, registered: int, magnitude: int):
    values = np.asarray(votes, dtype=np.int64)
    base = (values * int(magnitude)) // int(registered)
    remainder = values * int(magnitude) - base * int(registered)
    seats_left = int(magnitude - int(base.sum()))
    binding = None
    for remainder_value in sorted(set(int(value) for value in remainder.tolist()), reverse=True):
        group = np.flatnonzero(remainder == remainder_value)
        if len(group) <= seats_left:
            seats_left -= len(group)
            continue
        binding = group
        break
    engine.require(binding is not None and seats_left > 0, "audit could not identify binding tie group")
    tied_votes = values[binding]
    minimum = int(tied_votes.min())
    maximum = int(tied_votes.max())
    key = (
        "ALL_ONE" if minimum == maximum == 1 else
        "ALL_LE_5" if maximum <= 5 else
        "ALL_LE_20" if maximum <= 20 else
        "MIXED_OR_GT_20"
    )
    HISTOGRAM[key] += 1
    HISTOGRAM["TOTAL"] += 1
    if len(set(tied_votes.tolist())) == 1:
        HISTOGRAM["EQUAL_RAW_VOTE_COUNTS"] += 1
    if minimum == 1:
        HISTOGRAM["GROUP_CONTAINS_SUPPORT_VOTE_ONE"] += 1
    if maximum == 1:
        HISTOGRAM["GROUP_ALL_SUPPORT_VOTE_ONE"] += 1
    BY_MAGNITUDE[int(magnitude)][key] += 1
    BY_MAGNITUDE[int(magnitude)]["TOTAL"] += 1
    if len(EXAMPLES) < 25:
        EXAMPLES.append(
            {
                "registered": int(registered),
                "magnitude": int(magnitude),
                "seats_needed_from_binding_group": int(seats_left),
                "binding_group_size": int(len(binding)),
                "tied_vote_counts": tied_votes.astype(int).tolist(),
                "minimum_tied_votes": minimum,
                "maximum_tied_votes": maximum,
                "category": key,
            }
        )
    return ORIGINAL_RESOLVE(votes, registered, magnitude)


def main() -> None:
    if TMP.exists():
        shutil.rmtree(TMP)
    TMP.mkdir(parents=True)
    runtime.resolve_binding_tie_by_exchangeable_age = audited_resolve
    runtime.install()

    engine.FORECAST_DIR = TMP / "forecasts" / "F-1-AUDIT"
    engine.FORECAST_PATH = engine.FORECAST_DIR / "forecast.json"
    engine.DATA_MANIFEST_PATH = engine.FORECAST_DIR / "data_manifest.json"
    engine.PARAMETER_MANIFEST_PATH = engine.FORECAST_DIR / "parameter_manifest.json"
    engine.RNG_MANIFEST_PATH = engine.FORECAST_DIR / "rng_seed_manifest.json"
    engine.SNAPSHOT_MANIFEST_PATH = engine.FORECAST_DIR / "snapshot_manifest.json"
    engine.SIMULATION_CERTIFICATE_PATH = TMP / "simulation_certificate.json"
    engine.main()

    total = HISTOGRAM["TOTAL"]
    report = {
        "schema_version": "1.0",
        "audit_id": "M26-GOAL100-FMINUS1-AGE-PRIOR-AUDIT-V1",
        "candidate_snapshot": "F-1-V1.1-UNREGISTERED",
        "draws": engine.N_DRAWS,
        "binding_tie_groups": total,
        "histogram": dict(sorted(HISTOGRAM.items())),
        "rates_within_binding_groups": {
            key: (value / total if total else 0.0)
            for key, value in sorted(HISTOGRAM.items())
            if key != "TOTAL"
        },
        "by_magnitude": {str(key): dict(sorted(value.items())) for key, value in sorted(BY_MAGNITUDE.items())},
        "examples": EXAMPLES,
        "interpretation_gate": {
            "support_vote_artifact_material_if": "GROUP_ALL_SUPPORT_VOTE_ONE / TOTAL >= 0.10",
            "candidate_age_prior_material_if": "binding_tie_groups / (104*50000) >= 0.01",
        },
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    shutil.rmtree(TMP)


if __name__ == "__main__":
    main()
