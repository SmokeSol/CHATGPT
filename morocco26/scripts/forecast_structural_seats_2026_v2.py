#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
HIST = G100 / "historical"
LAB = G100 / "forecast_lab"
BASE_ENGINE = ROOT / "scripts" / "goal100_run_fminus1.py"
OUT_ROOT = G100 / "forecasts_experimental"
N_DRAWS = 50_000
LAMBDA = 0.5

PRIMARY = "F-ROLLING-V2-LOCAL"
SENSITIVITY = "F-ROLLING-V2-SYMMETRIC"


def sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_patched_engine():
    source = BASE_ENGINE.read_text(encoding="utf-8")
    needle = '    national_output = {\n        "bucket_seat_distribution": {'
    replacement = (
        '    first_mask = national_bucket_seats == national_bucket_seats.max(axis=1, keepdims=True)\n'
        '    first_count = first_mask.sum(axis=1)\n'
        '    first_stats = {\n'
        '        bucket: {\n'
        '            "P_sole_first": float(np.mean(first_mask[:, index] & (first_count == 1))),\n'
        '            "P_first_or_tied": float(np.mean(first_mask[:, index])),\n'
        '            "P_fractional_first": float(np.mean(first_mask[:, index] / first_count)),\n'
        '        }\n'
        '        for index, bucket in enumerate(BUCKETS)\n'
        '    }\n\n'
        '    national_output = {\n'
        '        "first_party_probabilities": first_stats,\n'
        '        "bucket_seat_distribution": {'
    )
    if needle not in source:
        raise RuntimeError("base engine patch anchor not found")
    source = source.replace(needle, replacement, 1)
    module = types.ModuleType("goal100_run_fminus1")
    module.__file__ = str(BASE_ENGINE)
    module.__package__ = ""
    sys.modules["goal100_run_fminus1"] = module
    exec(compile(source, str(BASE_ENGINE), "exec"), module.__dict__)
    return module


def bucket_counts(engine, row: dict) -> np.ndarray:
    return np.asarray(engine.bucket_counts(row), dtype=float)


def build_centers(engine):
    data = load_json(HIST / "tafra_legislative_2021_canonical.json")
    local = [r for r in data["rows"] if engine.norm(r.get("list_type")) == "locale"]
    regional = [r for r in data["rows"] if engine.norm(r.get("list_type")) == "regionale"]
    engine.require(len(local) == 92, f"expected 92 local rows, got {len(local)}")
    engine.require(len(regional) == 12, f"expected 12 regional rows, got {len(regional)}")
    local_raw = np.stack([bucket_counts(engine, r) for r in local])
    regional_raw = np.stack([bucket_counts(engine, r) for r in regional])
    local_national = local_raw.sum(axis=0)
    local_national /= local_national.sum()
    regional_national = regional_raw.sum(axis=0)
    regional_national /= regional_national.sum()
    return local_national, regional_national


def make_clr(engine, raw_clr, local_national, regional_national, shrink_regional: bool):
    def rolling_clr(row: dict) -> np.ndarray:
        kind = engine.norm(row.get("list_type"))
        if kind == "locale":
            national = local_national
        elif kind == "regionale" and shrink_regional:
            national = regional_national
        else:
            return raw_clr(row)
        territory = bucket_counts(engine, row)
        territory /= territory.sum()
        centered = LAMBDA * territory + (1.0 - LAMBDA) * national
        engine.require(np.all(centered > 0), "rolling center contains zero-probability bucket")
        logs = np.log(centered)
        return logs - logs.mean()
    return rolling_clr


def set_output_paths(engine, snapshot_id: str) -> Path:
    out = OUT_ROOT / snapshot_id
    engine.FORECAST_DIR = out
    engine.FORECAST_PATH = out / "forecast.json"
    engine.DATA_MANIFEST_PATH = out / "data_manifest.json"
    engine.PARAMETER_MANIFEST_PATH = out / "parameter_manifest.json"
    engine.RNG_MANIFEST_PATH = out / "rng_seed_manifest.json"
    engine.SNAPSHOT_MANIFEST_PATH = out / "snapshot_manifest.json"
    return out


