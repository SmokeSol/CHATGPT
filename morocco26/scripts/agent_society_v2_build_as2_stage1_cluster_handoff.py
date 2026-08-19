# -*- coding: utf-8 -*-
"""Build an outcome-blind, cost-reduced AS2 Stage-1 cluster handoff.

Stage-1 samples exactly one of the eight 32-archetype voter batches for every
(anonymous election, anonymous territory) pair and includes BOTH opaque
conditions for that same selected batch. Selection is deterministic,
balanced across B01..B08 within each anonymous election, and made without any
outcome or mapping access.

This handoff is a COST GATE only. It does not satisfy or replace the frozen
2,944-work-item AS2 protocol and MUST NOT unlock 2016 calibration.
"""
from __future__ import division
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile

SEED = "EXP_7C8A2F11_AS2_STAGE1_CLUSTER_SAMPLE_V1"
EXPECTED_EXPERIMENT = "EXP_7C8A2F11"
EXPECTED_ENVIRONMENT = "ENV_4D19B3E7"
BATCH_IDS = ["B%02d" % i for i in range(1, 9)]
FIXED_ZIP_TIME = (2026, 8, 19, 0, 0, 0)


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(obj, pretty=False):
    return json.dumps(
        obj, ensure_ascii=False, sort_keys=True,
        indent=2 if pretty else None,
        separators=None if pretty else (",", ":"),
    ) + "\n"


def write_text(path, text):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def stable_hash(*parts):
    return hashlib.sha256("\x1f".join(str(x) for x in parts).encode("utf-8")).hexdigest()


def select_pairs(work_items):
    by_cell = {}
    by_pair = {}
    for item in work_items:
        ck = (item["anonymous_election_id"], item["anonymous_territory_id"], item["condition_id"])
        by_cell.setdefault(ck, []).append(item)
        pk = (item["anonymous_election_id"], item["anonymous_territory_id"])
        by_pair.setdefault(pk, {}).setdefault(item["condition_id"], {})[item["batch_id"]] = item

    if len(by_cell) != 368:
        raise ValueError("expected 368 election/territory/condition cells; found %d" % len(by_cell))
    for ck, items in by_cell.items():
        if sorted(x["batch_id"] for x in items) != BATCH_IDS:
            raise ValueError("cell does not contain B01..B08 exactly: %r" % (ck,))

    elections = sorted(set(k[0] for k in by_pair))
    if len(elections) != 2:
        raise ValueError("expected two anonymous election ids; found %r" % elections)

    selected_batch = {}
    balance = {}
    for election in elections:
        territories = sorted(
            [t for (e, t) in by_pair if e == election],
            key=lambda t: stable_hash(SEED, "territory-order", election, t),
        )
        if len(territories) != 92:
            raise ValueError("expected 92 territories for %s; found %d" % (election, len(territories)))
        batch_order = sorted(
            BATCH_IDS,
            key=lambda b: stable_hash(SEED, "batch-order", election, b),
        )
        counts = {b: 0 for b in BATCH_IDS}
        for i, territory in enumerate(territories):
            batch = batch_order[i % len(batch_order)]
            selected_batch[(election, territory)] = batch
            counts[batch] += 1
        balance[election] = counts
        if max(counts.values()) - min(counts.values()) > 1:
            raise ValueError("batch selection is not balanced for %s: %r" % (election, counts))

    selected_items = []
    selections = []
    for (election, territory), conds in sorted(by_pair.items()):
        batch = selected_batch[(election, territory)]
        if len(conds) != 2:
            raise ValueError("expected two opaque conditions for %s/%s" % (election, territory))
        voter_paths = set()
        out_paths = []
        for condition in sorted(conds):
            if set(conds[condition]) != set(BATCH_IDS):
                raise ValueError("condition missing batch ids for %s/%s/%s" % (election, territory, condition))
            item = conds[condition][batch]
            selected_items.append(item)
            voter_paths.add(item["voter_batch_path"])
            out_paths.append(item["output_path"])
        if len(voter_paths) != 1:
            raise ValueError("paired conditions do not share voter batch for %s/%s/%s" % (election, territory, batch))
        selections.append({
            "anonymous_election_id": election,
            "anonymous_territory_id": territory,
            "selected_batch_id": batch,
            "voter_batch_path": sorted(voter_paths)[0],
            "condition_output_paths": sorted(out_paths),
        })

    selected_items.sort(key=lambda x: x["output_path"])
    if len(selected_items) != 368:
        raise ValueError("expected 368 selected work items; found %d" % len(selected_items))
    return selected_items, selections, balance


