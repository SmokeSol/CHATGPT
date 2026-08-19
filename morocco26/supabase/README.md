# Agent Society live backend

This directory mirrors the production Supabase wiring for the public Agent Society contribution flow.

## Security boundary

- `SUPABASE_SERVICE_ROLE_KEY` is read only from the Supabase Edge Function environment. It must never be committed or shipped to the browser.
- Public participation endpoints use short-lived claim tokens and validate every returned row against the claimed work item and voter-batch order.
- `asv2_social_previews` is private (RLS enabled; no `anon`/`authenticated` table grants).
- During collection the public social endpoint exposes only non-directional mechanics/status. Directional R0/R1/R2 samples remain locked until the cohort has a `revealed_at` timestamp.

## Scientific boundary

The live social preview uses the frozen graph construction and synchronous R1/R2 mechanics, but its lambdas remain `ILLUSTRATIVE_NOT_CALIBRATED`. It does not replace the later 2016-only calibration and 2021 holdout protocol.

## Production functions

- `agent-society-participation`: claim → strict validation → immutable R0 submission → automatic social preview derivation.
- `agent-society-social`: public non-directional status during collection; directional sample only after reveal.
