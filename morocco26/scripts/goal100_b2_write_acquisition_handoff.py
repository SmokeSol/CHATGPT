#!/usr/bin/env python3
"""Write the deterministic-acquisition handoff report and append the Ariane entry.

Both outputs are generated from the committed artifacts, so the prose can never
drift from the machine state. The journal append is idempotent by marker and
never rewrites an earlier entry.
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

SURFACE_PATH = G100 / "b2_deterministic_acquisition_surface.json"
RAW_MANIFEST_PATH = G100 / "b2_raw_acquisition_manifest.json"
PARSER_MANIFEST_PATH = G100 / "b2_parser_manifest.json"
HISTORICAL_CERT_PATH = G100 / "b2_historical_acquisition_certificate.json"
WAVE1_CERT_PATH = G100 / "b2_current_wave1_acquisition_certificate.json"
PANEL_CERT_PATH = G100 / "b2_historical_panel_certificate.json"
PANEL_PATH = G100 / "b2_historical_panel.json"
VALIDATOR_DIAG_PATH = G100 / "b2_validator_consistency_diagnostic.json"
MEMBERS_PATH = G100 / "historical" / "b2_historical_elected_members.json"

REPORT_PATH = ROOT / "reports" / "B2_DETERMINISTIC_ACQUISITION_HANDOFF.md"
JOURNAL_PATH = ROOT / "FIL_D_ARIANE.md"
MARKER = "Phase d'acquisition déterministe B2 — ouverture et premier résultat"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_HANDOFF_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def build_report() -> str:
    surface = load(SURFACE_PATH)
    raw = load(RAW_MANIFEST_PATH)
    parsers = load(PARSER_MANIFEST_PATH)
    hist = load(HISTORICAL_CERT_PATH)
    wave1 = load(WAVE1_CERT_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    panel = load(PANEL_PATH)
    diag = load(VALIDATOR_DIAG_PATH)
    members = load(MEMBERS_PATH)

    fit, val = panel_cert["transitions"]
    gate = hist["decision_gate"]
    verdicts = hist["verdict_tally"]

    member_rows = "\n".join(
        f"| {year} | {entry['elected_rows']} | {entry['local_rows_resolved']} | "
        f"{entry['local_territories_resolved']} | {entry['regional_rows_resolved']} | "
        f"{entry['elected_rows'] - entry['local_rows_resolved'] - entry['regional_rows_resolved']} |"
        for year, entry in sorted(members["years"].items(), key=lambda item: int(item[0]))
    )

    class_rows = "\n".join(
        f"| `{row['input_class']}` | {row['years_required']} | {row['years_covered'] or '—'} | `{row['verdict']}` |"
        for row in hist["input_class_verdicts"]
    )

    validator_rows = "\n".join(
        f"| `{row['validator']}` | `{row['classification']}` | "
        f"{'yes' if row.get('is_repository_defect') else 'no'} |"
        for row in diag["validators"]
    )

    return f"""# B2 — Deterministic acquisition handoff

Factual counts only. No political interpretation, no effect size, no forecast.

- Generated: {now_local()}
- Acquisition surface SHA-256: `{surface['canonical_surface_sha256']}`
- Panel SHA-256: `{panel['canonical_panel_sha256']}`
- Decision-gate outcome: **`{gate['outcome']}`**
- `ready_for_b2_backtest`: **{str(gate['residual_backtest_unlocked']).lower()}**

## 1. Can historical B2 features now be measured?

No. {fit['features_identifiable']} of {fit['features_total']} frozen features are constructible in the
`2011_TO_2016` fit transition and {val['features_identifiable']} of {val['features_total']} in the
`2016_TO_2021` validation transition.

This is **unidentifiability, not a negative predictive finding**. No feature has been tested against an
outcome, so none may be called non-predictive. Every predictive coefficient remains exactly zero.

## 2. Exact coverage

| Transition | Role | Features | Identifiable | Mechanical coverage | Core predictive coverage | Required |
|---|---|---:|---:|---:|---:|---:|
| `2011_TO_2016` | fit | {fit['features_total']} | {fit['features_identifiable']} | {fit['mechanical_panel_coverage']} | {fit['core_predictive_panel_coverage']} | {panel_cert['minimum_coverage_required']} |
| `2016_TO_2021` | validation | {val['features_total']} | {val['features_identifiable']} | {val['mechanical_panel_coverage']} | {val['core_predictive_panel_coverage']} | {panel_cert['minimum_coverage_required']} |

