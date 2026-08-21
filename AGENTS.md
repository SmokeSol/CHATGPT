# MOROCCO//26 — AI Agent Entry Point

> **Read this file first if you are an AI agent, coding agent, research agent, or new maintainer receiving this repository without prior conversational context.**
>
> Your job is to preserve the scientific experiment, make progress autonomously, and never trade experimental validity for convenience.

## 0. One-sentence mission

MOROCCO//26 is building a **pre-election, falsifiable territorial forecasting system for Morocco 2026** and testing whether an agentic synthetic-society layer adds measurable predictive information beyond a strong structural baseline.

This repository is an **analytical / simulation research system**, not a campaign-persuasion system.

---

# 1. First actions for any new agent

Before changing code, running a model, opening an outcome, deploying, or interpreting a number:

```bash
git status --short
git branch --show-current
git log -5 --oneline
```

Then read, in this order:

1. `AGENTS.md` — this file: project map, invariants, safe operating procedure.
2. `morocco26/data/goal100/agent_society_v2/current_state.json` — authoritative state of the public AS2 collection / social / security workstream.
3. `morocco26/data/goal100/agent_society_v2/CHATGPT_ACCOUNT_G0_STATE_V1.json` — authoritative state of the owner-generated GPT-5.6 Sol G0/L0/CF workstream.
4. `morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/FREEZE_MANIFEST.json` — frozen G0 generation / promotion constraints.
5. `morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V1.json` — G0 generation protocol.
6. `morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/DELIBERATION_OBSERVATORY_PROTOCOL_V1.json` — L0 explanatory-observatory protocol.
7. The code you intend to modify plus its tests.

Do **not** assume this document's snapshot is newer than those machine-readable state files. This file explains the architecture; the state JSON files tell you what has actually happened.

---

# 2. Current branch and repository topology

The active Agent Society implementation is on:

```text
morocco26-agent-society-v2-front-vote-llm
```

Do not silently move experimental work to `main` or another branch. If you find yourself elsewhere, inspect history and switch only when the task clearly requires it.

Key directories:

```text
morocco26/
├── data/goal100/agent_society_v2/          # experiment states, frozen protocols, audit artifacts
├── scripts/                                # builders, historical handoffs, population pipelines, audits
└── frontends/agent_society_opus/source_v2/
    ├── scripts/                            # deterministic E0/reference derivation helpers
    ├── chatgpt_baseline/                   # owner ChatGPT/Codex Sol G0 + deliberation observatory
    └── web/                                # GitHub Pages public frontend
```

Deployment workflow:

```text
.github/workflows/deploy-agent-society-pages.yml
```

Published directory:

```text
morocco26/frontends/agent_society_opus/source_v2/web
```

Production channel for this experiment is **GitHub Pages**. Do not treat a Vercel check as proof of the production deployment.

---

# 3. Scientific question

The core question is not "can an LLM produce plausible-looking votes?" It is:

> Can the Electoral Intelligence Graph + territorial decoder produce, **before an election**, falsifiable territorial / seat probabilities, and does an agentic layer provide measurable out-of-sample predictive information beyond the best structural baseline?

The project must therefore preserve:

- pre-registration;
- blindness to target outcomes during generation;
- immutable model/prompt/schema once a run has begun;
- explicit controls;
- out-of-sample evaluation;
- reproducible artifacts and hashes;
- a clean distinction between observed inputs, simulated outputs, explanations, and actual election results.

A visually compelling frontend is useful, but **scientific status always dominates presentation**.

---

# 4. The experiment ontology — do not blur these objects

## E0 — deterministic control

`E0_DETERMINISTIC` is the existing 94,208-row deterministic reference.

Role:

```text
mechanics / reproducibility / explicit-rule control
```

It is **not** a real LLM population and must never be relabeled as one.

Current registered role:

```text
DETERMINISTIC_REFERENCE_AND_MECHANICS_ONLY
```

