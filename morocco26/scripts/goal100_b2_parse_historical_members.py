#!/usr/bin/env python3
"""Parse elected-member partitions out of the raw vault, deterministically.

Extraction rules are copied from the already-committed 2021 ingest
(`goal75_observed_2021.py`) so the earlier legislatures are read exactly the way
the accepted 2021 rows were: `motifentree == 'elu'`, one record per `idsiege`,
earliest `dateentree` first.

Territory resolution uses the *certified* alias table from
`b2_identity_crosswalk.json`. No fuzzy matching, no edit distance, no
transliteration model, no LLM. A name that does not resolve to a certified
identifier exactly is reported as unresolved, never forced.

Leakage: a legislature elected in year Y is the outcome of Y. It is emitted only
as the incumbency state observable at a strictly later cutoff.
"""
from __future__ import annotations

import glob
import hashlib
import json
import unicodedata
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
G100 = ROOT / "data" / "goal100"
TZ = ZoneInfo("Africa/Casablanca")

CROSSWALK_PATH = G100 / "b2_identity_crosswalk.json"
VAULT_GLOB = str(G100 / "b2_raw_acquisition" / "HF_CHAMBER_MEMBERS_MULTIYEAR" / "data" / "*.parquet")
MANIFEST_PATH = G100 / "b2_raw_acquisition_manifest.json"
OUTPUT_PATH = G100 / "historical" / "b2_historical_elected_members.json"
PARSER_MANIFEST_PATH = G100 / "b2_parser_manifest.json"

PARSER_ID = "M26-GOAL100-B2-MEMBER-PARSER"
PARSER_VERSION = "1.0"

# parlement label -> the election year that produced it.
PARTITION_TO_ELECTION_YEAR = {
    "2007-2011": 2007,
    "2011-2016": 2011,
    "2016-2021": 2016,
    "2021-2026": 2021,
}

ARABIC_TRANSLATION = str.maketrans({
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
    "ى": "ي", "ؤ": "و", "ئ": "ي", "ـ": "",
    "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4",
    "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
})
APOSTROPHES = "'’ʼ`´ʻʹ"
DASHES = "‐‑‒–—―−"


def load(path: Path):
    if not path.exists():
        raise SystemExit(f"B2_MEMBER_PARSE_FAIL: missing {path.relative_to(REPO)}")
    return json.loads(path.read_text(encoding="utf-8"))


