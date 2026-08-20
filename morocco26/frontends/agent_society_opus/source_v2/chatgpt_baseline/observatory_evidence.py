from __future__ import annotations

from observatory_base import *

def add_evidence(
    catalogue: list[dict[str, Any]],
    evidence_id: str,
    factor: str,
    scope: str,
    field: str,
    value: Any,
    *,
    party_id: str | None = None,
    status: str = "SUPPLIED",
    directional: bool = True,
) -> None:
    if value is None:
        return
    catalogue.append(
        {
            "evidence_id": evidence_id,
            "factor": factor,
            "scope": scope,
            "field": field,
            "value": value,
            "party_id": party_id,
            "status": status,
            "directional": bool(directional),
        }
    )


def evidence_catalogue(
    task: R.FrozenTask,
    voter: Mapping[str, Any],
    decision: Mapping[str, Any],
) -> list[dict[str, Any]]:
    context = task_context(task)
    top, _, runner, _ = top_two(decision)
    catalogue: list[dict[str, Any]] = []

    voter_fields = (
        ("V_PRIOR_VOTE", "prior_vote_inertia", "prior_vote_or_abstention"),
        ("V_ACTIVITY", "employment_and_income", "activity_status"),
        ("V_OCCUPATION", "employment_and_income", "occupation_group"),
        ("V_INDUSTRY", "employment_and_income", "industry_sector"),
        ("V_HOUSEHOLD_UNEMPLOYED", "employment_and_income", "household_unemployed_count"),
        ("V_QUINTILE", "personal_economic_conditions", "latent_national_quintile"),
        ("V_ECONOMIC_CONDITION", "personal_economic_conditions", "latent_attitude_economic_condition_mean"),
        ("V_LIVING_CONDITIONS", "personal_economic_conditions", "latent_attitude_living_conditions_mean"),
        ("V_CASH_DEPRIVATION", "social_protection_and_public_services", "latent_attitude_cash_deprivation_mean"),
        ("V_FOOD_DEPRIVATION", "social_protection_and_public_services", "latent_attitude_food_deprivation_mean"),
        ("V_WATER_DEPRIVATION", "social_protection_and_public_services", "latent_attitude_water_deprivation_mean"),
        ("V_GOV_ECON", "government_reward_punishment", "latent_attitude_government_economic_performance_mean"),
        ("V_GOV_POVERTY", "government_reward_punishment", "latent_attitude_government_poverty_performance_mean"),
        ("V_GOV_ANTICORRUPTION", "government_reward_punishment", "latent_attitude_government_anticorruption_performance_mean"),
        ("V_DEMOCRACY_SATISFACTION", "governance_and_institutions", "latent_attitude_democracy_satisfaction_mean"),
        ("V_TRUST_PARLIAMENT", "governance_and_institutions", "latent_attitude_trust_parliament_mean"),
        ("V_TRUST_LOCAL", "governance_and_institutions", "latent_attitude_trust_local_government_mean"),
        ("V_LOCAL_CORRUPTION", "governance_and_institutions", "latent_attitude_perceived_local_corruption_mean"),
        ("V_MP_CORRUPTION", "governance_and_institutions", "latent_attitude_perceived_mp_corruption_mean"),
        ("V_LOCAL_RESPONSIVENESS", "local_candidate_context", "latent_attitude_local_responsiveness_mean"),
        ("V_POLITICAL_DISCUSSION", "turnout_habit", "latent_attitude_political_discussion_mean"),
        ("V_URBAN_RURAL", "territorial_rural_fit", "urban_rural"),
        ("V_EDUCATION", "governance_and_institutions", "education_level"),
        ("V_AGE", "turnout_habit", "age_band"),
    )
    for evidence_id, factor, field in voter_fields:
        add_evidence(catalogue, evidence_id, factor, "VOTER", field, voter.get(field))

    common = context.get("common_territory_card") or {}
    add_evidence(
        catalogue,
        "E_PREVIOUS_TURNOUT",
        "turnout_habit",
        "ELECTION",
        "previous_election_turnout_probability",
        common.get("previous_election_turnout_probability"),
    )
    previous_shares = common.get("previous_election_conditional_party_shares") or {}
    for party in (top, runner):
        add_evidence(
            catalogue,
            f"E_PREVIOUS_SHARE_{party}",
            "prior_vote_inertia",
            "ELECTION",
            f"previous_election_conditional_party_shares.{party}",
            previous_shares.get(party),
            party_id=party,
        )

    environment = context.get("election_environment_card") or {}
    for issue, value in sorted((environment.get("national_issue_pressures") or {}).items()):
        factor = (
            "employment_and_income" if "employment" in issue
            else "social_protection_and_public_services" if any(token in issue for token in ("health", "education", "social_protection"))
            else "territorial_rural_fit" if any(token in issue for token in ("agriculture", "territorial", "water"))
            else "governance_and_institutions" if "governance" in issue
            else "personal_economic_conditions"
        )
        add_evidence(
            catalogue,
            "E_ISSUE_" + re.sub(r"[^A-Z0-9]+", "_", issue.upper()),
            factor,
            "ELECTION",
            "national_issue_pressures." + issue,
            value,
        )

    offers = party_offer_lookup(context)
    locals_ = party_local_lookup(context)
    for party in (top, runner):
        offer = offers.get(party) or {}
        add_evidence(
            catalogue,
            f"P_{party}_GOVERNMENT_STATUS",
            "government_reward_punishment",
            "PARTY",
            "government_status",
            offer.get("government_status"),
            party_id=party,
        )
        for axis, level in sorted((offer.get("program_priority_levels") or {}).items()):
            add_evidence(
                catalogue,
                f"P_{party}_PROGRAM_{re.sub(r'[^A-Z0-9]+', '_', axis.upper())}",
                "policy_program_fit",
                "PARTY",
                "program_priority_levels." + axis,
                level,
                party_id=party,
                directional=(level != "UNKNOWN"),
            )
        local = locals_.get(party) or {}
        for feature in local.get("features") or []:
            if not isinstance(feature, dict):
                continue
            feature_id = str(feature.get("feature_id") or "UNKNOWN")
            status = str(feature.get("status") or "UNKNOWN")
            directional = status == "VERIFIED" and not bool(feature.get("conflict"))
            add_evidence(
                catalogue,
                f"P_{party}_LOCAL_{re.sub(r'[^A-Z0-9]+', '_', feature_id.upper())}",
                "local_candidate_context",
                "PARTY",
                "local_feature." + feature_id,
                feature.get("value") if feature.get("value") is not None else status,
                party_id=party,
                status=status,
                directional=directional,
            )
    catalogue.sort(key=lambda item: item["evidence_id"])
    seen = set()
    unique = []
    for item in catalogue:
        if item["evidence_id"] in seen:
            continue
        seen.add(item["evidence_id"])
        unique.append(item)
    return unique
