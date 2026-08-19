# MOROCCO//26 — Change Gate

Use this record for every material scientific/model change. Maintenance-only documentation, UI or deployment fixes must be labelled `MAINTENANCE_ONLY` and cannot claim predictive progress.

## 1. What is changing?

- **Question advanced:**
- **Affected lineage:** `CURRENT_V4 | NEW_SNAPSHOT | AGENTIC_EXPERIMENT | ATLAS_PRODUCT | HISTORICAL_MAINTENANCE`
- **Current frozen baseline:**
- **Why the change is necessary:**

## 2. Evidence role

Choose exactly the operational role that applies:

- [ ] `MECHANICAL`
- [ ] `PREDICTIVE_CALIBRATED`
- [ ] `REPORTING_ONLY / SHADOW`
- [ ] `PENDING / EXCLUDED`
- [ ] `MAINTENANCE_ONLY`

Also label the epistemic layer where relevant:

- [ ] OBSERVED
- [ ] DERIVED
- [ ] SYNTHETIC_CALIBRATED
- [ ] SYNTHETIC_SENSITIVITY
- [ ] LLM_DERIVED

**Evidence/source artifact:**

## 3. Falsifiability / admission

For a predictive change, all fields are mandatory:

- **Information class being tested:**
- **Historical pre-target reconstruction:**
- **Frozen transformation/rule:**
- **Frozen comparison baseline:** promoted V4 unless the protocol explicitly specifies an earlier immutable baseline.
- **Primary predefined metric:**
- **Result that rejects/kills admission:**
- **Targets/folds not yet opened when the rule was frozen:**

If no historical admission test exists, the role cannot be `PREDICTIVE_CALIBRATED`.

## 4. Snapshot effect

- [ ] No forecast change; evidence/reporting only.
- [ ] New mechanical snapshot required.
- [ ] New predictive snapshot required after admission PASS.
- [ ] Existing frozen forecast remains untouched.

**Parent snapshot / baseline:**

**New cutoff if applicable:**

## 5. Anti-drift checks

- [ ] No frozen artifact is overwritten.
- [ ] `UNKNOWN` is not converted to zero/false/absent.
- [ ] No effect is tuned because it looks politically plausible.
- [ ] Null/negative historical results will be retained.
- [ ] Agent/LLM output is compared against a non-agent baseline.
- [ ] Product presentation is not being counted as scientific evidence.
- [ ] Provenance and identity/territory mapping are explicit.
- [ ] Legal 395-seat invariants remain required for any promoted simulation.
- [ ] No voter microtargeting or persuasion optimization is introduced.

## 6. Validation required before merge

Minimum maintenance checks:

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```

List any additional admission/calibration/coverage/50k workflows required:

## Decision

`ON_MISSION | WATCH | REJECT | MAINTENANCE_ONLY`

A forecast-changing change may be promoted only after every required frozen gate passes.