E0 must remain available after G0 exists, because `G0 - E0` is scientifically informative.

## G0 / D0 — owner-generated GPT baseline

Candidate primary synthetic society generated with:

```text
model: gpt-5.6-sol
reasoning effort: medium
auth: owner's normal ChatGPT account via Codex CLI
API key: forbidden
fresh model context per work item: required
```

Canonical launcher:

```text
morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol.py
```

`run_g0_sol.py` exists specifically to freeze model + effort; prefer it over manually passing `--model` to the generic runner.

## L0 — observable deliberation

L0 is a **separate, post-decision explanatory pass** over frozen D0 decisions.

It is intentionally **not private chain-of-thought**. It is a structured, auditable explanation tied to a closed evidence catalogue.

It can describe:

- top choice and runner-up;
- central political conflict;
- directional drivers;
- why the top choice remains ahead;
- why the runner-up remains plausible;
- turnout / abstention posture;
- confidence;
- minimum flip hypothesis;
- evidence IDs supporting every asserted driver.

It cannot rewrite the D0 vote.

Canonical runner:

```text
morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_deliberation_observatory.py
```

## CF — synthetic counterfactual diagnostics

CF re-runs selected agents under pre-registered packet perturbations in fresh contexts.

Current scenario library includes:

```text
PRIOR_ANCHOR_ALTERNATIVE
GOVERNMENT_OUTLOOK_REVERSE
RUNNER_LOCAL_STRENGTH
TOP_RUNNER_PROGRAM_SWAP
NONINFORMATIVE_METADATA_PLACEBO
```

CF is a **causal diagnostic inside the synthetic model**, not a causal estimate about real Moroccan voters.

The placebo is mandatory for interpreting sensitivity.

## AS2 public / R0

Independent reader-contributed LLM decisions. Users bring their own ChatGPT/Claude/etc. The public collection has its own anti-abuse and blinding machinery.

This is an independent replication / diversity cohort. It is not interchangeable with G0.

## AS3 / social R1-R2

The social extension applies synthetic exposures through:

```text
family
work
neighborhood
```

with isolated R0 then synchronous R1/R2.

Current public social lambdas are **illustrative only**, not calibrated evidence.

---

# 5. Frozen full environment

Canonical public environment identifiers:

```text
experiment: EXP_7C8A2F11
environment: ENV_4D19B3E7
```

Expected scale:

```text
2,944 work items
32 archetypes per work item
94,208 output rows
92 territories
2 elections
2 conditions
8 batches in the full rich environment
```

The judge environment is designed to exclude:

- target outcomes;
- real election-year labels;
- real territory identities;
- real party names;
- private mapping material;
- source URLs that could make re-identification trivial.

Do not "help" the model identify the blinded election, constituency, party, candidate, or result.

---

# 6. Absolute scientific invariants

These are hard stop rules.

## 6.1 Never open outcomes opportunistically

At the current pre-run/pre-calibration phase:

```text
2016 outcomes: SEALED
2021 outcomes: SEALED
```

Do **not** inspect either merely to debug a model, select prompts, choose features, compare variants, or make the frontend more convincing.

The intended scientific sequence is conceptually:

```text
blind model generation
        ↓
allowed 2016 development/calibration unseal at the registered gate
        ↓
calibrate/freeze parameters on 2016 only
        ↓
freeze the resulting specification
        ↓
2021 holdout unseal
        ↓
out-of-sample scoring
```

If the current state/protocol specifies an even stricter gate, follow the stricter gate.

## 6.2 Do not tune after seeing outcomes

No prompt, feature, model, graph rule, lambda, aggregation choice, exclusion rule, or post-processing choice may be selected based on unseen target outcomes and then presented as pre-registered.

If an amendment becomes necessary after any outcome exposure, version it explicitly and treat it as post-outcome exploratory work.

