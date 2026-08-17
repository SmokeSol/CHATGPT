#!/usr/bin/env python3
"""Build the Arabic-native Atlas V1 identity and candidate layer.

This is an E_collect/product artifact builder, not a forecast updater. It:
- maps the exact 92 Arabic PJD constituency strings to the exact 92 frozen Atlas IDs;
- validates a one-to-one bijection against the canonical 92-seat geometry;
- carries the official-party Arabic list-agent names into a bilingual roster;
- enriches the public Médias24 2026 candidate dataset by canonical territory ID;
- emits a consolidated Atlas V1 evidence snapshot while keeping F0 immutable.
"""
from __future__ import annotations

import csv
import hashlib
import html
import json
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
M26 = ROOT / "morocco26"
G100 = M26 / "data" / "goal100"
E_ROOT = G100 / "e_collect"
ATLAS_ROOT = M26 / "data" / "atlas_v1"
WEB_DATA_ROOT = M26 / "web" / "data"

F0_PATH = G100 / "forecasts" / "F0" / "forecast.json"
B2_ROSTER_PATH = G100 / "b2_2026_ballot_roster.json"
CANONICAL_PATH = M26 / "data" / "constituencies_goal75.csv"
MEDIAS24_LATEST_PATH = E_ROOT / "medias24_db_latest.json"

EXPECTED_F0_SHA256 = "fbe5197999f20d0612bc0c66e1954b5c611b11208e43a72eb5494a03b1e40d3f"
EXPECTED_B2_ROSTER_SHA256 = "b206ad303869c744d8ade5e3dc09442611d2a59cc15c87aedb19265aae171b86"

