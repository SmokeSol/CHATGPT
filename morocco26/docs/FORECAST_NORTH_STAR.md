# MOROCCO//26 — Forecast north star

## Objective
Build and freeze before the 2026 election the **best meaningful, calibrated and falsifiable territorial + seat forecast supported by the data**. Statistical, agentic, hybrid or rule-based methods are implementation choices, not scientific goals.

## Historical discipline
For every historical target election:
1. create an as-if pre-election snapshot;
2. generate and hash the forecast without opening that target's result;
3. only then open the target result in a separate scorer.

Current folds:
- 2011 → 2016
- 2016 → 2021
- 2007 → 2011 is blocked until 2007 is recovered.
- 2002 → 2007 becomes possible if 2002 is also recovered.

2016 and 2021 are development folds, not fresh confirmatory holdouts. The next truly prospective scoring event is 2026.

## Forecast hierarchy
1. fixed naïve skill floors;
2. conventional statistical challengers;
3. richer political/list/candidate challengers when justified;
4. ensembles if they improve proper forecast scores;
5. LLM/agentic components only if they improve the forecast.

## Primary forecast objects
- probability a party list wins at least one local seat;
- probability the list finishes inside the territory top-S;
- last-seat / cutoff margin;
- national and party seat-count distributions;
- calibration and proper scores.

Party-share and rank errors remain useful secondary diagnostics.

## Hard constraints
- No target-year result may enter its own forecast snapshot.
- No 2021 result is a fresh holdout anymore.
- No method gets privileged status because it is sophisticated or agentic.
- F0 remains immutable as a benchmark, not as an assumed optimum.
- Older elections should be used in rolling-origin order once recovered.
