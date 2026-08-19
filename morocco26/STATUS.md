# MOROCCO//26 — Status

**Current human authority:** `CURRENT_STATE.md`  
**Current machine authority:** `data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`  
**Handover guide:** `HANDOVER.md`  
**Live 2026 update policy:** `docs/LIVE_2026_UPDATE_RUNBOOK.md`

## Current state — 19 August 2026

The Forecast-Lab V4 2026 probabilistic baseline is **PROMOTED**.

- National point: `PREVIOUS_NATIONAL_PERSISTENCE`, selected by the frozen four-fold rolling-origin tournament over 2002→2007, 2007→2011, 2011→2016 and 2016→2021.
- Territorial centre: `HALF_SHRINK`, `lambda = 0.5`, selected on the historical territorial folds.
- National uncertainty: PASS.
- Conditional geography uncertainty: PASS.
- Combined national + geography coverage: PASS on 1,656 historical territory×party cells.
- Final simulation: 50,000 elections; 104 contests per draw; exactly 395 seats every draw; zero unresolved legal allocation failures.
- Joint seat-stream SHA256: `a10becb1e85c2b3327e9430cd76c7801e6d3f515046ab8ec991c787e016bdf0d`.
- Generated forecast JSON SHA256: `c7ab03321c0e3883048862a6d94faeb545066ea996a81a710691c6085f5726d6`.

The national point equals the 2021 national local-ballot composition **because persistence won historically**, not because 2021 persistence was assumed a priori.

## Current candidate / current-information policy

No current-only candidate, press, poll, defection, prediction-market or campaign signal is presently admitted as an uncalibrated numeric adjustment to the V4 point.

When new 2026 information arrives:

1. verify and store the fact with provenance;
2. classify it as mechanical, predictive-calibrated, reporting/shadow, or pending/excluded;
3. only mechanical changes or historically admitted predictive classes may alter a **new** forecast snapshot;
4. never overwrite V4, F-1 or F0.

A real and important fact can therefore produce the correct result: **evidence updated, forecast unchanged**.

## Lineage separation

### Conventional immutable lineage

- F-1: immutable registered structural forecast.
- B2: frozen negative structured-evidence result.
- F0: immutable registered preliminary forecast, exact zero-delta over F-1 under B2.

### Current research baseline

Forecast-Lab V4 / `M26-PROBABILISTIC-FORECAST-2026-V1` is a separate later research lineage and is currently the strongest promoted baseline.

### Agentic work

Agentic collection/reasoning is an incremental-value experiment. It must improve frozen out-of-sample scores relative to the current baseline; narrative quality is not an admission criterion.

### Atlas 395 product

`atlas395-v0` is a separate publication/product branch. Daily product ingestion may publish new evidence without silently changing frozen science.

## Mandatory cautions

- Historical transitions are sparse, so uncertainty tails are deliberately broad.
- Pooled combined coverage passes, but RNI-specific coverage is weaker and was not tuned away after observation.
- Conditional geography residuals are treated exchangeably across territories.
- The current regional-ballot bridge has no prior same-system historical transition for calibration.
- Local registered-voter counts remain latent until authoritative 2026 local counts arrive.
- Current list availability and unknown candidate ages remain structural placeholders where not yet authoritatively resolved.

## Next scientific objective

Run the **incremental intelligence tournament** against the promoted V4 baseline, beginning with historically reconstructable candidate/list information classes. Admit only layers that demonstrate incremental predictive value under frozen historical scoring. Keep null/negative results.

## Reproduction

```bash
python morocco26/scripts/simulate_final_forecast_2026_v1.py \
  --output /tmp/final_probabilistic_forecast_2026_v1.json
```

For complete handover instructions, start at `../AGENTS.md` then `HANDOVER.md`.
