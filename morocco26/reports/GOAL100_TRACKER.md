# MOROCCO//26 — Goal100 Forecast Tracker

**Canonical human status page.** Machine truth lives in `morocco26/data/goal100/current_state.json`, `gate_registry.json`, and `forecast_registry.json`.

Last synchronized: **2026-08-16 21:30 Africa/Casablanca**.

## North star

Construire un forecast territorial probabiliste, entièrement gelé et falsifiable, puis déterminer expérimentalement si une intelligence agentique de collecte et de raisonnement résiduel apporte de l'information prédictive supplémentaire au-delà d'une baseline structurelle optimale.

This tracker does **not** award scientific progress for UI, narrative richness, implementation volume, or agent output quality. Progress is gate-based only.

## Current phase

`P6_PROBABILISTIC_FORECAST_ENGINE`

Goal75 remains an immutable 75% scientific checkpoint. Goal100 is a new prospective program layered on top of that checkpoint; old Goal75 evidence is never rewritten.

**Next forecast target:** `F-1` — `STRUCTURAL_PROBABILISTIC_FORECAST`.

F0 is explicitly preliminary. Forecasts before F0 are allowed. Every forecast is immutable and append-only.

## P0 status

| Gate | Status | Current scientific conclusion | Remaining work |
|---|---|---|---|
| P0-1 2026 geometry | **PARTIAL** | Working system is 92 local / 305 seats + 12 regional / 90 seats. Historical modern continuity is 92/92. | Authoritative current-law row diff + legal watch. |
| P0-2 legal allocator | **CLOSED** | Fail-closed current-law allocator certified on 92 local + 12 regional mathematical vectors. | No model blocker. Preserve Casablanca/Marrakech data anomalies. |
| P0-3 registered N | **OPEN** | National N = 15,801,162 exactly. Local N is a constrained latent vector with empirical variance support. | Fit N92 posterior + N-only seat sensitivity. |
| P0-4 historical panel | **CLOSED** | 2011/2016/2021: 92/92 common IDs, normalized names and seat magnitudes. | No core-data blocker. 2007 auxiliary; 2002 quarantined. |
| P0-5 B* | **CLOSED** | Frozen hindcast selects persistence-first vote + turnout cores. | Post-selection parameter fit only; no new model search under v1. |
| P0-6 uncertainty/correlation | **OPEN** | Architecture fixed: national + regional + local innovations, separate turnout state; no free 92x92 covariance. | Fit, posterior predictive diagnostics, variance floors, >=50k simulations. |

Authoritative P0 resolution: `morocco26/data/goal100/p0_resolution_v3.json`.

## Verified findings that must not drift

### Legal allocator

`morocco26/data/goal100/legal_regression_104.json` certifies:

- 92/92 local mathematical-vector equivalence;
- 12/12 regional mathematical-vector equivalence;
- zero unresolved statutory ties in the regression set;
- independent observed regional reproduction remains 10/12;
- Casablanca-Settat and Marrakech-Safi remain explicit data/provenance anomalies, not allocator failures.

### Historical continuity

`morocco26/data/goal100/historical_panel_diagnostic.json` certifies 92/92 common local IDs, names and seat magnitudes across 2011, 2016 and 2021.

### B* selection

Frozen selection protocol: `morocco26/data/goal100/forecast_protocol_v1.json`.

Frozen result: `morocco26/data/goal100/bstar_hindcast_v1.json`.

Selected cores:

- vote composition: `V0_PERSIST`;
- turnout: `T0_PERSIST`.

Validation scores on 2016 -> 2021:

| Vote model | Energy score, lower is better |
|---|---:|
| **V0_PERSIST** | **0.369729** |
| V1_GLOBAL_CLR | 0.413278 |
| V2_REGION_SHRUNK_CLR | 0.426605 |

| Turnout model | CRPS, lower is better |
|---|---:|
| **T0_PERSIST** | **0.094896** |
| T1_GLOBAL_LOGIT_SHIFT | 0.120192 |
| T2_REGION_SHRUNK_LOGIT_SHIFT | 0.121500 |

Interpretation: sophistication is not itself evidence. Historical swing extrapolation lost out-of-sample information relative to persistence in the frozen family. This selects the structural prior family; it does **not** assert that 2026 equals 2021.

## Current critical path to F-1

The first calibrated forecast remains blocked until all five gates below close:

