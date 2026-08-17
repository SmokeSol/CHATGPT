#!/usr/bin/env python3
"""Pre-execution reviewed ID convention for the Oriental region.

The authoritative French label is ``L'Oriental``. The frozen reviewed-alias table
already names the canonical target ``reg-oriental``. This wrapper makes that
article-independent convention explicit before the first identity-crosswalk run.
All other slug and crosswalk rules are unchanged.
"""
from __future__ import annotations

import goal100_build_b2_identity_crosswalk as engine

ORIGINAL_SLUG = engine.slug


def reviewed_slug(value: object) -> str:
    if engine.normalize_text(value) in {"l oriental", "oriental"}:
        return "oriental"
    return ORIGINAL_SLUG(value)


engine.slug = reviewed_slug


if __name__ == "__main__":
    engine.main()
