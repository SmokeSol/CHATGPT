#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import agent_society_v2_rich_patch_and_run_v2 as p2

EXTRA_HELPERS = r"""
for _c in ['ET_LIEU','ET_TRANS','FP_DIP_SG','FP_DIP_SGG','FP_DIP_GG']:
    if _c not in b.IND_COLS:
        b.IND_COLS.append(_c)
for _c in ['EAU_DIST','EAU_DUR']:
    if _c not in b.HH_COLS:
        b.HH_COLS.append(_c)
for _c in [
    'Quintiles','Quintileurbain','Decileurbain','Quintilerural','Decilerural',
    'Etat_matrimonial_CM','Diplôme_agregé_CM','Type_activité_dominante_CM',
    'Profession_agreg_CM','Secteur_activité_agreg_CM','Situation_profession_agreg_CM',
    'DAM_G2','DAM_G4','DAM_G8','DAM_G9','DAM_hygiene','DAM_soins_medicaux',
    'DAM_Transport','DAM_Communication','DAM_Loisirs','DAM_Enseignement',
    'DAM_Autres_dépenses','DAM_G31','DAM_G33','DAM_G04','DAM_G05','DAM_G06',
    'DAM_G08','DAM_G15','DAM_G61','DAM_G62','DAM_G63','DAM_G75','DAM_G76',
    'DAM_G87','DAM_G88','DAM_G91','DAM_G92','DAM_G93','DAM_G94','DAM_G95'
]:
    if _c not in b.ENCDM_COLS:
        b.ENCDM_COLS.append(_c)

_ENCDM_ACTIVITY = {
    1:'EMPLOYED',2:'UNEMPLOYED_PREVIOUSLY_WORKED',3:'UNEMPLOYED_NEVER_WORKED',
    4:'HOMEMAKER',5:'STUDENT',6:'CHILD',7:'ELDERLY',8:'RETIRED',
    9:'RENTIER',10:'OTHER_INACTIVE',11:'OTHER_INACTIVE'
}
_ENCDM_PROFESSION = {
    0:'NEVER_WORKED',1:'DIRECTOR_SENIOR_PROFESSIONAL',2:'MIDDLE_MANAGER_CLERICAL',
    3:'TRADER_FINANCE_INTERMEDIARY',4:'AGRICULTURE_FISHING_FORESTRY',
    5:'CRAFT_SKILLED_MACHINE_OPERATOR',6:'ELEMENTARY_NON_AGRICULTURAL',9:'NOT_DECLARED'
}
_ENCDM_SECTOR = {
    0:'NEVER_WORKED',1:'AGRICULTURE_FISHING_FORESTRY',2:'INDUSTRY',
    3:'CONSTRUCTION',4:'COMMERCE',5:'SERVICES',9:'NOT_DECLARED'
}
_ENCDM_STATUS = {
    0:'NEVER_WORKED',1:'INACTIVE',2:'EMPLOYEE',3:'SELF_EMPLOYED',
    4:'EMPLOYER',5:'OTHER',9:'NOT_DECLARED'
}
_ENCDM_MARITAL = {1:'SINGLE',2:'MARRIED',3:'DIVORCED',4:'WIDOWED'}
_ENCDM_DIPLOMA = {1:'NO_DIPLOMA',2:'MIDDLE_LEVEL',3:'HIGHER_LEVEL'}

def _finite(row, key):
    v = b.clean_num(row.get(key, np.nan))
    return float(v) if math.isfinite(v) else None

def _mapped(row, key, mapping):
    v = _finite(row, key)
    if v is None:
        return 'MISSING'
    return mapping.get(int(v), 'MISSING')

def _share(row, key):
    total = _finite(row, 'DAM')
    value = _finite(row, key)
    if total is None or total <= 0 or value is None:
        return None
    return max(0.0, min(1.0, value / total))

def _share_sum(row, keys):
    total = _finite(row, 'DAM')
    vals = [_finite(row, k) for k in keys]
    if total is None or total <= 0 or not any(v is not None for v in vals):
        return None
    return max(0.0, min(1.0, sum(v or 0.0 for v in vals) / total))

def extra_information_features(p, h, ep, im, hm):
    total = _finite(ep, 'DAM')
    hh_size = max(1, b.safe_int(ep.get('Taille_ménage', h.get('taille', 1)), 1))
    milieu = b.safe_int(ep.get('Milieu', np.nan), -1)
    within_decile = _finite(ep, 'Decileurbain') if milieu == 1 else _finite(ep, 'Decilerural') if milieu == 2 else None
    water_duration = b.clean_num(h.get('EAU_DUR', np.nan))
    if not math.isfinite(water_duration) or water_duration >= 998:
        water_duration = None
    return {
        'study_location': b.code_label(im, 'ET_LIEU', p.get('ET_LIEU', np.nan)),
        'study_commute_mode': b.code_label(im, 'ET_TRANS', p.get('ET_TRANS', np.nan)),
        'vocational_diploma_subgroup': b.code_label(im, 'FP_DIP_SG', p.get('FP_DIP_SG', np.nan)),
        'vocational_diploma_subgrand_group': b.code_label(im, 'FP_DIP_SGG', p.get('FP_DIP_SGG', np.nan)),
        'vocational_diploma_grand_group': b.code_label(im, 'FP_DIP_GG', p.get('FP_DIP_GG', np.nan)),
        'water_point_distance_band': b.code_label(hm, 'EAU_DIST', h.get('EAU_DIST', np.nan)),
        'water_fetch_duration_minutes': None if water_duration is None else float(water_duration),
        'latent_household_expenditure_log': None if total is None else float(np.log1p(max(0.0, total))),
        'latent_household_expenditure_per_person_log': None if total is None else float(np.log1p(max(0.0, total / hh_size))),
        'latent_national_quintile': None if _finite(ep, 'Quintiles') is None else float(_finite(ep, 'Quintiles') / 5.0),
        'latent_within_milieu_decile': None if within_decile is None else float(within_decile / 10.0),
        'latent_head_marital_status': _mapped(ep, 'Etat_matrimonial_CM', _ENCDM_MARITAL),
        'latent_head_diploma_level': _mapped(ep, 'Diplôme_agregé_CM', _ENCDM_DIPLOMA),
        'latent_head_activity': _mapped(ep, 'Type_activité_dominante_CM', _ENCDM_ACTIVITY),
        'latent_head_profession_group': _mapped(ep, 'Profession_agreg_CM', _ENCDM_PROFESSION),
        'latent_head_industry_sector': _mapped(ep, 'Secteur_activité_agreg_CM', _ENCDM_SECTOR),
        'latent_head_professional_status': _mapped(ep, 'Situation_profession_agreg_CM', _ENCDM_STATUS),
        'latent_clothing_budget_share': _share(ep, 'DAM_G2'),
        'latent_household_equipment_budget_share': _share(ep, 'DAM_G4'),
        'latent_other_goods_services_budget_share': _share(ep, 'DAM_G8'),
        'latent_tax_transfer_credit_budget_share': _share(ep, 'DAM_G9'),
        'latent_hygiene_budget_share': _share(ep, 'DAM_hygiene'),
        'latent_medical_budget_share': _share(ep, 'DAM_soins_medicaux'),
        'latent_transport_budget_share': _share(ep, 'DAM_Transport'),
        'latent_communication_budget_share': _share(ep, 'DAM_Communication'),
        'latent_leisure_budget_share': _share(ep, 'DAM_Loisirs'),
        'latent_education_budget_share': _share(ep, 'DAM_Enseignement'),
        'latent_other_combined_budget_share': _share(ep, 'DAM_Autres_dépenses'),
        'latent_rent_charges_budget_share': _share(ep, 'DAM_G31'),
        'latent_utilities_budget_share': _share(ep, 'DAM_G33'),
        'latent_meat_budget_share': _share(ep, 'DAM_G04'),
        'latent_fish_budget_share': _share(ep, 'DAM_G05'),
        'latent_fresh_vegetables_budget_share': _share(ep, 'DAM_G06'),
        'latent_fruit_budget_share': _share(ep, 'DAM_G08'),
        'latent_food_away_from_home_budget_share': _share(ep, 'DAM_G15'),
        'latent_private_transport_budget_share': _share(ep, 'DAM_G61'),
        'latent_public_transport_budget_share': _share(ep, 'DAM_G62'),
        'latent_communications_subgroup_share': _share(ep, 'DAM_G63'),
        'latent_formal_education_subgroup_share': _share_sum(ep, ['DAM_G75','DAM_G76']),
        'latent_insurance_budget_share': _share(ep, 'DAM_G87'),
        'latent_banking_services_budget_share': _share(ep, 'DAM_G88'),
        'latent_tax_payments_budget_share': _share(ep, 'DAM_G91'),
        'latent_outgoing_transfers_budget_share': _share_sum(ep, ['DAM_G92','DAM_G93','DAM_G95']),
        'latent_credit_repayment_budget_share': _share(ep, 'DAM_G94'),
    }
"""

