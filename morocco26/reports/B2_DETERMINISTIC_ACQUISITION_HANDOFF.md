# B2 — Deterministic acquisition handoff

Factual counts only. No political interpretation, no effect size, no forecast.

- Generated: 2026-08-17T11:03:48+01:00
- Acquisition surface SHA-256: `d51c5b7ff0fceec2e2f5ab439abb23ffbe369d7040c795e0b28fa336b8803059`
- Panel SHA-256: `797dcee2e211a14dea2a335863974c1905a3ec97aa6a74d5b018b598ff7078ae`
- Decision-gate outcome: **`C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL`**
- `ready_for_b2_backtest`: **false**

## 1. Can historical B2 features now be measured?

No. 0 of 16 frozen features are constructible in the
`2011_TO_2016` fit transition and 0 of 16 in the
`2016_TO_2021` validation transition.

This is **unidentifiability, not a negative predictive finding**. No feature has been tested against an
outcome, so none may be called non-predictive. Every predictive coefficient remains exactly zero.

## 2. Exact coverage

| Transition | Role | Features | Identifiable | Mechanical coverage | Core predictive coverage | Required |
|---|---|---:|---:|---:|---:|---:|
| `2011_TO_2016` | fit | 16 | 0 | 0.0 | 0.0 | 0.8 |
| `2016_TO_2021` | validation | 16 | 0 | 0.0 | 0.0 | 0.8 |

Territories in scope: 92 certified local constituencies.

### Recovered this phase

Deterministic acquisition recovered the elected-member rosters that were previously absent:

| Election | Elected rows | Local resolved | Local territories | Regional resolved | Unresolved |
|---|---:|---:|---:|---:|---:|
| 2007 | 325 | 225 | 74 | 0 | 100 |
| 2011 | 395 | 305 | 92 | 0 | 90 |
| 2016 | 395 | 305 | 92 | 0 | 90 |
| 2021 | 395 | 305 | 92 | 90 | 0 |

The 2021 row reproduces the already-certified 305 local + 90 regional split exactly, which is the
correctness check on the parser. The unresolved rows in 2011 and 2016 are the 90 `Liste nationale`
seats, which carry no territorial constituency and are therefore left unresolved rather than forced.

`HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` moved from absent to covered for both transitions. Blocking
input classes fell from 17 to 16.

## 3. Which gaps are source absence?

16 of 18 input classes:
no surface in either permitted family declares them.

The frozen B2 source registry is measurably 2026-scoped — its query templates name only 2026 election
terms and set a publication floor of 2025-01-01, so
`election_years_expressible = [2026]`.
It carries no historical acquisition surface at all. The historical provenance family carries list-level
results and member rosters, but no candidate roster for any year.

