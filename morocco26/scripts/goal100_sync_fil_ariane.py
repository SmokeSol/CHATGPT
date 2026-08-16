#!/usr/bin/env python3
"""Append missing FIL_ARIANE entries from machine evidence without rewriting history."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
G100 = ROOT / "data" / "goal100"
JOURNAL = ROOT / "FIL_ARIANE.md"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt(value: float, digits: int = 4) -> str:
    return f"{float(value):.{digits}f}"


def append_entry(text: str, entry_id: str, title: str, body: str) -> str:
    marker = f"Entrée {entry_id} —"
    if marker in text:
        return text
    return text.rstrip() + f"\n\n### 2026-08-16 — Entrée {entry_id} — {title}\n\n{body.strip()}\n"


def main() -> None:
    if not JOURNAL.exists():
        raise SystemExit("FIL_ARIANE_FAIL journal missing")
    text = JOURNAL.read_text(encoding="utf-8")
    existing = re.findall(r"Entrée\s+(A\d{3})\s+—", text)
    if len(existing) != len(set(existing)):
        raise SystemExit(f"FIL_ARIANE_FAIL duplicate entry IDs: {existing}")

    n_protocol = G100 / "local_N_protocol_v1.json"
    if n_protocol.exists():
        text = append_entry(text, "A002", "Protocole N92 gelé", f"""
**Question/gate :** `N92-POSTERIOR-FIT`.

**Hypothèse avant test :** les 92 dénominateurs locaux peuvent rester latents sans inventer une table officielle, sous contrainte exacte du total national et avec une dispersion ancrée empiriquement.

**Protocole :** `data/goal100/local_N_protocol_v1.json` — SHA-256 `{sha(n_protocol)}`. Centre 2011, dispersion 2007→2011, Student-t hiérarchique, 50 000 tirages et seed fixe.

**Falsification :** les tirages doivent être entiers, positifs, sommer exactement à 15 801 162 et couvrir la sensibilité N-only de 104 scrutins. L’échelle N ne peut jamais servir de substitut à une variation politique.
""")

    n_post = G100 / "local_N_posterior.json"
    n_inv = G100 / "n_scale_invariance_certificate.json"
    if n_post.exists() and n_inv.exists():
        p, n = load(n_post), load(n_inv)
        if p.get("gate") == "PASS" and n.get("gate") == "PASS":
            s = n["summary"]
            text = append_entry(text, "A003", "Résultat du posterior N92", f"""
**Artefacts :** `data/goal100/local_N_posterior.json` et `data/goal100/n_scale_invariance_certificate.json`.

**Résultat machine :** `PASS`. `{p['draws']:,}` tirages de 92 entiers positifs ; somme de chaque tirage = `{p['national_N']:,}`. Hash de la matrice reproductible : `{p['draw_matrix_sha256_int32_rowmajor']}`.

**Invariance et sensibilité :** `{n['exact_scale_tests']}` tests d’échelle exacts, `{len(n['exact_scale_failures'])}` échec. `{s['contests_with_any_integerization_sensitivity']}` des 104 profils présentent au moins une variation d’allocation liée uniquement à l’entierisation ; probabilité maximale `{fmt(s['max_probability_different_from_reference'], 6)}`.

**Décision :** le posterior est un modèle de dénominateur, jamais une table officielle ni une source cachée de volatilité politique.
""")

    u_protocol = G100 / "uncertainty_protocol_v1.json"
    if u_protocol.exists():
        text = append_entry(text, "A005", "Protocole d’incertitude gelé", f"""
**Question/gate :** `UNCERTAINTY-CALIBRATION`.

**Protocole :** `data/goal100/uncertainty_protocol_v1.json` — SHA-256 `{sha(u_protocol)}`.

**Architecture testée :** innovations nationales partagées + innovations régionales partagées + résidus locaux ; ILR-Helmert pour les compositions et logit pour la participation. La covariance territoriale libre 92×92 est interdite.

**Règle gelée :** calibration leave-one-transition-out dans les deux directions, grille d’inflation préenregistrée, planchers de couverture et plafond de largeur. Aucun facteur ne peut être choisi sur la qualité narrative.
""")

    cal_path = G100 / "uncertainty_calibration.json"
    par_path = G100 / "uncertainty_parameters_v1.json"
    if cal_path.exists() and par_path.exists():
        c, p = load(cal_path), load(par_path)
        if c.get("gate") == "PASS":
            m = c["selected_metrics"]
            text = append_entry(text, "A006", "Résultat de calibration hiérarchique", f"""
