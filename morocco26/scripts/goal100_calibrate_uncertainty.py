#!/usr/bin/env python3
"""Calibrate the Goal100 hierarchical innovation model under a frozen protocol.

This script performs two-direction leave-one-transition-out retrospective
calibration, selects the smallest preregistered variance inflation factor that
passes coverage and width gates, then fits final parameters on both modern
transitions. It does not consume any 2026 outcome.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
HIST = G100 / "historical"
PROTOCOL_PATH = G100 / "uncertainty_protocol_v1.json"
BSTAR_PATH = G100 / "bstar_hindcast_v1.json"
Y2011 = HIST / "tafra_legislative_2011_canonical.json"
Y2016 = HIST / "tafra_legislative_2016_canonical.json"
Y2021 = HIST / "tafra_legislative_2021_canonical.json"
OUT_CAL = G100 / "uncertainty_calibration.json"
OUT_PAR = G100 / "uncertainty_parameters_v1.json"


def load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def norm(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def local_rows(doc: dict) -> list[dict]:
    return [r for r in doc["rows"] if norm(r.get("list_type")).startswith("local")]


def helmert_basis(d: int) -> np.ndarray:
    h = np.zeros((d, d - 1), dtype=float)
    for k in range(1, d):
        den = math.sqrt(k * (k + 1.0))
        h[:k, k - 1] = 1.0 / den
        h[k, k - 1] = -k / den
    # Numerical orthonormality and zero-sum checks.
    if not np.allclose(h.T @ h, np.eye(d - 1), atol=1e-12):
        raise RuntimeError("invalid Helmert basis orthogonality")
    if not np.allclose(h.sum(axis=0), 0.0, atol=1e-12):
        raise RuntimeError("invalid Helmert basis zero-sum property")
    return h


def replace_zero_and_normalize(x: np.ndarray, eps: float) -> np.ndarray:
    y = np.maximum(np.asarray(x, dtype=float), eps)
    return y / y.sum(axis=-1, keepdims=True)


def ilr(x: np.ndarray, h: np.ndarray, eps: float) -> np.ndarray:
    y = replace_zero_and_normalize(x, eps)
    return np.log(y) @ h


def ilr_inv(z: np.ndarray, h: np.ndarray) -> np.ndarray:
    logx = np.asarray(z) @ h.T
    logx -= np.max(logx, axis=-1, keepdims=True)
    x = np.exp(logx)
    return x / x.sum(axis=-1, keepdims=True)


def logit(x: np.ndarray) -> np.ndarray:
    y = np.clip(np.asarray(x, dtype=float), 1e-6, 1.0 - 1e-6)
    return np.log(y / (1.0 - y))


def expit(x: np.ndarray) -> np.ndarray:
    z = np.asarray(x, dtype=float)
    out = np.empty_like(z)
    pos = z >= 0
    out[pos] = 1.0 / (1.0 + np.exp(-z[pos]))
    ez = np.exp(z[~pos])
    out[~pos] = ez / (1.0 + ez)
    return out


def party_composition(row: dict, buckets: list[str]) -> np.ndarray:
    votes = {str(k): int(v) for k, v in row["votes"].items() if int(v) > 0}
    total = sum(votes.values())
    if total <= 0:
        raise RuntimeError(f"empty vote vector for {row['id_constituency']}")
    core = buckets[:-1]
    arr = [votes.get(p, 0) / total for p in core]
    arr.append(max(0.0, 1.0 - sum(arr)))
    x = np.array(arr, dtype=float)
    x /= x.sum()
    return x


def turnout(row: dict) -> float:
    value = row.get("turnout_rate_reported")
    if value is None:
        raise RuntimeError(f"missing turnout for {row['id_constituency']}")
    value = float(value)
    if not 0.0 < value < 1.0:
        raise RuntimeError(f"invalid turnout {value} for {row['id_constituency']}")
    return value


def psd_shrink(cov: np.ndarray, shrink: float, floor: float) -> np.ndarray:
    a = np.asarray(cov, dtype=float)
    a = (a + a.T) / 2.0
    d = np.diag(np.diag(a))
    a = (1.0 - shrink) * a + shrink * d
    vals, vecs = np.linalg.eigh(a)
    vals = np.maximum(vals, floor)
    return (vecs * vals) @ vecs.T


def covariance_about_zero(x: np.ndarray) -> np.ndarray:
    a = np.asarray(x, dtype=float)
    if a.ndim != 2 or not len(a):
        raise ValueError("expected nonempty 2D matrix")
    return (a.T @ a) / float(len(a))


def decompose(delta_vote: np.ndarray, delta_turnout: np.ndarray, region_idx: np.ndarray, n_regions: int) -> dict:
    g_vote = delta_vote.mean(axis=0)
    g_turn = float(delta_turnout.mean())
    dv = delta_vote - g_vote
    dt = delta_turnout - g_turn
    r_vote = np.zeros((n_regions, delta_vote.shape[1]), dtype=float)
    r_turn = np.zeros(n_regions, dtype=float)
    for r in range(n_regions):
        mask = region_idx == r
        if not np.any(mask):
            raise RuntimeError(f"empty region index {r}")
        r_vote[r] = dv[mask].mean(axis=0)
        r_turn[r] = dt[mask].mean()
    l_vote = dv - r_vote[region_idx]
    l_turn = dt - r_turn[region_idx]
    if not np.allclose(l_vote.mean(axis=0), 0.0, atol=1e-10):
        raise RuntimeError("local vote residuals do not centre globally")
    if abs(float(l_turn.mean())) > 1e-10:
        raise RuntimeError("local turnout residuals do not centre globally")
    return {
        "g_vote": g_vote,
        "r_vote": r_vote,
        "l_vote": l_vote,
        "g_turn": g_turn,
        "r_turn": r_turn,
        "l_turn": l_turn,
    }


def fit_components(decompositions: list[dict], protocol: dict) -> dict:
    floor = float(protocol["hierarchy"]["eigenvalue_floor"])
    gv = np.stack([d["g_vote"] for d in decompositions])
    rv = np.concatenate([d["r_vote"] for d in decompositions], axis=0)
    lv = np.concatenate([d["l_vote"] for d in decompositions], axis=0)
    cov_g = psd_shrink(covariance_about_zero(gv), 0.75, floor)
    cov_r = psd_shrink(covariance_about_zero(rv), 0.50, floor)
    cov_l = psd_shrink(covariance_about_zero(lv), 0.20, floor)

    gt = np.array([d["g_turn"] for d in decompositions], dtype=float)
    rt = np.concatenate([d["r_turn"] for d in decompositions])
    lt = np.concatenate([d["l_turn"] for d in decompositions])
    var_floor = floor
    var_g = max(float(np.mean(gt**2)), var_floor)
    var_r = max(float(np.mean(rt**2)), var_floor)
    var_l = max(float(np.mean(lt**2)), var_floor)
    return {
        "cov_vote_national": cov_g,
        "cov_vote_regional": cov_r,
        "cov_vote_local": cov_l,
        "var_turnout_national": var_g,
        "var_turnout_regional": var_r,
        "var_turnout_local": var_l,
        "component_counts": {
            "national": len(gv),
            "regional": len(rv),
            "local": len(lv),
        },
    }


def covariance_sqrt(cov: np.ndarray) -> np.ndarray:
    vals, vecs = np.linalg.eigh((cov + cov.T) / 2.0)
    if np.min(vals) <= 0:
        raise RuntimeError(f"covariance not positive definite after floor: {np.min(vals)}")
    return (vecs * np.sqrt(vals)) @ vecs.T


def sample_mv_t(rng: np.random.Generator, cov: np.ndarray, df: float, shape: tuple[int, ...]) -> np.ndarray:
    """Variance-standardized multivariate Student-t with target covariance."""
    dim = cov.shape[0]
    lead = int(np.prod(shape))
    z = rng.standard_normal((lead, dim)) @ covariance_sqrt(cov).T
    chi = rng.chisquare(df, size=(lead, 1)) / df
    x = z / np.sqrt(chi)
    x /= math.sqrt(df / (df - 2.0))
    return x.reshape(*shape, dim)


def sample_scalar_t(rng: np.random.Generator, variance: float, df: float, shape: tuple[int, ...]) -> np.ndarray:
    x = rng.standard_t(df, size=shape) / math.sqrt(df / (df - 2.0))
    return x * math.sqrt(variance)


def simulate_joint(
    rng: np.random.Generator,
    fit: dict,
    base_ilr: np.ndarray,
    base_logit_turnout: np.ndarray,
    region_idx: np.ndarray,
    n_regions: int,
    draws: int,
    factor: float,
    h: np.ndarray,
    df_t: float,
) -> tuple[np.ndarray, np.ndarray]:
    n_territories, dim = base_ilr.shape
    gv = sample_mv_t(rng, fit["cov_vote_national"], df_t, (draws,))
    rv = sample_mv_t(rng, fit["cov_vote_regional"], df_t, (draws, n_regions))
    lv = sample_mv_t(rng, fit["cov_vote_local"], df_t, (draws, n_territories))
    dz = factor * (gv[:, None, :] + rv[:, region_idx, :] + lv)
    vote = ilr_inv(base_ilr[None, :, :] + dz, h)

    gt = sample_scalar_t(rng, fit["var_turnout_national"], df_t, (draws,))
    rt = sample_scalar_t(rng, fit["var_turnout_regional"], df_t, (draws, n_regions))
    lt = sample_scalar_t(rng, fit["var_turnout_local"], df_t, (draws, n_territories))
    dt = factor * (gt[:, None] + rt[:, region_idx] + lt)
    tout = expit(base_logit_turnout[None, :] + dt)
    return vote, tout


def energy_score(samples: np.ndarray, observed: np.ndarray) -> float:
    sx = np.sqrt(np.clip(samples, 0.0, 1.0))
    sy = np.sqrt(np.clip(observed, 0.0, 1.0))[None, :, :]
    first = np.linalg.norm(sx - sy, axis=2).mean(axis=0)
    paired = np.roll(sx, shift=sx.shape[0] // 2, axis=0)
    second = np.linalg.norm(sx - paired, axis=2).mean(axis=0)
    return float(np.mean(first - 0.5 * second))


def crps(samples: np.ndarray, observed: np.ndarray) -> float:
    first = np.abs(samples - observed[None, :]).mean(axis=0)
    paired = np.roll(samples, shift=samples.shape[0] // 2, axis=0)
    second = np.abs(samples - paired).mean(axis=0)
    return float(np.mean(first - 0.5 * second))


def coverage_and_width(samples: np.ndarray, observed: np.ndarray) -> dict:
    # samples shape draws x ...; observed shape ...
    result = {}
    for label, alpha in (("50", 0.25), ("80", 0.10), ("95", 0.025)):
        lo = np.quantile(samples, alpha, axis=0)
        hi = np.quantile(samples, 1.0 - alpha, axis=0)
        inside = (observed >= lo) & (observed <= hi)
        result[f"coverage_{label}"] = float(np.mean(inside))
        result[f"mean_width_{label}"] = float(np.mean(hi - lo))
    return result


def evaluate_direction(
    train_decomp: dict,
    base_vote: np.ndarray,
    base_turnout: np.ndarray,
    observed_vote: np.ndarray,
    observed_turnout: np.ndarray,
    region_idx: np.ndarray,
    n_regions: int,
    factors: list[float],
    protocol: dict,
    h: np.ndarray,
    seed: int,
    direction: str,
) -> dict:
    fit = fit_components([train_decomp], protocol)
    base_z = ilr(base_vote, h, float(protocol["vote_transform"]["zero_replacement"]))
    base_t = logit(base_turnout)
    draws = int(protocol["retrospective_calibration"]["draws_per_direction_and_factor"])
    df_t = 5.0
    results = []
    for i, factor in enumerate(factors):
        rng = np.random.default_rng(seed + i * 1009)
        pred_vote, pred_turn = simulate_joint(
            rng, fit, base_z, base_t, region_idx, n_regions, draws, factor, h, df_t
        )
        if not np.all(np.isfinite(pred_vote)) or not np.all(pred_vote >= 0):
            raise RuntimeError(f"invalid sampled vote composition in {direction}/{factor}")
        if not np.allclose(pred_vote.sum(axis=2), 1.0, atol=1e-10):
            raise RuntimeError(f"unnormalized sampled vote composition in {direction}/{factor}")
        if not np.all(np.isfinite(pred_turn)) or not np.all((pred_turn > 0) & (pred_turn < 1)):
            raise RuntimeError(f"invalid sampled turnout in {direction}/{factor}")
        vc = coverage_and_width(pred_vote, observed_vote)
        tc = coverage_and_width(pred_turn, observed_turnout)
        results.append({
            "factor": factor,
            "vote_energy_score": energy_score(pred_vote, observed_vote),
            "turnout_crps": crps(pred_turn, observed_turnout),
            "vote": vc,
            "turnout": tc,
        })
    return {
        "direction": direction,
        "training_transitions": 1,
        "fit_component_counts": fit["component_counts"],
        "factors": results,
    }


def combine_directions(directions: list[dict], factors: list[float], protocol: dict) -> list[dict]:
    floors = protocol["retrospective_calibration"]["coverage_floors"]
    widths = protocol["retrospective_calibration"]["anti_trivial_width"]
    by_dir = [{float(x["factor"]): x for x in d["factors"]} for d in directions]
    combined = []
    for factor in factors:
        rows = [m[float(factor)] for m in by_dir]
        item = {
            "factor": factor,
            "vote_energy_score": float(np.mean([r["vote_energy_score"] for r in rows])),
            "turnout_crps": float(np.mean([r["turnout_crps"] for r in rows])),
            "vote_coverage_50": float(np.mean([r["vote"]["coverage_50"] for r in rows])),
            "vote_coverage_80": float(np.mean([r["vote"]["coverage_80"] for r in rows])),
            "vote_coverage_95": float(np.mean([r["vote"]["coverage_95"] for r in rows])),
            "turnout_coverage_50": float(np.mean([r["turnout"]["coverage_50"] for r in rows])),
            "turnout_coverage_80": float(np.mean([r["turnout"]["coverage_80"] for r in rows])),
            "turnout_coverage_95": float(np.mean([r["turnout"]["coverage_95"] for r in rows])),
            "mean_vote_share_95_width": float(np.mean([r["vote"]["mean_width_95"] for r in rows])),
            "mean_turnout_95_width": float(np.mean([r["turnout"]["mean_width_95"] for r in rows])),
        }
        checks = {
            "vote_50": item["vote_coverage_50"] >= float(floors["vote_share_50"]),
            "vote_80": item["vote_coverage_80"] >= float(floors["vote_share_80"]),
            "vote_95": item["vote_coverage_95"] >= float(floors["vote_share_95"]),
            "turnout_50": item["turnout_coverage_50"] >= float(floors["turnout_50"]),
            "turnout_80": item["turnout_coverage_80"] >= float(floors["turnout_80"]),
            "turnout_95": item["turnout_coverage_95"] >= float(floors["turnout_95"]),
            "vote_width": item["mean_vote_share_95_width"] <= float(widths["mean_vote_share_95_width_max"]),
            "turnout_width": item["mean_turnout_95_width"] <= float(widths["mean_turnout_95_width_max"]),
        }
        item["checks"] = checks
        item["passes"] = all(checks.values())
        combined.append(item)
    return combined


def serial_matrix(a: np.ndarray) -> list[list[float]]:
    return [[float(x) for x in row] for row in np.asarray(a)]


def main() -> None:
    protocol = load(PROTOCOL_PATH)
    bstar = load(BSTAR_PATH)
    if bstar["selected_vote_model"] != "V0_PERSIST" or bstar["selected_turnout_model"] != "T0_PERSIST":
        raise SystemExit("UNCERTAINTY_FAIL B* is not frozen persistence-first")

    docs = {2011: load(Y2011), 2016: load(Y2016), 2021: load(Y2021)}
    rows = {year: {str(r["id_constituency"]): r for r in local_rows(doc)} for year, doc in docs.items()}
    common = set(rows[2011]) & set(rows[2016]) & set(rows[2021])
    if len(common) != 92 or any(set(rows[y]) != common for y in rows):
        raise SystemExit("UNCERTAINTY_FAIL modern territorial continuity is not 92/92")
    ids = sorted(common, key=lambda x: int(float(x)))

    buckets = list(protocol["party_buckets"])
    eps = float(protocol["vote_transform"]["zero_replacement"])
    h = helmert_basis(len(buckets))
    vote = {}
    tout = {}
    for year in (2011, 2016, 2021):
        vote[year] = np.stack([party_composition(rows[year][cid], buckets) for cid in ids])
        tout[year] = np.array([turnout(rows[year][cid]) for cid in ids], dtype=float)

    current_regions = [str(rows[2021][cid]["region"]) for cid in ids]
    region_names = sorted(set(current_regions), key=norm)
    if len(region_names) != 12:
        raise SystemExit(f"UNCERTAINTY_FAIL current region count {len(region_names)}")
    region_map = {r: i for i, r in enumerate(region_names)}
    region_idx = np.array([region_map[r] for r in current_regions], dtype=np.int64)

    delta_vote = {
        "2011_to_2016": ilr(vote[2016], h, eps) - ilr(vote[2011], h, eps),
        "2016_to_2021": ilr(vote[2021], h, eps) - ilr(vote[2016], h, eps),
    }
    delta_turn = {
        "2011_to_2016": logit(tout[2016]) - logit(tout[2011]),
        "2016_to_2021": logit(tout[2021]) - logit(tout[2016]),
    }
    decomposition = {
        key: decompose(delta_vote[key], delta_turn[key], region_idx, len(region_names))
        for key in delta_vote
    }

    factors = [float(x) for x in protocol["retrospective_calibration"]["variance_inflation_grid"]]
    seed = int(protocol["retrospective_calibration"]["seed"])
    d1 = evaluate_direction(
        decomposition["2011_to_2016"], vote[2016], tout[2016], vote[2021], tout[2021],
        region_idx, len(region_names), factors, protocol, h, seed + 100000,
        "fit_2011_to_2016_predict_2016_to_2021",
    )
    d2 = evaluate_direction(
        decomposition["2016_to_2021"], vote[2011], tout[2011], vote[2016], tout[2016],
        region_idx, len(region_names), factors, protocol, h, seed + 200000,
        "fit_2016_to_2021_predict_2011_to_2016_diagnostic_reverse_time",
    )
    combined = combine_directions([d1, d2], factors, protocol)
    passing = [x for x in combined if x["passes"]]
    if not passing:
        OUT_CAL.write_text(json.dumps({
            "schema_version": "1.0",
            "artifact_id": "M26-GOAL100-UNCERTAINTY-CALIBRATION-V1",
            "protocol_id": protocol["protocol_id"],
            "gate": "FAIL_NO_PREREGISTERED_FACTOR_PASSES",
            "directions": [d1, d2],
            "combined": combined,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        raise SystemExit("UNCERTAINTY_FAIL no preregistered variance factor passes")
    selected = passing[0]
    factor = float(selected["factor"])

    final_fit = fit_components([decomposition["2011_to_2016"], decomposition["2016_to_2021"]], protocol)
    factor2 = factor * factor
    cov_g = final_fit["cov_vote_national"] * factor2
    cov_r = final_fit["cov_vote_regional"] * factor2
    cov_l = final_fit["cov_vote_local"] * factor2
    var_g = float(final_fit["var_turnout_national"] * factor2)
    var_r = float(final_fit["var_turnout_regional"] * factor2)
    var_l = float(final_fit["var_turnout_local"] * factor2)

    eig = {
        "vote_national": [float(x) for x in np.linalg.eigvalsh(cov_g)],
        "vote_regional": [float(x) for x in np.linalg.eigvalsh(cov_r)],
        "vote_local": [float(x) for x in np.linalg.eigvalsh(cov_l)],
    }
    if any(min(v) <= 0 for v in eig.values()):
        raise SystemExit("UNCERTAINTY_FAIL final covariance is not positive definite")

    parameters = {
        "schema_version": "1.0",
        "parameter_id": "M26-GOAL100-UNCERTAINTY-PARAMETERS-V1",
        "protocol_id": protocol["protocol_id"],
        "centre": {"vote": "V0_PERSIST", "turnout": "T0_PERSIST"},
        "party_buckets": buckets,
        "ilr_basis_helmert": serial_matrix(h),
        "zero_replacement": eps,
        "regions": region_names,
        "student_t_df": 5.0,
        "selected_variance_inflation": factor,
        "cov_vote_national": serial_matrix(cov_g),
        "cov_vote_regional": serial_matrix(cov_r),
        "cov_vote_local": serial_matrix(cov_l),
        "var_turnout_national": var_g,
        "var_turnout_regional": var_r,
        "var_turnout_local": var_l,
        "turnout_vote_cross_correlation": 0.0,
        "regional_ballot_policy": "Apply national plus regional components to 2021 regional-list baseline; no local residual; explicitly extrapolated.",
        "component_counts": final_fit["component_counts"],
        "eigenvalues": eig,
        "data_hashes": {
            "2011": hashlib.sha256(Y2011.read_bytes()).hexdigest(),
            "2016": hashlib.sha256(Y2016.read_bytes()).hexdigest(),
            "2021": hashlib.sha256(Y2021.read_bytes()).hexdigest(),
            "bstar": hashlib.sha256(BSTAR_PATH.read_bytes()).hexdigest(),
            "protocol": hashlib.sha256(PROTOCOL_PATH.read_bytes()).hexdigest(),
        },
        "epistemic_status": "POST_SELECTION_RETROSPECTIVELY_CALIBRATED_2026_UNTOUCHED",
    }
    parameter_canonical = json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    parameters["parameter_manifest_sha256"] = hashlib.sha256(parameter_canonical.encode("utf-8")).hexdigest()

    calibration = {
        "schema_version": "1.0",
        "artifact_id": "M26-GOAL100-UNCERTAINTY-CALIBRATION-V1",
        "protocol_id": protocol["protocol_id"],
        "design": "two-direction leave-one-transition-out retrospective calibration",
        "territories_per_direction": 92,
        "party_buckets": buckets,
        "directions": [d1, d2],
        "combined": combined,
        "selected_factor": factor,
        "selected_metrics": selected,
        "final_parameter_manifest_sha256": parameters["parameter_manifest_sha256"],
        "gate_checks": {
            "both_loto_directions_complete": len(d1["factors"]) == len(factors) and len(d2["factors"]) == len(factors),
            "coverage_rule_satisfied": selected["passes"],
            "anti_trivial_width_satisfied": selected["checks"]["vote_width"] and selected["checks"]["turnout_width"],
            "all_covariances_positive_definite": all(min(v) > 0 for v in eig.values()),
            "2026_outcome_used": False,
            "post_selection_model_family_search": False,
        },
        "known_limitations": [
            "Only two modern transitions identify temporal innovation scales.",
            "The reverse-time LOTO direction is a calibration diagnostic, not a real-time forecasting claim.",
            "Regional-list uncertainty is extrapolated from local territorial dynamics.",
            "Coverage is retrospective and does not guarantee 2026 coverage."
        ],
        "gate": "PASS",
    }

    OUT_PAR.write_text(json.dumps(parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_CAL.write_text(json.dumps(calibration, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "gate": "PASS",
        "selected_factor": factor,
        "vote_coverage_50": selected["vote_coverage_50"],
        "vote_coverage_80": selected["vote_coverage_80"],
        "vote_coverage_95": selected["vote_coverage_95"],
        "turnout_coverage_50": selected["turnout_coverage_50"],
        "turnout_coverage_80": selected["turnout_coverage_80"],
        "turnout_coverage_95": selected["turnout_coverage_95"],
        "parameter_hash": parameters["parameter_manifest_sha256"],
    }, indent=2))


if __name__ == "__main__":
    main()
