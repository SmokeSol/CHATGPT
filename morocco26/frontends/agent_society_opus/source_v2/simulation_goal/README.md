# Agent Society — objectif canonique à trois régimes

Ce dossier est le point d’entrée du redesign méthodologique décidé après le premier lot Sol de 32 agents.

## Pourquoi le redesign existe

Le premier lot pleinement aveugle a montré que le modèle pouvait comparer les attributs structurés, mais qu’il ne simulait pas encore une élection telle qu’un électeur la vit : marque partisane, candidat, territoire et environnement informationnel étaient volontairement retirés. Ce lot reste utile, mais uniquement comme contrôle.

Le projet adopte donc trois régimes primaires :

```text
BLIND_ATTRIBUTE_CONTROL
HISTORICAL_SEMIBLIND_RICH
REALISTIC_2026_NAMED
```

et un diagnostic interne :

```text
NAMED_2026_PSEUDONYMIZED_TWIN
```

## 1. Contrôle aveugle

Le rapport existant correspond à un seul work item :

```text
1 lot × 32 agents
territoire T_0267CFF87A2606F5
batch B01
```

Il est enregistré sous `BLIND_ATTRIBUTE_CONTROL`. Il ne doit plus être présenté comme la simulation principale de l’élection.

## 2. Backtest historique semi-aveugle riche

Les vrais noms, années, territoires et outcomes restent cachés. Les faits politiques existants ne sont pas recopiés : le builder produit uniquement un contrat de lecture avec des JSON pointers vers les cartes déjà contenues dans le packet gelé.

Pour chaque parti anonyme, Sol est explicitement invité à lire :

- les 16 features candidat/locales déjà présentes ;
- les 18 axes programmatiques déjà présents ;
- le statut gouvernement/opposition ;
- l’ancrage antérieur déjà présent ;
- les valeurs `MISSING`, conflits et statuts de vérification comme tels.

Le prompt change donc la **lecture**, pas les faits. Toute variation d’une valeur impose un Bridge V2 avant le moindre output concerné.

## 3. Simulation 2026 nommée et réaliste

Ce mode doit montrer les vrais partis, symboles, dirigeants, circonscriptions et candidats vérifiés. Chaque circonscription porte son propre `ballot_party_ids` : aucun panel national artificiel n’est copié partout. Chaque électeur reçoit ensuite sa propre `known_electoral_surface` filtrée par un information diet déterministe.

Le diet utilise uniquement :

- `prior_vote_or_abstention` ;
- `latent_attitude_political_discussion_mean`.

Il n’utilise ni âge, ni sexe, ni religion, ni ethnie, ni langue, ni revenu pour décider ce que l’électeur sait.

### État actuel

Le mode nommé est correctement bloqué : le certificat `b2_2026_ballot_certificate.json` est `FAIL`, la couverture territoriale vérifiée est 0 %, et aucune ligne candidat n’a passé la double entrée. Le futur input exige deux clusters indépendants par candidat, les 18 axes canoniques, des dates antérieures au snapshot et une couverture exacte des bulletins locaux. Le code ne fabrique rien et ne lance aucun appel Sol.

## 4. Twin pseudonymisé 2026

Lorsque le named input sera complet, le builder pourra créer un twin possédant exactement les mêmes faits, électeurs et conditions, mais des labels pseudonymisés. La comparaison nommée ↔ twin mesure la sensibilité aux identités dans le même monde 2026.

Ce twin n’est pas un quatrième régime primaire. Les IDs de sources, URLs et hashes sont également retirés de la surface visible par le modèle : ils certifient le builder mais ne doivent jamais devenir des signaux de vote.

## Ordre opérationnel

### A. Certifier le bridge V1 existant

```bash
python3 morocco26/scripts/agent_society_v2_main_bridge_v6.py \
  --repo-root . \
  --main-sha 4df897c356d3f0c36832405c7fcfc7f8f0cd6de2 \
  --environment "$FULL_ENV_ZIP" \
  --output "$RUN_ROOT/main_bridge_v1.json"
```

### B. Construire le goal et les contrats historiques