1. `GEO-2026-AUTHORITATIVE-DIFF` — certify current geometry row by row.
2. `N92-POSTERIOR-FIT` — constrained positive-integer 92-local N posterior summing exactly to 15,801,162; report N-only seat sensitivity.
3. `UNCERTAINTY-CALIBRATION` — fit post-selection hierarchical innovation/covariance model and publish retrospective coverage/calibration.
4. `MC-50000-COHERENT` — at least 50,000 joint 395-seat election simulations with valid probability distributions and no unexplained legal failures.
5. `SNAPSHOT-IMMUTABILITY-MANIFEST` — hashes, cutoffs, code/data/parameters/seeds and forecast artifact frozen and registered.

Once these gates close, register **F-1** in `forecast_registry.json`; do not overwrite it later.

## Registered-voter N policy

Exact national constraint:

`sum(N_2026_local[1:92]) = 15,801,162`.

Until authoritative local counts are available, local N remains probabilistic. The current prior centre is based on 2011 local shares rescaled to the exact national 2026 N. `local_N_drift_diagnostic.json` supplies an empirical dispersion anchor from 2007 -> 2011 comparable territories. It is a variance floor / prior diagnostic, **not** proof of stationary local-roll dynamics.

Any later official local N table may only enter via a **new snapshot**. It cannot rewrite old forecasts.

## Uncertainty architecture

A coherent election draw must share shocks across territories:

`party territorial change = national factor + regional factor + local residual + credited structured evidence`.

Turnout is modeled separately on a logit state. Free 92x92 covariance is forbidden because it is not empirically identifiable from the available transitions.

The simulator must generate a **joint election**, not 92 independent forecasts, and then apply the current-law allocator to all local and regional contests before aggregating 395 seats.

## Forecast registry policy

Canonical registry: `morocco26/data/goal100/forecast_registry.json`.

Expected sequence may be:

`F-2 -> F-1 -> F0 -> F1 -> ... -> FINAL`

There is no requirement that F0 be the first forecast. F0 is a conventional preliminary milestone only.

Each snapshot must preserve at minimum:

- data cutoff;
- protocol/version;
- code commit;
- source/data manifest hash;
- parameter hash;
- RNG seed manifest;
- Monte Carlo draw count;
- legal allocator version;
- geometry certificate hash;
- N state;
- candidate/event evidence state;
- forecast artifact hash;
- calibration status;
- known limitations.

## Agentic experiment remains locked

Do **not** start fitting agentic residuals while B2 is moving.

Required order:

`B* -> F-1 structural engine -> B2 frozen -> E_collect / E_reason / E_full preregistration -> prospective scoring`.

Definitions:

- `E_collect - B2`: information-acquisition alpha;
- `E_reason - B2`: residual-reasoning alpha on the same evidence corpus;
- `E_full - B2`: total agentic value.

Narrative quality receives zero credit. The agent survives only through prospective proper-score improvement.

## Anti-drift invariants

- Never change a frozen protocol in place.
- Never erase a failed result.
- Never reuse the consumed Goal75 holdout as untouched tuning evidence.
- After post-selection refit, never describe 2021 as untouched holdout.
- Never convert `UNKNOWN` candidate status to absent/zero.
- Never assign a directional event effect without empirical calibration or a separately preregistered rule.
- Never treat the two regional provenance anomalies as solved by an undocumented list-to-party bridge.
- Never unlock a forecast because an agent produced a plausible narrative.
- Never overwrite a registered forecast.
- 2026 remains the decisive untouched temporal test.

## Machine files

- Current state: `morocco26/data/goal100/current_state.json`
- Gate registry: `morocco26/data/goal100/gate_registry.json`
- Forecast registry: `morocco26/data/goal100/forecast_registry.json`
- Frozen forecast protocol: `morocco26/data/goal100/forecast_protocol_v1.json`
- P0 evidence: `morocco26/data/goal100/p0_resolution_v3.json`
- Historical panel diagnostic: `morocco26/data/goal100/historical_panel_diagnostic.json`
- Legal regression: `morocco26/data/goal100/legal_regression_104.json`
- B* hindcast: `morocco26/data/goal100/bstar_hindcast_v1.json`
- Local-N diagnostic: `morocco26/data/goal100/local_N_drift_diagnostic.json`

The machine validator is `morocco26/scripts/validate_goal100_tracking.py`; CI must pass before this tracker is treated as synchronized.
