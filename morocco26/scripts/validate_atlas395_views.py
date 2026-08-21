#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

M26 = Path(__file__).resolve().parents[1]
DEFAULT_DATA = M26 / "web" / "data"
DEFAULT_EDITIONS = M26 / "web" / "editions"
DEFAULT_POLICY = M26 / "atlas395" / "source_policy.json"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise SystemExit(f"ATLAS395_VALIDATION_FAIL: {message}")


def validate_source_policy(evidence: dict, policy: dict) -> None:
    allowed = {str(x) for x in policy.get("authorized_source_ids") or []}
    media = {str(x) for x in policy.get("authorized_media_source_ids") or []}
    require(policy.get("default_decision") == "DENY", "source policy must fail closed")
    require(media == {"T2_MEDIAS24"}, "Médias24 must be the sole authorized media source")
    require(not any(x.startswith("T2_") and x not in media for x in allowed), "unauthorized media in source allowlist")
    policy_view = evidence.get("source_policy") or {}
    require(policy_view.get("policy_id") == policy.get("policy_id"), "reader source policy id mismatch")
    require(policy_view.get("policy_sha256") == canonical(policy), "reader source policy hash mismatch")
    source_ids = {str(x.get("source")) for x in evidence.get("sources") or []}
    event_source_ids = {str(x.get("source")) for x in evidence.get("events") or [] if x.get("source")}
    require(source_ids <= allowed, "reader source list contains a disallowed source")
    require(event_source_ids <= allowed, "reader event list contains a disallowed source")
    require(not ({"T2_HESPRESS", "T2_LE360", "T2_LEMATIN", "T2_SNRTNEWS", "T2_TELQUEL"} & (source_ids | event_source_ids)), "forbidden media leaked into reader data")
    reader = evidence.get("reader_scope") or {}
    require(int(reader.get("authorized_media_sources") or 0) <= 1, "reader reports more than one media source")
    daily_watch = evidence.get("daily_watch") or {}
    if daily_watch:
        require(daily_watch.get("source_policy_id") == policy.get("policy_id"), "daily intake source policy mismatch")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--editions-dir", type=Path, default=DEFAULT_EDITIONS)
    parser.add_argument("--require-daily", action="store_true")
    parser.add_argument("--source-policy", type=Path, default=DEFAULT_POLICY)
    args = parser.parse_args()
    data = args.data_dir

    snapshot = load(data / "current_snapshot.json")
    national = load(data / "national_projection.json")
    cards = load(data / "constituency_cards.json")
    parties = load(data / "party_cards.json")
    evidence = load(data / "evidence_index.json")
    methodology = load(data / "methodology_state.json")
    public_methodology = load(data / "public_methodology.json")
    public_manifest = load(data / "snapshot_manifest.json")

    require(snapshot.get("status") == "FROZEN", "displayed forecast snapshot must be frozen")
    require(snapshot.get("read_only_contract") is True, "read-only product contract missing")
    geometry = snapshot.get("geometry") or {}
    require(geometry.get("local_constituencies") == 92, "local constituency count != 92")
    require(geometry.get("local_seats") == 305, "local seats != 305")
    require(geometry.get("regional_constituencies") == 12, "regional constituency count != 12")
    require(geometry.get("regional_seats") == 90, "regional seats != 90")
    require(geometry.get("total_seats") == 395, "total seats != 395")
    require(national.get("total_seats") == 395 and national.get("local_seats") == 305 and national.get("regional_seats") == 90, "national seat accounting mismatch")
    require(cards.get("count") == 92 and len(cards.get("constituencies") or []) == 92, "constituency cards != 92")
    require(sum(int(card.get("magnitude") or 0) for card in cards["constituencies"]) == 305, "local magnitude sum != 305")
    require(len(parties.get("parties") or []) == 9, "party buckets != 9")

    public = public_methodology.get("public_methodology") or {}
    require(public_methodology.get("product") == "ATLAS 395", "public methodology product mismatch")
    require(public.get("total_seats") == 395, "public methodology total seats != 395")
    require(public.get("local_constituencies") == 92, "public methodology local constituencies != 92")
    require(public.get("regional_constituencies") == 12, "public methodology regional constituencies != 12")
    require(public.get("manual_party_bonus") == 0, "public methodology manual party bonus must be zero")
    require(public.get("draws") == snapshot.get("draws"), "public methodology draw count mismatch")

    separation = methodology.get("scientific_separation") or {}
    require(separation.get("atlas_views_are_model_inputs") is False, "Atlas views cannot become model inputs")
    require(separation.get("atlas_writes_scientific_artifacts") is False, "Atlas cannot write scientific artifacts")
    require(separation.get("unknown_preserved") is True, "missing information must remain explicitly missing")

    generated = public_manifest.get("generated_from") or {}
    require(generated.get("snapshot_id") == snapshot.get("snapshot_id"), "public manifest/current snapshot mismatch")
    require(generated.get("forecast_sha256") == snapshot.get("forecast_sha256"), "forecast hash mismatch across public views")
    for name, expected in (public_manifest.get("outputs") or {}).items():
        require((data / name).exists() and sha(data / name) == expected, f"public output hash mismatch {name}")

    for card in cards["constituencies"]:
        for party in (card.get("parties") or {}).values():
            for key in ("p_ge_1", "p_ge_2"):
                value = party.get(key)
                if value is not None:
                    require(-1e-12 <= float(value) <= 1 + 1e-12, f"invalid probability {key}")
            distribution = party.get("p_seats_k") or []
            if distribution:
                require(abs(sum(float(x) for x in distribution) - 1.0) < 1e-6, "seat distribution does not sum to 1")

    policy = load(args.source_policy)
    validate_source_policy(evidence, policy)

    if args.require_daily:
        daily = load(data / "daily_update.json")
        current = load(args.editions_dir / "current.json")
        index = load(args.editions_dir / "index.json")
        edition_id = current.get("edition_id")
        require(bool(edition_id), "daily current pointer has no edition id")
        require(index.get("current_edition") == edition_id, "daily pointers disagree")
        edition_dir = args.editions_dir / str(edition_id)
        edition_manifest = load(edition_dir / "edition.json")
        require(edition_manifest.get("forecast_snapshot") == snapshot.get("snapshot_id"), "edition/forecast mismatch")
        require(edition_manifest.get("product_version") == current.get("product_version"), "edition/product version mismatch")
        require(edition_manifest.get("source_policy_id") == policy.get("policy_id"), "edition/source policy mismatch")
        require(isinstance(daily.get("projection_changed"), bool), "daily projection_changed must be boolean")
        for name, expected in (edition_manifest.get("files") or {}).items():
            require((edition_dir / name).exists() and sha(edition_dir / name) == expected, f"immutable edition hash mismatch {name}")

    print(
        "ATLAS395_VALIDATION_OK "
        f"snapshot={snapshot.get('snapshot_id')} constituencies=92 seats=395 "
        f"daily={args.require_daily} source_policy={policy.get('policy_id')} read_only=true public_methodology=true"
    )


if __name__ == "__main__":
    main()
