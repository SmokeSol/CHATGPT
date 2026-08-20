import importlib.util
import pathlib
import sys
import unittest

HERE = pathlib.Path(__file__).resolve()
MODULE = HERE.parents[1] / "run_deliberation_observatory.py"
SPEC = importlib.util.spec_from_file_location("atlas_deliberation_observatory_sentinels", MODULE)
O = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = O
assert SPEC.loader is not None
SPEC.loader.exec_module(O)


class EvidenceSentinelTests(unittest.TestCase):
    def test_missing_and_ambiguous_values_are_never_directional(self):
        for value in (
            "MISSING",
            "UNKNOWN",
            "AMBIGUOUS",
            "UNVERIFIED",
            "NOT_FOUND",
            "DATA_BLOCKED",
        ):
            catalogue = []
            O.add_evidence(
                catalogue,
                "E_TEST",
                "other_verified_context",
                "TEST",
                "field",
                value,
                directional=True,
            )
            self.assertEqual(len(catalogue), 1)
            self.assertFalse(catalogue[0]["directional"], value)

    def test_verified_numeric_value_can_remain_directional(self):
        catalogue = []
        O.add_evidence(
            catalogue,
            "E_TEST",
            "personal_economic_conditions",
            "VOTER",
            "economic_condition",
            0.42,
            status="VERIFIED",
            directional=True,
        )
        self.assertTrue(catalogue[0]["directional"])

    def test_unknown_status_overrides_numeric_value(self):
        catalogue = []
        O.add_evidence(
            catalogue,
            "E_TEST",
            "local_candidate_context",
            "PARTY",
            "candidate_rank",
            1,
            status="UNKNOWN",
            directional=True,
        )
        self.assertFalse(catalogue[0]["directional"])


if __name__ == "__main__":
    unittest.main()
