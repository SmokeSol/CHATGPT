#!/usr/bin/env python3
"""Bridge the controller-accepted Arabic 92-territory identity layer to TAFRA 2016.

This is identity-only. It does not import 2026 seats, candidates, signals or
forecast information into E_reason. The 2026 Arabic layer supplies only Arabic
territory spellings and a stable French identity label; historical seat counts
and historical constituency IDs come exclusively from the frozen TAFRA-2016
canonical file.
"""
from __future__ import annotations

import html
import json
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
HIST = ROOT / "morocco26/data/goal100/historical/tafra_legislative_2016_canonical.json"
OUT = ROOT / "morocco26/data/goal100/e_reason/evidence/arabic_2016_crosswalk"

# Explicit identity aliases are limited to historical naming/transliteration
# differences observed in the frozen TAFRA-2016 labels. They encode no election
# result, candidate, seat or forecast information. Arabic semantics make the
# direction terms unambiguous: الشمالية=Chamalia/North, الجنوبية=Janoubia/South,
# المحيط=El Mouhit/Ocean. The remaining aliases are spelling variants.
HISTORICAL_IDENTITY_ALIASES = {
    "fes-nord": "Fès-Chamalia",
    "fes-sud": "Fès-Janoubia",
    "karia-ghafsay": "Karia - Rhafsai",
    "rabat-ocean": "Rabat - El Mouhit",
    "medina-sidi-youssef": "Médina - Sidi-Youssef-Ben-Ali",
    "taroudant-sud": "Taroudannt - Al-Janoubia",
    "taroudant-nord": "Taroudannt - Chamalia",
}


