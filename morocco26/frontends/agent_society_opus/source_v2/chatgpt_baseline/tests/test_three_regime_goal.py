from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import tempfile
import unittest


import os
import shutil
import uuid
import contextlib


@contextlib.contextmanager
def plain_temp_dir():
    base = os.environ.get("TEMP") or os.environ.get("TMP") or "."
    path = os.path.join(base, "test_" + uuid.uuid4().hex)
    os.mkdir(path)
    try:
        yield path
    finally:
        shutil.rmtree(path, ignore_errors=True)

HERE = pathlib.Path(__file__).resolve()
REPO_ROOT = HERE.parents[6]
SCRIPTS = REPO_ROOT / "morocco26" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import three_regime_core as C


def synthetic_context() -> C.ContextRecord:
    parties = ("Q_01", "Q_02")
    local = []
    programmes = []
    for party in parties:
        local.append(
            {
                "anonymous_party_id": party,
                "features": [
                    {
                        "feature_id": feature_id,
                        "status": "VERIFIED",
                        "value": bool(index % 2),
                        "conflict": False,
                    }
                    for index, feature_id in enumerate(C.CANONICAL_CANDIDATE_FEATURES)
                ],
            }
        )
        programmes.append(
            {
                "anonymous_party_id": party,
                "government_status": "OPPOSITION",
                "program_priority_levels": {
                    axis_id: "HIGH" if index % 2 else "MEDIUM"
                    for index, axis_id in enumerate(C.CANONICAL_PROGRAMME_AXES)
                },
            }
        )
    value = {
        "anonymous_election_id": "E_ABCDEF0123456789",
        "anonymous_territory_id": "T_ABCDEF0123456789",
        "condition_id": "C_12345678",
        "available_party_ids": list(parties),
        "common_territory_card": {"party_context_cards": local},
        "election_environment_card": {"party_offer_cards": programmes},
    }
    return C.ContextRecord(
        path=pathlib.Path("context.json"),
        raw_sha256=C.sha256_json(value),
        election_id=value["anonymous_election_id"],
        territory_id=value["anonymous_territory_id"],
        condition_id=value["condition_id"],
        context=value,
    )


