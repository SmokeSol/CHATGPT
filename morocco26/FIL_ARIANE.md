# MOROCCO//26 — FIL D’ARIANE

> Journal de navigation append-only du programme de forecast 2026. Ce fichier consigne les décisions, opérations, erreurs, corrections, preuves et prochaines actions. Il n’est pas, à lui seul, une preuve scientifique : chaque affirmation de fermeture d’un gate doit pointer vers un artefact machine vérifiable.

## Règles du journal

1. **Ne jamais réécrire l’histoire.** Une erreur est corrigée par une nouvelle entrée qui référence l’entrée antérieure ; elle n’est pas effacée.
2. **Un gate n’est fermé que par preuve.** Le registre machine de référence est `data/goal100/gate_registry.json`.
3. **Un forecast n’est jamais remplacé.** `F-1`, `F0`, `F1`, … et `FINAL` sont des snapshots immuables, enregistrés dans `data/goal100/forecast_registry.json`.
4. **Goal75 reste immuable.** Le checkpoint à 75 % et les résultats de falsification antérieurs ne sont pas retouchés.
5. **Séparer constat, décision et hypothèse.** Toute hypothèse non identifiée est interdite dans un artefact de forecast.
6. **Agentique verrouillé.** Aucun crédit prédictif n’est attribué à `E_collect`, `E_reason` ou `E_full` avant gel de la baseline non agentique B2.

## Point de départ certifié

**Date :** 2026-08-16 — Africa/Casablanca  
**Branche de travail :** `morocco26-fminus1`  
**Base :** `main` au checkpoint Goal100 fusionné après la PR #7  
**Phase :** `P6_PROBABILISTIC_FORECAST_ENGINE`  
**Prochain snapshot prévu :** `F-1 — STRUCTURAL_PROBABILISTIC_FORECAST`  
**Statut forecast :** aucun forecast enregistré à ce stade.

### Résultats déjà acquis

- Allocator juridique 2026 fail-closed : régression mathématique **92/92 local + 12/12 régional**, zéro égalité statutaire non résolue dans les vecteurs de test.
- Panel territorial moderne : **92/92 circonscriptions communes** en 2011, 2016 et 2021 avec noms normalisés et magnitudes identiques.
- Baseline B* sélectionnée sans tuning post-validation : `V0_PERSIST` pour les votes et `T0_PERSIST` pour la participation.
- Corps électoral national 2026 contraint à **15 801 162** inscrits ; les 92 dénominateurs locaux restent latents.
- Deux anomalies historiques de provenance régionales sont conservées, sans pont post-hoc : Casablanca-Settat et Marrakech-Safi.

### Gates au lancement de F-1

| Gate | État initial | Artefact de fermeture attendu |
|---|---|---|
| `GEO-2026-AUTHORITATIVE-DIFF` | OPEN | `data/goal100/geometry_2026_certificate.json` |
| `N92-POSTERIOR-FIT` | OPEN | `data/goal100/local_N_posterior.json` |
| `UNCERTAINTY-CALIBRATION` | OPEN | `data/goal100/uncertainty_calibration.json` |
| `MC-50000-COHERENT` | OPEN | `data/goal100/simulation_certificate.json` |
| `SNAPSHOT-IMMUTABILITY-MANIFEST` | OPEN | manifest complet du premier snapshot enregistré |

## Journal chronologique

### 2026-08-16 — Entrée A001 — Lancement de la phase F-1

**Objectif :** produire le premier forecast territorial probabiliste structurel, entièrement gelé, falsifiable et sans couche agentique.

**Actions réalisées :**

- création de la branche dédiée `morocco26-fminus1` depuis `main` ;
- création de ce `FIL_ARIANE.md` ;
- maintien de l’ordre d’exécution déjà préenregistré : géométrie → posterior N92 → incertitude/calibration → simulations cohérentes → snapshot immuable.

**Décisions conservées :**

