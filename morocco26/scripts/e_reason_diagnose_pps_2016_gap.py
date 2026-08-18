#!/usr/bin/env python3
"""Summarize the remaining PPS-2016 parsing gap without promoting evidence.

This diagnostic is deliberately downstream of the fail-closed parser. It
quantifies the PJD+PPS union, classifies excluded PPS pages, and computes
same-region Arabic header similarity candidates for audit. Similarity output is
never promoted automatically and has no forecast effect.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
PPS = ER / "evidence/pps_2016_parsed_missing_slates/parsed_missing_slates.json"
PJD = ER / "evidence/pjd_2016_valid_subset_summary/summary.json"
CROSS = ER / "evidence/arabic_2016_crosswalk/crosswalk.json"
OUT = ER / "evidence/pps_2016_gap_diagnostic"


def clean(value: object) -> str:
    return " ".join(str(value or "").replace("\n", " ").split())


def norm_ar(value: object) -> str:
    text = unicodedata.normalize("NFKC", html.unescape(clean(value))).replace("ـ", "")
    text = text.translate(str.maketrans({"ی": "ي", "ى": "ي", "ک": "ك", "ۀ": "ة", "ہ": "ه"}))
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"[^\u0600-\u06FF0-9]+", " ", text)
    return " ".join(text.split())


def compact(value: object) -> str:
    return norm_ar(value).replace(" ", "")


def norm_latin(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = "".join(c for c in text if not unicodedata.combining(c)).casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", text).split())


def main() -> int:
    pps = json.loads(PPS.read_text(encoding="utf-8"))
    pjd = json.loads(PJD.read_text(encoding="utf-8"))
    cross = json.loads(CROSS.read_text(encoding="utf-8"))
    by_cid = {r["source_2026_constituency_id"]: r for r in cross["records"]}

    pjd_ge3 = {r["constituency_id"] for r in pjd["districts"] if r["at_least_three"]}
    pps_ge3 = {
        cid
        for cid, names in _candidate_names_by_district(pps).items()
        if len(names) >= 3
    }
    union_ge3 = pjd_ge3 | pps_ge3

    failures = []
    unresolved = []
    error_counter: Counter[str] = Counter()
    method_counter: Counter[str] = Counter()
    for row in pps.get("page_diagnostics", []):
        if row.get("status") in {"SKIP_HEADER_TERRITORY_NOT_UNIQUE", "SKIP_TERRITORY_NOT_UNIQUE"}:
            unresolved.append(_diagnose_unresolved(row, by_cid))
            continue
        errors = list(row.get("errors") or [])
        if not errors:
            continue
        for error in errors:
            error_counter[error.split("_row", 1)[0].split("_r", 1)[0]] += 1
        cards = []
        for card in row.get("cards", []):
            method = str(card.get("method") or "NONE")
            method_counter[method] += 1
            detail = card.get("detail") or {}
            cards.append(
                {
                    "row": card.get("row"),
                    "bin_from_left": card.get("bin_from_left"),
                    "first_line_top": card.get("first_line_top"),
                    "method": method,
                    "candidate_name_ar": card.get("candidate_name_ar"),
                    "raw_words": detail.get("raw_words"),
                    "anchors": detail.get("anchors"),
                    "line_candidates": detail.get("line_candidates"),
                    "guess": detail.get("guess"),
                }
            )
        cid = row.get("constituency_id")
        meta = by_cid.get(cid, {})
        failures.append(
            {
                "region": row.get("region"),
                "page": row.get("page"),
                "constituency_id": cid,
                "historical_constituency": row.get("historical_constituency"),
                "historical_seats_2016": int(row.get("seats") or meta.get("historical_seats_2016") or 0),
                "already_passes_via_pjd": cid in pjd_ge3,
                "new_ge3_district_if_recovered": bool(cid and int(row.get("seats") or 0) >= 3 and cid not in pjd_ge3),
                "resolved_card_names": sum(bool(c.get("candidate_name_ar")) for c in row.get("cards", [])),
                "errors": errors,
                "header_lines": row.get("header_lines"),
                "matched_header_pattern": row.get("matched_header_pattern"),
                "cards": cards,
            }
        )

    high_header = [
        r
        for r in unresolved
        if r.get("best_score", 0) >= 0.78 and r.get("score_margin", 0) >= 0.06
    ]
    potential_failures = [r for r in failures if r["new_ge3_district_if_recovered"]]

    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_parser_schema": pps.get("schema_version"),
        "current": {
            "pjd_ge3_districts": len(pjd_ge3),
            "pps_ge3_districts": len(pps_ge3),
            "union_ge3_districts": len(union_ge3),
            "required_ge3_districts": 70,
            "remaining_ge3_districts": max(0, 70 - len(union_ge3)),
            "pps_success_territories": len(pps.get("territory_rows", [])),
            "pps_failure_pages": len(failures),
            "pps_unresolved_header_pages": len(unresolved),
            "resolved_failure_pages_that_would_add_new_ge3": len(potential_failures),
            "high_similarity_unresolved_headers_for_audit": len(high_header),
        },
        "error_counts": dict(error_counter.most_common()),
        "card_method_counts_on_failed_pages": dict(method_counter.most_common()),
        "resolved_failure_pages_new_ge3_first": sorted(
            failures,
            key=lambda r: (
                not r["new_ge3_district_if_recovered"],
                r["already_passes_via_pjd"],
                -(r["resolved_card_names"] or 0),
                r["region"] or "",
                r["page"] or 0,
            ),
        ),
        "unresolved_header_pages_high_score_first": sorted(
            unresolved,
            key=lambda r: (-(r.get("best_score") or 0), -(r.get("score_margin") or 0), r.get("region") or "", r.get("page") or 0),
        ),
        "invariants": {
            "similarity_promotes_evidence": False,
            "candidate_facts_generated": False,
            "outcomes_unsealed": False,
            "predictive_judgments_generated": False,
            "F1_created": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "diagnostic.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"current": payload["current"], "error_counts": payload["error_counts"], "top_unresolved": payload["unresolved_header_pages_high_score_first"][:12]}, ensure_ascii=False, indent=2))
    return 0


def _candidate_names_by_district(payload: dict) -> dict[str, set[str]]:
    out: dict[str, set[str]] = defaultdict(set)
    for row in payload.get("candidate_rows", []):
        cid = row.get("constituency_id")
        name = row.get("candidate_name_ar_normalized")
        if cid and name:
            out[cid].add(name)
    return out


def _diagnose_unresolved(row: dict, by_cid: dict[str, dict]) -> dict:
    region = row.get("region")
    header_lines = [norm_ar(x) for x in (row.get("header_lines") or []) if norm_ar(x)]
    candidates = []
    for cid, meta in by_cid.items():
        if norm_latin(meta.get("historical_region")) != _region_norm(region):
            continue
        variants = {
            norm_ar(meta.get("name_ar")),
            norm_ar(meta.get("name_ar_source_form")),
            norm_ar(meta.get("name_ar_match_key")),
        }
        variants = {v for v in variants if v}
        best = 0.0
        best_pair = None
        for line in header_lines:
            for variant in variants:
                score = max(
                    SequenceMatcher(None, compact(line), compact(variant)).ratio(),
                    SequenceMatcher(None, norm_ar(line), norm_ar(variant)).ratio(),
                )
                if score > best:
                    best = score
                    best_pair = {"header_line": line, "variant": variant}
        candidates.append(
            {
                "constituency_id": cid,
                "historical_constituency": meta.get("historical_constituency"),
                "historical_seats_2016": int(meta.get("historical_seats_2016") or 0),
                "score": round(best, 6),
                "best_pair": best_pair,
            }
        )
    candidates.sort(key=lambda x: -x["score"])
    best_score = candidates[0]["score"] if candidates else 0.0
    second_score = candidates[1]["score"] if len(candidates) > 1 else 0.0
    return {
        "region": region,
        "page": row.get("page"),
        "header_lines": header_lines,
        "best_hits_from_parser": row.get("best_hits"),
        "best_score": best_score,
        "second_score": second_score,
        "score_margin": round(best_score - second_score, 6),
        "top_candidates": candidates[:5],
    }


def _region_norm(region_slug: object) -> str:
    mapping = {
        "casablanca-settat": "casablanca settat",
        "souss-massa": "souss massa",
        "oriental": "oriental",
        "beni-mellal-khenifra": "beni mellal khenifra",
        "rabat-sale-kenitra": "rabat sale kenitra",
        "marrakech-safi": "marrakech safi",
        "fes-meknes": "fes meknes",
        "tanger-tetouan-al-hoceima": "tanger tetouan al hoceima",
        "draa-tafilalet": "draa tafilalet",
        "guelmim-oued-noun": "guelmim oued noun",
        "laayoune-sakia-el-hamra": "laayoune sakia el hamra",
        "dakhla-oued-ed-dahab": "dakhla oued ed dahab",
    }
    return mapping.get(str(region_slug or ""), str(region_slug or ""))


if __name__ == "__main__":
    raise SystemExit(main())
