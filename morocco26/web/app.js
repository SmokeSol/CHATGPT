const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmt = (v,d=1) => v == null ? '—' : Number(v).toLocaleString('fr-FR',{minimumFractionDigits:d,maximumFractionDigits:d});
const pct = (v,d=0) => v == null ? '—' : `${fmt(v*100,d)}%`;
const esc = s => String(s ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp = (x,a,b)=>Math.max(a,Math.min(b,x));
let D = {}, visibleCount = 12;

async function get(name){const r=await fetch(`/data/${name}`,{cache:'no-store'});if(!r.ok)throw new Error(`${name}: HTTP ${r.status}`);return r.json()}
async function boot(){
  try{
    const [snapshot,national,constituencies,parties,evidence,methodology] = await Promise.all([
      get('current_snapshot.json'),get('national_projection.json'),get('constituency_cards.json'),get('party_cards.json'),get('evidence_index.json'),get('methodology_state.json')
    ]);
    D={snapshot,national,constituencies,parties,evidence,methodology};
    renderAll();
  }catch(e){$('#fatal').hidden=false;$('#fatal').textContent=`Atlas 395 n'a pas pu charger ses vues dérivées: ${e.message}`;console.error(e)}
}
function renderAll(){
  const s=D.snapshot;
  $('#snapshotChip').textContent=`${s.snapshot_id} · ${s.status}`;
  $('#modelState').textContent='STRUCTURAL ONLY';
  $('#modelSubstate').textContent=`${s.draws.toLocaleString('fr-FR')} simulations · aucune correction candidat/événement/agentique`;
  $('#metrics').innerHTML=[['395','sièges simulés'],['92','circonscriptions locales'],['12','circonscriptions régionales'],[s.draws.toLocaleString('fr-FR'),'élections Monte Carlo'],['F−1','snapshot courant'],['READ ONLY','contrat produit']].map(([v,l])=>`<div class="metric"><b>${v}</b><span>${l}</span></div>`).join('');
  renderNational();renderConstituencies();renderParties();renderEvidence();renderTimeline();
}
function renderNational(){
  const parties=D.national.parties; const max=Math.max(...parties.map(x=>x.mean||0));
  $('#nationalGrid').innerHTML=parties.map(p=>`<article class="national-card"><header><span class="party-badge">${esc(p.party)}</span><span class="range">95% ${fmt(p.q025,0)} — ${fmt(p.q975,0)}</span></header><div class="mean">${fmt(p.mean,1)}</div><small>sièges attendus · médiane ${fmt(p.q50,0)}</small><div class="dist-track"><i style="width:${clamp((p.mean||0)/max*100,2,100)}%"></i></div></article>`).join('');
  const r=D.national.first_place_probability;
  $('#rankNotice').textContent=r?.reason||'';
}
function filteredConstituencies(){
  const q=$('#constSearch').value.trim().toLowerCase(), region=$('#regionFilter').value, u=$('#uncertaintyFilter').value;
  return D.constituencies.constituencies.filter(c=>(!q||`${c.name} ${c.region}`.toLowerCase().includes(q))&&(!region||c.region===region)&&(!u||c.uncertainty.label===u));
}
function renderConstituencies(){
  const regions=[...new Set(D.constituencies.constituencies.map(c=>c.region))].sort((a,b)=>a.localeCompare(b,'fr'));
  if($('#regionFilter').options.length===1) $('#regionFilter').insertAdjacentHTML('beforeend',regions.map(r=>`<option>${esc(r)}</option>`).join(''));
  const rows=filteredConstituencies();
  $('#constituencyGrid').innerHTML=rows.slice(0,visibleCount).map(c=>{
    const top=c.top_parties.slice(0,4), max=Math.max(...top.map(x=>x.expected_seats||0),1);
    return `<article class="const-card" data-id="${esc(c.constituency_id)}"><div class="const-head"><div><small>${esc(c.region)} · ${c.magnitude} sièges</small><h3>${esc(c.name)}</h3></div><span class="u ${c.uncertainty.label}">${c.uncertainty.label}</span></div><div class="seat-list">${top.map(p=>`<div class="seat-row"><b>${p.party}</b><span class="bar"><i style="width:${clamp((p.expected_seats||0)/max*100,1,100)}%"></i></span><span>${fmt(p.expected_seats,2)}</span></div>`).join('')}</div><div class="unknowns"><span>Candidats: UNKNOWN</span><span>Tête de liste: UNKNOWN</span><span>Switch: UNKNOWN</span></div></article>`
  }).join('');
  $('#showMore').hidden=rows.length<=visibleCount;
  $$('.const-card').forEach(el=>el.onclick=()=>openConstituency(el.dataset.id));
}
function openConstituency(id){
  const c=D.constituencies.constituencies.find(x=>x.constituency_id===id); if(!c)return;
  const parties=Object.entries(c.parties).sort((a,b)=>(b[1].expected_seats||0)-(a[1].expected_seats||0));
  const years=['2011','2016','2021'];
  const modal=document.createElement('div');modal.className='modal';
  modal.innerHTML=`<div class="modal-card"><button class="modal-close">Fermer</button><div class="eyebrow">${esc(c.region)} · ${c.magnitude} sièges</div><h2>${esc(c.name)}</h2><div class="modal-grid"><div class="modal-box"><h4>F−1 · sièges attendus</h4>${parties.map(([p,d])=>`<div class="seat-row"><b>${p}</b><span class="bar"><i style="width:${pct(d.p_ge_1).replace('%','')}%"></i></span><span>${fmt(d.expected_seats,2)}</span></div>`).join('')}</div><div class="modal-box"><h4>Incertitude</h4><strong>${c.uncertainty.label}</strong><p>${fmt(c.uncertainty.value,2)} bits · indicateur relatif</p><p>Inscrits latents médiane: ${fmt(c.registered_N_distribution?.q50,0)}<br>Turnout médian: ${pct(c.turnout_distribution?.q50,1)}</p></div></div><div class="modal-box" style="margin-top:10px"><h4>Historique local · parts de voix publiées</h4><table class="hist-table"><thead><tr><th>Année</th>${parties.slice(0,5).map(([p])=>`<th>${p}</th>`).join('')}</tr></thead><tbody>${years.map(y=>`<tr><td>${y}</td>${parties.slice(0,5).map(([p])=>`<td>${c.history[y]?.status==='AVAILABLE'?pct(c.history[y].vote_share[p],1):'UNKNOWN'}</td>`).join('')}</tr>`).join('')}</tbody></table></div><div class="unknowns" style="margin-top:12px"><span>2026 candidate roster: UNKNOWN</span><span>Head candidate: UNKNOWN</span><span>Party switch: UNKNOWN</span></div></div>`;
  document.body.appendChild(modal);modal.querySelector('.modal-close').onclick=()=>modal.remove();modal.onclick=e=>{if(e.target===modal)modal.remove()};
}
function renderParties(){
  const ps=D.parties.parties;
  $('#partyTabs').innerHTML=ps.map((p,i)=>`<button data-party="${p.party}" class="${i===0?'active':''}">${p.party}</button>`).join('');
  $$('#partyTabs button').forEach(b=>b.onclick=()=>{$$('#partyTabs button').forEach(x=>x.classList.remove('active'));b.classList.add('active');renderParty(b.dataset.party)});
  renderParty(ps[0].party);
}
function renderParty(code){
  const p=D.parties.parties.find(x=>x.party===code), n=p.national_seats||{};
  const hs=p.historical_local_vote_share||{};
  $('#partyDetail').innerHTML=`<div class="party-detail"><article class="party-hero"><div class="eyebrow dark">National · ${code}</div><h3>${code}</h3><div class="big">${fmt(n.mean,1)}</div><p>sièges attendus · 95% ${fmt(n.q025,0)} — ${fmt(n.q975,0)}</p><h4>Empreinte électorale locale</h4>${['2011','2016','2021'].map(y=>`<div class="history-line"><b>${y}</b><i><b style="width:${clamp((hs[y]||0)*250,1,100)}%"></b></i><span>${pct(hs[y],1)}</span></div>`).join('')}<div class="notice">P(finir premier) n'est pas reconstruit: cette probabilité n'est pas publiée dans F−1.</div></article><article class="party-list-card"><h3>Territoires structurellement forts</h3><div class="territory-list">${p.strongest_territories.slice(0,6).map(t=>`<div><b>${esc(t.name)}</b><span>${esc(t.region)} · E[sièges] ${fmt(t.expected_seats,2)} · P≥1 ${pct(t.p_ge_1)}</span></div>`).join('')}</div><h3>Où l'incertitude est la plus forte</h3><div class="territory-list">${p.most_uncertain_territories.slice(0,6).map(t=>`<div><b>${esc(t.name)}</b><span>${esc(t.region)} · entropie ${fmt(t.entropy_bits,2)} bits</span></div>`).join('')}</div></article></div>`;
}
function renderEvidence(){
  const e=D.evidence,w=e.wave1||{},c=e.collection||{};
  $('#evidenceSummary').innerHTML=[[w.documents_acquired,'documents acquis'],[w.documents_blocked,'accès bloqués'],[w.b2_claim_records_created,'claims B2 admis'],[c.evidence_records??0,'preuves structurées']].map(([v,l])=>`<div class="evidence-kpi"><b>${v??'—'}</b><span>${l}</span></div>`).join('');
  $('#evidenceEvents').innerHTML=(e.events||[]).length?e.events.map(x=>`<article class="event"><div class="source">${esc(x.source)}<br>${esc(x.status)}</div><div><h3>${esc(x.summary)}</h3><p>${esc(x.reason)}</p></div><div class="impact">FORECAST IMPACT<br><b>${esc(x.forecast_impact)}</b></div></article>`).join(''):`<div class="notice">Aucun événement produit n'est encore admissible comme changement de forecast.</div>`;
  $('#sourceGrid').innerHTML=(e.sources||[]).map(x=>`<div class="source"><b>${esc(x.source)}</b><small>${Object.entries(x.states).map(([k,v])=>`${k}: ${v}`).join(' · ')}</small></div>`).join('');
}
function renderTimeline(){
  const s=D.snapshot,m=D.methodology;
  $('#timeline').innerHTML=s.timeline.map(x=>`<div class="time-node ${x.status}"><span>${esc(x.status)}</span><strong>${esc(x.id)}</strong><span>${x.created_at?new Date(x.created_at).toLocaleString('fr-FR'):x.class||'future'}</span></div>`).join('');
  $('#hashShort').textContent=`${s.forecast_sha256.slice(0,16)}…`;
  $('#calibration').textContent=(m.model.calibration_status||'—').replaceAll('_',' ');
  $('#limitations').innerHTML=(s.known_limitations||[]).map(x=>`<li>${esc(x)}</li>`).join('');
}
['input','change'].forEach(ev=>document.addEventListener(ev,e=>{if(['constSearch','regionFilter','uncertaintyFilter'].includes(e.target.id)){visibleCount=12;renderConstituencies()}}));
$('#showMore').onclick=()=>{visibleCount+=12;renderConstituencies()};
boot();
