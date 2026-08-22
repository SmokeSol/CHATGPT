from __future__ import annotations
import unittest

from main_bridge_alignment_v2 import (
    ALIGNMENT_TOLERANCE, AMBIGUITY_MARGIN, align_territory_parties,
)


def packet(shares: dict[str, float]):
    return {
        "anonymous_election_id": "E_X",
        "anonymous_territory_id": "T_1",
        "parties": [
            {"anonymous_party_id": p, "baseline_vote_share": v}
            for p, v in shares.items()
        ],
    }


def env_packet(shares: dict[str, float]):
    return {
        "available_party_ids": sorted(shares),
        "common_territory_card": {
            "previous_election_conditional_party_shares": dict(shares),
        },
    }


P = {"P_A": 0.30, "P_B": 0.50, "P_C": 0.20}
Q = {"Q_1": 0.50, "Q_2": 0.20, "Q_3": 0.30}


class TerritoryAlignmentTests(unittest.TestCase):
    def test_finds_unique_optimal_mapping(self):
        mapping, audit = align_territory_parties(packet(P), env_packet(Q))
        self.assertEqual(mapping["P_A"], "Q_3")
        self.assertEqual(mapping["P_B"], "Q_1")
        self.assertEqual(mapping["P_C"], "Q_2")
        self.assertLess(audit["max_abs_error"], 1e-12)
        self.assertTrue(audit["bijection"])
        self.assertFalse(audit["identity_information_used"])
        self.assertFalse(audit["target_outcomes_used"])

    def test_permuted_env_labels_still_resolve(self):
        shuffled = {"Q_2": 0.30, "Q_3": 0.50, "Q_1": 0.20}
        mapping, audit = align_territory_parties(packet(P), env_packet(shuffled))
        self.assertEqual(mapping["P_A"], "Q_2")
        self.assertEqual(mapping["P_B"], "Q_3")
        self.assertEqual(mapping["P_C"], "Q_1")

    def test_error_above_tolerance_fails_closed(self):
        bad = {"Q_1": 0.90, "Q_2": 0.05, "Q_3": 0.05}
        with self.assertRaises(Exception):
            align_territory_parties(packet(P), env_packet(bad))

    def test_panel_size_mismatch_fails(self):
        small = {"Q_1": 0.5, "Q_2": 0.5}
        with self.assertRaises(Exception):
            align_territory_parties(packet(P), env_packet(small))

    def test_available_party_ids_enforced(self):
        env = env_packet(Q)
        env["available_party_ids"] = ["Q_1", "Q_2", "Q_9"]
        with self.assertRaises(Exception):
            align_territory_parties(packet(P), env)

    def test_tie_is_rejected_as_ambiguous(self):
        # symmetric shares make at least two mappings equally good
        sym_p = {"P_A": 1 / 3, "P_B": 1 / 3, "P_C": 1 / 3}
        sym_q = {"Q_1": 1 / 3, "Q_2": 1 / 3, "Q_3": 1 / 3}
        with self.assertRaises(Exception):
            align_territory_parties(
                packet(sym_p), env_packet(sym_q),
                tolerance=ALIGNMENT_TOLERANCE, ambiguity_margin=AMBIGUITY_MARGIN,
            )

    def test_mapping_digest_is_deterministic(self):
        m1, a1 = align_territory_parties(packet(P), env_packet(Q))
        m2, a2 = align_territory_parties(packet(P), env_packet(Q))
        self.assertEqual(a1["mapping_sha256"], a2["mapping_sha256"])


if __name__ == "__main__":
    unittest.main()
