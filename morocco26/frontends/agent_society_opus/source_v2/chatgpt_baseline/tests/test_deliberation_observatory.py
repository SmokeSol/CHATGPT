import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
MODULE = HERE.parents[1] / "run_deliberation_observatory.py"
SPEC = importlib.util.spec_from_file_location("atlas_deliberation_observatory", MODULE)
O = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = O
assert SPEC.loader is not None
SPEC.loader.exec_module(O)


def synthetic_task():
    parties = ("Q_01", "Q_02", "Q_03")
    voters = []
    decisions = []
    for i in range(32):
        prior = "ABSTAIN" if i % 5 == 0 else ("Q_01" if i % 2 == 0 else "Q_02")
        voter = {
            "weighted_archetype_id": f"A{i+1:03d}",
            "prior_vote_or_abstention": prior,
            "activity_status": "ACTIVE_EMPLOYED",
            "urban_rural": "URBAN",
            "age_band": "25_34",
            "education_level": "Supérieur",
            "latent_national_quintile": 0.6,
            "latent_attitude_economic_condition_mean": 0.4,
            "latent_attitude_government_economic_performance_mean": 0.3,
            "latent_attitude_government_poverty_performance_mean": 0.4,
            "latent_attitude_government_anticorruption_performance_mean": 0.2,
            "latent_attitude_democracy_satisfaction_mean": 0.5,
            "latent_attitude_trust_parliament_mean": 0.4,
        }
        p1 = 0.40 + i / 1000.0
        p2 = 0.39 - i / 2000.0
        p3 = 1.0 - p1 - p2
        decision = {
            "anonymous_election_id": "E_TEST",
            "anonymous_territory_id": "T_TEST",
            "condition_id": "C_12345678",
            "batch_id": "B01",
            "weighted_archetype_id": voter["weighted_archetype_id"],
            "turnout_probability": 0.30 + i / 100.0,
            "conditional_party_probabilities": {
                "Q_01": p1,
                "Q_02": p2,
                "Q_03": p3,
            },
            "factor_importance": {factor: 1.0 / len(O.FACTORS) for factor in O.FACTORS},
            "reason_codes": ["PRIOR_VOTE_INERTIA"],
        }
        voters.append(voter)
        decisions.append(decision)
    context = {
        "anonymous_election_id": "E_TEST",
        "anonymous_territory_id": "T_TEST",
        "condition_id": "C_12345678",
        "available_party_ids": list(parties),
        "common_territory_card": {
            "previous_election_turnout_probability": 0.50,
            "previous_election_conditional_party_shares": {
                "Q_01": 0.40,
                "Q_02": 0.35,
                "Q_03": 0.25,
            },
            "party_context_cards": [
                {
                    "anonymous_party_id": party,
                    "features": [
                        {
                            "feature_id": "CANDIDATE_REGISTERED_RANK",
                            "status": "VERIFIED",
                            "value": 1,
                            "conflict": False,
                        }
                    ],
                }
                for party in parties
            ],
        },
        "election_environment_card": {
            "national_issue_pressures": {"employment_stress": "HIGH"},
            "party_offer_cards": [
                {
                    "anonymous_party_id": party,
                    "government_status": "INCUMBENT_COALITION" if party == "Q_01" else "OPPOSITION",
                    "program_priority_levels": {
                        "employment": "HIGH",
                        "education": "MEDIUM",
                    },
                }
                for party in parties
            ],
        },
    }
    packet = {
        "anonymous_election_id": "E_TEST",
        "anonymous_territory_id": "T_TEST",
        "condition_id": "C_12345678",
        "batch_id": "B01",
        "available_party_ids": list(parties),
        "context": context,
        "voter_batch": {"voter_archetypes": voters},
    }
    task = O.R.FrozenTask(
        task_id="0000__E_TEST__C_12345678__T_TEST__B01",
        packet=packet,
        expected_rows=tuple(voters),
        available_party_ids=parties,
        output_relpath="outputs/E_TEST/C_12345678/T_TEST/B01.jsonl",
        source_paths=("context.json", "batch.json"),
        source_sha256=O.R.sha256_json(packet),
    )
    return task, voters, decisions


