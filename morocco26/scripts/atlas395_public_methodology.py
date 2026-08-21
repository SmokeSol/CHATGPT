#!/usr/bin/env python3
"""Regenerate the public methodology compatibility view for Atlas 395.

The daily pipeline rebuilds ``morocco26/web/data`` from the registered scientific
snapshot.  The reader historically consumes ``public_methodology.json`` while
newer code can also consume ``methodology_state.json``.  This adapter keeps the
public contract stable without mutating scientific artifacts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

M26 = Path(__file__).resolve().parents[1]
DEFAULT_DATA = M26 / "web" / "data"


def load(path: Path, optional: bool = False) -> dict[str, Any]:
    if optional and not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build(data_dir: Path) -> Path:
    methodology = load(data_dir / "methodology_state.json")
    evidence = load(data_dir / "evidence_index.json", optional=True)
    snapshot = methodology.get("snapshot") or {}
    geometry = snapshot.get("geometry") or {}

    forecast_change = evidence.get("forecast_change")
    projection_changed = forecast_change not in (None, "", "NONE")

    payload = {
        "product": "ATLAS 395",
        "public_methodology": {
            "reference_status": "Enregistrée" if snapshot.get("status") == "FROZEN" else snapshot.get("status"),
            "reference_date": snapshot.get("created_at"),
            "data_cutoff": snapshot.get("data_cutoff"),
            "draws": snapshot.get("draws"),
            "total_seats": geometry.get("total_seats", 395),
            "local_constituencies": geometry.get("local_constituencies", 92),
            "regional_constituencies": geometry.get("regional_constituencies", 12),
            "manual_party_bonus": 0,
            "polls_used_in_current_projection": False,
            "old_versions_rewritten": False,
            "missing_data_forced_to_zero": False,
            "same_rules_for_all_parties": True,
            "uncertainty_published": True,
            "post_election_scoring_planned": True,
        },
        "current_public_interpretation": {
            "projection_changed_by_new_2026_facts": projection_changed,
            "reason_fr": (
                "Une nouvelle version chiffrée de la projection est publiée."
                if projection_changed
                else "Les informations nouvelles de 2026 sont documentées séparément de leur éventuel effet électoral. À ce stade, aucune information nouvelle n'a satisfait l'ensemble des conditions requises pour justifier une modification chiffrée de la projection de référence."
            ),
            "integration_rule_fr": "Une information ne modifie la projection que si sa provenance, son rattachement territorial et son effet quantifiable peuvent être établis selon des règles identiques pour toutes les forces politiques.",
        },
        "source_principles": {
            "institutional_sources": "Sources de référence pour les règles du scrutin, les décisions officielles et les faits relevant d'une autorité publique.",
            "party_official_sources": "Sources utilisées pour documenter les annonces officielles des partis, sans les assimiler à une corroboration indépendante.",
            "authorized_media": "Médias24 est utilisé pour la veille et la corroboration ; une publication médiatique ne modifie jamais, à elle seule, la projection.",
            "party_neutrality": "Les mêmes critères de provenance, de date, de rattachement territorial et de vérification s'appliquent à toutes les forces politiques.",
        },
        "evaluation_framework": {
            "principle_fr": "La qualité de la projection sera évaluée après le scrutin à partir des résultats effectivement observés, en conservant l'intégralité des versions publiées avant le vote.",
            "dimensions": [
                "calibration des probabilités",
                "précision territoriale",
                "écart sur les sièges par parti",
                "couverture des intervalles d'incertitude",
            ],
        },
    }

    out = data_dir / "public_methodology.json"
    dump(out, payload)
    print(f"ATLAS395_PUBLIC_METHODOLOGY_OK output={out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    args = parser.parse_args()
    build(args.data_dir)


if __name__ == "__main__":
    main()
