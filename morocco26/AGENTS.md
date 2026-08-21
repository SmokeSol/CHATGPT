# MOROCCO//26 — local AI agent instructions

This file applies to everything under `morocco26/` and is more specific than the repository-root `AGENTS.md`.

## Forecast V4 is now the canonical forecasting architecture

Before changing Agent Society forecasting code, read in this order:

1. `frontends/agent_society_opus/source_v2/forecast_v4/AI_ENTRYPOINT.md`
2. `frontends/agent_society_opus/source_v2/forecast_v4/AGENT_SOCIETY_FORECAST_V4_PROTOCOL.json`
3. `data/goal100/agent_society_v2/AGENT_SOCIETY_FORECAST_V4_GOAL.json`
4. `data/goal100/agent_society_v2/AGENT_SOCIETY_FORECAST_V4_STATE.json`
5. `agent_society_v4/` and `tests/test_agent_society_forecast_v4*.py`

V4 does **not** rewrite or invalidate V5 historical artifacts. V5 Main Bridge, G0/D0/L0/CF files and historical output seals remain frozen controls/input artifacts. V4 defines how synthetic behavioural information is used for an actual 2026 forecast.

## Hard model distinction

```text
Agent Society raw level != forecast
Atlas structural baseline + historically calibrated Agent Society delta = forecast
```

Do not publish raw Sol aggregates as polling or forecast levels.

## Regimes

- `NAMED_REALISTIC_2026`: real names only as verified by a dated vintage. `UNKNOWN` is valid; never invent a candidate. `NO_LIST` requires evidence and is not a selectable ballot option.
- `RICH_SEMI_BLIND_BACKTEST`: rich historical evidence, pseudonymized identities, outcomes sealed during generation.
- `TOTAL_BLIND_CONTROL`: information-ablation control. The existing explanatory report covers 32 agents in batch B01 on one anonymized territory; do not reinterpret it as 32 work items or a national sample.

## Required forecast mechanics

- target the registered electorate, not all adults;
- model `LOCAL` and `REGIONAL` ballots separately;
- allow split-ticket behaviour;
- use deterministic profile-dependent information diets;
- social rounds modify perceptions, never probabilities directly;
- compute Agent Society as log-ratio/turnout deltas around Atlas;
- lambda is zero before historical validation;
- fit on 2016 only, freeze, then score untouched 2021 holdout;
- use correlated uncertainty;
- seat claims require an explicit certified Morocco-2026 rules configuration.

## Execution boundary

Architecture implementation is **not** authorization for a full Sol run. Read `AGENT_SOCIETY_FORECAST_V4_STATE.json` before execution. The first named operation is a small dated pilot and must preserve explicit source gaps rather than waiting for or inventing a complete roster.

Never open 2016/2021 outcomes opportunistically, never use floating `main` during a vintage, and never retune after holdout while describing the result as prospective.
