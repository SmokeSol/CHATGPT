# MOROCCO//26 — Lineage Map

This file exists to prevent a maintainer or AI from mixing artifacts that answer different questions.

## 1. Conventional immutable forecast lineage

```text
F-1
  ↓
B2 structured-evidence experiment
  ↓
F0
```

- `F-1`: registered immutable structural probabilistic forecast.
- `B2`: frozen deterministic structured-evidence experiment. Result: negative / insufficient admissible predictive evidence under its frozen protocol.
- `F0`: registered immutable preliminary forecast. Under frozen B2, its predictive/mechanical delta versus F-1 is exactly zero.

**Rule:** never overwrite or reopen these artifacts to accommodate later information.

## 2. Forecast-Lab V4 — current promoted research baseline

This later research lineage separates the problem into:

```text
historically selected national point
        +
historically selected territorial geography (lambda=.5)
        +
separate national uncertainty
        +
conditional territorial uncertainty
        ↓
combined historical coverage gate
        ↓
50,000 current-law elections
        ↓
PROMOTED V4 baseline
```

Machine authority:

`data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

This is currently the strongest promoted research forecast and the baseline that new predictive intelligence must beat.

## 3. Live 2026 evidence lineage

New 2026 evidence is append-only and begins as evidence, not as a forecast adjustment.

```text
source
  ↓
verified fact / unresolved claim
  ↓
identity + territory mapping
  ↓
role classification
  ├─ mechanical → new snapshot candidate
  ├─ predictive-calibrated → new snapshot candidate
  ├─ reporting/shadow → forecast unchanged
  └─ pending/excluded → forecast unchanged
```

The B2 evidence schema may be reused as a provenance schema; the frozen B2 experiment itself is not reopened.

## 4. Incremental intelligence / agentic experiments

Purpose: determine whether information acquisition or reasoning adds predictive value beyond a frozen baseline.

Examples:

- candidate-feature admission tests;
- structured current-information admission tests;
- `E_collect` style acquisition tests;
- `E_reason` residual-reasoning tests;
- combined agentic tests.

The output of an AI is not evidence of predictive skill. Only frozen out-of-sample improvement earns admission.

## 5. Atlas 395 product lineage

`atlas395-v0` is the publication/product branch used by the scheduled daily workflow.

It may ingest and publish evidence/intelligence, but product presentation does not alter frozen science. A product edition can say that new evidence exists while the numerical forecast remains unchanged.

## 6. Which lineage should a maintainer touch?

| Task | Correct lineage |
|---|---|
| Fix docs / handover / tests | `main` |
| Add a verified 2026 candidate fact | live evidence/intelligence layer on `main`, then publication sync as designed |
| Update official list availability | new mechanical snapshot proposal; never modify F-1/F0/V4 in place |
| Test whether party switches predict vote shifts | incremental historical admission experiment |
| Change forecast because of a press narrative | **not allowed** without admission |
| Publish daily intelligence | `atlas395-v0` product workflow |
| Study old B2 failure | historical B2 lineage, read-only unless fixing provenance/maintenance without rewriting the result |

## 7. Authority order

When documents disagree, use this order:

1. `CURRENT_STATE.md` + the referenced machine state;
2. `data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`;
3. immutable snapshot manifests/certificates for the lineage being inspected;
4. `STATUS.md`;
5. historical trackers/runbooks only for audit context.
