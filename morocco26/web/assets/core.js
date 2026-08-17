const $ = s => document.querySelector(s);
const $$ = s => [...document.querySelectorAll(s)];
const fmt = (v, d = 1) => v == null ? '—' : Number(v).toLocaleString('fr-FR', {minimumFractionDigits:d, maximumFractionDigits:d});
const pct = (v, d = 0) => v == null ? '—' : `${fmt(Number(v) * 100, d)} %`;
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const clamp = (v,a,b) => Math.max(a, Math.min(b, v));

const PARTIES = {
  RNI:'Rassemblement National des Indépendants',
  PAM:'Parti Authenticité et Modernité',
  PI:"Parti de l’Istiqlal",
  PJD:'Parti de la Justice et du Développement',
  MP:'Mouvement Populaire',
  UC:'Union Constitutionnelle',
  USFP:'Union Socialiste des Forces Populaires',
  PPS:'Parti du Progrès et du Socialisme',
  OTHER:'Autres listes'
};
const SOURCE_NAMES = {
  T0_CHAMBRE_REPRESENTANTS:'Chambre des représentants',
  T0_CONSTITUTIONAL_COURT:'Cour constitutionnelle',
  T0_LISTES_ELECTORALES:'Listes électorales',
  T0_MAROC_MA_ELECTIONS:'Portail officiel du Royaume du Maroc',
  T0_SGG_LEGISLATION:'Secrétariat général du Gouvernement',
  T1_ISTIQLAL_OFFICIAL:"Parti de l’Istiqlal",
  T1_MP_OFFICIAL:'Mouvement Populaire',
  T1_PAM_OFFICIAL:'Parti Authenticité et Modernité',
  T1_PJD_OFFICIAL:'Parti de la Justice et du Développement',
  T1_PPS_OFFICIAL:'Parti du Progrès et du Socialisme',
  T1_RNI_OFFICIAL:'Rassemblement National des Indépendants',
  T1_UC_OFFICIAL:'Union Constitutionnelle',
  T1_USFP_OFFICIAL:'Union Socialiste des Forces Populaires',
  T2_MEDIAS24:'Médias24',
  HF_CHAMBER_MEMBERS_MULTIYEAR:'Archives de la Chambre des représentants'
};
const U_LABEL = {HIGH:'Forte', MEDIUM:'Moyenne', LOW:'Faible'};
const U_COLOR = {HIGH:'#ffa24d', MEDIUM:'#b25a1e', LOW:'#704520'};

const CARTOGRAM_CELLS = {
  'Tanger-Tétouan-Al Hoceïma': [[5,0],[6,0],[7,0],[8,0],[5,1],[6,1],[7,1],[8,1]],
  'Oriental': [[10,1],[11,1],[10,2],[11,2],[10,3],[11,3],[10,4],[11,4]],
  'Rabat-Salé-Kénitra': [[2,2],[3,2],[4,2],[5,2],[2,3],[3,3],[4,3],[5,3],[3,4],[4,4],[5,4]],
  'Fès-Meknès': [[6,2],[7,2],[8,2],[9,2],[6,3],[7,3],[8,3],[9,3],[7,4],[8,4],[9,4]],
  'Casablanca-Settat': [[1,5],[2,5],[3,5],[4,5],[5,5],[1,6],[2,6],[3,6],[4,6],[5,6],[2,7],[3,7],[4,7],[5,7],[3,8],[4,8]],
  'Béni Mellal-Khénifra': [[6,5],[7,5],[8,5],[6,6],[7,6],[8,6]],
  'Drâa-Tafilalet': [[9,5],[10,5],[9,6],[10,6],[9,7]],
  'Marrakech-Safi': [[2,9],[3,9],[4,9],[5,9],[2,10],[3,10],[4,10],[5,10],[3,11],[4,11]],
  'Souss-Massa': [[3,12],[4,12],[5,12],[3,13],[4,13],[5,13],[4,14]],
  'Guelmim-Oued Noun': [[3,15],[4,15],[3,16],[4,16]],
  'Laâyoune-Sakia El Hamra': [[2,17],[3,17],[2,18],[3,18]],
  'Dakhla-Oued Eddahab': [[1,19],[2,19]]
};