def postprocess(engine, snapshot_id: str, mode: str, out: Path, rolling_scores: dict):
    forecast_path = out / "forecast.json"
    data_path = out / "data_manifest.json"
    params_path = out / "parameter_manifest.json"
    rng_path = out / "rng_seed_manifest.json"
    stale_snapshot_path = out / "snapshot_manifest.json"
    sim_global = G100 / "simulation_certificate.json"

    forecast = load_json(forecast_path)
    data = load_json(data_path)
    params = load_json(params_path)
    rng = load_json(rng_path)
    sim = load_json(sim_global)

    forecast["schema_version"] = "2.0"
    forecast["snapshot_id"] = snapshot_id
    forecast["forecast_label"] = "STRUCTURAL_ROLLING_ORIGIN_HALF_SHRINK_NO_CANDIDATE_EVENT_OR_AGENTIC_ADJUSTMENT"
    forecast["rolling_origin_center"] = {
        "selected_model": rolling_scores["skill_floor_winner"],
        "lambda": rolling_scores["lambda_selected_for_2026"],
        "mode": mode,
        "local_center": "HALF_SHRINK_2021_TERRITORY_TO_2021_NATIONAL",
        "regional_center": (
            "HALF_SHRINK_2021_REGION_TO_2021_REGIONAL_NATIONAL"
            if mode == "LOCAL_AND_REGIONAL_HALF_SHRINK"
            else "PERSIST_2021_REGIONAL_UNCHANGED_NO_COMPARABLE_HISTORICAL_REGIONAL_FOLDS"
        ),
        "selection_rule": rolling_scores["selection_rule"],
        "historical_folds": [2011, 2016, 2021],
    }
    forecast["known_limitations"] = [
        "Structural forecast only: no 2026 candidate, defection, endorsement, campaign or agentic adjustment.",
        "The local territorial center uses lambda=0.5 selected from three rolling-origin historical folds.",
        (
            "Regional means also use lambda=0.5 as a sensitivity extrapolation because no comparable pre-2021 regional ballot exists."
            if mode == "LOCAL_AND_REGIONAL_HALF_SHRINK"
            else "Regional means remain 2021 persistence in the primary specification because lambda=0.5 was validated on local constituencies, not the current regional ballot."
        ),
        "Local registered-voter counts remain latent constrained draws, not official 2026 local counts.",
        "Only lists with positive 2021 votes are eligible in this structural layer; verified 2026 list changes belong to a later candidate/ballot-aware layer.",
    ]
    write_json(forecast_path, forecast)

    data["schema_version"] = "2.0"
    data["snapshot_id"] = snapshot_id
    data["rolling_origin_selection"] = {
        "path": "morocco26/data/goal100/forecast_lab/baseline_scores_v2.json",
        "sha256": sha256_path(LAB / "baseline_scores_v2.json"),
    }
    write_json(data_path, data)

    params["schema_version"] = "2.0"
    params["snapshot_id"] = snapshot_id
    params["territorial_center"] = forecast["rolling_origin_center"]
    write_json(params_path, params)

    rng["schema_version"] = "2.0"
    rng["snapshot_id"] = snapshot_id
    write_json(rng_path, rng)

    sim["schema_version"] = "2.0"
    sim["snapshot_id"] = snapshot_id
    sim["gate"] = "PASS"
    sim["forecast_sha256"] = sha256_path(forecast_path)
    sim_path = out / "simulation_certificate.json"
    write_json(sim_path, sim)

    if stale_snapshot_path.exists():
        stale_snapshot_path.unlink()

    snapshot = {
        "schema_version": "2.0",
        "snapshot_id": snapshot_id,
        "snapshot_class": "EXPERIMENTAL_STRUCTURAL_PROBABILISTIC_FORECAST",
        "target_year": 2026,
        "target_outcome_used": False,
        "draws": N_DRAWS,
        "rolling_origin": forecast["rolling_origin_center"],
        "parent_protocol": "M26-GOAL100-FMINUS1-PROTOCOL-V1.1",
        "F0_modified": False,
        "files": {
            "forecast.json": sha256_path(forecast_path),
            "data_manifest.json": sha256_path(data_path),
            "parameter_manifest.json": sha256_path(params_path),
            "rng_seed_manifest.json": sha256_path(rng_path),
            "simulation_certificate.json": sha256_path(sim_path),
        },
        "model_code_commit": os.environ.get("GITHUB_SHA", ""),
    }
    write_json(stale_snapshot_path, snapshot)
    return forecast