## 6.3 Keep E0, G0, L0, CF, public AS2, and social AS3 distinct

Never call:

- E0 "LLM behavior";
- L0 "chain of thought";
- CF "real-world causal evidence";
- illustrative social lambdas "calibrated";
- historical actual results "simulation";
- a simulation "prediction" before the required scoring / prospective freeze.

## 6.4 Never leak mapping/outcomes into a model context

Frozen G0/D0, L0, and CF contexts must not gain:

- web search;
- repository browsing;
- MCP access;
- shell access;
- memory;
- previous work-item conversation state;
- real identities;
- target outcomes.

The orchestration code can of course access local files necessary to construct the allowed blinded input; the **model context** must remain bounded by the frozen contract.

## 6.5 Fresh context means fresh context

Never resume a Codex thread from a previous work item. Every D0 work item, L0 explanatory batch, and CF re-run must be isolated as specified by its protocol.

## 6.6 No political-output-based abuse filtering

The public AS2 anti-abuse system must not quarantine a contribution because its political probabilities, turnout level, factor pattern, or substantive political direction look unusual.

Abuse controls may use protocol integrity, exact replay/fingerprint signals, speed metadata, rate limits, and similar non-directional evidence — not political agreement with an expected answer.

---

# 7. Current parallel workstreams

A new agent must understand that there are **two legitimate parallel paths**.

## Workstream A — public BYO-LLM AS2 collection

Read first:

```text
morocco26/data/goal100/agent_society_v2/current_state.json
morocco26/data/goal100/agent_society_v2/AS2_PUBLIC_ABUSE_CONTROL_PROTOCOL_V1.json
```

At the latest registered state before this handoff, the public backend was protected and ready, with native proof-of-work, tickets, rate limits, strict 32-row validation, and collective directional results hidden during collection.

Backend components recorded in state include:

```text
agent-society-participation
agent-society-mcp
agent-society-social
asv2-payload-ingest   # retired / always 410
```

Do not weaken security after collection begins without a versioned protocol amendment.

## Workstream B — owner ChatGPT-account Sol baseline G0/L0/CF

Read first:

```text
morocco26/data/goal100/agent_society_v2/CHATGPT_ACCOUNT_G0_STATE_V1.json
morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/FREEZE_MANIFEST.json
```

At the latest registered state before this handoff:

```text
G0 real outputs: not yet generated
G0 model: gpt-5.6-sol
G0 effort: medium
L0: pre-registered, no outputs
CF: pre-registered diagnostics
```

Always re-read the state file before acting; this snapshot may have advanced.

---

# 8. Owner-account G0 execution contract

The G0 route deliberately uses the owner's **normal ChatGPT login through the official Codex CLI**, not an OpenAI API key.

Never request, copy, print, upload, or commit:

```text
~/.codex/auth.json
```

Treat it like a password.

The child execution contract removes API-key variables and requires ChatGPT-managed login.

Expected environment characteristics:

```text
codex exec --ephemeral
fresh context
read-only sandbox
web disabled
apps disabled
MCP disabled
shell tools disabled
memories disabled
no cross-batch history
structured output
```

A quota/rate-limit pause is not a scientific failure. Rerun the identical command; validated work items should be skipped.

---

# 9. Safe startup experiment: exactly 32 work items

Before scaling to all 2,944 work items, the intended startup diagnostic is:

```text
32 work items × 32 archetypes = 1,024 D0 decisions
```

Then a separate L0 pass explains those same 1,024 frozen decisions.

Use a dedicated local output directory outside git, for example:

```bash
BUNDLE="$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip"
D0="$HOME/agent-society-runs/G0_SOL_STARTUP_32"
L0="$HOME/agent-society-runs/G0_SOL_STARTUP_32_OBSERVATORY"
BASE="morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline"
```

## 9.1 Preflight — zero model work

```bash
python3 "$BASE/run_g0_sol.py" \
  --bundle "$BUNDLE" \
  --output "$D0" \
  --limit 32 \
  --dry-run
```