# Frozen after F0, before this execution. The row index and source Arabic form
# must both match the preserved 92-row PJD artifact. The canonical IDs must form
# a strict bijection with the frozen 92-local Atlas geometry.
ROW_MAPPING = [
    (1, "طنجة أصيلة", "tanger-assilah"),
    (2, "الفحص أنجرة", "fahs-anjra"),
    (3, "تطوان", "tetouan"),
    (4, "المضيق الفنيدق", "m-diq-fnideq"),
    (5, "العرائش", "larache"),
    (6, "شفشاون", "chefchaouen"),
    (7, "وزان", "ouezzane"),
    (8, "الحسيمة", "al-hoceima"),
    (9, "وجدة أنجاد", "oujda-angad"),
    (10, "جرادة", "jerada"),
    (11, "بركان", "berkane"),
    (12, "تاوريرت", "taourirt"),
    (13, "فجيج بوعرفة", "figuig"),
    (14, "الناظور", "nador"),
    (15, "الدرويش", "driouch"),
    (16, "جرسيف", "guercif"),
    (17, "فاس الشمالية", "fes-nord"),
    (18, "فاس الجنوبية", "fes-sud"),
    (19, "مكناس", "meknes"),
    (20, "الحاجب", "el-hajeb"),
    (21, "إفران", "ifrane"),
    (22, "مولاي يعقوب", "moulay-yaacoub"),
    (23, "صفرو", "sefrou"),
    (24, "بولمان", "boulemane"),
    (25, "تازة", "taza"),
    (26, "تاونات تيسة", "taounate-tissa"),
    (27, "القرية غفساي", "karia-ghafsay"),
    (28, "الرباط &#8211; المحيط", "rabat-ocean"),
    (29, "الرباط &#8211; شالة", "rabat-chellah"),
    (30, "سلا المدينة", "sale-medina"),
    (31, "سلا الجديدة", "sale-el-jadida"),
    (32, "الصخيرات -تمارة", "skhirate-temara"),
    (33, "القنيطرة", "kenitra"),
    (34, "الغرب", "el-gharb"),
    (35, "الخميسات &#8211; أولماس", "khemisset-oulmes"),
    (36, "تيفلت &#8211; الرماني", "tiflet-rommani"),
    (37, "سيدي قاسم", "sidi-kacem"),
    (38, "سيدي سليمان", "sidi-slimane"),
    (39, "الدار البيضاء آنفا", "casablanca-anfa"),
    (40, "الفداء مرس السلطان", "al-fida-mers-sultan"),
    (41, "عين السبع الحي المحمدي", "ain-sebaa-hay-mohammadi"),
    (42, "الحي الحسني", "hay-hassani"),
    (43, "عين الشق", "ain-chock"),
    (44, "سيدي البرنوصي", "sidi-bernoussi"),
    (45, "ابن مسيك", "ben-m-sick"),
    (46, "مولاي رشيد", "moulay-rachid"),
    (47, "النواصر", "nouaceur"),
    (48, "مديونة", "mediouna"),
    (49, "المحمدية", "mohammedia"),
    (50, "سطات", "settat"),
    (51, "برشيد", "berrechid"),
    (52, "الجديدة", "el-jadida"),
    (53, "سيدي بنور", "sidi-bennour"),
    (54, "بنسليمان", "benslimane"),
    (55, "المدينة &#8211; سيدي يوسف بن علي", "medina-sidi-youssef"),
    (56, "جليز &#8211; النخيل", "gueliz-nakhil"),
    (57, "المنارة", "menara"),
    (58, "شيشاوة", "chichaoua"),
    (59, "الحوز", "al-haouz"),
    (60, "قلعة السراغنة", "el-kelaa-des-sraghna"),
    (61, "الصويرة", "essaouira"),
    (62, "الرحامنة", "rehamna"),
    (63, "اليوسفية", "youssoufia"),
    (64, "آسفي", "safi"),
    (65, "بني ملال", "beni-mellal"),
    (66, "بزو &#8211; واويزغت", "bzou-ouaouizeght"),
    (67, "أزيلال &#8211; دمنات", "azilal-demnate"),
    (68, "الفقيه بن صالح", "fquih-ben-salah"),
    (69, "خنيفرة", "khenifra"),
    (70, "خريبكة", "khouribga"),
    (71, "الرشيدية", "errachidia"),
    (72, "ميدلت", "midelt"),
    (73, "ورزازات", "ouarzazate"),
    (74, "زاكورة", "zagora"),
    (75, "تنغير", "tinghir"),
    (76, "أكادير إداوتنان", "agadir-ida-outanane"),
    (77, "إنزكان آيت ملول", "inezgane-ait-melloul"),
    (78, "شتوكة آيت باها", "chtouka-ait-baha"),
    (79, "تارودانت الجنوبية", "taroudant-sud"),
    (80, "تارودانت الشمالية", "taroudant-nord"),
    (81, "تيزنيت", "tiznit"),
    (82, "طاطا", "tata"),
    (83, "كلميم", "guelmim"),
    (84, "سيدي افني", "sidi-ifni"),
    (85, "طانطان", "tan-tan"),
    (86, "أسا الزاك", "assa-zag"),
    (87, "العيون", "laayoune"),
    (88, "بوجدور", "boujdour"),
    (89, "طرفاية", "tarfaya"),
    (90, "السمارة", "es-semara"),
    (91, "وادي الذهب", "oued-eddahab"),
    (92, "أوسرد", "aousserd"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize_arabic(value: str | None) -> str:
    text = html.unescape(value or "")
    text = unicodedata.normalize("NFC", text)
    text = text.replace("ـ", "")
    text = re.sub(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]", "", text)
    text = re.sub(r"[أإآٱ]", "ا", text)
    text = re.sub(r"[\-–—]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_canonical() -> list[dict[str, Any]]:
    with CANONICAL_PATH.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        row["seats"] = int(row["seats"])
    if len(rows) != 92:
        raise RuntimeError(f"expected 92 canonical constituencies, got {len(rows)}")
    return rows


def main() -> int:
    before = {
        "F0": sha256_file(F0_PATH),
        "B2_ROSTER": sha256_file(B2_ROSTER_PATH),
    }
    if before["F0"] != EXPECTED_F0_SHA256:
        raise RuntimeError("F0 hash mismatch")
    if before["B2_ROSTER"] != EXPECTED_B2_ROSTER_SHA256:
        raise RuntimeError("B2 roster hash mismatch")

    canonical = load_canonical()
    canonical_by_id = {row["constituency_id"]: row for row in canonical}
    canonical_ids = set(canonical_by_id)
    roster = load_json(B2_ROSTER_PATH)
    source_rows = roster["rows"]

    if len(source_rows) != 92 or len(ROW_MAPPING) != 92:
        raise RuntimeError("the Arabic crosswalk must cover exactly 92 rows")

    mapped_ids = {item[2] for item in ROW_MAPPING}
    if mapped_ids != canonical_ids:
        missing = sorted(canonical_ids - mapped_ids)
        extra = sorted(mapped_ids - canonical_ids)
        raise RuntimeError(f"Arabic mapping is not a canonical bijection; missing={missing}, extra={extra}")

    mapping_by_index = {index: (raw, cid) for index, raw, cid in ROW_MAPPING}
    if len(mapping_by_index) != 92:
        raise RuntimeError("duplicate row index in Arabic mapping")

    current_region_ar = None
    territory_records: list[dict[str, Any]] = []
    pjd_records: list[dict[str, Any]] = []

    for row in source_rows:
        index = int(row["row_index"])
        expected_raw, constituency_id = mapping_by_index[index]
        if row["constituency_raw"] != expected_raw:
            raise RuntimeError(
                f"row {index} drift: expected {expected_raw!r}, got {row['constituency_raw']!r}"
            )
        if row.get("region_raw"):
            current_region_ar = row["region_raw"]
        canonical_row = canonical_by_id[constituency_id]
        name_ar = html.unescape(row["constituency_raw"])
        pending = "في طور الترشيح والتزكية" in normalize_arabic(row["agent_name_raw"])

        territory_records.append(
            {
                "row_index": index,
                "constituency_id": constituency_id,
                "name_ar": name_ar,
                "name_ar_source_form": row["constituency_raw"],
                "name_ar_match_key": normalize_arabic(row["constituency_raw"]),
                "name_fr": canonical_row["name"],
                "region_ar": current_region_ar,
                "region_fr": canonical_row["region"],
                "seats": canonical_row["seats"],
                "status": "CONTROLLER_ACCEPTED_BILINGUAL_IDENTITY",
                "resolution_method": "NATIVE_ARABIC_ONE_TO_ONE_CANONICAL_CROSSWALK_V1",
                "source_refs": [
                    "morocco26/data/goal100/b2_2026_ballot_roster.json",
                    "morocco26/data/constituencies_goal75.csv",
                ],
                "source_roster_sha256": before["B2_ROSTER"],
                "forecast_effect": "NONE_IDENTITY_ONLY",
            }
        )
        pjd_records.append(
            {
                "record_id": f"PJD-OFFICIAL-2026-{constituency_id}",
                "party": "PJD",
                "constituency_id": constituency_id,
                "constituency_name_ar": name_ar,
                "constituency_name_fr": canonical_row["name"],
                "region_ar": current_region_ar,
                "region_fr": canonical_row["region"],
                "seats": canonical_row["seats"],
                "person_name_ar": None if pending else row["agent_name_raw"],
                "person_name_ar_match_key": None if pending else normalize_arabic(row["agent_name_raw"]),
                "person_name_lat": None,
                "nomination_status": "PENDING_NOMINATION" if pending else "PARTY_ANNOUNCED",
                "evidence_status": "PARTY_ANNOUNCED",
                "source_class": "OFFICIAL_PARTY",
                "source_id": roster["source"]["source_id"],
                "source_artifact": "morocco26/data/goal100/b2_2026_ballot_roster.json",
                "source_raw_path": roster["source"]["stored_path"],
                "source_sha256": before["B2_ROSTER"],
                "forecast_impact_status": "NOT_CALIBRATED",
            }
        )

    # Structural validations independent of semantic confidence.
    if len({item["constituency_id"] for item in territory_records}) != 92:
        raise RuntimeError("Arabic territory crosswalk contains duplicate canonical IDs")
    if len({item["name_ar_match_key"] for item in territory_records}) != 92:
        raise RuntimeError("Arabic territory crosswalk contains duplicate Arabic match keys")

    latest = load_json(MEDIAS24_LATEST_PATH)
    medias24_snapshot_path = ROOT / latest["atlas_snapshot"]
    medias24 = load_json(medias24_snapshot_path)
    candidates = [dict(item) for item in medias24.get("candidates", [])]
    territory_by_id = {item["constituency_id"]: item for item in territory_records}

    for candidate in candidates:
        tid = candidate.get("constituency_id")
        territory = territory_by_id.get(tid)
        candidate["constituency_name_ar"] = territory["name_ar"] if territory else None
        candidate["region_ar"] = territory["region_ar"] if territory else None
        candidate["forecast_impact_status"] = "NOT_CALIBRATED"

    pjd_medias24_by_tid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate.get("party") == "PJD" and candidate.get("constituency_id"):
            pjd_medias24_by_tid[candidate["constituency_id"]].append(candidate)

    pjd_join_counts = Counter()
    pjd_conflicts: list[dict[str, Any]] = []
    official_by_tid = {item["constituency_id"]: item for item in pjd_records}

    for official in pjd_records:
        tid = official["constituency_id"]
        matches = pjd_medias24_by_tid.get(tid, [])
        if len(matches) == 1:
            match = matches[0]
            official["person_name_lat"] = match.get("name_source_form")
            official["medias24_record_id"] = match.get("record_id")
            official["evidence_status"] = "PARTY_ANNOUNCED_AND_MEDIAS24_STRUCTURED"
            match["name_ar"] = official["person_name_ar"]
            match["official_party_record_id"] = official["record_id"]
            match["atlas_evidence_status"] = official["evidence_status"]
            pjd_join_counts["unique_match"] += 1
        elif len(matches) == 0:
            pjd_join_counts["no_medias24_match"] += 1
            candidates.append(
                {
                    "record_id": official["record_id"],
                    "source_class": official["source_class"],
                    "discovery_origin": "REPO_EXISTING",
                    "source_url": None,
                    "source_artifact": official["source_artifact"],
                    "source_database_url": None,
                    "source_database_sha256": None,
                    "retrieved_at": roster["generated_at"],
                    "name_source_form": official["person_name_ar"],
                    "name_ar": official["person_name_ar"],
                    "name_lat": None,
                    "party": "PJD",
                    "region_source_form": official["region_ar"],
                    "region_ar": official["region_ar"],
                    "constituency_source_form": official["constituency_name_ar"],
                    "constituency_name_ar": official["constituency_name_ar"],
                    "constituency_id": tid,
                    "constituency_canonical_name": official["constituency_name_fr"],
                    "territory_resolution_status": "CONTROLLER_ACCEPTED_BILINGUAL_IDENTITY",
                    "territory_resolution_method": "NATIVE_ARABIC_ONE_TO_ONE_CANONICAL_CROSSWALK_V1",
                    "role": "وكيل(ة) اللائحة",
                    "source_status": official["nomination_status"],
                    "atlas_evidence_status": official["evidence_status"],
                    "forecast_impact_status": "NOT_CALIBRATED",
                }
            )
        else:
            pjd_join_counts["multiple_medias24_matches"] += 1
            pjd_conflicts.append(
                {
                    "constituency_id": tid,
                    "official_record_id": official["record_id"],
                    "medias24_record_ids": [item.get("record_id") for item in matches],
                    "status": "AMBIGUOUS_MULTIPLE_PJD_RECORDS",
                }
            )

    candidate_by_tid: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        if candidate.get("constituency_id"):
            candidate_by_tid[candidate["constituency_id"]].append(candidate)

    territories: list[dict[str, Any]] = []
    for territory in territory_records:
        tid = territory["constituency_id"]
        rows = candidate_by_tid.get(tid, [])
        parties = sorted({str(row.get("party")) for row in rows if row.get("party")})
        statuses = Counter(str(row.get("atlas_evidence_status")) for row in rows)
        territories.append(
            {
                **territory,
                "candidate_record_count": len(rows),
                "party_count": len(parties),
                "parties": parties,
                "evidence_status_counts": dict(statuses),
                "pjd_record": official_by_tid[tid],
            }
        )

    med_local_covered = {
        item.get("constituency_id")
        for item in medias24.get("candidates", [])
        if item.get("constituency_id")
    }
    all_covered = {item.get("constituency_id") for item in candidates if item.get("constituency_id")}
    missing_medias24 = sorted(set(canonical_by_id) - med_local_covered)
    missing_after_merge = sorted(set(canonical_by_id) - all_covered)

    crosswalk_artifact = {
        "schema_version": "1.0",
        "artifact_id": "ATLAS395-ARABIC-TERRITORY-CROSSWALK-V1",
        "created_at": now_iso(),
        "status": "CONTROLLER_ACCEPTED_PRODUCT_IDENTITY_LAYER",
        "scope": "IDENTITY_ONLY_NO_FORECAST_EFFECT",
        "source_roster_sha256": before["B2_ROSTER"],
        "canonical_geometry_path": str(CANONICAL_PATH.relative_to(ROOT)),
        "counts": {
            "source_rows": len(source_rows),
            "canonical_ids": len(canonical_ids),
            "resolved": len(territory_records),
            "ambiguous": 0,
            "duplicate_ids": 0,
            "duplicate_arabic_match_keys": 0,
        },
        "validation": {
            "row_index_and_source_form_exact_match": True,
            "strict_92_to_92_bijection": True,
            "all_seat_magnitudes_from_frozen_geometry": True,
            "F0_modified": False,
            "B2_modified": False,
        },
        "records": territory_records,
    }
    pjd_artifact = {
        "schema_version": "1.0",
        "artifact_id": "ATLAS395-PJD-2026-BILINGUAL-ROSTER-V1",
        "created_at": now_iso(),
        "source_class": "OFFICIAL_PARTY",
        "status": "PARTY_ANNOUNCED_EVIDENCE_LAYER",
        "forecast_impact_status": "NOT_CALIBRATED",
        "counts": {
            "rows": len(pjd_records),
            "named_people": sum(1 for item in pjd_records if item["person_name_ar"]),
            "pending_nomination": sum(1 for item in pjd_records if item["nomination_status"] == "PENDING_NOMINATION"),
            "unique_medias24_join": pjd_join_counts["unique_match"],
            "no_medias24_join": pjd_join_counts["no_medias24_match"],
            "multiple_medias24_join": pjd_join_counts["multiple_medias24_matches"],
        },
        "conflicts": pjd_conflicts,
        "records": pjd_records,
    }

    consolidated = {
        "schema_version": "1.0",
        "snapshot_id": "ATLAS395-V1-ARABIC-NATIVE-PREVIEW",
        "generated_at": now_iso(),
        "release_status": "FUNCTIONAL_EVIDENCE_LAYER_PREVIEW",
        "forecast": {
            "snapshot_id": "F0",
            "immutable": True,
            "artifact_sha256": before["F0"],
            "candidate_and_signal_impact": "NOT_CALIBRATED",
            "notice_fr": "Les candidatures et signaux 2026 sont affichés séparément et ne modifient pas encore la projection F0.",
            "notice_ar": "تُعرض ترشيحات وإشارات 2026 بشكل منفصل ولا تغيّر توقعات F0 في هذه المرحلة.",
        },
        "coverage": {
            "canonical_local_territories": 92,
            "arabic_identity_coverage": len(territory_records),
            "medias24_candidate_records_raw": len(medias24.get("candidates", [])),
            "candidate_records_after_official_pjd_merge": len(candidates),
            "medias24_local_territories_with_records": len(med_local_covered),
            "local_territories_with_records_after_merge": len(all_covered),
            "missing_from_medias24_local_records": missing_medias24,
            "missing_after_merge": missing_after_merge,
            "pjd_rows": len(pjd_records),
            "parties": len(medias24.get("parties", [])),
        },
        "source_ledger": [
            medias24["source"],
            {
                "class": "OFFICIAL_PARTY",
                "source_id": roster["source"]["source_id"],
                "artifact": str(B2_ROSTER_PATH.relative_to(ROOT)),
                "raw_path": roster["source"]["stored_path"],
                "sha256": before["B2_ROSTER"],
                "retrieved_at": roster["generated_at"],
            },
        ],
        "parties": medias24.get("parties", []),
        "territories": territories,
        "candidates": candidates,
        "pjd_bilingual_roster": pjd_records,
        "identity_conflicts": pjd_conflicts,
        "display_policy": {
            "arabic_first_class": True,
            "raw_arabic_preserved": True,
            "ambiguity_explicit": True,
            "forecast_and_evidence_separate": True,
            "statuses": [
                "PARTY_ANNOUNCED",
                "PARTY_ANNOUNCED_AND_MEDIAS24_STRUCTURED",
                "MEDIAS24_REPORTED",
                "AMBIGUOUS",
                "DATA_BLOCKED",
            ],
        },
        "integrity": {
            "F0_sha256": before["F0"],
            "B2_roster_sha256": before["B2_ROSTER"],
            "F0_modified": False,
            "B2_modified": False,
            "coefficients_modified": False,
            "forecast_delta_authorized": False,
        },
    }

    dump(E_ROOT / "arabic_territory_crosswalk_v1.json", crosswalk_artifact)
    dump(E_ROOT / "pjd_2026_bilingual_roster_v1.json", pjd_artifact)
    dump(ATLAS_ROOT / "atlas_v1_snapshot.json", consolidated)
    dump(WEB_DATA_ROOT / "atlas_v1.json", consolidated)

    execution_state = {
        "schema_version": "1.0",
        "state_id": "M26-E-COLLECT-V1.1-EXECUTION",
        "as_of": now_iso(),
        "status": "ARABIC_NATIVE_PRODUCTION_LAYER_BUILT",
        "human_seeded_discovery": True,
        "medias24_run_id": latest["latest_run_id"],
        "outputs": {
            "arabic_crosswalk": "morocco26/data/goal100/e_collect/arabic_territory_crosswalk_v1.json",
            "pjd_bilingual_roster": "morocco26/data/goal100/e_collect/pjd_2026_bilingual_roster_v1.json",
            "atlas_snapshot": "morocco26/data/atlas_v1/atlas_v1_snapshot.json",
            "web_snapshot": "morocco26/web/data/atlas_v1.json",
        },
        "coverage": consolidated["coverage"],
        "remaining_scientific_work": [
            "Independent record-level adjudication of candidate evidence",
            "Historical 16-class recovery and cutoff audit",
            "E_reason preregistration before any forecast effect",
        ],
        "remaining_product_work": [
            "Render the Atlas V1 evidence layer in the public UI",
            "Automate timestamped daily editions",
            "Expand official-source corroboration and source URLs",
        ],
        "protected": consolidated["integrity"],
    }
    dump(E_ROOT / "e_collect_v1_1_execution_state.json", execution_state)

    after = {
        "F0": sha256_file(F0_PATH),
        "B2_ROSTER": sha256_file(B2_ROSTER_PATH),
    }
    if after != before:
        raise RuntimeError("protected scientific artifacts changed")
    if missing_after_merge:
        raise RuntimeError(f"Atlas V1 merge left territories without candidate evidence: {missing_after_merge}")

    print(json.dumps(execution_state, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