def build(src, dest_dir):
    wm_path = os.path.join(src, "work_manifest.json")
    prompt_path = os.path.join(src, "as2_full_environment_prompt_v2.md")
    schema_path = os.path.join(src, "as2_full_environment_output_schema_v2.json")
    handoff_parent = os.path.join(src, "handoff_manifest.json")
    for p in (wm_path, prompt_path, schema_path, handoff_parent):
        if not os.path.isfile(p):
            raise ValueError("missing sealed parent input: %s" % p)

    wm = read_json(wm_path)
    if wm.get("experiment_id") != EXPECTED_EXPERIMENT or wm.get("environment_extension_id") != EXPECTED_ENVIRONMENT:
        raise ValueError("unexpected experiment/environment in parent work manifest")
    selected_items, selections, balance = select_pairs(wm["work_items"])

    os.makedirs(dest_dir, exist_ok=True)
    shutil.copy2(prompt_path, os.path.join(dest_dir, os.path.basename(prompt_path)))
    shutil.copy2(schema_path, os.path.join(dest_dir, os.path.basename(schema_path)))

    voter_paths = sorted(set(x["voter_batch_path"] for x in selected_items))
    context_paths = sorted(set(x["context_path"] for x in selected_items))
    for rel in voter_paths + context_paths:
        srcp = os.path.join(src, rel)
        dstp = os.path.join(dest_dir, rel)
        os.makedirs(os.path.dirname(dstp), exist_ok=True)
        shutil.copy2(srcp, dstp)

    reduced_wm = {
        "manifest_id": "FULL_ENV_AS2_STAGE1_CLUSTER_SAMPLE_WORK_MANIFEST_V1",
        "schema_version": "1.0",
        "experiment_id": EXPECTED_EXPERIMENT,
        "environment_extension_id": EXPECTED_ENVIRONMENT,
        "parent_work_manifest_sha256": sha256_file(wm_path),
        "selection_seed": SEED,
        "counts": {
            "context_files": len(context_paths),
            "rows": len(selected_items) * 32,
            "voter_batch_files": len(voter_paths),
            "work_items": len(selected_items),
        },
        "work_items": selected_items,
    }
    reduced_wm_path = os.path.join(dest_dir, "work_manifest.json")
    write_text(reduced_wm_path, canonical_json(reduced_wm, pretty=True))

    selection_manifest = {
        "manifest_id": "AS2_STAGE1_CLUSTER_SELECTION_V1",
        "status": "PRE_OUTCOME_COST_GATE_SELECTION_FROZEN",
        "experiment_id": EXPECTED_EXPERIMENT,
        "environment_extension_id": EXPECTED_ENVIRONMENT,
        "selection_seed": SEED,
        "selection_unit": "one_of_eight_32_archetype_batches_per_anonymous_election_territory_pair",
        "paired_conditions": True,
        "same_selected_voter_batch_across_both_opaque_conditions": True,
        "selection_uses_outcomes": False,
        "selection_uses_mapping": False,
        "batch_balance_by_anonymous_election": balance,
        "counts": {
            "anonymous_election_territory_pairs": len(selections),
            "selected_voter_batches": len(voter_paths),
            "work_items": len(selected_items),
            "rows_expected": len(selected_items) * 32,
            "full_protocol_work_items": len(wm["work_items"]),
            "work_item_reduction_factor": len(wm["work_items"]) / float(len(selected_items)),
        },
        "selections": selections,
    }
    selection_path = os.path.join(dest_dir, "stage1_selection_manifest.json")
    write_text(selection_path, canonical_json(selection_manifest, pretty=True))

    start = (
        "# START HERE — AS2 Stage-1 fresh-context cost gate\n\n"
        "This package is a PRE-OUTCOME COST GATE for EXP_7C8A2F11 / ENV_4D19B3E7.\n\n"
        "It contains 368 work items (11,776 voter rows), selected blindly as one 32-archetype batch from each anonymous election/territory pair and included under both opaque conditions.\n\n"
        "## Non-negotiable execution contract\n\n"
        "- Use **Claude Opus 5**.\n"
        "- Use **one genuinely fresh model context per work item**.\n"
        "- Each work item must see only its voter batch, its context, the frozen prompt and schema.\n"
        "- Never expose another work item's answer inside the current context.\n"
        "- Treat the two condition IDs identically and never infer their roles.\n"
        "- Use no web, repository, memory-based reidentification, mapping, outcomes or outside facts.\n"
        "- Retry only schema-invalid output with the identical prompt and no semantic feedback.\n"
        "- Stop before scoring.\n"
        "- **DO NOT write or substitute a deterministic engine, ruleset, script, emulator, batch judge, or shared-context evaluator.**\n"
        "- If 368 genuinely fresh contexts cannot be executed, return only `BLOCKED_FRESH_CONTEXT_EXECUTION_NOT_AVAILABLE` and stop.\n\n"
        "The exact frozen behavioural instruction is `as2_full_environment_prompt_v2.md`; the output must satisfy `as2_full_environment_output_schema_v2.json`.\n\n"
        "## Required returned artifacts\n\n"
        "- `outputs/<election>/<condition>/<territory>/<batch>.jsonl` for all 368 work items.\n"
        "- `outputs/as2_stage1_output_manifest.json` with model id, fresh-context=true, counts, validation errors, SHA-256 per output file and aggregate SHA-256.\n"
        "- `outputs/as2_stage1_terminal_report.json` with terminal status exactly `PASS_AS2_STAGE1_FRESH_CONTEXT_OUTPUTS_FROZEN_READY_FOR_RESIDUAL_GATE` only if every execution-contract and schema/completeness requirement passed.\n"
        "- If fresh contexts were not actually used, terminal status must be `BLOCKED_FRESH_CONTEXT_EXECUTION_NOT_AVAILABLE`; do not emit substitute behavioural rows.\n\n"
        "This Stage-1 package does **not** unlock 2016 calibration. Its outputs are compared only with the already-frozen E0 deterministic reference to decide whether a larger AS2 expenditure is justified.\n"
    )
    write_text(os.path.join(dest_dir, "START_HERE_OPUS5_AS2_STAGE1.md"), start)

    handoff = {
        "manifest_id": "AS2_STAGE1_CLUSTER_HANDOFF_V1",
        "status": "SEALED_READY_FOR_OPUS5_STAGE1_FRESH_CONTEXT_COST_GATE",
        "public_experiment_id": EXPECTED_EXPERIMENT,
        "public_environment_id": EXPECTED_ENVIRONMENT,
        "parent_work_manifest_sha256": sha256_file(wm_path),
        "parent_handoff_manifest_sha256": sha256_file(handoff_parent),
        "prompt_sha256": sha256_file(prompt_path),
        "schema_sha256": sha256_file(schema_path),
        "stage1_work_manifest_sha256": sha256_file(reduced_wm_path),
        "stage1_selection_manifest_sha256": sha256_file(selection_path),
        "counts": reduced_wm["counts"],
        "full_protocol_work_items": len(wm["work_items"]),
        "work_item_reduction_factor": len(wm["work_items"]) / float(len(selected_items)),
        "required_return": {
            "output_tree": "outputs/<election>/<condition>/<territory>/<batch>.jsonl",
            "output_manifest": "outputs/as2_stage1_output_manifest.json",
            "terminal_report": "outputs/as2_stage1_terminal_report.json",
            "pass_terminal_status": "PASS_AS2_STAGE1_FRESH_CONTEXT_OUTPUTS_FROZEN_READY_FOR_RESIDUAL_GATE",
            "blocked_terminal_status": "BLOCKED_FRESH_CONTEXT_EXECUTION_NOT_AVAILABLE"
        },
        "execution_contract": {
            "model_family": "CLAUDE_OPUS_5",
            "fresh_context_per_work_item": True,
            "deterministic_engine_substitution_allowed": False,
            "shared_context_batch_judging_allowed": False,
            "outside_information": False,
            "retry_schema_invalid_only": True,
            "semantic_feedback": False,
            "stop_before_scoring": True,
        },
        "scientific_role": "COST_GATE_ONLY_DOES_NOT_UNLOCK_2016_OR_REPLACE_FULL_AS2",
        "target_outcomes_present": False,
        "mapping_material_present": False,
        "e0_outputs_present": False,
    }
    handoff_path = os.path.join(dest_dir, "handoff_manifest.json")
    write_text(handoff_path, canonical_json(handoff, pretty=True))

    checksum_targets = [
        "START_HERE_OPUS5_AS2_STAGE1.md",
        "as2_full_environment_prompt_v2.md",
        "as2_full_environment_output_schema_v2.json",
        "work_manifest.json",
        "stage1_selection_manifest.json",
        "handoff_manifest.json",
    ] + context_paths + voter_paths
    lines = []
    for rel in sorted(checksum_targets):
        lines.append("%s  %s" % (sha256_file(os.path.join(dest_dir, rel)), rel))
    write_text(os.path.join(dest_dir, "judge_input_SHA256SUMS.txt"), "\n".join(lines) + "\n")

    return {
        "work_items": len(selected_items),
        "rows": len(selected_items) * 32,
        "voter_batches": len(voter_paths),
        "contexts": len(context_paths),
        "balance": balance,
    }


def deterministic_zip(src_dir, output_zip):
    rels = []
    for root, _, files in os.walk(src_dir):
        for name in files:
            path = os.path.join(root, name)
            rels.append(os.path.relpath(path, src_dir).replace(os.sep, "/"))
    rels.sort()
    with zipfile.ZipFile(output_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for rel in rels:
            path = os.path.join(src_dir, rel.replace("/", os.sep))
            info = zipfile.ZipInfo(rel, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            with open(path, "rb") as fh:
                zf.writestr(info, fh.read(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def cli(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("sealed_env_dir")
    ap.add_argument("output_zip")
    args = ap.parse_args(argv)
    tmp = tempfile.mkdtemp(prefix="as2_stage1_")
    try:
        summary = build(args.sealed_env_dir, tmp)
        deterministic_zip(tmp, args.output_zip)
    finally:
        shutil.rmtree(tmp)
    print("PASS_AS2_STAGE1_HANDOFF_FROZEN work_items=%d rows=%d voter_batches=%d contexts=%d sha256=%s" % (
        summary["work_items"], summary["rows"], summary["voter_batches"], summary["contexts"], sha256_file(args.output_zip)
    ))


if __name__ == "__main__":
    cli()
