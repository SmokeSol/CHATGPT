# -*- coding: utf-8 -*-
"""Bounded LLM social-reasoning layer.

The LLM is never allowed to replace the frozen private decision engine.  It
receives only:
  * the agent's already-computed private Rk state,
  * aggregate social exposures produced from the frozen graph,
  * non-political synthetic profile descriptors.

It returns bounded *social adjustments*.  The runner validates and clips those
adjustments before applying them.  No historical outcome is available here.
"""
from __future__ import division
import argparse
import concurrent.futures
import copy
import hashlib
import json
import math
import os
import urllib.error
import urllib.request

try:
    from .common import (
        RELATIONS, canonical_json, clip, entropy01, logit, normalize,
        read_json, read_jsonl, row_id, sha256_file, sigmoid, stable_u64,
        write_jsonl,
    )
    from .deterministic_social import exposure_snapshot
except ImportError:
    from common import (
        RELATIONS, canonical_json, clip, entropy01, logit, normalize,
        read_json, read_jsonl, row_id, sha256_file, sigmoid, stable_u64,
        write_jsonl,
    )
    from deterministic_social import exposure_snapshot


ALLOWED_RESPONSES = {
    "RESIST", "REINFORCE", "ADOPT", "CONFLICTED", "WITHDRAW", "NO_CHANGE"
}
ALLOWED_REASONS = {
    "FAMILY_ALIGNMENT", "FAMILY_CONFLICT",
    "WORK_ALIGNMENT", "WORK_CONFLICT",
    "NEIGHBORHOOD_ALIGNMENT", "NEIGHBORHOOD_CONFLICT",
    "PRIVATE_CONVICTION_RESISTS", "CROSS_PRESSURE", "SOCIAL_REINFORCEMENT",
    "PARTICIPATION_ENCOURAGED", "PARTICIPATION_DISCOURAGED",
}
PROFILE_FIELDS = (
    "age_band", "age_years", "sex", "urban_rural", "education_level",
    "activity_status", "latent_national_quintile", "household_type",
    "household_size", "marital_status", "industry_sector",
    "professional_status", "occupation_group",
)


def _request_id(item, agent_id, round_name):
    raw = "|".join([
        item["anonymous_election_id"], item["anonymous_territory_id"],
        item["condition_id"], agent_id, round_name
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _profile(voter):
    return {k: voter.get(k) for k in PROFILE_FIELDS}


def _exposure_payload(rows, graph, i):
    parties, turnout = exposure_snapshot(rows, graph, i)
    out = {}
    for relation in RELATIONS:
        edges = graph["nodes"][i]["relations"].get(relation, [])
        out[relation] = {
            "contacts": len(edges),
            "party_distribution": parties[relation],
            "turnout_probability": turnout[relation],
        }
    return out


def build_request(item, voter, row, rows, graph, i, lambdas, round_name, system_prompt):
    rid = _request_id(item, row_id(row), round_name)
    payload = {
        "request_id": rid,
        "round": round_name,
        "agent_id": row_id(row),
        "profile": _profile(voter),
        "private_state": {
            "turnout_probability": row["turnout_probability"],
            "party_distribution": row["conditional_party_probabilities"],
            "reason_codes": row.get("reason_codes", []),
        },
        "social_exposure": _exposure_payload(rows, graph, i),
        "relation_strength_budget": {r: float(lambdas[r]) for r in RELATIONS},
    }
    user = (
        "SOCIAL_CONTEXT_JSON\n" + canonical_json(payload) +
        "\n\nReturn exactly one JSON object matching ATLAS_SOCIAL_LLM_OUTPUT_V1. "
        "Do not use outside political knowledge."
    )
    return {
        "request_id": rid,
        "item": {
            "anonymous_election_id": item["anonymous_election_id"],
            "anonymous_territory_id": item["anonymous_territory_id"],
            "condition_id": item["condition_id"],
            "output_path": item["output_path"],
        },
        "agent_id": row_id(row),
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user},
        ],
        "context": payload,
    }


