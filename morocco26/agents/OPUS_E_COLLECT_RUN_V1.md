# OPUS E_collect V1 — autonomous multi-agent runbook

## Mission
Execute the frozen `M26-GOAL100-E-COLLECT-V1` collection benchmark on branch `morocco26-e-collect`. The scientific question is **collection only**: can an Arabic-native agentic system recover verified electoral evidence that frozen deterministic B2 could not recover?

## Non-negotiable preflight
1. `git fetch origin`
2. Checkout `morocco26-e-collect`.
3. Confirm the branch descends from F0 parent commit `540802f08cd2ac565ea59d531d51ac3f58d83d38`.
4. Read and hash-check every artifact listed in `morocco26/data/goal100/e_collect/e_collect_preregistration_certificate.json`.
5. Abort with `FAIL_PROTOCOL` if any frozen preregistration artifact differs.
6. Do **not** edit F-1, F0, B2, the preregistration certificate, protocol, source policy, normalization policy, output schema, scoring contract, test-set manifest, or Atlas V1 release contract.

## Team architecture
Use parallel specialist agents, with isolated notes and deterministic merge:
- `A1_ARABIC_TERRITORY`: resolve the 92 Arabic constituency strings to canonical territory IDs using Arabic-native evidence.
- `A2_PJD_ROSTER`: candidate/list-agent identity and roster evidence for the 92 PJD rows.
- `A3_HIST_ROSTER_2011_2016`: historical candidate-roster recovery.
- `A4_HIST_ROSTER_2021`: historical candidate-roster recovery for 2021 with strict pre-election cutoff.
- `A5_PARTY_SWITCH_INCUMBENCY`: party switches, defections, incumbency, local/national party office.
- `A6_ALLIANCE_ENDORSEMENT`: formal alliances, endorsements, list rejection/withdrawal/disqualification.
- `A7_CAMPAIGN_SANCTION`: campaign launch, official investigation/sanction, death/incapacity.
- `A8_OFFICIAL_ARABIC`: Arabic official/institutional source discovery.
- `A9_SOURCE_QA`: source-class qualification and provenance audit. This agent must not invent evidence.
- `A10_ENTITY_QA`: duplicate/conflict detection and bilingual entity-link proposal review.

The collector may add subagents, but every accepted proposal must identify the producing agent.

## Source boundary
Read `e_collect_source_policy_v1.json` first. Allowed evidence is only:
- official/institutional Moroccan sources;
- official Moroccan political-party websites;
- Médias24;
- archived copies of those same original domains.

Other media, Wikipedia, search snippets, social media, blogs, aggregators and LLM output are discovery aids at most and **must never become accepted evidence**.

## Arabic-native rule
Read `e_collect_arabic_normalization_v1.json`.
- Preserve original Arabic exactly.
- Search in Arabic directly.
- Do not route Arabic through mandatory French translation.
- Do not use transliteration as proof.
- If identity remains ambiguous, output `AMBIGUOUS`.

Useful Arabic search vocabulary includes, without limiting the search:
`انتخابات`, `الانتخابات التشريعية`, `مرشح`, `مرشحة`, `لائحة`, `وكيل اللائحة`, `دائرة انتخابية`, `تزكية`, `تحالف`, `انسحاب`, `انتقال حزبي`, `برلماني`, `نائب`, `رئيس جماعة`, `عضو المكتب السياسي`, `إقصاء`, `منع`, `وفاة`.

## Phase 1 — frozen benchmark only
Do **not** broaden to all 2026 parties yet.

### Corpus A: 92 Arabic PJD rows
Input is exactly:
`morocco26/data/goal100/b2_2026_ballot_roster.json`
SHA-256: `b702b92929f7271c0309c0e3a8d4336b6e1bd79ee87a222b0cf834bc37c767ac`

For every one of the 92 rows:
1. preserve its source Arabic strings;
2. search allowed Arabic/French sources;
3. propose a canonical constituency ID only if the evidence meets the frozen verification rule;
4. preserve conflicting candidates/territories;
5. emit exactly one terminal status for each row.

### Corpus B: 16 historical input classes
Process exactly the 16 classes in `e_collect_testset_manifest_v1.json`.
For each class, produce:
- search surface summary;
- correct historical cutoff discipline;
- evidence records found;
- missing/data-blocked explanation;
- no inference from later election outcomes.

## Evidence durability
Create a unique run:
`morocco26/data/goal100/e_collect/runs/<RUN_ID>/`

Minimum contents:
- `run_manifest.json`
- `source_registry.json`
- `records.jsonl`
- `terminal_92.json`
- `terminal_16.json`
- `conflicts.jsonl`
- `rejected_sources.jsonl`
- `search_log.jsonl`
- `raw/` archived allowed-source evidence where legally/technically possible, with SHA-256 sidecars
- `collector_report.md`

Never delete failed attempts. If a run is superseded, archive it and write a supersession record.

## Output contract
Every evidence proposal must validate against:
`e_collect_output_schema_v1.json`

`PROPOSED_VERIFIED` means **collector proposal only**, not final scientific acceptance. The independent controller performs final adjudication after the run.

## No forecast work
Forbidden:
- change F0 probabilities;
- change coefficients;
- estimate seat impact;
- say a nomination is bullish/bearish for a party;
- create F1;
- run E_reason or E_full.

## Completion
The run is complete only when:
- all 92 roster rows have terminal statuses;
- all 16 historical classes have terminal reports;
- all evidence has provenance and hashes;
- source QA has run;
- no preregistration artifact was changed.

Commit and push the completed benchmark to `morocco26-e-collect`.
Commit message prefix: `experiment(e-collect):`

At the end, report:
1. final commit SHA;
2. run ID;
3. 92-row proposed resolution count;
4. count of historical classes with proposed admissible evidence;
5. source-policy violations/rejections;
6. conflicts/ambiguities;
7. any access blockers;
8. explicit confirmation that F-1/F0/B2 and all preregistration artifacts were unchanged.

**Do not proceed to production-wide Atlas V1 collection. Stop after the frozen benchmark and wait for independent adjudication.**