class DeliberationObservatoryTests(unittest.TestCase):
    def test_panel_contains_pre_registered_diagnostic_roles(self):
        task, _, decisions = synthetic_task()
        selected = O.select_panel(task, decisions, "panel")
        self.assertTrue(2 <= len(selected) <= 4)
        self.assertIn("SWING", {item.panel for item in selected})
        self.assertIn("TURNOUT_PIVOT", {item.panel for item in selected})
        self.assertEqual(len({item.archetype_id for item in selected}), len(selected))

    def test_all_scope_preserves_original_order(self):
        task, _, decisions = synthetic_task()
        selected = O.select_panel(task, decisions, "all")
        self.assertEqual(len(selected), 32)
        self.assertEqual(selected[0].archetype_id, "A001")
        self.assertEqual(selected[-1].archetype_id, "A032")

    def test_evidence_catalogue_is_closed_unique_and_party_local(self):
        task, voters, decisions = synthetic_task()
        catalogue = O.evidence_catalogue(task, voters[0], decisions[0])
        ids = [item["evidence_id"] for item in catalogue]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertIn("V_PRIOR_VOTE", ids)
        self.assertIn("P_Q_01_GOVERNMENT_STATUS", ids)
        self.assertIn("P_Q_02_GOVERNMENT_STATUS", ids)
        self.assertFalse(any("Q_03_PROGRAM" in value for value in ids))

    def test_counterfactual_program_swap_is_exact_and_identity_preserving(self):
        task, _, decisions = synthetic_task()
        selected = O.select_panel(task, decisions, "panel")[0]
        top, _, runner, _ = O.top_two(selected.decision)
        original = O.task_context(task)
        cf_task, manifest = O.apply_scenario(
            task=task,
            selected=selected,
            scenario="TOP_RUNNER_PROGRAM_SWAP",
        )
        modified = O.task_context(cf_task)
        self.assertEqual(cf_task.election_id, task.election_id)
        self.assertEqual(cf_task.available_party_ids, task.available_party_ids)
        self.assertEqual(
            O.party_offer_lookup(modified)[top]["program_priority_levels"],
            O.party_offer_lookup(original)[runner]["program_priority_levels"],
        )
        self.assertEqual(len(manifest["changes"]), 2)
        self.assertTrue(manifest["synthetic_diagnostic_not_observed_fact"])

    def test_placebo_changes_no_scientific_field(self):
        task, _, decisions = synthetic_task()
        selected = O.select_panel(task, decisions, "panel")[0]
        cf_task, manifest = O.apply_scenario(
            task=task,
            selected=selected,
            scenario="NONINFORMATIVE_METADATA_PLACEBO",
        )
        original = O.task_context(task)
        modified = O.task_context(cf_task)
        diagnostic = modified.pop("diagnostic_metadata")
        self.assertEqual(original, modified)
        self.assertTrue(diagnostic["explicitly_nonpolitical"])
        self.assertEqual(len(manifest["changes"]), 1)

    def test_js_divergence_is_symmetric_and_zero_on_identity(self):
        p = {"Q_01": 0.7, "Q_02": 0.3}
        q = {"Q_01": 0.4, "Q_02": 0.6}
        self.assertAlmostEqual(O.js_divergence(p, p), 0.0, places=12)
        self.assertAlmostEqual(O.js_divergence(p, q), O.js_divergence(q, p), places=12)
        self.assertGreater(O.js_divergence(p, q), 0.0)

    def test_derived_fields_are_deterministic(self):
        task, voters, decisions = synthetic_task()
        derived = O.derived_decision_fields(voters[0], decisions[0])
        self.assertEqual(derived["top_party_id"], "Q_01")
        self.assertEqual(derived["runner_up_party_id"], "Q_02")
        self.assertEqual(derived["transition_type"], "ABSTENTION_CONTINUITY")
        self.assertEqual(derived["decision_certainty_band"], "LOW")
        self.assertRegex(derived["decision_sha256"], r"^[a-f0-9]{64}$")


if __name__ == "__main__":
    unittest.main()
