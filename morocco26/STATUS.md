# MOROCCO//26 — Current Status

Canonical live tracker: `reports/GOAL100_TRACKER.md`.

Machine-readable state:

- `data/goal100/current_state.json`
- `data/goal100/gate_registry.json`
- `data/goal100/forecast_registry.json`
- `data/goal100/b2_current_state.json`
- `data/goal100/b2_gate_registry.json`

Current scientific checkpoint: **F0 REGISTERED IMMUTABLE**.

B2 is frozen as a **negative deterministic result**: `B2_3_DATA_BLOCKED_NONAGENTIC`, `B2_4_FAIL`, provenance audit PASS on an empty admissible claim set, and all predictive coefficients exactly zero. No missing or unresolved evidence was converted to absence.

F0 is the first conventional preliminary forecast milestone. Because frozen B2 admits **0 mechanical constraints** and **0 predictive effect**, F0 is an exact identity counterfactual over the registered 50,000-election F-1 ensemble. F-1 remains immutable.

Reserved controlled test material for `E_collect`: **16 historical input classes + 92 unresolved Arabic PJD roster rows**.

Agentic experiment: **execution NOT STARTED**. `E-COLLECT-PREREGISTERED` is OPEN; `E_reason` and `E_full` remain LOCKED.

Next forecast ID: **F1**. Any update must be append-only; neither F-1 nor F0 may be overwritten.

## Forecast lab V3 — national / territory / uncertainty split

The research forecast path is now explicitly separated from the immutable F-1/F0 lineage. Canonical V3 research state: `data/goal100/forecast_lab/probabilistic_forecast_2026_state_v3.json`.

- Rolling-origin selection now includes **2007→2011, 2011→2016 and 2016→2021**. `HALF_SHRINK` wins the frozen {0, 0.5, 1} grid on equal-weight mean party-share RMSE, therefore **λ = 0.5** is the structural territorial skill-floor parameter.
- `structural_seat_forecast_2026_v2.json` remains useful as a **structural centre / stress-test reference** (approximately RNI 70, PAM 60, PI 50, MP 44, PJD 43, UC 39, USFP 36, PPS 34, OTHER 21), but its old uncertainty bands and first-party probabilities are **not promoted as calibrated 2026 probabilities**.
- The next prospective centre is no longer allowed to inherit the 2021 national composition silently. It must consume a separately frozen **current national 2026 party-strength forecast** satisfying `national_forecast_2026_contract_v1.json`.
- `scripts/forecast_v3_center.py` implements `national_2026 + 0.5 × (territory_2021 − national_2021)` and restores exact national aggregation by positive raking if a large national swing leaves the simplex. When national 2026 equals national 2021, this reduces exactly to the historically selected half-shrink centre.
- `scripts/calibrate_uncertainty_v3.py` rebuilds the **conditional territorial residual** library around this architecture instead of transplanting the old F-1 shock library. National uncertainty remains a separate hard gate.
- **`PROBABILISTIC FORECAST 2026 = NOT YET PROMOTED`** until national point strength, national uncertainty, territorial residual resampling/correlation, rolling-origin interval coverage and ≥50,000 exact-395-seat legal simulations all pass.

Current national evidence collection is recorded in `data/goal100/forecast_lab/national_2026_evidence_ledger_v1.json`. No arbitrary party percentages are permitted merely to unblock the pipeline.

CI authority: `.github/workflows/morocco26-b2-protocol.yml`, `.github/workflows/morocco26-goal100-tracking.yml`, and the research-only `.github/workflows/forecast-v3-calibration.yml` must pass for their respective scopes. Frozen Goal75 evidence and registered forecasts are never edited in place.
