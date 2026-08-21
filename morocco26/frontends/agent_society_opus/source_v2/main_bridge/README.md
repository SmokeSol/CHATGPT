# Main → Agent Society bridge

This is the reproducible electoral-data bridge from `main` into the historical Agent Society LLM experiment.

## Purpose

The 94,208-row full environment already contains anonymous candidate/context features and anonymous programme-priority cards. `main` is the canonical governed evidence pipeline behind that intelligence. Bridge V1 makes that relationship explicit and reproducible without weakening the blind experiment.

Bridge V1 reads **one exact `main` commit**, consumes only the already-blinded pre-cutoff `E_reason` bundles plus leakage/cutoff contracts, reconciles their opaque `P_*` party namespace with the full-environment `Q_*` namespace using baseline vote-share signatures, and emits a frozen anonymous audit overlay. The original environment ZIP stays byte-for-byte unchanged.

Registered upstream commit:

```text
4df897c356d3f0c36832405c7fcfc7f8f0cd6de2
```

Frozen full-environment ZIP SHA-256:

```text
e8acad28dea5a531c21171db570b60d612993edd91db8f893e58c187c226696a
```

## Critical V1 rule: provenance, not duplicated evidence

Bridge V1 is **semantic-equivalence only**.

It verifies, for every anonymous election × territory × party, that the non-meta candidate features in `main`'s blind bundles are exactly the candidate features already present in the frozen full environment. It also verifies that the existing anonymous programme cards are unchanged.

Therefore **Sol does not receive an extra `main_bridge_v1` evidence object**. The model sees the original frozen work item exactly once. The bridge file SHA, per-item SHA and exact `main` commit are attached to orchestration provenance, not repeated as political evidence.

If Bridge V1 finds a new or changed directionally usable candidate/programme field, it fails closed. Such a semantic enrichment requires a new pre-registered Bridge V2 before any affected G0 output can be generated.

This prevents duplicate evidence from being accidentally overweighted by the model.

## What the audit overlay contains

For provenance/audit only, each anonymous election × territory contains:

- one deterministic opaque candidate/list-head audit card per anonymous party;
- allowed pre-cutoff candidate/event feature states from `main`;
- explicit `VERIFIED`, `MISSING`, and conflict state;
- source class and anonymous source-record IDs;
- an opaque candidate ID;
- the already-frozen anonymous programme-priority card;
- semantic-equivalence counters.

The overlay contains **no real candidate names, party names, territory names, election years, target outcomes, or raw article prose**.

## Why not all of `main`?

`main` also contains later exploratory candidate-intelligence work, including `candidate_intelligence_v3`, whose own contract is post-2021 exploratory. That material is explicitly forbidden from this historical blind G0.

Bridge V1 source allowlist is restricted to:

```text
morocco26/data/goal100/e_reason/blind/development/blind_bundle.json
morocco26/data/goal100/e_reason/blind/holdout/blind_bundle.json
morocco26/data/goal100/e_reason/e_reason_historical_cutoffs_v1.json
morocco26/data/goal100/e_reason/e_reason_information_set_v1.json
morocco26/data/goal100/e_reason/e_reason_leakage_control_v1.json
```

## Programme caveat

Bridge V1 does not claim that a canonical complete historical manifesto corpus has been identified on `main`. It verifies and preserves the anonymous programme-priority cards already frozen in the full environment. Adding full manifestos requires an audited pre-cutoff source registry and a new bridge protocol version before affected model outputs exist.

## Build the bridge locally

From a clone that contains the registered `main` git object and the frozen full-environment ZIP:

```bash
python3 morocco26/scripts/agent_society_v2_main_bridge.py \
  --repo-root . \
  --main-sha 4df897c356d3f0c36832405c7fcfc7f8f0cd6de2 \
  --environment "$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip" \
  --output "$HOME/agent-society-runs/main_bridge_v1.json"
```

Expected terminal:

```text
PASS_MAIN_TO_AGENT_SOCIETY_BRIDGE_V1 items=184 ...
```

A PASS now means all of the following:

- 2 × 92 anonymous election-territory cells resolved;
- P→Q party alignment is a blind bijection within frozen tolerance;
- candidate non-meta feature sets match exactly;
- candidate status/value/conflict cells match exactly;
- programme cards match exactly;
- public leak scan passes;
- no target outcome was read.

The builder also writes `main_bridge_v1.json.manifest.json` with source hashes, environment audit, exact upstream SHA and canonical overlay hash.

## Dry-run the 32-item G0 startup gate

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol_main_bridge.py \
  --bundle "$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip" \
  --main-bridge "$HOME/agent-society-runs/main_bridge_v1.json" \
  --output "$HOME/agent-society-runs/G0_SOL_MAIN_BRIDGE" \
  --limit 32 \
  --dry-run
```

The launcher independently refuses:

- any full-environment ZIP whose SHA-256 differs from the frozen hash;
- any `main_commit_sha` other than the registered SHA;
- any bridge with other than exactly 184 items;
- any bridge without semantic-equivalence PASS;
- any bridge with a leak/outcome/identity flag;
- attempts to override model, reasoning or canonical-count protections.

Then the real 32-work-item startup run:

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol_main_bridge.py \
  --bundle "$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip" \
  --main-bridge "$HOME/agent-society-runs/main_bridge_v1.json" \
  --output "$HOME/agent-society-runs/G0_SOL_MAIN_BRIDGE" \
  --limit 32 \
  --workers 1
```

The launcher freezes GPT-5.6 Sol / medium. Bridge provenance is folded into every task source hash while the model-visible frozen packet remains semantically unchanged.

## Invariants

- Never use floating `main` for a scientific run.
- Never open target outcomes in the bridge process.
- Never place real historical identities in the overlay or model context.
- Never interpret missing candidate evidence as negative evidence.
- Never duplicate an already-present feature as additional model evidence.
- Never silently accept a semantic delta in Bridge V1.
- Never fabricate manifesto details.
- Never feed post-outcome exploratory candidate layers into historical blind G0.
- Never overwrite E0 or the original full-environment ZIP.
- A new upstream SHA or richer input creates a reviewed new protocol/snapshot; it never silently mutates an existing run.
