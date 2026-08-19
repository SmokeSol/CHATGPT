# ATLAS // SOCIÉTÉ — final reader handoff

## Non-negotiable visual rule
Preserve the existing Opus frontend visual language exactly: plane `#070b11`, Majorelle blue, saffron ramp, subtle zellige, typography, spacing, cards, motion and micro-interactions. Do not redesign the art direction.

## Reader promise
The product is **La Société artificielle du Maroc**.

A reader must understand the experience in seconds:
1. **Explorer** — enter a parallel Morocco, browse real constituencies and real parties.
2. **Comprendre** — compose a synthetic citizen and watch the choice move as life circumstances change.
3. **Participer** — one primary CTA only: `Participer` / `Apportez votre IA`.
4. After the CTA, choosing ChatGPT, Claude or another assistant is merely a practical choice. It is not a separate experiment in the UI.
5. **Suivre** — show one collective progress bar, never provider-specific counters.
6. **Révéler** — collective contributed results remain hidden until the experiment is closed.
7. **2016 → 2021 → 2026** — past elections are the testing ground; 2026 is the destination.

## Reader language
Use: Maroc, société, citoyens, circonscriptions, partis, programmes, vote, participation, bilan, décision, explorer, révéler.
Never surface in the primary UI: work item, batch, condition, SHA, JSON, prompt, API, MCP, provider cohorts, E0, scoring jargon, or internal contribution sizes.

## Participation
There is one public society, regardless of which assistant a reader uses. Assistant identity is retained only behind the scenes for later robustness checks.

Public participation service:
`https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation`

Claude connector endpoint:
`https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-mcp`

The source input must remain the exact frozen historical package; never reconstruct approximate participant payloads from outputs.
