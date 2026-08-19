# MOROCCO//26 — NORTH STAR

**Current operating north star — 19 August 2026**

The previous North Star dated 17 August 2026 is preserved at `docs/NORTH_STAR_ARCHIVE_2026-08-17.md` for audit history.

## Mission

Build and maintain the most credible territory-level probabilistic view of Morocco's 2026 legislative election, make every forecast auditable and falsifiable, and measure whether structured or agentic intelligence adds predictive information beyond the strongest frozen baseline.

MOROCCO//26 / Atlas 395 is an electoral-intelligence and forecasting system, not a poll, political-opinion engine, campaign persuasion system or LLM prediction machine.

## Four questions the system must continuously answer

1. **What do we know?**
2. **What is the source and verification state?**
3. **What does this information actually change: evidence, mechanics, prediction, or nothing?**
4. **How uncertain are we?**

## Current scientific baseline

The current promoted research baseline is Forecast-Lab V4 / `M26-PROBABILISTIC-FORECAST-2026-V1`.

It has already earned the following components historically:

- national point: `PREVIOUS_NATIONAL_PERSISTENCE`;
- territorial rule: `HALF_SHRINK`, `lambda = 0.5`;
- separate calibrated national uncertainty;
- separate calibrated conditional geography uncertainty;
- passing combined historical coverage;
- 50,000 current-law elections with exactly 395 seats in every draw.

This baseline is now the benchmark that every richer intelligence layer must beat.

## Product north star — Atlas 395

Before the election, Atlas 395 should provide:

- auditable forecasts for 92 local constituencies and 12 regional contests;
- party seat distributions and probability of finishing first;
- constituency-level seat/cutoff risk;
- sourced candidate/list/event intelligence;
- explicit uncertainty;
- an append-only change ledger distinguishing new evidence from model changes;
- immutable time-machine snapshots showing what the system knew and forecast at each date;
- a preregistered post-election scoring framework.

National projections are aggregations of coherent territorial simulations, not editorial seat guesses.

## Evidence graph north star

Maintain a sourced graph linking:

`PERSON -> PARTY -> CONSTITUENCY -> CANDIDACY -> LIST/RANK -> MANDATE/INCUMBENCY -> PARTY SWITCH -> EVENT -> SOURCE -> ELECTION RESULT`

Facts and model effects are separate objects.

A correct system response to new evidence can be:

**Evidence updated. Forecast unchanged.**

## Live 2026 rule

New candidate/list/poll/event information is classified as:

- `MECHANICAL`;
- `PREDICTIVE_CALIBRATED`;
- `REPORTING_ONLY/SHADOW`;
- `PENDING/EXCLUDED`.

Mechanical facts may alter a new snapshot when they change ballot/legal inputs. Predictive effects are admitted only after the same information class demonstrates incremental historical out-of-sample skill under a frozen rule. Current-only intuition never receives an arbitrary coefficient.

See `docs/LIVE_2026_UPDATE_RUNBOOK.md`.

## Scientific experiment

The original question remains active but is now cleaner because a strong baseline exists:

> Can candidate/current-information/agentic intelligence produce measurable predictive improvement beyond the promoted structural V4 baseline?

The next experiments should compare, separately where possible:

- candidate/list structured information;
- other historically comparable current-information classes;
- agentic collection / information acquisition;
- agentic residual reasoning;
- combinations only after their individual contribution is measurable.

A negative result is valid. The objective is to measure incremental predictive information, not prove that AI must help.

## Immutable historical lineages

The conventional `F-1 -> B2 -> F0` lineage is preserved exactly. B2 is a frozen negative result and F-1/F0 are immutable. Forecast-Lab V4 is a later separate research lineage; it does not rewrite those records.

Old Phase-2 AgentSociety artifacts remain historical experimental evidence, not current operating instructions.

## Hard anti-drift rules

1. Never overwrite a frozen forecast or failed result.
2. Never tune a model because its output looks politically plausible or implausible.
3. Evidence, mechanical consequence, predictive inference and product presentation remain separate layers.
4. `UNKNOWN` never silently becomes zero, false or absent.
5. A new predictive information class must earn admission historically before changing 2026 probabilities.
6. Agentic output receives no privileged status.
7. Every forecast-changing observation must be traceable to provenance and a versioned rule.
8. Product publication must not silently mutate science.
9. Every promoted simulated election allocates exactly 395 seats under the certified legal mechanics.
10. Post-election evaluation uses the snapshots actually frozen before election day, never reconstructed forecasts.

## Scope boundary

No voter microtargeting, persuasive political messaging optimization, personal voter targeting or campaign manipulation. Aggregate electoral intelligence and falsifiable forecasting only.

## Success before election day

Operational success means:

- a maintained promoted probabilistic baseline;
- auditable territorial forecasts;
- verified candidate/list/evidence graph;
- change ledger and immutable snapshots;
- clear uncertainty and provenance;
- a usable Atlas 395 publication layer;
- a frozen scoring protocol for the final election outcome.

Scientific success additionally means that the main candidate/current-information/agentic challengers have been tested against the frozen baseline, including publishing null results.

## One-sentence north star

**Maintain a falsifiable 395-seat territorial forecast, make every change explainable from evidence to model effect, and admit new intelligence only when it proves incremental predictive value.**
