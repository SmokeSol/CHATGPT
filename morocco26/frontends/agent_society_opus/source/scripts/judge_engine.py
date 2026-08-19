# -*- coding: utf-8 -*-
"""
Deterministic reference implementation of the frozen judge prompt
`as2_full_environment_prompt_v2.md` (sha256 a2561eb0...) for EXP_7C8A2F11 / ENV_4D19B3E7.

The engine consumes ONLY:
  * the supplied voter archetype card,
  * the supplied party offer cards + national issue pressures,
  * the supplied territory party-context cards + previous-election shares/turnout.

No outside information, no target outcomes, no cross-archetype borrowing, no
condition-role inference. MISSING / UNKNOWN / NOT_FOUND / UNVERIFIED /
DATA_BLOCKED / AMBIGUOUS are treated as non-evidence. A `conflict` flag makes a
local feature non-directional.

Output: one dict per archetype conforming to FULL_ENV_OUTPUT_SCHEMA_V2.
"""
import math

NON_EVIDENCE = {"MISSING", "NOT_FOUND", "UNVERIFIED", "DATA_BLOCKED", "AMBIGUOUS", "UNKNOWN", None, ""}

PROGRAM_AXES = [
    "civil_liberties", "culture", "decentralization", "digital_transition",
    "economic_sovereignty", "education", "employment", "environment_transition",
    "fiscal_relief", "gender_equality", "governance_rule_of_law", "health",
    "housing", "industrial_competitiveness", "private_investment_sme",
    "public_state_role", "rural_territorial_equity", "social_protection",
]

# LOW = "not established as salient in collected evidence; NOT policy opposition".
# Hence LOW is a *weak* fit signal, never a negative one.
LEVEL_SCORE = {"HIGH": 1.00, "MEDIUM": 0.55, "LOW": 0.25}

# National issue pressure -> program axis salience transfer.
PRESSURE_MAP = {
    "employment_stress":                     {"employment": 1.0, "private_investment_sme": 0.40, "industrial_competitiveness": 0.40},
    "youth_employment_stress":               {"employment": 0.60, "education": 0.25, "digital_transition": 0.20},
    "economic_activity_stress":              {"fiscal_relief": 0.60, "industrial_competitiveness": 0.60, "private_investment_sme": 0.60, "economic_sovereignty": 0.40},
    "fiscal_stability_salience":             {"fiscal_relief": 0.80, "public_state_role": 0.30},
    "social_protection_transition_salience": {"social_protection": 1.0, "health": 0.30},
    "health_service_pressure":               {"health": 1.0},
    "education_service_pressure":            {"education": 1.0},
    "governance_reform_salience":            {"governance_rule_of_law": 1.0, "civil_liberties": 0.40, "decentralization": 0.30},
    "territorial_inequality_salience":       {"rural_territorial_equity": 0.80, "decentralization": 0.60, "housing": 0.20},
    "agriculture_rural_stress":              {"rural_territorial_equity": 0.70, "environment_transition": 0.30},
    "environment_water_salience":            {"environment_transition": 1.0},
    "digital_transition_salience":           {"digital_transition": 1.0},
}
PRESSURE_LEVEL = {"HIGH": 1.30, "MEDIUM": 1.00, "LOW": 0.72}

# Program axis -> closed factor bucket used by the factor_importance decomposition.
AXIS_BUCKET = {
    "employment": "employment_and_income",
    "private_investment_sme": "employment_and_income",
    "industrial_competitiveness": "employment_and_income",
    "social_protection": "social_protection_and_public_services",
    "health": "social_protection_and_public_services",
    "education": "social_protection_and_public_services",
    "housing": "social_protection_and_public_services",
    "governance_rule_of_law": "governance_and_institutions",
    "civil_liberties": "governance_and_institutions",
    "decentralization": "governance_and_institutions",
    "rural_territorial_equity": "territorial_rural_fit",
    "fiscal_relief": "personal_economic_conditions",
    "economic_sovereignty": "personal_economic_conditions",
    "digital_transition": "policy_program_fit",
    "environment_transition": "policy_program_fit",
    "culture": "policy_program_fit",
    "gender_equality": "policy_program_fit",
    "public_state_role": "policy_program_fit",
}

FACTORS = [
    "prior_vote_inertia", "turnout_habit", "personal_economic_conditions",
    "employment_and_income", "social_protection_and_public_services",
    "policy_program_fit", "governance_and_institutions", "territorial_rural_fit",
    "government_reward_punishment", "local_candidate_context", "other_verified_context",
]

# Number of programme axes each closed factor aggregates. Used ONLY to normalise
# reason-code ranking for block breadth, never to change the numerical decision.
FACTOR_BREADTH = {
    "employment_and_income": 3, "social_protection_and_public_services": 4,
    "policy_program_fit": 5, "governance_and_institutions": 3,
    "territorial_rural_fit": 1, "personal_economic_conditions": 2,
}

