# HISTORICAL ARCHIVE — AgentSociety 2 bounded-execution runbook

> **Not current operating authority.** This runbook documents an earlier Phase-2 experiment and is preserved for reproducibility/audit. New maintainers must start from `../CURRENT_STATE.md`, `../HANDOVER.md` and `LIVE_2026_UPDATE_RUNBOOK.md`. Do not restart this protocol or use it to mutate the current V4 forecast unless a new experiment is explicitly preregistered.

## Purpose

Test whether LLM cognition adds stable, externally useful state updates beyond the executed structural and network models. This is not a voter-persuasion system.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[agents]'
```

The optional dependency is frozen to `agentsociety2==2.8.4` for this release; changing it requires a new protocol/version fingerprint.

Configure an approved provider through an environment variable supported by the runtime. Never commit credentials.

## Build the frozen bundle

```bash
make society
```

The canonical bundle is created under `reports/agentsociety2_bundle/` and contains aggregate delegate specs, event batch, strict output schema and system boundary.

## Smoke test

```bash
make agentsociety2-smoke
```

A successful smoke only validates runtime/API/replay integration. It does not validate political usefulness.

## Evidentiary D run requirements

Before a scored D run, freeze:

- AgentSociety package version;
- model/provider identifiers;
- system prompt and event serialization;
- delegate-clustering algorithm;
- random seeds and sampling settings;
- primary score and holdout;
- allowed failure/retry policy.

Run at least two model families and three semantically equivalent prompt variants. Record raw structured outputs and replay artifacts. Do not average away schema violations.

## Kill criteria

Kill or redesign D when any of the following occurs:

- more than 1% invalid or out-of-bounds records after one permitted retry;
- material output drift under irrelevant wording changes;
- directionally inconsistent dose response;
- instability across model families larger than the claimed incremental effect;
- no improvement over B/C on the frozen holdout;
- output requires subjective narrative coding to appear useful.
