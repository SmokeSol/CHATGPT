# MOROCCO//26 — Forecast North Star

## Objective

Build, maintain and freeze before the 2026 election the **best calibrated, falsifiable territorial + seat forecast supported by the data**, while preserving a clean benchmark against which candidate/current-information/agentic intelligence must prove incremental value.

The goal is not to maximize model complexity. A simpler rule wins when it forecasts better out of sample.

## Current baseline

The current promoted research baseline is Forecast-Lab V4 / `M26-PROBABILISTIC-FORECAST-2026-V1`.

Its validated architecture is:

1. **National point:** `PREVIOUS_NATIONAL_PERSISTENCE`, winner of four rolling-origin national folds: 2002→2007, 2007→2011, 2011→2016, 2016→2021.
2. **Territorial geography:** `HALF_SHRINK`, `lambda = 0.5`, winner of the available territorial rolling-origin folds.
3. **National uncertainty:** calibrated chronologically from historical forecast errors.
4. **Conditional geography uncertainty:** calibrated separately, conditional on national party strength.
5. **Combined replay:** national + geography coverage passes on historical territory×party cells.
6. **Seat conversion:** 50,000 full current-law elections with exactly 395 seats every draw.

Machine authority:

`data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

## Historical discipline

For every historical target election used to test a new model or information class:

1. reconstruct only information that existed before the target election;
2. freeze the rule before opening/scoring against the target result;
3. score the challenger against a frozen baseline;
4. preserve null and negative results;
5. do not retune the same target until the desired answer appears.

Historical folds are development/validation evidence, not fresh future holdouts. The 2026 election is the decisive prospective test.

## Forecast hierarchy

A challenger earns admission only by improving prediction, not by sounding more sophisticated:

1. frozen structural baseline;
2. simple statistical challengers;
3. structured candidate/list/current-information challengers with historically comparable inputs;
4. ensembles only if they improve out-of-sample scores;
5. LLM/agentic components only if they add measurable residual predictive value.

## New 2026 information

A verified current fact can have four roles:

- **mechanical** — changes ballot/legal/N inputs in a new snapshot;
- **predictive-calibrated** — belongs to a class that passed an historical admission test;
- **reporting/shadow** — useful intelligence, no numeric effect yet;
- **pending/excluded** — unresolved or inadmissible.

The default for politically interesting but uncalibrated information is **forecast unchanged**.

See `LIVE_2026_UPDATE_RUNBOOK.md`.

## Primary forecast objects

- party/list probability of winning seats by territory;
- last-seat/cutoff risk;
- territorial vote-share uncertainty;
- national party seat-count distributions;
- probability of finishing first;
- tail outcomes and parliamentary configurations;
- calibration and post-election proper scoring.

## Hard constraints

- No target-year outcome enters its own pre-election forecast reconstruction.
- No frozen forecast is overwritten.
- No current-only signal receives an arbitrary weight.
- No method is privileged because it is agentic or narratively convincing.
- `UNKNOWN` does not become zero/false.
- Mechanical evidence and predictive evidence remain separate.
- Every promoted forecast must remain reproducible from frozen inputs, parameters and RNG state.

## Next scientific question

**Which historically reconstructable information classes, if any, improve the promoted V4 baseline?**

Candidate/list information is the natural next tournament, followed by agentic collection and residual reasoning. A negative result is scientifically valid and must be retained.