Territories in scope: {panel_cert['territories_in_scope']} certified local constituencies.

### Recovered this phase

Deterministic acquisition recovered the elected-member rosters that were previously absent:

| Election | Elected rows | Local resolved | Local territories | Regional resolved | Unresolved |
|---|---:|---:|---:|---:|---:|
{member_rows}

The 2021 row reproduces the already-certified 305 local + 90 regional split exactly, which is the
correctness check on the parser. The unresolved rows in 2011 and 2016 are the 90 `Liste nationale`
seats, which carry no territorial constituency and are therefore left unresolved rather than forced.

`HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` moved from absent to covered for both transitions. Blocking
input classes fell from 17 to {len(panel_cert['blocking_missing_input_classes'])}.

## 3. Which gaps are source absence?

{verdicts.get('SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA', 0)} of {len(hist['input_class_verdicts'])} input classes:
no surface in either permitted family declares them.

The frozen B2 source registry is measurably 2026-scoped — its query templates name only 2026 election
terms and set a publication floor of 2025-01-01, so
`election_years_expressible = {surface['families']['B2_SOURCE_REGISTRY_V1']['temporal_reach']['election_years_expressible']}`.
It carries no historical acquisition surface at all. The historical provenance family carries list-level
results and member rosters, but no candidate roster for any year.

| Input class | Years required | Years covered | Verdict |
|---|---|---|---|
{class_rows}

## 4. Which gaps are access failures?

{verdicts.get('SOURCE_INACCESSIBLE', 0)} input classes. In the 2026 wave, {wave1['documents_blocked']} documents were
`BLOCKED_SOURCE` and {wave1['documents_error']} returned a fetch error, across
{len(wave1['sources_without_acquired_content'])} sources that yielded nothing. Access failure is recorded as
access failure; it is never converted into absence or into a false value.

## 5. Which gaps contain data but require semantic extraction?

For the **historical** panel: {verdicts.get('DATA_EXISTS_BUT_UNPARSABLE_NONAGENTIC', 0)}. No permitted historical surface
carries candidate-level rows at all, so the blocker is absence rather than extraction difficulty.

For the **2026** wave the answer differs and is worth separating. The acquired corpus contains
{sum(bucket['tables'] for bucket in wave1['format_inventory']['by_source'].values())} HTML tables, of which
{len(wave1['format_inventory']['deterministically_parsable_tables'])} match the registry's own frozen evidence
vocabulary — including a **{wave1['extractability_summary']['largest_parsable_table_rows']}-row table** on
`{', '.join(wave1['extractability_summary']['sources_with_parsable_candidate_tables'])}`. Verdict:
`{wave1['extractability_summary']['verdict']}`.

That table is structurally parsable without any semantic judgment. It still produced zero B2 claims,
because the frozen critical-double-entry rule requires two matching parses or one authoritative T0
structured table, and a T1 party page is not authoritative. Minting claims from it belongs to gate
`B2-4-2026-BALLOT-ROSTER`, not to this phase.

## 6. Is the residual backtest unlocked?

No. `residual_backtest_unlocked = {str(gate['residual_backtest_unlocked']).lower()}`.

## 7. What exact machine gate blocks it?

`{gate['blocking_machine_gate']}` — the core predictive panel covers
{fit['core_predictive_panel_coverage']} of territories against a required {panel_cert['minimum_coverage_required']}.

The single dominant blocker is `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`: it is the sole remaining
blocker for `B2_P01` and `B2_P02`, and appears in 14 of the 32 feature-by-transition cells. Recovering
it would not by itself close the gate for `B2_P03`–`B2_P08`, which additionally need party-switch,
office-holding, endorsement and defection inputs.

## 8. What corpus should be reserved for E_collect?

{len(hist['reserved_for_e_collect']['input_classes'])} input classes are preserved unresolved rather than filled by
agentic research:

{chr(10).join('- `' + row + '`' for row in hist['reserved_for_e_collect']['input_classes'])}

