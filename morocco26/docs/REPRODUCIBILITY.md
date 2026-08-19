# MOROCCO//26 — Reproducibility Record

## Current promoted forecast

**Forecast:** `M26-PROBABILISTIC-FORECAST-2026-V1`  
**State:** Forecast-Lab V4, `PROMOTED`  
**Machine authority:** `../data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

The current forecast is deterministic conditional on the frozen inputs, parameters and RNG seeds.

## Canonical reproduction

```bash
python morocco26/scripts/simulate_final_forecast_2026_v1.py \
  --output /tmp/final_probabilistic_forecast_2026_v1.json
```

Expected identifiers:

- draws: `50000`;
- seats in every draw: `395`;
- generated JSON SHA256: `c7ab03321c0e3883048862a6d94faeb545066ea996a81a710691c6085f5726d6`;
- joint 50,000-draw seat-stream SHA256: `a10becb1e85c2b3327e9430cd76c7801e6d3f515046ab8ec991c787e016bdf0d`;
- canonical successful CI run: `32289928633`;
- canonical artifact: `9379123421`.

A second clean-head 50,000-draw CI run reproduced the same joint seat-stream hash before handover.

## Model-selection reproducibility

The active point model is not an informal assumption:

- national winner: `PREVIOUS_NATIONAL_PERSISTENCE` over four rolling-origin folds;
- territorial winner: `HALF_SHRINK`, `lambda = 0.5` over the historical territorial folds;
- national uncertainty and conditional geography uncertainty are calibrated separately;
- the combined historical coverage gate passes before the final simulation is promoted.

See `../CURRENT_STATE.md` for concise metrics and the V4 machine state for exact values.

## Legal reproducibility

The final simulation reuses the certified F-1 V1.1 legal/runtime mechanics for registered-N/turnout/list availability/integer votes/statutory ties, but it does **not** reuse the old F-1 vote-uncertainty generator around the new V4 centre.

Every promoted draw must:

- include 92 local and 12 regional contests;
- allocate exactly 395 seats;
- have zero unique-list threshold failures;
- have zero unfilled-seat exceptions;
- have zero unresolved statutory ties after the frozen exchangeable-age prior where ages are unknown.

## Handover validation

Before accepting documentation/state maintenance:

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```

Forecast-changing work additionally requires the relevant frozen historical admission/calibration/coverage workflows and a new immutable simulation artifact.

## Historical Phase-2 experiments

Earlier AgentSociety/Phase-2 reproducibility artifacts remain preserved as historical research records. They are not the current forecast authority. See `PHASE2_ARCHITECTURE.md` and `AGENTSOCIETY2_RUNBOOK.md`, both explicitly marked historical archives.

## Public boundary

This repository studies aggregate electoral mechanisms and forecasting. It does not generate campaign persuasion, optimize political messages, target voter groups or ingest personal voter data.
