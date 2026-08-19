# G0 — baseline GPT via le compte ChatGPT du propriétaire

Ce dossier transforme les **2 944 work items gelés** d’Agent Society en **94 208 décisions réellement produites par GPT**, sans clé API OpenAI.

Le mécanisme officiel utilisé est **Codex CLI connecté avec “Sign in with ChatGPT”**. Un orchestrateur local lance un `codex exec --ephemeral` séparé pour chaque lot de 32 archétypes. Le compte ChatGPT finance/limite donc l’usage via son pool Codex ; le navigateur `chatgpt.com` n’est jamais automatisé et aucun cookie de session n’est extrait.

## Statut scientifique

- `E0_DETERMINISTIC` reste l’étalon mécanique immuable.
- `G0_CHATGPT_GPT56_TERRA` est le candidat appelé à devenir la simulation de référence affichée au public une fois les 2 944 lots validés.
- `R0_PUBLIC_BYO_LLM` reste une cohorte indépendante produite par les lecteurs.

Ne jamais renommer E0 en sortie LLM. Ne jamais supprimer E0 : la comparaison `G0 − E0` est précisément ce qui mesure ce que GPT ajoute au moteur explicite.

Le protocole gelé est `CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V1.json`.

## Pourquoi cette voie

Le CLI Codex accepte l’authentification normale du compte ChatGPT et possède un mode non interactif. Le runner exploite ce mode sans API key :

```text
un login ChatGPT local
        ↓
2 944 processus Codex éphémères
        ↓
32 décisions indépendantes par processus
        ↓
validation stricte + hash + checkpoint
        ↓
94 208 lignes G0
```

Il n’utilise pas une conversation unique et ne reprend jamais un thread précédent. Chaque work item est donc un contexte modèle neuf.

## Prérequis

Mac, Linux ou Windows avec WSL recommandé, Python 3.10+ et le CLI Codex officiel.

Installation :

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
# ou
npm install -g @openai/codex
```

Connexion — une seule fois sur la machine locale contrôlée par le propriétaire :

```bash
codex
```

Choisir **Sign in with ChatGPT**, terminer l’authentification dans le navigateur, puis quitter le TUI. Ne jamais copier ni committer `~/.codex/auth.json` : ce fichier équivaut à un mot de passe.

Le runner supprime `OPENAI_API_KEY` et `CODEX_API_KEY` de l’environnement de chaque subprocess et impose `forced_login_method="chatgpt"`.

## ZIP à utiliser

Utiliser le bundle full-environment qui contient **2 944 work items et 94 208 lignes attendues**. Le runner refuse par défaut l’ancien handoff de 1 472 lots / 47 104 lignes.

Le bundle peut être fourni sous forme ZIP ou déjà extrait. Il doit contenir l’un des formats gelés suivants :

1. `work_manifest.json` + `contexts/` + `voter_batches/`, ou
2. `packets/**/*.json`.

Le prompt et le schéma sont détectés dans le bundle ; ils ne sont pas recopiés depuis le repo courant.

## Préflight sans consommer GPT

```bash
python run_chatgpt_baseline.py \
  --bundle "/chemin/vers/EXP_7C8A2F11_FULL_ENV.zip" \
  --output "/chemin/vers/G0_CHATGPT_GPT56_TERRA" \
  --dry-run
```

Le préflight doit annoncer :

```text
2944 work items / 94208 rows
```

## Sonde réelle avant le run complet

Cette sonde consomme huit contextes ChatGPT mais ne regarde aucun outcome :

```bash
python run_chatgpt_baseline.py \
  --bundle "/chemin/vers/EXP_7C8A2F11_FULL_ENV.zip" \
  --output "/chemin/vers/G0_CHATGPT_GPT56_TERRA" \
  --model gpt-5.6-terra \
  --reasoning medium \
  --workers 1 \
  --limit 8
```

Elle vérifie le login, la disponibilité du modèle, la sortie structurée et le contrat « zéro outil ».

## Run complet

```bash
python run_chatgpt_baseline.py \
  --bundle "/chemin/vers/EXP_7C8A2F11_FULL_ENV.zip" \
  --output "/chemin/vers/G0_CHATGPT_GPT56_TERRA" \
  --model gpt-5.6-terra \
  --reasoning medium \
  --workers 1
```

Commencer avec `--workers 1`. Monter à `2` uniquement après une sonde propre. Une concurrence supérieure augmente la probabilité de heurter les limites du plan sans améliorer l’indépendance scientifique.

Le run est **reprenable**. Relancer exactement la même commande :

- les work items déjà valides sont relus et sautés ;
- aucun thread Codex n’est repris ;
- un lot invalide ne contamine pas les autres ;
- en cas de limite ChatGPT/Codex, le processus sort avec le code `75`.

## Invariants techniques imposés à chaque appel

Le runner lance notamment :

```text
codex exec
  --ephemeral
  --ignore-user-config
  --ignore-rules
  --sandbox read-only
  --json
  --model gpt-5.6-terra
  --output-schema <schéma spécifique au lot>
  -c forced_login_method="chatgpt"
  -c web_search="disabled"
  -c approval_policy="never"
  -c features.apps=false
  -c features.multi_agent=false
  -c features.shell_tool=false
  -c features.memories=false
  -c features.hooks=false
  -c features.goals=false
```

Le modèle travaille dans un dossier vide et ne reçoit que :

1. le prompt gelé ;
2. le schéma gelé ;
3. le work item gelé.

Le JSON Schema transmis à Codex est spécialisé pour les neuf pseudonymes locaux du lot. Le wrapper `{"rows":[...]}` est uniquement un format de transport pour Structured Outputs ; le corpus final est réécrit en JSONL conforme au schéma scientifique ligne par ligne.

## Validation et retry

Pour chaque lot :

- exactement 32 lignes ;
- ordre exact des archétypes ;
- identité élection/territoire/condition/batch exacte ;
- clés de partis exactes ;
- probabilités dans `[0,1]` et somme à `1 ± 1e-9` ;
- facteurs et reason codes conformes au schéma ;
- aucun événement shell, fichier, MCP, web, computer-use ou autre outil.

Un deuxième appel est autorisé **uniquement** si la sortie finale est schema-invalid. Le second appel reçoit le prompt strictement identique, sans message d’erreur ni feedback sémantique. Une panne transport ou une violation du contrat arrête le lot au lieu de déclencher un retry opportuniste.

## Artifacts

Le dossier de sortie contient :

```text
preflight.json
run_state.json
output_manifest.json
outputs/.../*.jsonl
outputs/.../*.jsonl.meta.json
_runs/<task>/attempt_*/events.jsonl
_runs/<task>/attempt_*/stderr.txt
```

`events.jsonl` conserve l’usage de tokens déclaré par Codex. Les fichiers d’authentification ChatGPT ne sont jamais copiés dans ce dossier.

Le terminal attendu à la complétion est :

```text
PASS_CHATGPT_ACCOUNT_BASELINE_FROZEN_READY_FOR_SCORING
```

Seulement après ce terminal et l’audit du manifest, le frontend peut basculer de E0 vers G0. Cela ne prouve pas encore que G0 prédit correctement : l’évaluation historique aveugle reste une étape séparée.
