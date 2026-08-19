# ATLAS // Société artificielle

Front-end public de l'expérience de société électorale artificielle `EXP_7C8A2F11` /
`ENV_4D19B3E7`. Page unique, statique, en français, sans jargon technique.

**Ce que la page montre.** Comment 94 208 décisions de vote simulées se forment : les onze
forces qui les pilotent, les profils qui changent de camp, ceux qui sanctionnent le bilan
sortant, ceux qui répondent au programme ou à la figure locale, un démonstrateur qui recalcule
une décision en direct et, désormais, une couche sociale illustrative famille / collègues /
voisinage qui permet de comprendre la propagation R0 → R1 → R2.

**Ce que la page ne montre pas.** Aucun résultat électoral caché, aucun siège ni information
provenant d'un outcome non unsealed n'est utilisé par la couche sociale. Les agrégats publics
du corpus historique restent bruts et non pondérés — le corpus ne fournit aucun poids de
population. La section sociale publique est explicitement marquée **illustrative et non
calibrée** : elle n'est pas le résultat du backtest 2016 → 2021.

## Arborescence

```text
vercel.json              en-têtes de sécurité + réécritures
web/
  index.html             structure, aucun script ni style en ligne
  styles.css             charte, rampes ordinales, thème sombre unique
  reader-final.css       extension du lecteur historique
  social.css             présentation de la couche sociale
  app.js                 rendu, interactions, portage du moteur de décision privé
  reader.js              lecteur 2016 / 2021
  social.js              démonstrateur social R0 / R1 / R2, non calibré
  data/
    societe.json         agrégats descriptifs sur les 94 208 décisions
    portraits.json       3 000 décisions individuelles échantillonnées
    simulateur.json      contexte + vecteurs de base + points de contrôle
    social_config.json   paramètres uniquement illustratifs du front
social/
  PROTOCOL.md
  SOCIAL_EXPERIMENT_MANIFEST.json
  SOCIAL_GRAPH_SPEC.json
  SOCIAL_OUTPUT_SCHEMA.json
  OUTCOME_ADAPTER_SCHEMA.json
  SOCIAL_PROMPT.txt
  SOCIAL_MANIFEST.sha256
  engine/
    build_social_graph.py
    deterministic_social.py
    run_social_experiment.py
    calibrate_lambda.py
    score_social.py
    run_agentic_social.py
    validate_social.py
  tests/
    test_social_engine.py
```

## Invariant de la V1 isolée

`scripts/judge_engine.py` reste le juge privé de référence et n'est pas modifié par cette
extension. Ses décisions constituent **R0 / ISO**, le contrôle immuable.

La couche sociale ne remplace donc pas le vote privé. Elle consomme R0 après coup, au travers
d'un graphe synthétique séparé et gelé.

## Ce que signifie le graphe social

Les 256 objets d'un territoire sont des **archétypes**, pas 256 personnes littéralement
voisines. Une relation sociale est donc une distribution d'exposition plausible entre strates :

- `family` : structure du foyer, taille, statut matrimonial, âge, milieu, niveau de vie ;
- `work` : uniquement pour les actifs employés, avec secteur / occupation / profession ;
- `neighborhood` : milieu, niveau de vie, SES, âge, structure du foyer, secteur, éducation.

Aucun lien ne traverse un work item et les pseudonymes `Q_01 ... Q_09` ne circulent jamais entre
territoires.

## Dynamique R0 → R1 → R2

- **R0 / ISO** : décisions isolées existantes ;
- **R1** : exposition directe, calculée simultanément depuis l'intégralité de R0 ;
- **R2** : propagation de second ordre, calculée simultanément depuis l'intégralité de R1 ;
- **STOP** : aucune simulation jusqu'à convergence.

Le moteur déterministe applique un pooling logarithmique borné. Une décision très certaine
résiste davantage qu'une décision diffuse. La participation est déplacée en log-odds. Lorsque
les trois `lambda` valent zéro, la décision est identique bit pour bit sur les champs de décision.

## Ablations et falsification

Les conditions pré-enregistrées sont :

`ISO, FAM, WORK, NEIGH, ALL, SHUFFLE, ALL_R2`

`SHUFFLE` conserve pour chaque agent le nombre de contacts et leurs poids sortants mais
réassigne les cibles : il sert de placebo de topologie.

La calibration de `lambda_family / lambda_work / lambda_neighborhood` se fait uniquement sur le
scrutin de calibration explicitement unsealed. Le script refuse un fichier outcome contenant
un deuxième scrutin. Le fichier de lambdas est ensuite gelé avant le holdout suivant.

La couche LLM est elle aussi séparée : elle ne peut retourner que des ajustements sociaux bornés
à partir de l'état privé et des expositions agrégées. Elle n'est jamais autorisée à introduire
de nouveaux faits politiques ou à refaire le vote privé. Le vrai test est donc également
`agentic social` vs `deterministic social`.

Voir `social/PROTOCOL.md` et `social/README.md` pour le protocole et les commandes exactes.

## Déploiement

Dépôt statique, aucune étape de compilation.

```bash
vercel --prod
```

En local :

```bash
python -m http.server 5178 --directory web
```

## Sécurité

`vercel.json` applique une CSP stricte sans aucune échappatoire. La couche sociale ne rajoute
ni CDN, ni police distante, ni télémétrie, ni appel outcome. `social.js` charge seulement
`data/portraits.json` et `data/social_config.json` depuis la même origine.

## Fidélité du démonstrateur privé

`app.js` réimplémente le moteur de décision utilisé pour produire le corpus. La fidélité de ce
portage reste contrôlée par les douze points de contrôle existants de `data/simulateur.json`.
La couche sociale n'altère ni ces points de contrôle ni `scripts/judge_engine.py`.

## Reproductibilité sociale

Depuis `source_v2/` :

```bash
python -m unittest discover -s social/tests -p 'test_*.py' -v
python social/engine/build_social_graph.py /path/to/FROZEN_ENV /path/to/social_graphs
python social/engine/validate_social.py graphs /path/to/FROZEN_ENV /path/to/social_graphs
```

La procédure complète calibration → ablations → validation → holdout est documentée dans
`social/README.md`.

## Provenance

Le `MANIFEST_source_v2.sha256` parent reste la trace du bundle historique et des divergences déjà
documentées avant cette extension. Il n'est pas réécrit pour faire disparaître l'historique.

`social/SOCIAL_MANIFEST.sha256` est le manifest **additif** de cette couche et enregistre les
fichiers scientifiques et frontaux ajoutés ou modifiés pour l'expérience sociale.
