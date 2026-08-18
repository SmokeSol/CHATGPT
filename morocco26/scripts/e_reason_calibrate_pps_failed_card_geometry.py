#!/usr/bin/env python3
"""Freeze word geometry for PPS pages that could add new >=3-seat districts.

Diagnostic only: no candidate or territory evidence is promoted. The output
retains Arabic word coordinates, font sizes, and gap-split line groups so the
card parser can be revised against observed poster geometry rather than guesses.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import pdfplumber

ROOT = Path(__file__).resolve().parents[2]
ER = ROOT / "morocco26/data/goal100/e_reason"
GAP = ER / "evidence/pps_2016_gap_diagnostic/diagnostic.json"
PTR = ER / "pps_2016_regional_pdf_probe_latest.json"
OUT = ER / "evidence/pps_2016_failed_card_geometry"


def is_arabic(value: object) -> bool:
    return bool(re.search(r"[\u0600-\u06FF]", unicodedata.normalize("NFKC", str(value or ""))))


def logical(value: object) -> str:
    return unicodedata.normalize("NFKC", str(value or ""))[::-1]


def split_by_gap(words: list[dict], gap: float = 22.0) -> list[list[dict]]:
    ordered = sorted(words, key=lambda w: float(w["x0"]))
    groups: list[list[dict]] = []
    for word in ordered:
        if not groups:
            groups.append([word])
            continue
        previous = groups[-1][-1]
        if float(word["x0"]) - float(previous["x1"]) > gap:
            groups.append([word])
        else:
            groups[-1].append(word)
    return groups


def main() -> int:
    gap = json.loads(GAP.read_text(encoding="utf-8"))
    pointer = json.loads(PTR.read_text(encoding="utf-8"))
    probe = json.loads((ROOT / pointer["latest_probe"]).read_text(encoding="utf-8"))
    by_region = {row["region_slug"]: row for row in probe["pdf_hits"]}
    targets = [
        row
        for row in gap["resolved_failure_pages_new_ge3_first"]
        if row.get("new_ge3_district_if_recovered")
    ]
    documents = []
    grouped_targets: dict[str, list[dict]] = defaultdict(list)
    for row in targets:
        grouped_targets[row["region"]].append(row)
    for region, rows in sorted(grouped_targets.items()):
        doc = by_region.get(region)
        if not doc:
            documents.append({"region": region, "error": "REGIONAL_PDF_NOT_FOUND"})
            continue
        path = ROOT / doc["pdf"]["raw_path"]
        with pdfplumber.open(str(path)) as pdf:
            for target in sorted(rows, key=lambda r: r["page"]):
                page_no = int(target["page"])
                page = pdf.pages[page_no - 1]
                words = page.extract_words(
                    use_text_flow=False,
                    keep_blank_chars=False,
                    x_tolerance=1,
                    y_tolerance=1,
                    extra_attrs=["size", "fontname"],
                ) or []
                selected = [
                    w
                    for w in words
                    if is_arabic(w.get("text"))
                    and 0.35 * float(page.height) <= float(w["top"]) <= 0.86 * float(page.height)
                    and float(w.get("size") or 0) >= 8.0
                ]
                top_clusters: list[dict] = []
                for word in sorted(selected, key=lambda w: (float(w["top"]), float(w["x0"]))):
                    cluster = next((c for c in top_clusters if abs(c["top"] - float(word["top"])) <= 2.5), None)
                    if cluster is None:
                        cluster = {"top": float(word["top"]), "words": []}
                        top_clusters.append(cluster)
                    cluster["words"].append(word)
                lines = []
                for cluster in sorted(top_clusters, key=lambda c: c["top"]):
                    groups = []
                    for group in split_by_gap(cluster["words"]):
                        rtl = sorted(group, key=lambda w: -float(w["x0"]))
                        groups.append(
                            {
                                "x0": round(min(float(w["x0"]) for w in group), 2),
                                "x1": round(max(float(w["x1"]) for w in group), 2),
                                "font_sizes": sorted({round(float(w.get("size") or 0), 2) for w in group}, reverse=True),
                                "raw_words_rtl": [w["text"] for w in rtl],
                                "logical_text": " ".join(logical(w["text"]) for w in rtl),
                            }
                        )
                    lines.append(
                        {
                            "top": round(cluster["top"], 2),
                            "top_fraction": round(cluster["top"] / float(page.height), 4),
                            "groups": groups,
                        }
                    )
                documents.append(
                    {
                        "region": region,
                        "page": page_no,
                        "constituency_id": target["constituency_id"],
                        "historical_constituency": target["historical_constituency"],
                        "historical_seats_2016": target["historical_seats_2016"],
                        "page_width": page.width,
                        "page_height": page.height,
                        "parser_cards": target["cards"],
                        "geometry_lines": lines,
                    }
                )
    payload = {
        "schema_version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "target_pages": len(targets),
        "documents": documents,
        "invariants": {
            "candidate_facts_promoted": False,
            "outcomes_unsealed": False,
            "predictive_judgments_generated": False,
            "F1_created": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "calibration.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps([{"region": x.get("region"), "page": x.get("page"), "district": x.get("historical_constituency"), "lines": len(x.get("geometry_lines", []))} for x in documents], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
