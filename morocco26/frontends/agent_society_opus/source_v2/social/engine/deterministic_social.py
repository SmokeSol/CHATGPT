# -*- coding: utf-8 -*-
"""Deterministic social influence baseline.

The update is synchronous: every R(k+1) decision is computed exclusively from
the complete frozen R(k) state.  No agent can observe another agent's new
decision early.

Party updates use bounded logarithmic opinion pooling.  Turnout uses the same
principle in log-odds space.  lambda=0 is an exact identity on the decision
fields by construction.
"""
from __future__ import division
import copy
import math

try:
    from .common import (
        EPS, RELATIONS, clip, ensure_rows_align, entropy01, logit, normalize,
        party_keys, sigmoid,
    )
except ImportError:
    from common import (
        EPS, RELATIONS, clip, ensure_rows_align, entropy01, logit, normalize,
        party_keys, sigmoid,
    )


def _weighted_party_exposure(rows, edges, keys):
    if not edges:
        return None
    acc = {k: 0.0 for k in keys}
    mass = 0.0
    for edge in edges:
        w = float(edge["w"])
        p = rows[edge["i"]]["conditional_party_probabilities"]
        for k in keys:
            acc[k] += w * float(p[k])
        mass += w
    if mass <= 0:
        return None
    return normalize({k: acc[k] / mass for k in keys})


def _weighted_turnout_exposure(rows, edges):
    if not edges:
        return None
    total = 0.0
    mass = 0.0
    for edge in edges:
        w = float(edge["w"])
        total += w * float(rows[edge["i"]]["turnout_probability"])
        mass += w
    return None if mass <= 0 else clip(total / mass, 1e-9, 1.0 - 1e-9)


def _party_susceptibility(p):
    # Certain choices resist social pressure; diffuse choices are more open.
    return 0.12 + 0.88 * entropy01(p)


def _turnout_susceptibility(t):
    # Participation close to 0.5 is easiest to move; near-certain states resist.
    ambiguity = 1.0 - min(1.0, 2.0 * abs(float(t) - 0.5))
    return 0.18 + 0.82 * ambiguity


def _pool_party(self_p, relation_exposure, lambdas):
    keys = tuple(sorted(self_p))
    current = normalize(self_p)
    sus = _party_susceptibility(current)
    total_lambda = sum(max(0.0, float(lambdas.get(r, 0.0)))
                       for r in RELATIONS if relation_exposure.get(r) is not None)
    if total_lambda <= 0:
        return dict(self_p), sus
    # Avoid allowing one social round to erase private information.
    scale = min(0.92, total_lambda) / total_lambda
    scores = {}
    for k in keys:
        lp = math.log(max(EPS, float(current[k])))
        delta = 0.0
        for relation in RELATIONS:
            exp = relation_exposure.get(relation)
            if exp is None:
                continue
            lam = max(0.0, float(lambdas.get(relation, 0.0))) * scale
            delta += lam * (
                math.log(max(EPS, float(exp[k]))) - lp
            )
        scores[k] = math.exp(lp + sus * delta)
    return normalize(scores), sus


def _pool_turnout(self_t, relation_exposure, lambdas):
    t = clip(float(self_t), 1e-9, 1.0 - 1e-9)
    sus = _turnout_susceptibility(t)
    total_lambda = sum(max(0.0, float(lambdas.get(r, 0.0)))
                       for r in RELATIONS if relation_exposure.get(r) is not None)
    if total_lambda <= 0:
        return float(self_t), sus
    scale = min(0.92, total_lambda) / total_lambda
    base = logit(t)
    delta = 0.0
    for relation in RELATIONS:
        exp = relation_exposure.get(relation)
        if exp is None:
            continue
        lam = max(0.0, float(lambdas.get(relation, 0.0))) * scale
        delta += lam * (logit(exp) - base)
    return sigmoid(base + sus * delta), sus


def exposure_snapshot(rows, graph, source_i):
    keys = party_keys(rows)
    node = graph["nodes"][source_i]
    parties = {}
    turnout = {}
    for relation in RELATIONS:
        edges = node["relations"].get(relation, [])
        parties[relation] = _weighted_party_exposure(rows, edges, keys)
        turnout[relation] = _weighted_turnout_exposure(rows, edges)
    return parties, turnout


def update_round(rows, graph, lambdas, round_name="R1", enabled_relations=None):
    ensure_rows_align(rows, graph)
    enabled = set(enabled_relations or RELATIONS)
    lam = {r: (float(lambdas.get(r, 0.0)) if r in enabled else 0.0) for r in RELATIONS}
    next_rows = []

    # Synchronous contract: all exposures are read from `rows`, never next_rows.
    for i, row in enumerate(rows):
        party_exp, turnout_exp = exposure_snapshot(rows, graph, i)
        new_p, p_sus = _pool_party(row["conditional_party_probabilities"], party_exp, lam)
        new_t, t_sus = _pool_turnout(row["turnout_probability"], turnout_exp, lam)

        out = copy.deepcopy(row)
        old_p = row["conditional_party_probabilities"]
        old_t = float(row["turnout_probability"])
        out["conditional_party_probabilities"] = new_p
        out["turnout_probability"] = new_t

        relation_meta = {}
        for r in RELATIONS:
            relation_meta[r] = {
                "lambda": lam[r],
                "contacts": len(graph["nodes"][i]["relations"].get(r, [])),
                "party_exposure": party_exp[r],
                "turnout_exposure": turnout_exp[r],
            }

        shift_l1 = sum(abs(float(new_p[k]) - float(old_p[k])) for k in new_p)
        out["social_influence"] = {
            "schema_version": "ATLAS_SOCIAL_DECISION_V1",
            "round": round_name,
            "synchronous": True,
            "private_state_preserved_as_anchor": True,
            "party_susceptibility": p_sus,
            "turnout_susceptibility": t_sus,
            "party_shift_l1": shift_l1,
            "turnout_shift": new_t - old_t,
            "relations": relation_meta,
        }
        next_rows.append(out)
    return next_rows


def run_condition(baseline_rows, graph, condition, lambdas):
    """Run one pre-registered ablation condition.

    ISO       : exact baseline copy
    FAM       : family R1 only
    WORK      : work R1 only
    NEIGH     : neighborhood R1 only
    ALL       : all three relations at R1
    ALL_R2    : all three R1 followed synchronously by all three R2
    """
    condition = condition.upper()
    if condition == "ISO":
        return copy.deepcopy(baseline_rows)
    relation_map = {
        "FAM": ("family",),
        "WORK": ("work",),
        "NEIGH": ("neighborhood",),
        "ALL": RELATIONS,
        "ALL_R2": RELATIONS,
    }
    if condition not in relation_map:
        raise ValueError("unsupported social condition %r" % condition)
    enabled = relation_map[condition]
    r1 = update_round(baseline_rows, graph, lambdas, "R1", enabled)
    if condition == "ALL_R2":
        return update_round(r1, graph, lambdas, "R2", enabled)
    return r1


def max_decision_delta(a, b):
    if len(a) != len(b):
        return float("inf")
    mx = 0.0
    for ra, rb in zip(a, b):
        mx = max(mx, abs(float(ra["turnout_probability"]) - float(rb["turnout_probability"])))
        keys = set(ra["conditional_party_probabilities"]) | set(rb["conditional_party_probabilities"])
        for k in keys:
            mx = max(mx, abs(float(ra["conditional_party_probabilities"].get(k, 0.0))
                             - float(rb["conditional_party_probabilities"].get(k, 0.0))))
    return mx
