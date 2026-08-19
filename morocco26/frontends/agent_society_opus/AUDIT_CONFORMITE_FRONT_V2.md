# Audit de conformité — front v2 (société artificielle + vote LLM)

Objet : vérifier que la version livrée dans `source_v2/` tient encore la ligne posée par le
front d'origine (`source/`) — portée institutionnelle, lecteur averti, surface d'attaque nulle,
aucune donnée renvoyée vers un tiers — maintenant qu'un vote par assistant IA s'y ajoute.

Périmètre : audit statique de `source_v2/vercel.json`, `source_v2/web/**`,
`source_v2/integration/**`. Référence : `source/` et son README.

---

## 1. Ce qui tient

**Les en-têtes.** `vercel.json` conserve la totalité de la politique d'origine : CSP sans
`unsafe-inline` ni `unsafe-eval`, `default-src 'none'`, `base-uri 'none'`, `form-action 'none'`,
`frame-ancestors 'none'`, plus `X-Content-Type-Options`, `X-Frame-Options: DENY`,
`Referrer-Policy: no-referrer`, `Permissions-Policy` en liste fermée, les trois en-têtes
`Cross-Origin-*`, HSTS avec `preload`, et `X-Robots-Tag: noindex, nofollow` — maintenu alors même
que la page devient participative. C'est le bon arbitrage à quelques mois d'un scrutin réel.

**L'élargissement de la CSP est minimal et nommé.** `connect-src` passe de `'self'` à
`'self' https://slgkvmjikvenhkioqglt.supabase.co`. Une origine, explicite, sans joker, sans
`unsafe-*`. C'est le strict nécessaire au vote LLM : conforme.

**Aucune dépendance distante.** Pas de CDN, pas de police distante, pas d'image distante, pas de
télémétrie. Les seules origines externes du code sont le service de participation, le connecteur
MCP (`integration/`), et deux liens sortants vers `chatgpt.com` / `claude.ai` ouverts en
`window.open(..., 'noopener')`.

**Le balisage reste propre.** `web/index.html` : aucun `<script>` en ligne, aucun bloc `<style>`,
aucun attribut `style=`, aucun gestionnaire `on*=`. Deux scripts externes, `app.js` et `reader.js`.
Aucun `eval`, aucun `new Function` dans l'ensemble du front.

**`web/privacy.html`** est un ajout juste : il énonce que le mot de passe de l'assistant ne
transite jamais par ATLAS. À étoffer, mais la page existe.

---

## 2. Ce qui ne tient plus

### A — Le README décrit une page qui n'existe plus  *(à corriger en premier)*

`source_v2/README.md` est identique octet pour octet à celui de `source/`. Il affirme :

> Aucun résultat électoral, aucune part de voix, aucun siège, aucun classement de partis,
> aucun nom réel de parti ou de territoire, aucune date de scrutin.

La page livrée fait exactement l'inverse, et c'est assumé :

- `web/reader.js:4` nomme PAM, RNI, PPS, Mouvement populaire, PJD, Union constitutionnelle,
  USFP, Istiqlal ;
- `web/index.html` (section `#maroc`) fait naviguer dans les circonscriptions réelles, groupées
  par région ;
- `web/reader.js:50` affiche les parts de voix réellement obtenues, `web/reader.js:53` le parti
  arrivé en tête au scrutin réel ;
- `web/reader.js:252` (`publiciseRenderedLabels`) réécrit jusqu'aux « liste N » du démonstrateur
  en noms de partis.

Le README annonce aussi une CSP `connect-src 'self'` qui n'est plus celle du fichier.

Ce n'est pas un défaut de code : la levée de l'anonymat est une décision produit, inscrite dans
`FRONT_READER_FINAL_HANDOFF.md`. Le défaut, c'est que la documentation n'a pas suivi — et qu'un
document qui promet l'anonymat au-dessus d'une page qui nomme les partis est le pire des deux
mondes. **Le README doit être réécrit pour dire ce que la page montre réellement, et pourquoi.**

Conséquence de fond, à trancher explicitement plutôt qu'à subir : la page passe de « aucun
résultat électoral » à « résultat historique réel affiché à côté d'une simulation », à l'approche
d'un scrutin. La ligne éditoriale qui justifie cet affichage existe aujourd'hui en une phrase
(« 2016 et 2021 servent à tester la société artificielle avant 2026 »). Elle mérite d'être tenue
au même niveau que les en-têtes de sécurité.

### B — `Permissions-Policy` ne couvre pas le presse-papiers, que le parcours utilise

