# Elections26 — MOROCCO//26 / Atlas 395

This repository contains the Morocco 2026 electoral-intelligence, probabilistic-forecasting and Atlas 395 publication system. It is an analytical research project, not a campaign persuasion or voter-targeting system.

## Start here

**AI maintainers:** read [`AGENTS.md`](AGENTS.md) first.  
**Human maintainers:** read [`morocco26/HANDOVER.md`](morocco26/HANDOVER.md), then [`morocco26/CURRENT_STATE.md`](morocco26/CURRENT_STATE.md).

The machine-readable handover authority is:

`morocco26/data/goal100/handover_manifest_v1.json`

## Canonical branches

- `main` — canonical integration / handover branch after the handover cleanup is merged.
- `atlas395-v0` — separate product/publication branch used by the scheduled Atlas 395 daily workflow.
- older `morocco26-*` research branches — retained for provenance; do not assume a branch is current from its name.

## Current forecast authority

The currently promoted research baseline is Forecast-Lab V4:

`morocco26/data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

It is separate from the immutable conventional `F-1 -> B2 -> F0` lineage. See [`morocco26/docs/LINEAGE_MAP.md`](morocco26/docs/LINEAGE_MAP.md).

## New 2026 information

New candidates, lists, polls, party switches, official counts and campaign events do **not** automatically change forecast probabilities. Follow:

[`morocco26/docs/LIVE_2026_UPDATE_RUNBOOK.md`](morocco26/docs/LIVE_2026_UPDATE_RUNBOOK.md)

A verified fact may be mechanical, predictive-calibrated, reporting/shadow only, or pending/excluded. Predictive effects require historical out-of-sample admission; frozen forecasts are never overwritten.

## Health check

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```
