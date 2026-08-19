# Agent Society V2 — public collection security audit (2026-08-19)

Status: **PRE-OUTCOME / NO REAL LLM CONTRIBUTIONS RECEIVED**.

## Public collection protections

- Cloudflare Turnstile is required before issuing a participation ticket.
- Turnstile verification is server-side and bound to action `atlas_claim`.
- Raw browser identifiers and raw IP addresses are not stored; only server-side peppered SHA-256 pseudonyms are persisted.
- Participation tickets are random, short-lived (300 seconds), single-use, and only their SHA-256 hashes are stored.
- Web claims are browser-bound. MCP claims require a ticket first issued by the protected web flow.
- Work items are selected pseudo-randomly using the single-use ticket and never from outcomes or mapping.
- Public/anon/authenticated roles cannot execute privileged ASV2 ticket/claim/finalize RPCs; only `service_role` can.
- Sensitive security tables have RLS enabled and no direct public access.

## Frozen rate limits

- 1 active claim per participant.
- 3 active claims per IP pseudonym.
- 3 claims per participant per 24h.
- 10 claims per IP pseudonym per 24h.
- 3 completed contributions per participant per 24h.
- 5 participation tickets per participant per hour.
- 20 participation tickets per IP pseudonym per hour.
- Cooldown after 5 expired claims from the same IP pseudonym in 24h.

## Anti-poisoning rule

Automatic quarantine is deliberately **non-substantive**. Political direction or output shape must never be used to reject a contribution.

Automatic quarantine threshold: 100 points.

- Exact canonical behavior fingerprint repeated across a different assignment: +100.
- Exact raw output replay across a different assignment: +100.
- Submission latency below 3 seconds: +10 metadata-only flag; it cannot quarantine by itself.

The following are explicitly forbidden as automatic exclusion criteria: party direction, turnout level, party-probability entropy/uniformity/diversity, factor-importance patterns, or political reason-code content.

Quarantined material is preserved for audit but excluded from aggregation and from R1/R2 socialization. The contributor is not told whether a valid-looking submission was accepted or quarantined, to avoid creating an oracle for evasion.

## Legacy ingest endpoint finding and remediation

During this audit, the previously deployed `asv2-payload-ingest` v1 was found to contain a hard-coded ingestion credential in server-side Edge Function source and to initialize a service-role Supabase client. There was no evidence that this credential was committed to the GitHub repository or exposed in the browser frontend, and it was not the Supabase `service_role` key. Nevertheless, retaining an upload endpoint after the payload registry was frozen was unnecessary attack surface.

Remediation: `asv2-payload-ingest` v2 is permanently retired. It contains no Supabase client, no storage access and no secret, and returns HTTP 410 `INGEST_RETIRED` for every request. The old credential is not reproduced anywhere in this repository.

## Secret handling

- No literal Supabase JWT (`eyJ…`) or `sb_secret_…` key is present in the repository search performed after remediation.
- Runtime administrative access in active Edge Functions reads the Supabase service role from the Edge Function secret environment, never from frontend code.
- The Turnstile secret must be configured only as an Edge Function secret. The Turnstile site key is public by design.

## Opening gate

The collection must remain fail-closed until the production Turnstile widget is configured and both `TURNSTILE_SITE_KEY` and `TURNSTILE_SECRET_KEY` are installed in the Supabase Edge Function secret environment. No 2016 or 2021 outcome is opened by this security work.