def initialize_git_repo(root: pathlib.Path, certificate: dict, roster: dict) -> str:
    path = root / "morocco26" / "data" / "goal100"
    path.mkdir(parents=True)
    (path / "b2_2026_ballot_certificate.json").write_text(json.dumps(certificate), encoding="utf-8")
    (path / "b2_2026_ballot_roster.json").write_text(json.dumps(roster), encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.email", "test@example.com"], check=True)
    subprocess.run(["git", "-C", str(root), "config", "user.name", "Test"], check=True)
    subprocess.run(["git", "-C", str(root), "add", "."], check=True)
    subprocess.run(["git", "-C", str(root), "commit", "-qm", "fixture"], check=True)
    return subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()


def named_input() -> dict:
    territories = [
        {
            "territory_id": f"T{i:03d}",
            "territory_name": f"Territory {i}",
            "ballot_party_ids": ["P1", "P2"],
            "verified_context": {},
        }
        for i in range(92)
    ]
    parties = [
        {
            "party_id": "P1",
            "party_name": "Party One",
            "abbreviation": "P1",
            "party_symbol": "S1",
            "government_status": "GOVERNMENT",
            "national_leader_name": "Leader One",
            "national_salience": "HIGH",
        },
        {
            "party_id": "P2",
            "party_name": "Party Two",
            "abbreviation": "P2",
            "party_symbol": "S2",
            "government_status": "OPPOSITION",
            "national_leader_name": "Leader Two",
            "national_salience": "HIGH",
        },
    ]
    sources = [
        {
            "source_record_id": "S1",
            "source_class": "T0",
            "independence_cluster": "OFFICIAL_ELECTION_AUTHORITY",
            "known_as_of": "2026-08-01",
            "sha256": "1" * 64,
        },
        {
            "source_record_id": "S2",
            "source_class": "T1_INDEPENDENT",
            "independence_cluster": "INDEPENDENT_PARTY_SOURCE",
            "known_as_of": "2026-08-01",
            "sha256": "2" * 64,
        },
    ]
    candidacies = []
    batches = []
    for territory in territories:
        tid = territory["territory_id"]
        for party in parties:
            candidacies.append(
                {
                    "territory_id": tid,
                    "party_id": party["party_id"],
                    "candidate_id": f"{tid}_{party['party_id']}",
                    "candidate_name": f"Candidate {tid} {party['party_id']}",
                    "verification_state": "VERIFIED_DOUBLE_ENTRY",
                    "known_as_of": "2026-08-01",
                    "source_record_ids": ["S1", "S2"],
                    "public_familiarity_band": "MEDIUM",
                    "local_viability_band": "COMPETITIVE",
                    "verified_profile": {
                        "profession": {
                            "verification_state": "VERIFIED",
                            "value": "Engineer",
                            "salience_rank": 1,
                            "source_record_ids": ["S1", "S2"],
                        }
                    },
                }
            )
        batches.append(
            {
                "territory_id": tid,
                "batch_id": "B01",
                "voters": [
                    {
                        "weighted_archetype_id": f"A_{tid}",
                        "prior_vote_or_abstention": "P1",
                        "latent_attitude_political_discussion_mean": 0.7,
                    }
                ],
            }
        )
    programmes = [
        {
            "party_id": party["party_id"],
            "known_as_of": "2026-08-01",
            "source_record_ids": ["S1"],
            "axes": {
                axis_id: {
                    "level": "HIGH",
                    "verification_state": "PUBLISHED_PARTY_PROGRAMME",
                    "national_salience_rank": index,
                }
                for index, axis_id in enumerate(C.CANONICAL_PROGRAMME_AXES)
            },
        }
        for party in parties
    ]
    return {
        "schema_version": "1.0",
        "artifact_id": "NAMED_FIXTURE",
        "main_commit_sha": C.REGISTERED_MAIN_SHA,
        "snapshot_known_as_of": "2026-08-01",
        "national_context": {
            "known_as_of": "2026-08-01",
            "common_verified_facts": {"salient_issue": "employment"},
            "party_specific_material_present": False,
            "candidate_specific_material_present": False,
        },
        "territories": territories,
        "parties": parties,
        "candidacies": candidacies,
        "programmes": programmes,
        "source_records": sources,
        "voter_population": {
            "artifact_id": "VOTERS_FIXTURE",
            "known_as_of": "2026-08-01",
            "batches": batches,
        },
        "conditions": [{
            "condition_id": "CURRENT_INFO",
            "description": "current information",
            "known_as_of": "2026-08-01",
        }],
        "coverage": {
            "all_intended_ballot_cells_verified": True,
            "intended_ballot_cells": 184,
        },
    }


class HistoricalContractTests(unittest.TestCase):
    def test_pointer_only_contract_has_expected_shape(self):
        contract = C.build_pointer_only_historical_contract(synthetic_context())
        C.validate_historical_contract(contract, strict_shape=True)
        self.assertFalse(contract["model_packet_mutated"])
        self.assertFalse(contract["model_packet_values_duplicated"])
        self.assertEqual(len(contract["cards"]), 2)
        self.assertNotIn("program_priority_levels", contract["cards"][0])
        self.assertNotIn("features", contract["cards"][0])

    def test_semantic_hash_changes_without_copying_value(self):
        record = synthetic_context()
        first = C.build_pointer_only_historical_contract(record)
        modified = json.loads(json.dumps(record.context))
        modified["election_environment_card"]["party_offer_cards"][0]["program_priority_levels"][C.CANONICAL_PROGRAMME_AXES[0]] = "LOW"
        second_record = C.ContextRecord(
            path=record.path,
            raw_sha256=C.sha256_json(modified),
            election_id=record.election_id,
            territory_id=record.territory_id,
            condition_id=record.condition_id,
            context=modified,
        )
        second = C.build_pointer_only_historical_contract(second_record)
        self.assertNotEqual(
            first["cards"][0]["programme_semantic_sha256"],
            second["cards"][0]["programme_semantic_sha256"],
        )
        self.assertNotIn("LOW", json.dumps(second["cards"][0]))

    def test_historical_leak_scan_rejects_real_year(self):
        contract = C.build_pointer_only_historical_contract(synthetic_context())
        contract["reading_instruction"] += " 2021"
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_historical_contract(contract, strict_shape=True)


class InformationDietTests(unittest.TestCase):
    def test_diet_is_deterministic(self):
        voter = {
            "prior_vote_or_abstention": "P1",
            "latent_attitude_political_discussion_mean": 0.61,
            "age_band": "65+",
            "sex": "F",
            "income": 1,
        }
        self.assertEqual(C.information_diet(voter), C.information_diet(voter))
        self.assertEqual(C.information_diet(voter)["level"], "HIGH")
        self.assertEqual(C.information_diet(voter)["protected_or_demographic_fields_used"], [])

    def test_protected_fields_do_not_change_diet(self):
        base = {
            "prior_vote_or_abstention": "ABSTAIN",
            "latent_attitude_political_discussion_mean": 0.45,
        }
        one = dict(base, sex="F", age_band="18_24", religion="X")
        two = dict(base, sex="M", age_band="65+", religion="Y")
        self.assertEqual(C.information_diet(one), C.information_diet(two))


class NamedReadinessTests(unittest.TestCase):
    def test_current_style_fail_certificate_blocks_named_mode(self):
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp)
            certificate = {
                "gate": "FAIL",
                "territory_coverage_fraction": 0.0,
                "verified_double_entry_rows": 0,
                "certified_local_constituencies": 92,
                "parties_covered": ["PJD"],
                "ambiguous_deterministic_match_rows": 92,
                "blocked_source_documents": 10,
                "failures": [{"kind": "NO_ROW_SATISFIES_CRITICAL_DOUBLE_ENTRY"}],
            }
            roster = {"artifact_id": "ROSTER", "rows": [{"row_index": i} for i in range(92)]}
            sha = initialize_git_repo(root, certificate, roster)
            status = C.named_2026_readiness(root, sha)
            self.assertEqual(status["status"], "BLOCKED_NAMED_2026_INCOMPLETE_ROSTER")
            self.assertFalse(status["ready_to_generate_named_packets"])
            self.assertIn("verified_candidate_rows_present", status["blockers"])

    def test_complete_named_input_validates(self):
        result = C.validate_named_input(named_input())
        self.assertEqual(result["status"], "PASS_NAMED_2026_INPUT_READY")
        self.assertEqual(result["territories"], 92)
        self.assertEqual(result["verified_candidacies"], 184)

    def test_named_input_rejects_single_source_candidate(self):
        value = named_input()
        value["candidacies"][0]["source_record_ids"] = ["S1"]
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_named_input(value)

    def test_named_input_rejects_same_cluster_double_count(self):
        value = named_input()
        value["source_records"][1]["independence_cluster"] = value["source_records"][0]["independence_cluster"]
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_named_input(value)

    def test_named_input_rejects_future_source(self):
        value = named_input()
        value["source_records"][0]["known_as_of"] = "2026-08-02"
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_named_input(value)

    def test_named_input_rejects_uncovered_local_ballot_cell(self):
        value = named_input()
        value["candidacies"] = value["candidacies"][:-1]
        value["coverage"]["intended_ballot_cells"] -= 1
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_named_input(value)

    def test_named_input_rejects_pre_election_outcome_field(self):
        value = named_input()
        value["national_context"]["common_verified_facts"]["winner"] = "P1"
        with self.assertRaises(C.ThreeRegimeError):
            C.validate_named_input(value)

    def test_named_environment_uses_local_ballot_panel(self):
        value = named_input()
        value["parties"].append({
            "party_id": "P3",
            "party_name": "Party Three",
            "abbreviation": "P3",
            "party_symbol": "S3",
            "government_status": "OPPOSITION",
            "national_leader_name": "Leader Three",
            "national_salience": "LOW",
        })
        value["programmes"].append({
            "party_id": "P3",
            "known_as_of": "2026-08-01",
            "source_record_ids": ["S1"],
            "axes": {
                axis_id: {
                    "level": "MEDIUM",
                    "verification_state": "PUBLISHED_PARTY_PROGRAMME",
                    "national_salience_rank": index,
                }
                for index, axis_id in enumerate(C.CANONICAL_PROGRAMME_AXES)
            },
        })
        territory = value["territories"][0]
        territory["ballot_party_ids"].append("P3")
        value["candidacies"].append({
            "territory_id": territory["territory_id"],
            "party_id": "P3",
            "candidate_id": "T000_P3",
            "candidate_name": "Candidate T000 P3",
            "verification_state": "VERIFIED_DOUBLE_ENTRY",
            "known_as_of": "2026-08-01",
            "source_record_ids": ["S1", "S2"],
            "public_familiarity_band": "LOW",
            "local_viability_band": "MINOR",
            "verified_profile": {},
        })
        value["coverage"]["intended_ballot_cells"] += 1
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp) / "named"
            C.build_named_environment(value, root)
            first = json.loads(next((root / "packets" / "CURRENT_INFO" / "T000").glob("*.json")).read_text())
            second = json.loads(next((root / "packets" / "CURRENT_INFO" / "T001").glob("*.json")).read_text())
            self.assertEqual(first["available_party_ids"], ["P1", "P2", "P3"])
            self.assertEqual(second["available_party_ids"], ["P1", "P2"])

    def test_pseudonymized_twin_removes_real_labels_and_preserves_counts(self):
        value = named_input()
        twin = C.pseudonymize_named_input(value)
        self.assertEqual(twin["regime"], C.REGIME_NAMED_TWIN)
        self.assertNotIn("party_name", twin["parties"][0])
        self.assertNotIn("candidate_name", twin["candidacies"][0])
        self.assertEqual(len(twin["candidacies"]), len(value["candidacies"]))
        self.assertTrue(twin["voter_population"]["batches"][0]["territory_id"].startswith("TERR_"))
        serialized = json.dumps(twin, ensure_ascii=False)
        self.assertNotIn("Party One", serialized)
        self.assertNotIn("Candidate T000 P1", serialized)
        self.assertNotIn('"S1"', serialized)

    def test_named_environment_builds_information_diets(self):
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp) / "named"
            manifest = C.build_named_environment(named_input(), root)
            self.assertEqual(manifest["status"], "PASS_REALISTIC_2026_NAMED_ENVIRONMENT_READY")
            self.assertEqual(manifest["work_items"], 92)
            packet = next((root / "packets").rglob("*.json"))
            data = json.loads(packet.read_text())
            voter = data["voter_batch"]["voter_archetypes"][0]
            self.assertEqual(voter["information_diet"]["level"], "HIGH")
            self.assertEqual(len(voter["known_electoral_surface"]["ballot_cards"]), 2)
            self.assertFalse(voter["known_electoral_surface"]["provenance_identifiers_visible_to_model"])
            self.assertNotIn(
                "source_record_ids",
                json.dumps(voter["known_electoral_surface"], ensure_ascii=False),
            )


