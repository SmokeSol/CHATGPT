# Agent Society live backend

This directory mirrors the production Supabase wiring for the public Agent Society contribution flow.

## Security boundary

- `SUPABASE_SERVICE_ROLE_KEY` is read only from the Supabase Edge Function environment. It must never be committed or shipped to the browser.
- Public claim issuance is protected by `ATLAS_POW_V1`: a short-lived, single-use SHA-256 proof-of-work challenge bound to a peppered browser identifier and peppered IP hash. No Cloudflare account, CAPTCHA provider, or third-party anti-bot secret is required.
- A valid proof produces a short-lived single-use participation ticket; the raw ticket is never stored, only its SHA-256 hash.
- Rate limits apply per participant and per IP hash before a work item can be claimed.
- Public participation endpoints validate every returned row against the claimed work item and voter-batch order.
- Automatic quarantine is limited to exact replay/duplicate evidence. Political direction or substantive LLM output shape is never an exclusion criterion.
- `asv2_social_previews` and `asv2_pow_challenges` are private (RLS enabled; no `anon`/`authenticated` direct table access).
- During collection the public social endpoint exposes only non-directional mechanics/status. Directional R0/R1/R2 samples remain locked until the cohort has a `revealed_at` timestamp.
- The historical `asv2-payload-ingest` function is retired and always returns HTTP 410; it no longer initializes a Supabase client or accepts uploads.

## Scientific boundary

The live social preview uses the frozen graph construction and synchronous R1/R2 mechanics, but its lambdas remain `ILLUSTRATIVE_NOT_CALIBRATED`. It does not replace the later 2016-only calibration and 2021 holdout protocol.

## Production functions

- `agent-society-participation` v9: PoW challenge → short-lived ticket → guarded claim → strict validation → immutable R0 submission → exact replay guard → automatic social preview derivation.
- `agent-society-mcp` v3: consumes a web-issued ticket before reserving a Claude contribution lot.
- `agent-society-social` v2: public non-directional status during collection; directional sample only after reveal.
- `asv2-payload-ingest` v2: retired; always HTTP 410.