Confirm discovery of the canonical full environment before a real run.

## 9.2 Generate 32 D0 work items

```bash
python3 "$BASE/run_g0_sol.py" \
  --bundle "$BUNDLE" \
  --output "$D0" \
  --workers 1 \
  --limit 32
```

Expected partial state after success:

```text
work_items_validated = 32
rows_validated = 1024
model = gpt-5.6-sol
auth_mode = CHATGPT_MANAGED_CODEX_LOGIN
api_key_used = false
status = IN_PROGRESS_RESUMABLE
```

Do not interpret a partial 32-item run as the final G0 corpus.

## 9.3 Generate L0 observable deliberation for all 1,024 startup rows

First preflight if useful:

```bash
python3 "$BASE/run_deliberation_observatory.py" \
  --bundle "$BUNDLE" \
  --decision-run "$D0" \
  --output "$L0" \
  --scope all \
  --limit 32 \
  --counterfactual-suite none \
  --workers 1 \
  --dry-run
```

Then real L0:

```bash
python3 "$BASE/run_deliberation_observatory.py" \
  --bundle "$BUNDLE" \
  --decision-run "$D0" \
  --output "$L0" \
  --scope all \
  --limit 32 \
  --counterfactual-suite none \
  --workers 1
```

The L0 pass must preserve D0 decision hashes / immutable derived fields and may only emit evidence-linked explanations.

## 9.4 Optional CF after reviewing L0

Do not automatically spend the counterfactual budget merely because the code exists.

Default targeted diagnostic:

```bash
python3 "$BASE/run_deliberation_observatory.py" \
  --bundle "$BUNDLE" \
  --decision-run "$D0" \
  --output "$L0" \
  --scope all \
  --limit 32 \
  --counterfactual-suite core \
  --counterfactual-panels SWING \
  --workers 1
```

With 32 work items × 1 SWING agent × 5 scenarios, the default upper bound is 160 CF calls before deduplication / already-valid skips.

Never silently expand the CF panel or scenario library after looking at desirable answers.

---

# 10. What L0 is allowed to claim

L0 is designed to make the synthetic election intelligible without pretending the hidden reasoning trace is available.

Every substantive driver must be attached to evidence IDs from a closed catalogue.

Important implementation files:

```text
DELIBERATION_PROMPT_V1.md
DELIBERATION_OUTPUT_SCHEMA_V1.json
observatory_evidence.py
observatory_selection.py
observatory_exec.py
observatory_transforms.py
observatory_causal.py
observatory_report.py
run_deliberation_observatory.py
```

Validation should fail closed when an explanation cites:

- an unknown evidence ID;
- missing / blocked / ambiguous evidence as directional;
- a conflicting un-resolved feature;
- an unsupported political claim;
- a top/runner-up inconsistent with D0;
- probabilities or margins altered relative to D0.

If you improve the explanation layer, **never let explanation generation alter the vote generation layer**.

---

# 11. Frontend epistemic rules

Public frontend root:

```text
morocco26/frontends/agent_society_opus/source_v2/web
```

Important current files include:

```text
app.js
reader.js
social.js
social-core.js
abuse.js
g0-reference.js
data/reference_provenance.json
```

Before validated G0 promotion, public numbers derived from the deterministic reference must be labeled as E0/reference simulation, not as empirical LLM findings.

After G0 promotion:

- G0 may become the primary GPT-generated synthetic reference;
- E0 remains a visible/archived control;
- actual historical results remain clearly separate;
- L0 explanations must be labeled observable model-generated explanations, not hidden chain-of-thought;
- CF results must be labeled synthetic perturbation diagnostics;
- predictive validity must not be claimed before the registered historical/prospective scoring gate.

Promotion helpers:

```text
promote_g0_sol_frontend.py
promote_g0_frontend.py
promote_deliberation_frontend.py
```

