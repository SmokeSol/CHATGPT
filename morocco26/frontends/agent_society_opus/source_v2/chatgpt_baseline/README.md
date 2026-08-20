# G0 — société GPT via le compte ChatGPT du propriétaire

Ce dossier permet de transformer les **2 944 work items gelés** d’Agent Society en **94 208 décisions réellement produites par GPT‑5.6 Sol**, sans clé API OpenAI.

L’authentification passe par le CLI Codex officiel et **Sign in with ChatGPT**. Chaque lot de 32 citoyens est traité dans un processus `codex exec --ephemeral` distinct. Aucun cookie navigateur n’est extrait et `~/.codex/auth.json` ne doit jamais être partagé ou committé.

## Architecture scientifique

```text
E0_DETERMINISTIC
  contrôle mécanique immuable

G0 / D0_DECISION
  Sol décide dans 2 944 contextes frais
  → participation
  → probabilités de vote
  → facteurs
  → reason codes

L0_OBSERVABLE_DELIBERATION
  un second contexte Sol explique la décision D0 déjà gelée
  → conflit central
  → pressions favorables/défavorables
  → pourquoi le premier choix
  → pourquoi pas l’alternative
  → hésitation
  → hypothèse de bascule

CF_BEHAVIOURAL_ABLATIONS
  de nouveaux contextes Sol rejouent réellement le citoyen
  après modification déterministe d’un élément du packet
  → ancrage électoral passé
  → bilan gouvernemental
  → offre locale de l’alternative
  → programme du premier choix et de l’alternative
  → placebo non politique
```

L0 n’est pas la chaîne de pensée privée du modèle. C’est une **explication externe structurée**, produite après le gel de D0 et obligatoirement reliée à un catalogue fermé de preuves. Les récits restent des hypothèses ; seuls les rejouements CF permettent d’observer si le comportement bouge réellement.

Le protocole principal est `CHATGPT_ACCOUNT_BASELINE_PROTOCOL_V1.json`. Le protocole explicatif et causal est `DELIBERATION_OBSERVATORY_PROTOCOL_V1.json`.

## Prérequis

Mac, Linux ou Windows avec WSL recommandé, Python 3.10+ et le CLI Codex officiel.

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
codex --version
codex
```

Dans Codex, choisir **Sign in with ChatGPT**, terminer la connexion dans le navigateur, puis quitter le TUI. Vérification :

```bash
codex login status
```

Le runner supprime `OPENAI_API_KEY` et `CODEX_API_KEY` de l’environnement de chaque subprocess et impose l’authentification ChatGPT.

## Bundle requis

Utiliser le package full environment contenant exactement :

```text
2 944 work items
94 208 décisions attendues
32 citoyens par lot
```

Le runner refuse par défaut l’ancien handoff de 1 472 lots / 47 104 lignes.

Exemple :

```bash
BUNDLE="$HOME/Downloads/opus5-agent-society-v2-FULL-ELECTION-ENVIRONMENT-FINAL(1).zip"
D0_OUT="$HOME/agent-society-runs/G0_CHATGPT_GPT56_SOL"
OBS_OUT="$HOME/agent-society-runs/G0_CHATGPT_GPT56_SOL_OBSERVATORY"
mkdir -p "$D0_OUT" "$OBS_OUT"
```

## 1. Préflight gratuit

```bash
python3 run_g0_sol.py \
  --bundle "$BUNDLE" \
  --output "$D0_OUT" \
  --dry-run
```

Le préflight doit annoncer exactement :

```text
2944 work items / 94208 rows
```

## 2. Premier run D0 — 32 contextes, 1 024 décisions

```bash
python3 run_g0_sol.py \
  --bundle "$BUNDLE" \
  --output "$D0_OUT" \
  --workers 1 \
  --limit 32
```

`run_g0_sol.py` interdit de changer le modèle ou l’effort de raisonnement : le contrat est gelé sur :

```text
model = gpt-5.6-sol
reasoning = medium
```

Résultat attendu après ce premier run :

```text
work_items_validated = 32
rows_validated = 1024
status = IN_PROGRESS_RESUMABLE
```

Le terminal complet `PASS_CHATGPT_ACCOUNT_BASELINE_FROZEN_READY_FOR_SCORING` n’apparaîtra qu’à 2 944 / 2 944.

## 3. Délibération profonde L0 — les 1 024 citoyens

Une fois D0 validé, lancer **32 nouveaux contextes Sol distincts**. Chaque contexte explique les 32 décisions de son lot sans modifier leurs chiffres :

```bash
python3 run_deliberation_observatory.py \
  --bundle "$BUNDLE" \
  --decision-run "$D0_OUT" \
  --output "$OBS_OUT" \
  --scope all \
  --limit 32 \
  --counterfactual-suite none \
  --workers 1
