from __future__ import annotations
import json, pathlib, zipfile
from typing import Any
from main_bridge_core import BridgeError, sha256_bytes, sha256_json

def extract_environment(bundle: pathlib.Path, temp_root: pathlib.Path) -> pathlib.Path:
    bundle = bundle.expanduser().resolve()
    if bundle.is_dir():
        return bundle
    if not bundle.is_file() or bundle.suffix.lower() != ".zip":
        raise BridgeError("--environment must be the full-environment ZIP or extracted directory")
    root = temp_root / "environment"
    root.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(bundle) as zf:
        for info in zf.infolist():
            p = pathlib.PurePosixPath(info.filename)
            if p.is_absolute() or ".." in p.parts:
                raise BridgeError(f"unsafe ZIP member: {info.filename}")
        zf.extractall(root)
    return root

def find_context_files(root: pathlib.Path):
    hits = sorted(root.rglob("contexts/*/*/*.json"))
    if not hits:
        hits = sorted(p for p in root.rglob("*.json") if "contexts" in p.parts)
    if not hits:
        raise BridgeError("no full-environment context files found")
    return hits

def collect_environment(root: pathlib.Path) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    by_key, hashes = {}, {}
    for path in find_context_files(root):
        raw = path.read_bytes()
        obj = json.loads(raw)
        eid = str(obj.get("anonymous_election_id", ""))
        tid = str(obj.get("anonymous_territory_id", ""))
        if not eid or not tid:
            raise BridgeError(f"context missing anonymous ids: {path}")
        key = f"{eid}|{tid}"
        if key not in by_key:
            by_key[key], hashes[key] = obj, sha256_bytes(raw)
        elif by_key[key].get("available_party_ids") != obj.get("available_party_ids"):
            raise BridgeError(f"party panel differs across conditions for {key}")
    eids = sorted({k.split("|", 1)[0] for k in by_key})
    territories = {
        eid: sorted(k.split("|", 1)[1] for k in by_key if k.startswith(eid + "|"))
        for eid in eids
    }
    return by_key, {
        "context_count": len(by_key),
        "anonymous_election_ids": eids,
        "territories_per_election": {eid: len(v) for eid, v in territories.items()},
        "context_signature_sha256": sha256_json(hashes),
    }
