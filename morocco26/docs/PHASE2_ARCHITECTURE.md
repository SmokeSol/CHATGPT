# Phase-2 architecture and causal contract

```text
PUBLIC SOURCES / OFFICIAL RESULTS / MEDIAS24
                  │
                  ▼
      Electoral Intelligence Graph
  constituencies · parties · candidates · events
                  │
        ┌─────────┴──────────┐
        ▼                    ▼
 empirical anchors      assumption registry
 votes · turnout        demographics · networks
 denominators · seats   effect ranges · uncertainty
        │                    │
        └─────────┬──────────┘
                  ▼
       weighted synthetic electorate
                  │
      ┌───────────┼────────────┐
      ▼           ▼            ▼
      B           C0           C
 aggregate   agents/no net  agents/network
      │           │            │
      └───────────┼────────────┘
                  ▼
     deterministic electoral allocator
                  │
                  ▼
  turnout · vote shares · cutoff · seat risk
                  │
                  ▼
 gates · ledger · fingerprints · public lab
                  │
                  ▼
 D: bounded AgentSociety cognition delegates
```

## Causal contract

C and C0 use the same:

- synthetic agents and weights;
- latent baseline state;
- intervention intensity draw;
- direct-exposure draw;
- aggregate ballot-integration draw;
- electoral allocation function.

Only C activates network exposure and peer discussion. Therefore, under a null intervention, C and C0 must be exactly identical. Any failure invalidates the ablation.

## Epistemic layers

- **Observed:** published 2021 votes, registered-voter denominators for the four pilot constituencies, seats and winners.
- **Derived:** vote shares, turnout, quota, cutoff margin and calibrated intercepts.
- **Synthetic but calibrated:** age bands, milieu, latent trust/stress/interest, individual propensities.
- **Synthetic sensitivity parameters:** event reach, diffusion, transfer portability and peer influence.
- **Not executed:** LLM cognition output.

No synthetic layer may silently be relabeled as observed data.

## Reproducibility artifacts

- `data/experiment_manifest.json` — frozen protocol, arms, amendments and kill criteria.
- `reports/society_experiment.json` — complete compact result.
- `reports/society_runs.jsonl` — one row per model/run/constituency.
- `reports/synthetic_population_snapshot.json` — calibration and topology audit.
- `reports/agentsociety2_bundle/` — bounded delegate specifications and output contract.
- `web/lab.html` — public research cockpit.
- `web/lab-standalone.html` — self-contained file:// research cockpit.