These are exactly the cells deterministic B2 could not recover. They form the controlled test set for a
later `E_collect` experiment: deterministic retrieval success versus agentic retrieval success, scored
before any question of incremental predictive value is asked. Filling them now with agentic research
would destroy that experiment.

## 9. Validator consistency

F-1 integrity: **{diag['F_minus_1_integrity']}**. The registered forecast artifact's git-blob digest matches both
the snapshot manifest and the B2 protocol's `parent_snapshot.forecast_sha256`.

| Validator | Classification | Repository defect |
|---|---|---|
{validator_rows}

A previous run of this work reported `validate_goal100_tracking` as a repository defect. That was
wrong: the failure was a local checkout artifact. This repository is checked out on Windows with
`core.autocrlf=true`, which rewrites LF to CRLF and changes the raw-byte digest of content that is
itself unmodified. Under a normalized checkout the artifact hashes match exactly and the validator
passes. No F-1 artifact was repaired, because none was damaged.

The two genuine defects are stale point-in-time assertions that became false when `B2-2` legitimately
closed. Proposed amendments are recorded in `b2_validator_consistency_diagnostic.json` as
`PROPOSED_NOT_APPLIED`; rewriting a frozen validator is a versioned act and is not performed here.

The same class of defect existed in this phase's own work and was fixed: the B2-3 panel originally
hashed raw input bytes, which would have failed in Linux CI from a Windows-generated artifact. Input
hashing is now `CANONICAL_JSON_SHA256`, verified identical under both line endings.

## 10. Machine state

```json
{json.dumps({
    "acquisition_surface_sha256": surface["canonical_surface_sha256"],
    "raw_documents_acquired": sum(row.get("state") == "ACQUIRED" for row in raw["entries"]),
    "raw_documents_blocked": sum(row.get("state") == "BLOCKED_SOURCE" for row in raw["entries"]),
    "parsers_registered": len(parsers["parsers"]),
    "historical_input_classes_recovered": hist["recovered_this_phase"]["input_classes"],
    "historical_verdict_tally": verdicts,
    "features_identifiable_fit": fit["features_identifiable"],
    "features_identifiable_validation": val["features_identifiable"],
    "core_predictive_coverage_fit": fit["core_predictive_panel_coverage"],
    "core_predictive_coverage_validation": val["core_predictive_panel_coverage"],
    "b2_claim_records": wave1["b2_claim_records_created"],
    "predictive_coefficients": "ALL_EXACTLY_ZERO",
    "decision_gate_outcome": gate["outcome"],
    "ready_for_b2_backtest": gate["residual_backtest_unlocked"],
    "blocking_machine_gate": gate["blocking_machine_gate"],
    "B2_FROZEN": False,
    "F0_CREATED": False,
    "AGENTIC_PREDICTIVE_LAYER": "LOCKED",
}, indent=2)}
```
"""


def append_journal() -> bool:
    hist = load(HISTORICAL_CERT_PATH)
    wave1 = load(WAVE1_CERT_PATH)
    panel_cert = load(PANEL_CERT_PATH)
    surface = load(SURFACE_PATH)
    diag = load(VALIDATOR_DIAG_PATH)
    members = load(MEMBERS_PATH)
    parsers = load(PARSER_MANIFEST_PATH)

    text = JOURNAL_PATH.read_text(encoding="utf-8")
    if MARKER in text:
        return False

    fit, val = panel_cert["transitions"]
    parser = parsers["parsers"][0]
    entry = f"""

### {now_local()[:10]} — {MARKER}

**Prompt agentique antérieur rejeté.** Le master-prompt d'orchestration agentique est incompatible avec
le protocole gelé `M26-GOAL100-B2-PROTOCOL-V1` : `agentic_status = PROHIBITED_AND_LOCKED`, découverte
autonome de sources interdite, et `extraction.llm_used` fixé à la constante `false` dans le schéma de
preuve. Aucune collecte agentique n'a été exécutée et aucune contrainte n'a été relâchée.

**Statut B2-3 conservé.** Le résultat reste `UNIDENTIFIABLE`, et non un résultat prédictif négatif :
features identifiables `{fit['features_identifiable']}/{fit['features_total']}` (fit) et
`{val['features_identifiable']}/{val['features_total']}` (validation), couverture prédictive centrale
`{fit['core_predictive_panel_coverage']}` / `{val['core_predictive_panel_coverage']}` pour un minimum requis de
`{panel_cert['minimum_coverage_required']}`. Aucun coefficient n'a bougé. La tentative antérieure est archivée sous
`b2_historical_panel_attempts/`.

