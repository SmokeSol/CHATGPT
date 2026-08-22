from __future__ import annotations

"""Core primitives for the Agent Society three-regime electoral simulation goal.

The module intentionally separates four concepts:

* BLIND_ATTRIBUTE_CONTROL: the already-generated fully blind control.
* HISTORICAL_SEMIBLIND_RICH: historical packets remain anonymous and byte-stable,
  but the prompt receives a pointer-only reading contract that makes the existing
  candidate/programme layer explicit without duplicating any value.
* REALISTIC_2026_NAMED: real names and current candidates are allowed only after
  an exact-SHA, time-bounded, complete roster gate passes.
* NAMED_2026_PSEUDONYMIZED_TWIN: an internal diagnostic twin used only to isolate
  the effect of identity labels inside the same 2026 information set.

No function in this module reads historical target outcomes.
"""

import dataclasses
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from typing import Any, Iterable, Mapping, MutableMapping, Sequence

GOAL_ID = "M26_AGENT_SOCIETY_THREE_REGIME_GOAL_V1"
PROTOCOL_ID = "M26_AGENT_SOCIETY_THREE_REGIME_PROTOCOL_V1"
SCHEMA_VERSION = "1.0"
REGISTERED_BRANCH_HEAD = "774758bdfc1f05813e04d0088ba323354aaac219"
REGISTERED_MAIN_SHA = "4df897c356d3f0c36832405c7fcfc7f8f0cd6de2"
FROZEN_FULL_ENVIRONMENT_SHA256 = "e8acad28dea5a531c21171db570b60d612993edd91db8f893e58c187c226696a"
FROZEN_MODEL = "gpt-5.6-sol"
FROZEN_REASONING = "medium"
EXPECTED_CONTEXTS = 368
EXPECTED_ELECTION_TERRITORY_ITEMS = 184
EXPECTED_WORK_ITEMS = 2944
EXPECTED_ROWS = 94208
STARTUP_WORK_ITEMS = 32
STARTUP_ROWS = 1024
EXPECTED_PROGRAMME_AXES = 18
EXPECTED_CANDIDATE_FEATURES = 16
CANONICAL_PROGRAMME_AXES = (
    "civil_liberties",
    "culture",
    "decentralization",
    "digital_transition",
    "economic_sovereignty",
    "education",
    "employment",
    "environment_transition",
    "fiscal_relief",
    "gender_equality",
    "governance_rule_of_law",
    "health",
    "housing",
    "industrial_competitiveness",
    "private_investment_sme",
    "public_state_role",
    "rural_territorial_equity",
    "social_protection",
)
CANONICAL_CANDIDATE_FEATURES = (
    "CANDIDATE_REGISTERED_RANK",
    "FORMAL_ENDORSEMENT",
    "FORMAL_LIST_ALLIANCE",
    "FORMER_MINISTER_OR_NATIONAL_OFFICE",
    "FORMER_MP",
    "INCUMBENT_SAME_PARTY_MOVED_DISTRICT",
    "INCUMBENT_SAME_PARTY_SAME_DISTRICT",
    "LOCAL_EXECUTIVE_OFFICE",
    "NATIONAL_OR_REGIONAL_PARTY_OFFICE",
    "OFFICIAL_SANCTION_OR_INVESTIGATION",
    "PARTY_SWITCH_IN",
    "PARTY_SWITCH_OUT",
    "PRINCIPAL_COMPETITOR_COUNT_WITH_VERIFIED_PROFILE",
    "PROVINCIAL_OR_REGIONAL_OFFICE",
    "VERIFIED_DEATH_OR_INCAPACITY",
    "WITHDRAWN_OR_DISQUALIFIED",
)

REGIME_BLIND = "BLIND_ATTRIBUTE_CONTROL"
REGIME_HISTORICAL = "HISTORICAL_SEMIBLIND_RICH"
REGIME_NAMED = "REALISTIC_2026_NAMED"
REGIME_NAMED_TWIN = "NAMED_2026_PSEUDONYMIZED_TWIN"
PRIMARY_REGIMES = (REGIME_BLIND, REGIME_HISTORICAL, REGIME_NAMED)

BLIND_CONTROL_REPORT_SHA256 = "0bc0ad9abf4b7160918324a330900cbad9fc5577f4c4d14e3b694ebcd0b0e05b"
BLIND_CONTROL_REPORT_BYTES = 81506
BLIND_CONTROL_AGENTS = 32
BLIND_CONTROL_TERRITORY = "T_0267CFF87A2606F5"
BLIND_CONTROL_BATCH = "B01"

MAIN_2026_CERTIFICATE_PATH = "morocco26/data/goal100/b2_2026_ballot_certificate.json"
MAIN_2026_ROSTER_PATH = "morocco26/data/goal100/b2_2026_ballot_roster.json"

FORBIDDEN_HISTORICAL_FIELD_TOKENS = (
    "outcome",
    "actual_vote",
    "actual_share",
    "winner",
    "seat_result",
    "target_result",
    "post_election",
    "unseal",
    "score_against",
    "real_party_name",
    "real_candidate_name",
    "real_territory_name",
)
FORBIDDEN_HISTORICAL_TEXT = (
    re.compile(r"\b(?:2016|2021)\b"),
    re.compile(r"\b(?:PJD|RNI|PAM|PI|PPS|USFP|UC|MP)\b", re.I),
)
SENTINELS = {"MISSING", "UNKNOWN", "UNVERIFIED", "NOT_FOUND", "DATA_BLOCKED", "AMBIGUOUS"}
SAFE_NEGATIVE_POLICY_KEYS = {
    "target_outcomes_present",
    "real_party_names_present",
    "real_candidate_names_present",
    "real_territory_names_present",
    "model_packet_mutated",
    "model_packet_values_duplicated",
}
FORBIDDEN_NAMED_FIELD_TOKENS = (
    "outcome",
    "actual_vote",
    "actual_share",
    "winner",
    "seat_result",
    "target_result",
    "post_election",
    "unseal",
    "score_against",
)
MODEL_PROVENANCE_KEYS = {
    "source_record_ids",
    "source_record_id",
    "source_url",
    "url",
    "raw_url",
    "sha256",
    "git_blob_sha",
    "known_as_of",
    "provenance",
    "raw",
}


class ThreeRegimeError(RuntimeError):
    """Fail-closed protocol or data error."""


@dataclasses.dataclass(frozen=True)
class ContextRecord:
    path: pathlib.Path
    raw_sha256: str
    election_id: str
    territory_id: str
    condition_id: str
    context: dict[str, Any]

    @property
    def election_territory_key(self) -> str:
        return f"{self.election_id}|{self.territory_id}"

    @property
    def context_key(self) -> str:
        return f"{self.election_id}|{self.condition_id}|{self.territory_id}"


