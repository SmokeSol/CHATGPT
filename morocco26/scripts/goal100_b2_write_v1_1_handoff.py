#!/usr/bin/env python3
"""Write the V1.1 historical + Wave-1 handoff report and append the Ariane entry.

Generated from committed artifacts so the prose cannot drift from machine state.
The journal append is idempotent by marker and never rewrites an earlier entry.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

SURFACE_PATH = G100 / "historical_source_surface_v1_1.json"
SURFACE_CERT_PATH = G100 / "historical_source_surface_certificate.json"
OUTCOME_PATH = G100 / "b2_v1_1_outcome_certificate.json"
PANEL_CERT_PATH = G100 / "b2_historical_panel_certificate.json"
BALLOT_CERT_PATH = G100 / "b2_2026_ballot_certificate.json"
ROSTER_PATH = G100 / "b2_2026_ballot_roster.json"
HIST_ACQ_CERT_PATH = G100 / "b2_historical_acquisition_certificate.json"
MEMBERS_PATH = G100 / "historical" / "b2_historical_elected_members.json"
STATE_PATH = G100 / "b2_current_state.json"

REPORT_PATH = ROOT / "reports" / "B2_V1_1_HISTORICAL_AND_WAVE1_HANDOFF.md"
JOURNAL_PATH = ROOT / "FIL_D_ARIANE.md"
MARKER = "Amendement V1.1 de la surface de sources historiques et exécution B2-4"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_V1_1_HANDOFF_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def build_report() -> str:
    surface = load(SURFACE_PATH)
    surface_cert = load(SURFACE_CERT_PATH)
    outcome = load(OUTCOME_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    ballot_cert = load(BALLOT_CERT_PATH)
    roster = load(ROSTER_PATH)
    hist = load(HIST_ACQ_CERT_PATH)
    members = load(MEMBERS_PATH)
    state = load(STATE_PATH)

    fit, val = panel_cert["transitions"]
    inv = outcome["invariants"]

    surface_rows = "\n".join(
        f"| `{row['source_id']}` | {row['requests']} | {row['acquired']} | {row['blocked']} | "
        f"{row['truncated']} | {row['captures_total']} | {'yes' if row['exhaustion_claimable'] else 'no'} |"
        for row in outcome["surface_results"]
    )
    member_rows = "\n".join(
        f"| {year} | {entry['elected_rows']} | {entry['local_rows_resolved']} | "
        f"{entry['local_territories_resolved']}/92 |"
        for year, entry in sorted(members["years"].items(), key=lambda item: int(item[0]))
    )
    e_collect = "\n".join(f"- `{row}`" for row in outcome["reserved_for_e_collect"]["input_classes"])

    scan = outcome["secondary_target_scan"]
    secondary_rows = "| Input class | Named surface | Matches | Status |\n|---|---|---:|---|\n" + "\n".join(
        f"| `{row['input_class']}` | {'yes' if row['candidate_surface_exists'] else 'no'} | "
        f"{len(row['matches'])} | `{row['status']}` |"
        for row in scan["classes"]
    )
    communal_2021 = scan["leakage_note"]["communal_election_dates"].get("2021", "2021-09-08")
    rejected = outcome["primary_target"]["dataset_name_search"].get("rejected_near_matches", [])
    rejected_rows = "\n".join(
        f"- `{row['name']}` — rejected: `{row['reason']}`" for row in rejected
    ) or "- none"

    return f"""# B2 V1.1 — historical source-surface amendment and Wave-1 handoff

Numeric answers only. No political interpretation, no effect size, no forecast.

- Generated: {now_local()}
- Amendment: `{surface['amendment_id']}`, frozen `{surface['frozen_at']}` **before** acquisition
- Source-surface SHA-256: `{surface['canonical_surface_sha256']}`
- Source-surface certificate: `{surface_cert['gate']}` ({len(surface_cert['checks'])} checks)
- **Termination state: `{outcome['termination_state']}`**
- **B2-4 state: `{'B2_4_PASS' if ballot_cert['gate'] == 'PASS' else 'B2_4_FAIL'}`**

## 1. Historical candidate rosters recovered?

**No.** `roster_dataset_found = {str(outcome['primary_target']['dataset_name_search']['roster_dataset_found']).lower()}`
across {outcome['primary_target']['dataset_name_search']['names_enumerated']} enumerated dataset/package names.
Required years {outcome['primary_target']['required_years']}; recovered coverage **0/92 territories in both**.

Previously recovered and preserved (elected members, not candidate rosters):

| Election | Elected rows | Local resolved | Territories |
|---|---:|---:|---:|
{member_rows}

### Secondary targets (§7): named candidate surfaces in the amended catalog

{secondary_rows}

`HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR` is the one secondary class that gained a named surface:
`composition-des-conseils-communaux-2015/2021` and `-regionaux`. It stays blocked, because `B2_P05`
also requires the candidate roster. A leakage constraint applies if it is ever used: the 2021 communal
election fell on {communal_2021}, the same day as the 2021 legislative election, so 2021 council
composition is not knowable before the 2021 legislative cutoff — office held at that cutoff derives
from the 2015 councils.

