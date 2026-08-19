# MOROCCO//26 — Current State

**Handover synchronization date:** 2026-08-19  
**Canonical integration branch after handover:** `main`  
**Machine authority:** `data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

This file contains only the current operational state. Historical development is kept elsewhere and must not override it.

## Current forecast

**Status:** `PROMOTED`  
**Forecast ID:** `M26-PROBABILISTIC-FORECAST-2026-V1`  
**Target:** Morocco legislative election 2026, 395 seats.

### Point model

- National model: `PREVIOUS_NATIONAL_PERSISTENCE`.
- Why: it won the frozen rolling-origin national tournament over 2002→2007, 2007→2011, 2011→2016 and 2016→2021.
- Territorial rule: `HALF_SHRINK`, `lambda = 0.5`.
- Why: it won all three territorial folds 2007→2011, 2011→2016 and 2016→2021.
- Current-only political signals included in the point: **none**.

### Uncertainty

- National uncertainty gate: PASS.
- Conditional geography uncertainty gate: PASS.
- Combined national + geography gate: PASS on 1,656 territory×party cells.
- Combined coverage: 89.07% at nominal 80%; 98.67% at nominal 95%.
- Mandatory caution: RNI-specific historical coverage is weaker than pooled coverage and has not been tuned away post hoc.

### Final simulation

- Draws: 50,000.
- Contests per draw: 104 = 92 local + 12 regional.
- Seats per draw: exactly 395.
- Legal failures: zero unique-list threshold failures; zero unfilled-seat exceptions; zero unresolved statutory ties after the frozen exchangeable-age prior.
- Joint seat-stream SHA256: `a10becb1e85c2b3327e9430cd76c7801e6d3f515046ab8ec991c787e016bdf0d`.
- Generated forecast JSON SHA256: `c7ab03321c0e3883048862a6d94faeb545066ea996a81a710691c6085f5726d6`.
- Canonical CI run: `32289928633`.
- Canonical CI artifact: `9379123421`.

## Current promoted national seat summary

| Party | Mean seats | Median | P(first or tied) |
|---|---:|---:|---:|
| RNI | 88.38 | 98 | 51.01% |
| PAM | 65.11 | 72 | 16.51% |
| PI | 62.70 | 67 | 16.94% |
| USFP | 35.08 | 28 | 4.42% |
| OTHER | 32.27 | 22 | 4.31% |
| MP | 31.19 | 24 | 1.96% |
| PPS | 28.91 | 18 | 3.69% |
| PJD | 27.22 | 15 | 2.80% |
| UC | 24.12 | 18 | 0.22% |

These are distributions from the current structural forecast, not claims that the election outcome is known.

## Current evidence/admission state

### Candidate and list facts

May be collected and verified now. They do **not** automatically receive vote effects.

### Predictive candidate layer

**No new 2026 candidate/current-information class is currently admitted as a numeric predictive adjustment to the V4 baseline.**

Any proposed predictive class must first improve frozen historical out-of-sample scoring under a preregistered admission test.

### Mechanical updates

Verified ballot/list registration, withdrawal, disqualification, rank, legally relevant age, official registered-voter counts, legal rules or geometry can change the mechanics of a **new** snapshot. They never rewrite a prior snapshot.

### Agentic layer

Agentic collection/reasoning remains an incremental-value experiment. It must beat the frozen baseline on proper scoring; plausible narrative output has no forecast authority.

## Immutable historical lineages

- `F-1`: immutable registered structural forecast.
- `B2`: frozen negative deterministic structured-evidence result.
- `F0`: immutable registered preliminary forecast, exact zero-delta over F-1 under B2.
- Forecast-Lab V4 is a separate later research lineage and currently the strongest promoted baseline.

## Product branch

`atlas395-v0` is the publication/product branch used by the scheduled daily Atlas workflow. Product updates must not silently alter frozen science.

## Next scientific objective

Build and run the **incremental intelligence tournament** against the promoted V4 baseline:

1. candidate/list information classes;
2. other historically comparable structured information classes;
3. agentic collection;
4. agentic residual reasoning;
5. combinations only when individually justified.

The admission criterion is measurable out-of-sample improvement, not political plausibility.

## Next action when new 2026 information arrives

Follow `docs/LIVE_2026_UPDATE_RUNBOOK.md`. If no admission/mechanical gate is passed, the correct output is often: **evidence updated, forecast unchanged**.
