#!/usr/bin/env python3
"""Append the post-squash provenance correction to FIL_ARIANE.md."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENT = ROOT / "data" / "goal100" / "fil_ariane_events" / "A019.json"
JOURNAL = ROOT / "FIL_ARIANE.md"
MARKER = "Entrée A019 — Correction du validateur de provenance après squash"


def main() -> None:
    event = json.loads(EVENT.read_text(encoding="utf-8"))
    text = JOURNAL.read_text(encoding="utf-8")
    if MARKER in text:
        print("B2_A019_ALREADY_PRESENT")
        return
    invariants = "\n".join(f"- {item}" for item in event["invariants_preserved"])
    entry = f"""

### 2026-08-17 — {MARKER}

**Question/gate traité :** pourquoi le workflow B2 `{event['failed_run']}` a-t-il échoué après que `B2_PROTOCOL_PASS` a été obtenu ?

**Hypothèse avant test :** l’échec vient d’une règle d’intégration devenue fausse après le squash de la PR #8, et non d’une divergence des artefacts F-1.

**Résultat machine :** `{event['failure']}`

**Correction :** {event['correction']}

**Impact scientifique :** `{event['scientific_impact']}`. Forecast modifié = `{str(event['forecast_changed']).lower()}` ; protocole modifié = `{str(event['protocol_changed']).lower()}` ; seuil modifié = `{str(event['threshold_changed']).lower()}`.

**Invariants conservés :**

{invariants}

**Décision scientifique :** correction d’ingénierie versionnée. Le validateur d’origine conserve tous les checks de hashes ; seule la condition d’ascendance, inapplicable après squash, est remplacée par existence + reachability dans une ref récupérée.

**Prochaine action exacte :** {event['next_action_exact']}
"""
    JOURNAL.write_text(text + entry, encoding="utf-8")
    print("B2_A019_APPENDED")


if __name__ == "__main__":
    main()
