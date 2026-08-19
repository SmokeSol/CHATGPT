# -*- coding: utf-8 -*-
"""Build frozen archetype-to-archetype *exposure distributions*.

Important: edges are NOT claims that two synthetic archetypes are literal
relatives, colleagues or neighbours.  A row describes which archetype strata
would plausibly supply social exposure to a representative member of the
source stratum.

The builder sees voter cards only.  It never opens decision outputs or
historical outcomes, and therefore cannot tune the graph to electoral results.
"""
from __future__ import division
import argparse
import json
import math
import os

try:
    from .common import (
        RELATIONS, archetype_id, clip, read_json, sha256_file,
        stable_unit, write_json,
    )
except ImportError:
    from common import (
        RELATIONS, archetype_id, clip, read_json, sha256_file,
        stable_unit, write_json,
    )

DEFAULT_TOP_K = {"family": 4, "work": 6, "neighborhood": 8}
DEFAULT_MIN_SCORE = {"family": 0.34, "work": 0.32, "neighborhood": 0.28}


def _num(v, key, default=0.5):
    x = v.get(key)
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(default)


def _close(a, b, scale):
    return clip(1.0 - abs(float(a) - float(b)) / float(scale))


def _eq(a, b, missing=("MISSING", "UNKNOWN", "NOT_FOUND", None, "")):
    if a in missing or b in missing:
        return 0.0
    return 1.0 if a == b else 0.0


def _prefix_eq(a, b):
    if not a or not b:
        return 0.0
    aa = str(a).split(" - ")[0].strip()
    bb = str(b).split(" - ")[0].strip()
    return 1.0 if aa == bb else 0.0


def _age(v):
    x = v.get("age_years")
    if isinstance(x, (int, float)):
        return float(x)
    bands = {"18_24": 21, "25_34": 29, "35_44": 39, "45_59": 51, "60_PLUS": 68}
    return float(bands.get(v.get("age_band"), 40))


def _household_family(v):
    h = v.get("household_type") or ""
    if "seule personne" in h:
        return "single"
    if "Mère avec" in h or "Père avec" in h:
        return "single_parent"
    if "élargi" in h or "composite" in h or "polygame" in h:
        return "extended"
    if "Couple" in h:
        return "nuclear"
    return str(h) if h else "unknown"


def _qv(v):
    return _num(v, "latent_national_quintile", 0.6)


def _ses(v):
    return _num(v, "latent_ses_decile", 0.5)


def _education_rank(v):
    return {
        "Aucun niveau d'études": 0.0,
        "Préscolaire": 0.12,
        "Primaire": 0.30,
        "Secondaire collégial": 0.52,
        "Secondaire qualifiant": 0.74,
        "Supérieur": 1.0,
    }.get(v.get("education_level"), 0.30)


def _is_employed(v):
    return v.get("activity_status") == "ACTIVE_EMPLOYED"


def _family_score(a, b):
    # Homophily on household stratum + socioeconomic environment, with a
    # broad age kernel that permits spouse/peer as well as inter-generation exposure.
    age_gap = abs(_age(a) - _age(b))
    age_fit = max(
        math.exp(-age_gap / 16.0),
        0.82 * math.exp(-abs(age_gap - 27.0) / 15.0),
    )
    hh_a = max(1.0, _num(a, "household_size", 5.0))
    hh_b = max(1.0, _num(b, "household_size", 5.0))
    marital = _eq(a.get("marital_status"), b.get("marital_status"))
    return (
        0.25 * _eq(_household_family(a), _household_family(b))
        + 0.18 * _close(_qv(a), _qv(b), 0.55)
        + 0.13 * _eq(a.get("urban_rural"), b.get("urban_rural"))
        + 0.14 * _close(hh_a, hh_b, 6.0)
        + 0.10 * marital
        + 0.15 * age_fit
        + 0.05 * (1.0 - _eq(a.get("sex"), b.get("sex")))
    )


