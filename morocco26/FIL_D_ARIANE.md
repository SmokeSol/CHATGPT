# MOROCCO//26 — FIL D’ARIANE

> Journal canonique de reprise et d’exécution du programme Goal100.  
> Il conserve le cap, les décisions, les preuves, les blockers et la prochaine action exacte.  
> Les entrées chronologiques ne sont pas réécrites rétroactivement.

## 1. North Star

Construire avant l’élection du 23 septembre 2026 un forecast territorial probabiliste, entièrement gelé et falsifiable, puis déterminer expérimentalement si une intelligence agentique de collecte et de raisonnement résiduel ajoute de l’information prédictive au-delà d’une baseline structurelle optimale.

## 2. État courant

- Timestamp : `2026-08-16T22:12:00+01:00`
- Branche active : `morocco26-fminus1`
- Base initiale : `main@2ccad2e5c89c710de85d8e1e992e65d5169986ca`
- Phase : `P6_PROBABILISTIC_FORECAST_ENGINE`
- Forecast publié : aucun
- Prochain snapshot autorisé : `F-1`
- Classe : `STRUCTURAL_PROBABILISTIC_FORECAST`
- P0 : `5 CLOSED / 1 OPEN`
- Gates F-1 restants : `UNCERTAINTY`, `MC-50000`, `IMMUTABILITY-MANIFEST`
- Agentique : `LOCKED` jusqu’au gel du premier moteur non agentique et de B2

## 3. Invariants anti-drift

1. Goal75 reste immuable ; aucune conclusion précédente n’est réécrite.
2. Aucun forecast n’est annoncé avant fermeture de ses gates machine.
3. Chaque snapshot `F-1/F0/F1/.../FINAL` est unique, timestampé, hashé et append-only.
4. Une nouvelle donnée ou méthode produit une nouvelle version, jamais une réécriture silencieuse.
5. La qualité narrative ne donne aucun crédit scientifique.
6. Le Model D/ancienne société d’électeurs LLM reste tué pour l’architecture actuelle.
7. La couche agentique future doit être comparée prospectivement à B2 avec le même cutoff.
8. Casablanca-Settat et Marrakech-Safi restent des anomalies de données/provenance jusqu’à preuve contraire.
9. Le moteur légal échoue fermé si l’âge candidat ou un tirage au sort manque lors d’une égalité contraignante.
10. Toute estimation locale des inscrits est étiquetée posterior latent, jamais compte officiel.
11. Le legal watch géographique reste actif même après fermeture de P0-1.
12. Une masse d’égalité légale, même minuscule, reste visible ; elle n’est jamais cassée par ordre alphabétique, parti ou voix.

## 4. Baseline scientifique gelée

- Vote core : `V0_PERSIST`
- Turnout core : `T0_PERSIST`
- Sélection : fit `2011→2016`, validation temporelle `2016→2021`
- Résultat : les extrapolations globales et régionales de swing ont été moins bonnes que la persistance.
- Conséquence : 2021 est le centre structurel ; tout déplacement 2026 doit être justifié par une couche mesurée.

## 5. Gates P0

| Gate | État | Preuve centrale | Reste à faire |
|---|---|---|---|
| P0-1 Géographie 2026 | **CLOSED** | `geometry_2026_certificate.json` : 92/92, 305 ; 12/12, 90 ; zéro différence | legal watch uniquement |
| P0-2 Allocator légal | **CLOSED** | régression mathématique 104/104 | surveillance uniquement |
| P0-3 Inscrits N | **CLOSED** | `local_N_posterior.json` : 50k tirages exacts + sensibilité 92+12 | utiliser conjointement dans F-1 |
| P0-4 Historique | **CLOSED** | 2011/2016/2021, 92/92 continus | ne pas rouvrir sans nouvelle preuve |
| P0-5 B* | **CLOSED** | `V0_PERSIST / T0_PERSIST` | construire B2 après F-1 |
| P0-6 Incertitude | OPEN | architecture national + région + local | fit, calibration, couverture, simulation cohérente |

## 6. Gates avant F-1