FACTOR_CODE = {
    "prior_vote_inertia": "PRIOR_VOTE_INERTIA",
    "turnout_habit": "TURNOUT_HABIT",
    "personal_economic_conditions": "ECONOMIC_SELF_INTEREST",
    "employment_and_income": "EMPLOYMENT_INCOME_FIT",
    "social_protection_and_public_services": "SOCIAL_PROTECTION_PUBLIC_SERVICES_FIT",
    "policy_program_fit": "POLICY_PROGRAM_FIT",
    "governance_and_institutions": "GOVERNANCE_INSTITUTIONAL_FIT",
    "territorial_rural_fit": "TERRITORIAL_RURAL_FIT",
    "government_reward_punishment": "GOVERNMENT_REWARD",
    "local_candidate_context": "LOCAL_CANDIDATE_STRENGTH",
    "other_verified_context": "OTHER_VERIFIED_CONTEXT",
}

# ---------------------------------------------------------------- coefficients
B_PRIOR_SHARE = 0.80   # territorial previous-election structure (log-share anchor)
B_PRIOR_VOTE = 1.80    # individual prior-vote loyalty (informative, not deterministic)
B_FIT = 6.20           # program-offer fit
B_GOV = 3.60           # incumbency reward / punishment
B_LOC = 2.20           # verified local candidate context
EPS_MIX = 0.020        # uniform mixture: calibrated residual uncertainty


def _f(v, default=None):
    if v is None or isinstance(v, bool):
        return default
    if isinstance(v, (int, float)):
        return float(v)
    return default


def _clip(x, lo, hi):
    return lo if x < lo else (hi if x > hi else x)


def _logit(p):
    p = _clip(p, 1e-6, 1 - 1e-6)
    return math.log(p / (1.0 - p))


def _sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _std(vals):
    n = len(vals)
    if n < 2:
        return 0.0
    m = sum(vals) / n
    return math.sqrt(sum((v - m) ** 2 for v in vals) / n)


