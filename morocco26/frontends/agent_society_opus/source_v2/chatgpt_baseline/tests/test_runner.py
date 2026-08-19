import importlib.util
import json
import pathlib
import sys
import tempfile
import unittest

HERE = pathlib.Path(__file__).resolve()
MODULE = HERE.parents[1] / "run_chatgpt_baseline.py"
SPEC = importlib.util.spec_from_file_location("atlas_chatgpt_runner", MODULE)
R = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = R
assert SPEC.loader is not None
SPEC.loader.exec_module(R)


def schema():
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "anonymous_election_id",
            "anonymous_territory_id",
            "condition_id",
            "batch_id",
            "weighted_archetype_id",
            "turnout_probability",
            "conditional_party_probabilities",
            "factor_importance",
            "reason_codes",
        ],
        "properties": {
            "anonymous_election_id": {"type": "string"},
            "anonymous_territory_id": {"type": "string"},
            "condition_id": {"type": "string"},
            "batch_id": {"type": "string"},
            "weighted_archetype_id": {"type": "string"},
            "turnout_probability": {"type": "number"},
            "conditional_party_probabilities": {
                "type": "object",
                "additionalProperties": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "factor_importance": {
                "type": "object",
                "additionalProperties": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1,
                },
            },
            "reason_codes": {
                "type": "array",
                "minItems": 1,
                "maxItems": 4,
                "uniqueItems": True,
                "items": {"enum": ["A", "B"]},
            },
        },
    }


def task(count=32):
    voters = tuple(
        {"weighted_archetype_id": f"A{i:03d}"} for i in range(count)
    )
    packet = {
        "anonymous_election_id": "E_X",
        "anonymous_territory_id": "T_X",
        "condition_id": "C_ABCDEF12",
        "batch_id": "B01",
        "available_party_ids": ["Q_01", "Q_02"],
        "voter_archetypes": list(voters),
    }
    return R.FrozenTask(
        task_id="E_X__C_ABCDEF12__T_X__B01",
        packet=packet,
        expected_rows=voters,
        available_party_ids=("Q_01", "Q_02"),
        output_relpath="outputs/test.jsonl",
        source_paths=("packet.json",),
        source_sha256=R.sha256_json(packet),
    )


def rows(count=32):
    factors = {name: 1 / len(R.FACTORS) for name in R.FACTORS}
    return [
        {
            "anonymous_election_id": "E_X",
            "anonymous_territory_id": "T_X",
            "condition_id": "C_ABCDEF12",
            "batch_id": "B01",
            "weighted_archetype_id": f"A{i:03d}",
            "turnout_probability": 0.5,
            "conditional_party_probabilities": {"Q_01": 0.4, "Q_02": 0.6},
            "factor_importance": factors,
            "reason_codes": ["A"],
        }
        for i in range(count)
    ]


class RunnerContractTests(unittest.TestCase):
    def test_task_specific_structured_output_schema(self):
        wrapped = R.wrapper_schema(schema(), task())
        item = wrapped["properties"]["rows"]["items"]
        party = item["properties"]["conditional_party_probabilities"]
        factor = item["properties"]["factor_importance"]
        self.assertEqual(set(party["required"]), {"Q_01", "Q_02"})
        self.assertFalse(party["additionalProperties"])
        self.assertEqual(set(factor["required"]), set(R.FACTORS))
        self.assertFalse(factor["additionalProperties"])
        self.assertEqual(
            item["properties"]["condition_id"]["enum"], ["C_ABCDEF12"]
        )

    def test_valid_rows_pass(self):
        self.assertEqual(len(R.validate_rows({"rows": rows()}, task(), schema())), 32)

    def test_archetype_order_fails_closed(self):
        value = rows()
        value[0]["weighted_archetype_id"] = "A031"
        with self.assertRaises(R.ValidationError):
            R.validate_rows({"rows": value}, task(), schema())

    def test_packet_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            path = root / "packets" / "E_X" / "C_ABCDEF12" / "T_X"
            path.mkdir(parents=True)
            (path / "B01.json").write_text(
                json.dumps(task().packet), encoding="utf-8"
            )
            discovered, mode = R.discover_tasks(root)
            self.assertEqual(mode, "PACKETS")
            self.assertEqual(len(discovered), 1)
            self.assertEqual(len(discovered[0].expected_rows), 32)


if __name__ == "__main__":
    unittest.main()
