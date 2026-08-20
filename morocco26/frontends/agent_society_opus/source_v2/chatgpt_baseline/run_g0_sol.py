#!/usr/bin/env python3
"""Canonical G0 decision entry point: enforce GPT-5.6 Sol + medium effort."""
from __future__ import annotations
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import run_chatgpt_baseline as runner

FROZEN_MODEL = "gpt-5.6-sol"
FROZEN_REASONING = "medium"


def main(argv=None):
    args = list(sys.argv[1:] if argv is None else argv)
    for forbidden in ("--model", "--reasoning"):
        if forbidden in args or any(value.startswith(forbidden + "=") for value in args):
            raise runner.RunnerError(
                f"{forbidden} is frozen by run_g0_sol.py; use {FROZEN_MODEL}/{FROZEN_REASONING}"
            )
    return runner.main(args + ["--model", FROZEN_MODEL, "--reasoning", FROZEN_REASONING])


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except runner.RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