# ------------------------------------------------------------ voter indicators
def voter_signals(v):
    """Bounded indicators derived strictly from supplied fields."""
    s = {}
    g = v.get

    n_str = _f(g("attitude_posterior_stratum_n"), 25.0) or 25.0
    s["conf_n"] = n_str / (n_str + 30.0)

    def att(name, default=0.5):
        m = _f(g("latent_attitude_%s_mean" % name), default)
        sd = _f(g("latent_attitude_%s_sd" % name), 0.25)
        if m is None:
            m = default
        if sd is None:
            sd = 0.25
        conf = _clip(1.15 - sd, 0.55, 1.0) * _clip(0.70 + 0.30 * s["conf_n"], 0.70, 1.0)
        return m, conf

    s["econ_cond"], s["c_econ"] = att("economic_condition", 0.55)
    s["living"], s["c_living"] = att("living_conditions", 0.54)
    s["cash_dep"], s["c_cash"] = att("cash_deprivation", 0.28)
    s["food_dep"], s["c_food"] = att("food_deprivation", 0.08)
    s["water_dep"], s["c_water"] = att("water_deprivation", 0.10)
    s["gov_econ"], s["c_gecon"] = att("government_economic_performance", 0.42)
    s["gov_pov"], s["c_gpov"] = att("government_poverty_performance", 0.32)
    s["gov_anti"], s["c_ganti"] = att("government_anticorruption_performance", 0.39)
    s["trust_parl"], s["c_tparl"] = att("trust_parliament", 0.37)
    s["trust_loc"], s["c_tloc"] = att("trust_local_government", 0.40)
    s["resp_loc"], s["c_resp"] = att("local_responsiveness", 0.23)
    s["corr_loc"], s["c_cloc"] = att("perceived_local_corruption", 0.44)
    s["corr_mp"], s["c_cmp"] = att("perceived_mp_corruption", 0.43)
    s["dem_sat"], s["c_dsat"] = att("democracy_satisfaction", 0.66)
    s["dem_sup"], s["c_dsup"] = att("democracy_support", 0.83)
    s["discuss"], s["c_disc"] = att("political_discussion", 0.38)
    s["net_use"], s["c_net"] = att("internet_use", 0.52)

    s["corruption"] = 0.5 * (s["corr_loc"] + s["corr_mp"])
    s["trust"] = 0.5 * (s["trust_parl"] + s["trust_loc"])
    s["c_att"] = (s["c_gecon"] + s["c_tparl"] + s["c_disc"] + s["c_cloc"]) / 4.0

    s["ses"] = _f(g("latent_ses_decile"), 0.5) or 0.5
    s["quint"] = _f(g("latent_national_quintile"), 0.6) or 0.6
    s["milieu"] = _f(g("latent_within_milieu_decile"), 0.5) or 0.5
    s["poverty"] = _f(g("latent_poverty_risk"), 0.0) or 0.0
    s["vuln"] = _f(g("latent_vulnerability_risk"), 0.0) or 0.0
    s["asset"] = _f(g("asset_index"), 0.45) or 0.45
    s["services"] = _f(g("basic_services_index"), 0.72) or 0.72
    s["food_share"] = _f(g("latent_food_budget_share"), 0.42) or 0.42
    s["med_share"] = _f(g("latent_medical_budget_share"), 0.03) or 0.03
    s["edu_share"] = _f(g("latent_education_budget_share"), 0.01) or 0.01
    s["rent_share"] = _f(g("latent_rent_charges_budget_share"), 0.12) or 0.12
    s["util_share"] = _f(g("latent_utilities_budget_share"), 0.07) or 0.07
    s["leisure_share"] = _f(g("latent_leisure_budget_share"), 0.0) or 0.0
    s["cult_share"] = _f(g("latent_education_culture_budget_share"), 0.02) or 0.02
    s["transp_share"] = _f(g("latent_transport_budget_share"), 0.03) or 0.03
    s["credit_share"] = _f(g("latent_credit_repayment_budget_share"), 0.0) or 0.0
    s["exp_pp_log"] = _f(g("latent_household_expenditure_per_person_log"), 9.4) or 9.4

    act = g("activity_status")
    s["unemployed"] = 1.0 if act == "UNEMPLOYED" else 0.0
    s["employed"] = 1.0 if act == "ACTIVE_EMPLOYED" else 0.0
    s["inactive"] = 1.0 if act == "INACTIVE" else 0.0
    hu = _f(g("household_unemployed_count"), 0.0) or 0.0
    hsz = max(1.0, _f(g("household_size"), 5.0) or 5.0)
    s["hh_unemp"] = _clip(hu / hsz * 3.0, 0.0, 1.0)
    hw = _f(g("household_worker_count"), 0.0) or 0.0
    s["hh_work"] = _clip(hw / hsz * 2.0, 0.0, 1.0)
    prof = g("professional_status")
    s["selfemp"] = 1.0 if prof in ("Indépendant", "Employeur / Membre d'une coopérative") else 0.0
    if not s["selfemp"] and g("latent_head_professional_status") in ("SELF_EMPLOYED", "EMPLOYER"):
        s["selfemp"] = 0.55
    s["pubemp"] = 1.0 if prof == "Salarié du secteur public" else 0.0
    s["privemp"] = 1.0 if prof == "Salarié du secteur privé" else 0.0
    s["famhelp"] = 1.0 if prof == "Aide familial / Apprenti" else 0.0

    sec = g("industry_sector") or ""
    hsec = g("latent_head_industry_sector") or ""
    s["agri"] = 1.0 if sec.startswith("Agriculture") else (0.6 if hsec == "AGRICULTURE_FISHING_FORESTRY" else 0.0)
    ls = g("livestock_status") or ""
    if ls.startswith("Utilisées"):
        s["agri"] = max(s["agri"], 0.5)
    s["indus"] = 1.0 if sec.startswith("Industries") else (0.5 if hsec == "INDUSTRY" else 0.0)
    s["commerce"] = 1.0 if sec.startswith("Commerce") else (0.5 if hsec == "COMMERCE" else 0.0)
    s["constr"] = 1.0 if sec.startswith("Construction") else (0.5 if hsec == "CONSTRUCTION" else 0.0)
    s["pubsec"] = 1.0 if sec.startswith("Administration publique") else 0.0

    ab = g("age_band")
    s["young"] = 1.0 if ab == "18_24" else (0.6 if ab == "25_34" else 0.0)
    s["old"] = 1.0 if ab == "60_PLUS" else (0.35 if ab == "45_59" else 0.0)
    s["age"] = _f(g("age_years"), 40.0) or 40.0
    s["female"] = 1.0 if g("sex") == "F" else 0.0
    s["children"] = _clip((_f(g("household_children_count"), 0.0) or 0.0) / 3.0, 0.0, 1.0)
    s["students"] = _clip((_f(g("household_student_count"), 0.0) or 0.0) / 3.0, 0.0, 1.0)
    s["elderly"] = _clip((_f(g("household_elderly_count"), 0.0) or 0.0) / 2.0, 0.0, 1.0)
    s["dep_ratio"] = _clip((_f(g("dependency_ratio"), 0.4) or 0.4) / 1.5, 0.0, 1.0)
    s["crowd"] = _clip(((_f(g("persons_per_room"), 1.7) or 1.7) - 0.8) / 2.6, 0.0, 1.0)
    s["renter"] = 1.0 if g("tenure_status") == "Locataire" else 0.0
    s["free_housed"] = 1.0 if g("tenure_status") == "Logé gratuitement" else 0.0

    edu = g("education_level")
    s["edu_rank"] = {"Aucun niveau d'études": 0.0, "Préscolaire": 0.12, "Primaire": 0.30,
                     "Secondaire collégial": 0.52, "Secondaire qualifiant": 0.74,
                     "Supérieur": 1.0}.get(edu, 0.30)
    s["illit"] = 1.0 if g("literacy_status") == "Analphabète" else 0.0
    s["higher_ed"] = 1.0 if edu == "Supérieur" else 0.0
    s["voc"] = 0.0 if (g("vocational_diploma_grand_group") in NON_EVIDENCE) else 1.0

    ur = g("urban_rural")
    s["rural"] = 1.0 if ur == "RURAL" else (0.0 if ur == "URBAN" else 0.35)
    s["rural_known"] = 0.0 if ur in NON_EVIDENCE else 1.0
    rd = _f(g("paved_road_distance_km"))
    s["road_known"] = 0.0 if rd is None else 1.0
    s["road_far"] = 0.0 if rd is None else _clip(rd / 25.0, 0.0, 1.0)
    wf = _f(g("water_fetch_duration_minutes"))
    s["water_known"] = 0.0 if wf is None else 1.0
    s["water_far"] = 0.0 if wf is None else _clip(wf / 60.0, 0.0, 1.0)
    wsm = g("water_supply_mode") or ""
    s["water_unpiped"] = 1.0 if ("Puits" in wsm or "Source" in wsm or "Vendeur" in wsm or "Fontaine" in wsm) else 0.0
    s["no_sewer"] = 1.0 if g("wastewater_mode") in ("Dans la nature", "Puits perdu") else 0.0
    s["no_waste"] = 1.0 if g("waste_disposal_mode") == "Dans la nature" else 0.0
    s["poor_light"] = 1.0 if g("lighting_mode") in ("Lampe à huile / Bougies", "Gaz (butane)", "Groupe électrogène") else 0.0
    wc = g("wood_cooking") or ""
    cc = g("charcoal_cooking") or ""
    s["biomass_cook"] = 1.0 if (wc.startswith("Utilisé fréq") or cc.startswith("Utilisé fréq")) else 0.0
    s["slum"] = 1.0 if g("dwelling_type") == "Maison sommaire / Bidonville" else 0.0
    s["no_bath"] = 1.0 if g("bath_shower_available") == "Non disponible" else 0.0

    s["internet"] = 1.0 if g("internet_owned") == "Oui" else 0.0
    s["computer"] = 1.0 if g("computer_owned") == "Oui" else 0.0

    s["hardship"] = _clip(
        0.24 * (1.0 - s["ses"]) + 0.18 * (1.0 - s["asset"]) + 0.14 * (1.0 - s["services"])
        + 0.16 * _clip((s["food_share"] - 0.25) / 0.45, 0, 1) + 0.10 * s["crowd"]
        + 0.10 * s["poverty"] + 0.08 * s["vuln"], 0.0, 1.0)
    return s


