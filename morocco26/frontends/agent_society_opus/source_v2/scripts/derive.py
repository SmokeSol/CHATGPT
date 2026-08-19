# -*- coding: utf-8 -*-
"""
Derive descriptive behaviour statistics from the 94,208 frozen voter-level decisions.

Strictly descriptive: unweighted counts over emitted agent decisions.
No population weighting, no territory/national aggregation to an outcome,
no party ranking presented as a result. Party pseudonyms are never carried
outside their own territory; only supplied bloc status (incumbent coalition /
opposition / aggregate other) is aggregated across territories.
"""
import io
import json
import os
import sys
import math
from collections import defaultdict, Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import judge_engine as JE

ENV = sys.argv[1]
RUN = sys.argv[2]
DEST = sys.argv[3]

FACTORS = JE.FACTORS
# facteurs differenciants : hors ancrage structurel et hors habitude de participation
DIFF_FACTORS = [f for f in FACTORS if f not in ("prior_vote_inertia", "turnout_habit")]


def gov_eval(s):
    g = (0.38 * s["gov_econ"] + 0.20 * s["gov_pov"] + 0.17 * s["gov_anti"] + 0.25 * s["trust_parl"])
    c = (0.38 * s["c_gecon"] + 0.20 * s["c_gpov"] + 0.17 * s["c_ganti"] + 0.25 * s["c_tparl"])
    a = (g + 0.40 * (s["dem_sat"] - 0.50) * s["c_dsat"]
         + 0.12 * (s["econ_cond"] - 0.55) * s["c_econ"]
         - 0.18 * (s["corruption"] - 0.44) * s["c_cloc"])
    return (a - 0.50) * c


EDU = {"Aucun niveau d'études": "aucun", "Préscolaire": "primaire", "Primaire": "primaire",
       "Secondaire collégial": "college", "Secondaire qualifiant": "lycee", "Supérieur": "superieur"}
HH = {"Ménage nucléaire - Couple marié avec enfant(s) non marié(s)": "nucleaire",
      "Ménage nucléaire - Couple marié sans enfant": "nucleaire",
      "Ménage élargi": "elargi", "Ménage composite": "elargi", "Ménage polygame": "elargi",
      "Ménage nucléaire - Mère avec enfant(s) non marié(s)": "monoparental",
      "Ménage nucléaire - Père avec enfant(s) non marié(s)": "monoparental",
      "Ménage d'une seule personne": "seul"}


def sector_of(v):
    sec = v.get("industry_sector") or ""
    if sec.startswith("Agriculture"):
        return "agriculture"
    if sec.startswith("Industries") or sec.startswith("Construction") or sec.startswith("Eau"):
        return "industrie_btp"
    if sec.startswith("Commerce"):
        return "commerce"
    if sec.startswith("Administration") or sec.startswith("Transports") or sec.startswith("Autres services"):
        return "services"
    return "non_renseigne"


# tercile cut points, computed on the archetype population in a first pass
def terc(x, lo, hi):
    return "bas" if x < lo else ("median" if x < hi else "haut")


