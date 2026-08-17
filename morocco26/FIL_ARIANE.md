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


### 2026-08-17 — Entrée A017 — Enregistrement fail-closed du snapshot F−1 existant

**Question/gate traité :** raccorder le candidat `F-1` déjà calculé au registre canonique, sans réexécution et sans modification d’un output.

**Hypothèse avant test :** l’enregistrement n’est permis que si les hashes du forecast, des manifests, du certificat de simulation, du code juridique, de la géométrie, de l’incertitude et du posterior N concordent exactement.

**Résultat machine :** `PASS` — 50 000 élections, 92 scrutins locaux / 305 sièges, 12 régionaux / 90 sièges, 395 sièges à chaque tirage, zéro échec juridique. Forecast SHA-256 `de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1` ; manifest source SHA-256 `54272dbfee8809456a9dc429329e34fcc0575553399ba6af54a380470daed2b1`.

**Écart et correction :** les orchestrateurs précédents mélangeaient deux schémas de fichiers et échouaient sur `N92 correction locus absent`. Aucun seuil scientifique n’a été abaissé et aucun tirage n’a été changé ; une enveloppe canonique pointe vers l’arbre immuable `forecasts/F-1`.

**Décision scientifique :** `F-1` est désormais enregistré comme prior structurel non agentique. Le registre passe à `F0`. Toutes les expériences agentiques restent `LOCKED`.

**Prochaine action exacte :** geler `B2` — schéma, admissibilité, cutoff, provenance, transformations et tests de non-fuite — avant toute collecte de candidats, listes, défections, endorsements ou événements.


### 2026-08-17 — Entrée A018 — Gel du protocole B2 non agentique avant collecte

**Question/gate traité :** `B2-0-PROTOCOL-FROZEN` — Comment ajouter des faits politiques structurés à F-1 sans introduire de raisonnement agentique, de fuite temporelle ou d'effets arbitraires ?

**Hypothèse avant test :** B2 doit séparer les contraintes mécaniques des features prédictives et verrouiller tous les coefficients prédictifs à zéro jusqu'à un backtest historique preregistré.

**Actions et artefacts créés :**

- `data/goal100/b2_protocol_v1.json` ;
- `data/goal100/b2_evidence_schema_v1.json` ;
- `data/goal100/b2_feature_dictionary_v1.json` ;
- `data/goal100/b2_gate_registry.json` ;
- `data/goal100/b2_source_registry.json` ;
- `data/goal100/b2_current_state.json` ;
- `data/goal100/fil_ariane_events/A018.json`.

**Résultat machine :** protocole `M26-GOAL100-B2-PROTOCOL-V1` figé sur le parent `F-1` hashé `de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1`. `B2-0` est `CLOSED` ; collecte autorisée = `false` ; coefficients prédictifs = `ALL_ZERO` ; gates agentiques = `ALL_LOCKED`.

**Écarts, échecs ou corrections :** aucun claim politique n’a été collecté avant le gel. Le cutoff final des preuves reste volontairement non fixé : il sera inscrit une seule fois dans le certificat `B2-FROZEN`, sans possibilité de backdating.

**Décisions anti-drift :**

- Opinion polls are excluded from B2 V1.
- LLM semantic extraction, sentiment and narrative salience are forbidden.
- Missing evidence is NA, not zero.
- Conflicts are excluded, not resolved by judgment.
- A feature with insufficient historical support remains exactly zero in F0.
- F-1 is referenced by hash and can never be overwritten.

**Décision scientifique :** B2 protocol is frozen but collection remains locked until the source universe and deterministic query templates pass B2-1.

**Prochaine action exacte :** Research and freeze the source/domain/document allowlist, independence clusters, archive rules and deterministic query templates; only then create B2 evidence records.


### 2026-08-17 — Entrée A019 — Correction du validateur de provenance après squash

**Question/gate traité :** pourquoi le workflow B2 `32001601015` a-t-il échoué après que `B2_PROTOCOL_PASS` a été obtenu ?

**Hypothèse avant test :** l’échec vient d’une règle d’intégration devenue fausse après le squash de la PR #8, et non d’une divergence des artefacts F-1.

**Résultat machine :** `The original registered-state validator required the pre-squash model commit to be an ancestor of HEAD. A squash merge intentionally destroys that ancestry relation although the commit object, remote ref and all immutable artifact hashes remain available.`

**Correction :** Require the recorded model commit object to exist and be reachable from a fetched repository ref, then execute every original artifact, manifest, legal, geometry, N92 and forecast-hash check unchanged.

**Impact scientifique :** `NONE`. Forecast modifié = `false` ; protocole modifié = `false` ; seuil modifié = `false`.

**Invariants conservés :**

- F-1 forecast SHA-256 remains de97880beb662e8940b038d8664b383ce23a7db66560101b95f9dd73ae0407a1.
- No model parameter, seed, draw, probability or seat output is altered.
- Goal75 remains immutable at 75%.
- B2 predictive coefficients remain zero.
- All agentic gates remain locked.

**Décision scientifique :** correction d’ingénierie versionnée. Le validateur d’origine conserve tous les checks de hashes ; seule la condition d’ascendance, inapplicable après squash, est remplacée par existence + reachability dans une ref récupérée.

**Prochaine action exacte :** Rerun the B2 protocol workflow, commit A018/A019 to FIL_ARIANE, and only after PASS proceed to freeze the B2 source universe.


### 2026-08-17 — Entrée A020 — Gel de l’univers de sources B2

**Question/gate traité :** `B2-1-SOURCE-UNIVERSE-FROZEN` — vérifier l’allowlist et les cinq requêtes déterministes avant le premier claim.

**Hypothèse avant test :** au moins 2 T0 actives, 8 partis officiellement représentés dont 5 T1 directement actifs, 3 clusters T2 actifs, 10 sources actives au total et zéro claim préexistant.

**Actions et artefacts :** smoke test HTTP borné sur les 19 routes figées ; SHA-256 du payload de source `8aa331e941ab892997b68a04b91b5b2147c9561f717a3ca976122dbb1ba44d32` ; `b2_source_universe_probe.json` et `b2_source_universe_certificate.json`.

**Résultat machine :** `PASS` — T0 actives `2`, partis T1 représentés `8`, partis T1 actifs `5`, clusters T2 actifs `4`, total actif `11`, reference-only `5`, inactives `3`, claims avant PASS `0`.

**Sources ACTIVE :** `['T0_MAROC_MA_ELECTIONS', 'T0_CONSTITUTIONAL_COURT', 'T1_ISTIQLAL_OFFICIAL', 'T1_PJD_OFFICIAL', 'T1_MP_OFFICIAL', 'T1_UC_OFFICIAL', 'T1_PPS_OFFICIAL', 'T2_LE360', 'T2_HESPRESS', 'T2_SNRTNEWS', 'T2_LEMATIN']`.

**Sources REFERENCE_ONLY :** `['T0_CHAMBRE_REPRESENTANTS', 'T0_LISTES_ELECTORALES', 'T1_RNI_OFFICIAL', 'T1_PAM_OFFICIAL', 'T1_USFP_OFFICIAL']`.

**Sources INACTIVE :** `['T0_SGG_LEGISLATION', 'T2_MEDIAS24', 'T2_TELQUEL']`.

**Décision scientifique :** seules les routes `ACTIVE` peuvent produire des records B2. Une route WAF/challenge ne reçoit aucun crédit par snippet. Tous les coefficients prédictifs restent à zéro.

**Prochaine action exacte :** construire et certifier le crosswalk déterministe identité/parti/liste/territoire (`B2-2`) avant l’admission d’une feature ou d’une contrainte mécanique.