@dataclasses.dataclass(frozen=True)
class MainSource:
    path: str
    git_blob_sha: str
    raw_sha256: str
    data: Any


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def parse_timestamp(value: Any, *, label: str) -> dt.datetime:
    text = str(value or "").strip()
    if not text:
        raise ThreeRegimeError(f"{label} is empty")
    try:
        parsed = dt.datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ThreeRegimeError(f"{label} is not ISO-8601: {text}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def require_not_after(value: Any, ceiling: dt.datetime, *, label: str) -> dt.datetime:
    parsed = parse_timestamp(value, label=label)
    if parsed > ceiling:
        raise ThreeRegimeError(f"{label} is newer than the frozen snapshot")
    return parsed


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def sha256_file(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: pathlib.Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ThreeRegimeError(f"cannot read JSON {path}: {exc}") from exc


def atomic_write(path: pathlib.Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=str(path.parent))
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass


def write_json(path: pathlib.Path, value: Any, *, pretty: bool = True) -> None:
    if pretty:
        payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    else:
        payload = canonical_bytes(value) + b"\n"
    atomic_write(path, payload)


def git(repo_root: pathlib.Path, *args: str) -> bytes:
    process = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if process.returncode:
        message = process.stderr.decode("utf-8", "replace").strip()
        raise ThreeRegimeError(message or f"git {' '.join(args)} failed")
    return process.stdout


def validate_exact_commit(repo_root: pathlib.Path, sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ThreeRegimeError("commit must be an exact 40-character lowercase SHA")
    resolved = git(repo_root, "rev-parse", f"{sha}^{{commit}}").decode().strip()
    if resolved != sha:
        raise ThreeRegimeError(f"commit {sha} did not resolve to itself")
    return resolved


def git_show_bytes(repo_root: pathlib.Path, sha: str, path: str) -> bytes:
    lower = path.lower()
    if any(token in lower for token in ("outcome", "unseal", "score_against", "result_2016", "result_2021")):
        raise ThreeRegimeError(f"forbidden source path: {path}")
    return git(repo_root, "show", f"{sha}:{path}")


def git_blob_sha(repo_root: pathlib.Path, sha: str, path: str) -> str:
    return git(repo_root, "rev-parse", f"{sha}:{path}").decode().strip()


def load_main_json(repo_root: pathlib.Path, sha: str, path: str) -> MainSource:
    raw = git_show_bytes(repo_root, sha, path)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ThreeRegimeError(f"invalid JSON at {sha}:{path}: {exc}") from exc
    return MainSource(path=path, git_blob_sha=git_blob_sha(repo_root, sha, path), raw_sha256=sha256_bytes(raw), data=data)


def list_commit_paths(repo_root: pathlib.Path, sha: str) -> list[str]:
    raw = git(repo_root, "ls-tree", "-r", "--name-only", sha).decode("utf-8", "replace")
    return [line for line in raw.splitlines() if line]


def safe_extract_environment(bundle: pathlib.Path, cache_root: pathlib.Path) -> tuple[pathlib.Path, str]:
    bundle = bundle.expanduser().resolve()
    if bundle.is_dir():
        return bundle, "DIRECTORY"
    if not bundle.is_file() or bundle.suffix.lower() != ".zip":
        raise ThreeRegimeError("--environment must be the full-environment ZIP or extracted directory")
    digest = sha256_file(bundle)
    target = cache_root / digest
    marker = target / ".three_regime_extracted_ok"
    if not marker.is_file():
        temporary = target.with_name(target.name + ".tmp")
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(bundle) as archive:
            for info in archive.infolist():
                member = pathlib.PurePosixPath(info.filename)
                if member.is_absolute() or ".." in member.parts:
                    raise ThreeRegimeError(f"unsafe ZIP member: {info.filename}")
            archive.extractall(temporary)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.rmtree(target, ignore_errors=True)
        os.replace(temporary, target)
        marker.write_text(digest + "\n", encoding="utf-8")
    return target, digest


def find_context_files(root: pathlib.Path) -> list[pathlib.Path]:
    candidates = sorted(root.rglob("contexts/*/*/*.json"))
    if not candidates:
        candidates = sorted(path for path in root.rglob("*.json") if "contexts" in path.parts)
    if not candidates:
        raise ThreeRegimeError(f"no context JSON files found under {root}")
    return candidates


def _context_identity(value: Mapping[str, Any], path: pathlib.Path) -> tuple[str, str, str]:
    election = str(value.get("anonymous_election_id") or "")
    territory = str(value.get("anonymous_territory_id") or "")
    condition = str(value.get("condition_id") or "")
    if not election or not territory or not condition:
        raise ThreeRegimeError(f"context identity incomplete at {path}")
    return election, territory, condition


def collect_contexts(root: pathlib.Path, *, strict_counts: bool = True) -> tuple[list[ContextRecord], dict[str, Any]]:
    records: list[ContextRecord] = []
    for path in find_context_files(root):
        raw = path.read_bytes()
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ThreeRegimeError(f"invalid context JSON {path}: {exc}") from exc
        election, territory, condition = _context_identity(value, path)
        records.append(
            ContextRecord(
                path=path,
                raw_sha256=sha256_bytes(raw),
                election_id=election,
                territory_id=territory,
                condition_id=condition,
                context=dict(value),
            )
        )
    keys = [record.context_key for record in records]
    if len(keys) != len(set(keys)):
        raise ThreeRegimeError("duplicate election-condition-territory context")
    election_territories = {record.election_territory_key for record in records}
    elections = sorted({record.election_id for record in records})
    conditions = sorted({record.condition_id for record in records})
    if strict_counts:
        if len(records) != EXPECTED_CONTEXTS:
            raise ThreeRegimeError(f"context count {len(records)} != {EXPECTED_CONTEXTS}")
        if len(election_territories) != EXPECTED_ELECTION_TERRITORY_ITEMS:
            raise ThreeRegimeError(
                f"election×territory count {len(election_territories)} != {EXPECTED_ELECTION_TERRITORY_ITEMS}"
            )
    return records, {
        "context_count": len(records),
        "election_territory_count": len(election_territories),
        "anonymous_election_ids": elections,
        "condition_ids": conditions,
        "context_hash_index_sha256": sha256_json({record.context_key: record.raw_sha256 for record in records}),
    }


def context_payload(value: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = value.get("context")
    return nested if isinstance(nested, Mapping) else value


def party_cards(context: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], tuple[str, ...]]:
    payload = context_payload(context)
    available = tuple(sorted(str(item) for item in (payload.get("available_party_ids") or [])))
    if not available:
        raise ThreeRegimeError("available_party_ids missing from context")
    common = payload.get("common_territory_card") or {}
    election = payload.get("election_environment_card") or {}
    local_cards = [dict(item) for item in (common.get("party_context_cards") or [])]
    programme_cards = [dict(item) for item in (election.get("party_offer_cards") or [])]
    local_by = {str(item.get("anonymous_party_id")): item for item in local_cards}
    programme_by = {str(item.get("anonymous_party_id")): item for item in programme_cards}
    if set(local_by) != set(available):
        raise ThreeRegimeError("candidate/local card party panel does not match available_party_ids")
    if set(programme_by) != set(available):
        raise ThreeRegimeError("programme card party panel does not match available_party_ids")
    return local_cards, programme_cards, available


def _candidate_feature_semantics(card: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for feature in card.get("features") or []:
        if not isinstance(feature, Mapping):
            raise ThreeRegimeError("candidate feature is not an object")
        feature_id = str(feature.get("feature_id") or "")
        if not feature_id:
            raise ThreeRegimeError("candidate feature_id missing")
        result.append(
            {
                "feature_id": feature_id,
                "status": feature.get("status"),
                "value": feature.get("value"),
                "conflict": bool(feature.get("conflict", False)),
            }
        )
    result.sort(key=lambda item: item["feature_id"])
    if len({item["feature_id"] for item in result}) != len(result):
        raise ThreeRegimeError("duplicate candidate feature_id")
    return result


def _programme_semantics(card: Mapping[str, Any]) -> dict[str, Any]:
    levels = card.get("program_priority_levels") or {}
    if not isinstance(levels, Mapping):
        raise ThreeRegimeError("program_priority_levels is not an object")
    return {
        "government_status": card.get("government_status"),
        "program_priority_levels": {str(key): levels[key] for key in sorted(levels)},
    }


def anonymous_candidate_id(election_id: str, territory_id: str, party_id: str) -> str:
    raw = f"{PROTOCOL_ID}|{election_id}|{territory_id}|{party_id}".encode("utf-8")
    return "CAND_" + hashlib.sha256(raw).hexdigest()[:16].upper()


def build_pointer_only_historical_contract(record: ContextRecord) -> dict[str, Any]:
    """Build a non-duplicative reading contract for the historical packet.

    Values are deliberately absent. The contract points to the exact existing JSON
    cards and records hashes of their semantics for audit. The original packet is
    therefore the only model-visible copy of every candidate/programme fact.
    """

    local_cards, programme_cards, available = party_cards(record.context)
    local_by = {str(item["anonymous_party_id"]): item for item in local_cards}
    programme_by = {str(item["anonymous_party_id"]): item for item in programme_cards}
    cards = []
    candidate_counts: list[int] = []
    programme_counts: list[int] = []
    for party_id in available:
        candidate_semantics = _candidate_feature_semantics(local_by[party_id])
        programme_semantics = _programme_semantics(programme_by[party_id])
        candidate_counts.append(len(candidate_semantics))
        programme_counts.append(len(programme_semantics["program_priority_levels"]))
        cards.append(
            {
                "anonymous_party_id": party_id,
                "anonymous_candidate_id": anonymous_candidate_id(
                    record.election_id, record.territory_id, party_id
                ),
                "candidate_card_json_pointer": (
                    "/common_territory_card/party_context_cards/"
                    + str(next(i for i, item in enumerate(local_cards) if str(item["anonymous_party_id"]) == party_id))
                ),
                "programme_card_json_pointer": (
                    "/election_environment_card/party_offer_cards/"
                    + str(next(i for i, item in enumerate(programme_cards) if str(item["anonymous_party_id"]) == party_id))
                ),
                "candidate_feature_ids": [item["feature_id"] for item in candidate_semantics],
                "programme_axis_ids": list(programme_semantics["program_priority_levels"]),
                "candidate_semantic_sha256": sha256_json(candidate_semantics),
                "programme_semantic_sha256": sha256_json(programme_semantics),
            }
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "regime": REGIME_HISTORICAL,
        "anonymous_election_id": record.election_id,
        "anonymous_territory_id": record.territory_id,
        "condition_id": record.condition_id,
        "source_context_sha256": record.raw_sha256,
        "model_packet_mutated": False,
        "model_packet_values_duplicated": False,
        "non_scoring_pointer_only_reading_contract": True,
        "real_party_names_present": False,
        "real_candidate_names_present": False,
        "real_territory_names_present": False,
        "target_outcomes_present": False,
        "cards": cards,
        "coverage": {
            "party_cards": len(cards),
            "candidate_feature_count_min": min(candidate_counts, default=0),
            "candidate_feature_count_max": max(candidate_counts, default=0),
            "programme_axis_count_min": min(programme_counts, default=0),
            "programme_axis_count_max": max(programme_counts, default=0),
            "expected_candidate_features": EXPECTED_CANDIDATE_FEATURES,
            "expected_programme_axes": EXPECTED_PROGRAMME_AXES,
        },
        "reading_instruction": (
            "Les identités sont volontairement pseudonymisées, mais chaque Q_* représente un vrai parti "
            "et chaque CAND_* une vraie offre locale. Examine les 16 attributs candidat/locaux et les "
            "18 axes programmatiques déjà présents aux pointeurs indiqués. Une valeur manquante signifie "
            "information indisponible, pas absence de candidat ou de programme. Ne tente aucune ré-identification."
        ),
    }


def validate_historical_contract(contract: Mapping[str, Any], *, strict_shape: bool = True) -> None:
    if contract.get("regime") != REGIME_HISTORICAL:
        raise ThreeRegimeError("wrong historical regime")
    required_false = (
        "model_packet_mutated",
        "model_packet_values_duplicated",
        "real_party_names_present",
        "real_candidate_names_present",
        "real_territory_names_present",
        "target_outcomes_present",
    )
    failed = [field for field in required_false if contract.get(field) is not False]
    if failed:
        raise ThreeRegimeError(f"historical contract safety flags failed: {failed}")
    if contract.get("non_scoring_pointer_only_reading_contract") is not True:
        raise ThreeRegimeError("historical contract is not pointer-only")
    for card in contract.get("cards") or []:
        forbidden_value_keys = {
            "features",
            "candidate_features",
            "program_priority_levels",
            "programme_values",
            "candidate_values",
        }
        if forbidden_value_keys.intersection(card):
            raise ThreeRegimeError("historical reading contract duplicated semantic values")
        for key in ("candidate_card_json_pointer", "programme_card_json_pointer"):
            if not str(card.get(key) or "").startswith("/"):
                raise ThreeRegimeError(f"invalid JSON pointer: {key}")
        if tuple(sorted(map(str, card.get("candidate_feature_ids") or []))) != tuple(sorted(CANONICAL_CANDIDATE_FEATURES)):
            raise ThreeRegimeError("historical candidate feature vocabulary drift")
        if tuple(sorted(map(str, card.get("programme_axis_ids") or []))) != tuple(sorted(CANONICAL_PROGRAMME_AXES)):
            raise ThreeRegimeError("historical programme-axis vocabulary drift")
    scan_historical_leaks(contract)
    if strict_shape:
        coverage = contract.get("coverage") or {}
        if int(coverage.get("candidate_feature_count_min") or 0) != EXPECTED_CANDIDATE_FEATURES:
            raise ThreeRegimeError("historical candidate feature layer is not exactly 16 per party")
        if int(coverage.get("candidate_feature_count_max") or 0) != EXPECTED_CANDIDATE_FEATURES:
            raise ThreeRegimeError("historical candidate feature layer varies from 16 per party")
        if int(coverage.get("programme_axis_count_min") or 0) != EXPECTED_PROGRAMME_AXES:
            raise ThreeRegimeError("historical programme layer is not exactly 18 axes per party")
        if int(coverage.get("programme_axis_count_max") or 0) != EXPECTED_PROGRAMME_AXES:
            raise ThreeRegimeError("historical programme layer varies from 18 axes per party")


def assert_no_forbidden_keys(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lower = str(key).lower()
            if any(token in lower for token in FORBIDDEN_HISTORICAL_FIELD_TOKENS):
                if str(key) not in SAFE_NEGATIVE_POLICY_KEYS or child is not False:
                    raise ThreeRegimeError(f"forbidden historical field at {path}.{key}")
            assert_no_forbidden_keys(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_forbidden_keys(child, path=f"{path}[{index}]")


def scan_historical_leaks(value: Any) -> None:
    assert_no_forbidden_keys(value)
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    findings = [pattern.pattern for pattern in FORBIDDEN_HISTORICAL_TEXT if pattern.search(text)]
    if findings:
        raise ThreeRegimeError(f"historical identity/year leakage detected: {findings}")


def assert_no_named_outcomes(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lower = str(key).lower()
            if any(token in lower for token in FORBIDDEN_NAMED_FIELD_TOKENS):
                if str(key) != "target_outcomes_present" or child is not False:
                    raise ThreeRegimeError(f"forbidden current-election result field at {path}.{key}")
            assert_no_named_outcomes(child, path=f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_named_outcomes(child, path=f"{path}[{index}]")


def load_main_bridge(path: pathlib.Path) -> tuple[dict[str, Any], str]:
    path = path.expanduser().resolve()
    value = read_json(path)
    items = value.get("items")
    semantic = value.get("semantic_equivalence_audit") or {}
    controls = value.get("historical_controls") or {}
    dev_pilot_scope = controls.get("scope") == "DEVELOPMENT_ONLY_P1_PILOT"
    expected_items = (
        EXPECTED_ELECTION_TERRITORY_ITEMS // 2
        if dev_pilot_scope
        else EXPECTED_ELECTION_TERRITORY_ITEMS
    )
    checks = {
        "bridge_id": value.get("bridge_id") == "M26_AS_MAIN_BRIDGE_V1",
        "status": value.get("status") == "PASS_FROZEN_MAIN_BRIDGE_READY_FOR_G0_SOL",
        "main_sha": value.get("main_commit_sha") == REGISTERED_MAIN_SHA,
        "items": isinstance(items, Mapping) and len(items) == expected_items,
        "outcomes": value.get("target_outcomes_present") is False,
        "identities": value.get("real_identity_material_present") is False,
        "semantic_delta": value.get("model_semantic_delta_v1") is False,
        "semantic_equivalence": semantic.get("status") == "PASS_SEMANTIC_EQUIVALENCE_ONLY",
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise ThreeRegimeError(f"main bridge gate failed: {failed}")
    return dict(value), sha256_file(path)


def engagement_score(voter: Mapping[str, Any]) -> float:
    """Deterministic awareness proxy, deliberately excluding protected traits.

    Only prior electoral participation and supplied political-discussion intensity
    are used. Age, sex, religion, ethnicity, language, location and income never
    alter the information diet.
    """

    discussion = (
        voter.get("latent_attitude_political_discussion_mean")
        if voter.get("latent_attitude_political_discussion_mean") is not None
        else voter.get("political_discussion")
    )
    try:
        score = float(discussion)
    except (TypeError, ValueError):
        score = 0.5
    prior = str(voter.get("prior_vote_or_abstention") or "")
    if prior == "ABSTAIN":
        score -= 0.15
    elif prior:
        score += 0.10
    return max(0.0, min(1.0, score))


def information_diet(voter: Mapping[str, Any]) -> dict[str, Any]:
    score = engagement_score(voter)
    if score < 0.35:
        level = "LOW"
        programme_axes = 5
        candidate_depth = "SALIENT_VERIFIED_ONLY"
    elif score < 0.65:
        level = "MEDIUM"
        programme_axes = 10
        candidate_depth = "BASIC_VERIFIED_PROFILE"
    else:
        level = "HIGH"
        programme_axes = EXPECTED_PROGRAMME_AXES
        candidate_depth = "FULL_VERIFIED_PROFILE"
    source = {
        "prior_vote_or_abstention": voter.get("prior_vote_or_abstention"),
        "latent_attitude_political_discussion_mean": voter.get(
            "latent_attitude_political_discussion_mean"
        ),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "information_diet_id": "DIET_" + sha256_json(source)[:16].upper(),
        "level": level,
        "engagement_score": round(score, 6),
        "source_fields": sorted(source),
        "protected_or_demographic_fields_used": [],
        "party_identity_visibility": "LOCAL_BALLOT_ALL",
        "programme_axes_visible_max": programme_axes,
        "candidate_depth": candidate_depth,
        "national_leader_visibility": "KNOWN_IF_SOURCE_VERIFIED" if level != "LOW" else "SALIENT_ONLY",
        "local_history_visibility": "BAND" if level != "HIGH" else "FULL_PRE_ELECTION_RECORD",
    }


def inspect_blind_control_run(root: pathlib.Path) -> dict[str, Any]:
    root = root.expanduser().resolve()
    state_path = root / "run_state.json"
    if not state_path.is_file():
        raise ThreeRegimeError(f"blind control run_state.json missing under {root}")
    state = read_json(state_path)
    checks = {
        "sealed_outcomes": state.get("target_outcomes_opened") is False,
        "chatgpt_auth": state.get("auth_mode") == "CHATGPT_MANAGED_CODEX_LOGIN",
        "no_api_key": state.get("api_key_used") is False,
        "sol_model": state.get("model") == FROZEN_MODEL,
    }
    failed = sorted(name for name, ok in checks.items() if not ok)
    if failed:
        raise ThreeRegimeError(f"blind control provenance gate failed: {failed}")
    output_files = sorted(
        path for path in (root / "outputs").rglob("*.jsonl")
        if "all_outputs" not in path.name
    )
    populated: list[tuple[pathlib.Path, list[dict[str, Any]]]] = []
    for path in output_files:
        rows = list(iter_jsonl(path))
        if rows:
            populated.append((path, rows))
    if len(populated) != 1:
        raise ThreeRegimeError(
            f"P0 pairing requires a snapshot with exactly one populated work-item output; found {len(populated)}"
        )
    output_path, rows = populated[0]
    if len(rows) != BLIND_CONTROL_AGENTS:
        raise ThreeRegimeError(f"P0 output rows {len(rows)} != {BLIND_CONTROL_AGENTS}")
    identity_fields = (
        "anonymous_election_id",
        "anonymous_territory_id",
        "condition_id",
        "batch_id",
    )
    identity = {field: str(rows[0].get(field) or "") for field in identity_fields}
    if any(not value for value in identity.values()):
        raise ThreeRegimeError("P0 raw rows have incomplete work-item identity")
    for row in rows:
        if any(str(row.get(field) or "") != value for field, value in identity.items()):
            raise ThreeRegimeError("P0 raw snapshot contains more than one work-item identity")
    archetypes = [str(row.get("weighted_archetype_id") or "") for row in rows]
    if any(not item for item in archetypes) or len(set(archetypes)) != BLIND_CONTROL_AGENTS:
        raise ThreeRegimeError("P0 raw output does not contain 32 unique archetypes")
    if identity["anonymous_territory_id"] != BLIND_CONTROL_TERRITORY:
        raise ThreeRegimeError("P0 raw territory does not match the registered report")
    if identity["batch_id"] != BLIND_CONTROL_BATCH:
        raise ThreeRegimeError("P0 raw batch does not match the registered report")
    task_suffix = "__".join(
        re.escape(identity[field])
        for field in (
            "anonymous_election_id",
            "condition_id",
            "anonymous_territory_id",
            "batch_id",
        )
    )
    return {
        "status": "PASS_P0_RAW_D0_EXACT_WORK_ITEM_BOUND",
        "root": str(root),
        "run_state_sha256": sha256_file(state_path),
        "output_path": str(output_path),
        "output_sha256": sha256_file(output_path),
        "rows": len(rows),
        "identity": identity,
        "archetype_ids_sha256": sha256_json(archetypes),
        "task_regex": rf"(?:^|__)({task_suffix})$",
    }


def named_2026_readiness(repo_root: pathlib.Path, main_sha: str) -> dict[str, Any]:
    sha = validate_exact_commit(repo_root, main_sha)
    certificate = load_main_json(repo_root, sha, MAIN_2026_CERTIFICATE_PATH)
    roster = load_main_json(repo_root, sha, MAIN_2026_ROSTER_PATH)
    cert = certificate.data
    rows = (roster.data or {}).get("rows") if isinstance(roster.data, Mapping) else None
    rows = rows if isinstance(rows, list) else []
    gate = str(cert.get("gate") or "UNKNOWN")
    coverage = float(cert.get("territory_coverage_fraction") or 0.0)
    verified = int(cert.get("verified_double_entry_rows") or 0)
    parties = sorted(str(item) for item in (cert.get("parties_covered") or []))
    failures = list(cert.get("failures") or [])
    checks = {
        "certificate_gate_pass": gate == "PASS",
        "territory_coverage_complete": abs(coverage - 1.0) <= 1e-12,
        "verified_candidate_rows_present": verified > 0,
        "all_92_local_constituencies_declared": int(cert.get("certified_local_constituencies") or 0) == 92,
        "more_than_one_party_covered": len(parties) > 1,
        "roster_rows_present": len(rows) > 0,
    }
    ready = all(checks.values())
    blockers = sorted(name for name, ok in checks.items() if not ok)
    return {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "regime": REGIME_NAMED,
        "status": "PASS_NAMED_2026_SOURCE_READY" if ready else "BLOCKED_NAMED_2026_INCOMPLETE_ROSTER",
        "ready_to_generate_named_packets": ready,
        "main_commit_sha": sha,
        "known_as_of_policy": "SOURCE_RECORD_MUST_BE_AVAILABLE_BEFORE_PACKET_SNAPSHOT",
        "source_inventory": {
            certificate.path: {
                "git_blob_sha": certificate.git_blob_sha,
                "raw_sha256": certificate.raw_sha256,
                "gate": gate,
            },
            roster.path: {
                "git_blob_sha": roster.git_blob_sha,
                "raw_sha256": roster.raw_sha256,
                "rows": len(rows),
                "artifact_id": (roster.data or {}).get("artifact_id") if isinstance(roster.data, Mapping) else None,
            },
        },
        "observed": {
            "territory_coverage_fraction": coverage,
            "verified_double_entry_rows": verified,
            "parties_covered": parties,
            "parsed_roster_rows": len(rows),
            "ambiguous_deterministic_match_rows": int(cert.get("ambiguous_deterministic_match_rows") or 0),
            "blocked_source_documents": int(cert.get("blocked_source_documents") or 0),
        },
        "checks": checks,
        "blockers": blockers,
        "certificate_failures": failures,
        "candidate_fabrication_allowed": False,
        "partial_named_simulation_allowed": False,
        "candidate_intelligence_v3_policy": (
            "EXCLUDED unless an explicit 2026 source record has known_as_of <= snapshot and passes the named-input schema"
        ),
        "next_gate": (
            "Provide a complete, exact-SHA, double-entry-verified 2026 ballot/candidate input for all intended contests; "
            "then validate it against NAMED_2026_INPUT_SCHEMA_V1 before any Sol call."
        ),
    }


def validate_named_input(value: Mapping[str, Any]) -> dict[str, Any]:
    required = {
        "schema_version",
        "artifact_id",
        "main_commit_sha",
        "snapshot_known_as_of",
        "territories",
        "parties",
        "candidacies",
        "programmes",
        "source_records",
        "coverage",
        "voter_population",
        "conditions",
        "national_context",
    }
    missing = required - set(value)
    if missing:
        raise ThreeRegimeError(f"named input missing fields: {sorted(missing)}")
    if value.get("main_commit_sha") != REGISTERED_MAIN_SHA:
        raise ThreeRegimeError("named input is not pinned to the registered main SHA")
    assert_no_named_outcomes(value)
    snapshot = parse_timestamp(value.get("snapshot_known_as_of"), label="snapshot_known_as_of")

    territories = value.get("territories")
    parties = value.get("parties")
    candidacies = value.get("candidacies")
    programmes = value.get("programmes")
    sources = value.get("source_records")
    if not all(isinstance(item, list) for item in (territories, parties, candidacies, programmes, sources)):
        raise ThreeRegimeError("named input collections must be arrays")

    party_index: dict[str, Mapping[str, Any]] = {}
    label_sets = {"party_name": set(), "abbreviation": set(), "party_symbol": set()}
    for item in parties:
        if not isinstance(item, Mapping):
            raise ThreeRegimeError("named party is not an object")
        party_id = str(item.get("party_id") or "")
        if not party_id or party_id in party_index:
            raise ThreeRegimeError("named party ids are empty or duplicated")
        party_index[party_id] = item
        for field, seen in label_sets.items():
            label = str(item.get(field) or "").strip()
            if not label or label in seen:
                raise ThreeRegimeError(f"named party {field} values are empty or duplicated")
            seen.add(label)
    party_ids = set(party_index)
    if len(party_ids) < 2:
        raise ThreeRegimeError("named input has fewer than two valid parties")

    territory_index: dict[str, Mapping[str, Any]] = {}
    territory_names: set[str] = set()
    expected_ballot_pairs: set[tuple[str, str]] = set()
    for item in territories:
        if not isinstance(item, Mapping):
            raise ThreeRegimeError("named territory is not an object")
        territory_id = str(item.get("territory_id") or "")
        territory_name = str(item.get("territory_name") or "").strip()
        ballot = tuple(map(str, item.get("ballot_party_ids") or []))
        if not territory_id or territory_id in territory_index:
            raise ThreeRegimeError("named territory ids are empty or duplicated")
        if not territory_name or territory_name in territory_names:
            raise ThreeRegimeError("named territory names are empty or duplicated")
        if len(ballot) < 2 or len(set(ballot)) != len(ballot) or not set(ballot).issubset(party_ids):
            raise ThreeRegimeError(f"invalid local ballot_party_ids for {territory_id}")
        territory_index[territory_id] = item
        territory_names.add(territory_name)
        expected_ballot_pairs.update((territory_id, party_id) for party_id in ballot)
    territory_ids = set(territory_index)
    if len(territory_ids) != 92:
        raise ThreeRegimeError("named input must contain exactly 92 unique local territories")

    national = value.get("national_context")
    if not isinstance(national, Mapping):
        raise ThreeRegimeError("named national_context must be an object")
    require_not_after(national.get("known_as_of"), snapshot, label="national_context.known_as_of")
    if national.get("party_specific_material_present") is not False:
        raise ThreeRegimeError("national_context must not bypass per-voter party information diets")
    if national.get("candidate_specific_material_present") is not False:
        raise ThreeRegimeError("national_context must not bypass per-voter candidate information diets")
    if not isinstance(national.get("common_verified_facts"), Mapping):
        raise ThreeRegimeError("national_context.common_verified_facts must be an object")

    source_index: dict[str, Mapping[str, Any]] = {}
    source_dates: dict[str, dt.datetime] = {}
    for item in sources:
        if not isinstance(item, Mapping):
            raise ThreeRegimeError("named source record is not an object")
        source_id = str(item.get("source_record_id") or "")
        cluster = str(item.get("independence_cluster") or "")
        source_class = str(item.get("source_class") or "")
        digest = str(item.get("sha256") or "")
        if not source_id or source_id in source_index or not cluster or not source_class:
            raise ThreeRegimeError("named source ids/clusters/classes are empty or duplicated")
        if not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ThreeRegimeError(f"named source {source_id} has invalid SHA256")
        source_index[source_id] = item
        source_dates[source_id] = require_not_after(
            item.get("known_as_of"), snapshot, label=f"source_records[{source_id}].known_as_of"
        )
    source_ids = set(source_index)
    if len(source_ids) < 2:
        raise ThreeRegimeError("named input requires at least two registered source records")

    verified_pairs: set[tuple[str, str]] = set()
    candidate_ids: set[str] = set()
    for candidacy in candidacies:
        if not isinstance(candidacy, Mapping):
            raise ThreeRegimeError("named candidacy is not an object")
        territory_id = str(candidacy.get("territory_id") or "")
        party_id = str(candidacy.get("party_id") or "")
        candidate_id = str(candidacy.get("candidate_id") or "")
        candidate_name = str(candidacy.get("candidate_name") or "").strip()
        pair = (territory_id, party_id)
        if pair not in expected_ballot_pairs or not candidate_id or not candidate_name:
            raise ThreeRegimeError("named candidacy is outside the certified local ballot or incomplete")
        if candidate_id in candidate_ids:
            raise ThreeRegimeError(f"duplicate named candidate_id {candidate_id}")
        candidate_ids.add(candidate_id)
        if candidacy.get("verification_state") != "VERIFIED_DOUBLE_ENTRY":
            raise ThreeRegimeError("every named candidacy must be VERIFIED_DOUBLE_ENTRY")
        refs = tuple(map(str, candidacy.get("source_record_ids") or []))
        if len(set(refs)) < 2 or not set(refs).issubset(source_ids):
            raise ThreeRegimeError("named candidacy lacks two registered source records")
        clusters = {str(source_index[ref].get("independence_cluster")) for ref in refs}
        if len(clusters) < 2:
            raise ThreeRegimeError("named candidacy sources are not independently clustered")
        candidate_date = require_not_after(
            candidacy.get("known_as_of"), snapshot, label=f"candidacy[{territory_id}|{party_id}].known_as_of"
        )
        if any(source_dates[ref] > candidate_date for ref in refs):
            raise ThreeRegimeError("named candidacy cites a source newer than its own known_as_of")
        profile = candidacy.get("verified_profile") or {}
        if not isinstance(profile, Mapping):
            raise ThreeRegimeError("candidate verified_profile must be an object")
        for field, raw in profile.items():
            if not isinstance(raw, Mapping):
                raise ThreeRegimeError(f"candidate profile field {field} must be an object")
            if raw.get("verification_state") == "VERIFIED":
                profile_refs = set(map(str, raw.get("source_record_ids") or []))
                if not profile_refs or not profile_refs.issubset(source_ids):
                    raise ThreeRegimeError(f"verified candidate profile field {field} lacks registered provenance")
        if pair in verified_pairs:
            raise ThreeRegimeError(f"duplicate named candidacy for {pair}")
        verified_pairs.add(pair)
    if verified_pairs != expected_ballot_pairs:
        missing_pairs = sorted(expected_ballot_pairs - verified_pairs)[:5]
        extra_pairs = sorted(verified_pairs - expected_ballot_pairs)[:5]
        raise ThreeRegimeError(
            f"named candidacy coverage differs from local ballots: missing={missing_pairs} extra={extra_pairs}"
        )

    programme_index: dict[str, Mapping[str, Any]] = {}
    for programme in programmes:
        if not isinstance(programme, Mapping):
            raise ThreeRegimeError("named programme is not an object")
        party_id = str(programme.get("party_id") or "")
        if party_id not in party_ids or party_id in programme_index:
            raise ThreeRegimeError("named programme party ids are invalid or duplicated")
        axes = programme.get("axes")
        if not isinstance(axes, Mapping) or set(map(str, axes)) != set(CANONICAL_PROGRAMME_AXES):
            raise ThreeRegimeError("named programme must contain exactly the canonical 18 axes")
        refs = set(map(str, programme.get("source_record_ids") or []))
        if not refs or not refs.issubset(source_ids):
            raise ThreeRegimeError("named programme lacks registered source records")
        programme_date = require_not_after(
            programme.get("known_as_of"), snapshot, label=f"programme[{party_id}].known_as_of"
        )
        if any(source_dates[ref] > programme_date for ref in refs):
            raise ThreeRegimeError("named programme cites a source newer than its own known_as_of")
        for axis_id, raw in axes.items():
            if not isinstance(raw, Mapping):
                raise ThreeRegimeError(f"programme axis {axis_id} must be an object")
            if raw.get("verification_state") not in ("VERIFIED", "PUBLISHED_PARTY_PROGRAMME"):
                raise ThreeRegimeError(f"programme axis {axis_id} is not verified/published")
        programme_index[party_id] = programme
    if set(programme_index) != party_ids:
        raise ThreeRegimeError("named programme coverage does not match the party panel")

    voter_population = value.get("voter_population") or {}
    if not isinstance(voter_population, Mapping):
        raise ThreeRegimeError("named voter_population must be an object")
    require_not_after(voter_population.get("known_as_of"), snapshot, label="voter_population.known_as_of")
    batches = voter_population.get("batches")
    if not isinstance(batches, list) or not batches:
        raise ThreeRegimeError("named input voter_population.batches is empty")
    batch_territories: set[str] = set()
    batch_ids: set[tuple[str, str]] = set()
    archetype_ids: set[tuple[str, str, str]] = set()
    for batch in batches:
        if not isinstance(batch, Mapping):
            raise ThreeRegimeError("named voter batch is not an object")
        territory_id = str(batch.get("territory_id") or "")
        batch_id = str(batch.get("batch_id") or "")
        voters = batch.get("voters")
        if territory_id not in territory_ids or not batch_id or not isinstance(voters, list) or not voters:
            raise ThreeRegimeError("named voter batch identity or voters are incomplete")
        batch_key = (territory_id, batch_id)
        if batch_key in batch_ids:
            raise ThreeRegimeError(f"duplicate named voter batch {batch_key}")
        batch_ids.add(batch_key)
        batch_territories.add(territory_id)
        for voter in voters:
            if not isinstance(voter, Mapping):
                raise ThreeRegimeError("named voter is not an object")
            archetype_id = str(voter.get("weighted_archetype_id") or voter.get("archetype_id") or "")
            if not archetype_id:
                raise ThreeRegimeError("named voter lacks an archetype id")
            key = (territory_id, batch_id, archetype_id)
            if key in archetype_ids:
                raise ThreeRegimeError(f"duplicate named voter identity {key}")
            archetype_ids.add(key)
    if batch_territories != territory_ids:
        raise ThreeRegimeError("named voter population does not cover all 92 territories")

    conditions = value.get("conditions")
    if not isinstance(conditions, list) or not conditions:
        raise ThreeRegimeError("named input has no conditions")
    condition_ids: list[str] = []
    for item in conditions:
        if not isinstance(item, Mapping):
            raise ThreeRegimeError("named condition is not an object")
        condition_id = str(item.get("condition_id") or "")
        if not condition_id or condition_id in condition_ids:
            raise ThreeRegimeError("named condition ids are invalid or duplicated")
        require_not_after(item.get("known_as_of"), snapshot, label=f"condition[{condition_id}].known_as_of")
        condition_ids.append(condition_id)

    coverage = value.get("coverage") or {}
    declared_ready = coverage.get("all_intended_ballot_cells_verified") is True
    expected_cells = int(coverage.get("intended_ballot_cells") or 0)
    if not declared_ready or expected_cells != len(expected_ballot_pairs):
        raise ThreeRegimeError("named input coverage declaration does not match local ballots")
    if len(verified_pairs) != expected_cells:
        raise ThreeRegimeError("named input verified candidacies do not cover every intended ballot cell")

    return {
        "status": "PASS_NAMED_2026_INPUT_READY",
        "territories": len(territory_ids),
        "parties": len(party_ids),
        "intended_ballot_cells": len(expected_ballot_pairs),
        "verified_candidacies": len(verified_pairs),
        "programme_cards": len(programmes),
        "source_records": len(source_ids),
        "source_independence_clusters": len({str(item.get("independence_cluster")) for item in sources}),
        "voter_batches": len(batches),
        "voter_rows": len(archetype_ids),
        "conditions": len(condition_ids),
        "named_input_sha256": sha256_json(value),
        "main_commit_sha": value.get("main_commit_sha"),
        "snapshot_known_as_of": str(value.get("snapshot_known_as_of")),
    }


def pseudonymize_named_input(value: Mapping[str, Any]) -> dict[str, Any]:
    """Create the internal 2026 twin with identical facts but hidden labels."""
    # CURRENT_VINTAGE mode skips strict final-balllot validation (V7 bridge handles it).
    if value.get("regime_gate") != "P3_CURRENT_VINTAGE_2026":
        validate_named_input(value)
    result = json.loads(json.dumps(value))
    original_parties = [dict(item) for item in value["parties"]]
    original_territories = [dict(item) for item in value["territories"]]
    original_candidates = [dict(item) for item in value["candidacies"]]
    original_sources = [dict(item) for item in value["source_records"]]
    party_map = {
        str(item["party_id"]): "PARTY_" + sha256_bytes(str(item["party_id"]).encode())[:10].upper()
        for item in original_parties
    }
    territory_map = {
        str(item["territory_id"]): "TERR_" + sha256_bytes(str(item["territory_id"]).encode())[:10].upper()
        for item in original_territories
    }
    candidate_map = {
        (str(item["territory_id"]), str(item["party_id"])): (
            "CAND_" + sha256_bytes(
                (str(item["territory_id"]) + "|" + str(item["party_id"])).encode()
            )[:12].upper()
        )
        for item in original_candidates
    }
    source_map = {
        str(item["source_record_id"]): "SRC_" + sha256_bytes(str(item["source_record_id"]).encode())[:12].upper()
        for item in original_sources
    }
    label_map: dict[str, str] = {}
    for item in original_parties:
        pseudo = party_map[str(item["party_id"])]
        for key in ("party_name", "abbreviation", "party_symbol", "national_leader_name"):
            label = str(item.get(key) or "").strip()
            if label:
                label_map[label] = pseudo
    for item in original_territories:
        pseudo = territory_map[str(item["territory_id"])]
        for key in ("territory_name", "region_name"):
            label = str(item.get(key) or "").strip()
            if label:
                label_map[label] = pseudo
    for item in original_candidates:
        label = str(item.get("candidate_name") or "").strip()
        if label:
            label_map[label] = candidate_map[(str(item["territory_id"]), str(item["party_id"]))]

    def scrub(item: Any) -> Any:
        if isinstance(item, Mapping):
            return {str(key): scrub(child) for key, child in item.items()}
        if isinstance(item, list):
            return [scrub(child) for child in item]
        if isinstance(item, str):
            output = item
            for label in sorted(label_map, key=len, reverse=True):
                output = output.replace(label, label_map[label])
            return source_map.get(output, output)
        return item

    result = scrub(result)
    for original, item in zip(original_parties, result["parties"]):
        item["party_id"] = party_map[str(original["party_id"])]
        for key in ("party_name", "party_symbol", "national_leader_name", "abbreviation"):
            item.pop(key, None)
    for original, item in zip(original_territories, result["territories"]):
        item["territory_id"] = territory_map[str(original["territory_id"])]
        item["ballot_party_ids"] = [party_map[str(party_id)] for party_id in original["ballot_party_ids"]]
        for key in ("territory_name", "region_name"):
            item.pop(key, None)
    for original, item in zip(original_candidates, result["candidacies"]):
        original_territory = str(original["territory_id"])
        original_party = str(original["party_id"])
        item["territory_id"] = territory_map[original_territory]
        item["party_id"] = party_map[original_party]
        item["candidate_id"] = candidate_map[(original_territory, original_party)]
        item["source_record_ids"] = [source_map[str(ref)] for ref in original["source_record_ids"]]
        item.pop("candidate_name", None)
        profile = item.get("verified_profile") or {}
        for raw in profile.values():
            if isinstance(raw, MutableMapping) and raw.get("source_record_ids"):
                raw["source_record_ids"] = [source_map.get(str(ref), str(ref)) for ref in raw["source_record_ids"]]
    for original, item in zip(value["programmes"], result["programmes"]):
        item["party_id"] = party_map[str(original["party_id"])]
        item["source_record_ids"] = [source_map[str(ref)] for ref in original["source_record_ids"]]
    for original, item in zip(value["voter_population"]["batches"], result["voter_population"]["batches"]):
        item["territory_id"] = territory_map[str(original["territory_id"])]
        for voter in item.get("voters") or []:
            prior = str(voter.get("prior_vote_or_abstention") or "")
            if prior in party_map:
                voter["prior_vote_or_abstention"] = party_map[prior]
    result["source_records"] = [
        {
            "source_record_id": source_map[str(item["source_record_id"])],
            "source_class": item.get("source_class"),
            "independence_cluster": "CLUSTER_" + sha256_bytes(str(item.get("independence_cluster")).encode())[:10].upper(),
            "known_as_of": item.get("known_as_of"),
            "sha256": item.get("sha256"),
        }
        for item in original_sources
    ]
    result["artifact_id"] = str(result["artifact_id"]) + "__PSEUDONYMIZED_TWIN"
    result["regime"] = REGIME_NAMED_TWIN
    result["real_identity_material_present"] = False
    result["identity_mapping_persisted_in_public_artifact"] = False
    return result


def _named_party_index(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["party_id"]): dict(item) for item in value.get("parties") or []}


def _named_candidate_index(value: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(item["territory_id"]), str(item["party_id"])): dict(item)
        for item in value.get("candidacies") or []
    }


def _named_programme_index(value: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item["party_id"]): dict(item) for item in value.get("programmes") or []}


def _model_visible_verified_value(raw: Mapping[str, Any]) -> dict[str, Any]:
    return {
        str(key): value
        for key, value in raw.items()
        if str(key) not in MODEL_PROVENANCE_KEYS
    }


def _verified_profile_fields(candidate: Mapping[str, Any], depth: str) -> dict[str, Any]:
    profile = candidate.get("verified_profile") or {}
    if not isinstance(profile, Mapping):
        return {}
    fields = []
    for key, raw in profile.items():
        if not isinstance(raw, Mapping):
            continue
        state = raw.get("verification_state")
        value = raw.get("value")
        salience = int(raw.get("salience_rank") or 9999)
        if state != "VERIFIED" or value is None:
            continue
        fields.append((salience, str(key), value))
    fields.sort(key=lambda item: (item[0], item[1]))
    if depth == "SALIENT_VERIFIED_ONLY":
        fields = fields[:3]
    elif depth == "BASIC_VERIFIED_PROFILE":
        fields = fields[:8]
    return {
        key: {"value": value, "verification_state": "VERIFIED"}
        for _, key, value in fields
    }


def _programme_axes_for_diet(programme: Mapping[str, Any], maximum: int) -> dict[str, Any]:
    axes = programme.get("axes") or {}
    ranked = []
    for axis_id, raw in axes.items():
        if not isinstance(raw, Mapping):
            continue
        rank = int(raw.get("national_salience_rank") or 9999)
        state = raw.get("verification_state", "VERIFIED")
        if state not in ("VERIFIED", "PUBLISHED_PARTY_PROGRAMME"):
            continue
        ranked.append((rank, str(axis_id), _model_visible_verified_value(raw)))
    ranked.sort(key=lambda item: (item[0], item[1]))
    return {axis_id: value for _, axis_id, value in ranked[:maximum]}


def voter_named_surface(
    *,
    value: Mapping[str, Any],
    territory_id: str,
    voter: Mapping[str, Any],
) -> dict[str, Any]:
    parties = _named_party_index(value)
    candidates = _named_candidate_index(value)
    programmes = _named_programme_index(value)
    territories = {str(item["territory_id"]): dict(item) for item in value.get("territories") or []}
    territory = territories.get(territory_id)
    if territory is None:
        raise ThreeRegimeError(f"unknown named territory {territory_id}")
    ballot_party_ids = tuple(map(str, territory.get("ballot_party_ids") or []))
    diet = information_diet(voter)
    cards = []
    for party_id in ballot_party_ids:
        party = parties.get(party_id)
        candidate = candidates.get((territory_id, party_id))
        programme = programmes.get(party_id)
        if party is None:
            raise ThreeRegimeError(f"named ballot cell missing party for {territory_id}|{party_id}")
        if candidate is None:
            candidate = {
                "candidate_id": f"UNKNOWN_{territory_id}_{party_id}",
                "candidate_name": None,
                "verification_state": "UNKNOWN_AS_OF_SNAPSHOT",
                "public_familiarity_band": "UNKNOWN",
                "local_viability_band": None,
                "verified_profile": {},
            }
        if programme is None:
            programme = {"axes": {}}
        cards.append(
            {
                "party_id": party_id,
                "party_name": party.get("party_name"),
                "party_abbreviation": party.get("abbreviation"),
                "party_symbol": party.get("party_symbol"),
                "government_status": party.get("government_status"),
                "national_leader_name": (
                    party.get("national_leader_name")
                    if diet["national_leader_visibility"] != "SALIENT_ONLY"
                    or party.get("national_salience") == "HIGH"
                    else None
                ),
                "candidate_id": candidate.get("candidate_id"),
                "candidate_name": candidate.get("candidate_name"),
                "candidate_verification_state": candidate.get("verification_state") or "UNKNOWN_AS_OF_SNAPSHOT",
                "candidate_familiarity": candidate.get("public_familiarity_band", "UNKNOWN"),
                "candidate_verified_profile": _verified_profile_fields(
                    candidate, str(diet["candidate_depth"])
                ),
                "programme_axes": _programme_axes_for_diet(
                    programme, int(diet["programme_axes_visible_max"])
                ),
                "local_viability_band": candidate.get("local_viability_band"),
            }
        )
    return {
        "information_diet": diet,
        "known_electoral_surface": {
            "territory_id": territory_id,
            "ballot_party_ids": list(ballot_party_ids),
            "ballot_cards": cards,
            "source_boundary": "ONLY_FIELDS_VERIFIED_AND_AVAILABLE_BY_SNAPSHOT",
            "provenance_identifiers_visible_to_model": False,
        },
    }


def build_named_environment(
    value: Mapping[str, Any],
    output_root: pathlib.Path,
    *,
    pseudonymized_twin: bool = False,
) -> dict[str, Any]:
    """Build a generic-runner-compatible named 2026 environment directory."""

    if value.get("regime_gate") == "P3_CURRENT_VINTAGE_2026":
        # Current-vintage mode: structural validation without final-balllot constraints.
        # The V7 bridge already validated dates, panels, coverage honesty, and state semantics.
        validation = {
            "status": "PASS_NAMED_2026_INPUT_READY",
            "validation_mode": "P3_CURRENT_VINTAGE_2026",
            "named_input_sha256": sha256_json(value),
            "voter_rows": sum(
                len(b.get("voters") or [])
                for b in (value.get("voter_population") or {}).get("batches") or []
            ),
            "conditions": len(value.get("conditions") or []),
        }
    else:
        validation = validate_named_input(value)
    source = pseudonymize_named_input(value) if pseudonymized_twin else json.loads(json.dumps(value))
    regime = REGIME_NAMED_TWIN if pseudonymized_twin else REGIME_NAMED
    output_root = output_root.expanduser().resolve()
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True)
    contexts_dir = output_root / "contexts"
    voters_dir = output_root / "voter_batches"
    packets_dir = output_root / "packets"
    all_party_ids = tuple(sorted(str(item["party_id"]) for item in source["parties"]))
    territory_index = {str(item["territory_id"]): dict(item) for item in source["territories"]}
    conditions = [dict(item) for item in source["conditions"]]
    work_items = []
    pair_map = {
        "schema_version": SCHEMA_VERSION,
        "goal_id": GOAL_ID,
        "party_map": {},
        "territory_map": {},
        "candidate_map": {},
    }
    if pseudonymized_twin:
        original_parties = [str(item["party_id"]) for item in value["parties"]]
        twin_parties = [str(item["party_id"]) for item in source["parties"]]
        pair_map["party_map"] = dict(zip(original_parties, twin_parties))
        original_territories = [str(item["territory_id"]) for item in value["territories"]]
        twin_territories = [str(item["territory_id"]) for item in source["territories"]]
        pair_map["territory_map"] = dict(zip(original_territories, twin_territories))
        pair_map["candidate_map"] = {
            str(original.get("candidate_id")): str(twin.get("candidate_id"))
            for original, twin in zip(value["candidacies"], source["candidacies"])
        }
    for batch in source["voter_population"]["batches"]:
        territory_id = str(batch["territory_id"])
        batch_id = str(batch["batch_id"])
        territory = territory_index[territory_id]
        party_ids = tuple(map(str, territory.get("ballot_party_ids") or []))
        if len(party_ids) < 2 or not set(party_ids).issubset(set(all_party_ids)):
            raise ThreeRegimeError(f"invalid local ballot in built environment for {territory_id}")
        enriched_voters = []
        for voter in batch["voters"]:
            row = dict(voter)
            row.update(voter_named_surface(value=source, territory_id=territory_id, voter=row))
            enriched_voters.append(row)
        voter_batch = {
            "schema_version": "ATLAS_NAMED_2026_VOTER_BATCH_V1",
            "anonymous_election_id": "MOROCCO_2026_CURRENT",
            "anonymous_territory_id": territory_id,
            "batch_id": batch_id,
            "available_party_ids": list(party_ids),
            "voter_archetypes": enriched_voters,
        }
        voter_path = voters_dir / territory_id / f"{batch_id}.json"
        write_json(voter_path, voter_batch)
        for condition in conditions:
            condition_id = str(condition["condition_id"])
            context = {
                "schema_version": "ATLAS_NAMED_2026_CONTEXT_V1",
                "anonymous_election_id": "MOROCCO_2026_CURRENT",
                "anonymous_territory_id": territory_id,
                "condition_id": condition_id,
                "available_party_ids": list(party_ids),
                "real_identity_material_present": not pseudonymized_twin,
                "target_outcomes_present": False,
                "snapshot_known_as_of": source["snapshot_known_as_of"],
                "territory": territory,
                "national_context": {
                    "known_as_of": source["national_context"]["known_as_of"],
                    "common_verified_facts": source["national_context"]["common_verified_facts"],
                    "party_specific_material_present": False,
                    "candidate_specific_material_present": False,
                },
                "condition": condition,
                "instruction": (
                    "Judge each voter only from that voter's known_electoral_surface. "
                    "Do not borrow details exposed to another voter in the same batch."
                ),
            }
            context_path = contexts_dir / condition_id / f"{territory_id}.json"
            if not context_path.is_file():
                write_json(context_path, context)
            packet = {
                "schema_version": "ATLAS_NAMED_2026_PACKET_V1",
                "anonymous_election_id": "MOROCCO_2026_CURRENT",
                "anonymous_territory_id": territory_id,
                "condition_id": condition_id,
                "batch_id": batch_id,
                "available_party_ids": list(party_ids),
                "context": context,
                "voter_batch": voter_batch,
            }
            packet_path = packets_dir / condition_id / territory_id / f"{batch_id}.json"
            write_json(packet_path, packet)
            work_items.append(
                {
                    "anonymous_election_id": "MOROCCO_2026_CURRENT",
                    "anonymous_territory_id": territory_id,
                    "condition_id": condition_id,
                    "batch_id": batch_id,
                    "context_path": str(context_path.relative_to(output_root)).replace("\\", "/"),
                    "voter_batch_path": str(voter_path.relative_to(output_root)).replace("\\", "/"),
                    "packet_audit_path": str(packet_path.relative_to(output_root)).replace("\\", "/"),
                    "output_path": str(
                        pathlib.PurePosixPath("outputs")
                        / "MOROCCO_2026_CURRENT"
                        / condition_id
                        / territory_id
                        / f"{batch_id}.jsonl"
                    ),
                }
            )
    manifest = {
        "schema_version": "ATLAS_NAMED_2026_ENVIRONMENT_MANIFEST_V1",
        "goal_id": GOAL_ID,
        "regime": regime,
        "status": "PASS_REALISTIC_2026_NAMED_ENVIRONMENT_READY",
        "main_commit_sha": source["main_commit_sha"],
        "named_source_gate": validation["status"],
        "real_identity_material_present": not pseudonymized_twin,
        "target_outcomes_present": False,
        "candidate_fabrication_used": False,
        "partial_roster_used": False,
        "per_voter_information_diets_present": True,
        "pseudonymized_twin_buildable": True,
        "work_items": len(work_items),
        "voter_rows_per_condition": validation["voter_rows"],
        "conditions": validation["conditions"],
        "source_input_sha256": validation["named_input_sha256"],
    }
    write_json(output_root / "named_2026_environment_manifest.json", manifest)
    write_json(output_root / "work_manifest.json", {"work_items": work_items})
    if pseudonymized_twin:
        write_json(output_root / "named_2026_pair_map.json", pair_map)
    return manifest

def verify_freeze_manifest(repo_root: pathlib.Path, manifest_path: pathlib.Path) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    files = manifest.get("frozen_files")
    if not isinstance(files, Mapping) or not files:
        raise ThreeRegimeError("freeze manifest has no frozen_files mapping")
    failures = []
    for relative, expected in sorted(files.items()):
        path = repo_root / relative
        if not path.is_file():
            failures.append({"path": relative, "reason": "MISSING"})
            continue
        actual = sha256_file(path)
        if actual != expected:
            failures.append({"path": relative, "reason": "SHA256_MISMATCH", "expected": expected, "actual": actual})
    if failures:
        raise ThreeRegimeError(f"freeze verification failed: {failures[:5]}")
    return {
        "status": "PASS_THREE_REGIME_FREEZE_VERIFIED",
        "manifest": str(manifest_path),
        "files_verified": len(files),
        "parent_branch_head": manifest.get("parent_branch_head"),
        "registered_main_sha": manifest.get("registered_main_sha"),
    }


def iter_jsonl(path: pathlib.Path) -> Iterable[dict[str, Any]]:
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ThreeRegimeError(f"invalid JSONL {path}:{number}: {exc}") from exc
        if not isinstance(value, Mapping):
            raise ThreeRegimeError(f"JSONL row is not an object at {path}:{number}")
        yield dict(value)


def entropy(probabilities: Mapping[str, Any]) -> float:
    import math

    result = 0.0
    for value in probabilities.values():
        probability = float(value)
        if probability > 0:
            result -= probability * math.log(probability, 2)
    return result


def summarize_output_rows(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ThreeRegimeError("cannot summarize an empty output set")
    top_counts: dict[str, int] = {}
    turnout = []
    margins = []
    entropies = []
    ties = 0
    loyalty = 0
    switches = 0
    for row in rows:
        probabilities = row.get("conditional_party_probabilities")
        if not isinstance(probabilities, Mapping) or len(probabilities) < 2:
            raise ThreeRegimeError("output row has no party probability simplex")
        ordered = sorted(
            ((str(party), float(value)) for party, value in probabilities.items()),
            key=lambda pair: (-pair[1], pair[0]),
        )
        top_counts[ordered[0][0]] = top_counts.get(ordered[0][0], 0) + 1
        margin = ordered[0][1] - ordered[1][1]
        margins.append(margin)
        if abs(margin) <= 1e-12:
            ties += 1
        turnout.append(float(row.get("turnout_probability") or 0.0))
        entropies.append(entropy(probabilities))
        prior = row.get("prior_vote_or_abstention")
        if prior is not None:
            if str(prior) == ordered[0][0]:
                loyalty += 1
            elif str(prior) != "ABSTAIN":
                switches += 1
    count = len(rows)
    return {
        "rows": count,
        "mean_turnout_probability": sum(turnout) / count,
        "mean_top_two_margin": sum(margins) / count,
        "mean_party_entropy_bits": sum(entropies) / count,
        "exact_tie_rows": ties,
        "exact_tie_rate": ties / count,
        "top_choice_counts": dict(sorted(top_counts.items())),
        "loyalty_rows_where_prior_available": loyalty,
        "switch_rows_where_prior_available": switches,
    }
