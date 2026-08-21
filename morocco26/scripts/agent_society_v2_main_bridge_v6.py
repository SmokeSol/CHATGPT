#!/usr/bin/env python3
"""V6 compatibility entry point for the frozen V1 main bridge.

The V5 `main_bridge_overlay.py` contains one lowercase JSON-style literal
(`false`) in two provenance-only booleans. Modifying that frozen source would
invalidate its historical file hash. Python resolves the name at call time, so
this wrapper binds `false = False` in that module and delegates to the unchanged
V1 builder. No data, hash, semantic comparison or model packet is changed.
"""
from __future__ import annotations

import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import main_bridge_overlay  # noqa: E402

# Compatibility binding for the frozen source typo. Deliberately do not edit V5.
main_bridge_overlay.false = False

import agent_society_v2_main_bridge as frozen_v1  # noqa: E402


def main(argv=None) -> int:
    return int(frozen_v1.main(argv))


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except frozen_v1.BridgeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
