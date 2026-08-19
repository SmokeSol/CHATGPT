# -*- coding: utf-8 -*-
"""Provenance gate for isolated Agent Society baselines.

The scientific AS3 track may only consume a true AS2 Opus-5 isolated run:
one fresh model context per work item, complete schema-valid outputs, and the
frozen terminal PASS status. The known deterministic reference (E0) remains
usable only for explicit mechanics/reference runs.
"""
from __future__ import division
import os

try:
    from .common import read_json, sha256_file
except ImportError:
    from common import read_json, sha256_file


EXPECTED_EXPERIMENT = "EXP_7C8A2F11"
EXPECTED_ENVIRONMENT = "ENV_4D19B3E7"
EXPECTED_MODEL_FAMILY = "claude-opus-5"
EXPECTED_WORK_ITEMS = 2944
EXPECTED_ROWS = 94208
PASS_STATUS = "PASS_FULL_ENV_ASV2_HISTORICAL_VOTES_FROZEN_READY_FOR_SCORING"
DEVIATION_STATUS = "FROZEN_SCHEMA_COMPLETE_WITH_EXECUTION_CONTRACT_DEVIATION"
TERMINAL_NAME = "as2_full_environment_terminal_report.json"
MANIFEST_NAME = "as2_full_environment_output_manifest.json"


def _locate(baseline_run, filename):
    candidates = (
        os.path.join(baseline_run, "outputs", filename),
        os.path.join(baseline_run, filename),
    )
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise ValueError(
        "baseline provenance file missing: %s (looked under baseline root and outputs/)"
        % filename
    )


def _bool(mapping, key):
    return mapping.get(key) is True


def _is_opus5_model(value):
    """Accept the frozen family label and dated/provider suffixes, never another family."""
    if not isinstance(value, str):
        return False
    model = value.strip().lower()
    return model == EXPECTED_MODEL_FAMILY or model.startswith(EXPECTED_MODEL_FAMILY + "-")


def classify_baseline(baseline_run):
    """Return a fail-closed provenance classification for one extracted run."""
    terminal_path = _locate(baseline_run, TERMINAL_NAME)
    manifest_path = _locate(baseline_run, MANIFEST_NAME)
    report = read_json(terminal_path)
    manifest = read_json(manifest_path)

    errors = []
    if report.get("experiment_id") != EXPECTED_EXPERIMENT:
        errors.append("terminal experiment_id mismatch")
    if report.get("environment_extension_id") != EXPECTED_ENVIRONMENT:
        errors.append("terminal environment id mismatch")
    if manifest.get("experiment_id") != EXPECTED_EXPERIMENT:
        errors.append("manifest experiment_id mismatch")
    if manifest.get("environment_extension_id") != EXPECTED_ENVIRONMENT:
        errors.append("manifest environment id mismatch")

    counts = report.get("counts") or {}
    mcounts = manifest.get("counts") or {}
    for key, expected in (
        ("work_items_expected", EXPECTED_WORK_ITEMS),
        ("work_items_processed", EXPECTED_WORK_ITEMS),
        ("rows_expected", EXPECTED_ROWS),
        ("rows_emitted", EXPECTED_ROWS),
    ):
        if counts.get(key) != expected:
            errors.append("terminal %s != %d" % (key, expected))
        if mcounts.get(key) != expected:
            errors.append("manifest %s != %d" % (key, expected))

    validation = report.get("validation") or {}
    mvalidation = manifest.get("validation") or {}
    if validation.get("all_rows_schema_valid") is not True:
        errors.append("terminal all_rows_schema_valid is not true")
    if mvalidation.get("all_rows_schema_valid") is not True:
        errors.append("manifest all_rows_schema_valid is not true")
    for key in ("json_schema_errors", "closure_sum_errors", "row_order_errors", "identity_errors"):
        if validation.get(key) != 0:
            errors.append("terminal %s != 0" % key)
        if mvalidation.get(key) != 0:
            errors.append("manifest %s != 0" % key)

    comp = report.get("execution_contract_compliance") or {}
    generated = manifest.get("generated_by") or {}
    model = comp.get("model")
    manifest_model = generated.get("model_id")
    fresh = comp.get("fresh_model_context_per_work_item")
    manifest_fresh = generated.get("fresh_model_context_per_work_item")

    if not _is_opus5_model(model):
        errors.append("terminal model is not in the %s family" % EXPECTED_MODEL_FAMILY)
    if not _is_opus5_model(manifest_model):
        errors.append("manifest model_id is not in the %s family" % EXPECTED_MODEL_FAMILY)
    if model != manifest_model:
        errors.append("model id differs between terminal report and manifest")
    if fresh is not manifest_fresh:
        errors.append("fresh-context flag differs between terminal report and manifest")

    required_contract_bools = (
        "used_only_sealed_zip",
        "no_web_repository_or_outside_information",
        "no_memory_based_reidentification",
        "no_target_outcomes_or_post_cutoff_facts",
        "party_ids_treated_as_territory_local",
        "conditions_treated_identically_and_roles_not_inferred",
        "retry_schema_invalid_only",
        "stopped_before_scoring",
    )
    for key in required_contract_bools:
        if not _bool(comp, key):
            errors.append("execution contract %s is not true" % key)
    if comp.get("cross_archetype_answer_borrowing") is not False:
        errors.append("cross_archetype_answer_borrowing must be false")
    if comp.get("semantic_feedback_on_retry") is not False:
        errors.append("semantic_feedback_on_retry must be false")

    status = report.get("terminal_status")
    schema_gate = (report.get("schema_and_completeness_gate") or {}).get("gate_result")

    baseline_class = "UNKNOWN_REJECTED"
    eligible = False
    if not errors:
        if (
            status == PASS_STATUS
            and schema_gate == PASS_STATUS
            and fresh is True
            and manifest_fresh is True
        ):
            baseline_class = "AS2_OPUS5_ISOLATED_FRESH_CONTEXT"
            eligible = True
        elif (
            status == DEVIATION_STATUS
            and schema_gate == PASS_STATUS
            and fresh is False
            and manifest_fresh is False
        ):
            baseline_class = "E0_DETERMINISTIC_REFERENCE"
            eligible = False
        else:
            errors.append("terminal/fresh-context combination is not a recognized baseline class")

    return {
        "schema_version": "ATLAS_BASELINE_PROVENANCE_GATE_V1",
        "baseline_class": baseline_class,
        "eligible_for_as3_calibration": bool(eligible),
        "experiment_id": report.get("experiment_id"),
        "environment_id": report.get("environment_extension_id"),
        "model": model,
        "fresh_model_context_per_work_item": fresh,
        "terminal_status": status,
        "schema_gate": schema_gate,
        "work_items": counts.get("work_items_processed"),
        "rows": counts.get("rows_emitted"),
        "terminal_report_sha256": sha256_file(terminal_path),
        "output_manifest_sha256": sha256_file(manifest_path),
        "errors": errors,
    }


def require_as2_baseline(baseline_run):
    info = classify_baseline(baseline_run)
    if not info["eligible_for_as3_calibration"]:
        raise ValueError(
            "AS2 provenance gate failed: baseline_class=%s fresh_model_context_per_work_item=%r "
            "terminal_status=%r errors=%r. E0 is reference-only; do not unseal/calibrate 2016."
            % (
                info["baseline_class"],
                info["fresh_model_context_per_work_item"],
                info["terminal_status"],
                info["errors"],
            )
        )
    return info
