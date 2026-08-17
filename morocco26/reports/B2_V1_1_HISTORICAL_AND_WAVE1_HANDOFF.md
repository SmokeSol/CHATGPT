# B2 V1.1 — historical source-surface amendment and Wave-1 handoff

Numeric answers only. No political interpretation, no effect size, no forecast.

- Generated: 2026-08-17T11:52:32+01:00
- Amendment: `M26-GOAL100-B2-HISTORICAL-SOURCE-SURFACE-V1.1`, frozen `2026-08-17T11:14:31+01:00` **before** acquisition
- Source-surface SHA-256: `e0fe3585d24ca50fe023b1d7747ae2dba4f0be946dbe86b6a56e33caebf158df`
- Source-surface certificate: `PASS` (10 checks)
- **Termination state: `B2_3_DATA_BLOCKED_NONAGENTIC`**
- **B2-4 state: `B2_4_FAIL`**

## 1. Historical candidate rosters recovered?

**No.** `roster_dataset_found = false`
across 1093 enumerated dataset/package names.
Required years [2016, 2021]; recovered coverage **0/92 territories in both**.

Previously recovered and preserved (elected members, not candidate rosters):

| Election | Elected rows | Local resolved | Territories |
|---|---:|---:|---:|
| 2007 | 325 | 225 | 74/92 |
| 2011 | 395 | 305 | 92/92 |
| 2016 | 395 | 305 | 92/92 |
| 2021 | 395 | 305 | 92/92 |

### Secondary targets (§7): named candidate surfaces in the amended catalog

