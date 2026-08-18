#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
M = ROOT / "morocco26"
G = M / "data" / "goal100"
CI2 = G / "e_collect" / "candidate_intelligence_v2"
CI3 = G / "e_collect" / "candidate_intelligence_v3"
H = G / "historical"

CONTRACT = CI3 / "candidate_intelligence_v3_contract_v1.json"
POWER = CI2 / "candidate_intelligence_v2_multipart_head_power_gate_v4.json"
D16 = CI2 / "multipart" / "2016_head_prior_mp_features_v4.jsonl"
D21 = CI2 / "multipart" / "2021_head_prior_mp_features_v4.jsonl"
OUT = CI3 / "candidate_intelligence_v3_symmetric_territorial_gate_v1.json"
CERT = CI3 / "candidate_intelligence_v3_terminal_certificate_v1.json"

RIDGE = [0.01, 0.1, 1.0, 10.0, 100.0, 1000.0]
SEED = 260818
NBOOT = 10000
EPS = 1e-6
PARTY_ORDER = ("PJD", "RNI")
M1 = "M1_HEAD_PRIOR_MP_SAME_PARTY_SAME_DISTRICT"

spec = importlib.util.spec_from_file_location(
    "hb", M / "scripts" / "e_reason_build_blind_holdout_bundle.py"
)
hb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(hb)
PARTIES = hb.PARTIES


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def logit(value: float | np.ndarray) -> float | np.ndarray:
    p = np.clip(np.asarray(value, dtype=float), EPS, 1.0 - EPS)
    out = np.log(p / (1.0 - p))
    return float(out) if out.ndim == 0 else out


def logistic(value: float | np.ndarray) -> float | np.ndarray:
    out = 1.0 / (1.0 + np.exp(-np.asarray(value, dtype=float)))
    return float(out) if out.ndim == 0 else out


def local_rows(year: int) -> list[dict[str, Any]]:
    if year in (2011, 2016):
        rows = hb.load_local(year)
    else:
        data = read_json(H / f"tafra_legislative_{year}_canonical.json")
        rows = [
            row
            for row in data["rows"]
            if str(row.get("list_type", "")).lower() in {"local", "locale"}
        ]
    if len(rows) != 92:
        raise RuntimeError(f"expected 92 local rows for {year}, got {len(rows)}")
    return rows


def party_shares(row: dict[str, Any]) -> np.ndarray:
    raw = row.get("votes", {})
    values = [float(raw.get(party, 0) or 0) for party in hb.CORE]
    values.append(
        sum(float(v or 0) for key, v in raw.items() if key not in hb.CORE)
    )
    arr = np.asarray(values, dtype=float)
    if arr.sum() <= 0:
        raise RuntimeError("non-positive vote total")
    return arr / arr.sum()


def state_value(state: str | None) -> float | None:
    if state == "VERIFIED_TRUE":
        return 1.0
    if state == "VERIFIED_FALSE":
        return 0.0
    return None


def build_cells(
    detail_path: Path,
    prior_map: dict[str, dict[str, Any]],
    current_map: dict[str, dict[str, Any]],
    constituency_meta: dict[str, dict[str, Any]],
    transition: str,
) -> list[dict[str, Any]]:
    cells: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()

    for row in read_jsonl(detail_path):
        party = row.get("party")
        territory_id = row.get("territory_id")
        if party not in PARTY_ORDER or not territory_id:
            continue
        key = (party, territory_id)
        if key in seen:
            raise RuntimeError(f"duplicate party-territory head cell: {key}")
        seen.add(key)

        state = row.get("feature_states", {}).get(M1)
        m1 = state_value(state)
        if m1 is None:
            continue
        if (
            territory_id not in prior_map
            or territory_id not in current_map
            or territory_id not in constituency_meta
        ):
            continue

        party_index = PARTIES.index(party)
        prior_share = float(party_shares(prior_map[territory_id])[party_index])
        current_share = float(party_shares(current_map[territory_id])[party_index])
        prior_logit = float(logit(prior_share))
        current_logit = float(logit(current_share))

        cells.append(
            {
                "transition": transition,
                "party": party,
                "territory_id": territory_id,
                "region": constituency_meta[territory_id]["region"],
                "m1": m1,
                "prior_share": prior_share,
                "current_share": current_share,
                "prior_logit": prior_logit,
                "current_logit": current_logit,
                "raw_logit_change": current_logit - prior_logit,
            }
        )

    return cells


