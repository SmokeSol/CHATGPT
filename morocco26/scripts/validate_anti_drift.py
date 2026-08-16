#!/usr/bin/env python3
"""Machine-checkable anti-drift guard for MOROCCO//26.

No third-party dependencies. Intended for local runs and GitHub Actions.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONSTITUTION = ROOT / "data" / "project_constitution.json"
CURRENT = ROOT / "data" / "current_phase.json"
MANIFEST = ROOT / "data" / "experiment_manifest.json"


def load(path: Path):
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def fail(errors: list[str], message: str) -> None:
    errors.append(message)


def main() -> int:
    errors: list[str] = []
    for p in (CONSTITUTION, CURRENT, MANIFEST):
        if not p.exists():
            fail(errors, f"missing required anti-drift artifact: {p.relative_to(ROOT)}")
    if errors:
        print("ANTI_DRIFT_FAIL")
        print("\n".join(f"- {e}" for e in errors))
        return 1

    c = load(CONSTITUTION)
    s = load(CURRENT)
    m = load(MANIFEST)

    # North star cannot silently mutate between the project constitution and experiment protocol.
    if c.get("north_star") != m.get("north_star"):
        fail(errors, "north_star mismatch between project_constitution.json and experiment_manifest.json")

    weights = c.get("priority_weights", {})
    if abs(sum(float(v) for v in weights.values()) - 1.0) > 1e-9:
        fail(errors, "priority_weights must sum to 1.0")
    if float(weights.get("morocco_2026_political_understanding", 0)) < 0.70:
        fail(errors, "political-understanding weight cannot fall below 70% without explicit constitution amendment")

    phases = c.get("phase_map", [])
    if not phases:
        fail(errors, "phase_map is empty")
    else:
        expected_start = 0
        ids = set()
        for phase in phases:
            pid = phase.get("id")
            if pid in ids:
                fail(errors, f"duplicate phase id: {pid}")
            ids.add(pid)
            rng = phase.get("range_percent", [])
            if len(rng) != 2 or rng[0] != expected_start or rng[1] <= rng[0]:
                fail(errors, f"non-contiguous or invalid phase range for {pid}: {rng}")
                break
            expected_start = rng[1]
        if expected_start != 100:
            fail(errors, f"phase map must terminate at 100%, got {expected_start}")
        if s.get("formal_phase") not in ids:
            fail(errors, f"unknown formal_phase: {s.get('formal_phase')}")
        if s.get("experimental_frontier") not in ids:
            fail(errors, f"unknown experimental_frontier: {s.get('experimental_frontier')}")

    impl = s.get("implementation_completion_percent")
    gated = s.get("scientifically_gated_completion_percent")
    if not isinstance(impl, (int, float)) or not 0 <= impl <= 100:
        fail(errors, "implementation_completion_percent must be in [0,100]")
    if not isinstance(gated, (int, float)) or not 0 <= gated <= 100:
        fail(errors, "scientifically_gated_completion_percent must be in [0,100]")
    if isinstance(impl, (int, float)) and isinstance(gated, (int, float)) and gated > impl:
        fail(errors, "scientifically gated completion cannot exceed implementation completion")

    if s.get("forecast_status") != "BLOCKED":
        missing = set(c.get("forecast_unlock_gate", {}).get("required", []))
        completed = set(s.get("completed", []))
        # This intentionally requires explicit completion strings for every unlock item.
        if not missing.issubset(completed):
            fail(errors, "forecast status was unlocked before all constitution forecast gates were explicitly completed")

    safety = m.get("safety_boundary", {})
    for key in ("political_message_generation", "voter_microtargeting", "real_personal_data", "party_strategy_recommendations"):
        if safety.get(key) is not False:
            fail(errors, f"safety boundary drift: {key} must remain false")

    kill = m.get("protocol", {}).get("kill_criteria", [])
    if not any("LLM layer" in x or "D does not beat B and C" in x for x in kill):
        fail(errors, "Model D must retain an explicit kill criterion versus B and C")
    if not any("Never publish a national 2026 forecast" in x for x in kill):
        fail(errors, "forecast boundary kill criterion missing from experiment manifest")

    non_goals = set(c.get("non_goals", []))
    required_non_goals = {
        "building a generic election dashboard",
        "tuning synthetic parameters until dramatic political effects appear",
        "treating LLM narrative richness as evidence",
        "political persuasion optimization",
        "voter microtargeting",
    }
    missing_ng = sorted(required_non_goals - non_goals)
    if missing_ng:
        fail(errors, "missing mandatory non-goals: " + ", ".join(missing_ng))

    if errors:
        print("ANTI_DRIFT_FAIL")
        print("\n".join(f"- {e}" for e in errors))
        return 1

    print("ANTI_DRIFT_PASS")
    print(f"north_star={c['north_star']}")
    print(f"formal_phase={s['formal_phase']}")
    print(f"implementation_completion={s['implementation_completion_percent']}%")
    print(f"scientifically_gated_completion={s['scientifically_gated_completion_percent']}%")
    print(f"forecast_status={s['forecast_status']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
