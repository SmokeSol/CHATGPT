# MOROCCO//26 — Live 2026 Update Runbook

Use this runbook for every new piece of 2026 information after the promoted V4 baseline.

## Core principle

**Evidence can be true without being predictive.**

The system separates:

1. what happened / what is officially known;
2. whether that fact mechanically changes the ballot or legal input;
3. whether that class of fact has earned a calibrated predictive effect;
4. what the public/intelligence layer should report.

Never jump from step 1 directly to a hand-edited vote-share adjustment.

## Step 1 — Capture provenance first

For every new observation record:

- canonical subject/candidate/list/party;
- constituency or regional scope;
- event/claim type;
- event date and publication date;
- source publisher and locator;
- source tier;
- verification/corroboration state;
- extraction method;
- conflicts or unresolved identity/territory mappings.

The existing `data/goal100/b2_evidence_schema_v1.json` remains a useful provenance contract. B2 itself is frozen; using its schema does **not** reopen B2.

If identity or territory mapping is uncertain, keep it `UNRESOLVED`. Do not guess transliterations, aliases or absent values into existence.

## Step 2 — Classify the forecast role

Assign exactly one operational role:

### A. MECHANICAL

The information changes known election mechanics rather than estimated voter preference.

Typical examples:

- official list registered or rejected;
- candidate officially registered, withdrawn or disqualified;
- authoritative list rank;
- authoritative candidate birthdate/age when relevant to the statutory tie rule;
- official constituency/seat geometry change;
- official registered-voter counts;
- authoritative legal-rule change.

Action: create a proposal for a **new immutable snapshot**, update only the affected mechanical layer, rerun legal/invariant tests and, if the forecast distribution changes, rerun the full simulation. Never overwrite V4, F-1 or F0.

### B. PREDICTIVE_CALIBRATED

The observation belongs to an information class whose incremental predictive value has already passed a frozen historical admission test against the current baseline.

Action: apply only the frozen transformation/coefficient/rule; create a new snapshot; rerun calibration/coverage checks required by that protocol and the final simulation.

If the class has no passed admission artifact, it is **not** predictive-calibrated.

### C. REPORTING_ONLY / SHADOW

The fact may be politically important but has no validated numeric effect.

Typical examples until separately admitted:

- party switch/defection;
- incumbency or notability;
- campaign launch;
- endorsement;
- general press narrative;
- prediction market;
- one-off local political signal;
- uncalibrated poll;
- partial election result whose class has not passed a historical admission test.

Action: store, verify, map and expose it in intelligence/change surfaces. Do **not** move the numeric forecast. Optionally register a shadow counterfactual only if its rule is frozen before observing the future outcome.

### D. PENDING / EXCLUDED

Unverified, conflicted, post-cutoff for a frozen experiment, prohibited, unresolved or too weakly sourced.

Action: retain provenance and reason code; no forecast effect.

## Step 3 — Event-specific handling

### New candidate announced in press

1. record the claim;
2. seek official/independent confirmation;
3. map identity and constituency;
4. until official/corroborated, keep pending;
5. when verified, update candidate graph;
6. no vote effect unless the candidate-information class has passed historical admission.

### Official candidate/list registration

Treat list availability/rank as mechanical. Propose a new snapshot if this changes the simulated contest set or list structure. Do not infer popularity from registration alone.

### Candidate withdrawal/disqualification/death

If authoritative, treat the ballot consequence as mechanical. Any additional behavioural vote effect requires separate calibration.

### Candidate age/birthdate

If authoritative and relevant to a legal remainder tie, it may replace the exchangeable-age prior in a later snapshot for the affected contest. It is not a popularity signal by default.

### Party switch / defection

Record previous and current party, office/incumbency status and source. Default role: reporting/shadow. A numeric vote-transfer effect requires a historical admission experiment.

### Incumbent / former elected official / party office

Record as structured candidate features. Do not assign a coefficient until the corresponding feature class passes rolling-origin/holdout evaluation.

### Poll

Check sample frame, field dates, sponsor, mode, geography, question wording and whether it measures party vote intention. A poll may be high-quality information yet still remain reporting/shadow unless the same class can be historically calibrated. Never blend arbitrary poll weights into the national point.

### Partial/by-election/local election result

Store exact result and comparability metadata. It becomes predictive only if the same class of intermediate result has been reconstructed historically and improves out-of-sample forecasting under a frozen rule.

### News article / political analysis

Extract verifiable facts separately from commentary. Facts enter the graph; narrative assessment is reporting-only unless transformed by a validated information class.

### Official registered-voter counts

Mechanical input. A new authoritative 2026 local-N table supersedes the latent N assumption only in a **new snapshot**. Preserve old forecasts unchanged.

### Law / electoral geometry change

STOP ordinary updating. Re-certify geometry and legal allocator first. A law/geometry change is upstream of the entire forecast and cannot be patched as a local adjustment.

## Step 4 — Predictive admission test

Before any new information class can alter vote probabilities:

1. define the class before scoring it;
2. reconstruct the same class using only information available before historical target elections;
3. freeze the transformation from evidence to forecast adjustment;
4. compare `current baseline` versus `baseline + class` in rolling-origin order;
5. use predefined proper scoring / error metrics;
6. retain null and negative results;
7. test sensitivity to parties/territories where feasible;
8. admit only if improvement is sufficiently stable and not a one-fold artifact.

Current baseline to beat is the promoted V4 architecture, not an informal political judgement.

## Step 5 — Snapshot decision

### Evidence changed, forecast unchanged

This is normal. Update the intelligence/change ledger and state that no forecast-changing gate passed.

### Mechanical forecast change

Create a new immutable forecast snapshot with:

- new cutoff;
- exact new evidence IDs;
- previous snapshot parent;
- changed mechanical inputs;
- code/data/parameter hashes;
- RNG manifest;
- legal invariants;
- 50,000-draw output if the distribution changed.

### Predictive forecast change

Require all of the above plus the admission-test artifact and frozen predictive rule.

## Step 6 — Required validation

For ordinary evidence maintenance:

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```

For forecast-changing work, also run the specific admission/calibration/coverage workflow and the deterministic final 50,000-election workflow.

## Never do these

- hand-edit a party's forecast because an event feels important;
- overwrite an old forecast;
- treat absence of evidence as evidence of absence;
- turn an unresolved Arabic/French identity into a guessed match;
- use post-election information in an historical pre-election reconstruction;
- tune an effect after seeing that it improves the target being used for validation;
- reopen B2 merely because new 2026 candidates are arriving;
- let an LLM narrative directly mutate forecast probabilities.

## Default answer under uncertainty

When a new fact is real but its predictive effect is not validated, the correct system response is:

**Evidence updated. Forecast unchanged. Signal retained for shadow/admission testing.**
