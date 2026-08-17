function atlasDataBase(){return window.ATLAS_DATA_BASE||'/data/'}
function atlasEditionBase(){return window.ATLAS_EDITION_BASE||'/editions/'}
async function atlasOptional(base,name){try{const r=await fetch(`${base}${name}`,{cache:'no-store'});if(!r.ok)return null;return r.json()}catch(_){return null}}
function editionDateFr(id){if(!id)return'—';const d=new Date(`${id}T12:00:00+01:00`);return d.toLocaleDateString('fr-FR',{day:'2-digit',month:'long',year:'numeric'})}
async function boot(){
  try{
    const [snapshot,national,constituencies,parties,evidence,methodology,daily,editionCurrent,editionIndex]=await Promise.all([
      load('current_snapshot.json'),load('national_projection.json'),load('constituency_cards.json'),load('party_cards.json'),load('evidence_index.json'),load('public_methodology.json'),
      atlasOptional(atlasDataBase(),'daily_update.json'),atlasOptional(atlasEditionBase(),'current.json'),atlasOptional(atlasEditionBase(),'index.json')
    ]);
    D={snapshot,national,constituencies,parties,evidence,methodology,daily,editionCurrent,editionIndex};
    selectedTerritory=[...constituencies.constituencies].sort((a,b)=>b.uncertainty.value-a.uncertainty.value)[0]?.constituency_id;
    selectedParty=national.parties[0]?.party||'RNI';
    initNavigation();renderHeader();renderOverview();initTerritories();renderTerritories();renderParties();renderSignals();renderHistory();renderMethodology();
    window.addEventListener('scroll',()=>document.body.classList.toggle('compact',window.scrollY>140),{passive:true});
  }catch(e){$('#fatal').hidden=false;$('#fatal').textContent=`Atlas 395 ne peut pas charger les données de cette édition : ${e.message}`;console.error(e)}
}
function renderHeader(){
  const s=D.snapshot,ec=D.editionCurrent,daily=D.daily;
  $('#meta-asof').textContent=ec?.published_at?dateFr(ec.published_at,true):dateFr(s.data_cutoff||s.created_at);
  $('#edition-date').textContent=ec?.edition_id?editionDateFr(ec.edition_id):dateFr(s.created_at);
  const noChange=D.evidence.forecast_change==='NONE';
  $('#status-detail').textContent=noChange?'Projection territoriale de référence · veille 2026 active · nouvelles informations distinguées de leur éventuel impact électoral.':'Une version enrichie de la projection est disponible.';
  $('#kpis').innerHTML=[['395','sièges au total','hi'],['305','sièges locaux',''],['90','sièges régionaux',''],[Number(s.draws||0).toLocaleString('fr-FR'),'scénarios simulés',''],['92','circonscriptions locales',''],['12','circonscriptions régionales','']].map(([v,l,c])=>`<div class="kpi ${c}"><b class="big">${v}</b><span>${l}</span></div>`).join('');
  let strip=$('#daily-strip');if(!strip){document.querySelector('.atlas-status')?.insertAdjacentHTML('afterend','<div class="daily-strip" id="daily-strip" hidden></div>');strip=$('#daily-strip')}
  if(!daily||!strip){if(strip)strip.hidden=true;return}
  const title=ec?.edition_id?`Édition du ${editionDateFr(ec.edition_id)}`:'Édition quotidienne';
  const projection=daily.projection_changed?`${daily.territories_changed||0} territoire(s) évoluent`:'Projection chiffrée stable';
  const signals=`${daily.new_documented_signals||0} nouveau(x) signal(aux)`;const docs=Number(daily.documents_acquired_delta||0);
  strip.hidden=false;strip.innerHTML=`<div class="daily-title"><span class="section-kicker">${esc(title)}</span><b>${esc(daily.summary_fr||'Actualisation quotidienne enregistrée.')}</b></div><div class="daily-stat"><span>Projection</span><b>${esc(projection)}</b></div><div class="daily-stat"><span>Veille</span><b>${esc(signals)}</b></div><div class="daily-stat"><span>Documents</span><b>${docs>=0?'+':''}${docs}</b></div>`;
}
function renderHistory(){
  const rows=[...(D.editionIndex?.editions||[])].sort((a,b)=>String(b.edition_id).localeCompare(String(a.edition_id)));
  if(!rows.length){const d=dateFr(D.snapshot.created_at);$('#history-rail').innerHTML=`<article class="history-card-premium current"><span class="date">${d}</span><h3>Projection structurelle de référence</h3><p>Projection nationale entièrement territorialisée : 395 sièges couverts dans chaque scénario simulé.</p><span class="status">Version enregistrée</span></article><article class="history-card-premium future"><span class="date">Prochaine édition</span><h3>Actualisation quotidienne</h3><p>Les nouvelles informations suffisamment documentées apparaîtront ici sans réécrire les éditions précédentes.</p><span class="status">À venir</span></article>`;return}
  const cards=rows.slice(0,12).map((r,i)=>{const title=r.projection_changed?'Projection actualisée':'Projection stable';return`<article class="history-card-premium ${i===0?'current':''}"><span class="date">${editionDateFr(r.edition_id)}</span><h3>${title}</h3><p>${esc(r.summary_fr||'Édition quotidienne enregistrée.')}</p><span class="status">${i===0?'Édition actuelle':'Édition conservée'}</span></article>`}).join('');
  $('#history-rail').innerHTML=cards+`<article class="history-card-premium future"><span class="date">Après le 23 septembre 2026</span><h3>Évaluation de la projection</h3><p>Comparaison des résultats observés aux distributions publiées avant le scrutin, circonscription par circonscription.</p><span class="status">Après scrutin</span></article>`;
}
