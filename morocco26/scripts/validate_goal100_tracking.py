#!/usr/bin/env python3
"""Stable Goal100 registered-state validation entry point."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
F0 = ROOT / "data" / "goal100" / "forecasts" / "F0" / "forecast.json"

if F0.exists():
    from validate_b2_post_f0 import main
else:
    from validate_registered_fminus1_post_squash import main

if __name__ == "__main__":
    main()