# ------------------------------------------------------------- axis need model
def axis_needs(s):
    n = {}
    n["employment"] = _clip(0.16 + 0.42 * s["unemployed"] + 0.26 * s["hh_unemp"]
                            + 0.22 * s["young"] + 0.16 * s["famhelp"]
                            + 0.20 * (1.0 - s["ses"]) + 0.28 * (0.55 - s["econ_cond"]), 0.05, 1.0)
    n["private_investment_sme"] = _clip(0.12 + 0.38 * s["selfemp"] + 0.20 * s["commerce"]
                                        + 0.10 * s["employed"] + 0.10 * s["ses"], 0.05, 1.0)
    n["industrial_competitiveness"] = _clip(0.12 + 0.34 * s["indus"] + 0.20 * s["constr"]
                                            + 0.14 * s["privemp"] + 0.10 * s["ses"], 0.05, 1.0)
    n["fiscal_relief"] = _clip(0.20 + 0.44 * _clip((s["cash_dep"] - 0.12) / 0.42, 0, 1) * s["c_cash"]
                               + 0.24 * _clip((s["food_share"] - 0.25) / 0.45, 0, 1)
                               + 0.16 * _clip(s["credit_share"] * 3.0, 0, 1)
                               + 0.14 * (1.0 - s["econ_cond"]) * s["c_econ"], 0.05, 1.0)
    n["economic_sovereignty"] = _clip(0.16 + 0.16 * s["agri"] + 0.16 * s["indus"]
                                      + 0.14 * s["edu_rank"] + 0.12 * s["discuss"] * s["c_disc"], 0.05, 1.0)
    n["social_protection"] = _clip(0.20 + 0.34 * s["hardship"] + 0.22 * s["dep_ratio"]
                                   + 0.20 * s["elderly"] + 0.18 * s["poverty"] + 0.14 * s["vuln"]
                                   + 0.16 * _clip((s["food_dep"] - 0.03) / 0.24, 0, 1) * s["c_food"]
                                   + 0.12 * s["inactive"], 0.05, 1.0)
    n["health"] = _clip(0.20 + 0.30 * _clip(s["med_share"] / 0.16, 0, 1) + 0.22 * s["elderly"]
                        + 0.16 * s["children"] + 0.14 * _clip((s["age"] - 35.0) / 45.0, 0, 1)
                        + 0.14 * s["hardship"], 0.05, 1.0)
    n["education"] = _clip(0.16 + 0.34 * s["students"] + 0.24 * s["children"]
                           + 0.22 * _clip(s["edu_share"] / 0.10, 0, 1) + 0.16 * s["edu_rank"]
                           + 0.12 * s["young"], 0.05, 1.0)
    n["housing"] = _clip(0.12 + 0.32 * s["crowd"] + 0.28 * s["renter"] + 0.22 * s["slum"]
                         + 0.16 * _clip((s["rent_share"] - 0.08) / 0.30, 0, 1) + 0.14 * s["young"], 0.05, 1.0)
    n["governance_rule_of_law"] = _clip(0.18 + 0.40 * _clip((s["corruption"] - 0.30) / 0.32, 0, 1) * s["c_cloc"]
                                        + 0.26 * _clip((0.45 - s["trust"]) / 0.30, 0, 1) * s["c_tparl"]
                                        + 0.18 * s["discuss"] * s["c_disc"] + 0.14 * s["edu_rank"], 0.05, 1.0)
    n["civil_liberties"] = _clip(0.12 + 0.26 * _clip((s["dem_sup"] - 0.55) / 0.45, 0, 1) * s["c_dsup"]
                                 + 0.20 * s["discuss"] * s["c_disc"] + 0.18 * s["edu_rank"]
                                 + 0.12 * s["young"], 0.05, 1.0)
    n["decentralization"] = _clip(0.14 + 0.30 * _clip((0.30 - s["resp_loc"]) / 0.28, 0, 1) * s["c_resp"]
                                  + 0.24 * s["rural"] * s["rural_known"]
                                  + 0.18 * _clip((0.45 - s["trust_loc"]) / 0.28, 0, 1) * s["c_tloc"], 0.05, 1.0)
    n["rural_territorial_equity"] = _clip(0.10 + 0.40 * s["rural"] * s["rural_known"]
                                          + 0.20 * s["road_far"] * s["road_known"]
                                          + 0.18 * s["water_far"] * s["water_known"]
                                          + 0.16 * (1.0 - s["services"]) + 0.16 * s["agri"]
                                          + 0.10 * s["no_sewer"], 0.05, 1.0)
    n["environment_transition"] = _clip(0.12 + 0.28 * _clip((s["water_dep"] - 0.02) / 0.34, 0, 1) * s["c_water"]
                                        + 0.20 * s["agri"] + 0.16 * s["water_unpiped"]
                                        + 0.14 * s["biomass_cook"] + 0.12 * s["edu_rank"], 0.05, 1.0)
    n["digital_transition"] = _clip(0.10 + 0.32 * s["net_use"] * s["c_net"] + 0.20 * s["internet"]
                                    + 0.16 * s["computer"] + 0.20 * s["young"] + 0.14 * s["edu_rank"], 0.05, 1.0)
    n["public_state_role"] = _clip(0.14 + 0.26 * s["hardship"] + 0.22 * s["pubemp"] + 0.16 * s["pubsec"]
                                   + 0.16 * s["inactive"] + 0.14 * (1.0 - s["ses"]), 0.05, 1.0)
    n["gender_equality"] = _clip(0.12 + 0.22 * s["female"] + 0.16 * s["edu_rank"]
                                 + 0.12 * s["young"] * s["female"] + 0.10 * s["discuss"] * s["c_disc"], 0.05, 1.0)
    n["culture"] = _clip(0.08 + 0.22 * _clip(s["cult_share"] / 0.12, 0, 1) + 0.18 * s["edu_rank"]
                         + 0.14 * _clip(s["leisure_share"] / 0.06, 0, 1) + 0.10 * s["young"], 0.05, 1.0)
    return n