def validate_response(payload, party_keys):
    if not isinstance(payload, dict):
        raise ValueError("LLM response must be an object")
    mode = payload.get("social_response")
    if mode not in ALLOWED_RESPONSES:
        raise ValueError("invalid social_response %r" % mode)

    tdelta = float(payload.get("turnout_delta_logit", 0.0))
    if not math.isfinite(tdelta):
        raise ValueError("non-finite turnout_delta_logit")
    tdelta = clip(tdelta, -0.75, 0.75)

    adj = payload.get("party_logit_adjustments") or {}
    if set(adj) - set(party_keys):
        raise ValueError("party adjustment contains unknown pseudonym")
    clean_adj = {}
    for k in party_keys:
        x = float(adj.get(k, 0.0))
        if not math.isfinite(x):
            raise ValueError("non-finite party adjustment")
        clean_adj[k] = clip(x, -1.0, 1.0)
    # Remove the arbitrary common offset; only relative logits may move.
    mean = sum(clean_adj.values()) / max(1, len(clean_adj))
    clean_adj = {k: v - mean for k, v in clean_adj.items()}

    reliance = payload.get("relation_reliance") or {}
    clean_rel = {r: clip(float(reliance.get(r, 0.0)), 0.0, 1.0) for r in RELATIONS}
    reasons = [r for r in payload.get("reason_codes", []) if r in ALLOWED_REASONS][:4]
    return {
        "social_response": mode,
        "turnout_delta_logit": tdelta,
        "party_logit_adjustments": clean_adj,
        "relation_reliance": clean_rel,
        "reason_codes": reasons,
    }


def apply_adjustment(row, response, lambdas, round_name):
    keys = tuple(sorted(row["conditional_party_probabilities"]))
    clean = validate_response(response, keys)
    budget = min(0.92, sum(max(0.0, float(lambdas[r])) for r in RELATIONS))
    old_p = normalize(row["conditional_party_probabilities"])
    p_sus = 0.12 + 0.88 * entropy01(old_p)
    scores = {
        k: math.exp(math.log(max(1e-12, old_p[k])) +
                    budget * p_sus * clean["party_logit_adjustments"][k])
        for k in keys
    }
    new_p = normalize(scores)

    t = clip(float(row["turnout_probability"]), 1e-9, 1.0 - 1e-9)
    ambiguity = 1.0 - min(1.0, 2.0 * abs(t - 0.5))
    t_sus = 0.18 + 0.82 * ambiguity
    new_t = sigmoid(logit(t) + budget * t_sus * clean["turnout_delta_logit"])

    out = copy.deepcopy(row)
    out["conditional_party_probabilities"] = new_p
    out["turnout_probability"] = new_t
    out["agentic_social_influence"] = {
        "schema_version": "ATLAS_SOCIAL_LLM_APPLIED_V1",
        "round": round_name,
        "bounded_budget": budget,
        "party_susceptibility": p_sus,
        "turnout_susceptibility": t_sus,
        "validated_response": clean,
        "party_shift_l1": sum(abs(new_p[k] - old_p[k]) for k in keys),
        "turnout_shift": new_t - t,
    }
    return out


def emit_requests(env, input_run, graph_root, output_jsonl, lambdas,
                  round_name="R1", system_prompt_path=None):
    wm = read_json(os.path.join(env, "work_manifest.json"))
    gi = read_json(os.path.join(graph_root, "graph_index.json"))
    if system_prompt_path is None:
        system_prompt_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "SOCIAL_PROMPT.txt")
        )
    with open(system_prompt_path, "r", encoding="utf-8") as fh:
        system_prompt = fh.read().strip()

    requests = []
    graph_cache = {}
    batch_cache = {}
    for item in wm["work_items"]:
        bref = gi["graphs"][item["voter_batch_path"]]
        gp = os.path.join(graph_root, bref["graph"])
        if gp not in graph_cache:
            if sha256_file(gp) != bref["graph_sha256"]:
                raise ValueError("graph hash mismatch: %s" % gp)
            graph_cache[gp] = read_json(gp)
        bp = os.path.join(env, item["voter_batch_path"])
        if bp not in batch_cache:
            batch_cache[bp] = read_json(bp)["voter_archetypes"]

        rows = read_jsonl(os.path.join(input_run, item["output_path"]))
        voters = batch_cache[bp]
        if len(rows) != len(voters):
            raise ValueError("input rows/voters length mismatch")
        graph = graph_cache[gp]
        for i, (voter, row) in enumerate(zip(voters, rows)):
            requests.append(build_request(
                item, voter, row, rows, graph, i, lambdas, round_name, system_prompt
            ))
    write_jsonl(output_jsonl, requests)
    print("PASS_AGENTIC_SOCIAL_REQUESTS %d" % len(requests))
    return requests


def _extract_content(raw):
    if isinstance(raw, dict) and "choices" in raw:
        return raw["choices"][0]["message"]["content"]
    if isinstance(raw, dict) and "content" in raw:
        return raw["content"]
    raise ValueError("unrecognized OpenAI-compatible response envelope")


