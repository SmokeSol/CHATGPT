# -*- coding: utf-8 -*-
import copy
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ENGINE = os.path.join(ROOT, "engine")
if ENGINE not in sys.path:
    sys.path.insert(0, ENGINE)

import build_social_graph as G
import deterministic_social as D
import run_agentic_social as A


def voter(i, employed=True, rural=False, sector="Commerce"):
    return {
        "weighted_archetype_id": "A%03d" % i,
        "age_band": "25_34" if i % 2 else "35_44",
        "age_years": 28 + i * 3,
        "sex": "F" if i % 2 else "M",
        "urban_rural": "RURAL" if rural else "URBAN",
        "education_level": "Secondaire qualifiant" if i % 3 else "Supérieur",
        "activity_status": "ACTIVE_EMPLOYED" if employed else "INACTIVE",
        "latent_national_quintile": 0.2 + 0.12 * i,
        "latent_ses_decile": 0.25 + 0.10 * i,
        "household_type": "Ménage nucléaire - Couple marié avec enfant(s) non marié(s)",
        "household_size": 3 + (i % 3),
        "marital_status": "Marié",
        "industry_sector": sector,
        "professional_status": "Salarié du secteur privé" if employed else None,
        "occupation_group": "5 - Services" if employed else None,
    }


def row(i, p1, turnout):
    return {
        "weighted_archetype_id": "A%03d" % i,
        "turnout_probability": turnout,
        "conditional_party_probabilities": {"Q_01": p1, "Q_02": 1.0 - p1},
        "factor_importance": {"prior_vote_inertia": 0.5},
        "reason_codes": ["PRIOR_VOTE_INERTIA"],
    }


class SocialGraphTests(unittest.TestCase):
    def setUp(self):
        self.voters = [
            voter(1), voter(2), voter(3, sector="Commerce"),
            voter(4, employed=False), voter(5, rural=True), voter(6, rural=True),
        ]

    def test_graph_deterministic_and_valid(self):
        a = G.build_graph(self.voters, "batch", seed="S")
        b = G.build_graph(self.voters, "batch", seed="S")
        self.assertEqual(a, b)
        self.assertEqual(G.validate_graph(a), [])
        for i, node in enumerate(a["nodes"]):
            for rel, edges in node["relations"].items():
                self.assertTrue(all(e["i"] != i for e in edges))
                if edges:
                    self.assertAlmostEqual(sum(e["w"] for e in edges), 1.0, places=8)

    def test_inactive_has_no_workplace_exposure(self):
        g = G.build_graph(self.voters, "batch", seed="S")
        self.assertEqual(g["nodes"][3]["relations"]["work"], [])

    def test_placebo_preserves_outdegree_and_weights(self):
        g = G.build_graph(self.voters, "batch", seed="S")
        p = G.shuffled_placebo(g, seed="P")
        self.assertEqual(G.validate_graph(p), [])
        for a, b in zip(g["nodes"], p["nodes"]):
            for rel in G.RELATIONS:
                self.assertEqual(len(a["relations"][rel]), len(b["relations"][rel]))
                self.assertEqual(
                    [x["w"] for x in a["relations"][rel]],
                    [x["w"] for x in b["relations"][rel]],
                )


class DeterministicInfluenceTests(unittest.TestCase):
    def test_zero_lambda_identity_exact_on_decisions(self):
        voters = [voter(1), voter(2), voter(3)]
        g = G.build_graph(voters, "batch", seed="S")
        rows = [row(1, .8, .7), row(2, .2, .3), row(3, .55, .52)]
        out = D.run_condition(
            rows, g, "ALL_R2",
            {"family": 0.0, "work": 0.0, "neighborhood": 0.0},
        )
        self.assertEqual(D.max_decision_delta(rows, out), 0.0)

    def test_updates_are_synchronous(self):
        # A hand graph where each node sees only the other.
        g = {
            "nodes": [
                {"id": "A001", "relations": {
                    "family": [{"i": 1, "w": 1.0}], "work": [], "neighborhood": []}},
                {"id": "A002", "relations": {
                    "family": [{"i": 0, "w": 1.0}], "work": [], "neighborhood": []}},
            ]
        }
        rows = [row(1, .9, .8), row(2, .1, .2)]
        out = D.update_round(rows, g, {"family": .4, "work": 0, "neighborhood": 0}, "R1")
        self.assertAlmostEqual(
            out[0]["conditional_party_probabilities"]["Q_01"],
            1.0 - out[1]["conditional_party_probabilities"]["Q_01"],
            places=12,
        )
        self.assertAlmostEqual(out[0]["turnout_probability"],
                               1.0 - out[1]["turnout_probability"], places=12)

    def test_probabilities_remain_normalized(self):
        voters = [voter(1), voter(2), voter(3)]
        g = G.build_graph(voters, "batch", seed="S")
        rows = [row(1, .95, .85), row(2, .05, .2), row(3, .5, .5)]
        out = D.run_condition(
            rows, g, "ALL_R2",
            {"family": .2, "work": .12, "neighborhood": .08},
        )
        for r in out:
            self.assertAlmostEqual(sum(r["conditional_party_probabilities"].values()), 1.0, places=12)
            self.assertGreaterEqual(r["turnout_probability"], 0.0)
            self.assertLessEqual(r["turnout_probability"], 1.0)


class AgenticBoundsTests(unittest.TestCase):
    def test_agentic_adjustment_is_clipped_and_bounded(self):
        r = row(1, .6, .55)
        response = {
            "social_response": "ADOPT",
            "turnout_delta_logit": 99,
            "party_logit_adjustments": {"Q_01": -99, "Q_02": 99},
            "relation_reliance": {"family": 2, "work": -2, "neighborhood": .5},
            "reason_codes": ["FAMILY_ALIGNMENT", "NOT_ALLOWED"],
        }
        out = A.apply_adjustment(
            r, response, {"family": .2, "work": .1, "neighborhood": .05}, "R1"
        )
        self.assertAlmostEqual(sum(out["conditional_party_probabilities"].values()), 1.0, places=12)
        clean = out["agentic_social_influence"]["validated_response"]
        self.assertLessEqual(clean["turnout_delta_logit"], .75)
        self.assertEqual(clean["reason_codes"], ["FAMILY_ALIGNMENT"])
        self.assertEqual(clean["relation_reliance"]["family"], 1.0)
        self.assertEqual(clean["relation_reliance"]["work"], 0.0)


if __name__ == "__main__":
    unittest.main()