def _work_score(a, b):
    if not (_is_employed(a) and _is_employed(b)):
        return 0.0
    sector = _prefix_eq(a.get("industry_sector"), b.get("industry_sector"))
    occupation = _prefix_eq(a.get("occupation_group"), b.get("occupation_group"))
    profession = _eq(a.get("professional_status"), b.get("professional_status"))
    return (
        0.34 * sector
        + 0.14 * occupation
        + 0.08 * profession
        + 0.14 * _close(_qv(a), _qv(b), 0.55)
        + 0.10 * _eq(a.get("urban_rural"), b.get("urban_rural"))
        + 0.10 * _close(_education_rank(a), _education_rank(b), 0.8)
        + 0.10 * _close(_age(a), _age(b), 35.0)
    )


def _neighborhood_score(a, b):
    return (
        0.34 * _eq(a.get("urban_rural"), b.get("urban_rural"))
        + 0.24 * _close(_qv(a), _qv(b), 0.55)
        + 0.16 * _close(_ses(a), _ses(b), 0.65)
        + 0.09 * _close(_age(a), _age(b), 45.0)
        + 0.08 * _eq(_household_family(a), _household_family(b))
        + 0.05 * _prefix_eq(a.get("industry_sector"), b.get("industry_sector"))
        + 0.04 * _close(_education_rank(a), _education_rank(b), 1.0)
    )


SCORE_FN = {
    "family": _family_score,
    "work": _work_score,
    "neighborhood": _neighborhood_score,
}


def _relation_targets(voters, source_i, relation, seed, top_k, min_score):
    src = voters[source_i]
    scored = []
    for j, target in enumerate(voters):
        if j == source_i:
            continue
        score = SCORE_FN[relation](src, target)
        if score < min_score:
            continue
        # Stable tie-breaker only; it never rescues an incompatible pair.
        jitter = stable_unit(seed, relation, archetype_id(src), archetype_id(target)) * 1e-7
        scored.append((score + jitter, j))
    scored.sort(key=lambda x: (-x[0], x[1]))
    selected = scored[:top_k]
    if not selected:
        return []
    raw = [max(1e-9, s) for s, _ in selected]
    total = sum(raw)
    return [{"i": j, "w": round(s / total, 12)} for s, (_, j) in zip(raw, selected)]


def build_graph(voters, source_key, seed="ATLAS_SOCIAL_V1", top_k=None, min_score=None):
    top_k = dict(DEFAULT_TOP_K, **(top_k or {}))
    min_score = dict(DEFAULT_MIN_SCORE, **(min_score or {}))
    ids = [archetype_id(v) for v in voters]
    if len(set(ids)) != len(ids):
        raise ValueError("weighted_archetype_id must be unique inside a voter batch")
    nodes = []
    for i, voter in enumerate(voters):
        rel = {}
        for r in RELATIONS:
            rel[r] = _relation_targets(
                voters, i, r, seed, int(top_k[r]), float(min_score[r])
            )
        nodes.append({
            "id": ids[i],
            "relations": rel,
        })
    return {
        "schema_version": "ATLAS_SOCIAL_GRAPH_V1",
        "semantics": "archetype_exposure_distribution_not_literal_person_edges",
        "source_key": source_key,
        "seed": seed,
        "top_k": top_k,
        "min_score": min_score,
        "nodes": nodes,
    }


def shuffled_placebo(graph, seed="ATLAS_SOCIAL_SHUFFLE_V1"):
    """Preserve each node's relation-specific out-degree and edge weights.

    Targets are reassigned deterministically within the same frozen graph.
    This is a topology placebo; it does not claim to preserve in-degree.
    """
    n = len(graph["nodes"])
    out = {
        "schema_version": graph["schema_version"],
        "semantics": "placebo_reassigned_targets_preserving_out_degree_and_weights",
        "source_key": graph["source_key"],
        "seed": seed,
        "top_k": graph.get("top_k", {}),
        "min_score": graph.get("min_score", {}),
        "nodes": [],
    }
    for i, node in enumerate(graph["nodes"]):
        rel_out = {}
        for relation in RELATIONS:
            src_edges = node["relations"].get(relation, [])
            k = len(src_edges)
            if not k:
                rel_out[relation] = []
                continue
            candidates = [j for j in range(n) if j != i]
            candidates.sort(
                key=lambda j: stable_unit(seed, graph["source_key"], relation, i, j)
            )
            chosen = candidates[:k]
            rel_out[relation] = [
                {"i": j, "w": edge["w"]} for j, edge in zip(chosen, src_edges)
            ]
        out["nodes"].append({"id": node["id"], "relations": rel_out})
    return out