def _call_one(req, endpoint, api_key, model, timeout):
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": req["messages"],
    }
    data = json.dumps(body).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = "Bearer " + api_key
    http_req = urllib.request.Request(endpoint, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(http_req, timeout=timeout) as resp:
        envelope = json.loads(resp.read().decode("utf-8"))
    content = _extract_content(envelope)
    parsed = json.loads(content) if isinstance(content, str) else content
    return {
        "request_id": req["request_id"],
        "agent_id": req["agent_id"],
        "response": parsed,
    }


def call_openai_compatible(requests_jsonl, responses_jsonl, endpoint, model,
                           api_key=None, workers=4, timeout=120):
    requests = read_jsonl(requests_jsonl)
    out = [None] * len(requests)

    def task(pair):
        idx, req = pair
        return idx, _call_one(req, endpoint, api_key, model, timeout)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, workers)) as ex:
        for idx, result in ex.map(task, enumerate(requests)):
            out[idx] = result
    write_jsonl(responses_jsonl, out)
    print("PASS_AGENTIC_SOCIAL_RESPONSES %d" % len(out))


def apply_responses(env, input_run, requests_jsonl, responses_jsonl, dest,
                    lambdas, round_name="R1"):
    wm = read_json(os.path.join(env, "work_manifest.json"))
    requests = read_jsonl(requests_jsonl)
    responses = read_jsonl(responses_jsonl)
    req_by_id = {x["request_id"]: x for x in requests}
    resp_by_id = {}
    for x in responses:
        rid = x["request_id"]
        if rid in resp_by_id:
            raise ValueError("duplicate response request_id %s" % rid)
        resp_by_id[rid] = x["response"]

    by_output = {}
    for req in requests:
        by_output.setdefault(req["item"]["output_path"], []).append(req)

    for item in wm["work_items"]:
        path = item["output_path"]
        reqs = by_output.get(path, [])
        rows = read_jsonl(os.path.join(input_run, path))
        if len(reqs) != len(rows):
            raise ValueError("missing request rows for %s" % path)
        reqs_by_agent = {x["agent_id"]: x for x in reqs}
        out = []
        for row in rows:
            aid = row_id(row)
            req = reqs_by_agent.get(aid)
            if not req:
                raise ValueError("missing request for %s/%s" % (path, aid))
            rid = req["request_id"]
            if rid not in resp_by_id:
                raise ValueError("missing LLM response %s" % rid)
            out.append(apply_adjustment(row, resp_by_id[rid], lambdas, round_name))
        write_jsonl(os.path.join(dest, path), out)
    print("PASS_AGENTIC_SOCIAL_APPLIED %d work_items" % len(wm["work_items"]))


def _parse_lambdas(args):
    if args.lambda_file:
        payload = read_json(args.lambda_file)
        src = payload.get("lambdas", payload)
        return {r: float(src[r]) for r in RELATIONS}
    vals = {
        "family": args.lambda_family,
        "work": args.lambda_work,
        "neighborhood": args.lambda_neighborhood,
    }
    if any(v is None for v in vals.values()):
        raise ValueError("provide --lambda-file or all three --lambda-* values")
    return {r: float(vals[r]) for r in RELATIONS}


def cli(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_lambda_flags(p):
        p.add_argument("--lambda-file")
        p.add_argument("--lambda-family", type=float)
        p.add_argument("--lambda-work", type=float)
        p.add_argument("--lambda-neighborhood", type=float)

    p = sub.add_parser("emit")
    p.add_argument("env")
    p.add_argument("input_run")
    p.add_argument("graph_root")
    p.add_argument("requests_jsonl")
    p.add_argument("--round", default="R1")
    p.add_argument("--system-prompt")
    add_lambda_flags(p)

    p = sub.add_parser("call")
    p.add_argument("requests_jsonl")
    p.add_argument("responses_jsonl")
    p.add_argument("--endpoint", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--api-key-env", default="SOCIAL_LLM_API_KEY")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--timeout", type=int, default=120)

    p = sub.add_parser("apply")
    p.add_argument("env")
    p.add_argument("input_run")
    p.add_argument("requests_jsonl")
    p.add_argument("responses_jsonl")
    p.add_argument("dest")
    p.add_argument("--round", default="R1")
    add_lambda_flags(p)

    args = ap.parse_args(argv)
    if args.cmd == "emit":
        emit_requests(
            args.env, args.input_run, args.graph_root, args.requests_jsonl,
            _parse_lambdas(args), args.round, args.system_prompt
        )
    elif args.cmd == "call":
        call_openai_compatible(
            args.requests_jsonl, args.responses_jsonl, args.endpoint, args.model,
            os.environ.get(args.api_key_env), args.workers, args.timeout
        )
    elif args.cmd == "apply":
        apply_responses(
            args.env, args.input_run, args.requests_jsonl, args.responses_jsonl,
            args.dest, _parse_lambdas(args), args.round
        )


if __name__ == "__main__":
    cli()
