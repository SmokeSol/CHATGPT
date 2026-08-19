# ATLAS Social Influence V1

Extension additive de `source_v2` pour famille, collègues, voisinage et propagation inter-agents.

Le juge privé existant reste inchangé. Le répertoire `social/` ne contient que la couche
d'exposition sociale, ses protocoles, ses validations et ses adapters outcome post-unseal.

## Arborescence

```text
social/
  PROTOCOL.md
  SOCIAL_EXPERIMENT_MANIFEST.json
  SOCIAL_GRAPH_SPEC.json
  SOCIAL_OUTPUT_SCHEMA.json
  OUTCOME_ADAPTER_SCHEMA.json
  SOCIAL_PROMPT.txt
  SOCIAL_MANIFEST.sha256
  engine/
    common.py
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

Tout est standard-library Python.

## 1. Tests unitaires

Depuis `source_v2/` :

```bash
python -m unittest discover -s social/tests -p 'test_*.py' -v
```

## 2. Geler les graphes

```bash
python social/engine/build_social_graph.py \
  /path/to/FROZEN_ENV \
  /path/to/social_graphs
```

Puis :

```bash
python social/engine/validate_social.py graphs \
  /path/to/FROZEN_ENV \
  /path/to/social_graphs
```

Le builder n'ouvre ni RUN ni outcomes.

## 3. Calibration 2016

Préparer après unseal un adapter conforme à `OUTCOME_ADAPTER_SCHEMA.json` qui ne contient
**que** l'`anonymous_election_id` 2016.

```bash
python social/engine/calibrate_lambda.py \
  /path/to/FROZEN_ENV \
  /path/to/R0_RUN \
  /path/to/social_graphs \
  /path/to/outcomes_2016_only.json \
  E_2016_ANON_ID \
  /path/to/calibrated_lambdas_2016.json
```

Le script refuse un fichier contenant un autre scrutin.

## 4. Générer les ablations avec les lambdas gelés

```bash
python social/engine/run_social_experiment.py \
  /path/to/FROZEN_ENV \
  /path/to/R0_RUN \
  /path/to/social_graphs \
  /path/to/social_run \
  --lambda-file /path/to/calibrated_lambdas_2016.json
```

Conditions produites par défaut :

`ISO,FAM,WORK,NEIGH,ALL,SHUFFLE,ALL_R2`

Validation :

```bash
python social/engine/validate_social.py run \
  /path/to/FROZEN_ENV \
  /path/to/R0_RUN \
  /path/to/social_graphs \
  /path/to/social_run
```

## 5. Holdout 2021

Fournir l'adapter 2021 seulement après le gel des lambdas :

```bash
python social/engine/score_social.py \
  /path/to/social_run \
  ALL_R2 \
  /path/to/outcomes_2021_only.json \
  --election-id E_2021_ANON_ID \
  --output /path/to/score_2021_ALL_R2.json
```

Répéter le scorer pour les ablations, sans modifier les lambdas.

## 6. Couche LLM sociale

### Émettre les requêtes fermées

```bash
python social/engine/run_agentic_social.py emit \
  /path/to/FROZEN_ENV \
  /path/to/R0_RUN \
  /path/to/social_graphs \
  /path/to/social_requests_R1.jsonl \
  --lambda-file /path/to/calibrated_lambdas_2016.json
```

### Appeler un endpoint OpenAI-compatible, optionnel

```bash
SOCIAL_LLM_API_KEY=... \
python social/engine/run_agentic_social.py call \
  /path/to/social_requests_R1.jsonl \
  /path/to/social_responses_R1.jsonl \
  --endpoint https://YOUR_ENDPOINT/v1/chat/completions \
  --model YOUR_MODEL \
  --workers 4
```

### Valider et appliquer les réponses

```bash
python social/engine/run_agentic_social.py apply \
  /path/to/FROZEN_ENV \
  /path/to/R0_RUN \
  /path/to/social_requests_R1.jsonl \
  /path/to/social_responses_R1.jsonl \
  /path/to/agentic_R1_RUN \
  --lambda-file /path/to/calibrated_lambdas_2016.json
```

Le mode `emit` permet aussi d'utiliser Claude/Opus ou tout autre transport hors du runner sans
modifier le protocole : seul le JSON conforme au schéma peut être réinjecté.

## 7. Front

`web/social.js` + `web/social.css` ajoutent une section « L'entourage entre dans le vote » au
parcours public. Elle utilise `web/data/portraits.json` et
`web/data/social_config.json`.

La configuration front est marquée `ILLUSTRATIVE_NOT_CALIBRATED` afin d'empêcher de confondre
la démonstration pédagogique avec la calibration scientifique.