class Acc(object):
    __slots__ = ("n", "turnout", "fid", "fidn", "punish", "reward", "prog", "local",
                 "blocs", "fact", "codes", "dom", "dom2", "turn_hist", "fid_hist",
                 "gd", "trust", "hard", "acquis", "hesitant", "partant", "flow", "flown")

    def __init__(self):
        self.n = 0
        self.turnout = 0.0
        self.fid = 0.0
        self.fidn = 0
        self.punish = 0
        self.reward = 0
        self.prog = 0
        self.local = 0
        self.blocs = [0.0, 0.0, 0.0]
        self.fact = [0.0] * len(FACTORS)
        self.codes = Counter()
        self.dom = Counter()
        self.dom2 = Counter()
        self.turn_hist = [0] * 20
        self.fid_hist = [0] * 20
        self.gd = 0.0
        self.trust = 0.0
        self.hard = 0.0
        self.acquis = 0
        self.hesitant = 0
        self.partant = 0
        self.flow = [[0.0, 0.0, 0.0], [0.0, 0.0, 0.0], [0.0, 0.0, 0.0]]
        self.flown = [0, 0, 0]

    def add(self, turnout, fi, codes, blocs, fid, gd, trust=0.0, hard=0.0, prior_bloc=None):
        self.n += 1
        self.turnout += turnout
        self.turn_hist[min(19, int(turnout * 20))] += 1
        for i, f in enumerate(FACTORS):
            self.fact[i] += fi[f]
        self.dom[max(FACTORS, key=lambda k: fi[k])] += 1
        self.dom2[max(DIFF_FACTORS, key=lambda k: fi[k])] += 1
        self.gd += gd
        self.trust += trust
        self.hard += hard
        for c in codes:
            self.codes[c] += 1
        if "GOVERNMENT_PUNISHMENT" in codes:
            self.punish += 1
        if "GOVERNMENT_REWARD" in codes:
            self.reward += 1
        if any(c.endswith("_FIT") for c in codes):
            self.prog += 1
        if "LOCAL_CANDIDATE_STRENGTH" in codes:
            self.local += 1
        for i in range(3):
            self.blocs[i] += blocs[i]
        if fid is not None:
            self.fid += fid
            self.fidn += 1
            self.fid_hist[min(19, int(fid * 20))] += 1
            if fid >= 0.65:
                self.acquis += 1
            elif fid >= 0.35:
                self.hesitant += 1
            else:
                self.partant += 1
            if prior_bloc is not None:
                self.flown[prior_bloc] += 1
                for j in range(3):
                    self.flow[prior_bloc][j] += blocs[j]

    def out(self):
        n = max(1, self.n)
        return {
            "n": self.n,
            "part": round(self.turnout / n, 4),
            "fid": round(self.fid / self.fidn, 4) if self.fidn else None,
            "fidn": self.fidn,
            "sanction": round(self.punish / n, 4),
            "recompense": round(self.reward / n, 4),
            "programme": round(self.prog / n, 4),
            "locale": round(self.local / n, 4),
            "blocs": [round(x / n, 4) for x in self.blocs],
            "fact": [round(x / n, 4) for x in self.fact],
            "dom": {k: v for k, v in self.dom.most_common()},
            "dom2": {k: v for k, v in self.dom2.most_common()},
            "gd": round(self.gd / n, 5),
            "trust": round(self.trust / n, 4),
            "hard": round(self.hard / n, 4),
            "acquis": round(self.acquis / max(1, self.fidn), 4),
            "hesitant": round(self.hesitant / max(1, self.fidn), 4),
            "partant": round(self.partant / max(1, self.fidn), 4),
            "flow": [[round(self.flow[i][j] / max(1, self.flown[i]), 4) for j in range(3)] for i in range(3)],
            "flown": self.flown,
            "codes": {k: round(v / n, 4) for k, v in self.codes.most_common()},
            "hpart": self.turn_hist,
            "hfid": self.fid_hist,
        }


