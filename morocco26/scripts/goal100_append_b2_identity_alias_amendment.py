#!/usr/bin/env python3
"""Append the exact Dakhla alias amendment to FIL_ARIANE.md."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT = ROOT / "data" / "goal100" / "fil_ariane_events" / "A022.json"
JOURNAL = ROOT / "FIL_ARIANE.md"
MARKER = "Entrée A022 — Amendement exact de l’alias régional Dakhla"


def main() -> None:
    event = json.loads(EVENT.read_text(encoding="utf-8"))
    text = JOURNAL.read_text(encoding="utf-8")
    if MARKER in text:
        print("B2_A022_ALREADY_PRESENT")
        return
    failure = event["observed_failure"]
    amendment = event["amendment"]
    text += f"""

### 2026-08-17 — {MARKER}

**Question/gate traité :** corriger l’unique classe d’échec du run `{event['failed_run']}` sans introduire de fuzzy matching.

**Échec conservé :** crosswalk canonique `{event['failed_crosswalk_canonical_sha256']}` au commit `{event['failed_commit']}`. Les deux échecs sont `{failure['class']}` pour `{failure['source_label']}` dans `{failure['contexts']}` ; l’intitulé officiel cible est `{failure['authoritative_label']}`.

**Amendement preregistré :** protocole `{amendment['protocol_id']}` ; alias normalisé exact `{amendment['normalized_alias']}` → `{amendment['canonical_target_id']}` ; portée `{amendment['scope']}`.

**Impact scientifique :** `{event['scientific_impact']}`. Forecast modifié = `{str(event['forecast_changed']).lower()}` ; claims B2 modifiés = `{str(event['B2_claims_changed']).lower()}` ; dictionnaire de features modifié = `{str(event['feature_dictionary_changed']).lower()}` ; coefficient modifié = `{str(event['coefficient_changed']).lower()}` ; seuil modifié = `{str(event['threshold_changed']).lower()}` ; fuzzy matching activé = `{str(event['fuzzy_matching_enabled']).lower()}`.

**Préservation :** {event['preservation']}

**Prochaine action exacte :** {event['next_action_exact']}
"""
    JOURNAL.write_text(text, encoding="utf-8")
    print("B2_A022_APPENDED")


if __name__ == "__main__":
    main()
