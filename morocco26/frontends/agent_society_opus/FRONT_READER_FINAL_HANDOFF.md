# ATLAS // SOCIÉTÉ — reader final handoff

## Non-negotiable visual rule
Preserve the existing Opus frontend visual language exactly: plane `#070b11`, Majorelle blue, saffron ramp, subtle zellige, typography, spacing, cards, micro-interactions and strict CSP. Do not redesign or change the art direction.

## What the reader must experience
The product is **La Société artificielle du Maroc**. Technical experimental vocabulary is never part of the primary UI.

Primary journey:
1. **Explorer le Maroc** — 2016 / 2021, 92 real constituencies, real party names (RNI, PAM, PJD, Istiqlal, USFP, MP, PPS, UC, Autres).
2. **Participer** — two large CTAs: `Contribuer avec ChatGPT` and `Contribuer avec Claude`. One contribution = 32 synthetic citizens voting. Show progress only; never reveal collective contributed results while collection is open.
3. **Faites voter un citoyen** — retain the Opus interactive simulator, but expose the real public political labels. The existing sample territory is El-Gharb, 2021. Local party labels are: Q_01=PAM, Q_02=Autres, Q_03=RNI, Q_04=PPS, Q_05=Mouvement populaire, Q_06=PJD, Q_07=Union constitutionnelle, Q_08=USFP, Q_09=Istiqlal.
4. **Ce qui fait voter / Le regard sur le bilan / Qui change d’avis / Portraits** — keep Opus interaction and visual components, rewrite only labels when needed so a normal reader understands them.
5. **2016 → 2021 → 2026** — make 2026 the narrative destination: past elections are the test ground; 2026 is the prospective experiment.

## Reader language
Use: citoyens, société, Maroc, circonscriptions, partis, programmes, vote, participation, bilan, décision.
Avoid in the primary UI: work item, condition_id, SHA, JSON, prompt, API, MCP, batch, residual, latent posterior, E0, scoring jargon.

## Participation services already deployed
Public status/claim/submit service:
`https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation`

Claude remote MCP endpoint:
`https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-mcp`

Two separate societies are registered:
- `AS2_CHATGPT_V1` — 2,944 contributions target
- `AS2_CLAUDE_V1` — 2,944 contributions target

Database work registry contains exactly 2,944 contribution slots. Payload serving is intentionally locked until the exact frozen input payloads are loaded. Do not invent or reconstruct approximate payloads from outputs.

## Collection UX
While collecting:
- show `x / 2,944 contributions validées` per provider;
- show `32 citoyens` per contribution;
- keep collective voting results hidden;
- after completion: freeze first, then unlock `Révéler les résultats`.

## ChatGPT public GPT package
The final source bundle contains an OpenAPI Action specification and GPT instructions. Once the GPT is published, insert its public URL into the ChatGPT CTA. The reader must never enter an API key or password on our site.

## Claude package
The remote MCP service is already active. The Claude CTA should lead to the simplest supported connector/opening flow. Again, no password is ever collected by our site.

## Method language
Primary explanation only:
> Nous avons reconstruit une population synthétique dans les 92 circonscriptions du Maroc. Chaque citoyen a une situation, un passé électoral, des priorités et des partis devant lui. Des assistants IA les font voter un par un. Les résultats collectifs restent cachés jusqu’à la fin de la collecte.

## Scientific boundary
Do not describe the current deterministic demonstration as an Opus/ChatGPT behavioral result. In reader-facing copy, simply call it `la simulation` / `le démonstrateur`. The actual contributed ChatGPT and Claude societies remain separate and unrevealed until frozen.