Do not run a promotion merely because a partial startup run exists unless the task explicitly calls for a startup/diagnostic publication and the provenance labeling supports it.

---

# 12. Social extension

The social layer is a separate experiment, not a decorative animation.

Channels:

```text
family
work
neighborhood
```

Scientific conditions currently include:

```text
ISO
FAM
WORK
NEIGH
ALL
SHUFFLE
ALL_R2
```

`SHUFFLE` is a topology/placebo-style control and must be retained.

Current public preview lambdas recorded in state:

```text
family       0.18
work         0.10
neighborhood 0.06
```

These values are **illustrative and not calibrated**.

Do not describe R1/R2 movement generated with them as measured real-world social influence.

---

# 13. Public anti-abuse / security invariants

The public collector uses native PoW + short-lived single-use tickets before claims.

Security is part of experimental validity because duplicate/replayed/automated submissions can distort the synthetic population.

Never commit secrets.

In particular:

- a Supabase publishable/anon key in frontend code is not automatically a secret leak when RLS/policies are correct;
- a Supabase `service_role` / secret key is sensitive and must remain server-side;
- do not expose raw IPs;
- do not replace privacy-preserving hashed/bound identifiers with persistent direct identity unless a versioned protocol explicitly requires it.

When auditing security, distinguish a real secret from a publishable browser credential. Do not rotate credentials merely because a publishable key is visible.

---

# 14. Validation before committing

For G0 / observatory changes, run at minimum:

```bash
python3 -m py_compile \
  morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_chatgpt_baseline.py \
  morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol.py \
  morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_deliberation_observatory.py \
  morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/promote_g0_sol_frontend.py \
  morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/promote_deliberation_frontend.py
```

Then:

```bash
python3 -m unittest discover -v \
  -s morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/tests \
  -p 'test_*.py'
```

For frontend JavaScript changes, at minimum:

```bash
node --check morocco26/frontends/agent_society_opus/source_v2/web/app.js
node --check morocco26/frontends/agent_society_opus/source_v2/web/reader.js
node --check morocco26/frontends/agent_society_opus/source_v2/web/social.js
node --check morocco26/frontends/agent_society_opus/source_v2/web/social-core.js
node --check morocco26/frontends/agent_society_opus/source_v2/web/abuse.js
node --check morocco26/frontends/agent_society_opus/source_v2/web/g0-reference.js
```

Also run any narrower tests relevant to the code you touched.

A green Vercel status is not a substitute for these tests or for GitHub Pages production verification.

---

# 15. Provenance and generated artifacts

Every scientific run should retain enough information to answer:

- exactly which model and reasoning effort produced this output?
- which frozen prompt/schema/input hashes were used?
- was the context fresh?
- were tools/web/MCP disabled?
- were any retries performed, and why?
- were any target outcomes available to the model or orchestration step?
- what output hash belongs to each work item?
- can a partial run resume without changing prior validated rows?

Do not commit generated G0 outputs or authentication material merely for convenience. The baseline directory `.gitignore` intentionally excludes local run artifacts.

If artifacts must become durable/shareable, use an explicit, provenance-preserving handoff mechanism rather than casually adding huge generated corpora to git.

---

# 16. Truth hierarchy when documents disagree

Use this precedence order:

1. **A newer frozen protocol / manifest that explicitly supersedes an older one.**
2. **Machine-readable current state for the relevant workstream.**
3. **Actual code + tests implementing that frozen contract.**
4. This `AGENTS.md` project map.
5. Human-readable README prose.
6. Historical conversation summaries / old notes / stale deployment messages.

If two authoritative artifacts genuinely conflict:

- do not guess;
- identify the exact conflicting fields and commit hashes;
- prefer the stricter scientific boundary until the conflict is resolved;
- never resolve a conflict by opening an outcome or weakening blinding.

---

# 17. How to work autonomously here