| Input class | Years required | Years covered | Verdict |
|---|---|---|---|
| `HISTORICAL_CAMPAIGN_LAUNCH_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_CANDIDATE_BIRTHDATE_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_CANDIDATE_DISQUALIFICATION_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_CANDIDATE_RANK_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_CANDIDATE_WITHDRAWAL_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_DEATH_OR_INCAPACITY_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` | [2011, 2016] | [2011, 2016] | `DATA_EXISTS_AND_PARSED` |
| `HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_LIST_PRESENCE_TARGET_YEAR` | [2016, 2021] | [2016, 2021] | `DATA_EXISTS_AND_PARSED` |
| `HISTORICAL_LIST_REJECTION_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_OFFICIAL_INVESTIGATION_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_OFFICIAL_SANCTION_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_PARTY_OFFICE_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |
| `HISTORICAL_PARTY_SWITCH_TARGET_YEAR` | [2016, 2021] | — | `SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA` |

## 4. Which gaps are access failures?

0 input classes. In the 2026 wave, 10 documents were
`BLOCKED_SOURCE` and 15 returned a fetch error, across
8 sources that yielded nothing. Access failure is recorded as
access failure; it is never converted into absence or into a false value.

## 5. Which gaps contain data but require semantic extraction?

For the **historical** panel: 0. No permitted historical surface
carries candidate-level rows at all, so the blocker is absence rather than extraction difficulty.

For the **2026** wave the answer differs and is worth separating. The acquired corpus contains
19 HTML tables, of which
1 match the registry's own frozen evidence
vocabulary — including a **93-row table** on
`T1_PJD_OFFICIAL`. Verdict:
`DETERMINISTIC_ROSTER_SURFACE_EXISTS_FOR_2026`.

That table is structurally parsable without any semantic judgment. It still produced zero B2 claims,
because the frozen critical-double-entry rule requires two matching parses or one authoritative T0
structured table, and a T1 party page is not authoritative. Minting claims from it belongs to gate
`B2-4-2026-BALLOT-ROSTER`, not to this phase.

## 6. Is the residual backtest unlocked?

No. `residual_backtest_unlocked = false`.

## 7. What exact machine gate blocks it?

`B2-3-HISTORICAL-FEATURE-PANEL` — the core predictive panel covers
0.0 of territories against a required 0.8.

The single dominant blocker is `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`: it is the sole remaining
blocker for `B2_P01` and `B2_P02`, and appears in 14 of the 32 feature-by-transition cells. Recovering
it would not by itself close the gate for `B2_P03`–`B2_P08`, which additionally need party-switch,
office-holding, endorsement and defection inputs.

## 8. What corpus should be reserved for E_collect?

16 input classes are preserved unresolved rather than filled by
agentic research:

- `HISTORICAL_CAMPAIGN_LAUNCH_TARGET_YEAR`
- `HISTORICAL_CANDIDATE_BIRTHDATE_TARGET_YEAR`
- `HISTORICAL_CANDIDATE_DISQUALIFICATION_TARGET_YEAR`
- `HISTORICAL_CANDIDATE_RANK_TARGET_YEAR`
- `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`
- `HISTORICAL_CANDIDATE_WITHDRAWAL_TARGET_YEAR`
- `HISTORICAL_DEATH_OR_INCAPACITY_TARGET_YEAR`
- `HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR`
- `HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR`
- `HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR`
- `HISTORICAL_LIST_REJECTION_TARGET_YEAR`
- `HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR`
- `HISTORICAL_OFFICIAL_INVESTIGATION_TARGET_YEAR`
- `HISTORICAL_OFFICIAL_SANCTION_TARGET_YEAR`
- `HISTORICAL_PARTY_OFFICE_TARGET_YEAR`
- `HISTORICAL_PARTY_SWITCH_TARGET_YEAR`

These are exactly the cells deterministic B2 could not recover. They form the controlled test set for a
later `E_collect` experiment: deterministic retrieval success versus agentic retrieval success, scored
before any question of incremental predictive value is asked. Filling them now with agentic research
would destroy that experiment.

## 9. Validator consistency

F-1 integrity: **INTACT**. The registered forecast artifact's git-blob digest matches both
the snapshot manifest and the B2 protocol's `parent_snapshot.forecast_sha256`.

| Validator | Classification | Repository defect |
|---|---|---|
| `validate_b2_protocol` | `STALE_ASSERTION_AFTER_LEGITIMATE_TRANSITION` | yes |
| `validate_b2_source_universe` | `STALE_ASSERTION_AFTER_LEGITIMATE_TRANSITION` | yes |
| `validate_goal100_tracking` | `ENVIRONMENT_LINE_ENDING` | no |
| `validate_b2_historical_panel` | `CONSISTENT` | no |
| `validate_anti_drift` | `CONSISTENT` | no |

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
{
  "acquisition_surface_sha256": "d51c5b7ff0fceec2e2f5ab439abb23ffbe369d7040c795e0b28fa336b8803059",
  "raw_documents_acquired": 34,
  "raw_documents_blocked": 10,
  "parsers_registered": 1,
  "historical_input_classes_recovered": [
    "HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR",
    "HISTORICAL_LIST_PRESENCE_TARGET_YEAR"
  ],
  "historical_verdict_tally": {
    "DATA_EXISTS_AND_PARSED": 2,
    "SOURCE_UNIVERSE_HAS_NO_RELEVANT_DATA": 16
  },
  "features_identifiable_fit": 0,
  "features_identifiable_validation": 0,
  "core_predictive_coverage_fit": 0.0,
  "core_predictive_coverage_validation": 0.0,
  "b2_claim_records": 0,
  "predictive_coefficients": "ALL_EXACTLY_ZERO",
  "decision_gate_outcome": "C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL",
  "ready_for_b2_backtest": false,
  "blocking_machine_gate": "B2-3-HISTORICAL-FEATURE-PANEL",
  "B2_FROZEN": false,
  "F0_CREATED": false,
  "AGENTIC_PREDICTIVE_LAYER": "LOCKED"
}
```
