from __future__ import annotations
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = HERE.parents[3] / "scripts"
sys.path.insert(0, str(SCRIPTS))
sys.path.insert(0, str(HERE))

from main_bridge_alignment import align_election_parties
from main_bridge_core import BridgeError, leak_scan
from main_bridge_overlay import build_overlay
import run_g0_sol_main_bridge as launcher

EID = "E_TEST_ABCDEF"
PIDS = ["P_ALPHA", "P_BETA", "P_GAMMA"]
QIDS = ["Q_01", "Q_02", "Q_03"]
P_TO_Q = {"P_ALPHA": "Q_02", "P_BETA": "Q_03", "P_GAMMA": "Q_01"}


def shares(i: int):
    q1 = 0.20 + i * 0.0001
    q2 = 0.30 - i * 0.00005
    q3 = 1.0 - q1 - q2
    return {"Q_01": q1, "Q_02": q2, "Q_03": q3}


def synthetic_inputs():
    packets = []
    environment = {}
    for i in range(92):
        tid = f"T_{i:03d}"
        qs = shares(i)
        parties = []
        for p in PIDS:
            parties.append({
                "anonymous_party_id": p,
                "baseline_vote_share": qs[P_TO_Q[p]],
                "evidence_completeness": {
                    "allowed_feature_count": 2,
                    "observed_feature_count": 2,
                    "missingness_explicit": True,
                },
                "features": [
                    {
                        "feature_id": "BALLOT_LIST_PRESENT",
                        "status": "VERIFIED",
                        "value": True,
                        "conflict": False,
                        "source_class": "T1",
                        "source_record_ids": [f"SRC_{i:03d}_{p}"],
                    },
                    {
                        "feature_id": "LOCAL_EXECUTIVE_OFFICE",
                        "status": "VERIFIED",
                        "value": p == "P_ALPHA",
                        "conflict": False,
                        "source_class": "T1",
                        "source_record_ids": [f"SRC_LOCAL_{i:03d}_{p}"],
                    },
                ],
            })
        packets.append({
            "anonymous_election_id": EID,
            "anonymous_territory_id": tid,
            "parties": parties,
        })
        environment[f"{EID}|{tid}"] = {
            "anonymous_election_id": EID,
            "anonymous_territory_id": tid,
            "available_party_ids": QIDS,
            "common_territory_card": {
                "previous_election_conditional_party_shares": qs,
            },
            "election_environment_card": {
                "party_offer_cards": [
                    {
                        "anonymous_party_id": q,
                        "government_status": "OPPOSITION" if q != "Q_01" else "GOVERNMENT",
                        "program_priority_levels": {
                            "employment": "HIGH" if q == "Q_02" else "MEDIUM",
                            "public_services": "MEDIUM",
                        },
                    }
                    for q in QIDS
                ]
            },
        }
    return {"anonymous_election_id": EID, "packets": packets}, environment


class MainBridgeTests(unittest.TestCase):
    def test_blind_signature_alignment_is_exact_and_bijective(self):
        blind, environment = synthetic_inputs()
        mapping, audit = align_election_parties(blind, environment)
        self.assertEqual(mapping, P_TO_Q)
        self.assertTrue(audit["bijection"])
        self.assertFalse(audit["identity_information_used"])
        self.assertFalse(audit["target_outcomes_used"])
        self.assertLessEqual(audit["max_abs_error"], 1e-12)

    def test_alignment_fails_closed_on_signature_drift(self):
        blind, environment = synthetic_inputs()
        blind["packets"][0]["parties"][0]["baseline_vote_share"] += 0.01
        with self.assertRaises(BridgeError):
            align_election_parties(blind, environment)

    def test_overlay_contains_anonymous_candidate_and_programme_layers(self):
        blind, environment = synthetic_inputs()
        overlay = build_overlay(
            main_sha="a" * 40,
            blind_bundles=[blind],
            environment=environment,
            source_hashes={"blind.json": "b" * 64},
            controls={"cutoffs": {"contract_id": "TEST", "sha256": "c" * 64}},
        )
        self.assertEqual(overlay["status"], "PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL")
        self.assertEqual(overlay["item_count"], 92)
        self.assertEqual(leak_scan(overlay["items"]), [])
        item = overlay["items"][f"{EID}|T_000"]
        self.assertEqual(len(item["candidate_offer"]["cards"]), 3)
        self.assertEqual(len(item["programme_offer"]["cards"]), 3)
        self.assertRegex(item["candidate_offer"]["cards"][0]["anonymous_candidate_id"], r"^C_[0-9A-F]{16}$")
        self.assertFalse(item["candidate_offer"]["real_names_present"])

    def test_enriched_launcher_rejects_non_pass_bridge(self):
        bad = {
            "bridge_id": "M26_AS_MAIN_BRIDGE_V1",
            "status": "NOT_READY",
            "target_outcomes_present": False,
            "real_identity_material_present": False,
            "floating_main_reads_allowed": False,
            "public_leak_scan": {"status": "PASS"},
            "main_commit_sha": "a" * 40,
            "items": {"E|T": {}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "bridge.json"
            path.write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaises(Exception):
                launcher.load_bridge(path)


if __name__ == "__main__":
    unittest.main()