def transform_transition(cells: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    moments: dict[str, dict[str, float]] = {}
    for party in PARTY_ORDER:
        party_cells = [cell for cell in cells if cell["party"] == party]
        if not party_cells:
            raise RuntimeError(f"no cells for {party}")
        moments[party] = {
            "mean_raw_logit_change": float(
                np.mean([cell["raw_logit_change"] for cell in party_cells])
            ),
            "mean_prior_logit": float(
                np.mean([cell["prior_logit"] for cell in party_cells])
            ),
            "mean_m1": float(np.mean([cell["m1"] for cell in party_cells])),
        }

    for cell in cells:
        moment = moments[cell["party"]]
        cell["y"] = (
            cell["raw_logit_change"] - moment["mean_raw_logit_change"]
        )
        cell["strength"] = cell["prior_logit"] - moment["mean_prior_logit"]
        cell["m1_centered"] = cell["m1"] - moment["mean_m1"]
        cell["rni"] = 1.0 if cell["party"] == "RNI" else 0.0

    return moments


def design_c1(cell: dict[str, Any]) -> np.ndarray:
    strength = float(cell["strength"])
    rni = float(cell["rni"])
    return np.asarray([strength, strength * rni], dtype=float)


def design_c2(cell: dict[str, Any]) -> np.ndarray:
    strength = float(cell["strength"])
    m1c = float(cell["m1_centered"])
    rni = float(cell["rni"])
    interaction = m1c * strength
    return np.asarray(
        [
            strength,
            strength * rni,
            m1c,
            m1c * rni,
            interaction,
            interaction * rni,
        ],
        dtype=float,
    )


def ridge_beta(X: np.ndarray, y: np.ndarray, alpha: float) -> np.ndarray:
    return np.linalg.solve(
        X.T @ X + float(alpha) * np.eye(X.shape[1], dtype=float),
        X.T @ y,
    )


def centered_predictions(
    cells: list[dict[str, Any]],
    beta: np.ndarray,
    design_fn: Callable[[dict[str, Any]], np.ndarray],
) -> dict[tuple[str, str], float]:
    raw = {
        (cell["party"], cell["territory_id"]): float(design_fn(cell) @ beta)
        for cell in cells
    }
    means = {
        party: float(
            np.mean(
                [
                    raw[(cell["party"], cell["territory_id"])]
                    for cell in cells
                    if cell["party"] == party
                ]
            )
        )
        for party in PARTY_ORDER
    }
    return {
        key: value - means[key[0]]
        for key, value in raw.items()
    }


def rmse(values: list[float] | np.ndarray) -> float:
    arr = np.asarray(values, dtype=float)
    return float(np.sqrt(np.mean(arr**2)))


def mae(values: list[float] | np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(values, dtype=float))))


def cv_select_alpha(
    cells: list[dict[str, Any]],
    design_fn: Callable[[dict[str, Any]], np.ndarray],
) -> tuple[float, list[dict[str, Any]]]:
    regions = sorted({cell["region"] for cell in cells})
    results: list[dict[str, Any]] = []

    for alpha in RIDGE:
        errors: list[float] = []
        folds: list[dict[str, Any]] = []
        for region in regions:
            train = [cell for cell in cells if cell["region"] != region]
            test = [cell for cell in cells if cell["region"] == region]
            if not test:
                continue
            X = np.stack([design_fn(cell) for cell in train])
            y = np.asarray([cell["y"] for cell in train], dtype=float)
            beta = ridge_beta(X, y, alpha)

            predictions = centered_predictions(cells, beta, design_fn)
            fold_errors = [
                predictions[(cell["party"], cell["territory_id"])] - cell["y"]
                for cell in test
            ]
            errors.extend(fold_errors)
            folds.append(
                {
                    "region": region,
                    "n": len(test),
                    "centered_residual_RMSE": rmse(fold_errors),
                }
            )

        results.append(
            {
                "alpha": alpha,
                "pooled_heldout_centered_residual_RMSE": rmse(errors),
                "folds": folds,
            }
        )

    selected = sorted(
        results,
        key=lambda row: (
            row["pooled_heldout_centered_residual_RMSE"],
            -row["alpha"],
        ),
    )[0]["alpha"]
    return float(selected), results


def fit_model(
    cells: list[dict[str, Any]],
    design_fn: Callable[[dict[str, Any]], np.ndarray],
    alpha: float,
) -> np.ndarray:
    X = np.stack([design_fn(cell) for cell in cells])
    y = np.asarray([cell["y"] for cell in cells], dtype=float)
    return ridge_beta(X, y, alpha)