def main():
    wm = json.load(io.open(os.path.join(ENV, "work_manifest.json"), encoding="utf-8"))
    items = wm["work_items"]

    # ---- pass 1: tercile cut points for the two attitude indices
    trusts, govs = [], []
    seen_batches = set()
    for it in items:
        bp = it["voter_batch_path"]
        if bp in seen_batches:
            continue
        seen_batches.add(bp)
        b = json.load(io.open(os.path.join(ENV, bp), encoding="utf-8"))
        for v in b["voter_archetypes"]:
            s = JE.voter_signals(v)
            trusts.append(s["trust"])
            govs.append(gov_eval(s))
    trusts.sort()
    govs.sort()
    T1, T2 = trusts[len(trusts) // 3], trusts[2 * len(trusts) // 3]
    G1, G2 = govs[len(govs) // 3], govs[2 * len(govs) // 3]
    sys.stderr.write("cut points trust %.4f/%.4f gov %.5f/%.5f\n" % (T1, T2, G1, G2))

    seg = defaultdict(Acc)
    glob = {"A": Acc(), "B": Acc(), "*": Acc()}
    terr = {}
    portraits = []
    cond_ids = sorted(set(i["condition_id"] for i in items))
    cond_label = {cond_ids[0]: "A", cond_ids[1]: "B"}
    factor_pairs = Counter()
    prof_matrix = defaultdict(Acc)

    ctx_cache, prep_cache = {}, {}
    batch_cache = {}
    portrait_every = 31   # coprime stride -> spread across the whole tree

    idx = 0
    for it in items:
        cp = it["context_path"]
        if cp not in ctx_cache:
            ctx_cache[cp] = json.load(io.open(os.path.join(ENV, cp), encoding="utf-8"))
            prep_cache[cp] = JE.prepare_context(ctx_cache[cp])
        ctx, prep = ctx_cache[cp], prep_cache[cp]
        parties = prep["parties"]
        blocidx = {}
        for q in parties:
            g = prep["gov_status"].get(q)
            blocidx[q] = 0 if g == "INCUMBENT_COALITION" else (1 if g == "OPPOSITION" else 2)

        bp = it["voter_batch_path"]
        if bp not in batch_cache:
            if len(batch_cache) > 16:
                batch_cache.clear()
            batch_cache[bp] = json.load(io.open(os.path.join(ENV, bp), encoding="utf-8"))
        batch = batch_cache[bp]

        cl = cond_label[it["condition_id"]]
        tkey = it["anonymous_election_id"][:10] + "|" + it["anonymous_territory_id"][:10]
        if tkey not in terr:
            terr[tkey] = {"e": it["anonymous_election_id"], "t": it["anonymous_territory_id"],
                          "acc": Acc(),
                          "prev_part": prep["prev_turnout"],
                          "ncomp": prep["ncomp"]}

        raw = open(os.path.join(RUN, it["output_path"]), "rb").read().decode("utf-8")
        lines = raw.splitlines()
        for i, line in enumerate(lines):
            row = json.loads(line)
            v = batch["voter_archetypes"][i]
            s = JE.voter_signals(v)
            gd = gov_eval(s)
            p = row["conditional_party_probabilities"]
            fi = row["factor_importance"]
            codes = row["reason_codes"]
            t = row["turnout_probability"]
            blocs = [0.0, 0.0, 0.0]
            for q, pv in p.items():
                blocs[blocidx.get(q, 2)] += pv
            pv0 = v["prior_vote_or_abstention"]
            fid = p.get(pv0) if pv0 in p else None

            keys = [
                ("age", v.get("age_band")),
                ("sexe", v.get("sex")),
                ("milieu", v.get("urban_rural")),
                ("etudes", EDU.get(v.get("education_level"), "aucun")),
                ("activite", v.get("activity_status")),
                ("niveau_vie", "Q%d" % max(1, min(5, int(round((v.get("latent_national_quintile") or 0.6) * 5))))),
                ("comportement", "vote" if pv0 != "ABSTAIN" else "abstention"),
                ("confiance", terc(s["trust"], T1, T2)),
                ("bilan", terc(gd, G1, G2)),
                ("foyer", HH.get(v.get("household_type"), "autre")),
                ("secteur", sector_of(v)),
            ]
            pb = blocidx.get(pv0) if pv0 in p else None
            ex = (s["trust"], s["hardship"], pb)
            for dim, val in keys:
                if val:
                    seg[(dim, str(val))].add(t, fi, codes, blocs, fid, gd, *ex)
            glob[cl].add(t, fi, codes, blocs, fid, gd, *ex)
            glob["*"].add(t, fi, codes, blocs, fid, gd, *ex)
            terr[tkey]["acc"].add(t, fi, codes, blocs, fid, gd, *ex)
            prof_matrix[(v.get("age_band"), v.get("urban_rural"))].add(t, fi, codes, blocs, fid, gd, *ex)

            rk = sorted(FACTORS, key=lambda k: fi[k], reverse=True)
            factor_pairs[(rk[0], rk[1])] += 1

            idx += 1
            if idx % portrait_every == 0 and len(portraits) < 3000:
                portraits.append(compact_portrait(v, row, s, gd, blocs, fid, cl, it))

    out = {
        "meta": {
            "rows": glob["*"].n,
            "work_items": len(items),
            "territoires": len(terr),
            "archetypes_par_territoire": 256,
            "cadres": {"A": cond_ids[0], "B": cond_ids[1]},
            "facteurs": FACTORS,
            "cut_points": {"confiance": [round(T1, 4), round(T2, 4)],
                           "bilan": [round(G1, 5), round(G2, 5)]},
        },
        "global": {k: v.out() for k, v in glob.items()},
        "segments": {},
        "profil_croise": {},
        "territoires": [],
        "enchainements": [{"a": a, "b": b, "n": n} for (a, b), n in factor_pairs.most_common(40)],
    }
    for (dim, val), a in seg.items():
        out["segments"].setdefault(dim, {})[val] = a.out()
    for (ageb, mil), a in prof_matrix.items():
        if ageb and mil:
            out["profil_croise"]["%s|%s" % (ageb, mil)] = a.out()
    for k, d in terr.items():
        o = d["acc"].out()
        out["territoires"].append({
            "e": d["e"][:8], "t": d["t"][:8], "n": o["n"],
            "part": o["part"], "part_prec": round(d["prev_part"], 4),
            "fid": o["fid"], "sanction": o["sanction"], "locale": o["locale"],
            "blocs": o["blocs"], "dom": max(o["dom"], key=o["dom"].get),
            "ncomp": d["ncomp"],
        })
    out["territoires"].sort(key=lambda x: -x["part"])

    if not os.path.isdir(DEST):
        os.makedirs(DEST)
    with open(os.path.join(DEST, "societe.json"), "wb") as f:
        f.write(json.dumps(out, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    with open(os.path.join(DEST, "portraits.json"), "wb") as f:
        f.write(json.dumps({"cles": PORTRAIT_KEYS, "agents": portraits, "facteurs": FACTORS},
                           ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    sys.stderr.write("societe.json %.1f KB | portraits.json %.1f KB (%d agents)\n" % (
        os.path.getsize(os.path.join(DEST, "societe.json")) / 1024.0,
        os.path.getsize(os.path.join(DEST, "portraits.json")) / 1024.0, len(portraits)))


PORTRAIT_KEYS = ["id", "c", "e", "t", "age", "ans", "sx", "mi", "ed", "ac", "qv", "fo", "se",
                 "ms", "hh", "pr", "occ", "lit", "tr", "co", "di", "ec", "ha", "gd", "rl", "ds",
                 "part", "fid", "pp", "bl", "fa", "rc"]


def compact_portrait(v, row, s, gd, blocs, fid, cl, it):
    p = row["conditional_party_probabilities"]
    fi = row["factor_importance"]
    return [
        row["weighted_archetype_id"], cl,
        it["anonymous_election_id"][:8], it["anonymous_territory_id"][:8],
        v.get("age_band"), v.get("age_years"), v.get("sex"), v.get("urban_rural"),
        EDU.get(v.get("education_level"), "aucun"), v.get("activity_status"),
        v.get("latent_national_quintile"), HH.get(v.get("household_type"), "autre"),
        sector_of(v), v.get("marital_status"), v.get("household_size"),
        v.get("prior_vote_or_abstention"),
        (v.get("occupation_group") or "MISSING").split(" - ")[-1][:58],
        v.get("literacy_status"),
        round(s["trust"], 3), round(s["corruption"], 3), round(s["discuss"], 3),
        round(s["econ_cond"], 3), round(s["hardship"], 3), round(gd, 4),
        round(s["resp_loc"], 3), round(s["dem_sat"], 3),
        round(row["turnout_probability"], 4),
        (round(fid, 4) if fid is not None else None),
        [round(p[q], 4) for q in sorted(p)],
        [round(x, 4) for x in blocs],
        [round(fi[f], 3) for f in FACTORS],
        row["reason_codes"],
    ]


if __name__ == "__main__":
    main()