def salience_multipliers(pressures):
    mult = {a: 1.0 for a in PROGRAM_AXES}
    acc = {a: [] for a in PROGRAM_AXES}
    for pid, lvl in (pressures or {}).items():
        if lvl in NON_EVIDENCE:
            continue
        f = PRESSURE_LEVEL.get(lvl)
        if f is None:
            continue
        for axis, w in PRESSURE_MAP.get(pid, {}).items():
            acc[axis].append((w, f))
    for a in PROGRAM_AXES:
        lst = acc[a]
        if not lst:
            continue
        tw = sum(w for w, _ in lst)
        blended = sum(w * f for w, f in lst) / tw
        strength = _clip(tw, 0.0, 1.6) / 1.6
        mult[a] = 1.0 + strength * (blended - 1.0)
    return mult


# ---------------------------------------------------------- local candidate ctx
POS_FLAGS = {
    "INCUMBENT_SAME_PARTY_SAME_DISTRICT": 0.46,
    "INCUMBENT_SAME_PARTY_MOVED_DISTRICT": 0.16,
    "FORMER_MP": 0.30,
    "LOCAL_EXECUTIVE_OFFICE": 0.32,
    "PROVINCIAL_OR_REGIONAL_OFFICE": 0.24,
    "NATIONAL_OR_REGIONAL_PARTY_OFFICE": 0.22,
    "FORMER_MINISTER_OR_NATIONAL_OFFICE": 0.34,
    "FORMAL_ENDORSEMENT": 0.34,
    "FORMAL_LIST_ALLIANCE": 0.20,
}
NEG_FLAGS = {
    "WITHDRAWN_OR_DISQUALIFIED": -1.60,
    "VERIFIED_DEATH_OR_INCAPACITY": -1.60,
    "OFFICIAL_SANCTION_OR_INVESTIGATION": -0.55,
    "PARTY_SWITCH_OUT": -0.24,
}
# Non-directional even when verified (evidence mass only, no sign).
NEUTRAL_FLAGS = {"PARTY_SWITCH_IN"}