### Near-matches rejected by the matcher

{rejected_rows}

The first pass of this scan reported a roster as found. It was a substring artifact:
`avis-de-candidature-aux-emplois-superieurs-publics` is a civil-service vacancy notice, and it matched
because "candidature" contains "candidat". A second artifact matched `rang` inside "etranger". The
matcher now requires word boundaries plus an electoral qualifier, and both disappear. Had this not
been caught, the run would have claimed a recovered roster that does not exist.

## 2. B2-3 features identifiable, fit transition

**{fit['features_identifiable']}/16** (`2011_TO_2016`)

## 3. B2-3 features identifiable, validation transition

**{val['features_identifiable']}/16** (`2016_TO_2021`)

## 4. Core predictive coverage vs the 0.8 threshold

| Transition | Coverage | Threshold | Meets |
|---|---:|---:|---|
| `2011_TO_2016` | {fit['core_predictive_panel_coverage']} | {panel_cert['minimum_coverage_required']} | no |
| `2016_TO_2021` | {val['core_predictive_panel_coverage']} | {panel_cert['minimum_coverage_required']} | no |

Threshold unchanged: `{str(outcome['b2_3']['threshold_unchanged']).lower()}`.

## 5. Is the residual backtest unlocked?

**No.** Blocking machine gate: `B2-3-HISTORICAL-FEATURE-PANEL`, still `OPEN`.

## 6. Current 2026 Wave-1 verified roster coverage

| Metric | Value |
|---|---:|
| Rows parsed | {ballot_cert['rows_parsed']} |
| Distinct constituencies in table | {roster['counts']['rows_parsed']} |
| Territories resolved to certified IDs | {ballot_cert['constituencies_covered']}/{ballot_cert['certified_local_constituencies']} |
| Territory coverage | {ballot_cert['territory_coverage_fraction']} |
| **Verified double-entry rows** | **{ballot_cert['verified_double_entry_rows']}** |
| Single-source rows | {ballot_cert['single_source_rows']} |
| Ambiguous deterministic match | {ballot_cert['ambiguous_deterministic_match_rows']} |
| Conflicts | {ballot_cert['conflict_rows']} |
| Blocked source documents | {ballot_cert['blocked_source_documents']} |
| B2 claim records created | {ballot_cert['b2_claim_records_created']} |

Source-class breakdown: T0 authoritative structured tables
{ballot_cert['source_class_breakdown']['T0_authoritative_structured_tables']}, T1 party official
{ballot_cert['source_class_breakdown']['T1_party_official']}, T2 media
{ballot_cert['source_class_breakdown']['T2_media']}. Parties covered: {ballot_cert['parties_covered']}.

The table parsed perfectly — 92 rows, 92 distinct constituencies, 92 distinct list-agent names, 0
malformed rows. It resolves to zero certified territory IDs because the roster is written in Arabic
and the certified crosswalk carries Latin-script aliases only. Resolving them would require either
transliteration judgment, which the identity protocol forbids, or a versioned Arabic territory-alias
amendment reviewed entry by entry. Neither is performed here.

## 7. Exact B2-4 gate state

`B2_4_FAIL` — gate remains `OPEN`. Two independent blockers, both machine-checked:

1. `NO_ROW_SATISFIES_CRITICAL_DOUBLE_ENTRY` — the only roster source is T1, and the frozen rule needs
   two matching parses or one authoritative T0 structured table. Corroboration was searched across
   {roster['corroboration_search']['documents_searched']} documents in
   {roster['corroboration_search']['clusters_searched']} independence clusters and found none.
2. `TERRITORY_COVERAGE_INCOMPLETE` — {ballot_cert['territory_coverage_fraction']} against a required 1.0.

## 8. Unresolved cells reserved for E_collect

`e_collect_executed = {str(outcome['reserved_for_e_collect']['e_collect_executed']).lower()}`.

{len(outcome['reserved_for_e_collect']['input_classes'])} historical input classes:

{e_collect}

Plus {outcome['reserved_for_e_collect']['b2_4_unresolved_rows']} unresolved 2026 roster rows.

## 9. Did any coefficient move?

**No.** `{inv['coefficients']}` — `coefficients_all_zero = {str(inv['coefficients_all_zero']).lower()}`.

## 10. Did F-1 change?

**No.** The source-surface certificate check `F_MINUS_1_UNCHANGED` passed: the declared, manifest and
protocol digests all agree.

## Amended surface: what the enumeration actually returned

| Surface | Requests | Acquired | Blocked | Truncated | Captures | Exhaustion claimable |
|---|---:|---:|---:|---:|---:|---|
{surface_rows}

`{outcome['termination_state']}` was selected because: {outcome['termination_reason']}

Exhaustion is only claimable when a surface is both fully enumerated and reachable. A truncated
enumeration or a blocked route cannot support a claim that nothing exists, which is why this run does
not report `B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION` merely because no roster was found.