**Artefacts :** `data/goal100/uncertainty_calibration.json` et `data/goal100/uncertainty_parameters_v1.json`.

**Résultat machine :** `PASS`. Facteur d’inflation choisi par la règle gelée : `{c['selected_factor']}`.

**Couverture rétrospective combinée :** votes 50/80/95 = `{fmt(m['vote_coverage_50'],3)}` / `{fmt(m['vote_coverage_80'],3)}` / `{fmt(m['vote_coverage_95'],3)}` ; participation = `{fmt(m['turnout_coverage_50'],3)}` / `{fmt(m['turnout_coverage_80'],3)}` / `{fmt(m['turnout_coverage_95'],3)}`.

**Scores :** energy score votes `{fmt(m['vote_energy_score'],6)}` ; CRPS participation `{fmt(m['turnout_crps'],6)}`. Hash paramètres `{p['parameter_manifest_sha256']}`.

**Limite :** deux transitions modernes seulement ; l’incertitude du bulletin régional est une extrapolation explicitement déclarée.
""")

    dynamic = ROOT / "scripts" / "validate_goal100_tracking_dynamic.py"
    if dynamic.exists():
        text = append_entry(text, "A007", "Suivi rendu evidence-driven", f"""
**Problème corrigé :** le validateur initial encodait un nombre fixe de gates ouverts/fermés et pouvait devenir contradictoire lors d’une transition légitime.

**Solution :** `scripts/validate_goal100_tracking_dynamic.py` — SHA-256 `{sha(dynamic)}`. Chaque gate `CLOSED` est désormais recalculé à partir de ses propres preuves ; l’absence d’artefact ne peut jamais fermer un gate.

**Décision :** les statuts suivent les preuves, pas l’inverse.
""")

    probe_path = G100 / "geometry_official_probe.json"
    if probe_path.exists():
        r = load(probe_path); s = r["summary"]
        text = append_entry(text, "A008", "Probe des sources géométriques officielles", f"""
**Action :** interrogation et hashage de l’index électoral de la Chambre et des textes SGG ; conservation des octets candidats sous `data/goal100/geometry_sources/`.

**Résultat :** `{s['source_pages_ok']}/{s['source_pages_total']}` pages accessibles ; `{s['candidate_documents']}` documents candidats, `{s['downloaded_candidates']}` téléchargés, `{s['candidates_with_extractable_pdf_text']}` PDF à texte extractible. Numéro du décret recherché détecté : `{s['decree_number_found_in_index_or_candidate']}`.

**Décision :** acquisition de preuve uniquement ; ce probe ne ferme pas à lui seul P0-1.
""")

    geo_path = G100 / "geometry_2026_certificate.json"
    if geo_path.exists():
        c = load(geo_path)
        if c.get("gate") == "PASS":
            text = append_entry(text, "A009", "Certificat opérationnel de géométrie", f"""
**Résultat :** `{c['status']}`. Géométrie : 92 locales / 305 sièges et 12 régionales / 90 sièges ; 92 lignes crosswalkées, zéro différence inexpliquée.

**Preuve officielle :** référence courante au décret 2.11.603 détectée. Parsing direct intégral de la table officielle : `{c['direct_official_table_machine_parsed']}`.

**Limite divulguée :** {c['bounded_limitation']}

**Décision :** fermeture opérationnelle de P0-1 avec legal-watch obligatoire à chaque snapshot. Toute modification de source officielle bloque le forecast suivant.
""")

    rec_path = G100 / "fminus1_state_reconciliation.json"
    if rec_path.exists():
        r = load(rec_path)
        text = append_entry(text, "A010", "Réconciliation des gates par preuve", f"""
**Artefact :** `data/goal100/fminus1_state_reconciliation.json` — SHA-256 `{sha(rec_path)}`.

**Transitions soutenues :** `{', '.join(r.get('transitions_supported_by_current_evidence', [])) or 'aucune nouvelle fermeture'}`.

**P0 courant :** `{json.dumps(r['p0_status'], ensure_ascii=False, sort_keys=True)}`.