def local_scores(party_context_cards):
    out, mass, comp = {}, {}, {}
    for card in party_context_cards or []:
        pid = card.get("anonymous_party_id")
        sc, m, ncomp = 0.0, 0.0, None
        for ft in card.get("features", []):
            fid, st, val, cf = ft.get("feature_id"), ft.get("status"), ft.get("value"), bool(ft.get("conflict"))
            if st != "VERIFIED" or val is None:
                continue
            if cf:                       # conflict -> evidence exists but is non-directional
                m += 0.12
                continue
            if fid == "PRINCIPAL_COMPETITOR_COUNT_WITH_VERIFIED_PROFILE":
                ncomp = val
                m += 0.08
                continue
            if fid == "CANDIDATE_REGISTERED_RANK":
                if isinstance(val, (int, float)) and not isinstance(val, bool):
                    sc += 0.30 if val <= 1 else (0.14 if val <= 2 else 0.05)
                    m += 0.25
                continue
            if fid in NEUTRAL_FLAGS:
                m += 0.10
                continue
            if fid in POS_FLAGS:
                if val is True:
                    sc += POS_FLAGS[fid]
                    m += abs(POS_FLAGS[fid])
                else:
                    m += 0.05          # verified absence: informative, not penalising
                continue
            if fid in NEG_FLAGS:
                if val is True:
                    sc += NEG_FLAGS[fid]
                    m += abs(NEG_FLAGS[fid])
                else:
                    m += 0.05
        out[pid] = sc
        mass[pid] = m
        comp[pid] = ncomp
    return out, mass, comp