def norm_latin(value: str | None) -> str:
    text = html.unescape(value or "")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    text = text.replace("’", " ").replace("'", " ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def load_crosswalk(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    counts = payload.get("counts", {})
    validation = payload.get("validation", {})
    if counts.get("resolved") != 92 or counts.get("canonical_ids") != 92:
        raise RuntimeError("Arabic source crosswalk is not 92/92 resolved")
    if not validation.get("strict_92_to_92_bijection"):
        raise RuntimeError("Arabic source crosswalk lacks strict bijection validation")
    if payload.get("scope") != "IDENTITY_ONLY_NO_FORECAST_EFFECT":
        raise RuntimeError("Arabic source crosswalk scope drift")
    return payload


def historical_rows() -> list[dict[str, Any]]:
    payload = json.loads(HIST.read_text(encoding="utf-8"))
    rows = [r for r in payload["rows"] if r.get("list_type") == "locale"]
    if len(rows) != 92:
        raise RuntimeError(f"expected 92 TAFRA-2016 local rows, got {len(rows)}")
    return rows


def match_one(source: dict[str, Any], rows: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, float, str, float]:
    source_id = str(source.get("constituency_id") or "")
    alias = HISTORICAL_IDENTITY_ALIASES.get(source_id)
    if alias:
        exact_alias = [r for r in rows if norm_latin(r.get("constituency")) == norm_latin(alias)]
        if len(exact_alias) != 1:
            raise RuntimeError(f"audited historical alias {source_id!r}->{alias!r} does not resolve uniquely")
        return exact_alias[0], 1.0, "AUDITED_HISTORICAL_NAMING_ALIAS", 0.0

    key = norm_latin(source.get("name_fr"))
    # Constituency label has priority. A prefecture/province can legitimately
    # contain multiple constituencies (e.g. Kénitra + El-Gharb), so mixing both
    # exact-match sets creates false ambiguity.
    exact_constituency = [r for r in rows if key and key == norm_latin(r.get("constituency"))]
    if len(exact_constituency) == 1:
        return exact_constituency[0], 1.0, "EXACT_NORMALIZED_CONSTITUENCY_IDENTITY", 0.0
    if len(exact_constituency) > 1:
        return None, 1.0, "AMBIGUOUS_EXACT_CONSTITUENCY", 1.0

    exact_prefprov = [r for r in rows if key and key == norm_latin(r.get("prefprov"))]
    if len(exact_prefprov) == 1:
        return exact_prefprov[0], 1.0, "EXACT_UNIQUE_PREFPROV_IDENTITY", 0.0

    best = None
    best_score = -1.0
    second = -1.0
    for r in rows:
        score = max(
            SequenceMatcher(None, key, norm_latin(r.get("constituency"))).ratio(),
            SequenceMatcher(None, key, norm_latin(r.get("prefprov"))).ratio(),
        )
        if score > best_score:
            second = best_score
            best_score = score
            best = r
        elif score > second:
            second = score
    if best is not None and best_score >= 0.88 and best_score - second >= 0.08:
        return best, best_score, "FUZZY_IDENTITY_BRIDGE_CONSERVATIVE", second
    return None, best_score, "UNRESOLVED", second


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: e_reason_bridge_arabic_2016_crosswalk.py <arabic_territory_crosswalk_v1.json>")
    source_path = Path(sys.argv[1]).resolve()
    source = load_crosswalk(source_path)
    rows = historical_rows()

    records = []
    used: dict[str, str] = {}
    for rec in source["records"]:
        hist, score, method, second = match_one(rec, rows)
        out = {
            "name_ar": rec.get("name_ar"),
            "name_ar_source_form": rec.get("name_ar_source_form"),
            "name_ar_match_key": rec.get("name_ar_match_key"),
            "source_2026_constituency_id": rec.get("constituency_id"),
            "source_name_fr": rec.get("name_fr"),
            "resolution_method": method,
            "match_score": round(score, 6),
            "second_score": round(second, 6),
            "historical_id_constituency": hist.get("id_constituency") if hist else None,
            "historical_constituency": hist.get("constituency") if hist else None,
            "historical_prefprov": hist.get("prefprov") if hist else None,
            "historical_region": hist.get("region") if hist else None,
            "historical_seats_2016": hist.get("seats") if hist else None,
            "forecast_effect": "NONE_IDENTITY_ONLY",
        }
        if hist:
            hid = str(hist["id_constituency"])
            if hid in used:
                out["resolution_method"] = "DUPLICATE_HISTORICAL_ID_BLOCKED"
                out["duplicate_with"] = used[hid]
                out["historical_id_constituency"] = None
            else:
                used[hid] = str(rec.get("constituency_id"))
        records.append(out)

    resolved = [r for r in records if r["historical_id_constituency"] is not None]
    unresolved = [r for r in records if r["historical_id_constituency"] is None]
    exact = [r for r in resolved if r["resolution_method"].startswith("EXACT_")]
    fuzzy = [r for r in resolved if r["resolution_method"] == "FUZZY_IDENTITY_BRIDGE_CONSERVATIVE"]
    aliases = [r for r in resolved if r["resolution_method"] == "AUDITED_HISTORICAL_NAMING_ALIAS"]
    historical_ids = {str(r["historical_id_constituency"]) for r in resolved}

    payload = {
        "schema_version": "1.1",
        "artifact_id": "M26-E-REASON-ARABIC-2016-CROSSWALK-BRIDGE-V1",
        "status": "PASS" if len(resolved) == 92 and len(historical_ids) == 92 else "PARTIAL_REQUIRES_AUDIT",
        "purpose": "IDENTITY_ONLY_NO_FORECAST_EFFECT",
        "source_artifact_id": source.get("artifact_id"),
        "source_artifact_status": source.get("status"),
        "source_artifact_scope": source.get("scope"),
        "historical_source": str(HIST.relative_to(ROOT)),
        "historical_identity_aliases": HISTORICAL_IDENTITY_ALIASES,
        "counts": {
            "source_arabic_records": len(records),
            "resolved": len(resolved),
            "exact": len(exact),
            "audited_historical_alias": len(aliases),
            "fuzzy_conservative": len(fuzzy),
            "unresolved": len(unresolved),
            "unique_historical_ids": len(historical_ids),
        },
        "invariants": {
            "imports_2026_seat_magnitude": False,
            "imports_2026_candidates": False,
            "imports_forecast_information": False,
            "historical_seats_from_tafra_2016_only": True,
            "outcomes_unsealed": False,
            "predictive_judgments_generated": False,
            "F1_created": False,
        },
        "unresolved": unresolved,
        "records": records,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "crosswalk.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], **payload["counts"], "unresolved": [{"ar": r["name_ar"], "fr": r["source_name_fr"], "score": r["match_score"]} for r in unresolved]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