| Input class | Named surface | Matches | Status |
|---|---|---:|---|
| `HISTORICAL_CANDIDATE_RANK_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |
| `HISTORICAL_FORMAL_ALLIANCE_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |
| `HISTORICAL_FORMAL_DEFECTION_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |
| `HISTORICAL_FORMAL_ENDORSEMENT_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |
| `HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR` | yes | 4 | `CANDIDATE_SURFACE_IDENTIFIED_NOT_YET_PARSED` |
| `HISTORICAL_PARTY_OFFICE_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |
| `HISTORICAL_PARTY_SWITCH_TARGET_YEAR` | no | 0 | `NO_NAMED_SURFACE_IN_AMENDED_CATALOG` |

`HISTORICAL_LOCAL_OFFICE_HOLDING_TARGET_YEAR` is the one secondary class that gained a named surface:
`composition-des-conseils-communaux-2015/2021` and `-regionaux`. It stays blocked, because `B2_P05`
also requires the candidate roster. A leakage constraint applies if it is ever used: the 2021 communal
election fell on 2021-09-08, the same day as the 2021 legislative election, so 2021 council
composition is not knowable before the 2021 legislative cutoff — office held at that cutoff derives
from the 2015 councils.

### Near-matches rejected by the matcher

- none

The first pass of this scan reported a roster as found. It was a substring artifact:
`avis-de-candidature-aux-emplois-superieurs-publics` is a civil-service vacancy notice, and it matched
because "candidature" contains "candidat". A second artifact matched `rang` inside "etranger". The
matcher now requires word boundaries plus an electoral qualifier, and both disappear. Had this not
been caught, the run would have claimed a recovered roster that does not exist.

## 2. B2-3 features identifiable, fit transition

**0/16** (`2011_TO_2016`)

## 3. B2-3 features identifiable, validation transition

**0/16** (`2016_TO_2021`)

## 4. Core predictive coverage vs the 0.8 threshold

| Transition | Coverage | Threshold | Meets |
|---|---:|---:|---|
| `2011_TO_2016` | 0.0 | 0.8 | no |
| `2016_TO_2021` | 0.0 | 0.8 | no |

Threshold unchanged: `true`.

## 5. Is the residual backtest unlocked?

**No.** Blocking machine gate: `B2-3-HISTORICAL-FEATURE-PANEL`, still `OPEN`.

## 6. Current 2026 Wave-1 verified roster coverage

| Metric | Value |
|---|---:|
| Rows parsed | 92 |
| Distinct constituencies in table | 92 |
| Territories resolved to certified IDs | 0/92 |
| Territory coverage | 0.0 |
| **Verified double-entry rows** | **0** |
| Single-source rows | 0 |
| Ambiguous deterministic match | 92 |
| Conflicts | 0 |
| Blocked source documents | 10 |
| B2 claim records created | 0 |

Source-class breakdown: T0 authoritative structured tables
0, T1 party official
1, T2 media
0. Parties covered: ['PJD'].

The table parsed perfectly — 92 rows, 92 distinct constituencies, 92 distinct list-agent names, 0
malformed rows. It resolves to zero certified territory IDs because the roster is written in Arabic
and the certified crosswalk carries Latin-script aliases only. Resolving them would require either
transliteration judgment, which the identity protocol forbids, or a versioned Arabic territory-alias
amendment reviewed entry by entry. Neither is performed here.

## 7. Exact B2-4 gate state

`B2_4_FAIL` — gate remains `OPEN`. Two independent blockers, both machine-checked:

1. `NO_ROW_SATISFIES_CRITICAL_DOUBLE_ENTRY` — the only roster source is T1, and the frozen rule needs
   two matching parses or one authoritative T0 structured table. Corroboration was searched across
   29 documents in
   11 independence clusters and found none.
2. `TERRITORY_COVERAGE_INCOMPLETE` — 0.0 against a required 1.0.

## 8. Unresolved cells reserved for E_collect

`e_collect_executed = false`.

16 historical input classes:

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

Plus 92 unresolved 2026 roster rows.

## 9. Did any coefficient move?

**No.** `ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION` — `coefficients_all_zero = true`.

## 10. Did F-1 change?

**No.** The source-surface certificate check `F_MINUS_1_UNCHANGED` passed: the declared, manifest and
protocol digests all agree.

## Amended surface: what the enumeration actually returned

| Surface | Requests | Acquired | Blocked | Truncated | Captures | Exhaustion claimable |
|---|---:|---:|---:|---:|---:|---|
| `H1_OPENAFRICA_CATALOG` | 5 | 2 | 3 | 0 | 0 | no |
| `H2_HUGGINGFACE_ELECTRICSHEEPAFRICA` | 6 | 6 | 0 | 1 | 0 | no |
| `H3_WEB_ARCHIVE_OF_REGISTERED_DOMAINS` | 126 | 9 | 22 | 4 | 11258 | no |

`B2_3_DATA_BLOCKED_NONAGENTIC` was selected because: Exhaustion is not established. Blocked or failing surfaces: ['H1_OPENAFRICA_CATALOG', 'H3_WEB_ARCHIVE_OF_REGISTERED_DOMAINS']. Truncated enumerations: ['H2_HUGGINGFACE_ELECTRICSHEEPAFRICA', 'H3_WEB_ARCHIVE_OF_REGISTERED_DOMAINS']. Pre-cutoff archived material reachable but not deterministically parsable into the required input classes: 11258 captures.

Exhaustion is only claimable when a surface is both fully enumerated and reachable. A truncated
enumeration or a blocked route cannot support a claim that nothing exists, which is why this run does
not report `B2_3_UNIDENTIFIABLE_AFTER_V1_1_EXHAUSTION` merely because no roster was found.

## Invariants

```json
{
  "coefficients": "ALL_EXACTLY_ZERO_PENDING_HISTORICAL_CALIBRATION",
  "F_minus_1": "IMMUTABLE",
  "B2_FROZEN": false,
  "F0_CREATED": false,
  "AGENTIC_PREDICTIVE_LAYER": "LOCKED",
  "E_collect_executed": false,
  "b2_3_gate": "OPEN",
  "b2_4_gate": "OPEN",
  "feature_definitions_changed": false,
  "thresholds_changed": false,
  "v1_registry_edited": false
}
```
