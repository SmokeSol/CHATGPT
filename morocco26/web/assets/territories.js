function renderOverview(){
  renderNationalBoard();
  drawCartogram('overview-map', D.constituencies.constituencies, c=>U_COLOR[c.uncertainty.label]||'#56637a', id=>{selectedTerritory=id;showView('territories');renderTerritories();});
  renderLegend('overview-legend');
  const ranked = [...D.constituencies.constituencies].sort((a,b)=>b.uncertainty.value-a.uncertainty.value).slice(0,10);
  $('#open-territories').innerHTML = ranked.map((c,i)=>{
    const top=c.top_parties[0]||{};
    return `<button class="open-row" data-id="${esc(c.constituency_id)}"><span class="rank">${String(i+1).padStart(2,'0')}</span><span><b>${esc(c.name)}</b><small>${esc(c.region)} · ${c.magnitude} sièges</small></span><span class="u-label">${U_LABEL[c.uncertainty.label]||'—'}<br>${top.party?`${top.party} ${fmt(top.expected_seats,2)}`:''}</span></button>`;
  }).join('');
  $$('#open-territories .open-row').forEach(b=>b.onclick=()=>{selectedTerritory=b.dataset.id;showView('territories');renderTerritories();});
}

function renderNationalBoard(){
  const ps = D.national.parties;
  const scale = Math.max(160, ...ps.map(p=>p.q975||0));
  $('#national-board').innerHTML = ps.map(p=>{
    const left=clamp((p.q025||0)/scale*100,0,100), right=clamp((p.q975||0)/scale*100,0,100), med=clamp((p.q50||0)/scale*100,0,100);
    return `<div class="national-row"><span class="pty">${p.party}</span><span><b class="mean">${fmt(p.mean,1)}</b><span class="seat-label">sièges en moyenne</span></span><span class="range-track" title="Fourchette à 95 %"><i class="range" style="left:${left}%;width:${Math.max(1,right-left)}%"></i><i class="median" style="left:${med}%"></i></span><span class="bounds">${fmt(p.q025,0)} — ${fmt(p.q975,0)}</span></div>`;
  }).join('') + `<p class="note">Trait vertical safran : médiane. Bande bleue : fourchette centrale à 95 %. Les résultats nationaux proviennent de l'agrégation des simulations territoriales.</p>`;
}