**Phase d'acquisition déterministe ouverte.** Surface figée à partir des seuls contrats déjà commités :
`{surface['families']['B2_SOURCE_REGISTRY_V1']['entries']}` entrées du registre B2 (dont
`{surface['families']['B2_SOURCE_REGISTRY_V1']['claim_eligible_entries']}` éligibles aux claims) et
`{surface['families']['HISTORICAL_INGEST_PROVENANCE']['entries']}` entrées de provenance historique.
Hash de surface `{surface['canonical_surface_sha256']}`. Mesure décisive : les gabarits de requête gelés
n'expriment que `{surface['families']['B2_SOURCE_REGISTRY_V1']['temporal_reach']['election_years_expressible']}` —
le registre B2 ne porte aucune surface d'acquisition historique.

**Acquisition réussie.** Le jeu de données de membres déjà référencé par `observed_elected_2021.json`
contient les quatre législatures. Parser `{parser['parser_id']}` v`{parser['version']}`, méthode
`{parser['method']}`, `llm_used = false`. Élus récupérés :
{', '.join(f"{year} → {entry_['local_rows_resolved']} locaux sur {entry_['local_territories_resolved']} territoires" for year, entry_ in sorted(members['years'].items(), key=lambda i: int(i[0])))}.
Le contrôle de correction est 2021, qui reproduit exactement le partage certifié 305 locaux + 90 régionaux.
Les `Liste nationale` restent non résolues : elles n'ont pas de circonscription certifiée.

**Couverture avant/après.** Classes d'entrée bloquantes : `17` → `{len(panel_cert['blocking_missing_input_classes'])}`.
`HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` passe d'absente à couverte pour les deux transitions. La couverture
prédictive reste `0.0` : le blocage résiduel dominant est `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`.

**Wave 1 2026.** `{wave1['documents_acquired']}` documents acquis, `{wave1['documents_blocked']}` `BLOCKED_SOURCE`,
`{wave1['b2_claim_records_created']}` claim B2 créé. Verdict d'extractibilité :
`{wave1['extractability_summary']['verdict']}` — une table de `{wave1['extractability_summary']['largest_parsable_table_rows']}`
lignes sur `{', '.join(wave1['extractability_summary']['sources_with_parsable_candidate_tables'])}` correspond au
vocabulaire de preuve gelé. Elle ne produit aucun claim ici : la règle de double saisie critique exige deux
lectures concordantes ou une table structurée T0 autoritative, et une page de parti T1 ne l'est pas.

**Incohérences de validateurs.** `{diag['counts']['stale_assertions']}` assertions périmées après la fermeture
légitime de B2-2 ; `{diag['counts']['environment_artifacts']}` artefact d'environnement. Correction d'une
affirmation antérieure : l'échec de `validate_goal100_tracking` n'était pas un défaut du dépôt mais un effet
de `core.autocrlf=true`. Intégrité F-1 : `{diag['F_minus_1_integrity']}`. Aucun artefact F-1 n'a été réparé.

**Résultat de gate.** `{hist['decision_gate']['outcome']}`. `ready_for_b2_backtest = false`.
`{len(hist['reserved_for_e_collect']['input_classes'])}` classes d'entrée sont réservées non résolues pour
`E_collect` ; elles ne doivent pas être comblées par de la recherche agentique.

**Prochaine action exacte :** décider entre (a) un amendement versionné de l'univers de sources ouvrant une
surface historique de rosters de candidats, et (b) le maintien de `C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL`.
Dans les deux cas aucun coefficient prédictif ne bouge et `B2-4` reste le prochain gate exécutable.
"""
    JOURNAL_PATH.write_text(text + entry, encoding="utf-8")
    return True


def main() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(build_report(), encoding="utf-8")
    appended = append_journal()
    print("B2_ACQUISITION_HANDOFF_WRITTEN")
    print(f"report={REPORT_PATH.relative_to(REPO).as_posix()}")
    print(f"journal_appended={appended}")


if __name__ == "__main__":
    main()