| Ordre | Gate | État | Artefact |
|---:|---|---|---|
| 1 | `GEO-2026-AUTHORITATIVE-DIFF` | **CLOSED** | `geometry_2026_certificate.json` |
| 2 | `N92-POSTERIOR-FIT` | **CLOSED** | `local_N_posterior.json` |
| 3 | `UNCERTAINTY-CALIBRATION` | OPEN | `uncertainty_calibration.json` |
| 4 | `MC-50000-COHERENT` | OPEN | `simulation_certificate.json` |
| 5 | `SNAPSHOT-IMMUTABILITY-MANIFEST` | OPEN | manifest F-1 complet |

## 7. Contrat de F-1

F-1 doit produire, sans couche agentique :

- 92 distributions locales de vote et de sièges ;
- 12 distributions régionales ;
- une distribution jointe des 395 sièges ;
- `P(seats=k)` par parti et territoire ;
- sièges attendus et intervalles crédibles ;
- sensibilité attribuable uniquement à l’incertitude sur N ;
- diagnostics de calibration, normalisation, Monte-Carlo et allocations légales ;
- manifest immuable enregistré dans `forecast_registry.json`.

## 8. Décisions actives

- `D-001` — Produire F-1 structurel avant le F0 conventionnel.
- `D-002` — F0 sera le premier forecast préliminaire enrichi par B2.
- `D-003` — Ne pas attendre les listes définitives de candidats pour F-1.
- `D-004` — N92 reste un posterior latent contraint tant que les comptes officiels locaux manquent.
- `D-005` — Interdire une covariance territoriale libre 92×92 ; utiliser facteurs national, régional et résidu local shrinké.
- `D-006` — Séparer collecte agentique et raisonnement agentique pour attribution causale future.
- `D-007` — Conserver le HTTP 403 du Parlement comme limite de reproductibilité ; témoin statique sourcé + legal watch.
- `D-008` — La dérive 2007→2011 sert de variance floor, pas de loi stationnaire affirmée.

## 9. Exécution en cours

### Lot F-1A — Vérité mécanique

- [x] Certificat géographique 92+12.
- [x] Legal watch actif.
- [x] Posterior contraint N92.
- [x] Sensibilité N-only locale et régionale.

### Lot F-1B — Vérité probabiliste

- [ ] Fitter les innovations nationales, régionales et locales post-sélection.
- [ ] Appliquer les variance floors empiriques.
- [ ] Exécuter la validation rétrospective de couverture et proper scores.
- [ ] Certifier la cohérence jointe vote/turnout/N/allocator.

### Lot F-1C — Gel et publication

- [ ] Exécuter au moins 50 000 simulations.
- [ ] Générer l’artefact F-1 et son manifest.
- [ ] Enregistrer F-1 sans écraser aucun artefact.
- [ ] Mettre à jour les trois registres machine.

## 10. Journal chronologique

### 2026-08-16 21:52 +01 — Reprise Goal100 / lancement F-1

- Branche `morocco26-fminus1` créée depuis le `main` post-tracking.
- Le présent fichier devient le journal canonique de reprise.
- Aucun forecast n’est émis.

### 2026-08-16 21:56 +01 — Probe géographique

- Les pages officielles du Parlement retournent HTTP 403 depuis GitHub Actions.
- Le WAF est enregistré ; aucun fallback secondaire silencieux.

### 2026-08-16 22:02 +01 — P0-1 fermé

- `geometry_2026_certificate.json` : `PASS`.
- Local `92/92`, `305/305`; régional `12/12`, `90/90`; total `395`; zéro différence.
- Legal watch maintenu actif.

### 2026-08-16 22:12 +01 — P0-3 fermé

- `local_N_posterior.json` : `PASS`.
- `50 000` tirages ; 92 entiers positifs ; somme exacte `15 801 162` à chaque tirage ; zéro violation de floor.
- Variance historique : 74 appariements exacts 2007→2011, décomposition shrinkée région/local, floor total `0,2230517` en log-share.
- 81 territoires sont mathématiquement invariants à N ; 11 sensibles ; seuls 2 reçoivent une masse de changement dans le posterior.
- 5 des 12 régions reçoivent une masse de changement N-only.
- Une égalité légale locale non résolue sur 50 000 tirages (`0,00002`) est conservée ; aucune égalité régionale.
- Draw-stream hash : `092382b44873c2ee709e3fb62566247980c11eee29daf2758f0a1e1a52919d71`.

## 11. Prochaine action exacte

