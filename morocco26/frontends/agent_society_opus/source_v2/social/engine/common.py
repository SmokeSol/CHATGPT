# -*- coding: utf-8 -*-
"""Shared primitives for the ATLAS social-influence experiment.

This module intentionally depends only on the Python standard library.  It
contains no outcome access, no party-name mapping and no network calls.
"""
from __future__ import division
import hashlib
import json
import math
import os

RELATIONS = ("family", "work", "neighborhood")
EPS = 1e-12


def clip(x, lo=0.0, hi=1.0):
    return lo if x < lo else hi if x > hi else x


def logit(p):
    p = clip(float(p), 1e-9, 1.0 - 1e-9)
    return math.log(p / (1.0 - p))


def sigmoid(x):
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def normalize(prob):
    if isinstance(prob, dict):
        keys = list(prob)
        vals = [max(EPS, float(prob[k])) for k in keys]
        s = sum(vals)
        return {k: v / s for k, v in zip(keys, vals)}
    vals = [max(EPS, float(v)) for v in prob]
    s = sum(vals)
    return [v / s for v in vals]


def entropy01(prob):
    vals = list(normalize(prob).values()) if isinstance(prob, dict) else normalize(prob)
    n = len(vals)
    if n <= 1:
        return 0.0
    h = -sum(p * math.log(max(EPS, p)) for p in vals)
    return clip(h / math.log(n))


def canonical_json(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def sha256_text(text):
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def stable_u64(*parts):
    raw = "\x1f".join(str(p) for p in parts).encode("utf-8")
    return int(hashlib.sha256(raw).hexdigest()[:16], 16)


def stable_unit(*parts):
    return stable_u64(*parts) / float(0xFFFFFFFFFFFFFFFF)


def read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj, pretty=False):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(
            obj, fh, ensure_ascii=False, sort_keys=bool(pretty),
            indent=2 if pretty else None,
            separators=None if pretty else (",", ":"),
        )
        fh.write("\n")


def read_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception as exc:
                raise ValueError("%s:%d invalid JSON: %s" % (path, lineno, exc))
    return out


def write_jsonl(path, rows):
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(canonical_json(row) + "\n")


def archetype_id(voter):
    value = voter.get("weighted_archetype_id") or voter.get("archetype_id")
    if not value:
        raise ValueError("voter archetype missing weighted_archetype_id")
    return str(value)


def row_id(row):
    value = row.get("weighted_archetype_id") or row.get("archetype_id")
    if not value:
        raise ValueError("decision row missing weighted_archetype_id")
    return str(value)


def party_keys(rows):
    keys = None
    for row in rows:
        p = row.get("conditional_party_probabilities")
        if not isinstance(p, dict) or not p:
            raise ValueError("decision row missing conditional_party_probabilities")
        ks = tuple(sorted(p))
        if keys is None:
            keys = ks
        elif ks != keys:
            raise ValueError("party pseudonym set differs inside one work item")
    return keys or tuple()


def ensure_rows_align(rows, graph):
    if len(rows) != len(graph["nodes"]):
        raise ValueError("row count %d != graph node count %d" % (len(rows), len(graph["nodes"])))
    g_ids = [str(n["id"]) for n in graph["nodes"]]
    r_ids = [row_id(r) for r in rows]
    if r_ids != g_ids:
        raise ValueError("baseline row order does not match frozen graph node order")
    party_keys(rows)
