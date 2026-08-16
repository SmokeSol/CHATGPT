# MOROCCO//26 — Anti-drift operating contract

## North star

MOROCCO//26 exists to **decode the 2026 Moroccan parliamentary election using an empirically anchored artificial electoral society, then test whether agent dynamics add stable out-of-sample value beyond structural baselines**.

The Electoral Intelligence Graph is infrastructure and empirical ground truth. The dashboard is presentation. A forecast is a possible output only after validation. None of those are the north star by themselves.

## Priority order

1. **70% — Political understanding of Morocco 2026.** Identify mechanisms that change turnout, party choice, territorial cutoffs, seat risk or coalition structure, and distinguish signal from political noise.
2. **30% — Artificial-society experiment.** Determine whether calibrated synthetic agents / AgentSociety add falsifiable explanatory or predictive value beyond structural/statistical models.

## Mandatory contribution test for every material task

Before work begins, record:

1. Which north-star question does this answer?
2. Which phase exit gate does it advance?
3. What falsifiable claim becomes testable?
4. What evidence class is being added?
   - OBSERVED
   - DERIVED
   - SYNTHETIC_CALIBRATED
   - SYNTHETIC_SENSITIVITY
   - LLM_DERIVED
5. What result would kill/reverse the proposed mechanism?
6. Why is this work more valuable than directly improving the Morocco-2026 evidence graph?

If items 1–5 cannot be answered, the task is **DRIFT / DEFER**.

## Hard anti-drift rules

### AD-01 — Infrastructure is never a scientific milestone
GitHub, Vercel, UI, dashboards, deployment, refactors and monitoring count as progress only when they unblock a named scientific/political gate. UI polish cannot move the formal project-completion percentage.

### AD-02 — No forecast-by-default
National or constituency forecasts remain `BLOCKED` until the constitution's forecast unlock gate passes. A simulation result must not be relabeled a forecast.

### AD-03 — No synthetic-to-observed laundering
Synthetic demographics, diffusion, trust, portability, peer influence or LLM outputs must retain their epistemic labels. They cannot silently become facts about Moroccan voters.

### AD-04 — AgentSociety has to earn its existence
Model D is retained only if it is replayable, stable and improves frozen out-of-sample performance versus both B and C. Better prose, plausible narratives or larger agent counts are not evidence.

### AD-05 — Seat impact requires a chain
A political event is not called electorally material unless the analysis can trace:
`observed event -> mechanism -> affected geography -> behavior/turnout/vote effect -> local cutoff/seat or coalition consequence`.
If the chain breaks, classify the result as salience/reach only.

### AD-06 — No tuning toward drama
Parameters may not be tuned because a result looks politically uninteresting. Null and non-material findings are retained. Changes require an amendment with timing, reason and anti-p-hacking note.

### AD-07 — Prospective beats retrospective
Once a 2026 claim is frozen, later evidence may score or falsify it, not rewrite the original prediction/mechanism. Retrospective explanation must be stored separately from prospective output.

### AD-08 — Keep structural baselines alive
Every agent result must remain comparable to A/B/C0/C. The project must never become an LLM-only society simulation.

### AD-09 — Scope boundary
No voter microtargeting, persuasive political messaging, party campaign optimization or personal voter data. Aggregate mechanism analysis only.

## Weekly / milestone drift audit

Score each item 0 or 1:

- The last material work advanced a canonical value-chain step.
- At least one falsifiable claim became easier to test.
- Empirical coverage or out-of-sample validity improved.
- Synthetic assumptions did not gain epistemic status without evidence.
- The agent layer was compared against a non-agent baseline.
- Forecast gates were respected.
- At least 70% of research effort still serves political understanding of Morocco 2026.
- A kill criterion remains active for the current experimental layer.

**8/8:** ON MISSION  
**6–7/8:** WATCH  
**<=5/8:** DRIFT — stop new feature work and return to the evidence/gate backlog.

## Current interpretation

The Phase-2 A/B/C0/C pilot is aligned with the original prompt because it tests the causal value of a social-agent layer on top of real territorial anchors. Its strongest current finding is negative but useful: network diffusion can increase reach without producing a material electoral effect under current priors.

The next useful step is **not a larger simulation for its own sake**. It is a paired advance:

1. complete enough of the territorial graph/replay to create a genuine frozen holdout;
2. run the bounded AgentSociety Model D once against that frozen benchmark and kill it if it fails.