**Fitter et certifier `uncertainty_calibration.json` : modèle hiérarchique compositionnel et turnout séparé, facteurs national/régional/local, variance floors explicites, validation rétrospective par proper scores et couverture, sans covariance libre 92×92 ni retuning silencieux.**


### 2026-08-17 — Phase d'acquisition déterministe B2 — ouverture et premier résultat

**Prompt agentique antérieur rejeté.** Le master-prompt d'orchestration agentique est incompatible avec
le protocole gelé `M26-GOAL100-B2-PROTOCOL-V1` : `agentic_status = PROHIBITED_AND_LOCKED`, découverte
autonome de sources interdite, et `extraction.llm_used` fixé à la constante `false` dans le schéma de
preuve. Aucune collecte agentique n'a été exécutée et aucune contrainte n'a été relâchée.

**Statut B2-3 conservé.** Le résultat reste `UNIDENTIFIABLE`, et non un résultat prédictif négatif :
features identifiables `0/16` (fit) et
`0/16` (validation), couverture prédictive centrale
`0.0` / `0.0` pour un minimum requis de
`0.8`. Aucun coefficient n'a bougé. La tentative antérieure est archivée sous
`b2_historical_panel_attempts/`.

**Phase d'acquisition déterministe ouverte.** Surface figée à partir des seuls contrats déjà commités :
`19` entrées du registre B2 (dont
`11` éligibles aux claims) et
`6` entrées de provenance historique.
Hash de surface `5845c2514bdb2b10b77f1d1a35b939681c0f7cf763a936a6c626e99e4f79d94c`. Mesure décisive : les gabarits de requête gelés
n'expriment que `[2026]` —
le registre B2 ne porte aucune surface d'acquisition historique.

**Acquisition réussie.** Le jeu de données de membres déjà référencé par `observed_elected_2021.json`
contient les quatre législatures. Parser `M26-GOAL100-B2-MEMBER-PARSER` v`1.0`, méthode
`STRUCTURED_API`, `llm_used = false`. Élus récupérés :
2007 → 225 locaux sur 74 territoires, 2011 → 305 locaux sur 92 territoires, 2016 → 305 locaux sur 92 territoires, 2021 → 305 locaux sur 92 territoires.
Le contrôle de correction est 2021, qui reproduit exactement le partage certifié 305 locaux + 90 régionaux.
Les `Liste nationale` restent non résolues : elles n'ont pas de circonscription certifiée.

**Couverture avant/après.** Classes d'entrée bloquantes : `17` → `16`.
`HISTORICAL_ELECTED_MEMBERS_PRIOR_YEAR` passe d'absente à couverte pour les deux transitions. La couverture
prédictive reste `0.0` : le blocage résiduel dominant est `HISTORICAL_CANDIDATE_ROSTER_TARGET_YEAR`.

**Wave 1 2026.** `30` documents acquis, `10` `BLOCKED_SOURCE`,
`0` claim B2 créé. Verdict d'extractibilité :
`DETERMINISTIC_ROSTER_SURFACE_EXISTS_FOR_2026` — une table de `93`
lignes sur `T1_PJD_OFFICIAL` correspond au
vocabulaire de preuve gelé. Elle ne produit aucun claim ici : la règle de double saisie critique exige deux
lectures concordantes ou une table structurée T0 autoritative, et une page de parti T1 ne l'est pas.

**Incohérences de validateurs.** `2` assertions périmées après la fermeture
légitime de B2-2 ; `1` artefact d'environnement. Correction d'une
affirmation antérieure : l'échec de `validate_goal100_tracking` n'était pas un défaut du dépôt mais un effet
de `core.autocrlf=true`. Intégrité F-1 : `INTACT`. Aucun artefact F-1 n'a été réparé.

**Résultat de gate.** `C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL`. `ready_for_b2_backtest = false`.
`16` classes d'entrée sont réservées non résolues pour
`E_collect` ; elles ne doivent pas être comblées par de la recherche agentique.

**Prochaine action exacte :** décider entre (a) un amendement versionné de l'univers de sources ouvrant une
surface historique de rosters de candidats, et (b) le maintien de `C_UNIDENTIFIABLE_UNDER_FROZEN_PROTOCOL`.
Dans les deux cas aucun coefficient prédictif ne bouge et `B2-4` reste le prochain gate exécutable.
