# ATLAS — Protocole de société inter-agents V1

## 0. Objet

Cette extension teste une seule hypothèse falsifiable :

> **à information politique privée identique, la structure et la propagation de l'exposition sociale
> (famille, travail, voisinage) ajoutent-elles du signal prédictif hors échantillon par rapport aux
> agents strictement isolés ?**

Elle ne remplace pas le juge privé existant. Elle vient **après** lui.

La branche de référence conserve donc le corpus R0 actuel comme contrôle immuable. Le social est
une expérience additive, avec son propre manifest, ses propres hashes et ses propres sorties.

## 1. Frontière anti-drift

Le graphe social est construit uniquement depuis les cartes d'archétypes électeurs déjà présentes
dans l'environnement gelé. Le builder :

- n'ouvre aucun output de décision ;
- n'ouvre aucun résultat historique ;
- ne connaît aucun mapping réel derrière `Q_01 ... Q_09` ;
- n'utilise aucun nom de parti, candidat ou territoire ;
- ne relie jamais deux work items entre eux.

Une arête n'affirme pas « A017 est réellement le frère de A044 ». Les 256 objets sont des
archétypes, pas des personnes. Une arête signifie :

> pour un représentant de cette strate, cette autre strate constitue une source plausible
> d'exposition sociale de type famille / travail / voisinage.

Le graphe est donc une matrice d'exposition synthétique et reproductible.

## 2. Trois réseaux

### Famille

Compatibilité sur la structure du foyer, le niveau de vie, le milieu, la taille du ménage,
le statut matrimonial et un noyau d'âge suffisamment large pour autoriser pairs, conjoints
et générations différentes. Maximum : 4 strates d'exposition par source.

### Travail

Réservé aux archétypes `ACTIVE_EMPLOYED`. Compatibilité sur secteur, profession, occupation,
niveau de vie, milieu, éducation et âge. Maximum : 6 strates.

### Voisinage

Homophilie territoriale interne au work item : urbain/rural, niveau de vie, SES, âge,
structure du foyer, secteur et éducation. Maximum : 8 strates.

Les poids sortants d'une relation sont toujours normalisés à 1 lorsqu'au moins une exposition
compatible existe.

## 3. États et synchronisation

### R0 — `ISO`

Sortie actuelle du juge privé. Aucun voisin n'est visible.

### R1

Chaque agent voit uniquement des **agrégats pondérés de R0** provenant de ses trois réseaux.
Tous les nouveaux états R1 sont calculés après que l'intégralité de R0 a été lue.

### R2

Même mécanisme, mais les expositions sont calculées depuis l'intégralité de R1.

**Arrêt obligatoire après R2.** Il n'y a pas de boucle « jusqu'à convergence ».

Cette règle élimine l'effet arbitraire de l'ordre d'exécution.

## 4. Baseline sociale déterministe

La distribution privée reste l'ancre. Pour chaque relation disponible, le moteur calcule la
distribution moyenne des contacts et applique un pooling logarithmique borné.

Une décision très concentrée résiste davantage ; une décision diffuse est plus susceptible.
La participation est mise à jour de la même manière en log-odds.

Propriétés contractuelles :

- `lambda_family = lambda_work = lambda_neighborhood = 0` ⇒ identité exacte ;
- la somme des probabilités de partis reste 1 ;
- les probabilités de participation restent dans `[0,1]` ;
- un round ne peut pas effacer entièrement l'information privée ;
- `factor_importance` et les `reason_codes` du juge privé ne sont pas réécrits comme s'ils
  expliquaient l'effet social : l'effet social reçoit son propre bloc `social_influence`.

## 5. Ablations pré-enregistrées

| Condition | Traitement |
|---|---|
| `ISO` | aucun réseau |
| `FAM` | famille, R1 |
| `WORK` | travail, R1 |
| `NEIGH` | voisinage, R1 |
| `ALL` | trois réseaux, R1 |
| `SHUFFLE` | mêmes nombres de contacts et mêmes poids sortants, cibles réassignées |
| `ALL_R2` | trois réseaux, R1 puis R2 |

`SHUFFLE` teste si un gain vient réellement de la topologie compatible ou simplement d'un
lissage supplémentaire.

## 6. Calibration 2016 → gel → holdout 2021

La grille est gelée dans `SOCIAL_EXPERIMENT_MANIFEST.json`.

Objectif de calibration :

`party_share_rmse + 0.25 * turnout_rmse`

Le script `calibrate_lambda.py` exige un fichier d'outcomes contenant **exactement un seul
anonymous_election_id**, celui déclaré comme calibration. S'il trouve un deuxième scrutin, il
s'arrête. Ainsi un fichier 2016 ne peut pas embarquer accidentellement 2021.

Après sélection, le fichier de lambdas porte le statut :

`CALIBRATED_ON_DECLARED_ELECTION_ONLY_FROZEN_FOR_HOLDOUT`

Ce fichier doit ensuite être utilisé tel quel sur 2021.

Aucune modification du graphe, des seuils, des features, des ablations, du prompt social ou de
l'objectif n'est autorisée après ouverture de la calibration.

## 7. Couche agentique sociale

Le LLM n'est pas autorisé à refaire le vote privé.

Il reçoit seulement :

1. le profil synthétique non politique ;
2. l'état privé déjà produit par Rk ;
3. les distributions agrégées famille / travail / voisinage ;
4. le budget de force de chaque relation.

Il renvoie seulement des ajustements bornés :

- `turnout_delta_logit ∈ [-0.75, 0.75]` ;
- ajustement relatif de chaque pseudonyme `∈ [-1,1]` ;
- reliance par relation `∈ [0,1]` ;
- un petit vocabulaire fermé de reason codes.

Le runner centre, clippe et reborne encore la réponse avant application.

La comparaison pertinente est donc :

`agentic social` **vs** `deterministic social`, et non seulement `agentic social` vs `ISO`.

## 8. Scoring

Le social n'accède jamais directement aux fichiers de résultat du projet. Le scorer accepte un
**adapter explicitement fourni après unseal** conforme à `OUTCOME_ADAPTER_SCHEMA.json`.

Pour chaque work item, il agrège les décisions exactement sans inventer de poids de population :
moyenne non pondérée des archétypes, cohérente avec le front actuel qui précise que le corpus ne
fournit pas de poids.

Métriques disponibles :

- RMSE et MAE des parts de vote ;
- cross-entropy ;
- divergence Jensen-Shannon ;
- RMSE et MAE de participation.

Le résultat négatif est valide. Si `ALL_R2` ne bat pas `ISO` sur le holdout, la couche sociale
n'est pas promue comme amélioration prédictive.

## 9. Front public

Le front utilise uniquement l'échantillon de 3 000 portraits déjà publié. Il reconstruit à la
volée un petit graphe d'exposition compatible pour expliquer R0 → R1 → R2.

**Cette visualisation est explicitement illustrative et non calibrée.** Elle ne lit aucun outcome
historique et ne doit pas être présentée comme forecast.

## 10. Gates minimaux avant toute conclusion

1. `python -m unittest discover social/tests`
2. `validate_social.py graphs ...`
3. zero-lambda identity `<= 1e-15`
4. `validate_social.py run ...`
5. calibration sur un fichier ne contenant que 2016
6. gel du fichier de lambdas
7. scoring 2021 sans retouche
8. comparaison `ISO / FAM / WORK / NEIGH / ALL / SHUFFLE / ALL_R2`
9. comparaison optionnelle `agentic social / deterministic social`

Aucune conclusion « plus réaliste » ne remplace ces gates.