def validate_graph(graph):
    errors = []
    nodes = graph.get("nodes") or []
    ids = [str(n.get("id")) for n in nodes]
    if len(ids) != len(set(ids)):
        errors.append("duplicate node ids")
    for i, node in enumerate(nodes):
        for relation in RELATIONS:
            edges = node.get("relations", {}).get(relation, [])
            targets = []
            total = 0.0
            for edge in edges:
                j = edge.get("i")
                w = edge.get("w")
                if not isinstance(j, int) or j < 0 or j >= len(nodes):
                    errors.append("node %d %s invalid target" % (i, relation))
                    continue
                if j == i:
                    errors.append("node %d %s self exposure" % (i, relation))
                if j in targets:
                    errors.append("node %d %s duplicate target" % (i, relation))
                targets.append(j)
                try:
                    wf = float(w)
                except (TypeError, ValueError):
                    errors.append("node %d %s invalid weight" % (i, relation))
                    continue
                if wf <= 0:
                    errors.append("node %d %s non-positive weight" % (i, relation))
                total += wf
            if edges and abs(total - 1.0) > 1e-8:
                errors.append("node %d %s weights sum %.12f" % (i, relation, total))
    return errors


def _unique_batches(work_manifest):
    seen = []
    present = set()
    for item in work_manifest["work_items"]:
        path = item["voter_batch_path"]
        if path not in present:
            present.add(path)
            seen.append(path)
    return seen


def cli(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("env", help="frozen experiment environment containing work_manifest.json")
    ap.add_argument("dest", help="output directory for frozen social graphs")
    ap.add_argument("--seed", default="ATLAS_SOCIAL_V1")
    ap.add_argument("--placebo-seed", default="ATLAS_SOCIAL_SHUFFLE_V1")
    args = ap.parse_args(argv)

    wm_path = os.path.join(args.env, "work_manifest.json")
    wm = read_json(wm_path)
    graph_dir = os.path.join(args.dest, "graphs")
    placebo_dir = os.path.join(args.dest, "graphs_shuffle")
    os.makedirs(graph_dir, exist_ok=True)
    os.makedirs(placebo_dir, exist_ok=True)

    index = {
        "schema_version": "ATLAS_SOCIAL_GRAPH_INDEX_V1",
        "builder_seed": args.seed,
        "placebo_seed": args.placebo_seed,
        "work_manifest_sha256": sha256_file(wm_path),
        "graphs": {},
    }

    for batch_path in _unique_batches(wm):
        abs_batch = os.path.join(args.env, batch_path)
        batch = read_json(abs_batch)
        voters = batch["voter_archetypes"]
        key = sha256_file(abs_batch)[:20]
        graph = build_graph(voters, source_key=batch_path, seed=args.seed)
        errors = validate_graph(graph)
        if errors:
            raise ValueError("%s: %s" % (batch_path, "; ".join(errors)))
        placebo = shuffled_placebo(graph, args.placebo_seed)
        errors = validate_graph(placebo)
        if errors:
            raise ValueError("%s placebo: %s" % (batch_path, "; ".join(errors)))
        gname = key + ".json"
        pname = key + ".json"
        gpath = os.path.join(graph_dir, gname)
        ppath = os.path.join(placebo_dir, pname)
        write_json(gpath, graph)
        write_json(ppath, placebo)
        index["graphs"][batch_path] = {
            "voter_batch_sha256": sha256_file(abs_batch),
            "graph": "graphs/" + gname,
            "graph_sha256": sha256_file(gpath),
            "shuffle_graph": "graphs_shuffle/" + pname,
            "shuffle_graph_sha256": sha256_file(ppath),
            "nodes": len(voters),
        }

    write_json(os.path.join(args.dest, "graph_index.json"), index, pretty=True)
    print("PASS_SOCIAL_GRAPH_FROZEN %d batches" % len(index["graphs"]))


if __name__ == "__main__":
    cli()