- ne pas appeler le prochain snapshot `F0` par commodité ; le premier objet est `F-1` ;
- ne pas publier de probabilités tant que les cinq gates ci-dessus ne sont pas fermés ;
- ne pas intégrer candidats, événements ou raisonnements LLM dans F-1 ;
- traiter `OTHER` comme un agrégat de publication uniquement : l’allocator devra opérer sur des listes distinctes, jamais sur une fausse liste unique `OTHER`.

**Prochaine action :** établir le certificat de géométrie 2026 et un legal-watch reproductible, avec zéro différence inexpliquée avant fermeture de `P0-1`.

---

## Format obligatoire des prochaines entrées

Chaque entrée doit contenir, dans cet ordre :

- **ID et date** ;
- **question/gate traité** ;
- **hypothèse avant test** ;
- **actions et artefacts créés** ;
- **résultat machine** ;
- **écarts, échecs ou corrections** ;
- **décision scientifique** ;
- **prochaine action exacte**.

## Références de navigation

- État courant machine : `data/goal100/current_state.json`
- Registre des gates : `data/goal100/gate_registry.json`
- Registre append-only des forecasts : `data/goal100/forecast_registry.json`
- Protocole gelé : `data/goal100/forecast_protocol_v1.json`
- Tracker humain : `reports/GOAL100_TRACKER.md`
- Validation Goal100 : `scripts/validate_goal100_tracking.py`
- Validation anti-drift Goal75 : `scripts/validate_anti_drift.py`


### 2026-08-16 — Entrée A008 — Probe des sources géométriques officielles

**Question/gate :** `GEO-2026-AUTHORITATIVE-DIFF`.

**Action :** interrogation et hashage de l’index électoral de la Chambre et des textes SGG ; téléchargement des documents candidats sans les déclarer automatiquement équivalents à la géométrie du repo.

**Résultat du probe :** 0/3 pages sources accessibles ; 0 document(s) candidat(s), 0 téléchargé(s), 0 PDF avec texte extractible. Présence du numéro de décret recherchée : `False`.

**Artefact :** `data/goal100/geometry_official_probe.json` et octets sources sous `data/goal100/geometry_sources/`.

**Décision :** ce résultat est une acquisition de preuve, pas encore un certificat. P0-1 reste PARTIAL jusqu’au diff ligne par ligne et au legal-watch sans différence inexpliquée.

**Prochaine action :** construire le parser/crosswalk officiel à partir du document effectivement découvert ; en cas de source non extractible, produire un contrôle manuel borné et hashé plutôt qu’un faux parsing.


### 2026-08-16 — Entrée A015 — Postflight F−1

**Statut :** `FAIL_MISSING_EVIDENCE`.

**Preuves manquantes :** `["morocco26/data/goal100/n_scale_invariance_certificate.json", "morocco26/data/goal100/uncertainty_parameters_v1.json", "morocco26/data/goal100/snapshots/F-1/forecast.json", "morocco26/data/goal100/snapshots/F-1/manifest.json", "morocco26/data/goal100/fminus1_registration_certificate.json"]`.

**Détails machine :** `{}`.

**Décision :** un statut autre que PASS interdit la fusion et l’utilisation de F−1. Le rapport complet est `data/goal100/fminus1_postflight.json`.


### 2026-08-16 — Entrée A016 — Investigation d’un échec F−1

**Run :** `31976786865` — statut `completed`, conclusion `failure`, head `55d48b7362aeb0bae2cf2a37da68956277e3de9d`.

**Preuve :** `data/goal100/fminus1_failure_investigation.json` et `data/goal100/fminus1_failure_log.txt`; SHA-256 log `f77216ee27982bc48eb78b0df24b9015047e73bfde795416d9f06d26ff840fe2`.

**Décision :** aucune baisse de seuil ni modification silencieuse du protocole. La prochaine correction doit être classée explicitement comme bug d’ingénierie ou amendment scientifique versionné.
