from __future__ import annotations
import hashlib, json, pathlib, re, subprocess
from typing import Any, Mapping

BRIDGE_ID = "M26_AS_MAIN_BRIDGE_V1"
SCHEMA_VERSION = "1.0"
REGISTERED_MAIN_SHA = "4df897c356d3f0c36832405c7fcfc7f8f0cd6de2"
BLIND_PATHS = {
    "development": "morocco26/data/goal100/e_reason/blind/development/blind_bundle.json",
    "holdout": "morocco26/data/goal100/e_reason/blind/holdout/blind_bundle.json",
}
CONTROL_PATHS = (
    "morocco26/data/goal100/e_reason/e_reason_historical_cutoffs_v1.json",
    "morocco26/data/goal100/e_reason/e_reason_information_set_v1.json",
    "morocco26/data/goal100/e_reason/e_reason_leakage_control_v1.json",
)
FORBIDDEN_FIELD_TOKENS = (
    "outcome", "actual_vote", "actual_share", "winner", "seat_result",
    "target_result", "post_election", "unseal", "score_against",
)
FORBIDDEN_TEXT_PATTERNS = (
    re.compile(r"\b(2016|2021)\b"),
    re.compile(r"\b(PJD|RNI|PAM|PI|PPS|USFP|UC|MP)\b", re.I),
)

class BridgeError(RuntimeError):
    pass

def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

def sha256_json(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))

def write_json(path: pathlib.Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")

def git(repo_root: pathlib.Path, *args: str) -> bytes:
    proc = subprocess.run(["git", "-C", str(repo_root), *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    if proc.returncode:
        raise BridgeError(proc.stderr.decode("utf-8", "replace").strip() or f"git {' '.join(args)} failed")
    return proc.stdout

def validate_commit(repo_root: pathlib.Path, sha: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise BridgeError("--main-sha must be an exact 40-hex commit SHA; floating refs are forbidden")
    resolved = git(repo_root, "rev-parse", f"{sha}^{{commit}}").decode().strip()
    if resolved != sha:
        raise BridgeError("--main-sha did not resolve to itself")
    return resolved

def show_bytes(repo_root: pathlib.Path, sha: str, path: str) -> bytes:
    if any(token in path.lower() for token in ("outcome", "unseal", "score", "result_2021", "result_2016")):
        raise BridgeError(f"forbidden source path: {path}")
    return git(repo_root, "show", f"{sha}:{path}")

def show_json(repo_root: pathlib.Path, sha: str, path: str):
    raw = show_bytes(repo_root, sha, path)
    try:
        return json.loads(raw), sha256_bytes(raw)
    except json.JSONDecodeError as exc:
        raise BridgeError(f"invalid JSON at {path}: {exc}") from exc

def assert_no_forbidden_keys(value: Any, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            lower = str(key).lower()
            if any(token in lower for token in FORBIDDEN_FIELD_TOKENS):
                raise BridgeError(f"forbidden field in public overlay: {path}.{key}")
            assert_no_forbidden_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            assert_no_forbidden_keys(child, f"{path}[{i}]")

def leak_scan(value: Any) -> list[str]:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True)
    return [p.pattern for p in FORBIDDEN_TEXT_PATTERNS if p.search(text)]
