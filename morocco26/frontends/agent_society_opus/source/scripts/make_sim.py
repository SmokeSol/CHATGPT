# -*- coding: utf-8 -*-
"""
Build the data pack for the in-page decision demonstrator.

Ships (a) one real, fully anonymous territory context digested into numbers,
(b) 150 baseline signal vectors covering age x milieu x niveau de vie x situation,
(c) reference outputs from the Python engine so the browser port can self-check.
"""
import io
import json
import os
import sys
import statistics

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_engine as JE

ENV = sys.argv[1]
DEST = sys.argv[2]

AGES = ["18_24", "25_34", "35_44", "45_59", "60_PLUS"]
MIL = ["URBAN", "RURAL"]
QV = [0.2, 0.4, 0.6, 0.8, 1.0]
ACT = ["ACTIVE_EMPLOYED", "UNEMPLOYED", "INACTIVE"]

SIG_KEYS = None


def pick_context():
    wm = json.load(io.open(os.path.join(ENV, "work_manifest.json"), encoding="utf-8"))
    cands = []
    seen = set()
    for it in wm["work_items"]:
        cp = it["context_path"]
        if cp in seen:
            continue
        seen.add(cp)
        ctx = json.load(io.open(os.path.join(ENV, cp), encoding="utf-8"))
        prep = JE.prepare_context(ctx)
        nloc = sum(1 for v in prep["loc"].values() if abs(v) > 0.01)
        cands.append((abs(prep["prev_turnout"] - 0.47), -nloc, cp, ctx, prep))
    cands.sort(key=lambda x: (x[1], x[0]))
    return cands[0][2], cands[0][3], cands[0][4]


def median_signals():
    """Population-median signal vector, computed over every archetype card."""
    wm = json.load(io.open(os.path.join(ENV, "work_manifest.json"), encoding="utf-8"))
    seen, acc = set(), {}
    n = 0
    for it in wm["work_items"]:
        bp = it["voter_batch_path"]
        if bp in seen:
            continue
        seen.add(bp)
        b = json.load(io.open(os.path.join(ENV, bp), encoding="utf-8"))
        for v in b["voter_archetypes"]:
            s = JE.voter_signals(v)
            for k, x in s.items():
                acc.setdefault(k, []).append(x)
            n += 1
    return {k: round(statistics.median(vs), 6) for k, vs in acc.items()}