**Gates restants :** `{', '.join(r['remaining_hard_gates']) or 'aucun avant enregistrement'}`.

**Règle :** réconciliation idempotente ; l’absence de preuve ne ferme jamais un gate.
""")

    event_path = G100 / "fil_ariane_events" / "A011.json"
    if event_path.exists():
        e = load(event_path); m = e["machine_result"]
        text = append_entry(text, "A011", "Simulation F−1 cohérente terminée", f"""
**Gate :** `MC-50000-COHERENT` — `{e['status']}`.

**Résultat machine :** `{m['valid_draws']:,}` élections valides sur `{m['attempts']:,}` tentatives ; taux de rejet juridique `{fmt(m['rejection_rate'],6)}` ; erreur maximale de normalisation `{m['max_probability_normalization_error']}` ; erreur-type binomiale Monte-Carlo maximale `{fmt(m['monte_carlo_max_binomial_se'],6)}`.

**Contrôle OTHER :** `{m['OTHER_single_list_calls']}` appel de l’allocator avec une liste synthétique `OTHER`.

**Hashes :** forecast `{m['forecast_sha256']}` ; manifest initial `{m['manifest_sha256']}`.

**Sièges nationaux moyens :** `{json.dumps(m['expected_national_seats'], ensure_ascii=False, sort_keys=True)}`.

**Décision :** le gate de simulation devient éligible ; le forecast n’est toutefois public/immuable qu’après transition append-only du registre.
""")

    registration = G100 / "fminus1_registration_certificate.json"
    if registration.exists():
        r = load(registration)
        if r.get("gate") == "PASS":
            text = append_entry(text, "A012", "Enregistrement immuable de F−1", f"""
**Snapshot :** `F-1 — STRUCTURAL_PROBABILISTIC_FORECAST`.

**Résultat :** insertion append-only dans `data/goal100/forecast_registry.json`. Hash forecast `{r['forecast_artifact_sha256']}` ; hash manifest `{r['manifest_sha256']}` ; commit modèle `{r['model_code_commit']}`.

**Statut :** F−1 est désormais gelé et falsifiable. Toute modification future doit utiliser un nouvel identifiant de snapshot.

**Prochaine étape :** construire et geler B2 — candidats, changements de parti, réseaux et événements structurés non agentiques — puis émettre F0. La couche agentique reste verrouillée.
""")

    # Append a compact current-state checkpoint after successful registration.
    registry_path = G100 / "forecast_registry.json"
    gates_path = G100 / "gate_registry.json"
    if registry_path.exists() and gates_path.exists():
        registry, gates = load(registry_path), load(gates_path)
        if any(s.get("snapshot_id") == "F-1" for s in registry.get("snapshots", [])):
            statuses = {g["id"]: g["status"] for g in gates["p0"]}
            open_unlock = [g["id"] for g in gates["forecast_unlock"] if g["status"] != "CLOSED"]
            text = append_entry(text, "A013", "Checkpoint après F−1", f"""
**P0 :** `{json.dumps(statuses, sort_keys=True)}`.

**Forecasts enregistrés :** `{', '.join(s['snapshot_id'] for s in registry['snapshots'])}`. Prochain identifiant : `{registry['sequence']['next_id']}`.

**Gates de forecast encore ouverts :** `{', '.join(open_unlock) or 'aucun pour F−1'}`.

**Frontière anti-drift :** aucune expérience agentique n’est autorisée avant gel de B2.
""")

    final_ids = re.findall(r"Entrée\s+(A\d{3})\s+—", text)
    if len(final_ids) != len(set(final_ids)):
        raise SystemExit(f"FIL_ARIANE_FAIL duplicate IDs after sync: {final_ids}")
    JOURNAL.write_text(text.rstrip() + "\n", encoding="utf-8")
    index = {
        "schema_version": "1.0",
        "journal": "morocco26/FIL_ARIANE.md",
        "journal_sha256": sha(JOURNAL),
        "entry_ids": final_ids,
        "entry_count": len(final_ids),
        "latest_entry": final_ids[-1] if final_ids else None,
        "rule": "Entries are append-only; synchronization appends missing evidence-backed entries and never edits an existing entry.",
    }
    (G100 / "fil_ariane_index.json").write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(index, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
