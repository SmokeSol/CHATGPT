#!/usr/bin/env python3
"""Ensure a failed B2 identity gate is append-only recorded in FIL_ARIANE.md."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
CERT = G100 / "b2_identity_territory_certificate.json"
JOURNAL = ROOT / "FIL_ARIANE.md"


def main() -> None:
    if not CERT.exists():
        print("B2_IDENTITY_CERTIFICATE_NOT_CREATED")
        return
    certificate = json.loads(CERT.read_text(encoding="utf-8"))
    if certificate.get("gate") == "PASS":
        print("B2_IDENTITY_PASS_ALREADY_JOURNALED")
        return
    run_id = os.environ.get("GITHUB_RUN_ID", "LOCAL")
    event_id = f"A021F{run_id}"
    marker = f"Entrée {event_id} — Échec du crosswalk identité-territoire B2"
    text = JOURNAL.read_text(encoding="utf-8")
    if marker in text:
        print("B2_IDENTITY_FAILURE_ALREADY_JOURNALED")
        return
    failures = certificate.get("failures", [])
    failure_lines = "\n".join(f"- `{item.get('kind', 'UNKNOWN')}` — `{json.dumps(item, ensure_ascii=False)}`" for item in failures[:50])
    text += f"""

### {certificate.get('certified_at', '')[:10]} — {marker}

**Question/gate traité :** `B2-2-IDENTITY-TERRITORY-CROSSWALK`.

**Résultat machine :** `FAIL`. Territoires locaux `{certificate.get('local_territories')}`, régions `{certificate.get('regional_territories')}`, élus `{certificate.get('elected_member_rows')}`, fuzzy matches `{certificate.get('unreviewed_fuzzy_matches')}`, claims B2 préexistants `{certificate.get('B2_claim_records_before_certificate')}`.

**Classes d’échec :**

{failure_lines or '- Certificat absent de détails.'}

**Décision scientifique :** le gate reste `OPEN`. Aucun fallback fuzzy, aucune fusion d’homonyme et aucun record candidat 2026 n’est admis.

**Prochaine action exacte :** corriger uniquement les inputs ou aliases explicitement défaillants sous une nouvelle version revue, sans diminuer les critères de couverture.
"""
    JOURNAL.write_text(text, encoding="utf-8")
    print("B2_IDENTITY_FAILURE_JOURNALED")


if __name__ == "__main__":
    main()