When given a goal, do not return immediately with a speculative proposal.

A competent agent should, when tools permit:

1. inspect relevant state/protocol/code;
2. reproduce the issue;
3. verify assumptions from primary artifacts;
4. implement the smallest scientifically correct change;
5. add/update tests;
6. run validation;
7. inspect the diff for leakage or epistemic-status regressions;
8. update state/provenance when the change materially changes experiment status;
9. commit only after the above passes;
10. report exactly what was changed, what was verified, and what remains externally blocked.

Do not ask the owner to perform work that the agent can safely perform itself.

Legitimate owner-only/external blockers include, for example:

- authenticating a trusted local Codex CLI with the owner's ChatGPT account;
- supplying a local frozen bundle that is not present in the runtime;
- changing an external UI setting not exposed by available tools;
- intentionally authorizing a scientific unseal gate.

When blocked by such an action, leave the repo in a **fully prepared fail-closed state** so the owner action is minimal.

---

# 18. Things that look tempting but are wrong

Do **not**:

- replace E0 and delete the control;
- run 2,944 full Sol work items before reviewing the 32-item startup gate if the startup gate is still the registered plan;
- change Sol to Terra/Luna for cost reasons after a Sol run has begun;
- add web search to the voter judge;
- let L0 explanations feed back into D0 decisions;
- treat self-reported explanation as proven causality;
- remove the CF placebo because it "does nothing";
- select only politically plausible LLM outputs;
- use actual 2016/2021 outcomes to choose better-looking parameters before their registered gate;
- call illustrative R1/R2 social movement empirical social science;
- expose public collective direction during a collection phase whose protocol says it must remain hidden;
- automate `chatgpt.com` scraping as a substitute for the supported Codex execution path;
- commit `~/.codex/auth.json`, service-role secrets, raw tickets, or raw IPs;
- claim GitHub Pages is live merely because the workflow file exists;
- claim a model is predictive because its synthetic narratives are compelling.

---

# 19. What a successful final system should eventually contain

The desired end-state is an auditable stack roughly like:

```text
structural territorial baseline
        +
G0 synthetic voter decisions
        +
L0 observable evidence-linked deliberation
        +
CF sensitivity diagnostics
        +
AS2 independent BYO-LLM replication
        +
AS3 social propagation experiment
        ↓
2016 development/calibration under frozen rules
        ↓
freeze
        ↓
2021 holdout evaluation
        ↓
2026 pre-election prospective freeze
        ↓
post-election falsification
```

Success is **not** "the website looks believable".

Success is:

> a pre-election system that makes explicit probabilistic claims, survives a genuine holdout/prospective test, and quantifies whether agentic intelligence adds information beyond the structural baseline.

---

# 20. Minimal handoff checklist for the next agent

Before saying "I understand the project", verify all of the following yourself:

- [ ] I am on the intended branch.
- [ ] I read both `current_state.json` and `CHATGPT_ACCOUNT_G0_STATE_V1.json`.
- [ ] I know whether any real G0 outputs now exist.
- [ ] I know whether 2016 has been unsealed.
- [ ] I know whether 2021 has been unsealed.
- [ ] I know whether public AS2 collection has actually started.
- [ ] I know whether GitHub Pages production is actually verified live.
- [ ] I can distinguish E0, G0/D0, L0, CF, AS2/R0, and AS3/R1-R2.
- [ ] I know which files are frozen and which are implementation details.
- [ ] I will not use target outcomes to improve pre-outcome decisions.
- [ ] I will preserve provenance and fail closed on uncertainty.

If you cannot check one of these items from the repository/tooling available to you, state the uncertainty explicitly rather than inventing an answer.

---

## Final operating principle

**Be ambitious in engineering and conservative in scientific claims.**

Automate aggressively, investigate deeply, and remove avoidable human work — but never weaken blinding, falsifiability, provenance, controls, or holdout discipline to make progress appear faster.
