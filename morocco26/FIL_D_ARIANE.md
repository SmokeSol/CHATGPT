# MOROCCO//26 — FIL D’ARIANE

> Journal canonique de reprise et d’exécution du programme Goal100.  
> Ce fichier conserve le cap, les décisions, les preuves, les blockers et la prochaine action exacte.  
> Il est mis à jour à chaque transition matérielle ; les entrées chronologiques ne sont pas réécrites rétroactivement.

## 1. North Star

Construire avant l’élection du 23 septembre 2026 un forecast territorial probabiliste, entièrement gelé et falsifiable, puis déterminer expérimentalement si une intelligence agentique de collecte et de raisonnement résiduel ajoute de l’information prédictive au-delà d’une baseline structurelle optimale.

## 2. État courant

- Timestamp : `2026-08-16T21:52:26+01:00`
- Branche active : `morocco26-fminus1`
- Base : `main@2ccad2e5c89c710de85d8e1e992e65d5169986ca`
- Phase : `P6_PROBABILISTIC_FORECAST_ENGINE`
- Forecast publié : aucun
- Prochain snapshot autorisé : `F-1`
- Classe : `STRUCTURAL_PROBABILISTIC_FORECAST`
- F0 : préliminaire, postérieur à F-1 sauf découverte méthodologique imposant une version plus précoce
- Agentique : `LOCKED` jusqu’au gel du premier moteur non agentique et de B2

## 3. Invariants anti-drift

1. Goal75 reste immuable ; aucune conclusion précédente n’est réécrite.
2. Aucun forecast n’est annoncé avant fermeture de ses gates machine.
3. Chaque snapshot `F-1/F0/F1/.../FINAL` est unique, timestampé, hashé et append-only.
4. Un nouveau modèle ou une nouvelle donnée produit une nouvelle version ; jamais une réécriture silencieuse.
5. La qualité narrative ne donne aucun crédit scientifique.
6. Le Model D/ancienne société d’électeurs LLM reste tué pour l’architecture actuelle.
7. La couche agentique future doit être comparée prospectivement à B2 avec le même cutoff.
8. Les anomalies Casablanca-Settat et Marrakech-Safi restent explicitement des anomalies de données/provenance tant qu’aucune preuve contraire n’est obtenue.
9. Le moteur légal échoue fermé en cas d’égalité exigeant âge ou tirage au sort non disponible.
10. Toute estimation locale des inscrits est étiquetée posterior latent, jamais compte officiel.

## 4. Baseline scientifique gelée

- Vote core : `V0_PERSIST`
- Turnout core : `T0_PERSIST`
- Sélection : fit `2011→2016`, validation temporelle `2016→2021`
- Résultat : les extrapolations globales et régionales de swing ont été moins bonnes que la persistance.
- Conséquence : 2021 est le centre structurel ; tout déplacement 2026 doit être justifié par une couche explicitement mesurée.

## 5. Gates P0

| Gate | État | Preuve centrale | Reste à faire |
|---|---|---|---|
| P0-1 Géographie 2026 | PARTIAL | 92 locaux / 305 + 12 régionaux / 90 ; continuité moderne 92/92 | certificat autoritatif ligne par ligne + legal watch |
| P0-2 Allocator légal | CLOSED | régression mathématique 104/104 | surveillance uniquement |
| P0-3 Inscrits N | OPEN | N national exact 15 801 162 ; variance historique ancrée | posterior contraint N92 + sensibilité sièges |
| P0-4 Historique | CLOSED | 2011/2016/2021, 92/92 continus | aucune réouverture sans nouvelle preuve |
| P0-5 B* | CLOSED | V0_PERSIST / T0_PERSIST | construire B2 après F-1 |
| P0-6 Incertitude | OPEN | architecture national + région + local | fit, calibration, couverture, simulation cohérente |

## 6. Gates avant F-1

| Ordre | Gate | Artefact attendu | Critère de fermeture |
|---:|---|---|---|
| 1 | `GEO-2026-AUTHORITATIVE-DIFF` | `data/goal100/geometry_2026_certificate.json` | 92+12 contrôlés, zéro écart inexpliqué |
| 2 | `N92-POSTERIOR-FIT` | `data/goal100/local_N_posterior.json` | chaque draw positif entier, somme exacte 15 801 162, diagnostics publiés |
| 3 | `UNCERTAINTY-CALIBRATION` | `data/goal100/uncertainty_calibration.json` | variance floors + couverture et proper scores rétrospectifs |
| 4 | `MC-50000-COHERENT` | `data/goal100/simulation_certificate.json` | ≥50 000 élections jointes valides, erreurs MC bornées |
| 5 | `SNAPSHOT-IMMUTABILITY-MANIFEST` | manifest F-1 | code/data/paramètres/seeds/cutoff/hashes complets |

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

- `D-001` — Ne pas appeler le prochain objet F0 : produire d’abord F-1 structurel.
- `D-002` — F0 sera le premier forecast préliminaire enrichi par B2, pas le premier test du moteur.
- `D-003` — Ne pas attendre les listes définitives de candidats pour F-1.
- `D-004` — Modéliser N92 comme variable latente contrainte tant que les comptes locaux officiels ne sont pas obtenus.
- `D-005` — Interdire une covariance territoriale libre 92×92 ; utiliser facteurs national, régional et résidu local shrinké.
- `D-006` — Garder les couches collecte agentique et raisonnement agentique séparées pour attribution causale future.

## 9. Exécution en cours

### Lot F-1A — Fermer la vérité mécanique

- [ ] Construire le certificat géographique 2026.
- [ ] Vérifier qu’aucun texte officiel plus récent ne remplace la géographie de travail.
- [ ] Produire le posterior contraint N92.
- [ ] Mesurer la sensibilité N-only des sièges.

### Lot F-1B — Fermer la vérité probabiliste

- [ ] Fitter les innovations nationales, régionales et locales post-sélection.
- [ ] Appliquer les variance floors empiriques.
- [ ] Exécuter la validation rétrospective de couverture et proper scores.
- [ ] Certifier la cohérence jointe vote/turnout/N/allocator.

### Lot F-1C — Geler et publier

- [ ] Exécuter au moins 50 000 simulations.
- [ ] Générer l’artefact F-1 et son manifest.
- [ ] Enregistrer F-1 sans écraser aucun artefact.
- [ ] Mettre à jour `current_state.json`, `gate_registry.json` et `forecast_registry.json`.

## 10. Journal chronologique

### 2026-08-16 21:52 +01 — Reprise Goal100 / lancement F-1

- Demande utilisateur : procéder vers le forecast et conserver un fil d’Ariane dans le repo.
- Branche `morocco26-fminus1` créée depuis le `main` post-tracking.
- Le présent fichier devient le journal canonique de reprise.
- Prochaine action exacte : construire et exécuter le gate `GEO-2026-AUTHORITATIVE-DIFF`.
- Aucun forecast n’est encore émis.

## 11. Prochaine action exacte

**Établir `geometry_2026_certificate.json` à partir des sources autoritatives courantes, avec diff ligne par ligne contre `constituencies_goal75.csv`, puis fermer P0-1 uniquement si zéro écart inexpliqué subsiste.**