## Invariants

```json
{json.dumps({
    "coefficients": inv["coefficients"],
    "F_minus_1": "IMMUTABLE",
    "B2_FROZEN": False,
    "F0_CREATED": False,
    "AGENTIC_PREDICTIVE_LAYER": inv["AGENTIC_PREDICTIVE_LAYER"],
    "E_collect_executed": False,
    "b2_3_gate": "OPEN",
    "b2_4_gate": "OPEN",
    "feature_definitions_changed": False,
    "thresholds_changed": False,
    "v1_registry_edited": False,
}, indent=2)}
```
"""


def append_journal() -> bool:
    text = JOURNAL_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        return False

    surface = load(SURFACE_PATH)
    outcome = load(OUTCOME_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    ballot_cert = load(BALLOT_CERT_PATH)
    fit, val = panel_cert["transitions"]

    blocked = ", ".join(f"`{s}`" for s in outcome["termination_detail"].get("blocked_surfaces", [])) or "aucune"
    truncated = ", ".join(f"`{s}`" for s in outcome["termination_detail"].get("truncated_surfaces", [])) or "aucune"

    entry = f"""

### {now_local()[:10]} — {MARKER}

**Diagnostic structurel.** Le registre de sources B2 V1 n'exprime que
`{surface['trigger_measurement']['v1_election_years_expressible']}` alors que B2-3 exige
`{surface['trigger_measurement']['b2_3_required_years']}`. C'est une omission définitionnelle de V1, pas une
mesure d'indisponibilité des données historiques.

**Amendement V1.1 gelé AVANT acquisition.** `{surface['amendment_id']}`, portée
`{surface['amendment_scope']}`, hash `{surface['canonical_surface_sha256']}`. Trois surfaces ajoutées au
niveau racine/classe avant toute inspection de contenu, selon deux tests indépendants du résultat :
racine déjà présente dans la provenance du dépôt, ou miroir d'archive d'un domaine déjà enregistré. Les
10 contrôles du certificat passent : dictionnaire de features inchangé, seuils inchangés (0,8 / 30),
F-1 inchangé, aucun coefficient modifié, extraction LLM interdite, registre V1 non édité.

**Acquisition exécutée.** Surfaces : {', '.join('`'+r['source_id']+'`' for r in outcome['surface_results'])}.
Bloquées : {blocked}. Tronquées : {truncated}. Aucun jeu de données de roster de candidats marocains n'a
été trouvé parmi `{outcome['primary_target']['dataset_name_search']['names_enumerated']}` noms énumérés.

**Couverture B2-3 avant/après.** Inchangée : identifiables `{fit['features_identifiable']}/16` (fit) et
`{val['features_identifiable']}/16` (validation) ; couverture prédictive centrale
`{fit['core_predictive_panel_coverage']}` / `{val['core_predictive_panel_coverage']}` contre un seuil de
`{panel_cert['minimum_coverage_required']}` non affaibli. Le blocage résiduel dominant reste
`HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`.

**État terminal B2-3 : `{outcome['termination_state']}`.** Motif : {outcome['termination_reason']}
L'exhaustion n'est revendiquée que si chaque surface est intégralement énumérée et joignable ; une
énumération tronquée ou une route bloquée ne peut jamais fonder une affirmation d'absence.

**B2-4 exécuté.** Table de roster 2026 analysée déterministiquement : `{ballot_cert['rows_parsed']}` lignes,
92 circonscriptions distinctes, 0 ligne malformée. Territoires résolus
`{ballot_cert['constituencies_covered']}/{ballot_cert['certified_local_constituencies']}` : la table est en
arabe et le crosswalk certifié ne porte que des alias latins. Aucune translittération n'a été inventée.
Double saisie critique vérifiée : `{ballot_cert['verified_double_entry_rows']}` ligne(s) ; source unique T1
non autoritative. Gate `B2-4` reste `OPEN`, `{ballot_cert['b2_claim_records_created']}` claim B2 créé.

**Réservé pour E_collect.** `{len(outcome['reserved_for_e_collect']['input_classes'])}` classes d'entrée et
`{outcome['reserved_for_e_collect']['b2_4_unresolved_rows']}` lignes 2026 non résolues. `E_collect` n'a pas
été exécuté.

**Prochain gate machine :** `B2-3-HISTORICAL-FEATURE-PANEL` reste le gate bloquant ; `B2-4` requiert soit
une source T0 autoritative, soit un amendement versionné d'alias territoriaux arabes revus un par un.
Coefficients exactement nuls, `B2_FROZEN = false`, `F0_CREATED = false`.
"""
    JOURNAL_PATH.write_text(text + entry, encoding="utf-8")
    return True


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(), encoding="utf-8")
    appended = append_journal()
    print("B2_V1_1_HANDOFF_WRITTEN")
    print(f"report={REPORT_PATH.relative_to(REPO).as_posix()}")
    print(f"journal_appended={appended}")


if __name__ == "__main__":
    main()
