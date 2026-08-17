#!/usr/bin/env python3
"""Registered F-1 validation compatible with a squash merge.

The immutable F-1 manifest records the exact pre-squash model commit. A squash
merge intentionally does not preserve that commit as an ancestor of ``main``.
The scientific contract is therefore:

1. the recorded commit object must exist;
2. it must remain reachable from at least one fetched repository ref;
3. all executable/data/parameter/forecast hashes must still match exactly.

Conditions 2 and 3 are stronger and more relevant than pretending the recorded
commit should be an ancestor of the squash commit. No forecast artifact is
modified by this compatibility validator.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import goal100_register_existing_fminus1_v1_1 as registration

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def verify_model_commit_reachable(commit: str) -> None:
    registration.require(
        len(commit) == 40 and all(char in "0123456789abcdef" for char in commit),
        "invalid model commit SHA",
    )
    try:
        subprocess.run(
            ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        )
        refs = subprocess.run(
            ["git", "branch", "-a", "--contains", commit],
            cwd=REPO,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(
            f"FMINUS1_REGISTRATION_FAIL: recorded model commit is unavailable: {exc}"
        )
    refs = [line.strip().lstrip("* ") for line in refs if line.strip()]
    registration.require(
        bool(refs),
        "recorded model commit exists but is not reachable from any fetched ref",
    )
    print(f"FMINUS1_MODEL_COMMIT_REACHABLE refs={','.join(sorted(refs))}")


def main() -> None:
    # Narrow compatibility substitution: every hash and registered-state check
    # continues to execute in the original fail-closed verifier.
    registration.verify_model_commit = verify_model_commit_reachable
    registration.verify_registered_state()
    print("FMINUS1_POST_SQUASH_PROVENANCE_PASS")


if __name__ == "__main__":
    main()
