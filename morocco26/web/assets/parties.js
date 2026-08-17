function renderParties(){
  const partyMap = Object.fromEntries(D.parties.parties.map(p=>[p.party,p]));
  const ordered=D.national.parties.map(n=>({code:n.party,n,card:partyMap[n.party]}));
  $('#party-list').innerHTML=ordered.map(p=>`<button data-party="${p.code}" class="${p.code===selectedParty?'active':''}"><span class="code">${p.code}</span><span class="label">${esc(PARTIES[p.code]||p.code)}</span><span class="seats">${fmt(p.n.mean,1)}</span></button>`).join('');
  $$('#party-list button').forEach(b=>b.onclick=()=>{selectedParty=b.dataset.party;renderParties();});
  renderPartyStage();
}
function renderPartyStage(){
  const n=D.national.parties.find(x=>x.party===selectedParty), p=D.parties.parties.find(x=>x.party===selectedParty);if(!n||!p)return;
  $('#party-stage').innerHTML=`<div class="party-stage-grid"><div class="panel"><div class="party-hero-premium"><span class="section-kicker">Projection nationale</span><div class="party-code">${selectedParty}</div><p>${esc(PARTIES[selectedParty]||selectedParty)}</p><div class="party-seats">${fmt(n.mean,1)} <span>sièges en moyenne</span></div><div class="interval-display"><b>${fmt(n.q025,0)} — ${fmt(n.q975,0)} sièges</b><span>Fourchette centrale à 95 % · médiane ${fmt(n.q50,0)}</span></div><div class="history-bars"><h3>Part des voix locales</h3>${['2011','2016','2021'].map(y=>{const v=p.historical_local_vote_share?.[y];return`<div class="history-bar"><b>${y}</b><span class="track"><i style="width:${clamp((v||0)*300,1,100)}%"></i></span><span class="num">${pct(v,1)}</span></div>`}).join('')}</div></div></div><div><div class="panel"><div class="panel-head"><h3>Implantation territoriale</h3><div class="grow"></div><span class="eyebrow">Probabilité d'au moins un siège</span></div><div class="party-map-wrap"><svg class="cartogram atlas-party-map" id="party-map"></svg><div class="atlas-legend"><div><i style="background:#6e8bff"></i>≥ 75 %</div><div><i style="background:#536ac2"></i>50–75 %</div><div><i style="background:#384981"></i>25–50 %</div><div><i style="background:#242e40"></i>&lt; 25 %</div></div></div></div><div class="panel" style="margin-top:14px"><div class="panel-head"><h3>Principaux territoires d'appui</h3></div><div class="panel-body"><div class="party-territory-grid">${p.strongest_territories.slice(0,10).map(t=>`<button class="party-territory" data-id="${esc(t.constituency_id)}"><b>${esc(t.name)}</b><small>${esc(t.region)} · ${fmt(t.expected_seats,2)} siège(s) moyen(s) · ${pct(t.p_ge_1,0)}</small></button>`).join('')}</div></div></div></div></div>`;
  drawCartogram('party-map',D.constituencies.constituencies,c=>probColor(c.parties?.[selectedParty]?.p_ge_1),id=>{selectedTerritory=id;showView('territories');renderTerritories();});
  $$('.party-territory').forEach(b=>b.onclick=()=>{selectedTerritory=b.dataset.id;showView('territories');renderTerritories();});
}
function probColor(v){if(v>=.75)return'#6e8bff';if(v>=.5)return'#536ac2';if(v>=.25)return'#384981';return'#242e40';}

