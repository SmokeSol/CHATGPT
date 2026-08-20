import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
MODULE = HERE.parents[1] / "promote_g0_frontend.py"
SPEC = importlib.util.spec_from_file_location("atlas_g0_promotion", MODULE)
P = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = P
assert SPEC.loader is not None
SPEC.loader.exec_module(P)


class PromotionMathTests(unittest.TestCase):
    def test_hungarian_finds_minimum_assignment(self):
        assignment = P.hungarian([
            [9.0, 1.0, 8.0],
            [2.0, 7.0, 3.0],
            [6.0, 5.0, 1.0],
        ])
        self.assertEqual(assignment, [1, 0, 2])

    def test_party_mapping_recovers_permutation(self):
        e0 = {"Q_01": 0.11, "Q_02": 0.53, "Q_03": 0.36}
        public = {"PAM": 0.36, "RNI": 0.11, "Autres": 0.53}
        mapping, audit = P.party_mapping(e0, public)
        self.assertEqual(mapping, {
            "Q_01": "RNI",
            "Q_02": "Autres",
            "Q_03": "PAM",
        })
        self.assertLess(audit["max_residual"], 1e-12)

    def test_condition_combination_supports_expected_vote_and_mean_probability(self):
        data = {}
        for condition, turnout, p1 in (
            ("C_A", 0.4, 0.2),
            ("C_B", 0.6, 0.4),
        ):
            data[("E", "T", condition)] = P.TerritoryAggregate(
                election_id="E",
                territory_id="T",
                condition_id=condition,
                turnout=turnout,
                expected_vote={"Q_01": p1, "Q_02": 1-p1},
                mean_probability={"Q_01": p1+0.1, "Q_02": 0.9-p1},
                rows=256,
            )
        turnout, shares = P.combine_conditions(data, "average_expected_vote")[("E", "T")]
        self.assertAlmostEqual(turnout, 0.5)
        self.assertAlmostEqual(shares["Q_01"], 0.3)
        turnout2, shares2 = P.combine_conditions(data, "condition0_mean_probability")[("E", "T")]
        self.assertAlmostEqual(turnout2, 0.4)
        self.assertAlmostEqual(shares2["Q_01"], 0.3)

    def test_fingerprint_is_party_label_invariant(self):
        public = P.PublicTerritory(
            year="2016",
            index=0,
            data={
                "slug": "x",
                "turnout_sim": 0.5,
                "simulation": {"A": 0.1, "B": 0.2, "C": 0.7},
            },
        )
        cost = P.fingerprint_cost(
            (0.5, {"Q_01": 0.7, "Q_02": 0.1, "Q_03": 0.2}),
            public,
        )
        self.assertAlmostEqual(cost, 0.0)


if __name__ == "__main__":
    unittest.main()