def dump(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def canonical_sha256(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def now_local() -> str:
    return datetime.now(TZ).isoformat(timespec="seconds")


def normalize_text(value: object) -> str:
    """The frozen M26_TEXT_NORMALIZER_V1 behaviour, reproduced exactly."""
    text = unicodedata.normalize("NFKC", str(value or "")).translate(ARABIC_TRANSLATION)
    for char in APOSTROPHES:
        text = text.replace(char, " ")
    for char in DASHES:
        text = text.replace(char, " ")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    cleaned = []
    for char in text.casefold():
        category = unicodedata.category(char)
        cleaned.append(char if char.isalnum() or category.startswith("L") else " ")
    return " ".join("".join(cleaned).split())


def party_code(value: object) -> str:
    import re
    return re.sub(r"[^A-Z0-9]+", "-", str(value or "").strip().upper()).strip("-")


def certified_alias_maps(crosswalk: dict) -> tuple[dict[str, str], dict[str, str]]:
    """Exact normalized alias -> certified territory ID, from the certified crosswalk."""
    local: dict[str, str] = {}
    regional: dict[str, str] = {}
    for row in crosswalk["territories"]["local"]:
        for alias in row.get("normalized_aliases", []):
            local[alias] = row["constituency_id"]
        local[normalize_text(row["canonical_name"])] = row["constituency_id"]
    for row in crosswalk["territories"]["regional"]:
        for alias in row.get("normalized_aliases", []):
            regional[alias] = row["region_id"]
        regional[normalize_text(row["canonical_name"])] = row["region_id"]
    return local, regional


def parse_members() -> tuple[dict, dict]:
    crosswalk = load(CROSSWALK_PATH)
    if crosswalk["gate"] != "PASS":
        raise SystemExit("B2_MEMBER_PARSE_FAIL: identity crosswalk is not PASS")
    local_alias, regional_alias = certified_alias_maps(crosswalk)

    files = sorted(glob.glob(VAULT_GLOB))
    if not files:
        raise SystemExit("B2_MEMBER_PARSE_FAIL: raw vault contains no member parquet; run the acquirer first")

    frame = pd.concat([pd.read_parquet(path) for path in files], ignore_index=True)
    required = {"parlement", "motifentree", "idsiege", "idperson", "prenomnom", "parti", "circonscription", "region", "dateentree"}
    missing = required - set(frame.columns)
    if missing:
        raise SystemExit(f"B2_MEMBER_PARSE_FAIL: raw schema is missing columns {sorted(missing)}")

    regional_prefix = normalize_text("Circonscription régionale")
    years: dict[str, dict] = {}
    unresolved_samples: list[dict] = []

    for partition, election_year in sorted(PARTITION_TO_ELECTION_YEAR.items()):
        subset = frame[frame["parlement"].astype(str) == partition].copy()
        elected = subset[subset["motifentree"].astype(str).str.casefold() == "elu"].copy()
        elected = elected.sort_values(["idsiege", "dateentree"]).drop_duplicates(subset=["idsiege"], keep="first")

        rows = []
        counters = Counter()
        party_counts = Counter()
        for record in elected.to_dict("records"):
            circonscription = str(record.get("circonscription") or "")
            normalized_circ = normalize_text(circonscription)
            is_regional = normalized_circ.startswith(regional_prefix)
            if is_regional:
                scope = "regional"
                key = normalize_text(record.get("region"))
                territory_id = regional_alias.get(key)
            else:
                scope = "local"
                key = normalized_circ
                territory_id = local_alias.get(key)

            resolution = "CERTIFIED_EXACT_ID" if territory_id else "UNRESOLVED_NO_CERTIFIED_ALIAS"
            counters[f"{scope}_{'resolved' if territory_id else 'unresolved'}"] += 1
            code = party_code(record.get("parti"))
            party_counts[code] += 1
            if territory_id is None and len(unresolved_samples) < 60:
                unresolved_samples.append({
                    "election_year": election_year,
                    "scope": scope,
                    "raw_label": circonscription if scope == "local" else str(record.get("region") or ""),
                    "normalized_label": key,
                    "resolution": resolution,
                })

            rows.append({
                "election_year": election_year,
                "parlement": partition,
                "person_id": f"tafra-person:{int(record['idperson'])}",
                "seat_id": f"tafra-seat:{int(record['idsiege'])}",
                "canonical_name_source": str(record.get("prenomnom") or "").strip(),
                "normalized_name": normalize_text(record.get("prenomnom")),
                "party_code": code,
                "scope": scope,
                "territory_id": territory_id,
                "territory_resolution": resolution,
                "source_label": circonscription,
                "region_source": str(record.get("region") or ""),
                "entry_date": str(record.get("dateentree") or ""),
                "identity_basis": "TAFRA_STABLE_PERSON_ID",
            })

        rows.sort(key=lambda row: (row["scope"], row["territory_id"] or "~", row["seat_id"]))
        local_total = counters["local_resolved"] + counters["local_unresolved"]
        years[str(election_year)] = {
            "election_year": election_year,
            "parlement": partition,
            "elected_rows": len(rows),
            "local_rows": local_total,
            "regional_rows": counters["regional_resolved"] + counters["regional_unresolved"],
            "local_territories_resolved": len({row["territory_id"] for row in rows if row["scope"] == "local" and row["territory_id"]}),
            "local_rows_resolved": counters["local_resolved"],
            "local_rows_unresolved": counters["local_unresolved"],
            "regional_rows_resolved": counters["regional_resolved"],
            "regional_rows_unresolved": counters["regional_unresolved"],
            "distinct_parties": len(party_counts),
            "admissible_as_prior_cycle_for_cutoff_after": election_year,
            "rows": rows,
        }

    output = {
        "schema_version": "1.0",
        "artifact_id": "M26-GOAL100-B2-HISTORICAL-ELECTED-MEMBERS-V1",
        "generated_at": now_local(),
        "parser": {"parser_id": PARSER_ID, "version": PARSER_VERSION, "llm_used": False},
        "extraction_rules": {
            "partition_field": "parlement",
            "elected_filter": "motifentree casefolded == 'elu'",
            "deduplication": "one row per idsiege, earliest dateentree retained",
            "territory_resolution": "exact normalized alias lookup against the certified crosswalk",
            "fuzzy_matching": False,
            "provenance": "rules copied from morocco26/scripts/goal75_observed_2021.py",
        },
        "leakage_controls": {
            "outcome_year_used_for_its_own_cycle": False,
            "note": "Each legislature is emitted only as incumbency observable at a strictly later cutoff.",
        },
        "source_files": [Path(path).relative_to(REPO).as_posix() for path in files],
        "source_file_sha256": {
            Path(path).name: hashlib.sha256(Path(path).read_bytes()).hexdigest() for path in files
        },
        "years": years,
        "unresolved_territory_samples": unresolved_samples,
    }
    output["canonical_artifact_sha256"] = canonical_sha256(output)

    parser_manifest = {
        "schema_version": "1.0",
        "manifest_id": "M26-GOAL100-B2-PARSER-MANIFEST-V1",
        "generated_at": output["generated_at"],
        "parsers": [
            {
                "parser_id": PARSER_ID,
                "version": PARSER_VERSION,
                "input_format": "parquet",
                "method": "STRUCTURED_API",
                "llm_used": False,
                "semantic_judgment_used": False,
                "handles": ["HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR"],
                "input_source_id": "HF_CHAMBER_MEMBERS_MULTIYEAR",
                "output_artifact": OUTPUT_PATH.relative_to(REPO).as_posix(),
                "output_sha256": output["canonical_artifact_sha256"],
                "unparsable_policy": "UNPARSABLE_NONAGENTIC is reported; no field is inferred semantically.",
                "years_parsed": sorted(int(year) for year in years),
            }
        ],
    }
    parser_manifest["canonical_manifest_sha256"] = canonical_sha256(
        {k: v for k, v in parser_manifest.items() if k != "canonical_manifest_sha256"}
    )
    return output, parser_manifest


def main() -> None:
    output, parser_manifest = parse_members()
    dump(OUTPUT_PATH, output)
    dump(PARSER_MANIFEST_PATH, parser_manifest)

    print("B2_MEMBER_PARSE_COMPLETE")
    for year in sorted(output["years"], key=int):
        row = output["years"][year]
        print(
            f"  {year}: elected={row['elected_rows']:>4} "
            f"local={row['local_rows']:>4} (resolved {row['local_rows_resolved']}, "
            f"territories {row['local_territories_resolved']}) "
            f"regional={row['regional_rows']:>3} (resolved {row['regional_rows_resolved']})"
        )
    print(f"artifact_sha256={output['canonical_artifact_sha256']}")


if __name__ == "__main__":
    main()
