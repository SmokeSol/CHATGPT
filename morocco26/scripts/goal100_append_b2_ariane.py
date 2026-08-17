#!/usr/bin/env python3
"""Append the frozen B2 protocol event to FIL_ARIANE.md, idempotently."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
JOURNAL = ROOT / "FIL_ARIANE.md"
EVENT = G100 / "fil_ariane_events" / "A018.json"
MARKER = "Entrée A018 — Gel du protocole B2 non agentique avant collecte"


def main() -> None:
    event = json.loads(EVENT.read_text(encoding="utf-8"))
    text = JOURNAL.read_text(encoding="utf-8")
    if MARKER in text:
        print("B2_ARIANE_ALREADY_PRESENT")
        return

    result = event["machine_result"]
    decisions = "\n".join(f"- {item}" for item in event["anti_drift_decisions"])
    entry = f"""

### 2026-08-17 — {MARKER}

**Question/gate traité :** `{event['gate']}` — {event['question']}

**Hypothèse avant test :** {event['pre_test_hypothesis']}

**Actions et artefacts créés :**

- `data/goal100/b2_protocol_v1.json` ;
- `data/goal100/b2_evidence_schema_v1.json` ;
- `data/goal100/b2_feature_dictionary_v1.json` ;
- `data/goal100/b2_gate_registry.json` ;
- `data/goal100/b2_source_registry.json` ;
- `data/goal100/b2_current_state.json` ;
- `data/goal100/fil_ariane_events/A018.json`.

**Résultat machine :** protocole `{result['protocol_id']}` figé sur le parent `F-1` hashé `{result['parent_forecast_sha256']}`. `B2-0` est `{result['B2_0_status']}` ; collecte autorisée = `{str(result['collection_allowed']).lower()}` ; coefficients prédictifs = `{result['predictive_coefficients']}` ; gates agentiques = `{result['agentic_gates']}`.

**Écarts, échecs ou corrections :** aucun claim politique n’a été collecté avant le gel. Le cutoff final des preuves reste volontairement non fixé : il sera inscrit une seule fois dans le certificat `B2-FROZEN`, sans possibilité de backdating.

**Décisions anti-drift :**

{decisions}

**Décision scientifique :** {event['scientific_decision']}

**Prochaine action exacte :** {event['next_action_exact']}
"""
    JOURNAL.write_text(text + entry, encoding="utf-8")
    print("B2_ARIANE_APPENDED")


if __name__ == "__main__":
    main()
