#!/usr/bin/env python3
"""Versioned operational wrapper for the frozen development blind-bundle builder.

The only purpose of this wrapper is to bind two deterministic historical-label aliases
identified by the fail-closed 92/92 territory matching check. It does not read outcomes,
change features, change the C2 prompt, or change scoring.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TARGET = HERE / "e_reason_build_blind_development_bundle.py"
spec = importlib.util.spec_from_file_location("e_reason_blind_builder", TARGET)
if spec is None or spec.loader is None:
    raise SystemExit("cannot load blind development builder")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

mod.ALIASES.update({
    "taroudannt al janoubia": "taroudant sud",
    "taroudannt chamalia": "taroudant nord",
})

if __name__ == "__main__":
    mod.main()
