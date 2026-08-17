(()=>{
  const methodology=document.querySelector('#view-methodology');
  if(methodology){methodology.innerHTML=`
    <div class="view-head method-public-head">
      <div><span class="section-kicker">Méthodologie</span><h2>Une projection territoriale, probabiliste et traçable</h2><p>Atlas 395 estime la répartition plausible des 395 sièges à partir d'un cadre commun à toutes les forces politiques. La méthode privilégie la cohérence territoriale, la qualité des sources, l'explicitation de l'incertitude et la conservation des versions publiées.</p></div>
    </div>

    <div class="method-hero">
      <article class="method-thesis">
        <span class="section-kicker">Cadre de référence</span>
        <h3>Produire une estimation vérifiable, sans ajustement partisan ni lecture opportuniste.</h3>
        <p>La projection est établie avant le scrutin à partir de données historiques harmonisées, des règles électorales applicables et d'une modélisation probabiliste. Les informations nouvelles de 2026 peuvent enrichir la projection uniquement lorsqu'elles sont suffisamment établies et qu'une méthode d'intégration défendable existe.</p>
        <div class="method-northstar"><span>Principe directeur</span><b>À chaque date, Atlas doit pouvoir expliquer l'origine d'un chiffre, ce qui peut le faire évoluer et ce qui demeure incertain.</b></div>
      </article>
      <aside class="method-state">
        <div class="method-state-head"><span class="eyebrow">Référence publiée</span><b>Version datée et conservée</b></div>
        <div class="method-state-grid">
          <div><span>Statut</span><b id="method-version">Enregistrée</b><small id="method-version-date">avant le scrutin</small></div>
          <div><span>Scénarios</span><b id="method-draws">50 000</b><small>élections complètes simulées</small></div>
          <div><span>Périmètre</span><b id="method-seats">395</b><small>sièges couverts à chaque scénario</small></div>
          <div><span>Ajustements discrétionnaires</span><b id="method-manual-bonus">0</b><small>même règle pour toutes les forces</small></div>
        </div>
      </aside>
    </div>

    <div class="panel method-intro">
      <div class="panel-head"><h3>La démarche en synthèse</h3><div class="grow"></div><span class="eyebrow">4 étapes</span></div>
      <div class="panel-body"><p>Atlas part du territoire, non d'une estimation nationale imposée d'en haut. Les résultats historiques et les règles du scrutin sont harmonisés circonscription par circonscription. Le modèle génère ensuite 50 000 élections cohérentes afin de mesurer une distribution de résultats possibles. Les informations nouvelles sont documentées séparément de leur éventuel effet électoral ; elles ne modifient la projection que lorsque les conditions de vérification et d'intégration prévues sont réunies.</p></div>
    </div>

    <div class="method-flow" aria-label="Les quatre étapes de la méthode Atlas 395">
      <article class="method-step"><div class="n">01</div><h3>Structurer le territoire</h3><p>Harmoniser les circonscriptions, les sièges, les règles d'attribution et les résultats historiques dans un référentiel commun.</p></article>
      <article class="method-step"><div class="n">02</div><h3>Simuler l'incertitude</h3><p>Produire 50 000 élections complètes afin d'obtenir des probabilités, des moyennes et des intervalles plutôt qu'un chiffre unique.</p></article>
      <article class="method-step"><div class="n">03</div><h3>Documenter les évolutions</h3><p>Qualifier les candidatures, alliances, retraits et autres faits nouveaux selon une hiérarchie de sources et des règles identiques.</p></article>
      <article class="method-step"><div class="n">04</div><h3>Publier et conserver</h3><p>Dater chaque projection, conserver les versions antérieures et permettre une évaluation objective après le scrutin.</p></article>
    </div>

    <div class="method-grid">
      <section class="panel">
        <div class="panel-head"><h3>Principes de méthode</h3></div>
        <div class="method-rules">
          <div class="method-rule"><div class="rule-icon">01</div><b>Territorial d'abord</b><p>La projection nationale résulte de la consolidation des distributions produites au niveau des circonscriptions.</p></div>
          <div class="method-rule"><div class="rule-icon">02</div><b>Incertitude explicite</b><p>Les fourchettes et probabilités sont publiées afin de distinguer estimation centrale et dispersion des scénarios.</p></div>
          <div class="method-rule"><div class="rule-icon">03</div><b>Règles définies en amont</b><p>Les critères de traitement d'une information sont fixés avant d'observer son éventuel effet sur la projection.</p></div>
          <div class="method-rule"><div class="rule-icon">04</div><b>Données manquantes identifiées</b><p>Une information non disponible ou non résolue demeure signalée comme telle ; elle n'est pas convertie en certitude.</p></div>
          <div class="method-rule"><div class="rule-icon">05</div><b>Versions conservées</b><p>Une nouvelle édition complète l'historique sans réécrire les projections précédemment publiées.</p></div>
          <div class="method-rule"><div class="rule-icon">06</div><b>Évaluation ex post</b><p>La qualité de la méthode sera mesurée sur les résultats observés après le scrutin.</p></div>
        </div>
      </section>

      <section class="panel">
        <div class="panel-head"><h3>Neutralité et gouvernance des données</h3></div>
        <div class="method-rules">
          <div class="method-rule"><div class="rule-icon">=</div><b>Mêmes critères pour tous</b><p>Les règles de source, de vérification et d'intégration sont identiques quelle que soit la force politique concernée.</p></div>
          <div class="method-rule"><div class="rule-icon">0</div><b>Aucun ajustement discrétionnaire</b><p>Une appréciation qualitative d'un parti, d'un candidat ou d'une dynamique médiatique ne produit pas, à elle seule, un effet chiffré.</p></div>
          <div class="method-rule"><div class="rule-icon">S</div><b>Provenance documentée</b><p>Chaque information est qualifiée selon sa source, sa date, son statut et son rattachement territorial.</p></div>
          <div class="method-rule"><div class="rule-icon">↔</div><b>Fait et impact séparés</b><p>Établir qu'un événement a eu lieu ne suffit pas à déterminer son effet en voix ou en sièges.</p></div>
          <div class="method-rule"><div class="rule-icon">V</div><b>Corroboration proportionnée</b><p>Le niveau de confirmation demandé dépend de la nature de l'information et de son importance potentielle.</p></div>
          <div class="method-rule"><div class="rule-icon">T</div><b>Traçabilité</b><p>Les évolutions de la projection doivent pouvoir être reliées à des données et à une règle d'intégration identifiables.</p></div>
        </div>
      </section>
    </div>

    <section class="method-current">
      <div class="method-current-head">
        <div><span class="section-kicker">Conditions d'évolution</span><h3>Une information nouvelle ne devient pas automatiquement un ajustement électoral.</h3><p class="lead">Atlas distingue trois niveaux : l'information repérée, le fait suffisamment établi et l'effet quantifiable. Une candidature, une alliance, un retrait ou une décision officielle peut être important sans qu'il existe immédiatement une base suffisamment robuste pour traduire ce fait en voix ou en sièges. Dans ce cas, l'information est conservée et documentée, mais la projection chiffrée demeure inchangée.</p></div>
        <div class="method-zero"><span>Ajustement discrétionnaire</span><b>0</b></div>
      </div>
      <div class="method-chain">
        <div class="method-chain-card"><span>Niveau 1</span><b>Information documentée</b><p>Source, date, contenu et territoire sont identifiés.</p></div>
        <div class="method-chain-arrow">→</div>
        <div class="method-chain-card"><span>Niveau 2</span><b>Fait confirmé</b><p>Le degré de confirmation requis est atteint selon la nature de l'événement.</p></div>
        <div class="method-chain-arrow">→</div>
        <div class="method-chain-card"><span>Niveau 3</span><b>Effet intégrable</b><p>La traduction dans la projection repose sur une règle explicite et défendable.</p></div>
      </div>
      <div class="method-promise"><strong>Règle de prudence :</strong> l'absence d'effet chiffré immédiat ne signifie pas qu'une information est sans importance ; elle signifie que son impact n'est pas encore établi avec un niveau de confiance suffisant.</div>
    </section>

    <div class="method-grid">
      <section class="panel">
        <div class="panel-head"><h3>Hiérarchie des sources</h3></div>
        <ul class="method-plain-list">
          <li><strong>Sources institutionnelles et officielles :</strong> règles du scrutin, décisions, textes et faits relevant d'une autorité publique.</li>
          <li><strong>Sources officielles des partis :</strong> investitures, listes, retraits et annonces attribuables directement à l'organisation concernée.</li>
          <li><strong>Médias24 :</strong> veille et corroboration ; une publication médiatique ne modifie jamais, à elle seule, la projection.</li>
          <li>Une déclaration émanant d'une partie intéressée est documentée comme telle et n'est pas assimilée à une confirmation indépendante.</li>
          <li>La langue de publication, française ou arabe, ne modifie ni le niveau d'exigence ni la hiérarchie des sources.</li>
        </ul>
      </section>
      <section class="panel">
        <div class="panel-head"><h3>Limites de lecture</h3></div>
        <ul class="method-plain-list">
          <li>La projection est une distribution probabiliste, non une annonce certaine du résultat.</li>
          <li>La référence actuelle prolonge principalement les structures électorales observées jusqu'en 2021 ; toutes les candidatures 2026 ne sont pas encore intégrées.</li>
          <li>La qualité de l'estimation varie selon la profondeur historique disponible pour chaque territoire et chaque force politique.</li>
          <li>Les événements de campagne peuvent modifier le contexte ; ils ne sont intégrés que lorsqu'ils satisfont les critères de documentation et de quantification prévus.</li>
          <li>Les estimations locales d'électorat utilisées dans la simulation ne doivent pas être interprétées comme des chiffres officiels d'inscrits 2026.</li>
        </ul>
      </section>
    </div>

    <section class="method-test">
      <div class="method-test-title"><span class="section-kicker">Évaluation après scrutin</span><h3>La méthode sera confrontée aux résultats observés.</h3><p>L'historique publié avant le vote constitue le référentiel d'évaluation.</p></div>
      <div class="method-test-body"><p>Après le 23 septembre 2026, Atlas comparera les résultats effectivement observés aux distributions publiées avant le scrutin. L'évaluation portera à la fois sur la précision territoriale et sur la qualité probabiliste des estimations.</p><div class="method-score-grid"><div><b>Calibration</b><span>Vérifier si les probabilités annoncées correspondent à la fréquence des événements observés.</span></div><div><b>Précision territoriale</b><span>Mesurer les écarts de voix et de sièges circonscription par circonscription.</span></div><div><b>Couverture de l'incertitude</b><span>Évaluer la fréquence à laquelle les résultats observés se situent dans les intervalles publiés.</span></div></div></div>
    </section>`;}

  const v='20260817-1848';
  const files=['/assets/core.js','/assets/territories.js','/assets/parties.js','/assets/daily.js','/assets/map.js'];
  let i=0;
  const next=()=>{if(i>=files.length)return;const s=document.createElement('script');s.src=`${files[i++]}?v=${v}`;s.onload=next;s.onerror=()=>{const f=document.querySelector('#fatal');if(f){f.hidden=false;f.textContent='Atlas 395 ne peut pas initialiser cette édition.'}};document.head.appendChild(s)};
  next();
})();