# ---------------------------------------------------------------- main scoring
def score_voter(v, ctx, ids, prep=None):
    s = voter_signals(v)
    env = ctx["election_environment_card"]
    terr = ctx["common_territory_card"]
    parties = list(ctx["available_party_ids"])

    if prep is None:
        prep = prepare_context(ctx)
    offers = prep["offers"]
    prev_share = prep["prev_share"]
    prev_turnout = prep["prev_turnout"]
    sal = prep["sal"]
    loc = prep["loc"]
    loc_mass = prep["loc_mass"]
    ncomp = prep["ncomp"]
    log_share = prep["log_share"]
    gov_status = prep["gov_status"]

    needs = axis_needs(s)
    raw_w = {a: needs[a] * sal[a] for a in PROGRAM_AXES}

    fit = {}
    bucket_component = {b: {} for b in set(AXIS_BUCKET.values())}
    unknown_mass = {}
    for q in parties:
        known = prep["known_levels"].get(q, [])
        unknown_mass[q] = 1.0 - (len(known) / float(len(PROGRAM_AXES)))
        tw = 0.0
        bs_acc = {b: 0.0 for b in bucket_component}
        tot = 0.0
        for a, sc in known:
            w = raw_w[a]
            tw += w
            tot += w * sc
            bs_acc[AXIS_BUCKET[a]] += w * sc
        if tw <= 0:
            fit[q] = None
            for b in bucket_component:
                bucket_component[b][q] = None
            continue
        fit[q] = tot / tw
        for b in bucket_component:
            bucket_component[b][q] = bs_acc[b] / tw

    known_fits = [f for f in fit.values() if f is not None]
    neutral_fit = sum(known_fits) / len(known_fits) if known_fits else 0.0

    gov_raw = (0.38 * s["gov_econ"] + 0.20 * s["gov_pov"] + 0.17 * s["gov_anti"] + 0.25 * s["trust_parl"])
    gov_conf = (0.38 * s["c_gecon"] + 0.20 * s["c_gpov"] + 0.17 * s["c_ganti"] + 0.25 * s["c_tparl"])
    gov_adj = (gov_raw
               + 0.40 * (s["dem_sat"] - 0.50) * s["c_dsat"]
               + 0.12 * (s["econ_cond"] - 0.55) * s["c_econ"]
               - 0.18 * (s["corruption"] - 0.44) * s["c_cloc"])
    gov_delta = (gov_adj - 0.50) * gov_conf

    loc_sal = 0.55 + 0.45 * _clip((s["trust_loc"] - 0.18) / 0.42, 0, 1) * s["c_tloc"]

    prior_choice = v.get("prior_vote_or_abstention")
    voted_before = prior_choice in parties

    comp_prior, comp_fit, comp_gov, comp_loc, comp_pv = {}, {}, {}, {}, {}
    for q in parties:
        comp_prior[q] = log_share[q]
        f = fit[q] if fit[q] is not None else neutral_fit
        comp_fit[q] = B_FIT * (f - neutral_fit)
        gs = gov_status.get(q)
        if gs == "INCUMBENT_COALITION":
            comp_gov[q] = B_GOV * gov_delta
        elif gs == "OPPOSITION":
            comp_gov[q] = -B_GOV * 0.68 * gov_delta
        else:
            comp_gov[q] = 0.0
        comp_loc[q] = B_LOC * loc_sal * loc.get(q, 0.0)
        comp_pv[q] = B_PRIOR_VOTE if (voted_before and q == prior_choice) else 0.0

    u = {q: comp_prior[q] + comp_fit[q] + comp_gov[q] + comp_loc[q] + comp_pv[q] for q in parties}
    temp = 1.0 + (0.030 * ncomp if isinstance(ncomp, (int, float)) else 0.0)
    mx = max(u.values())
    ex = {q: math.exp((u[q] - mx) / temp) for q in parties}
    z = sum(ex.values())
    k = len(parties)
    probs = {q: (1.0 - EPS_MIX) * (ex[q] / z) + EPS_MIX / k for q in parties}

    lt = _logit(prev_turnout)
    t_habit = (0.94 if voted_before else -0.72)
    lt += t_habit
    ab = v.get("age_band")
    t_age = {"18_24": -0.34, "25_34": -0.11, "35_44": 0.06, "45_59": 0.21, "60_PLUS": 0.08}.get(ab, 0.0)
    lt += t_age
    t_edu = 0.30 * (s["edu_rank"] - 0.34) - 0.10 * s["illit"]
    lt += t_edu
    t_eng = (0.95 * (s["discuss"] - 0.38) * s["c_disc"]
             + 0.45 * (s["dem_sup"] - 0.83) * s["c_dsup"]
             + 0.38 * (s["dem_sat"] - 0.66) * s["c_dsat"])
    lt += t_eng
    t_inst = (0.72 * (s["trust"] - 0.385) * ((s["c_tparl"] + s["c_tloc"]) / 2.0)
              + 0.46 * (s["resp_loc"] - 0.24) * s["c_resp"]
              - 0.34 * (s["corruption"] - 0.44) * s["c_cloc"])
    lt += t_inst
    t_econ = (-0.30 * (s["cash_dep"] - 0.28) * s["c_cash"] - 0.11 * s["hardship"] + 0.10)
    lt += t_econ
    t_access = -0.34 * s["road_far"] * s["road_known"] - 0.18 * s["water_far"] * s["water_known"]
    lt += t_access
    t_loc_ctx = 0.22 * loc_sal * (max(loc.values()) if loc else 0.0)
    lt += t_loc_ctx
    turnout = _clip(_sigmoid(lt), 0.02, 0.985)

    m = {f: 0.0 for f in FACTORS}
    m["prior_vote_inertia"] = _std(list(comp_prior.values())) + (_std(list(comp_pv.values())) if voted_before else 0.0)
    m["government_reward_punishment"] = _std(list(comp_gov.values()))
    m["local_candidate_context"] = _std(list(comp_loc.values())) + 0.03 * (sum(loc_mass.values()) / max(1, len(loc_mass)))
    for b, per_q in bucket_component.items():
        vals = [B_FIT * (per_q[q] if per_q[q] is not None else 0.0) for q in parties]
        m[b] += _std(vals)
    m["other_verified_context"] += (0.42 * (sum(unknown_mass.values()) / max(1, len(unknown_mass)))
                                    + (0.10 if ncomp is not None else 0.0))
    m["turnout_habit"] += 0.34 * abs(t_habit) + 0.50 * abs(t_age) + 0.60 * abs(t_eng) + 0.28 * abs(t_edu)
    m["governance_and_institutions"] += 0.45 * abs(t_inst)
    m["personal_economic_conditions"] += 0.45 * abs(t_econ) + 0.10 * s["hardship"]
    m["territorial_rural_fit"] += 0.40 * abs(t_access)
    m["local_candidate_context"] += 0.35 * abs(t_loc_ctx)
    turn_scale = 0.70 + 0.60 * (4.0 * turnout * (1.0 - turnout))
    m["turnout_habit"] *= turn_scale
    turnout_shift = abs(turnout - prev_turnout)

    directional = (m["prior_vote_inertia"] + m["government_reward_punishment"] + m["local_candidate_context"]
                   + m["employment_and_income"] + m["social_protection_and_public_services"]
                   + m["policy_program_fit"] + m["governance_and_institutions"]
                   + m["territorial_rural_fit"] + m["personal_economic_conditions"])

    FLOOR = 0.004
    for f in FACTORS:
        if m[f] < 0.0:
            m[f] = 0.0
    tot = sum(m.values())
    if tot <= 0:
        fi = {f: 1.0 / len(FACTORS) for f in FACTORS}
    else:
        fi = {f: (m[f] / tot) * (1.0 - FLOOR * len(FACTORS)) + FLOOR for f in FACTORS}

    fi = {f: round(fi[f], 9) for f in FACTORS}
    resid = round(1.0 - sum(fi.values()), 9)
    top_f = max(fi, key=lambda x: fi[x])
    fi[top_f] = round(fi[top_f] + resid, 9)

    probs = {q: round(probs[q], 9) for q in parties}
    presid = round(1.0 - sum(probs.values()), 9)
    top_q = max(probs, key=lambda x: probs[x])
    probs[top_q] = round(probs[top_q] + presid, 9)
    turnout = round(turnout, 9)

    PROGRAM_F = ["employment_and_income", "social_protection_and_public_services",
                 "policy_program_fit", "governance_and_institutions",
                 "territorial_rural_fit", "personal_economic_conditions"]
    prog_ranked = sorted(PROGRAM_F, key=lambda x: fi[x] / (FACTOR_BREADTH[x] ** 0.75), reverse=True)
    loc_vals = list(loc.values()) or [0.0]
    loc_spread = max(loc_vals) - min(loc_vals)
    codes = []

    def add(c):
        if c and c not in codes and len(codes) < 4:
            codes.append(c)

    if directional < 0.035:
        codes.append("NO_DIRECTIONAL_EVIDENCE")
    else:
        if fi[prog_ranked[0]] >= 0.050:
            add(FACTOR_CODE[prog_ranked[0]])
        if fi["prior_vote_inertia"] >= 0.17:
            add("PRIOR_VOTE_INERTIA" if voted_before else "PRIOR_ABSTENTION_INERTIA")
        if fi["government_reward_punishment"] >= 0.038 and abs(gov_delta) >= 0.008:
            add("GOVERNMENT_REWARD" if gov_delta > 0 else "GOVERNMENT_PUNISHMENT")
        if fi["turnout_habit"] >= 0.155 and turnout_shift >= 0.050:
            add("TURNOUT_HABIT")
        if fi["local_candidate_context"] >= 0.085 and loc_spread >= 0.05:
            best, worst = max(loc_vals), min(loc_vals)
            if worst < -0.02 and abs(worst) > best:
                add("LOCAL_CANDIDATE_WEAKNESS")
            elif best > 0.02:
                add("LOCAL_CANDIDATE_STRENGTH")
        if s["c_att"] >= 0.62 and (fi["governance_and_institutions"] + fi["government_reward_punishment"]) >= 0.14:
            add("ATTITUDE_POSTERIOR")
        if fi[prog_ranked[1]] >= 0.085:
            add(FACTOR_CODE[prog_ranked[1]])
        # residual: non-directional / uncarded evidence explains what is left
        if len(codes) <= 2 and fi["other_verified_context"] >= 0.030:
            add("OTHER_VERIFIED_CONTEXT")
        if not codes:
            add(FACTOR_CODE[prog_ranked[0]])
    codes = codes[:4]

    return {
        "anonymous_election_id": ids["anonymous_election_id"],
        "anonymous_territory_id": ids["anonymous_territory_id"],
        "condition_id": ids["condition_id"],
        "batch_id": ids["batch_id"],
        "weighted_archetype_id": v["weighted_archetype_id"],
        "turnout_probability": turnout,
        "conditional_party_probabilities": probs,
        "factor_importance": fi,
        "reason_codes": codes,
    }


