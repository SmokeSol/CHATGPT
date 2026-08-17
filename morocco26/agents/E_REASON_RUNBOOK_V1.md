# E_reason V1 — execution runbook

## Non-negotiable ancestry

- Branch: `morocco26-e-reason`
- Exact parent: `1f6403f80d1516de7c407d1a3ddebbbbd0f9c9b5`
- F-1, B2, F0 and `morocco26/data/goal100/e_collect/**` are immutable.
- `morocco26/web/**`, deployment files and Atlas production/UI are out of scope.

## Order of operations

1. Validate the preregistration and immutable-path diff guard.
2. Archive and extract only evidence published before each historical cutoff.
3. Build complete 92 x 9 evidence panels; encode missingness rather than dropping cells.
4. Generate an anonymization mapping and publish only its SHA-256.
5. Freeze 2016 packets, run C1 and C2, then calibrate `lambda_C1` and `lambda_C2` on 2016 only.
6. Freeze 2021 packets and parameters.
7. Run C1 and C2 on 2021 without access to outcomes or the mapping.
8. Commit packet and judgment manifests.
9. Unseal outcomes in a separate scoring step.
10. Issue exactly one terminal certificate: promote, no-promotion, data-insufficient, leakage-invalidated or execution-blocked.
11. Create an F1 candidate only after `E_REASON_PROMOTE` and a separate 2026 application certificate.

## Interpretation discipline

A 2021 success is a **component-level locked holdout** for E_reason, not a pristine end-to-end holdout for the already-selected Bstar family. The decisive prospective falsification remains the 2026 election.

Narrative quality, political plausibility and confidence scores receive no scientific credit.