def apply_controls(base, age, mil, qv, act, conf=None, bil=None):
    s = dict(base)
    s["young"] = 1.0 if age == "18_24" else (0.6 if age == "25_34" else 0.0)
    s["old"] = 1.0 if age == "60_PLUS" else (0.35 if age == "45_59" else 0.0)
    s["age"] = {"18_24": 21.0, "25_34": 29.0, "35_44": 39.0, "45_59": 51.0, "60_PLUS": 68.0}[age]
    s["children"] = {"18_24": 0.15, "25_34": 0.45, "35_44": 0.70, "45_59": 0.40, "60_PLUS": 0.15}[age]
    s["students"] = {"18_24": 0.45, "25_34": 0.35, "35_44": 0.55, "45_59": 0.40, "60_PLUS": 0.15}[age]
    s["elderly"] = {"18_24": 0.10, "25_34": 0.10, "35_44": 0.15, "45_59": 0.25, "60_PLUS": 0.75}[age]
    s["edu_rank"] = {"18_24": 0.52, "25_34": 0.46, "35_44": 0.34, "45_59": 0.22, "60_PLUS": 0.08}[age]
    s["net_use"] = {"18_24": 0.88, "25_34": 0.78, "35_44": 0.56, "45_59": 0.30, "60_PLUS": 0.10}[age]
    s["illit"] = {"18_24": 0.06, "25_34": 0.14, "35_44": 0.30, "45_59": 0.48, "60_PLUS": 0.72}[age]

    rural = 1.0 if mil == "RURAL" else 0.0
    s["rural"] = rural
    s["rural_known"] = 1.0
    s["services"] = 0.60 if rural else 0.82
    s["road_known"] = rural
    s["road_far"] = 0.32 * rural
    s["water_known"] = rural
    s["water_far"] = 0.30 * rural
    s["water_unpiped"] = 0.65 * rural
    s["no_sewer"] = 0.70 * rural
    s["biomass_cook"] = 0.45 * rural
    s["agri"] = 0.55 * rural
    s["renter"] = 0.06 if rural else 0.20
    s["internet"] = 0.10 if rural else 0.26
    s["computer"] = 0.12 if rural else 0.32

    s["ses"] = qv
    s["quint"] = qv
    s["milieu"] = qv
    s["asset"] = 0.18 + 0.55 * qv
    s["food_share"] = 0.58 - 0.24 * qv
    s["med_share"] = 0.015 + 0.045 * qv
    s["edu_share"] = 0.004 + 0.030 * qv
    s["rent_share"] = 0.09 + 0.07 * qv
    s["cult_share"] = 0.005 + 0.045 * qv
    s["leisure_share"] = max(0.0, 0.055 * (qv - 0.4))
    s["credit_share"] = max(0.0, 0.030 * (qv - 0.4))
    s["poverty"] = 1.0 if qv <= 0.2 else 0.0
    s["vuln"] = 1.0 if qv <= 0.4 else 0.0
    s["crowd"] = 0.72 - 0.45 * qv
    s["cash_dep"] = 0.42 - 0.20 * qv
    s["food_dep"] = 0.16 - 0.11 * qv
    s["econ_cond"] = 0.46 + 0.19 * qv
    s["living"] = 0.44 + 0.20 * qv

    s["unemployed"] = 1.0 if act == "UNEMPLOYED" else 0.0
    s["employed"] = 1.0 if act == "ACTIVE_EMPLOYED" else 0.0
    s["inactive"] = 1.0 if act == "INACTIVE" else 0.0
    s["hh_unemp"] = 0.55 if act == "UNEMPLOYED" else 0.12
    s["famhelp"] = 0.20 if act == "ACTIVE_EMPLOYED" and rural else 0.0
    s["selfemp"] = 0.35 if act == "ACTIVE_EMPLOYED" else 0.0
    s["privemp"] = 0.40 if act == "ACTIVE_EMPLOYED" else 0.0
    s["pubemp"] = 0.12 if act == "ACTIVE_EMPLOYED" else 0.0
    s["indus"] = 0.22 if act == "ACTIVE_EMPLOYED" else 0.0
    s["commerce"] = 0.18 if act == "ACTIVE_EMPLOYED" else 0.0
    s["constr"] = 0.16 if act == "ACTIVE_EMPLOYED" else 0.0
    s["pubsec"] = 0.10 if act == "ACTIVE_EMPLOYED" else 0.0

    s["hardship"] = JE._clip(
        0.24 * (1.0 - s["ses"]) + 0.18 * (1.0 - s["asset"]) + 0.14 * (1.0 - s["services"])
        + 0.16 * JE._clip((s["food_share"] - 0.25) / 0.45, 0, 1) + 0.10 * s["crowd"]
        + 0.10 * s["poverty"] + 0.08 * s["vuln"], 0.0, 1.0)

    if conf is not None:
        apply_conf(s, conf)
    if bil is not None:
        apply_bil(s, bil)
    return s


def apply_conf(s, c):
    """c in [0,1] : confiance dans les institutions."""
    s["trust_parl"] = 0.16 + 0.50 * c
    s["trust_loc"] = 0.18 + 0.46 * c
    s["trust"] = 0.5 * (s["trust_parl"] + s["trust_loc"])
    s["resp_loc"] = 0.05 + 0.42 * c
    s["corr_loc"] = 0.62 - 0.34 * c
    s["corr_mp"] = 0.65 - 0.35 * c
    s["corruption"] = 0.5 * (s["corr_loc"] + s["corr_mp"])


def apply_bil(s, b):
    """b in [0,1] : jugement porte sur le bilan du gouvernement sortant."""
    s["gov_econ"] = 0.21 + 0.37 * b
    s["gov_pov"] = 0.15 + 0.31 * b
    s["gov_anti"] = 0.14 + 0.44 * b
    s["dem_sat"] = 0.37 + 0.46 * b


def digest(ctx, prep):
    parties = prep["parties"]
    sal = prep["sal"]
    levels = {}
    for q in parties:
        d = dict((a, None) for a in JE.PROGRAM_AXES)
        for a, sc in prep["known_levels"][q]:
            d[a] = sc
        levels[q] = [d[a] for a in JE.PROGRAM_AXES]
    return {
        "axes": JE.PROGRAM_AXES,
        "parties": parties,
        "sal": [round(sal[a], 6) for a in JE.PROGRAM_AXES],
        "levels": levels,
        "gov": [prep["gov_status"][q] for q in parties],
        "logshare": [round(prep["log_share"][q], 6) for q in parties],
        "share": [round(math_exp(prep["log_share"][q] / JE.B_PRIOR_SHARE), 6) for q in parties],
        "loc": [round(prep["loc"].get(q, 0.0), 6) for q in parties],
        "locmass": [round(prep["loc_mass"].get(q, 0.0), 6) for q in parties],
        "ncomp": prep["ncomp"],
        "prevturnout": round(prep["prev_turnout"], 6),
        "pressures": ctx["election_environment_card"]["national_issue_pressures"],
        "territoire": ctx["anonymous_territory_id"][:8],
    }