```

Ce passage produit pour chacun des 1 024 citoyens :

- premier choix et alternative ;
- marge de décision et posture de participation ;
- fidélité, bascule, mobilisation ou abstention persistante ;
- conflit électoral central ;
- deux à cinq drivers directionnels ;
- références exactes aux éléments du packet utilisés ;
- pourquoi le premier choix reste devant ;
- pourquoi l’alternative reste derrière ;
- logique de participation ou d’abstention ;
- incertitude réelle ;
- hypothèse minimale de bascule ;
- hypothèse minimale de mobilisation/démobilisation ;
- synthèse en français.

La validation échoue si le modèle :

- modifie une probabilité D0 ;
- change l’ordre ou l’identité d’un citoyen ;
- cite une preuve absente ;
- cite un champ non directionnel comme preuve ;
- invente un parti ou une caractéristique ;
- prétend avoir exposé une chaîne de pensée cachée.

Terminal attendu :

```text
PASS_STARTUP_32_DELIBERATION_OBSERVATORY_COMPLETE
```

## 4. Batterie causale optionnelle CF

Après inspection du rapport L0, tester le **citoyen SWING de chaque lot** avec cinq scénarios. Cela représente au maximum :

```text
32 lots × 1 citoyen × 5 scénarios = 160 contextes supplémentaires
```

Commande :

```bash
python3 run_deliberation_observatory.py \
  --bundle "$BUNDLE" \
  --decision-run "$D0_OUT" \
  --output "$OBS_OUT" \
  --scope all \
  --limit 32 \
  --counterfactual-suite core \
  --counterfactual-panels SWING \
  --workers 1
```

Le runner saute les explications L0 déjà validées et n’exécute que les diagnostics manquants.

Statuts causaux possibles :

```text
SUPPORTED
PARTIAL
NOT_SUPPORTED
REFUTED_DIRECTION
UNSAFE_PLACEBO_SENSITIVE
```

Une explication fluide n’est jamais promue comme causalité lorsque le placebo est instable.

## 5. Artefacts locaux

```text
D0_OUT/
  preflight.json
  run_state.json
  output_manifest.json
  outputs/**/*.jsonl
  outputs/**/*.jsonl.meta.json
  _runs/**/events.jsonl

OBS_OUT/
  observatory_preflight.json
  observatory_state.json
  observatory_report.json
  deliberations/**/*.jsonl
  deliberations/**/*.jsonl.meta.json
  counterfactuals/**/*.jsonl
  _observatory_runs/**
```

Le run est reprenable. En cas de quota ChatGPT/Codex : relancer la **même commande**. Les work items déjà valides sont vérifiés puis sautés ; aucun thread n’est repris.

## 6. Promotion vers GitHub Pages

### Référence G0 complète

Après les 94 208 décisions D0, construire une prévisualisation :

```bash
python3 promote_g0_sol_frontend.py \
  --env "/chemin/vers/ENV_4D19B3E7_extrait" \
  --run "$D0_OUT" \
  --e0-run "/chemin/vers/E0_DETERMINISTIC_REFERENCE_extrait"
```

Puis seulement après lecture de `promotion_preview/promotion_audit.json` :

```bash
python3 promote_g0_sol_frontend.py \
  --env "/chemin/vers/ENV_4D19B3E7_extrait" \
  --run "$D0_OUT" \
  --e0-run "/chemin/vers/E0_DETERMINISTIC_REFERENCE_extrait" \
  --apply
```

E0 est archivé et reste disponible comme contrôle ; il n’est jamais supprimé ou renommé G0.

### Observatoire des délibérations

Prévisualisation :

```bash
python3 promote_deliberation_frontend.py \
  --observatory-report "$OBS_OUT/observatory_report.json" \
  --web-root "../web"
```

Application :

```bash
python3 promote_deliberation_frontend.py \
  --observatory-report "$OBS_OUT/observatory_report.json" \
  --web-root "../web" \
  --apply
```

Avant toute donnée réelle, le frontend affiche uniquement la méthode et l’état d’attente. Il n’invente aucune explication. Après promotion, il permet d’ouvrir un citoyen, lire sa décision, ses tensions et ses preuves, puis distinguer clairement les récits L0 des effets CF observés.

## Règles de sécurité et d’intégrité

- ne jamais envoyer ou committer `~/.codex/auth.json` ;
- ne jamais automatiser `chatgpt.com` avec les cookies du navigateur ;
- ne jamais ouvrir 2016 ou 2021 pendant D0, L0 ou CF ;
- ne jamais alimenter D0 avec une explication L0 ;
- ne jamais sélectionner les citoyens selon les résultats historiques ;
- ne jamais interpréter un récit comme un effet causal sans rejouement ;
- conserver E0 comme contrôle falsifiable ;
- conserver les λ famille/collègues/voisinage comme illustratifs jusqu’au protocole séparé 2016 → freeze → 2021.
