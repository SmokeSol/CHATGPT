# -*- coding: utf-8 -*-
import json
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(ROOT, "engine")
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

import baseline_gate as B


def _payloads(fresh, status):
    counts = {
        "work_items_expected": 2944,
        "work_items_processed": 2944,
        "rows_expected": 94208,
        "rows_emitted": 94208,
    }
    validation = {
        "json_schema_errors": 0,
        "closure_sum_errors": 0,
        "row_order_errors": 0,
        "identity_errors": 0,
        "all_rows_schema_valid": True,
    }
    report = {
        "experiment_id": "EXP_7C8A2F11",
        "environment_extension_id": "ENV_4D19B3E7",
        "terminal_status": status,
        "schema_and_completeness_gate": {"gate_result": B.PASS_STATUS},
        "execution_contract_compliance": {
            "used_only_sealed_zip": True,
            "no_web_repository_or_outside_information": True,
            "no_memory_based_reidentification": True,
            "no_target_outcomes_or_post_cutoff_facts": True,
            "party_ids_treated_as_territory_local": True,
            "conditions_treated_identically_and_roles_not_inferred": True,
            "cross_archetype_answer_borrowing": False,
            "retry_schema_invalid_only": True,
            "semantic_feedback_on_retry": False,
            "stopped_before_scoring": True,
            "model": "claude-opus-5",
            "fresh_model_context_per_work_item": fresh,
        },
        "counts": counts,
        "validation": validation,
    }
    manifest = {
        "experiment_id": "EXP_7C8A2F11",
        "environment_extension_id": "ENV_4D19B3E7",
        "generated_by": {
            "model_id": "claude-opus-5",
            "fresh_model_context_per_work_item": fresh,
        },
        "counts": counts,
        "validation": validation,
    }
    return report, manifest


class BaselineProvenanceGateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="atlas_baseline_gate_")
        os.makedirs(os.path.join(self.root, "outputs"))

    def tearDown(self):
        shutil.rmtree(self.root)

    def _write(self, fresh, status):
        report, manifest = _payloads(fresh, status)
        with open(os.path.join(self.root, "outputs", B.TERMINAL_NAME), "w", encoding="utf-8") as fh:
            json.dump(report, fh)
        with open(os.path.join(self.root, "outputs", B.MANIFEST_NAME), "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)

    def test_e0_is_recognized_but_rejected_for_as3_calibration(self):
        self._write(False, B.DEVIATION_STATUS)
        info = B.classify_baseline(self.root)
        self.assertEqual(info["baseline_class"], "E0_DETERMINISTIC_REFERENCE")
        self.assertFalse(info["eligible_for_as3_calibration"])
        with self.assertRaises(ValueError):
            B.require_as2_baseline(self.root)

    def test_true_fresh_context_opus_run_passes_as2_gate(self):
        self._write(True, B.PASS_STATUS)
        info = B.require_as2_baseline(self.root)
        self.assertEqual(info["baseline_class"], "AS2_OPUS5_ISOLATED_FRESH_CONTEXT")
        self.assertTrue(info["eligible_for_as3_calibration"])

    def test_fresh_flag_mismatch_fails_closed(self):
        self._write(True, B.PASS_STATUS)
        path = os.path.join(self.root, "outputs", B.MANIFEST_NAME)
        with open(path, "r", encoding="utf-8") as fh:
            manifest = json.load(fh)
        manifest["generated_by"]["fresh_model_context_per_work_item"] = False
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(manifest, fh)
        info = B.classify_baseline(self.root)
        self.assertEqual(info["baseline_class"], "UNKNOWN_REJECTED")
        self.assertFalse(info["eligible_for_as3_calibration"])
        self.assertTrue(info["errors"])


if __name__ == "__main__":
    unittest.main()