DONOR_OLD = "rec.update(b.ses_features(b.pick_encdm(enc,eidx,donor,SEED+year+ti)))"
DONOR_NEW = (
    "ep=b.pick_encdm(enc,eidx,donor,SEED+year+ti); "
    "rec.update(b.ses_features(ep)); "
    "rec.update(extra_information_features(p,h,ep,im,hm))"
)

def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", required=True)
    args, rest = parser.parse_known_args()
    source_path = Path(args.source)
    source = source_path.read_text(encoding="utf-8")
    if source.count("\ndef main():\n") != 1:
        raise RuntimeError("unexpected V2 main marker count")
    source = source.replace(
        "\ndef main():\n",
        "\n" + p2.HELPERS + "\n" + EXTRA_HELPERS + "\ndef main():\n",
        1,
    )
    if source.count(p2.SAMPLE_OLD) != 1:
        raise RuntimeError("unexpected V2 sampling block count")
    source = source.replace(p2.SAMPLE_OLD, p2.SAMPLE_NEW, 1)
    if source.count(p2.RANK_OLD) != 1:
        raise RuntimeError("unexpected V2 effective-rank block count")
    source = source.replace(p2.RANK_OLD, p2.RANK_NEW, 1)
    if source.count(DONOR_OLD) != 1:
        raise RuntimeError("unexpected V2 donor block count")
    source = source.replace(DONOR_OLD, DONOR_NEW, 1)
    sys.argv = [str(source_path)] + rest
    namespace = {"__name__": "__main__", "__file__": str(source_path)}
    exec(compile(source, str(source_path) + "::x10-extended", "exec"), namespace, namespace)

if __name__ == "__main__":
    main()
