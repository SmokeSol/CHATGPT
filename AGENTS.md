# MOROCCO//26 — AI Maintainer Instructions

This file is the first entry point for any AI or human maintaining this repository.

## Canonical branch

After the handover merge, `main` is the canonical integration branch. Do not resume work from an old research branch simply because its name sounds more recent. `atlas395-v0` is a separate publication/product branch used by the daily Atlas workflow.

## Read in this order

1. `README.md`
2. `morocco26/HANDOVER.md`
3. `morocco26/CURRENT_STATE.md`
4. `morocco26/NORTH_STAR.md`
5. `morocco26/docs/LIVE_2026_UPDATE_RUNBOOK.md`
6. `morocco26/data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`
7. `morocco26/STATUS.md`

Historical documents, old branches, failed runs and prior forecast lineages remain valuable audit evidence, but they do not override the files above.

## Current scientific authority

The active research forecast is the promoted Forecast-Lab V4 / `M26-PROBABILISTIC-FORECAST-2026-V1` lineage. It is separate from the immutable conventional `F-1 -> B2 -> F0` lineage. Never overwrite F-1, F0, B2 freezes, or any already-published forecast artifact.

The current baseline was earned historically:

- national point model: `PREVIOUS_NATIONAL_PERSISTENCE`;
- territorial model: `HALF_SHRINK`, `lambda = 0.5`;
- national uncertainty: calibrated prequentially;
- conditional geography uncertainty: calibrated separately;
- final forecast: 50,000 current-law elections, exactly 395 seats in every draw.

## Hard rule for new 2026 information

A fact is not automatically a forecast effect.

Every new candidate, list, poll, party switch, campaign event, official count or article must first be classified as one of:

- `MECHANICAL` — changes the electoral mechanics or known ballot state;
- `PREDICTIVE_CALIBRATED` — belongs to an information class whose incremental predictive value has passed a frozen historical admission test;
- `REPORTING_ONLY` — useful current intelligence that has not earned a numeric effect;
- `NONE/PENDING` — unverified, conflicted or inadmissible.

If an information class has not demonstrated out-of-sample incremental predictive value, it must not move the numeric forecast. Put it in the evidence/shadow layer instead.

## Snapshot discipline

- Never edit a frozen forecast in place.
- A verified mechanical update may justify a new immutable snapshot.
- A predictive update requires a frozen admission rule before it can affect a new forecast snapshot.
- `UNKNOWN` never silently becomes zero, false or absent.
- Failed and null results remain in history.
- Do not tune parameters because an output looks politically plausible.

## Before a material model change

Use `morocco26/docs/CHANGE_GATE_TEMPLATE.md` and state:

1. what question is being advanced;
2. what evidence class is involved;
3. the frozen comparison baseline;
4. the metric used to judge improvement;
5. what result would kill the change.

## Minimum validation before merging maintenance work

Run, when applicable:

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```

Forecast-changing work must additionally run its preregistered calibration/replay gates and the 50,000-election current-law simulation before promotion.

## Scope boundary

MOROCCO//26 is electoral intelligence and forecasting research. Do not add voter microtargeting, persuasive political messaging optimization, or personal voter targeting.
