(()=>{
  const navIndex=NAV.findIndex(([id])=>id==='signals');
  if(!NAV.some(([id])=>id==='candidates')) NAV.splice(navIndex<0?NAV.length:navIndex,0,['candidates','Candidatures 2026','V1']);

  const main=document.querySelector('main');
  if(main&&!document.querySelector('#view-candidates')){
    const section=document.createElement('section');
    section.className='view'; section.id='view-candidates'; section.setAttribute('role','tabpanel');
    section.innerHTML=`
      <div class="view-head candidates-head"><div><span class="section-kicker">Atlas V1 · Arabic Native</span><h2>Candidatures et identité territoriale 2026</h2><p>Une couche factuelle bilingue reliée aux 92 circonscriptions canoniques. Elle reste séparée de F0 : aucun candidat ou signal ne reçoit encore un effet automatique en voix ou en sièges.</p></div><div class="edition-badge v1-edition"><span>COUCHE D'ÉVIDENCE</span><b id="v1-generated">—</b></div></div>
      <div class="v1-separation" role="note"><div class="v1-separation-mark">F0</div><div><b>Projection gelée inchangée</b><span>Les candidatures 2026 sont consultables, mais leur impact prédictif n'est pas encore calibré.</span></div><div class="v1-separation-status">AUCUN DELTA APPLIQUÉ</div></div>
      <div class="v1-kpis" id="v1-kpis"></div>
      <div class="candidate-controls panel"><label class="candidate-search"><span>Rechercher</span><input id="candidate-query" type="search" dir="auto" autocomplete="off" placeholder="Candidat, دائرة انتخابية, circonscription…"></label><label><span>Parti</span><select id="candidate-party"><option value="">Tous les partis</option></select></label><label><span>Région</span><select id="candidate-region"><option value="">Toutes les régions</option></select></label><button class="candidate-reset" id="candidate-reset" type="button">Réinitialiser</button></div>
      <div class="candidate-layout"><section class="panel candidate-territories-panel"><div class="panel-head"><h3>Circonscriptions</h3><div class="grow"></div><span class="eyebrow" id="candidate-territory-count">92 territoires</span></div><div class="candidate-territory-list" id="candidate-territory-list"></div></section><section class="panel candidate-detail-panel"><div id="candidate-detail"></div></section></div>`;
    const signals=document.querySelector('#view-signals'); if(signals)main.insertBefore(section,signals);else main.appendChild(section);
  }

  const originalBoot=boot;
  let V1=null,selected=null;
  const filters={query:'',party:'',region:''};
  const searchKey=value=>String(value??'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[أإآٱ]/g,'ا').replace(/[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]/g,'').toLowerCase().replace(/[^a-z0-9\u0600-\u06ff]+/g,' ').trim();
  const isArabic=value=>/[\u0600-\u06ff]/.test(String(value??''));
  const candidateLatin=c=>c.name_lat||(c.name_source_form&&!isArabic(c.name_source_form)?c.name_source_form:null);
  const candidateArabic=c=>c.name_ar||(c.name_source_form&&isArabic(c.name_source_form)?c.name_source_form:null);
  const statusLabel=status=>({PARTY_ANNOUNCED_AND_MEDIAS24_STRUCTURED:'Parti + Médias24',PARTY_ANNOUNCED_OR_MEDIAS24_REPORTED:'Médias24 structuré',PARTY_ANNOUNCED:'Annonce officielle du parti',PARTY_ANNOUNCED_EVIDENCE_LAYER:'Annonce officielle du parti',MEDIAS24_REPORTED:'Médias24',AMBIGUOUS:'Ambigu',DATA_BLOCKED:'Donnée bloquée'}[status]||String(status||'Source documentée').replaceAll('_',' '));
  const statusClass=status=>String(status).includes('AMBIGUOUS')?'bad':String(status).includes('DATA_BLOCKED')?'blocked':String(status).includes('PARTY_ANNOUNCED_AND')?'strong':String(status).includes('PARTY_ANNOUNCED')?'party':'media';
  const sourceHref=c=>/^https?:\/\//.test(c.source_url||'')?c.source_url:/^https?:\/\//.test(c.source_database_url||'')?'https://assets.medias24.com/elections/':null;
  const sourceLabel=c=>c.source_class==='OFFICIAL_PARTY'?'Source officielle du parti':c.source_class==='MEDIAS24'?'Médias24 · base structurée':c.source_class||'Source documentée';
  const candidateNameKey=c=>searchKey([candidateLatin(c),candidateArabic(c),c.party,c.role,c.constituency_canonical_name,c.constituency_name_ar].filter(Boolean).join(' '));

  function prepare(){
    const byTerritory=new Map();
    (V1.candidates||[]).forEach(c=>{if(!c.constituency_id)return;if(!byTerritory.has(c.constituency_id))byTerritory.set(c.constituency_id,[]);byTerritory.get(c.constituency_id).push(c)});
    V1._byTerritory=byTerritory; V1._territories=[...(V1.territories||[])].sort((a,b)=>a.name_fr.localeCompare(b.name_fr,'fr'));
    if(!selected)selected=V1._territories.find(t=>t.constituency_id==='casablanca-anfa')?.constituency_id||V1._territories[0]?.constituency_id;
  }
  function filteredTerritories(){
    const q=searchKey(filters.query);
    return V1._territories.filter(t=>{if(filters.region&&t.region_fr!==filters.region)return false;const cs=V1._byTerritory.get(t.constituency_id)||[];if(filters.party&&!cs.some(c=>c.party===filters.party))return false;if(!q)return true;return searchKey(`${t.name_fr} ${t.name_ar} ${t.region_fr} ${t.region_ar}`).includes(q)||cs.some(c=>candidateNameKey(c).includes(q))});
  }
  function renderKpis(){
    const c=V1.coverage||{},p=V1.pjd_bilingual_roster||[];
    const values=[[c.arabic_identity_coverage||0,'identités territoriales arabes','hi'],[c.candidate_records_after_official_pjd_merge||0,'fiches candidatures',''],[c.local_territories_with_records_after_merge||0,'circonscriptions couvertes',''],[c.parties||0,'partis structurés',''],[p.filter(r=>r.person_name_ar&&r.person_name_lat).length,'PJD arabe + latin',''],[p.filter(r=>r.nomination_status==='PENDING_NOMINATION').length,'investiture en attente','warn']];
    $('#v1-kpis').innerHTML=values.map(([v,l,k])=>`<div class="v1-kpi ${k}"><b class="big">${Number(v).toLocaleString('fr-FR')}</b><span>${esc(l)}</span></div>`).join('');
  }
  function renderTerritoryList(){
    const rows=filteredTerritories(); $('#candidate-territory-count').textContent=`${rows.length} territoire${rows.length>1?'s':''}`;
    if(rows.length&&!rows.some(t=>t.constituency_id===selected))selected=rows[0].constituency_id;
    $('#candidate-territory-list').innerHTML=rows.length?rows.map(t=>{const cs=V1._byTerritory.get(t.constituency_id)||[],visible=filters.party?cs.filter(c=>c.party===filters.party):cs;return`<button class="candidate-territory ${t.constituency_id===selected?'selected':''}" data-id="${esc(t.constituency_id)}"><span class="candidate-territory-main"><b>${esc(t.name_fr)}</b><i dir="rtl" lang="ar">${esc(t.name_ar)}</i></span><span class="candidate-territory-meta"><em>${visible.length}</em><small>candidat${visible.length>1?'s':''}</small></span></button>`}).join(''):'<div class="candidate-empty">Aucun territoire ne correspond aux filtres.</div>';
    $$('#candidate-territory-list .candidate-territory').forEach(b=>b.onclick=()=>{selected=b.dataset.id;renderTerritoryList();renderDetail()});
  }
  function renderCandidateCard(c){
    const latin=candidateLatin(c),arabic=candidateArabic(c),pending=!latin&&!arabic||String(c.source_status||'').includes('PENDING'),status=c.atlas_evidence_status||c.evidence_status||'MEDIAS24_REPORTED',href=sourceHref(c),role=c.role||'Candidature législative';
    return`<article class="candidate-card"><div class="candidate-card-top"><span class="candidate-party">${esc(c.party||'—')}</span><span class="candidate-status ${statusClass(status)}">${esc(statusLabel(status))}</span></div><div class="candidate-names"><b>${esc(latin||(pending?'Investiture en cours':'Nom latin non documenté'))}</b>${arabic?`<span dir="rtl" lang="ar">${esc(arabic)}</span>`:''}</div><div class="candidate-role">${esc(role)}</div><div class="candidate-source"><span>${esc(sourceLabel(c))}</span>${href?`<a href="${esc(href)}" target="_blank" rel="noopener">Voir la source ↗</a>`:''}</div></article>`;
  }
  function renderDetail(){
    const t=V1._territories.find(r=>r.constituency_id===selected);if(!t){$('#candidate-detail').innerHTML='<div class="candidate-empty">Sélectionnez une circonscription.</div>';return}
    let cs=[...(V1._byTerritory.get(t.constituency_id)||[])];if(filters.party)cs=cs.filter(c=>c.party===filters.party);const q=searchKey(filters.query);if(q&&!searchKey(`${t.name_fr} ${t.name_ar}`).includes(q))cs=cs.filter(c=>candidateNameKey(c).includes(q));cs.sort((a,b)=>String(a.party).localeCompare(String(b.party),'fr')||String(candidateLatin(a)||candidateArabic(a)||'').localeCompare(String(candidateLatin(b)||candidateArabic(b)||''),'fr'));const parties=[...new Set(cs.map(c=>c.party).filter(Boolean))];
    $('#candidate-detail').innerHTML=`<header class="candidate-detail-head"><div><span class="section-kicker">${esc(t.region_fr)}</span><h3>${esc(t.name_fr)}</h3><div class="candidate-arabic-title" dir="rtl" lang="ar">${esc(t.name_ar)}</div></div><div class="candidate-seat"><b>${t.seats}</b><span>siège${t.seats>1?'s':''}</span></div></header><div class="candidate-detail-stats"><div><b>${cs.length}</b><span>fiches visibles</span></div><div><b>${parties.length}</b><span>partis visibles</span></div><div><b>92/92</b><span>identité arabe</span></div></div><div class="candidate-no-impact"><b>Lecture factuelle uniquement.</b> Aucun élément ci-dessous ne modifie F0 tant que son effet électoral n'est pas calibré.</div><div class="candidate-cards">${cs.length?cs.map(renderCandidateCard).join(''):'<div class="candidate-empty">Aucune fiche visible avec ces filtres.</div>'}</div>`;
  }
  function renderCandidates(){
    prepare();$('#v1-generated').textContent=dateFr(V1.generated_at,true);renderKpis();
    const codes=[...new Set((V1.candidates||[]).map(c=>c.party).filter(Boolean))].sort();$('#candidate-party').innerHTML='<option value="">Tous les partis</option>'+codes.map(code=>`<option value="${esc(code)}">${esc(code)} · ${esc(PARTIES[code]||code)}</option>`).join('');
    const regions=[...new Set(V1._territories.map(t=>t.region_fr))].sort((a,b)=>a.localeCompare(b,'fr'));$('#candidate-region').innerHTML='<option value="">Toutes les régions</option>'+regions.map(r=>`<option value="${esc(r)}">${esc(r)}</option>`).join('');
    $('#candidate-query').oninput=e=>{filters.query=e.target.value;renderTerritoryList();renderDetail()};$('#candidate-party').onchange=e=>{filters.party=e.target.value;renderTerritoryList();renderDetail()};$('#candidate-region').onchange=e=>{filters.region=e.target.value;renderTerritoryList();renderDetail()};$('#candidate-reset').onclick=()=>{filters.query=filters.party=filters.region='';$('#candidate-query').value='';$('#candidate-party').value='';$('#candidate-region').value='';renderTerritoryList();renderDetail()};
    renderTerritoryList();renderDetail();const badge=$('#tab-candidates i');if(badge)badge.textContent=String(V1.coverage?.candidate_records_after_official_pjd_merge||'V1');const status=$('#status-detail');if(status)status.textContent=`Projection F0 gelée · couche factuelle 2026 active : ${Number(V1.coverage?.candidate_records_after_official_pjd_merge||0).toLocaleString('fr-FR')} fiches, 92 identités territoriales arabes.`;
  }
  boot=async function(){await originalBoot();try{V1=await load('atlas_v1.json');D.atlasV1=V1;renderCandidates()}catch(error){console.error('Atlas V1 evidence layer unavailable',error);const tab=$('#tab-candidates');if(tab)tab.title='Couche Atlas V1 temporairement indisponible'}};
})();
