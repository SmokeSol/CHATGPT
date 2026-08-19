#!/usr/bin/env python3
"""Fail-closed consistency checks for MOROCCO//26 handover documentation/state."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
LAB = G100 / "forecast_lab"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"HANDOVER_FAIL: {message}")


def load_json(path: Path) -> dict:
    require(path.exists(), f"missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def text(path: Path) -> str:
    require(path.exists(), f"missing {path.relative_to(REPO)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    manifest = load_json(G100 / "handover_manifest_v1.json")
    state = load_json(LAB / "probabilistic_forecast_2026_state_v4.json")

    require(manifest.get("handover_id") == "M26-HANDOVER-V1", "handover id drift")
    require(manifest.get("canonical_integration_branch") == "main", "canonical branch must be main")

    for relative in manifest.get("read_order", []):
        require((REPO / relative).exists(), f"read-order target missing: {relative}")

    active = manifest.get("active_forecast", {})
    require(active.get("forecast_id") == "M26-PROBABILISTIC-FORECAST-2026-V1", "active forecast id drift")
    require(active.get("status") == "PROMOTED", "active forecast not promoted")
    require(active.get("national_model") == "PREVIOUS_NATIONAL_PERSISTENCE", "national winner drift")
    require(active.get("territorial_model") == "HALF_SHRINK", "territorial winner drift")
    require(float(active.get("lambda")) == 0.5, "lambda drift")
    require(int(active.get("draws")) == 50_000, "draw count drift")
    require(int(active.get("house_seats_every_draw")) == 395, "house seat invariant drift")

    state_gate = state.get("gates", {}).get("probabilistic_forecast_2026", {})
    final_gate = state.get("gates", {}).get("final_50000_simulations", {})
    national_gate = state.get("gates", {}).get("current_national_2026_point", {})
    territorial_gate = state.get("gates", {}).get("rolling_origin_territorial_model", {})
    require(state_gate.get("status") == "PROMOTED", "V4 machine state not promoted")
    require(final_gate.get("status") == "PASS", "final 50k machine gate not PASS")
    require(final_gate.get("draws") == 50_000, "machine-state draw count drift")
    require(final_gate.get("exact_seats_every_draw") == 395, "machine-state 395-seat invariant drift")
    require(national_gate.get("model") == "PREVIOUS_NATIONAL_PERSISTENCE", "machine-state national model drift")
    require(territorial_gate.get("winner") == "HALF_SHRINK", "machine-state territorial winner drift")
    require(float(territorial_gate.get("lambda")) == 0.5, "machine-state lambda drift")

    require(active.get("seat_stream_sha256") == final_gate.get("seat_stream_sha256"), "seat-stream hash mismatch")
    require(active.get("generated_json_sha256") == final_gate.get("generated_json_sha256"), "forecast JSON hash mismatch")

    agents = text(REPO / "AGENTS.md")
    handover = text(ROOT / "HANDOVER.md")
    current = text(ROOT / "CURRENT_STATE.md")
    status = text(ROOT / "STATUS.md")
    north_star = text(ROOT / "docs" / "FORECAST_NORTH_STAR.md")
    reproducibility = text(ROOT / "docs" / "REPRODUCIBILITY.md")
    anti_drift = text(ROOT / "docs" / "ANTI_DRIFT.md")
    tracker = text(ROOT / "reports" / "GOAL100_TRACKER.md")
    phase2 = text(ROOT / "docs" / "PHASE2_ARCHITECTURE.md")
    society = text(ROOT / "docs" / "AGENTSOCIETY2_RUNBOOK.md")

    require("LIVE_2026_UPDATE_RUNBOOK.md" in agents, "AGENTS.md does not point to live update runbook")
    require("CURRENT_STATE.md" in handover, "handover does not point to current state")
    require("M26-PROBABILISTIC-FORECAST-2026-V1" in current, "current state missing active forecast id")
    require("probabilistic_forecast_2026_state_v4.json" in status, "STATUS missing V4 authority")
    require("PROMOTED" in status, "STATUS does not identify promoted forecast")

    stale_active_phrases = (
        "2007 is blocked",
        "national forecast remains blocked",
        "The first calibrated forecast remains blocked",
    )
    for name, body in {
        "FORECAST_NORTH_STAR.md": north_star,
        "REPRODUCIBILITY.md": reproducibility,
        "ANTI_DRIFT.md": anti_drift,
    }.items():
        for phrase in stale_active_phrases:
            require(phrase not in body, f"stale active-state phrase in {name}: {phrase}")

    require("HISTORICAL" in tracker[:1200].upper(), "GOAL100 tracker is not clearly marked historical/current-pointer")
    require("HISTORICAL ARCHIVE" in phase2[:400].upper(), "Phase-2 architecture not marked historical archive")
    require("HISTORICAL ARCHIVE" in society[:400].upper(), "AgentSociety2 runbook not marked historical archive")

    live_policy = manifest.get("live_2026_policy", {})
    require(live_policy.get("predictive_updates_require_historical_admission") is True, "predictive admission guard disabled")
    require(live_policy.get("frozen_snapshots_may_be_overwritten") is False, "snapshot immutability guard disabled")
    require(live_policy.get("unknown_may_be_zeroed") is False, "UNKNOWN zeroing guard disabled")

    print(
        "HANDOVER_PASS="
        + json.dumps(
            {
                "handover_id": manifest["handover_id"],
                "active_forecast": active["forecast_id"],
                "status": state_gate["status"],
                "draws": final_gate["draws"],
                "seats_every_draw": final_gate["exact_seats_every_draw"],
                "canonical_branch": manifest["canonical_integration_branch"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