class BlindControlPairingTests(unittest.TestCase):
    def _write_run(self, root: pathlib.Path, *, extra_output: bool = False) -> None:
        state = {
            "target_outcomes_opened": False,
            "auth_mode": "CHATGPT_MANAGED_CODEX_LOGIN",
            "api_key_used": False,
            "model": C.FROZEN_MODEL,
        }
        (root / "run_state.json").parent.mkdir(parents=True, exist_ok=True)
        (root / "run_state.json").write_text(json.dumps(state), encoding="utf-8")
        rows = [
            {
                "anonymous_election_id": "E_ABCDEF0123456789",
                "anonymous_territory_id": C.BLIND_CONTROL_TERRITORY,
                "condition_id": "C_12345678",
                "batch_id": C.BLIND_CONTROL_BATCH,
                "weighted_archetype_id": f"A{index:03d}",
            }
            for index in range(1, 33)
        ]
        output = root / "outputs" / "E" / "C" / "T" / "B01.jsonl"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
        if extra_output:
            other = root / "outputs" / "E" / "C2" / "T" / "B01.jsonl"
            other.parent.mkdir(parents=True, exist_ok=True)
            other.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")

    def test_exact_raw_control_generates_exact_task_regex(self):
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp)
            self._write_run(root)
            result = C.inspect_blind_control_run(root)
            self.assertEqual(result["status"], "PASS_P0_RAW_D0_EXACT_WORK_ITEM_BOUND")
            self.assertEqual(result["rows"], 32)
            self.assertIn(C.BLIND_CONTROL_TERRITORY, result["task_regex"])

    def test_raw_control_rejects_multiple_work_items(self):
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp)
            self._write_run(root, extra_output=True)
            with self.assertRaises(C.ThreeRegimeError):
                C.inspect_blind_control_run(root)


class FreezeTests(unittest.TestCase):
    def test_freeze_manifest_verifier(self):
        with plain_temp_dir() as tmp:
            root = pathlib.Path(tmp)
            target = root / "a.txt"
            target.write_text("x", encoding="utf-8")
            manifest = root / "freeze.json"
            manifest.write_text(
                json.dumps(
                    {
                        "parent_branch_head": C.REGISTERED_BRANCH_HEAD,
                        "registered_main_sha": C.REGISTERED_MAIN_SHA,
                        "frozen_files": {"a.txt": C.sha256_file(target)},
                    }
                ),
                encoding="utf-8",
            )
            result = C.verify_freeze_manifest(root, manifest)
            self.assertEqual(result["status"], "PASS_THREE_REGIME_FREEZE_VERIFIED")

    def test_primary_regimes_are_exactly_three(self):
        self.assertEqual(
            C.PRIMARY_REGIMES,
            (C.REGIME_BLIND, C.REGIME_HISTORICAL, C.REGIME_NAMED),
        )
        self.assertNotIn(C.REGIME_NAMED_TWIN, C.PRIMARY_REGIMES)


if __name__ == "__main__":
    unittest.main()