```bash
python3 morocco26/scripts/agent_society_v2_three_regime_goal.py build-goal \
  --repo-root . \
  --main-sha 4df897c356d3f0c36832405c7fcfc7f8f0cd6de2 \
  --environment "$FULL_ENV_ZIP" \
  --main-bridge "$RUN_ROOT/main_bridge_v1.json" \
  --control-report "$CONTROL_REPORT" \
  --output "$RUN_ROOT/three_regime_goal"
```

Le statut attendu actuellement est :

```text
PASS_THREE_REGIME_GOAL_READY_NAMED_SOURCE_BLOCKED
```

### C. Gate P1 — mêmes 32 agents, lecture historique riche

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_three_regime_startup.py \
  historical-pilot-32 \
  --goal-root "$RUN_ROOT/three_regime_goal" \
  --environment "$FULL_ENV_ZIP" \
  --main-bridge "$RUN_ROOT/main_bridge_v1.json" \
  --control-report "$CONTROL_REPORT" \
  --control-raw-run "$P0_RAW_D0" \
  --output "$RUN_ROOT/P1_historical_semiblind" \
  --workers 1
```

Le raw run P0 est obligatoire dès le lancement : le runner en extrait l’élection, la condition, le territoire, le batch et les 32 archétypes, puis sélectionne ce work item exact. Le rapport seul ne suffit pas à identifier l’élection et la condition.

### D. Gate P2 — 1 024 décisions

P2 exige un fichier de revue explicite :

```json
{
  "status": "PASS_P1_REVIEW_APPROVED_FOR_1024",
  "blind_vs_rich_reviewed": true
}
```

Puis :

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_three_regime_startup.py \
  historical-expand-1024 \
  --goal-root "$RUN_ROOT/three_regime_goal" \
  --environment "$FULL_ENV_ZIP" \
  --main-bridge "$RUN_ROOT/main_bridge_v1.json" \
  --p1-review "$RUN_ROOT/P1_review.json" \
  --output "$RUN_ROOT/P2_historical_semiblind_1024" \
  --workers 1
```

### E. Gate P3 — named 2026

P3 reste bloqué tant que `NAMED_2026_READINESS_STATUS.json` ne passe pas. Lorsqu’un input complet existe :

```bash
python3 morocco26/scripts/agent_society_v2_three_regime_goal.py validate-named-input \
  --input "$NAMED_INPUT"

python3 morocco26/scripts/agent_society_v2_three_regime_goal.py build-named-environment \
  --input "$NAMED_INPUT" \
  --output "$RUN_ROOT/named_2026_environment" \
  --protocol-root morocco26/frontends/agent_society_opus/source_v2/simulation_goal

python3 morocco26/scripts/agent_society_v2_three_regime_goal.py build-named-environment \
  --input "$NAMED_INPUT" \
  --output "$RUN_ROOT/named_2026_twin_environment" \
  --protocol-root morocco26/frontends/agent_society_opus/source_v2/simulation_goal \
  --pseudonymized-twin
```

Le premier lancement 2026 est obligatoirement apparié :

```bash
python3 morocco26/frontends/agent_society_opus/source_v2/chatgpt_baseline/run_three_regime_startup.py \
  named-paired-pilot \
  --goal-root "$RUN_ROOT/three_regime_goal" \
  --named-environment "$RUN_ROOT/named_2026_environment" \
  --twin-environment "$RUN_ROOT/named_2026_twin_environment" \
  --named-output "$RUN_ROOT/P3_named" \
  --twin-output "$RUN_ROOT/P3_twin" \
  --limit 1 \
  --workers 1
```

Le passage à l’échelle est interdit tant que la comparaison nommée ↔ twin n’a pas été revue explicitement.

## Ce qui est interdit

- relancer massivement le contrôle aveugle ;
- appeler P0 une simulation réaliste ;
- révéler les identités historiques ;
- ouvrir les outcomes 2016/2021 ;
- recopier les mêmes features historiques dans le prompt ;
- fabriquer les candidats 2026 manquants ;
- lancer une simulation nationale nommée partielle ;
- comparer causalement une élection historique à 2026 ;
- passer automatiquement de 32 à 1 024 ou 94 208 décisions.
