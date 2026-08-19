# MOROCCO//26 Goal100 — State Authority Guide

Do **not** infer project authority from a filename such as `current_state.json`. This directory contains multiple frozen scientific lineages from different dates.

## Overall current authority

For the project as handed over on 19 August 2026:

1. human current state: `../../CURRENT_STATE.md`;
2. machine handover map: `handover_manifest_v1.json`;
3. current promoted forecast machine state: `forecast_lab/probabilistic_forecast_2026_state_v4.json`.

## Why `current_state.json` is not the overall current state

`current_state.json` is the preserved machine state of the **conventional Goal100 / F-1 -> B2 -> F0 lineage**, synchronized on 17 August 2026. It correctly describes that lineage and must not be rewritten merely because a later research lineage exists.

Likewise:

- `b2_current_state.json` describes the frozen B2/F0 experiment state;
- `forecast_registry.json` describes the conventional immutable forecast registry;
- F-1 and F0 snapshot directories remain historical registered artifacts.

These files are authoritative **for their own lineages**, not for the overall latest research forecast.

## Current research forecast

The strongest currently promoted research baseline lives under `forecast_lab/`:

`forecast_lab/probabilistic_forecast_2026_state_v4.json`

It is separate from, and does not overwrite, F-1/B2/F0.

## New 2026 evidence

New candidate/list/current-information evidence must follow:

`../../docs/LIVE_2026_UPDATE_RUNBOOK.md`

Do not edit an old state file to make it look current. Add a new version/snapshot/pointer while preserving the historical record.

## Default rule

When two files appear to disagree, first identify which lineage and timestamp each file belongs to. Then follow the authority order in `handover_manifest_v1.json` rather than choosing the file with the most generic name.