def summarize(engine, snapshot_id: str, forecast: dict) -> dict:
    seat = forecast["national_395"]["bucket_seat_distribution"]
    first = forecast["national_395"]["first_party_probabilities"]
    rows = {}
    for party in engine.BUCKETS:
        d = seat[party]
        rows[party] = {
            "mean": float(d["mean"]),
            "median": float(d["q50"]),
            "q025": float(d["q025"]),
            "q975": float(d["q975"]),
            "P_sole_first": float(first[party]["P_sole_first"]),
            "P_first_or_tied": float(first[party]["P_first_or_tied"]),
            "P_fractional_first": float(first[party]["P_fractional_first"]),
        }
    return {"snapshot_id": snapshot_id, "draws": int(forecast["draws"]), "parties": rows}


def run_one(engine, runtime, raw_clr, local_nat, regional_nat, rolling_scores, snapshot_id: str, mode: str):
    shrink_regional = mode == "LOCAL_AND_REGIONAL_HALF_SHRINK"
    out = set_output_paths(engine, snapshot_id)
    if out.exists():
        raise RuntimeError(f"experimental output already exists: {out}")
    runtime.AGE_RNG = np.random.default_rng(runtime.AGE_PRIOR_SEED)
    engine.clr = make_clr(engine, raw_clr, local_nat, regional_nat, shrink_regional)
    engine.main()
    forecast = postprocess(engine, snapshot_id, mode, out, rolling_scores)
    return summarize(engine, snapshot_id, forecast)


def main():
    scores_path = LAB / "baseline_scores_v2.json"
    if not scores_path.exists():
        raise RuntimeError("baseline_scores_v2.json missing; run forecast_lab_rolling_v2.py first")
    rolling_scores = load_json(scores_path)
    if rolling_scores.get("skill_floor_winner") != "HALF_SHRINK":
        raise RuntimeError(f"rolling-origin winner drifted: {rolling_scores.get('skill_floor_winner')}")
    if float(rolling_scores.get("lambda_selected_for_2026")) != LAMBDA:
        raise RuntimeError("rolling-origin lambda drifted from 0.5")

    engine = load_patched_engine()
    sys.path.insert(0, str(ROOT / "scripts"))
    runtime = importlib.import_module("goal100_fminus1_runtime_v4")
    runtime.install()
    raw_clr = engine.clr
    local_nat, regional_nat = build_centers(engine)

    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    primary = run_one(
        engine, runtime, raw_clr, local_nat, regional_nat, rolling_scores,
        PRIMARY, "LOCAL_HALF_SHRINK_REGIONAL_PERSIST"
    )
    sensitivity = run_one(
        engine, runtime, raw_clr, local_nat, regional_nat, rolling_scores,
        SENSITIVITY, "LOCAL_AND_REGIONAL_HALF_SHRINK"
    )

    comparison = {
        "schema_version": "2.0",
        "target_year": 2026,
        "primary_snapshot": PRIMARY,
        "sensitivity_snapshot": SENSITIVITY,
        "selected_lambda": LAMBDA,
        "draws_each": N_DRAWS,
        "primary": primary,
        "sensitivity": sensitivity,
        "F0_modified": False,
        "interpretation": (
            "Primary applies the empirically selected lambda=0.5 only where it was validated (local constituencies). "
            "Sensitivity also applies lambda=0.5 to regional ballots to measure the effect of that unvalidated extrapolation."
        ),
    }
    out = LAB / "structural_seat_forecast_2026_v2.json"
    write_json(out, comparison)
    print("STRUCTURAL_SEAT_FORECAST_V2=" + json.dumps(comparison, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
