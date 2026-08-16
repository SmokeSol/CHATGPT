# MOROCCO//26 — FIL D’ARIANE

> Journal canonique de reprise et d’exécution du programme Goal100.  
> Il conserve le cap, les décisions, les preuves, les blockers et la prochaine action exacte.  
> Les entrées chronologiques ne sont pas réécrites rétroactivement.

## 1. North Star

Construire avant l’élection du 23 septembre 2026 un forecast territorial probabiliste, entièrement gelé et falsifiable, puis déterminer expérimentalement si une intelligence agentique de collecte et de raisonnement résiduel ajoute de l’information prédictive au-delà d’une baseline structurelle optimale.

## 2. État courant

- Timestamp : `2026-08-16T22:02:13+01:00`
- Branche active : `morocco26-fminus1`
- Base initiale : `main@2ccad2e5c89c710de85d8e1e992e65d5169986ca`
- Phase : `P6_PROBABILISTIC_FORECAST_ENGINE`
- Forecast publié : aucun
- Prochain snapshot autorisé : `F-1`
- Classe : `STRUCTURAL_PROBABILISTIC_FORECAST`
- P0 : `4 CLOSED / 2 OPEN`
- Gates F-1 restants : `N92`, `UNCERTAINTY`, `MC-50000`, `IMMUTABILITY-MANIFEST`
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
| P0-3 Inscrits N | OPEN | N national exact 15 801 162 ; variance historique ancrée | posterior contraint N92 + sensibilité sièges |
| P0-4 Historique | **CLOSED** | 2011/2016/2021, 92/92 continus | ne pas rouvrir sans nouvelle preuve |
| P0-5 B* | **CLOSED** | `V0_PERSIST / T0_PERSIST` | construire B2 après F-1 |
| P0-6 Incertitude | OPEN | architecture national + région + local | fit, calibration, couverture, simulation cohérente |

## 6. Gates avant F-1

| Ordre | Gate | État | Artefact attendu |
|---:|---|---|---|
| 1 | `GEO-2026-AUTHORITATIVE-DIFF` | **CLOSED** | `geometry_2026_certificate.json` |
| 2 | `N92-POSTERIOR-FIT` | OPEN | `local_N_posterior.json` |
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
- `D-004` — Modéliser N92 comme variable latente contrainte tant que les comptes locaux officiels manquent.
- `D-005` — Interdire une covariance territoriale libre 92×92 ; utiliser facteurs national, régional et résidu local shrinké.
- `D-006` — Séparer collecte agentique et raisonnement agentique pour attribution causale future.
- `D-007` — Conserver le HTTP 403 du Parlement comme limite de reproductibilité ; utiliser un témoin statique sourcé et un legal watch, sans prétendre à un live fetch inexistant.

## 9. Exécution en cours

### Lot F-1A — Vérité mécanique

- [x] Construire le certificat géographique 2026.
- [x] Vérifier les 92 lignes locales et 12 magnitudes régionales.
- [x] Maintenir le legal watch pour tout décret supersédant.
- [ ] Produire le posterior contraint N92.
- [ ] Mesurer la sensibilité N-only des sièges.

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

### 2026-08-16 21:56 +01 — Probe des sources géographiques

- Les trois pages officielles du Parlement retournent HTTP 403 depuis GitHub Actions.
- Le blocage WAF est enregistré dans `geometry_2026_probe.json`; aucun fallback secondaire silencieux n’est utilisé.
- Les contenus officiels accessibles via index de recherche et la loi organique SGG sont transformés en témoins statiques sourcés.

### 2026-08-16 22:02 +01 — P0-1 fermé

- `geometry_2026_certificate.json` : `PASS`.
- Local : `92/92` lignes appariées, `305/305` sièges, zéro différence.
- Régional : `12/12` lignes, `90/90` sièges, zéro différence.
- Total Chambre : `395`.
- `p0_resolution_v4.json`, `gate_registry.json` et `current_state.json` mis à jour.
- Legal watch maintenu actif ; aucune prétention de live fetch direct.

## 11. Prochaine action exacte

**Construire `local_N_posterior.json` : une distribution jointe sur 92 entiers positifs, contrainte à sommer exactement à 15 801 162, ancrée sur les parts locales 2011 et la dérive 2007→2011, puis mesurer pour chaque territoire la probabilité qu’un changement de N seul modifie l’allocation des sièges.**