`web/reader.js:170` écrit dans le presse-papiers, `web/reader.js:206` le lit. La liste fermée de
`vercel.json` n'énumère ni `clipboard-read` ni `clipboard-write` : ces deux fonctionnalités
retombent sur leur valeur par défaut au lieu d'être déclarées, alors que tout le reste de la
politique est explicite. Correctif d'une ligne :

```
clipboard-read=(self), clipboard-write=(self)
```

### C — `innerHTML` réintroduit

`web/reader.js:238` : `n.innerHTML = html[sel]`, sur cinq titres de section. Les chaînes sont
littérales, il n'y a pas d'injection possible en l'état. Mais `app.js` construit chaque nœud par
`createElement` + `textContent`, sans exception, précisément pour que la règle n'ait jamais à être
jugée au cas par cas. Cinq titres à reconstruire en nœuds : le coût est nul, la règle redevient
absolue.

### D — Des chiffres du bandeau ne sont plus traçables

`web/app.js:193-196` remplace des valeurs dérivées du corpus par des littéraux : `'0 contribution'`,
`'0'`, et un pied de page qui perd les empreintes du prompt et du schéma. Le principe « chaque
chiffre affiché se remonte jusqu'au corpus » tombe à cet endroit.

S'y ajoute une écriture concurrente : `#hero-fid` est renseigné par `app.js:193`
(`'0 contribution'`) puis écrasé par `reader.js:96` (`Math.round(pc)+' %'`). Deux sources pour le
même nœud, l'ordre décide — à unifier sur `reader.js`, seule source légitime de cette valeur
désormais.

### E — Le jargon revient, à un seul endroit

`web/reader.js:153-166` (`contributionPrompt`) colle au lecteur `JSON.stringify(context)`,
`JSON.stringify(voters)`, `JSON.stringify(schema)` et le libellé `judge_prompt`. C'est le seul
point du parcours qui expose la plomberie — et il enfreint à la fois la règle de lecture sans
jargon et la consigne explicite du handoff. Le contenu doit rester ce qu'il est (l'assistant en a
besoin mot pour mot) ; c'est sa présentation qui doit changer : un bloc replié, présenté comme
« ce que votre IA va recevoir », jamais du texte brut jeté dans une fenêtre de lecture.

### F — Un point que l'audit statique ne peut pas trancher

`Cross-Origin-Embedder-Policy: require-corp` est conservé. Les appels au service de participation
sont en mode CORS, donc admissibles — **à condition** que la fonction Edge renvoie les en-têtes
CORS attendus. À vérifier en ligne, console ouverte, avant l'ouverture des participations : c'est
le seul risque de rupture entre la politique de sécurité et le vote LLM.

---

## 3. Hors périmètre front, mais à signaler

`web/reader.js:213` valide une contribution à partir d'un texte collé à la main dans une zone de
saisie. Rien ne distingue la sortie d'un modèle d'un texte réécrit par le participant.

`morocco26/STATUS.md` place `E_collect` en **pré-enregistré**, `E_reason` et `E_full`
**verrouillés**, et impose que rien de non résolu ne soit converti en absence. Une collecte
publique par copier-coller n'apporte aucune provenance vérifiable et ne peut pas, telle quelle,
alimenter un protocole pré-enregistré. Le connecteur MCP (`integration/claude_connector.txt`) est
la seule des deux voies qui établit une chaîne de garde de bout en bout.

Décision à prendre avant l'ouverture, et à inscrire dans le protocole : ce que vaut une
contribution collée dans le registre des preuves — participation publique sans valeur probante,
ou exclusion pure et simple de l'ensemble admissible.

---

## 4. Ordre de traitement suggéré

1. Réécrire le README (A) — c'est le seul écart qui trompe activement un lecteur.
2. Ajouter les deux directives presse-papiers (B) — une ligne.
3. Vérifier CORS/COEP en ligne (F) — avant toute ouverture.
4. Unifier `#hero-fid` et restaurer les chiffres traçables (D).
5. Replier le bloc technique de la participation (E).
6. Supprimer les cinq `innerHTML` (C).
7. Trancher le statut probatoire des contributions collées (§3).

Aucun de ces points n'exige de revenir sur la direction artistique, la CSP, ni le vote LLM.

---

## 5. Provenance de `source_v2/`

Extraction fidèle de `atlas-societe-artificielle-maroc-final (1).zip`
(50 552 747 octets, `sha256 = e30c810b8ac28dd01ea29135be6dfa9258f7595b371dcd994fff6c28c9598cc1`),
1 863 fichiers versionnés. Seule exclusion : `scripts/__pycache__/`, artefact d'exécution Python.
Empreinte de chaque fichier dans `MANIFEST_source_v2.sha256`. Aucun octet du front n'a été modifié
par cet audit — les correctifs listés en §2 restent à appliquer.