def math_exp(x):
    import math
    return math.exp(x)


def main():
    cp, ctx, prep = pick_context()
    sys.stderr.write("sim context: %s (prev turnout %.4f)\n" % (cp, prep["prev_turnout"]))
    med = median_signals()

    base = {}
    for a in AGES:
        for m in MIL:
            for q in QV:
                for ac in ACT:
                    s = apply_controls(med, a, m, q, ac)
                    base["%s|%s|%.1f|%s" % (a, m, q, ac)] = s

    keys = sorted(base[list(base)[0]].keys())
    packed = {k: [round(v[kk], 6) for kk in keys] for k, v in base.items()}

    # reference outputs from the authoritative Python engine
    refs = []
    combos = [("18_24", "URBAN", 1.0, "ACTIVE_EMPLOYED", 0.15, 0.15, "ABSTAIN"),
              ("18_24", "RURAL", 0.2, "UNEMPLOYED", 0.10, 0.10, "ABSTAIN"),
              ("25_34", "URBAN", 0.6, "ACTIVE_EMPLOYED", 0.50, 0.50, "Q_03"),
              ("35_44", "RURAL", 0.4, "INACTIVE", 0.35, 0.30, "Q_01"),
              ("45_59", "URBAN", 0.8, "ACTIVE_EMPLOYED", 0.75, 0.80, "Q_05"),
              ("60_PLUS", "RURAL", 0.2, "INACTIVE", 0.90, 0.95, "Q_08"),
              ("60_PLUS", "URBAN", 1.0, "INACTIVE", 0.60, 0.55, "ABSTAIN"),
              ("35_44", "URBAN", 0.4, "UNEMPLOYED", 0.05, 0.05, "Q_02"),
              ("45_59", "RURAL", 0.6, "ACTIVE_EMPLOYED", 0.45, 0.65, "ABSTAIN"),
              ("25_34", "RURAL", 1.0, "INACTIVE", 1.00, 0.00, "Q_07"),
              ("18_24", "URBAN", 0.2, "INACTIVE", 0.00, 1.00, "Q_09"),
              ("60_PLUS", "URBAN", 0.6, "ACTIVE_EMPLOYED", 0.55, 0.45, "Q_04")]
    for (a, m, q, ac, cf, bl, pv) in combos:
        s = apply_controls(med, a, m, q, ac, cf, bl)
        row = score_from_signals(s, ctx, prep, pv, a)
        refs.append({"ctl": [a, m, q, ac, cf, bl, pv],
                     "part": row["turnout_probability"],
                     "pp": [round(row["conditional_party_probabilities"][x], 6) for x in prep["parties"]],
                     "fa": [round(row["factor_importance"][f], 6) for f in JE.FACTORS],
                     "rc": row["reason_codes"]})

    out = {
        "sigkeys": keys,
        "base": packed,
        "ctx": digest(ctx, prep),
        "facteurs": JE.FACTORS,
        "coef": {"share": JE.B_PRIOR_SHARE, "vote": JE.B_PRIOR_VOTE, "fit": JE.B_FIT,
                 "gov": JE.B_GOV, "loc": JE.B_LOC, "eps": JE.EPS_MIX},
        "breadth": JE.FACTOR_BREADTH,
        "bucket": JE.AXIS_BUCKET,
        "ref": refs,
    }
    if not os.path.isdir(DEST):
        os.makedirs(DEST)
    with open(os.path.join(DEST, "simulateur.json"), "wb") as f:
        f.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sys.stderr.write("simulateur.json %.1f KB\n" % (os.path.getsize(os.path.join(DEST, "simulateur.json")) / 1024.0))


def score_from_signals(s, ctx, prep, prior, age_band):
    """Run the authoritative engine from a signal vector (bypasses voter_signals)."""
    import types
    fake = {"prior_vote_or_abstention": prior, "age_band": age_band,
            "weighted_archetype_id": "A001"}
    orig = JE.voter_signals
    JE.voter_signals = lambda v: s
    try:
        r = JE.score_voter(fake, ctx, {"anonymous_election_id": ctx["anonymous_election_id"],
                                       "anonymous_territory_id": ctx["anonymous_territory_id"],
                                       "condition_id": ctx["condition_id"],
                                       "batch_id": "B01"}, prep)
    finally:
        JE.voter_signals = orig
    return r


if __name__ == "__main__":
    main()
