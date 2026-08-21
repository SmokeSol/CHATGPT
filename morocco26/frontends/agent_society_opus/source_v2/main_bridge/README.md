# Main → Agent Society bridge

This is the reproducible electoral-data bridge from `main` into the historical Agent Society LLM experiment.

## Purpose

The original 94,208-row full environment intentionally contains coarse anonymous political-offer cards. `main` has a richer, separately governed evidence pipeline. Agent Society should reuse it rather than fork it, while preserving the blind historical experiment.

Bridge V1 reads **one exact `main` commit**, consumes the already-blinded pre-cutoff E_reason bundles, reconciles their opaque `P_*` party namespace with the full-environment `Q_*` namespace using only baseline vote-share signatures, and emits a frozen anonymous overlay. The original environment ZIP stays byte-for-byte unchanged.

Registered upstream commit:

```text
4df897c356d3f0c36832405c7fcfc7f8f0cd6de2
```

## What Sol receives

Each anonymous election × territory gets an additional `main_bridge_v1` object with:

- one deterministic opaque candidate/list-head card per anonymous party;
- the full allowed candidate/event feature panel from `main`'s blinded evidence bundle;
- explicit `VERIFIED`, `MISSING`, and conflict state;
- source class and anonymous source-record IDs;
- an opaque candidate ID;
- the already-frozen anonymous programme-priority card.

It receives **no real candidate names, party names, territory names, election years, outcomes, or raw article prose**.

## Programme caveat

Bridge V1 does not claim that a canonical complete historical manifesto corpus has been identified on `main`. It preserves the anonymous programme-priority cards already frozen in the full environment. Adding full manifestos requires an audited pre-cutoff source registry and a new bridge protocol version before affected model outputs exist.

## Build

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

The builder also writes `main_bridge_v1.json.manifest.json` with source hashes, environment audit, exact upstream SHA, and canonical overlay hash.

## Dry-run enriched G0

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol_main_bridge.py \
  --bundle "$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip" \
  --main-bridge "$HOME/agent-society-runs/main_bridge_v1.json" \
  --output "$HOME/agent-society-runs/G0_SOL_MAIN_BRIDGE" \
  --limit 32 \
  --dry-run
```

Then the 32-work-item startup run:

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_g0_sol_main_bridge.py \
  --bundle "$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip" \
  --main-bridge "$HOME/agent-society-runs/main_bridge_v1.json" \
  --output "$HOME/agent-society-runs/G0_SOL_MAIN_BRIDGE" \
  --limit 32 \
  --workers 1
```

The launcher freezes GPT-5.6 Sol / medium and refuses to run without a PASS bridge. The bridge hash and upstream `main` SHA are folded into task provenance before the model context is hashed.

## Invariants

- Never use floating `main` for a scientific run.
- Never open target outcomes in the bridge process.
- Never place real historical identities in the public overlay.
- Never interpret missing candidate evidence as negative evidence.
- Never fabricate manifesto details.
- Never overwrite E0 or the original full-environment ZIP.
- A new upstream SHA creates a reviewed new snapshot; it never silently mutates an existing run.