function initTerritories(){
  const regs = [...new Set(D.constituencies.constituencies.map(c=>c.region))].sort((a,b)=>a.localeCompare(b,'fr'));
  $('#region-filter').innerHTML = `<option value="">Toutes les régions</option>` + regs.map(r=>`<option>${esc(r)}</option>`).join('');
  const counts = ['HIGH','MEDIUM','LOW'].map(k=>[k,D.constituencies.constituencies.filter(c=>c.uncertainty.label===k).length]);
  $('#uncertainty-chips').innerHTML = `<button class="chip" data-u="" aria-pressed="true">Toutes <span class="n">92</span></button>` + counts.map(([k,n])=>`<button class="chip" data-u="${k}" aria-pressed="false"><span class="dot" style="background:${U_COLOR[k]}"></span>${U_LABEL[k]} <span class="n">${n}</span></button>`).join('');
  $('#q').oninput = e=>{territoryFilters.query=e.target.value.trim().toLowerCase();renderTerritories();};
  $('#region-filter').onchange = e=>{territoryFilters.region=e.target.value;renderTerritories();};
  $$('#uncertainty-chips .chip').forEach(b=>b.onclick=()=>{territoryFilters.uncertainty=b.dataset.u;$$('#uncertainty-chips .chip').forEach(x=>x.setAttribute('aria-pressed',String(x===b)));renderTerritories();});
  $('#toggle-table').onclick=()=>{const on=$('#table-panel').style.display==='none';$('#table-panel').style.display=on?'block':'none';$('#toggle-table').setAttribute('aria-pressed',String(on));};
}
function filteredTerritories(){
  return D.constituencies.constituencies.filter(c=>(!territoryFilters.query||`${c.name} ${c.region}`.toLowerCase().includes(territoryFilters.query))&&(!territoryFilters.region||c.region===territoryFilters.region)&&(!territoryFilters.uncertainty||c.uncertainty.label===territoryFilters.uncertainty));
}
function renderTerritories(){
  const rows = filteredTerritories();
  const visible = new Set(rows.map(c=>c.constituency_id));
  $('#map-count').textContent = `${rows.length} sur 92`;
  drawCartogram('territory-map', D.constituencies.constituencies, c=>visible.has(c.constituency_id)?(U_COLOR[c.uncertainty.label]||'#56637a'):'#202938', id=>{selectedTerritory=id;renderTerritoryCard();renderTerritories();}, selectedTerritory, visible);
  renderLegend('territory-legend');
  renderTerritoryCard();
  const ranked=[...rows].sort((a,b)=>b.uncertainty.value-a.uncertainty.value).slice(0,10);
  $('#uncertainty-ranking').innerHTML=ranked.map((c,i)=>`<button class="open-row" data-id="${esc(c.constituency_id)}"><span class="rank">${String(i+1).padStart(2,'0')}</span><span><b>${esc(c.name)}</b><small>${esc(c.region)}</small></span><span class="u-label">${U_LABEL[c.uncertainty.label]}</span></button>`).join('');
  $$('#uncertainty-ranking .open-row').forEach(b=>b.onclick=()=>{selectedTerritory=b.dataset.id;renderTerritories();});
  renderTerritoryTable(rows);
}
function renderTerritoryCard(){
  const c=D.constituencies.constituencies.find(x=>x.constituency_id===selectedTerritory);if(!c)return;
  const tops=[...c.top_parties].slice(0,5), max=Math.max(...tops.map(x=>x.expected_seats||0),1);
  const hist=c.history?.['2021'];
  const histTop=hist?.status==='AVAILABLE'?Object.entries(hist.vote_share||{}).sort((a,b)=>(b[1]||0)-(a[1]||0)).slice(0,3):[];
  $('#territory-card-body').innerHTML=`<div class="territory-insight"><div class="territory-title"><span class="eyebrow">${esc(c.region)}</span><h3>${esc(c.name)}</h3><p>${c.magnitude} sièges locaux · incertitude ${String(U_LABEL[c.uncertainty.label]||'').toLowerCase()}</p><div class="territory-tags"><span>Participation médiane : ${pct(c.turnout_distribution?.q50,1)}</span><span>Projection probabiliste</span></div></div><div class="projection-list"><h4>Rapport de forces projeté</h4>${tops.map(p=>`<div class="projection-line"><b>${p.party}</b><span class="bar"><i style="width:${clamp((p.expected_seats||0)/max*100,1,100)}%"></i></span><span class="val">${fmt(p.expected_seats,2)} · ${pct(p.p_ge_1,0)}</span></div>`).join('')}<p class="note">Le premier chiffre est le nombre moyen de sièges ; le second, la probabilité d'obtenir au moins un siège.</p></div><div class="history-mini"><h4>Repères 2021</h4><div class="history-grid">${histTop.length?histTop.map(([p,v])=>`<div><b>${p} · ${pct(v,1)}</b><span>part des voix locales</span></div>`).join(''):'<div><b>Non disponible</b><span>historique territorial</span></div>'}</div></div><div class="info-state"><h4>Informations 2026</h4><div class="info-grid"><div><b>Candidatures</b><span>Non encore intégrées</span></div><div><b>Têtes de liste</b><span>Non encore intégrées</span></div><div><b>Changements de parti</b><span>Non encore intégrés</span></div><div><b>Incidence récente</b><span>Aucune modification validée</span></div></div></div></div>`;
}
function renderTerritoryTable(rows){
  $('#table-count').textContent=`${rows.length} lignes`;
  $('#territory-table').innerHTML=`<thead><tr><th>Circonscription</th><th>Région</th><th>Sièges</th><th>Incertitude</th><th>Parti le mieux positionné</th><th>Sièges moyens</th><th>Au moins 1 siège</th></tr></thead><tbody>${rows.map(c=>{const p=c.top_parties[0]||{};return`<tr data-id="${esc(c.constituency_id)}"><td>${esc(c.name)}</td><td>${esc(c.region)}</td><td class="num">${c.magnitude}</td><td>${U_LABEL[c.uncertainty.label]||'—'}</td><td><b>${p.party||'—'}</b></td><td class="num">${fmt(p.expected_seats,2)}</td><td class="num">${pct(p.p_ge_1,0)}</td></tr>`}).join('')}</tbody>`;
  $$('#territory-table tbody tr').forEach(r=>r.onclick=()=>{selectedTerritory=r.dataset.id;$('#table-panel').style.display='none';$('#toggle-table').setAttribute('aria-pressed','false');renderTerritories();});
}