def prepare_context(ctx):
    """Context-level quantities that do not depend on the individual archetype."""
    env = ctx["election_environment_card"]
    terr = ctx["common_territory_card"]
    parties = list(ctx["available_party_ids"])
    offers = {c["anonymous_party_id"]: c for c in env.get("party_offer_cards", [])}
    prev_share = terr.get("previous_election_conditional_party_shares", {}) or {}
    prev_turnout = _f(terr.get("previous_election_turnout_probability"), 0.47) or 0.47
    sal = salience_multipliers(env.get("national_issue_pressures"))
    loc, loc_mass, comp = local_scores(terr.get("party_context_cards"))
    ncomp_vals = [c for c in comp.values() if isinstance(c, (int, float)) and not isinstance(c, bool)]
    ncomp = max(ncomp_vals) if ncomp_vals else None
    log_share = {}
    known_levels = {}
    gov_status = {}
    for q in parties:
        sh = _f(prev_share.get(q), 0.0) or 0.0
        log_share[q] = B_PRIOR_SHARE * math.log(max(sh, 0.004))
        card = offers.get(q, {}) or {}
        levels = card.get("program_priority_levels", {}) or {}
        known_levels[q] = [(a, LEVEL_SCORE[levels[a]]) for a in PROGRAM_AXES if levels.get(a) in LEVEL_SCORE]
        gov_status[q] = card.get("government_status")
    return {
        "offers": offers, "prev_share": prev_share, "prev_turnout": prev_turnout,
        "sal": sal, "loc": loc, "loc_mass": loc_mass, "ncomp": ncomp,
        "log_share": log_share, "known_levels": known_levels, "gov_status": gov_status,
        "parties": parties,
    }