function renderSignals(){
  const e=D.evidence, scope=e.reader_scope||{}, sources=e.sources||[], events=e.events||[];
  $('#signal-kpis').innerHTML=[
    [scope.authorized_sources??sources.length,'sources autorisées'],
    [scope.documents_acquired??'—','documents acquis dans ce périmètre'],
    [scope.authorized_media_sources??1,'média autorisé'],
    [scope.documented_signals??events.length,'signaux documentés']
  ].map(([v,l])=>`<div class="signal-kpi"><b>${v}</b><span>${l}</span></div>`).join('');
  $('#signal-callout').innerHTML=`<b>Périmètre documentaire strict.</b><p>Atlas retient uniquement les sources institutionnelles, les publications officielles des partis et Médias24. Aucun autre média n'est collecté, affiché ou comptabilisé.</p><p>Médias24 sert à la veille et à la corroboration. Une publication médiatique ne peut jamais modifier seule la projection.</p>`;
  $('#signal-events').innerHTML=events.length?events.map(x=>{
    const origin=SOURCE_NAMES[x.source]||'Source officielle';
    const code=String(x.source||'');
    const isMedias24=code==='T2_MEDIAS24';
    const isParty=code.startsWith('T1_');
    const summary=x.id==='PJD_ROSTER_SURFACE_WAVE1'
      ?'Une liste structurée de candidatures a été repérée sur une publication officielle du PJD.'
      :(isMedias24?'Information repérée par Médias24 — confirmation primaire requise':isParty?'Annonce officielle d’un parti — validation externe requise':'Information institutionnelle en cours de qualification');
    const detail=x.id==='PJD_ROSTER_SURFACE_WAVE1'
      ?'93 lignes ont été identifiées. Une confirmation indépendante reste nécessaire avant toute intégration dans la projection.'
      :(isMedias24?'Cette publication est conservée comme piste de veille. Elle doit être confirmée par une source primaire compétente ou par des éléments réellement indépendants avant toute utilisation.':isParty?'Cette publication établit ce que le parti annonce, mais pas à elle seule l’enregistrement juridique ou la véracité définitive du fait.':'Cette information reste hors du calcul jusqu’à validation de l’autorité compétente, de l’identité et du périmètre territorial.');
    return`<div class="signal-event"><div class="origin">${esc(origin)}</div><div><h4>${esc(summary)}</h4><p>${esc(detail)}</p></div><div class="impact-none">Aucune incidence automatique</div></div>`;
  }).join(''):`<p class="note">Aucun signal suffisamment confirmé n'est encore disponible dans le périmètre autorisé.</p>`;
  const orderedSources=[...sources].sort((a,b)=>sourceOrder(a.source)-sourceOrder(b.source)||String(SOURCE_NAMES[a.source]||a.source).localeCompare(String(SOURCE_NAMES[b.source]||b.source),'fr'));
  $('#source-grid').innerHTML=orderedSources.map(s=>{const st=sourceState(s.states||{});return`<div class="source-card-premium"><b>${esc(SOURCE_NAMES[s.source]||'Source officielle')}</b><span>${esc(sourceRole(s.source))} · ${st.detail}</span><div class="state"><i class="state-dot ${st.cls}"></i>${st.label}</div></div>`}).join('');
}
function sourceOrder(code){const c=String(code||'');if(c.startsWith('T0_'))return 0;if(c.startsWith('T1_'))return 1;if(c==='T2_MEDIAS24')return 2;return 9;}
function sourceRole(code){
  const c=String(code||'');
  if(c.startsWith('T0_'))return'Source institutionnelle officielle';
  if(c.startsWith('T1_'))return'Publication officielle d’un parti — déclaration intéressée';
  if(c==='T2_MEDIAS24')return'Média autorisé — veille et corroboration uniquement';
  return'Source hors périmètre';
}
function sourceState(states){
  const a=Number(states.ACQUIRED||0), er=Number(states.FETCH_ERROR||0), bl=Number(states.BLOCKED_SOURCE||0);
  if(a>0&&(er>0||bl>0))return{label:'Accessible, couverture partielle',detail:`${a} document${a>1?'s':''} acquis`,cls:'state-partial'};
  if(a>0)return{label:'Accessible',detail:`${a} document${a>1?'s':''} acquis`,cls:'state-ok'};
  if(bl>0)return{label:'Indisponible à cette date',detail:'Accès non obtenu lors de la dernière collecte',cls:'state-off'};
  if(er>0)return{label:'Accès intermittent',detail:'Nouvelle tentative nécessaire',cls:'state-partial'};
  return{label:'À documenter',detail:'Aucun contenu exploitable à ce stade',cls:'state-off'};
}
function humanizeSource(code){return String(code||'Source').replace(/^T\d_/, '').replace(/_/g,' ').toLowerCase().replace(/^./,c=>c.toUpperCase());}

function renderHistory(){
  const s=D.snapshot, d=dateFr(s.created_at);
  $('#history-rail').innerHTML=`<article class="history-card-premium current"><span class="date">${d}</span><h3>Projection structurelle de référence</h3><p>Première projection nationale entièrement territorialisée : 395 sièges couverts dans chaque scénario simulé.</p><span class="status">Version enregistrée</span></article><article class="history-card-premium future"><span class="date">Prochaine étape</span><h3>Projection enrichie 2026</h3><p>Intégration des candidatures, changements de parti et autres informations validées lorsqu'elles deviennent suffisamment documentées.</p><span class="status">À venir</span></article><article class="history-card-premium future"><span class="date">Après le 23 septembre 2026</span><h3>Évaluation de la projection</h3><p>Comparaison des résultats observés aux distributions publiées avant le scrutin, circonscription par circonscription.</p><span class="status">Après scrutin</span></article>`;
}
