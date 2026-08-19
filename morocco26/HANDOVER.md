# MOROCCO//26 — Operational Handover

**Audience:** the next human maintainer and the AI working with them.

This page is the shortest path from a cold start to safe maintenance.

## 1. What the project is

MOROCCO//26 / Atlas 395 is a territory-first probabilistic forecasting and electoral-intelligence system for Morocco's 2026 legislative election. Its scientific objective is to maintain a falsifiable structural baseline, then measure whether candidate/current-information/agentic layers add genuine predictive signal rather than plausible narrative noise.

## 2. What is current now

The current research authority is:

`data/goal100/forecast_lab/probabilistic_forecast_2026_state_v4.json`

The current forecast is **PROMOTED**. Its central architecture is:

1. national 2026 point selected by historical rolling-origin competition;
2. territorialization using the historically selected `lambda = 0.5` rule;
3. national and territorial uncertainty calibrated separately;
4. combined coverage tested historically;
5. 50,000 legally valid simulated elections, exactly 395 seats per draw.

See `CURRENT_STATE.md` for the concise live state and `STATUS.md` for a slightly longer explanation.

## 3. Branches and lineages

### Canonical integration branch

`main` is the canonical handover/integration branch after this cleanup is merged.

### Product publication branch

`atlas395-v0` is a separate product/publication branch. The scheduled Atlas workflow checks out that branch deliberately. Do not interpret it as the scientific authority.

### Historical research branches

Old `morocco26-*` branches are retained for provenance. Do not choose a branch by name and assume it is current; start from `main` and the handover manifest.

### Scientific lineages

There are three distinct concepts that must not be conflated:

- **Conventional immutable lineage:** `F-1 -> B2 -> F0`. B2 is a frozen negative result; F-1 and F0 are immutable.
- **Current Forecast-Lab lineage:** V4 / `M26-PROBABILISTIC-FORECAST-2026-V1`, currently the strongest promoted research baseline.
- **Agentic incremental-value experiments:** separate tests asking whether collection/reasoning adds value beyond a frozen baseline. Agent output never earns forecast authority through narrative plausibility.

See `docs/LINEAGE_MAP.md`.

## 4. The single most important rule

**New information is not the same thing as predictive information.**

When a candidate, list, party switch, poll or political event appears, first store and verify the fact. Then decide its role:

- mechanical;
- predictive-calibrated;
- reporting/shadow only;
- pending/excluded.

Only a historically admitted predictive class may alter the numeric forecast as a predictive effect. Mechanical facts may alter a new snapshot when they change the ballot/legal input itself.

Follow `docs/LIVE_2026_UPDATE_RUNBOOK.md` exactly.

## 5. What is frozen and must never be rewritten

- registered F-1 artifacts;
- registered F0 artifacts;
- B2 freeze and negative-result artifacts;
- historical source snapshots and failed runs used for audit;
- already-promoted forecast artifacts and their hashes;
- preregistered scoring rules after they have consumed their target data.

A correction creates a new version/snapshot and a provenance link; it never silently rewrites the past.

## 6. Reproduce the current forecast

The canonical final runner is:

```bash
python morocco26/scripts/simulate_final_forecast_2026_v1.py \
  --output /tmp/final_probabilistic_forecast_2026_v1.json
```

Expected deterministic identifiers are recorded in `CURRENT_STATE.md` and the machine state V4. The 50,000-draw joint seat-stream SHA256 is:

`a10becb1e85c2b3327e9430cd76c7801e6d3f515046ab8ec991c787e016bdf0d`

Do not change seeds or frozen parameters and then describe the result as the same forecast.

## 7. Daily maintenance workflow

When new 2026 information arrives:

1. identify the source and timestamp;
2. map it to candidate/list/party/territory identifiers without guessing;
3. store it append-only with provenance;
4. verify/corroborate according to evidence rules;
5. classify its forecast role;
6. if reporting-only, update intelligence surfaces but do not change probabilities;
7. if mechanical, create a new snapshot proposal and rerun the affected legal/50k gates;
8. if proposed predictive, first run a frozen historical admission experiment against the current baseline;
9. update `CURRENT_STATE.md` only after the relevant gate passes;
10. merge through CI with handover, anti-drift and Goal100 validators green.

## 8. What to do when many candidates arrive

Candidate ingestion is primarily an **evidence-graph operation**, not a licence to hand-edit vote shares.

Record at minimum where available:

- canonical candidate identity;
- party/list;
- constituency/region;
- registration status;
- list rank;
- incumbent/elected-office status;
- party switch history;
- birthdate/age when authoritative and legally relevant;
- source, timestamp, verification status.

List registration, withdrawal, disqualification, rank and verified age can be mechanical inputs. Incumbency, notoriety, defection or party switch are not assigned vote effects unless their information class has passed an historical admission test.

## 9. What the next maintainer should work on

The next high-value research task is not to add political intuition manually. It is to build the **incremental intelligence tournament** against the promoted baseline:

- candidate/list information classes;
- other historically comparable structured information classes;
- agentic collection;
- agentic residual reasoning;
- combinations only after individual effects are measurable.

The winner must improve frozen out-of-sample scoring. A null result is a valid result.

## 10. Fast health check

Run:

```bash
python morocco26/scripts/validate_handover.py
python morocco26/scripts/validate_anti_drift.py
python morocco26/scripts/validate_goal100_tracking.py
```

If the handover validator fails, do not ask the AI to infer which document is authoritative. Fix the documentation/state inconsistency first.
