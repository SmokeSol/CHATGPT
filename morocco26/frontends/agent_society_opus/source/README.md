# ATLAS // Société artificielle

Front-end public de l'expérience de société électorale artificielle `EXP_7C8A2F11` /
`ENV_4D19B3E7`. Page unique, statique, en français, sans jargon technique.

**Ce que la page montre.** Comment 94 208 décisions de vote simulées se forment : les onze
forces qui les pilotent, les profils qui changent de camp, ceux qui sanctionnent le bilan
sortant, ceux qui répondent au programme ou à la figure locale, et un démonstrateur qui
recalcule une décision en direct pendant qu'on déplace les curseurs.

**Ce que la page ne montre pas.** Aucun résultat électoral, aucune part de voix, aucun siège,
aucun classement de partis, aucun nom réel de parti ou de territoire, aucune date de scrutin.
Les agrégats sont bruts, non pondérés — le corpus ne fournit d'ailleurs aucun poids de
population.

## Arborescence

```
vercel.json              en-têtes de sécurité + réécritures
web/
  index.html             structure, aucun script ni style en ligne
  styles.css             charte, rampes ordinales, thème sombre unique
  app.js                 rendu, interactions, portage du moteur de décision
  data/
    societe.json         agrégats descriptifs sur les 94 208 décisions   (~123 Ko)
    portraits.json       3 000 décisions individuelles échantillonnées   (~1,4 Mo)
    simulateur.json      contexte d'un territoire + vecteurs de base + points de contrôle
```

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

`vercel.json` applique une CSP stricte sans aucune échappatoire :

```
default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none';
script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self';
connect-src 'self'; media-src 'none'; object-src 'none'; worker-src 'none';
manifest-src 'self'; upgrade-insecure-requests
```

Ni `unsafe-inline`, ni `unsafe-eval`, ni CDN, ni police distante, ni image distante, ni
télémétrie. Le code respecte ces contraintes de bout en bout : aucun attribut `style` n'est
écrit dans le balisage ni via `setAttribute`, toute mise en forme dynamique passe par le CSSOM.
S'y ajoutent `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy: no-referrer`,
`Permissions-Policy` fermée, les trois en-têtes `Cross-Origin-*`, HSTS et `X-Robots-Tag: noindex`.

## Le démonstrateur

`app.js` réimplémente le moteur de décision utilisé pour produire le corpus. La fidélité de ce
portage n'est pas supposée : `data/simulateur.json` embarque douze points de contrôle calculés
par le moteur Python de référence, et la page les rejoue au chargement. L'écart maximal
constaté est de 5,2 × 10⁻⁷, soit l'arrondi des valeurs de référence. Le résultat est écrit
dans la console du navigateur à chaque chargement.

Le territoire utilisé par le démonstrateur est un territoire réel du corpus, retenu pour sa
configuration ordinaire — participation précédente proche de la médiane, candidatures locales
documentées. Il reste anonyme, comme tous les autres.

## Accessibilité et robustesse

- Un seul thème, sombre, entièrement peint : aucune surface ne dépend du thème de l'hôte.
- La couleur ne porte jamais seule le sens : chaque barre, chaque tuile et chaque état porte
  un libellé et un chiffre.
- Rampes ordinales à teinte unique, luminance monotone.
- Tuiles de l'atlas atteignables au clavier, infobulle en `aria-live`.
- `prefers-reduced-motion` coupe l'animation du champ d'agents et les transitions de barres.
- Tableaux larges confinés dans un conteneur défilant : le corps de page ne défile jamais
  horizontalement.

## Régénérer les données

Les trois fichiers de `web/data/` sont dérivés de l'arborescence gelée des décisions par les
scripts livrés avec l'archive de sortie (`engine/derive.py` et `engine/make_sim.py`). Ils ne
contiennent aucun résultat électoral, aucune pondération et aucune agrégation vers un résultat.

## Suite

Cette version simule des agents strictement isolés : aucun ne voit la réponse d'un autre.
La version 2 introduit la famille, les collègues, le voisinage et l'influence entre agents.