def evaluation_rows(
    cells: list[dict[str, Any]],
    pred_c1: dict[tuple[str, str], float],
    pred_c2: dict[tuple[str, str], float],
    transition_moments: dict[str, dict[str, float]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        key = (cell["party"], cell["territory_id"])
        p0 = 0.0
        p1 = float(pred_c1[key])
        p2 = float(pred_c2[key])
        y = float(cell["y"])
        national_change = transition_moments[cell["party"]][
            "mean_raw_logit_change"
        ]

        share_c0 = float(
            logistic(cell["prior_logit"] + national_change + p0)
        )
        share_c1 = float(
            logistic(cell["prior_logit"] + national_change + p1)
        )
        share_c2 = float(
            logistic(cell["prior_logit"] + national_change + p2)
        )
        rows.append(
            {
                "party": cell["party"],
                "territory_id": cell["territory_id"],
                "region": cell["region"],
                "target_centered_logit_change": y,
                "pred_C0": p0,
                "pred_C1": p1,
                "pred_C2": p2,
                "err_C0": p0 - y,
                "err_C1": p1 - y,
                "err_C2": p2 - y,
                "prior_share": cell["prior_share"],
                "observed_share": cell["current_share"],
                "oracle_swing_share_C0": share_c0,
                "oracle_swing_share_C1": share_c1,
                "oracle_swing_share_C2": share_c2,
                "share_err_C0": share_c0 - cell["current_share"],
                "share_err_C1": share_c1 - cell["current_share"],
                "share_err_C2": share_c2 - cell["current_share"],
            }
        )
    return rows


def metric_pair(
    rows: list[dict[str, Any]],
    model_key: str,
    comparator_key: str,
) -> dict[str, float]:
    model = rmse([row[model_key] for row in rows])
    comparator = rmse([row[comparator_key] for row in rows])
    return {
        "model_RMSE": model,
        "comparator_RMSE": comparator,
        "relative_improvement": (
            (comparator - model) / comparator if comparator > 0 else 0.0
        ),
        "model_MAE": mae([row[model_key] for row in rows]),
        "comparator_MAE": mae([row[comparator_key] for row in rows]),
    }


def metric_block(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {
        "n": len(rows),
        "centered_residual": {
            "C1_vs_C0": metric_pair(rows, "err_C1", "err_C0"),
            "C2_vs_C1": metric_pair(rows, "err_C2", "err_C1"),
            "C2_vs_C0": metric_pair(rows, "err_C2", "err_C0"),
        },
        "oracle_national_swing_share": {
            "C1_vs_C0": metric_pair(rows, "share_err_C1", "share_err_C0"),
            "C2_vs_C1": metric_pair(rows, "share_err_C2", "share_err_C1"),
            "C2_vs_C0": metric_pair(rows, "share_err_C2", "share_err_C0"),
        },
        "by_party": {},
    }
    for party in PARTY_ORDER:
        party_rows = [row for row in rows if row["party"] == party]
        out["by_party"][party] = {
            "n": len(party_rows),
            "centered_residual_C2_vs_C1": metric_pair(
                party_rows, "err_C2", "err_C1"
            ),
            "oracle_national_swing_share_C2_vs_C1": metric_pair(
                party_rows, "share_err_C2", "share_err_C1"
            ),
        }
    return out


def cluster_bootstrap(
    rows: list[dict[str, Any]],
    model_key: str,
    comparator_key: str,
) -> dict[str, Any]:
    by_territory: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_territory[row["territory_id"]].append(row)

    territories = sorted(by_territory)
    rng = np.random.default_rng(SEED)
    deltas = np.empty(NBOOT, dtype=float)

    for i in range(NBOOT):
        sampled = rng.choice(territories, size=len(territories), replace=True)
        model_sq: list[float] = []
        comparator_sq: list[float] = []
        for territory_id in sampled:
            for row in by_territory[str(territory_id)]:
                model_sq.append(float(row[model_key]) ** 2)
                comparator_sq.append(float(row[comparator_key]) ** 2)
        deltas[i] = (
            float(np.sqrt(np.mean(model_sq)))
            - float(np.sqrt(np.mean(comparator_sq)))
        )

    return {
        "cluster": "territory_id",
        "clusters": len(territories),
        "replicates": NBOOT,
        "seed": SEED,
        "bootstrap_probability_model_better": float(np.mean(deltas < 0)),
        "percentile_95_interval_delta_model_minus_comparator": [
            float(np.quantile(deltas, 0.025)),
            float(np.quantile(deltas, 0.975)),
        ],
    }


def main() -> None:
    CI3.mkdir(parents=True, exist_ok=True)
    contract = read_json(CONTRACT)
    power = read_json(POWER)
    if power.get("status") != "PASS_MULTIPART_HEAD_POWER":
        raise RuntimeError(
            f"required V2 support gate is not PASS: {power.get('status')}"
        )
    if power.get("eligible_features") != [M1]:
        raise RuntimeError(
            f"unexpected eligible features: {power.get('eligible_features')}"
        )

    constituencies = hb.load_constituencies()
    constituency_meta = {
        row["constituency_id"]: row for row in constituencies
    }

    rows11 = local_rows(2011)
    rows16 = local_rows(2016)
    rows21 = local_rows(2021)
    map11 = hb.match_rows(constituencies, rows11)
    map16 = hb.match_rows(constituencies, rows16)
    map21 = hb.match_rows(constituencies, rows21)

    fit_cells = build_cells(
        D16, map11, map16, constituency_meta, "2011_TO_2016"
    )
    validation_cells = build_cells(
        D21, map16, map21, constituency_meta, "2016_TO_2021"
    )
    fit_moments = transform_transition(fit_cells)
    validation_moments = transform_transition(validation_cells)

    alpha_c1, cv_c1 = cv_select_alpha(fit_cells, design_c1)
    alpha_c2, cv_c2 = cv_select_alpha(fit_cells, design_c2)
    beta_c1 = fit_model(fit_cells, design_c1, alpha_c1)
    beta_c2 = fit_model(fit_cells, design_c2, alpha_c2)

    fit_pred_c1 = centered_predictions(fit_cells, beta_c1, design_c1)
    fit_pred_c2 = centered_predictions(fit_cells, beta_c2, design_c2)
    validation_pred_c1 = centered_predictions(
        validation_cells, beta_c1, design_c1
    )
    validation_pred_c2 = centered_predictions(
        validation_cells, beta_c2, design_c2
    )

    fit_rows = evaluation_rows(
        fit_cells, fit_pred_c1, fit_pred_c2, fit_moments
    )
    validation_rows = evaluation_rows(
        validation_cells,
        validation_pred_c1,
        validation_pred_c2,
        validation_moments,
    )
    fit_metrics = metric_block(fit_rows)
    validation_metrics = metric_block(validation_rows)

    bootstrap_c2_c1 = cluster_bootstrap(
        validation_rows, "err_C2", "err_C1"
    )
    bootstrap_c1_c0 = cluster_bootstrap(
        validation_rows, "err_C1", "err_C0"
    )

    candidate_comparison = validation_metrics["centered_residual"]["C2_vs_C1"]
    pooled_improvement = candidate_comparison["relative_improvement"]
    probability = bootstrap_c2_c1[
        "bootstrap_probability_model_better"
    ]
    party_improvements = {
        party: validation_metrics["by_party"][party][
            "centered_residual_C2_vs_C1"
        ]["relative_improvement"]
        for party in PARTY_ORDER
    }

    rule = contract["decision_rule"]["candidate_material_signal"]
    no_party_excess_deterioration = all(
        value >= -float(
            rule["maximum_allowed_party_specific_deterioration"]
        )
        for value in party_improvements.values()
    )
    material = (
        pooled_improvement
        >= float(rule["C2_vs_C1_relative_RMSE_improvement_min"])
        and probability
        >= float(rule["bootstrap_probability_C2_better_min"])
        and no_party_excess_deterioration
    )

    if material:
        interpretation = "MATERIAL_TRANSPORTABLE_CANDIDATE_SIGNAL"
        next_decision = (
            "JUSTIFY_NEW_PROSPECTIVE_2026_CANDIDATE_LAYER_SPECIFICATION"
        )
    elif pooled_improvement > 0:
        interpretation = "POSITIVE_BUT_NOT_MATERIAL_CANDIDATE_SIGNAL"
        next_decision = "NO_PROMOTION_RESEARCH_SIGNAL_ONLY"
    else:
        interpretation = "NO_TRANSPORTABLE_RETAINED_INCUMBENCY_SIGNAL"
        next_decision = (
            "STOP_RETAINED_INCUMBENCY_SPEC_NOT_GENERAL_CANDIDATE_KILL"
        )

    out = {
        "schema_version": "1.0",
        "result_id": (
            "M26-CANDIDATE-INTELLIGENCE-V3-SYMMETRIC-TERRITORIAL-GATE-V1"
        ),
        "contract_id": contract["contract_id"],
        "scientific_status": contract["scientific_status"],
        "prior_v2_general_kill_status": "SUPERSEDED_AS_OVERBROAD",
        "incremental_over_F0_identified": False,
        "oracle_national_swing_diagnostic": True,
        "2021_is_blind_holdout": False,
        "panel": {
            "fit_cells": len(fit_cells),
            "validation_cells": len(validation_cells),
            "fit_by_party": {
                party: sum(
                    cell["party"] == party for cell in fit_cells
                )
                for party in PARTY_ORDER
            },
            "validation_by_party": {
                party: sum(
                    cell["party"] == party
                    for cell in validation_cells
                )
                for party in PARTY_ORDER
            },
        },
        "transition_moments": {
            "2011_TO_2016": fit_moments,
            "2016_TO_2021": validation_moments,
        },
        "models": {
            "C1": {
                "alpha": alpha_c1,
                "beta_names": [
                    "centered_prior_logit_share",
                    "centered_prior_logit_share_x_RNI",
                ],
                "beta": [float(value) for value in beta_c1],
                "ridge_cv": cv_c1,
            },
            "C2": {
                "alpha": alpha_c2,
                "beta_names": [
                    "centered_prior_logit_share",
                    "centered_prior_logit_share_x_RNI",
                    "centered_retained_incumbent",
                    "centered_retained_incumbent_x_RNI",
                    (
                        "centered_retained_incumbent_x_"
                        "centered_prior_strength"
                    ),
                    (
                        "centered_retained_incumbent_x_"
                        "centered_prior_strength_x_RNI"
                    ),
                ],
                "beta": [float(value) for value in beta_c2],
                "ridge_cv": cv_c2,
            },
        },
        "fit_2011_TO_2016": fit_metrics,
        "validation_2016_TO_2021": validation_metrics,
        "cluster_bootstrap": {
            "C2_vs_C1_centered_residual_RMSE": bootstrap_c2_c1,
            "C1_vs_C0_centered_residual_RMSE": bootstrap_c1_c0,
        },
        "candidate_material_gate": {
            "pooled_relative_improvement": pooled_improvement,
            "bootstrap_probability_C2_better": probability,
            "party_relative_improvements": party_improvements,
            "no_party_deterioration_beyond_limit": (
                no_party_excess_deterioration
            ),
            "pass": material,
        },
        "terminal_interpretation": interpretation,
        "terminal_decision": next_decision,
        "f0_modified": False,
        "llm_invoked": False,
        "seat_level_claim": False,
    }
    OUT.write_text(
        json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    certificate = {
        "schema_version": "1.0",
        "certificate_id": (
            "M26-CANDIDATE-INTELLIGENCE-V3-TERMINAL-CERTIFICATE-V1"
        ),
        "contract_id": contract["contract_id"],
        "prior_v2_terminal_kill": (
            "SUPERSEDED_AS_OVERBROAD_PRESERVE_NUMERIC_RESULT"
        ),
        "corrected_test": (
            "SYMMETRIC_NATIONAL_SWING_CONDITIONED_TERRITORIAL_DIAGNOSTIC"
        ),
        "incremental_over_F0_identified": False,
        "power_support_status": power["status"],
        "fit_cells": len(fit_cells),
        "validation_cells": len(validation_cells),
        "candidate_material_gate": out["candidate_material_gate"],
        "terminal_interpretation": interpretation,
        "terminal_decision": next_decision,
        "f0_modified": False,
        "llm_invoked": False,
        "2021_blind_status": "RETROSPECTIVE_NOT_BLIND",
        "next_action": (
            "If material, freeze a separate prospective 2026 local "
            "candidate-layer protocol. If not material, stop this retained-"
            "incumbency specification without generalizing to all candidate "
            "intelligence. A true incremental-over-F0 test still requires a "
            "symmetric historical F0/pseudo-F0 design."
        ),
    }
    CERT.write_text(
        json.dumps(
            certificate, ensure_ascii=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )

    print(
        json.dumps(
            {
                "terminal_interpretation": interpretation,
                "terminal_decision": next_decision,
                "fit_cells": len(fit_cells),
                "validation_cells": len(validation_cells),
                "C1_vs_C0_relative": validation_metrics[
                    "centered_residual"
                ]["C1_vs_C0"]["relative_improvement"],
                "C2_vs_C1_relative": pooled_improvement,
                "C2_vs_C1_probability": probability,
                "party_relative_improvements": party_improvements,
                "incremental_over_F0_identified": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
