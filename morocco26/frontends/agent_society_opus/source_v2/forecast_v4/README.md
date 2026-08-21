# Agent Society Forecast V4

V4 separates **society simulation** from **forecasting**:

```text
Atlas structural baseline
        +
historically calibrated Agent Society behavioural delta
        =
hybrid forecast
```

Agent Society is not a synthetic poll. Its rows are correlated model judgments attached to registered-electorate cells, not independent human respondents.

## Three regimes

- `NAMED_REALISTIC_2026`: real names as known at an immutable `as_of` vintage. Missing candidates remain `UNKNOWN`; they are never invented.
- `RICH_SEMI_BLIND_BACKTEST`: 2016 development + 2021 holdout, rich candidate/program substance but pseudonymized identity and sealed outcomes.
- `TOTAL_BLIND_CONTROL`: information-ablation control. The existing 32-agent `B01` report is retained only in this role; it contains 32 agents on one anonymized territory, not a national forecast.

## Key methodological changes

1. Do **not** wait for every candidate before running an interim vintage. Freeze dated vintages and rerun only affected contests when a nomination becomes known.
2. Every synthetic elector gets a deterministic `information_diet`; all ballot options remain present but detail and salience vary.
3. Model `LOCAL` and `REGIONAL` ballots separately and allow split tickets.
4. Target the **registered electorate**, not all adults.
5. Social exposures change perceptions first; they may not directly add vote probability.
6. Compute Agent Society as a log-ratio delta around Atlas. Lambda is zero until historical validation.
7. Fit lambda on 2016 only; freeze; score 2021 as untouched holdout; never retune after holdout and call it prospective.
8. Use correlated uncertainty. Seat allocation requires a separately recorded official-rule configuration.

## CLI

```bash
python3 morocco26/scripts/agent_society_forecast_v4.py --help
```

Typical first steps:

```bash
python3 morocco26/scripts/agent_society_forecast_v4.py inventory-main \
  --repo-root . --main-ref origin/main \
  --output /tmp/asv4-main-inventory.json

python3 morocco26/scripts/agent_society_forecast_v4.py adapt-candidates \
  --repo-root . --main-ref origin/main --as-of 2026-08-21 \
  --output /tmp/asv4-candidates.json
```

The next model operation is a **small named pilot**, not a national run. Production scale remains explicitly unauthorized in `AGENT_SOCIETY_FORECAST_V4_STATE.json`.
