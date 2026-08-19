# Baseline provenance — E0, AS2, AS3

This file is an additive pre-unseal amendment. It resolves one ambiguity discovered after the
first Opus-5 handoff was returned. No election outcome is used here.

## E0 — deterministic reference

The archive currently registered under
`morocco26/data/goal100/agent_society_v2/external_outputs/e0_deterministic_reference/`
is complete and schema-valid, but its own terminal report states:

- `terminal_status = FROZEN_SCHEMA_COMPLETE_WITH_EXECUTION_CONTRACT_DEVIATION`;
- `model = claude-opus-5`;
- `fresh_model_context_per_work_item = false`;
- 2,944 / 2,944 work items processed;
- 94,208 / 94,208 rows emitted.

It is therefore **E0**, a deterministic implementation of the frozen prompt, not an Opus-5
behavioural sample. It may be used for reproducibility and mechanics tests only. It must never be
renamed AS2 and must never unlock the 2016 calibration outcome.

## AS2 — required isolated Opus-5 run

The scientific isolated baseline is accepted only when `social/engine/baseline_gate.py` verifies
both the terminal report and output manifest and obtains all of the following:

- experiment `EXP_7C8A2F11` and environment `ENV_4D19B3E7`;
- model `claude-opus-5`;
- `fresh_model_context_per_work_item = true` in both artifacts;
- terminal status exactly `PASS_FULL_ENV_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING`;
- schema/completeness gate exactly the same PASS status;
- 2,944 work items and 94,208 rows complete;
- zero schema, closure, row-order and identity errors;
- frozen information-boundary contract satisfied.

Only that class is returned as `AS2_OPUS5_ISOLATED_FRESH_CONTEXT`.

## AS3 — social extension

For scientific AS3, `R0` means the accepted AS2 isolated decisions above. `R1` and `R2` are the
pre-registered synchronous social rounds. The deterministic E0 archive can still exercise the
social machinery only through the explicit `--allow-e0-reference` switch; those outputs are
marked `E0_MECHANICS_REFERENCE_ONLY_NOT_AS3`.

`calibrate_lambda.py` invokes the AS2 provenance gate **before opening the supplied 2016 outcome
adapter**. Consequently E0 cannot accidentally unseal or calibrate 2016.

2021 remains sealed until the 2016 lambda file has been produced and frozen from a true AS2-based
AS3 run.
