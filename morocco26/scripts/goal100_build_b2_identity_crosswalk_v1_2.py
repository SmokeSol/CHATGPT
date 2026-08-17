#!/usr/bin/env python3
"""Execute B2 identity protocol V1.1 after preserving the failed V1 attempt."""
from __future__ import annotations

import json

import goal100_build_b2_identity_crosswalk as engine

PROTOCOL_V1_1 = engine.G100 / "b2_identity_protocol_v1_1.json"
ORIGINAL_SLUG = engine.slug


def reviewed_slug(value: object) -> str:
    if engine.normalize_text(value) in {"l oriental", "oriental"}:
        return "oriental"
    return ORIGINAL_SLUG(value)


def main() -> None:
    engine.PROTOCOL_PATH = PROTOCOL_V1_1
    engine.slug = reviewed_slug
    crosswalk, certificate = engine.build_crosswalk()
    crosswalk["crosswalk_id"] = "M26-GOAL100-B2-IDENTITY-CROSSWALK-V1.1"
    certificate["certificate_id"] = "M26-GOAL100-B2-IDENTITY-TERRITORY-CERTIFICATE-V1.1"

    # Recompute after the versioned identity has been made explicit.
    payload = dict(crosswalk)
    payload.pop("canonical_crosswalk_sha256", None)
    crosswalk_hash = engine.canonical_sha256(payload)
    crosswalk["canonical_crosswalk_sha256"] = crosswalk_hash
    certificate["crosswalk_sha256"] = crosswalk_hash

    engine.dump(engine.CROSSWALK_PATH, crosswalk)
    engine.dump(engine.CERTIFICATE_PATH, certificate)
    engine.append_event_and_transition(certificate)
    print("B2_IDENTITY_TERRITORY_PASS" if certificate["gate"] == "PASS" else "B2_IDENTITY_TERRITORY_FAIL")
    print(json.dumps(certificate, ensure_ascii=False, indent=2))
    raise SystemExit(0 if certificate["gate"] == "PASS" else 3)


if __name__ == "__main__":
    main()
