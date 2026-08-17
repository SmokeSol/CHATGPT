# B2 — Acquisition handoff

Factual counts only. No political interpretation, no effect size, no forecast.

- Branch: `morocco26-b2`
- Gate executed: `B2-3-HISTORICAL-FEATURE-PANEL`
- Result: `FAIL` — the gate stays `OPEN`
- Artifacts: `morocco26/data/goal100/b2_historical_panel.json`, `morocco26/data/goal100/b2_historical_panel_certificate.json`
- Panel SHA-256, reference local run: `fe91b5a71237eae536e691bbeff21d4bb7fcc7ef3c6c98673172929df60eee2f`
  (the panel embeds `generated_at`, so the workflow run recorded in `b2_current_state.json` is
  authoritative; the counts below are invariant across runs)

## 1. Scope actually executed

The frozen protocol `M26-GOAL100-B2-PROTOCOL-V1` sets `agentic_status = PROHIBITED_AND_LOCKED`,
forbids autonomous source discovery, and pins `extraction.llm_used` to the constant `false` in
`b2_evidence_schema_v1.json`. Free-form agentic collection therefore cannot produce a B2 record.

The open gate named by `b2_current_state.json` and by journal entry `A021` was `B2-3`. That gate is a
deterministic computation over already-ingested corpora, and it is what was executed.

Execution properties: `llm_used=false`, `network_access=false`, `source_discovery=false`,
`extraction_method=DETERMINISTIC_STRUCTURED_JOIN`.

## 2. Measured result

| Transition | Role | Features | Identifiable | Mechanical coverage | Core predictive coverage | Minimum |
|---|---|---:|---:|---:|---:|---:|
| `2011_TO_2016` | FIT | 16 | 0 | 0.0 | 0.0 | 0.8 |
| `2016_TO_2021` | VALIDATION | 16 | 0 | 0.0 | 0.0 | 0.8 |

- Territories in scope: 92 certified local constituencies
- Features meeting the binary support minimum (30 positive instances): 0
- Predictive coefficients: all exactly zero, unchanged
- B2 claim records in the store: 0
- Blocking input classes: 17

## 3. Input inventory (measured over the repository, not asserted)

| Input class | Years available |
|---|---|
| `HISTORICAL_LIST_PRESENCE_TARGET_YEAR` | 2011, 2016, 2021 |
| `HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` | 2021 |
| all 16 other declared classes | none |

The two binding gaps are:

1. **`HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR` — absent for every year.** The ingested TAFRA
   legislative corpus is list/party vote-level (92 rows per year), not candidate-level. A column scan
   of the 2011, 2016 and 2021 canonical rows finds no candidate, rank or birthdate field. This blocks
   `B2_M02`, and every one of `B2_P01`–`B2_P06`.
2. **`HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` — present only for 2021.** The fit transition needs 2011
   members and the validation transition needs 2016 members; neither exists in the repository. This
   blocks `B2_P01`–`B2_P04`.

`people_2021` was not substituted for either gap. It is the outcome of the 2021 cycle, so using it to
build a `2016_TO_2021` feature would be post-outcome leakage, and it lists winners rather than
candidates. Both substitutions are recorded as `false` in `leakage_controls` and enforced by the
validator.

## 4. Published diagnostic (not a feature)

`OBSERVED_POSITIVE_LOCAL_LIST_PRESENCE` is measurable and is published so the coverage is not lost:

| Transition | Target year | Territories | Coverage | Positive instances | Distinct parties |
|---|---:|---:|---:|---:|---:|
| `2011_TO_2016` | 2016 | 92/92 | 1.0 | 1343 | 27 |
| `2016_TO_2021` | 2021 | 92/92 | 1.0 | 1472 | 30 |

It does **not** satisfy `B2_M01_BALLOT_LIST_PRESENT`. `B2_M01` requires a certified full-coverage
authoritative ballot table so absent/rejected lists can be set to 0; the corpus carries only positive
vote observations, which establish presence and never absence.

The panel holds 2815 cells: 0 feature cells and 2815 diagnostic cells. They are stored as a
derivation plus a canonical hash rather than copied, because the underlying rows are already
committed in `b2_identity_crosswalk.json`. The validator rebuilds all 2815 cells from that artifact
and fails if the hash differs. No cell encodes an absence as zero.

## 5. Handoff state

```json
{
  "gate": "B2-3-HISTORICAL-FEATURE-PANEL",
  "gate_result": "FAIL",
  "gate_status_after_run": "OPEN",
  "transitions_attempted": 2,
  "features_declared": 16,
  "features_identifiable_fit": 0,
  "features_identifiable_validation": 0,
  "core_predictive_coverage_fit": 0.0,
  "core_predictive_coverage_validation": 0.0,
  "minimum_coverage_required": 0.8,
  "features_meeting_support_minimum": 0,
  "blocking_input_classes": 17,
  "b2_claim_records": 0,
  "leakage_failures": 0,
  "identity_conflicts_open": 0,
  "predictive_coefficients": "ALL_EXACTLY_ZERO",
  "ready_for_b2_backtest": false,
  "blockers": [
    "HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR absent for 2011, 2016 and 2021",
    "HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR absent for 2011 and 2016",
    "14 further declared input classes have no ingested provider"
  ]
}
```

`ready_for_b2_backtest` is `false` because the machine gate says so, not because work stopped.

## 6. Deterministic next actions

Either path is legitimate; neither may move a coefficient.

1. **Close the gap.** Ingest historical candidate rosters (all registered candidates and ranks, not
   winners) for 2016 and 2021, plus 2011 and 2016 elected members, through a versioned historical
   ingest pipeline in the manner of `M26-GOAL100-TAFRA-HISTORY-V1`. Then rerun
   `goal100_build_b2_historical_panel.py`. Note the frozen `b2_source_registry.json` covers 2026
   routes only, so a historical corpus is an ingest act, not a B2 claim-collection act.
2. **Freeze the negative result.** Record that the structured candidate/network/event families are
   not identifiable at the historical cutoff with the present corpus, keep every predictive
   coefficient at exactly zero, and let B2 equal F-1 on those dimensions.

## 7. Repository defects found while executing (not introduced here)

These three validators already fail on pristine `morocco26-b2` HEAD, before any change in this run.
They hard-code a gate state that became false when `B2-2` legitimately closed:

| Validator | Assertion | Status |
|---|---|---|
| `validate_b2_protocol.py:211` | `B2-2` must be `OPEN` | false since `B2-2` closed |
| `validate_b2_source_universe.py:101` | `next_gate` must be `B2-2` | false since `next_gate` became `B2-3` |
| `validate_goal100_tracking.py` | F-1 forecast hash match | `FMINUS1_REGISTRATION_FAIL: forecast hash mismatch` |

They were left unmodified: rewriting a frozen validator's assertions is a versioned protocol act, not
a side effect of this gate.
