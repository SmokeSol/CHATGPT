# OPUS E_collect V1.1 — human-seeded Arabic-native collection

## Mission
Deliver the fastest scientifically defensible path from frozen F0 to a fully functional Atlas V1 evidence layer. This run no longer tests whether Opus discovers source URLs better than a human. Human seeds are allowed and should be exploited aggressively. The measurable task is to convert permitted source surfaces into correct, provenance-complete, bilingual, canonical electoral data.

Read first:
- `morocco26/data/goal100/e_collect/e_collect_v1_1_human_seed_amendment.json`
- all frozen E_collect V1 artifacts and the existing V1 runbook.

## Immediate human seed
Start with and deeply enumerate:
`https://assets.medias24.com/elections/`

Do not stop at the directory/root response. Inspect Médias24 pages, asset references, network/static payloads, JSON/CSV/JS/data files, versioned paths, and archived copies where available. Record every discovered surface and its provenance.

The seed is a discovery hint, not factual evidence by itself. Every accepted record must still come from the allowed source policy and have hashable provenance.

## If V1 work has already started
Do NOT discard it and do NOT restart valid collection from zero.
- Preserve the original V1 run directory unchanged.
- Mark it `SUPERSEDED_FOR_DISCOVERY_ABLATION` in a new supersession record.
- Reuse valid evidence only after revalidating provenance/source/cutoff rules.
- Continue under a new V1.1 run ID.

## Discovery-origin bookkeeping
Every source/evidence record must include one of:
- `HUMAN_SEED`
- `AGENT_DISCOVERY`
- `REPO_EXISTING`

This is provenance only. Do not optimize for or score the ratio. There is no human-vs-agent discovery contest in V1.1.

## Parallel team
Keep or expand the 10-agent structure from V1. Prioritize parallel throughput:
1. Arabic territory/entity normalization
2. 2026 PJD roster
3. historical roster 2011/2016
4. historical roster 2021
5. incumbency/party switches/local and party office
6. alliances/endorsements/withdrawals/disqualifications
7. campaign launches/sanctions/investigations/death/incapacity
8. official Arabic source discovery
9. source/provenance QA
10. entity/conflict QA
11+ optional dedicated Médias24 asset enumerators if useful

## Phase A — finish the frozen quality benchmark quickly
Process all 92 Arabic PJD rows and all 16 historical classes. Human seeds may be used. The benchmark is now interpreted as a **verified extraction / entity-resolution / provenance quality gate**, not autonomous discovery attribution.

For each of the 92 rows produce a terminal status and, where evidence permits:
- canonical territory ID
- Arabic territory name
- Latin/French evidenced name(s)
- original Arabic form
- person/list-agent identity where supported
- source references
- confidence category based on evidence, never model intuition

For each of the 16 classes produce a terminal report with correct temporal cutoff.

## Phase B — Atlas V1 production expansion
Once Phase A outputs are internally QA-complete, do NOT wait for a human to manually feed URLs. Continue collecting production data for Atlas V1 from allowed sources, while keeping it computationally separate from F0.

Target all 92 constituencies and all major parties for 2026. Build a canonical bilingual evidence layer containing, when available:
- candidates/list agents
- party nominations
- incumbency
- local executive office
- national/regional party office
- party switches/defections
- formal alliances/endorsements
- withdrawals/disqualifications/list rejection
- campaign launch
- official sanction/investigation
- verified death/incapacity

Use official sources, official party sites and Médias24. Search Arabic and French natively.

## Atlas V1 product contract
Prepare production artifacts so the web app can display:
- immutable F0 forecast
- Arabic + Latin/French canonical territory identity
- 2026 candidate and signal ledger
- source URLs/content hashes/retrieval timestamps
- VERIFIED / PARTY_ANNOUNCED / AMBIGUOUS / UNVERIFIED / DATA_BLOCKED status
- last-updated timestamps
- explicit statement that 2026 signal impact on F0 is not calibrated yet

Do not alter forecast probabilities, coefficients or F0.

## Required output
Create or update only new E_collect / Atlas-V1 production artifacts. Preserve frozen V1 protocol files, B2, F-1 and F0.

At completion report:
1. final commit SHA
2. V1.1 run ID
3. 92-row resolution/verification counts
4. 16-class recovery counts
5. Médias24 asset surfaces discovered and usable
6. number of 2026 territories with at least one structured verified/party-announced record
7. source-policy rejection count
8. ambiguity/conflict count
9. explicit hash confirmation that F-1, F0 and B2 stayed unchanged
10. exact remaining blockers to Atlas V1 release

Do not run E_reason or assign forecast impact. Human-vs-LLM comparison is deferred to reasoning/predictive residual experiments.