from __future__ import annotations
import sys, unittest
from pathlib import Path

_repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_repo))
sys.path.insert(0, str(_repo / "morocco26" / "scripts"))

from morocco26.agent_society_v4.vintage import build_named_vintage
from morocco26.agent_society_v4.vintage_bridge_v7 import (
    CURRENT_VINTAGE, classify_p3_gate, validate_current_vintage_input,
    vintage_to_named_input,
)


def _source():
    return {"source_id": "S1", "tier": "T1", "known_at": "2026-08-21"}


def _option(party, name=None, state="UNKNOWN"):
    named = state not in ("UNKNOWN", "NO_LIST")
    return {
        "party_id": party, "party_name": party,
        "candidate": {
            "status": state,
            "candidate_name": name if named else None,
            "known_at": "2026-08-20" if named else None,
            "sources": [_source()] if state != "UNKNOWN" else [],
            "attributes": {},
            "unknown_reason": "NOT_VERIFIED" if state == "UNKNOWN" else None,
        },
        "program_axes": {}, "program_sources": [],
    }


def _spec():
    return {
        "snapshot_id": "M26_2026-08-22", "as_of": "2026-08-22",
        "source_main_commit": "4df897c356d3f0c36832405c7fcfc7f8f0cd6de2",
        "territories": [{
            "territory_id": "T1", "territory_name": "Territory One",
            "region_id": "R1", "region_name": "Region One",
            "registered_electorate": 1000,
            "ballots": {
                "LOCAL": {"contest_id": "L1", "options": [
                    _option("RNI", "Head RNI", "OFFICIAL"),
                    _option("PAM", "Declared PAM", "DECLARED"),
                    _option("PI", None, "NO_LIST"),
                    _option("USFP", None, "UNKNOWN"),
                ]},
                "REGIONAL": {"contest_id": "R1", "options": [
                    _option("RNI", "Head RNI", "OFFICIAL"),
                    _option("PAM"),
                ]},
            },
        }],
    }


def _named_kwargs():
    return dict(
        parties=[
            {"party_id": "RNI", "party_name": "RNI", "abbreviation": "RNI",
             "party_symbol": "S1", "government_status": "GOVERNMENT"},
            {"party_id": "PAM", "party_name": "PAM", "abbreviation": "PAM",
             "party_symbol": "S2", "government_status": "OPPOSITION"},
            {"party_id": "PI", "party_name": "PI", "abbreviation": "PI",
             "party_symbol": "S3", "government_status": "OPPOSITION"},
            {"party_id": "USFP", "party_name": "USFP", "abbreviation": "USFP",
             "party_symbol": "S4", "government_status": "OPPOSITION"},
        ],
        programmes=[
            {"party_id": "RNI", "axes": {}, "known_as_of": "2026-08-20",
             "source_record_ids": ["VINTAGE_2026-08-22"]},
            {"party_id": "PAM", "axes": {}, "known_as_of": "2026-08-20",
             "source_record_ids": ["VINTAGE_2026-08-22"]},
        ],
        source_records=[],
        voter_population={"known_as_of": "2026-08-22", "batches": [
            {"territory_id": "T1", "batch_id": "B01",
             "voters": [{"weighted_archetype_id": "A001"}]}
        ]},
        conditions=[{"condition_id": "C_TRUE", "description": "true",
                     "known_as_of": "2026-08-22"}],
        national_context={"known_as_of": "2026-08-22",
                          "common_verified_facts": {},
                          "party_specific_material_present": False,
                          "candidate_specific_material_present": False},
    )


class P3GateTests(unittest.TestCase):
    def test_current_vintage_passes_and_final_blocked(self):
        snap = build_named_vintage(_spec())
        gates = classify_p3_gate(snap)
        self.assertEqual(gates["P3_CURRENT_VINTAGE_2026"]["status"], "PASS")
        self.assertEqual(gates["FINAL_BALLOT_2026"]["status"], "BLOCKED_NOT_A_FINAL_BALLOT")

    def test_unknown_cells_counted(self):
        snap = build_named_vintage(_spec())
        gates = classify_p3_gate(snap)
        self.assertGreater(gates["P3_CURRENT_VINTAGE_2026"]["unknown_candidate_cells"], 0)


class VintageToNamedTests(unittest.TestCase):
    def test_all_states_represented(self):
        snap = build_named_vintage(_spec())
        named = vintage_to_named_input(snap, **_named_kwargs())
        states = named["state_census"]
        self.assertIn("OFFICIAL", states)
        self.assertIn("DECLARED", states)
        self.assertIn("UNKNOWN", states)
        self.assertIn("NO_LIST", states)

    def test_unknown_rows_have_no_name(self):
        snap = build_named_vintage(_spec())
        named = vintage_to_named_input(snap, **_named_kwargs())
        for c in named["candidacies"]:
            if c["verification_state"] == "UNKNOWN_AS_OF_SNAPSHOT":
                self.assertIsNone(c["candidate_name"])

    def test_regime_gate_tagged(self):
        snap = build_named_vintage(_spec())
        named = vintage_to_named_input(snap, **_named_kwargs())
        self.assertEqual(named["regime_gate"], CURRENT_VINTAGE)

    def test_validate_relaxed_accepts_partial(self):
        snap = build_named_vintage(_spec())
        named = vintage_to_named_input(snap, **_named_kwargs())
        result = validate_current_vintage_input(named)
        self.assertEqual(result["validation_mode"], CURRENT_VINTAGE)
        self.assertFalse(result["coverage_declared_final"])


if __name__ == "__main__":
    unittest.main()
