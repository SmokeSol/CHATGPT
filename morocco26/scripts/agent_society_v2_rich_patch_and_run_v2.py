#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HELPERS = r"""
DEMO_DIMS_COVERAGE = ["age_band", "sex", "urban_rural", "education_band", "activity_status"]

def coverage_pick(pool, weights, targets, n, rng):
    # Weighted sample without replacement that guarantees every positive core marginal.
    idx_all = np.arange(len(pool), dtype=np.int64)
    weights = np.asarray(weights, dtype=float)
    if len(pool) < n:
        raise RuntimeError(f"coverage sample needs {n} rows but pool has {len(pool)}")
    req = []
    for dim in DEMO_DIMS_COVERAGE:
        values = pool[dim].astype(str).to_numpy()
        for cat, target in targets[dim].items():
            if float(target) <= 1e-12:
                continue
            cand = idx_all[values == str(cat)]
            if len(cand) == 0:
                raise RuntimeError(f"positive target has no population support: {dim}={cat}")
            req.append((len(cand), dim, str(cat), cand))
    req.sort(key=lambda x: (x[0], x[1], x[2]))
    selected = set()
    for _, dim, cat, cand in req:
        if any(str(pool.iloc[i][dim]) == cat for i in selected):
            continue
        avail = np.asarray([int(i) for i in cand if int(i) not in selected], dtype=np.int64)
        if len(avail) == 0:
            raise RuntimeError(f"cannot add unique support row for {dim}={cat}")
        p = np.clip(weights[avail], 0.0, None)
        p = p / p.sum() if p.sum() > 0 else None
        selected.add(int(rng.choice(avail, p=p)))
    if len(selected) > n:
        raise RuntimeError("coverage seed exceeds target archetype count")
    remain = np.asarray([int(i) for i in idx_all if int(i) not in selected], dtype=np.int64)
    need = n - len(selected)
    fill = np.empty(0, dtype=np.int64)
    if need:
        p = np.clip(weights[remain], 0.0, None)
        p = p / p.sum() if p.sum() > 0 else None
        fill = np.asarray(rng.choice(remain, size=need, replace=False, p=p), dtype=np.int64)
    out = np.asarray(list(selected) + fill.tolist(), dtype=np.int64)
    rng.shuffle(out)
    return out

def robust_effective_rank(records, fields):
    # Finite deterministic diagnostic with explicit missing-value handling.
    df = pd.DataFrame([{k: r.get(k) for k in fields} for r in records])
    blocks = []
    for col in fields:
        s = df[col]
        numeric = pd.to_numeric(s, errors="coerce")
        nonmissing = s.notna()
        parse_rate = float(numeric[nonmissing].notna().mean()) if int(nonmissing.sum()) else 0.0
        if parse_rate >= 0.95:
            x = numeric.replace([np.inf, -np.inf], np.nan).to_numpy(dtype=float)
            finite = np.isfinite(x)
            med = float(np.nanmedian(x)) if finite.any() else 0.0
            x[~finite] = med
            sd = float(np.std(x))
            if sd > 1e-10:
                blocks.append(((x - float(np.mean(x))) / sd)[:, None])
        else:
            text = s.fillna("__MISSING__").astype(str)
            counts = text.value_counts(dropna=False)
            rare = set(counts[counts < 5].index)
            if rare:
                text = text.where(~text.isin(rare), "__RARE__")
            dum = pd.get_dummies(text, prefix=col, dtype=float)
            if dum.shape[1] > 1:
                blocks.append(dum.to_numpy(dtype=float))
    if not blocks:
        return {"effective_rank": 0.0, "encoded_columns": 0, "nonzero_eigenvalues": 0}
    X = np.column_stack(blocks)
    X[~np.isfinite(X)] = 0.0
    raw_var = np.var(X, axis=0)
    X = X[:, raw_var > 1e-12]
    if X.shape[1] > 800:
        order = np.argsort(np.var(X, axis=0))[::-1][:800]
        X = X[:, order]
    X -= np.mean(X, axis=0, keepdims=True)
    sd = np.std(X, axis=0)
    X = X[:, sd > 1e-10]
    sd = np.std(X, axis=0)
    X /= sd
    C = (X.T @ X) / max(1, X.shape[0] - 1)
    C = (C + C.T) / 2.0
    try:
        ev = np.linalg.eigvalsh(C + np.eye(C.shape[0]) * 1e-12)
    except np.linalg.LinAlgError:
        sv = np.linalg.svd(X, compute_uv=False, full_matrices=False)
        ev = (sv * sv) / max(1, X.shape[0] - 1)
    ev = ev[np.isfinite(ev) & (ev > 1e-10)]
    if not len(ev):
        return {"effective_rank": 0.0, "encoded_columns": int(X.shape[1]), "nonzero_eigenvalues": 0}
    p = ev / ev.sum()
    return {
        "effective_rank": float(np.exp(-(p * np.log(p)).sum())),
        "encoded_columns": int(X.shape[1]),
        "nonzero_eigenvalues": int(len(ev)),
    }
"""

SAMPLE_OLD = (
    'rng=np.random.default_rng(SEED+year*100000+ti*101+attempt); '
    'pick=rng.choice(len(pool),N,replace=False,p=sw/sw.sum()); '
    'r=b.prior_assign(pool.iloc[pick].copy().reset_index(drop=True),prior,SEED+year+ti+attempt)'
)
SAMPLE_NEW = (
    'rng=np.random.default_rng(SEED+year*100000+ti*101+attempt); '
    'pick=coverage_pick(pool,sw,tm,N,rng); '
    'r=b.prior_assign(pool.iloc[pick].copy().reset_index(drop=True),prior,SEED+year+ti+attempt)'
)
RANK_OLD = 'er0=b.effective_rank(sample,r0); err=b.effective_rank(sample,rich);'
RANK_NEW = 'er0=robust_effective_rank(sample,r0); err=robust_effective_rank(sample,rich);'

def main() -> None:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--source", required=True)
    args, rest = parser.parse_known_args()
    source_path = Path(args.source)
    source = source_path.read_text(encoding="utf-8")
    if source.count("\ndef main():\n") != 1:
        raise RuntimeError("unexpected V2 main marker count")
    source = source.replace("\ndef main():\n", "\n" + HELPERS + "\ndef main():\n", 1)
    if source.count(SAMPLE_OLD) != 1:
        raise RuntimeError("unexpected V2 sampling block count")
    source = source.replace(SAMPLE_OLD, SAMPLE_NEW, 1)
    if source.count(RANK_OLD) != 1:
        raise RuntimeError("unexpected V2 effective-rank block count")
    source = source.replace(RANK_OLD, RANK_NEW, 1)
    sys.argv = [str(source_path)] + rest
    namespace = {"__name__": "__main__", "__file__": str(source_path)}
    exec(compile(source, str(source_path) + "::coverage-fixed", "exec"), namespace, namespace)

if __name__ == "__main__":
    main()
