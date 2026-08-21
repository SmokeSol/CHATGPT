from __future__ import annotations

import csv
import io
import json
import pathlib
import subprocess
from typing import Any, Iterator, Mapping, Sequence

from .contracts import BallotType, CandidateRecord, CandidateState, ContractError


class MainAdapterError(ContractError):
    pass


class GitSnapshotReader:
    """Read an immutable `main` tree. Floating working-tree reads are forbidden."""
    def __init__(self, repo_root: pathlib.Path, ref: str):
        self.repo_root = repo_root.resolve()
        self.commit_sha = self._git("rev-parse", ref).strip()
        if len(self.commit_sha) != 40:
            raise MainAdapterError("main ref did not resolve to a commit SHA")

    def _git(self, *args: str, binary: bool = False):
        proc = subprocess.run(["git", "-C", str(self.repo_root), *args], capture_output=True, text=not binary, check=False)
        if proc.returncode:
            err = proc.stderr.decode(errors="replace") if binary else proc.stderr
            raise MainAdapterError(err.strip())
        return proc.stdout

    def paths(self, prefix: str = "morocco26/") -> list[str]:
        return [x for x in str(self._git("ls-tree", "-r", "--name-only", self.commit_sha, prefix)).splitlines() if x]

    def read_bytes(self, path: str) -> bytes:
        return bytes(self._git("show", f"{self.commit_sha}:{path}", binary=True))


def discover_sources(reader: GitSnapshotReader) -> dict[str, list[str]]:
    buckets = {"candidate": [], "program": [], "territory": [], "registered_electorate": []}
    for path in reader.paths():
        lower = path.lower(); suffix = pathlib.PurePosixPath(path).suffix.lower()
        if suffix not in {".json", ".jsonl", ".csv"}: continue
        if any(x in lower for x in ("candidate_ledger", "ballot_roster", "candidate_intelligence", "candidate_coverage", "candidat")): buckets["candidate"].append(path)
        if any(x in lower for x in ("program", "programme", "manifesto", "party_offer")): buckets["program"].append(path)
        if any(x in lower for x in ("territory_crosswalk", "circonscriptions_raw", "constituencies", "territor", "circonscription")): buckets["territory"].append(path)
        if any(x in lower for x in ("registered_elector", "electoral_roll", "inscrits", "electeurs")): buckets["registered_electorate"].append(path)
    return {k: sorted(set(v)) for k, v in buckets.items()}


def source_inventory(reader: GitSnapshotReader) -> dict[str, Any]:
    sources = discover_sources(reader)
    records = []
    for kind, paths in sources.items():
        for path in paths:
            payload = reader.read_bytes(path)
            import hashlib
            records.append({"kind": kind, "path": path, "sha256": hashlib.sha256(payload).hexdigest(), "bytes": len(payload)})
    return {"schema_version": "AGENT_SOCIETY_MAIN_SOURCE_INVENTORY_V4", "main_commit_sha": reader.commit_sha, "sources": records, "floating_reads": False}


def _walk_records(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, list):
        for item in value: yield from _walk_records(item)
    elif isinstance(value, dict):
        keys = {str(k).lower() for k in value}
        if keys.intersection({"party", "party_id", "party_code", "parti"}) and keys.intersection({"territory_id", "territory", "constituency", "circonscription", "district"}):
            yield value
        for nested in value.values():
            if isinstance(nested, (dict, list)): yield from _walk_records(nested)


def _records(payload: bytes, path: str) -> list[Mapping[str, Any]]:
    suffix = pathlib.PurePosixPath(path).suffix.lower()
    if suffix == ".json": return list(_walk_records(json.loads(payload.decode())))
    if suffix == ".jsonl":
        result=[]
        for line in payload.decode().splitlines():
            if line.strip(): result.extend(_walk_records(json.loads(line)))
        return result
    if suffix == ".csv": return list(csv.DictReader(io.StringIO(payload.decode("utf-8-sig"))))
    return []


def _first(row: Mapping[str, Any], keys: Sequence[str]):
    lower={str(k).lower():v for k,v in row.items()}
    return next((lower[k] for k in keys if k in lower and lower[k] not in (None,"")), None)


def candidate_records(reader: GitSnapshotReader, *, as_of: str) -> tuple[list[CandidateRecord], list[dict[str, Any]]]:
    """Best-effort schema adapter; unsupported/unresolved rows stay outside the model surface."""
    records: dict[tuple[str,str,BallotType], CandidateRecord] = {}; unresolved=[]
    for path in discover_sources(reader)["candidate"]:
        try: rows=_records(reader.read_bytes(path), path)
        except Exception: continue
        for row in rows:
            party=_first(row,("party","party_id","party_code","parti")); territory=_first(row,("territory_id","territory","constituency","circonscription","district")); name=_first(row,("candidate_name","candidate","name","nom","full_name","tete_de_liste"))
            if not party or not territory: continue
            status=str(_first(row,("status","candidate_status","nomination_status","state")) or ("DECLARED" if name else "UNKNOWN")).upper().replace(" ","_")
            aliases={"REGISTERED":"OFFICIAL","CONFIRMED":"OFFICIAL","DECLARED_ACTIVE":"DECLARED","ANNOUNCED":"DECLARED","PENDING_NOMINATION":"UNKNOWN","PENDING":"UNKNOWN","SOURCE_GAP":"UNKNOWN","REPORTED_UNCONFIRMED":"REPORTED","RUMORED":"REPORTED","ABSENT":"NO_LIST"}
            status=aliases.get(status,status)
            if status not in CandidateState.__members__: status="UNKNOWN"
            state=CandidateState[status]
            if state in {CandidateState.OFFICIAL,CandidateState.DECLARED,CandidateState.REPORTED} and not name: state=CandidateState.UNKNOWN
            known=str(_first(row,("source_date","known_at","verified_at","as_of","published_at","updated_at")) or "")[:10] or None
            source_id=str(_first(row,("source_ref","source_url","url","source")) or path)
            sources=({"source_id":source_id,"known_at":known or as_of,"tier":str(row.get("source_tier") or "UNSPECIFIED")},) if state is not CandidateState.UNKNOWN else ()
            rec=CandidateRecord(str(territory),str(party).upper(),BallotType.REGIONAL if "REG" in str(row.get("ballot_type") or row.get("ballot") or "LOCAL").upper() else BallotType.LOCAL,state,str(name).strip() if name and state not in {CandidateState.UNKNOWN,CandidateState.NO_LIST} else None,known,sources,{})
            try: rec.validate(as_of=as_of)
            except ContractError as exc:
                unresolved.append({"path":path,"party":party,"territory":territory,"reason":str(exc)}); continue
            key=(rec.territory_id,rec.party_id,rec.ballot); current=records.get(key)
            rank={CandidateState.OFFICIAL:5,CandidateState.DECLARED:4,CandidateState.REPORTED:3,CandidateState.UNKNOWN:2,CandidateState.NO_LIST:1}
            if current is None or rank[rec.state] > rank[current.state]: records[key]=rec
    return sorted(records.values(),key=lambda r:(r.territory_id,r.ballot.value,r.party_id)),unresolved