const NAV = [
  ['overview','Synthèse',''],
  ['territories','Carte territoriale','92'],
  ['parties','Partis','9'],
  ['signals','Veille 2026',''],
  ['methodology','Méthode',''],
  ['history','Historique','']
];
let D = {};
let selectedTerritory = null;
let selectedParty = null;
let territoryFilters = {query:'', region:'', uncertainty:''};

async function load(name){
  const base = window.ATLAS_DATA_BASE || '/data/';
  const r = await fetch(`${base}${name}`, {cache:'no-store'});
  if(!r.ok) throw new Error(`Données indisponibles (${r.status})`);
  return r.json();
}

async function boot(){
  try{
    const [snapshot,national,constituencies,parties,evidence,methodology] = await Promise.all([
      load('current_snapshot.json'), load('national_projection.json'), load('constituency_cards.json'),
      load('party_cards.json'), load('evidence_index.json'), load('public_methodology.json')
    ]);
    D = {snapshot,national,constituencies,parties,evidence,methodology};
    selectedTerritory = [...constituencies.constituencies].sort((a,b)=>b.uncertainty.value-a.uncertainty.value)[0]?.constituency_id;
    selectedParty = national.parties[0]?.party || 'RNI';
    initNavigation();
    renderHeader();
    renderOverview();
    initTerritories();
    renderTerritories();
    renderParties();
    renderSignals();
    renderHistory();
    renderMethodology();
    window.addEventListener('scroll',()=>document.body.classList.toggle('compact',window.scrollY>140),{passive:true});
  }catch(e){
    $('#fatal').hidden = false;
    $('#fatal').textContent = `Atlas 395 ne peut pas charger les données de cette version : ${e.message}`;
    console.error(e);
  }
}

function dateFr(value, withTime=false){
  if(!value) return '—';
  const d = new Date(value);
  return d.toLocaleDateString('fr-FR', withTime ? {day:'2-digit',month:'long',year:'numeric',hour:'2-digit',minute:'2-digit'} : {day:'2-digit',month:'long',year:'numeric'});
}

function initNavigation(){
  $('#nav').innerHTML = NAV.map(([id,label,badge],i)=>`<button id="tab-${id}" role="tab" aria-selected="${i===0}" data-view="${id}">${label}${badge?`<i>${badge}</i>`:''}</button>`).join('');
  $$('#nav button').forEach(b=>b.onclick=()=>showView(b.dataset.view));
}
function showView(id){
  $$('#nav button').forEach(b=>b.setAttribute('aria-selected',String(b.dataset.view===id)));
  $$('.view').forEach(v=>v.classList.toggle('active',v.id===`view-${id}`));
  window.scrollTo({top:0,behavior:'smooth'});
}

function renderHeader(){
  const s = D.snapshot;
  $('#meta-asof').textContent = dateFr(s.data_cutoff || s.created_at);
  $('#edition-date').textContent = dateFr(s.created_at);
  const noChange = D.evidence.forecast_change === 'NONE';
  $('#status-detail').textContent = noChange
    ? 'Projection territoriale de référence · veille 2026 active · nouvelles informations distinguées de leur éventuel impact électoral.'
    : 'Une version enrichie de la projection est disponible.';
  $('#kpis').innerHTML = [
    ['395','sièges au total','hi'],['305','sièges locaux',''],['90','sièges régionaux',''],
    [Number(s.draws||0).toLocaleString('fr-FR'),'scénarios simulés',''],['92','circonscriptions locales',''],['12','circonscriptions régionales','']
  ].map(([v,l,c])=>`<div class="kpi ${c}"><b class="big">${v}</b><span>${l}</span></div>`).join('');
}

function renderMethodology(){
  if(!$('#method-version')) return;
  const m = D.methodology?.public_methodology || {};
  const draws = Number(m.draws || D.snapshot?.draws || 0);
  $('#method-version').textContent = m.reference_status || 'Enregistrée';
  $('#method-version-date').textContent = m.reference_date ? `depuis le ${dateFr(m.reference_date)}` : 'avant le scrutin';
  $('#method-draws').textContent = draws ? draws.toLocaleString('fr-FR') : '50 000';
  $('#method-seats').textContent = Number(m.total_seats || 395).toLocaleString('fr-FR');
  $('#method-manual-bonus').textContent = String(m.manual_party_bonus || 0);
}
