#!/usr/bin/env python3
"""Promote a validated G0 deliberation observatory into the static frontend."""
from __future__ import annotations
import argparse
import hashlib
import json
import pathlib
import shutil
import sys
from typing import Any, Mapping, Sequence

EXPECTED_BASELINE = "G0_CHATGPT_GPT56_SOL"
EXPECTED_DECISION_MODEL = "gpt-5.6-sol"


class PromotionError(RuntimeError):
    pass


def read_json(path: pathlib.Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: pathlib.Path, value: Any, pretty: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2 if pretty else None, separators=None if pretty else (",", ":")) + "\n"
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def mapping_lookup(path: pathlib.Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None:
        return {}
    payload = read_json(path)
    rows = payload.get("mappings") or []
    result = {}
    for row in rows:
        key = (str(row["anonymous_election_id"]), str(row["anonymous_territory_id"]))
        result[key] = {
            "public": row.get("public"),
            "party_mapping": {str(k): str(v) for k, v in (row.get("party_mapping") or {}).items()},
        }
    return result


def validate_report(report: Mapping[str, Any]) -> None:
    if report.get("baseline_id") != EXPECTED_BASELINE:
        raise PromotionError("wrong deliberation baseline")
    contract = report.get("model_contract") or {}
    decision = contract.get("decision") or []
    if not decision or decision[0] != EXPECTED_DECISION_MODEL:
        raise PromotionError("wrong decision model in observatory report")
    labels = report.get("methodological_labels") or {}
    if labels.get("deliberation") != "MODEL_GENERATED_OBSERVABLE_EXPLANATION_NOT_PRIVATE_CHAIN_OF_THOUGHT":
        raise PromotionError("missing observable-deliberation label")
    if not isinstance(report.get("deliberations"), list):
        raise PromotionError("deliberations array missing")


def deterministic_sample(rows: Sequence[Mapping[str, Any]], limit: int) -> list[Mapping[str, Any]]:
    if len(rows) <= limit:
        return list(rows)
    required = []
    rest = []
    for row in rows:
        if row.get("panel") in {"SWING", "TURNOUT_PIVOT"}:
            required.append(row)
        else:
            rest.append(row)
    required = sorted(required, key=lambda r: (str(r.get("task_id", "")), str(r.get("weighted_archetype_id", ""))))
    remaining = max(0, limit - len(required))
    ranked = sorted(
        rest,
        key=lambda r: hashlib.sha256(
            (str(r.get("anonymous_election_id")) + "|" + str(r.get("anonymous_territory_id")) + "|" + str(r.get("weighted_archetype_id"))).encode()
        ).hexdigest(),
    )
    return (required + ranked[:remaining])[:limit]


def build_public_payload(
    report: Mapping[str, Any],
    mapping: Mapping[tuple[str, str], Mapping[str, Any]],
    max_agents: int,
) -> dict[str, Any]:
    counters = {
        (str(row.get("task_id")), str(row.get("archetype_id"))): row
        for row in report.get("counterfactual_evaluations") or []
    }
    rows = deterministic_sample(report.get("deliberations") or [], max_agents)
    agents = []
    for row in rows:
        election = str(row.get("anonymous_election_id"))
        territory = str(row.get("anonymous_territory_id"))
        info = mapping.get((election, territory)) or {}
        parties = info.get("party_mapping") or {}
        top = str(row.get("top_party_id"))
        runner = str(row.get("runner_up_party_id"))
        task_id = str(row.get("task_id") or "")
        archetype = str(row.get("weighted_archetype_id"))
        cf = counters.get((task_id, archetype))
        agent = dict(row)
        agent["top_party_label"] = parties.get(top, top)
        agent["runner_up_party_label"] = parties.get(runner, runner)
        agent["public_territory"] = info.get("public")
        agent["public_label"] = archetype + (" · " + str(info.get("public")) if info.get("public") else "")
        agent["counterfactual"] = cf
        agents.append(agent)
    return {
        "schema_version": "ATLAS_PUBLIC_DELIBERATION_OBSERVATORY_V1",
        "status": "G0_OBSERVABLE_DELIBERATION_AVAILABLE",
        "baseline_id": EXPECTED_BASELINE,
        "methodological_labels": report.get("methodological_labels"),
        "work_items": report.get("work_items"),
        "source_deliberation_rows": report.get("deliberation_rows"),
        "published_agents": len(agents),
        "aggregates": report.get("aggregates"),
        "agents": agents,
    }


def apply_preview(preview: pathlib.Path, web_data: pathlib.Path) -> None:
    archive = web_data / "reference" / "deliberation_previous"
    archive.mkdir(parents=True, exist_ok=True)
    for name in ("deliberation_observatory.json", "deliberation_provenance.json"):
        current = web_data / name
        if current.is_file() and not (archive / name).exists():
            shutil.copy2(current, archive / name)
        shutil.copy2(preview / name, current)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--observatory-report", required=True, type=pathlib.Path)
    ap.add_argument("--web-root", required=True, type=pathlib.Path)
    ap.add_argument("--territory-mapping-audit", type=pathlib.Path)
    ap.add_argument("--preview-dir", type=pathlib.Path)
    ap.add_argument("--max-agents", type=int, default=12000)
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args(argv)

    report_path = args.observatory_report.expanduser().resolve()
    web_root = args.web_root.expanduser().resolve()
    if not (web_root / "data").is_dir():
        raise PromotionError("web/data directory missing")
    report = read_json(report_path)
    validate_report(report)
    mapping = mapping_lookup(args.territory_mapping_audit.expanduser().resolve() if args.territory_mapping_audit else None)
    payload = build_public_payload(report, mapping, args.max_agents)
    preview = args.preview_dir.expanduser().resolve() if args.preview_dir else report_path.parent / "deliberation_frontend_preview"
    if preview.exists():
        shutil.rmtree(preview)
    preview.mkdir(parents=True)
    data_path = preview / "deliberation_observatory.json"
    write_json(data_path, payload, pretty=False)
    provenance = {
        "schema_version": "ATLAS_PUBLIC_DELIBERATION_PROVENANCE_V2",
        "available": True,
        "status": "G0_OBSERVABLE_DELIBERATION_AVAILABLE",
        "data_path": "data/deliberation_observatory.json",
        "baseline_id": EXPECTED_BASELINE,
        "source_report_sha256": sha256(report_path),
        "published_data_sha256": sha256(data_path),
        "published_agents": payload["published_agents"],
        "territory_party_labels_mapped": bool(mapping),
        "labels": {
            "short": "G0 · délibération observable",
            "long": "Les décisions ont été gelées avant leur explication. Les récits sont reliés à un catalogue de preuves fermé et restent des hypothèses tant que les packets contrefactuels ne les confirment pas. Aucune chaîne de pensée privée n’est exposée."
        },
        "private_chain_of_thought": "NOT_REQUESTED_NOT_EXPOSED",
        "observable_deliberation": "SEPARATE_POST_DECISION_STRUCTURED_EXPLANATION",
        "counterfactual_validation": "SEPARATE_PACKET_RERUNS_WITH_PLACEBO",
        "outcomes_opened": False
    }
    write_json(preview / "deliberation_provenance.json", provenance)
    audit = {
        "schema_version": "ATLAS_DELIBERATION_FRONTEND_PROMOTION_AUDIT_V1",
        "status": "PASS_APPLIED" if args.apply else "PASS_PREVIEW_READY",
        "source_report_sha256": sha256(report_path),
        "files": {
            "deliberation_observatory.json": sha256(data_path),
            "deliberation_provenance.json": sha256(preview / "deliberation_provenance.json")
        }
    }
    write_json(preview / "deliberation_promotion_audit.json", audit)
    if args.apply:
        apply_preview(preview, web_root / "data")
        print("PASS_G0_DELIBERATION_PROMOTED_TO_FRONTEND")
    else:
        print(f"PASS_G0_DELIBERATION_PREVIEW_READY {preview}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except PromotionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(2)
