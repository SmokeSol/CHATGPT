/* ══════════════════════════════════════════════════════════════════════════
   ATLAS // SOCIÉTÉ ARTIFICIELLE
   Aucune règle en ligne n'est écrite dans le balisage : toute mise en forme
   dynamique passe par le CSSOM (el.style.prop), jamais par setAttribute('style').
   Aucune requête sortante. Aucun résultat électoral n'est produit.
   ══════════════════════════════════════════════════════════════════════════ */
'use strict';

/* ── vocabulaire ─────────────────────────────────────────────────────────── */

var FAM = {
  prior_vote_inertia: 'ancrage', turnout_habit: 'ancrage',
  personal_economic_conditions: 'vie', employment_and_income: 'vie',
  social_protection_and_public_services: 'vie',
  policy_program_fit: 'offre', governance_and_institutions: 'offre',
  territorial_rural_fit: 'offre',
  government_reward_punishment: 'jugement', local_candidate_context: 'jugement',
  other_verified_context: 'jugement'
};
var FAMCOL = { ancrage: '#7f8ea6', vie: '#e9701f', offre: '#6e8bff', jugement: '#199e70' };
var FACT_COL = {
  prior_vote_inertia: '#8b99b0', turnout_habit: '#5d6b83',
  personal_economic_conditions: '#ffc98a', employment_and_income: '#ffa24d',
  social_protection_and_public_services: '#e9701f',
  policy_program_fit: '#9db0ff', governance_and_institutions: '#6e8bff',
  territorial_rural_fit: '#4a63cc',
  government_reward_punishment: '#2fa855', local_candidate_context: '#d55181',
  other_verified_context: '#4b5768'
};
var FACT_FR = {
  prior_vote_inertia: 'Ancrage territorial et fidélité',
  turnout_habit: 'Habitude d’aller voter',
  personal_economic_conditions: 'Le budget du foyer',
  employment_and_income: 'L’emploi et les revenus',
  social_protection_and_public_services: 'Santé, école, protection sociale',
  policy_program_fit: 'Le reste des engagements',
  governance_and_institutions: 'Confiance et bonne gestion',
  territorial_rural_fit: 'L’attention portée aux territoires',
  government_reward_punishment: 'Le jugement sur le bilan sortant',
  local_candidate_context: 'La figure locale',
  other_verified_context: 'Le reste du contexte vérifié'
};
var FACT_SHORT = {
  prior_vote_inertia: 'Ancrage', turnout_habit: 'Habitude',
  personal_economic_conditions: 'Budget du foyer', employment_and_income: 'Emploi et revenus',
  social_protection_and_public_services: 'Santé et école',
  policy_program_fit: 'Autres engagements', governance_and_institutions: 'Confiance',
  territorial_rural_fit: 'Territoires', government_reward_punishment: 'Bilan sortant',
  local_candidate_context: 'Figure locale', other_verified_context: 'Autre contexte'
};
var CODE_FR = {
  PRIOR_VOTE_INERTIA: 'reste sur son choix précédent',
  PRIOR_ABSTENTION_INERTIA: 'habitué à ne pas voter',
  TURNOUT_HABIT: 'son habitude de participation pèse',
  ECONOMIC_SELF_INTEREST: 'intérêt matériel direct',
  EMPLOYMENT_INCOME_FIT: 'attend des réponses sur l’emploi et les revenus',
  SOCIAL_PROTECTION_PUBLIC_SERVICES_FIT: 'attend des réponses sur la santé, l’école, la protection sociale',
  POLICY_PROGRAM_FIT: 'sensible au reste des engagements',
  GOVERNANCE_INSTITUTIONAL_FIT: 'exige de la bonne gestion',
  TERRITORIAL_RURAL_FIT: 'attentif à ce qui est promis à son territoire',
  GOVERNMENT_REWARD: 'récompense le bilan sortant',
  GOVERNMENT_PUNISHMENT: 'sanctionne le bilan sortant',
  LOCAL_CANDIDATE_STRENGTH: 'reconnaît une figure locale établie',
  LOCAL_CANDIDATE_WEAKNESS: 'figure locale affaiblie',
  ATTITUDE_POSTERIOR: 'son état d’esprit déclaré pèse lourd',
  OTHER_VERIFIED_CONTEXT: 'd’autres éléments vérifiés entrent en compte',
  NO_DIRECTIONAL_EVIDENCE: 'aucun élément ne tranche'
};
var CODE_TONE = {
  GOVERNMENT_PUNISHMENT: 'hot', LOCAL_CANDIDATE_WEAKNESS: 'hot',
  GOVERNMENT_REWARD: 'cool', LOCAL_CANDIDATE_STRENGTH: 'cool',
  PRIOR_VOTE_INERTIA: 'blue', PRIOR_ABSTENTION_INERTIA: 'blue'
};

var DIM_FR = {
  age: 'Âge', sexe: 'Sexe', milieu: 'Milieu', etudes: 'Études',
  activite: 'Situation d’activité', niveau_vie: 'Niveau de vie',
  comportement: 'Comportement précédent', confiance: 'Confiance dans les institutions',
  bilan: 'Jugement sur le bilan', foyer: 'Composition du foyer', secteur: 'Secteur d’activité'
};
var VAL_FR = {
  '18_24': '18–24 ans', '25_34': '25–34 ans', '35_44': '35–44 ans',
  '45_59': '45–59 ans', '60_PLUS': '60 ans et plus',
  F: 'Femmes', M: 'Hommes',
  URBAN: 'Urbain', RURAL: 'Rural', MISSING: 'Non renseigné',
  aucun: 'Sans niveau d’études', primaire: 'Primaire', college: 'Collège',
  lycee: 'Lycée', superieur: 'Supérieur',
  ACTIVE_EMPLOYED: 'En emploi', UNEMPLOYED: 'Au chômage', INACTIVE: 'Hors emploi',
  Q1: 'Niveau de vie 1 — le plus modeste', Q2: 'Niveau de vie 2', Q3: 'Niveau de vie 3',
  Q4: 'Niveau de vie 4', Q5: 'Niveau de vie 5 — le plus aisé',
  vote: 'A voté la fois précédente', abstention: 'S’est abstenu la fois précédente',
  bas: 'Faible', median: 'Moyenne', haut: 'Élevée',
  nucleaire: 'Couple avec ou sans enfants', elargi: 'Foyer élargi',
  monoparental: 'Foyer monoparental', seul: 'Personne seule', autre: 'Autre foyer',
  agriculture: 'Agriculture et pêche', industrie_btp: 'Industrie et bâtiment',
  commerce: 'Commerce', services: 'Services et fonction publique',
  non_renseigne: 'Sans activité déclarée'
};
var VAL_FR_BILAN = { bas: 'Jugement sévère', median: 'Jugement mitigé', haut: 'Jugement favorable' };
var BLOC_FR = ['Coalition sortante', 'Opposition', 'Ensemble résiduel'];
var BLOC_COL = ['#e9701f', '#6e8bff', '#5d6b83'];
var RAMP = ['#3a2a30', '#7c4520', '#b25a1e', '#e9701f', '#ffa24d', '#ffc98a'];

/* ── outils ──────────────────────────────────────────────────────────────── */

function $(s) { return document.querySelector(s); }
function el(tag, cls, txt) {
  var n = document.createElement(tag);
  if (cls) n.className = cls;
  if (txt !== undefined && txt !== null) n.textContent = txt;
  return n;
}
function nf(v, d) {
  return Number(v).toLocaleString('fr-FR', { minimumFractionDigits: d || 0, maximumFractionDigits: d || 0 });
}
function pct(v, d) { return nf(100 * v, d === undefined ? 1 : d) + ' %'; }
function valFr(dim, k) { return dim === 'bilan' ? (VAL_FR_BILAN[k] || k) : (VAL_FR[k] || k); }
function partyName(q) { return (window.ATLAS_PARTY_NAMES && window.ATLAS_PARTY_NAMES[q]) || ('Liste ' + q.replace('Q_', '')); }
function clip(x, a, b) { return x < a ? a : (x > b ? b : x); }
function sigmoid(x) { return x >= 0 ? 1 / (1 + Math.exp(-x)) : Math.exp(x) / (1 + Math.exp(x)); }
function logit(p) { p = clip(p, 1e-6, 1 - 1e-6); return Math.log(p / (1 - p)); }
function std(a) {
  if (a.length < 2) return 0;
  var m = 0, i;
  for (i = 0; i < a.length; i++) m += a[i];
  m /= a.length;
  var s = 0;
  for (i = 0; i < a.length; i++) s += (a[i] - m) * (a[i] - m);
  return Math.sqrt(s / a.length);
}

/** Barre horizontale. La largeur passe par le CSSOM, jamais par un attribut style. */
function barRow(host, label, value, colour, text, wide) {
  var r = el('div', 'bar' + (wide ? ' wide' : ''));
  var l = el('span', 'lab', label);
  l.title = label;
  var t = el('div', 'track');
  var f = el('i', 'fill');
  f.style.background = colour;
  t.appendChild(f);
  r.appendChild(l); r.appendChild(t); r.appendChild(el('span', 'val', text));
  host.appendChild(r);
  requestAnimationFrame(function () { f.style.width = clip(value, 0, 1) * 100 + '%'; });
  return f;
}
function clear(n) { while (n.firstChild) n.removeChild(n.firstChild); }
function rampColour(v) {
  var i = clip(Math.floor(v * (RAMP.length - 1)), 0, RAMP.length - 2);
  return RAMP[i + 1];
}

/* ── état ────────────────────────────────────────────────────────────────── */

var S = null, P = null, SIM = null, F = null;

/* Les données arrivent soit depuis /data (déploiement statique), soit depuis des blocs
   JSON embarqués (page autonome, aucune requête réseau). */
function loadData() {
  var inline = document.getElementById('d-societe');
  if (inline) {
    return Promise.resolve([
      JSON.parse(inline.textContent),
      JSON.parse(document.getElementById('d-portraits').textContent),
      JSON.parse(document.getElementById('d-simulateur').textContent)
    ]);
  }
  return Promise.all([
    fetch('data/societe.json').then(function (r) { return r.json(); }),
    fetch('data/portraits.json').then(function (r) { return r.json(); }),
    fetch('data/simulateur.json').then(function (r) { return r.json(); })
  ]);
}

loadData().then(function (res) {
  S = res[0]; P = res[1]; SIM = res[2]; F = S.meta.facteurs;
  boot();
}).catch(function (e) {
  var b = $('#kpis');
  if (b) b.appendChild(el('p', 'note', 'Les données de la société n’ont pas pu être chargées. ' + e));
});

function boot() {
  header(); heroField(); kpis(); steps(); simulator();
  forces(); sanction(); bascule(); ecoute(); portraits(); rules();
  reveal(); spy();
}

/* ── en-tête & indicateurs ───────────────────────────────────────────────── */

function header() {
  var g = S.global['*'];
  var mr=$('#m-rows'), mt=$('#m-terr'); if(mr)mr.textContent=nf(S.meta.rows); if(mt)mt.textContent='92';
  var hf=$('#hero-fid'); if(hf)hf.textContent='0 contribution';
  var hp=$('#hero-part'); if(hp)hp.textContent='0';
  var hs=$('#hero-sanc'); if(hs)hs.textContent='0';
  var fh=$('#foot-hash'); if(fh)fh.textContent='Société artificielle du Maroc · 92 circonscriptions · horizon 2026';
}

function kpis() {
  var K = [
    ['23 552', 'citoyens-types dans chaque élection'],
    ['92', 'circonscriptions marocaines'],
    ['8 + 1', 'grands partis et ensemble des autres listes'],
    ['2016', 'premier terrain d’essai historique'],
    ['2021', 'deuxième terrain d’essai historique'],
    ['2026', 'le rendez-vous prospectif']
  ];
  var host = $('#kpis');
  clear(host);
  K.forEach(function (k) {
    var d = el('div', 'kpi');
    d.appendChild(el('b', 'num', k[0]));
    d.appendChild(el('span', null, k[1]));
    host.appendChild(d);
  });
}

/* ── champ d'agents (héros) ──────────────────────────────────────────────── */

function heroField() {
  var c = $('#field'), ctx = c.getContext('2d');
  var reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var N = window.innerWidth < 700 ? 900 : 2200;
  var pts = [], i, dpr, W, H;
  var share = S.global['*'].part;

  function size() {
    dpr = Math.min(2, window.devicePixelRatio || 1);
    W = c.clientWidth; H = c.clientHeight;
    c.width = Math.max(1, Math.round(W * dpr));
    c.height = Math.max(1, Math.round(H * dpr));
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    layout();
  }
  function layout() {
    var cols = Math.ceil(Math.sqrt(N * W / Math.max(1, H)));
    var rows = Math.ceil(N / cols);
    var gx = W / (cols + 1), gy = H / (rows + 1);
    for (i = 0; i < pts.length; i++) {
      var r = Math.floor(i / cols), q = i % cols;
      pts[i].tx = gx * (q + 1) + (((r % 2) ? 1 : -1) * gx * 0.18);
      pts[i].ty = gy * (r + 1);
    }
  }
  for (i = 0; i < N; i++) {
    pts.push({
      x: Math.random(), y: Math.random(), tx: 0, ty: 0,
      v: (i / N) < share, ph: Math.random() * 6.28,
      s: 0.7 + Math.random() * 1.5
    });
  }
  size();
  for (i = 0; i < pts.length; i++) { pts[i].x = Math.random() * W; pts[i].y = Math.random() * H; }
  window.addEventListener('resize', size);

  var t0 = performance.now();
  function frame(now) {
    var t = (now - t0) / 1000;
    ctx.clearRect(0, 0, W, H);
    for (i = 0; i < pts.length; i++) {
      var p = pts[i];
      var k = reduced ? 1 : clip((t - 0.15) * 0.55, 0, 1);
      k = 1 - Math.pow(1 - k, 3);
      var wob = reduced ? 0 : Math.sin(t * 0.7 + p.ph) * 2.4;
      var x = p.x + (p.tx - p.x) * k + wob;
      var y = p.y + (p.ty - p.y) * k + Math.cos(t * 0.55 + p.ph) * (reduced ? 0 : 1.8);
      ctx.fillStyle = p.v ? 'rgba(255,162,77,.62)' : 'rgba(110,139,255,.34)';
      ctx.fillRect(x, y, p.s, p.s);
    }
    if (!reduced && t < 40) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

/* ── les cinq gestes ─────────────────────────────────────────────────────── */

function steps() {
  var g = S.global['*'];
  var ST = [
    ['Il lit sa propre situation', 'Âge, foyer, travail, logement, budget, accès à l’eau et à la route, et ce qu’il pense de sa vie et des institutions. Rien d’autre.'],
    ['Il traduit cela en attentes', 'Dix-huit sujets, du logement à la santé, pondérés par sa situation puis par les tensions du pays. Un chômeur ne pèse pas l’emploi comme un retraité.'],
    ['Il confronte à ce qu’on lui propose', 'Neuf offres locales, décrites en priorités grossières. Une priorité absente ne veut pas dire une opposition : elle veut dire « non établie ».'],
    ['Il juge le bilan sortant', 'Récompense ou sanction selon son propre jugement, jamais par automatisme. ' + pct(g.sanction, 0) + ' sanctionnent, ' + pct(g.recompense, 0) + ' récompensent.'],
    ['Il choisit — sans certitude absolue', 'Il peut voter, s’abstenir, rester fidèle ou changer. La société ne force jamais une réponse unique quand le choix reste ouvert.']
  ];
  var host = $('#steps');
  clear(host);
  ST.forEach(function (s, i) {
    var d = el('div', 'step');
    d.appendChild(el('div', 'n num', String(i + 1)));
    d.appendChild(el('h3', null, s[0]));
    d.appendChild(el('p', null, s[1]));
    host.appendChild(d);
  });
  var n = $('#mec-note');
  clear(n);
  n.appendChild(el('b', null, 'Une règle simple : '));
  n.appendChild(document.createTextNode(
    'on ne complète jamais un citoyen avec ce que l’on ne sait pas de lui. Sa religion, son origine, sa langue ou une proximité partisane supposée ne sont jamais inventées. Chaque décision part uniquement de la fiche du citoyen et de son environnement politique.'));
}

/* ══ DÉMONSTRATEUR — portage fidèle du moteur ═══════════════════════════════ */

var AXES, SK, CTL = {
  age: '25_34', mil: 'URBAN', qv: 0.6, act: 'ACTIVE_EMPLOYED',
  conf: 0.38, bil: 0.34, prior: 'Q_03'
};

function sigOf() {
  var key = CTL.age + '|' + CTL.mil + '|' + CTL.qv.toFixed(1) + '|' + CTL.act;
  var arr = SIM.base[key], s = {}, i;
  for (i = 0; i < SK.length; i++) s[SK[i]] = arr[i];
  applyConf(s, CTL.conf);
  applyBil(s, CTL.bil);
  return s;
}
function applyConf(s, c) {
  s.trust_parl = 0.16 + 0.50 * c;
  s.trust_loc = 0.18 + 0.46 * c;
  s.trust = 0.5 * (s.trust_parl + s.trust_loc);
  s.resp_loc = 0.05 + 0.42 * c;
  s.corr_loc = 0.62 - 0.34 * c;
  s.corr_mp = 0.65 - 0.35 * c;
  s.corruption = 0.5 * (s.corr_loc + s.corr_mp);
}
function applyBil(s, b) {
  s.gov_econ = 0.21 + 0.37 * b;
  s.gov_pov = 0.15 + 0.31 * b;
  s.gov_anti = 0.14 + 0.44 * b;
  s.dem_sat = 0.37 + 0.46 * b;
}

function axisNeeds(s) {
  var n = {};
  n.employment = clip(0.16 + 0.42 * s.unemployed + 0.26 * s.hh_unemp + 0.22 * s.young +
    0.16 * s.famhelp + 0.20 * (1 - s.ses) + 0.28 * (0.55 - s.econ_cond), 0.05, 1);
  n.private_investment_sme = clip(0.12 + 0.38 * s.selfemp + 0.20 * s.commerce +
    0.10 * s.employed + 0.10 * s.ses, 0.05, 1);
  n.industrial_competitiveness = clip(0.12 + 0.34 * s.indus + 0.20 * s.constr +
    0.14 * s.privemp + 0.10 * s.ses, 0.05, 1);
  n.fiscal_relief = clip(0.20 + 0.44 * clip((s.cash_dep - 0.12) / 0.42, 0, 1) * s.c_cash +
    0.24 * clip((s.food_share - 0.25) / 0.45, 0, 1) + 0.16 * clip(s.credit_share * 3, 0, 1) +
    0.14 * (1 - s.econ_cond) * s.c_econ, 0.05, 1);
  n.economic_sovereignty = clip(0.16 + 0.16 * s.agri + 0.16 * s.indus + 0.14 * s.edu_rank +
    0.12 * s.discuss * s.c_disc, 0.05, 1);
  n.social_protection = clip(0.20 + 0.34 * s.hardship + 0.22 * s.dep_ratio + 0.20 * s.elderly +
    0.18 * s.poverty + 0.14 * s.vuln + 0.16 * clip((s.food_dep - 0.03) / 0.24, 0, 1) * s.c_food +
    0.12 * s.inactive, 0.05, 1);
  n.health = clip(0.20 + 0.30 * clip(s.med_share / 0.16, 0, 1) + 0.22 * s.elderly +
    0.16 * s.children + 0.14 * clip((s.age - 35) / 45, 0, 1) + 0.14 * s.hardship, 0.05, 1);
  n.education = clip(0.16 + 0.34 * s.students + 0.24 * s.children +
    0.22 * clip(s.edu_share / 0.10, 0, 1) + 0.16 * s.edu_rank + 0.12 * s.young, 0.05, 1);
  n.housing = clip(0.12 + 0.32 * s.crowd + 0.28 * s.renter + 0.22 * s.slum +
    0.16 * clip((s.rent_share - 0.08) / 0.30, 0, 1) + 0.14 * s.young, 0.05, 1);
  n.governance_rule_of_law = clip(0.18 + 0.40 * clip((s.corruption - 0.30) / 0.32, 0, 1) * s.c_cloc +
    0.26 * clip((0.45 - s.trust) / 0.30, 0, 1) * s.c_tparl + 0.18 * s.discuss * s.c_disc +
    0.14 * s.edu_rank, 0.05, 1);
  n.civil_liberties = clip(0.12 + 0.26 * clip((s.dem_sup - 0.55) / 0.45, 0, 1) * s.c_dsup +
    0.20 * s.discuss * s.c_disc + 0.18 * s.edu_rank + 0.12 * s.young, 0.05, 1);
  n.decentralization = clip(0.14 + 0.30 * clip((0.30 - s.resp_loc) / 0.28, 0, 1) * s.c_resp +
    0.24 * s.rural * s.rural_known + 0.18 * clip((0.45 - s.trust_loc) / 0.28, 0, 1) * s.c_tloc, 0.05, 1);
  n.rural_territorial_equity = clip(0.10 + 0.40 * s.rural * s.rural_known +
    0.20 * s.road_far * s.road_known + 0.18 * s.water_far * s.water_known +
    0.16 * (1 - s.services) + 0.16 * s.agri + 0.10 * s.no_sewer, 0.05, 1);
  n.environment_transition = clip(0.12 + 0.28 * clip((s.water_dep - 0.02) / 0.34, 0, 1) * s.c_water +
    0.20 * s.agri + 0.16 * s.water_unpiped + 0.14 * s.biomass_cook + 0.12 * s.edu_rank, 0.05, 1);
  n.digital_transition = clip(0.10 + 0.32 * s.net_use * s.c_net + 0.20 * s.internet +
    0.16 * s.computer + 0.20 * s.young + 0.14 * s.edu_rank, 0.05, 1);
  n.public_state_role = clip(0.14 + 0.26 * s.hardship + 0.22 * s.pubemp + 0.16 * s.pubsec +
    0.16 * s.inactive + 0.14 * (1 - s.ses), 0.05, 1);
  n.gender_equality = clip(0.12 + 0.22 * s.female + 0.16 * s.edu_rank +
    0.12 * s.young * s.female + 0.10 * s.discuss * s.c_disc, 0.05, 1);
  n.culture = clip(0.08 + 0.22 * clip(s.cult_share / 0.12, 0, 1) + 0.18 * s.edu_rank +
    0.14 * clip(s.leisure_share / 0.06, 0, 1) + 0.10 * s.young, 0.05, 1);
  return n;
}

function decide(s, prior) {
  var C = SIM.coef, X = SIM.ctx, Q = X.parties, nQ = Q.length, i, q, a;
  var needs = axisNeeds(s), w = [], bucketOf = [];
  for (a = 0; a < AXES.length; a++) {
    w.push(needs[AXES[a]] * X.sal[a]);
    bucketOf.push(SIM.bucket[AXES[a]]);
  }
  var fit = [], bcomp = [], unk = [];
  for (i = 0; i < nQ; i++) {
    var lv = X.levels[Q[i]], tw = 0, tot = 0, nk = 0, bb = {};
    for (a = 0; a < AXES.length; a++) {
      if (lv[a] === null) continue;
      nk++; tw += w[a]; tot += w[a] * lv[a];
      bb[bucketOf[a]] = (bb[bucketOf[a]] || 0) + w[a] * lv[a];
    }
    unk.push(1 - nk / AXES.length);
    if (tw <= 0) { fit.push(null); bcomp.push(null); continue; }
    fit.push(tot / tw);
    var bo = {};
    for (var k in bb) bo[k] = bb[k] / tw;
    bcomp.push(bo);
  }
  var kf = fit.filter(function (x) { return x !== null; });
  var nfit = kf.length ? kf.reduce(function (p, c) { return p + c; }, 0) / kf.length : 0;

  var govRaw = 0.38 * s.gov_econ + 0.20 * s.gov_pov + 0.17 * s.gov_anti + 0.25 * s.trust_parl;
  var govConf = 0.38 * s.c_gecon + 0.20 * s.c_gpov + 0.17 * s.c_ganti + 0.25 * s.c_tparl;
  var govAdj = govRaw + 0.40 * (s.dem_sat - 0.50) * s.c_dsat +
    0.12 * (s.econ_cond - 0.55) * s.c_econ - 0.18 * (s.corruption - 0.44) * s.c_cloc;
  var gd = (govAdj - 0.50) * govConf;
  var locSal = 0.55 + 0.45 * clip((s.trust_loc - 0.18) / 0.42, 0, 1) * s.c_tloc;
  var voted = Q.indexOf(prior) >= 0;

  var cPrior = [], cFit = [], cGov = [], cLoc = [], cPv = [], u = [];
  for (i = 0; i < nQ; i++) {
    cPrior.push(X.logshare[i]);
    cFit.push(C.fit * ((fit[i] === null ? nfit : fit[i]) - nfit));
    cGov.push(X.gov[i] === 'INCUMBENT_COALITION' ? C.gov * gd :
      (X.gov[i] === 'OPPOSITION' ? -C.gov * 0.68 * gd : 0));
    cLoc.push(C.loc * locSal * X.loc[i]);
    cPv.push(voted && Q[i] === prior ? C.vote : 0);
    u.push(cPrior[i] + cFit[i] + cGov[i] + cLoc[i] + cPv[i]);
  }
  var temp = 1 + (typeof X.ncomp === 'number' ? 0.030 * X.ncomp : 0);
  var mx = Math.max.apply(null, u), z = 0, ex = [];
  for (i = 0; i < nQ; i++) { ex.push(Math.exp((u[i] - mx) / temp)); z += ex[i]; }
  var pr = [];
  for (i = 0; i < nQ; i++) pr.push((1 - C.eps) * (ex[i] / z) + C.eps / nQ);

  var lt = logit(X.prevturnout);
  var tHabit = voted ? 0.94 : -0.72; lt += tHabit;
  var AGEB = { '18_24': -0.34, '25_34': -0.11, '35_44': 0.06, '45_59': 0.21, '60_PLUS': 0.08 };
  var tAge = AGEB[CTL.age] || 0; lt += tAge;
  var tEdu = 0.30 * (s.edu_rank - 0.34) - 0.10 * s.illit; lt += tEdu;
  var tEng = 0.95 * (s.discuss - 0.38) * s.c_disc + 0.45 * (s.dem_sup - 0.83) * s.c_dsup +
    0.38 * (s.dem_sat - 0.66) * s.c_dsat; lt += tEng;
  var tInst = 0.72 * (s.trust - 0.385) * ((s.c_tparl + s.c_tloc) / 2) +
    0.46 * (s.resp_loc - 0.24) * s.c_resp - 0.34 * (s.corruption - 0.44) * s.c_cloc; lt += tInst;
  var tEcon = -0.30 * (s.cash_dep - 0.28) * s.c_cash - 0.11 * s.hardship + 0.10; lt += tEcon;
  var tAccess = -0.34 * s.road_far * s.road_known - 0.18 * s.water_far * s.water_known; lt += tAccess;
  var locMax = Math.max.apply(null, X.loc);
  var tLoc = 0.22 * locSal * locMax; lt += tLoc;
  var turnout = clip(sigmoid(lt), 0.02, 0.985);

  var m = {};
  for (i = 0; i < F.length; i++) m[F[i]] = 0;
  m.prior_vote_inertia = std(cPrior) + (voted ? std(cPv) : 0);
  m.government_reward_punishment = std(cGov);
  var lmSum = 0;
  for (i = 0; i < X.locmass.length; i++) lmSum += X.locmass[i];
  m.local_candidate_context = std(cLoc) + 0.03 * (lmSum / Math.max(1, X.locmass.length));
  var buckets = {};
  for (a = 0; a < AXES.length; a++) buckets[bucketOf[a]] = 1;
  for (var b in buckets) {
    var vals = [];
    for (i = 0; i < nQ; i++) vals.push(C.fit * (bcomp[i] ? (bcomp[i][b] || 0) : 0));
    m[b] += std(vals);
  }
  var uSum = 0;
  for (i = 0; i < unk.length; i++) uSum += unk[i];
  m.other_verified_context += 0.42 * (uSum / unk.length) + (typeof X.ncomp === 'number' ? 0.10 : 0);
  m.turnout_habit += 0.34 * Math.abs(tHabit) + 0.50 * Math.abs(tAge) +
    0.60 * Math.abs(tEng) + 0.28 * Math.abs(tEdu);
  m.governance_and_institutions += 0.45 * Math.abs(tInst);
  m.personal_economic_conditions += 0.45 * Math.abs(tEcon) + 0.10 * s.hardship;
  m.territorial_rural_fit += 0.40 * Math.abs(tAccess);
  m.local_candidate_context += 0.35 * Math.abs(tLoc);
  m.turnout_habit *= 0.70 + 0.60 * (4 * turnout * (1 - turnout));

  var directional = m.prior_vote_inertia + m.government_reward_punishment + m.local_candidate_context +
    m.employment_and_income + m.social_protection_and_public_services + m.policy_program_fit +
    m.governance_and_institutions + m.territorial_rural_fit + m.personal_economic_conditions;

  var FLOOR = 0.004, tot2 = 0, fi = {};
  for (i = 0; i < F.length; i++) { if (m[F[i]] < 0) m[F[i]] = 0; tot2 += m[F[i]]; }
  for (i = 0; i < F.length; i++) {
    fi[F[i]] = tot2 <= 0 ? 1 / F.length : (m[F[i]] / tot2) * (1 - FLOOR * F.length) + FLOOR;
  }

  var PROG = ['employment_and_income', 'social_protection_and_public_services', 'policy_program_fit',
    'governance_and_institutions', 'territorial_rural_fit', 'personal_economic_conditions'];
  var progRank = PROG.slice().sort(function (x, y) {
    return fi[y] / Math.pow(SIM.breadth[y], 0.75) - fi[x] / Math.pow(SIM.breadth[x], 0.75);
  });
  var locSpread = Math.max.apply(null, X.loc) - Math.min.apply(null, X.loc);
  var shift = Math.abs(turnout - X.prevturnout);
  var codes = [];
  function add(c) { if (c && codes.indexOf(c) < 0 && codes.length < 4) codes.push(c); }
  if (directional < 0.035) codes.push('NO_DIRECTIONAL_EVIDENCE');
  else {
    var FC = {
      employment_and_income: 'EMPLOYMENT_INCOME_FIT',
      social_protection_and_public_services: 'SOCIAL_PROTECTION_PUBLIC_SERVICES_FIT',
      policy_program_fit: 'POLICY_PROGRAM_FIT',
      governance_and_institutions: 'GOVERNANCE_INSTITUTIONAL_FIT',
      territorial_rural_fit: 'TERRITORIAL_RURAL_FIT',
      personal_economic_conditions: 'ECONOMIC_SELF_INTEREST'
    };
    if (fi[progRank[0]] >= 0.050) add(FC[progRank[0]]);
    if (fi.prior_vote_inertia >= 0.17) add(voted ? 'PRIOR_VOTE_INERTIA' : 'PRIOR_ABSTENTION_INERTIA');
    if (fi.government_reward_punishment >= 0.038 && Math.abs(gd) >= 0.008)
      add(gd > 0 ? 'GOVERNMENT_REWARD' : 'GOVERNMENT_PUNISHMENT');
    if (fi.turnout_habit >= 0.155 && shift >= 0.050) add('TURNOUT_HABIT');
    if (fi.local_candidate_context >= 0.085 && locSpread >= 0.05) {
      var best = Math.max.apply(null, X.loc), worst = Math.min.apply(null, X.loc);
      if (worst < -0.02 && Math.abs(worst) > best) add('LOCAL_CANDIDATE_WEAKNESS');
      else if (best > 0.02) add('LOCAL_CANDIDATE_STRENGTH');
    }
    if (s.c_att >= 0.62 && (fi.governance_and_institutions + fi.government_reward_punishment) >= 0.14)
      add('ATTITUDE_POSTERIOR');
    if (fi[progRank[1]] >= 0.085) add(FC[progRank[1]]);
    if (codes.length <= 2 && fi.other_verified_context >= 0.030) add('OTHER_VERIFIED_CONTEXT');
    if (!codes.length) add(FC[progRank[0]]);
  }

  var blocs = [0, 0, 0];
  for (i = 0; i < nQ; i++) {
    blocs[X.gov[i] === 'INCUMBENT_COALITION' ? 0 : (X.gov[i] === 'OPPOSITION' ? 1 : 2)] += pr[i];
  }
  return { part: turnout, pp: pr, fi: fi, codes: codes.slice(0, 4), gd: gd, blocs: blocs, voted: voted };
}

function selfCheck() {
  var worst = 0;
  SIM.ref.forEach(function (r) {
    var save = { age: CTL.age, mil: CTL.mil, qv: CTL.qv, act: CTL.act, conf: CTL.conf, bil: CTL.bil };
    CTL.age = r.ctl[0]; CTL.mil = r.ctl[1]; CTL.qv = r.ctl[2]; CTL.act = r.ctl[3];
    CTL.conf = r.ctl[4]; CTL.bil = r.ctl[5];
    var d = decide(sigOf(), r.ctl[6]);
    worst = Math.max(worst, Math.abs(d.part - r.part));
    for (var i = 0; i < r.pp.length; i++) worst = Math.max(worst, Math.abs(d.pp[i] - r.pp[i]));
    for (i = 0; i < r.fa.length; i++) worst = Math.max(worst, Math.abs(d.fi[F[i]] - r.fa[i]));
    if (d.codes.join('|') !== r.rc.join('|')) worst = Math.max(worst, 9);
    CTL.age = save.age; CTL.mil = save.mil; CTL.qv = save.qv; CTL.act = save.act;
    CTL.conf = save.conf; CTL.bil = save.bil;
  });
  if (worst > 1e-5) console.warn('[atlas] écart démonstrateur / moteur de référence :', worst);
  else console.info('[atlas] démonstrateur conforme au moteur de référence (écart max ' + worst.toExponential(2) + ')');
}

function simulator() {
  AXES = SIM.ctx.axes; SK = SIM.sigkeys;
  selfCheck();
  var host = $('#controls');
  clear(host);

  function segCtl(label, valueText, options, get, set) {
    var c = el('div', 'ctl');
    var top = el('div', 'ctl-top');
    var lb = el('label', null, label);
    var vv = el('span', 'v', valueText);
    top.appendChild(lb); top.appendChild(vv); c.appendChild(top);
    var g = el('div', 'seg');
    options.forEach(function (o) {
      var b = el('button', null, o[1]);
      b.type = 'button';
      b.setAttribute('aria-pressed', String(get() === o[0]));
      b.addEventListener('click', function () { set(o[0]); render(); });
      g.appendChild(b);
    });
    c.appendChild(g); host.appendChild(c);
  }
  function rangeCtl(id, label, get, set, fmt) {
    var c = el('div', 'ctl');
    var top = el('div', 'ctl-top');
    var lb = el('label', null, label); lb.htmlFor = id;
    var vv = el('span', 'v', fmt(get())); vv.id = id + '-v';
    top.appendChild(lb); top.appendChild(vv); c.appendChild(top);
    var r = document.createElement('input');
    r.type = 'range'; r.min = '0'; r.max = '100'; r.step = '1'; r.id = id;
    r.value = String(Math.round(get() * 100));
    r.addEventListener('input', function () { set(Number(r.value) / 100); render(); });
    c.appendChild(r); host.appendChild(c);
  }

  segCtl('Âge', '', [['18_24', '18–24'], ['25_34', '25–34'], ['35_44', '35–44'], ['45_59', '45–59'], ['60_PLUS', '60 +']],
    function () { return CTL.age; }, function (v) { CTL.age = v; });
  segCtl('Milieu', '', [['URBAN', 'Urbain'], ['RURAL', 'Rural']],
    function () { return CTL.mil; }, function (v) { CTL.mil = v; });
  segCtl('Situation', '', [['ACTIVE_EMPLOYED', 'En emploi'], ['UNEMPLOYED', 'Au chômage'], ['INACTIVE', 'Hors emploi']],
    function () { return CTL.act; }, function (v) { CTL.act = v; });
  segCtl('Niveau de vie', '', [[0.2, '1'], [0.4, '2'], [0.6, '3'], [0.8, '4'], [1.0, '5']],
    function () { return CTL.qv; }, function (v) { CTL.qv = v; });
  rangeCtl('c-conf', 'Confiance dans les institutions', function () { return CTL.conf; },
    function (v) { CTL.conf = v; }, function (v) { return v < .28 ? 'très faible' : v < .45 ? 'faible' : v < .62 ? 'moyenne' : v < .8 ? 'élevée' : 'très élevée'; });
  rangeCtl('c-bil', 'Jugement sur le bilan sortant', function () { return CTL.bil; },
    function (v) { CTL.bil = v; }, function (v) { return v < .28 ? 'très sévère' : v < .45 ? 'sévère' : v < .62 ? 'mitigé' : v < .8 ? 'favorable' : 'très favorable'; });

  var c = el('div', 'ctl');
  var top = el('div', 'ctl-top');
  var lb = el('label', null, 'La fois précédente, il a…'); lb.htmlFor = 'c-prior';
  top.appendChild(lb); c.appendChild(top);
  var sel = document.createElement('select'); sel.id = 'c-prior';
  var o0 = document.createElement('option'); o0.value = 'ABSTAIN'; o0.textContent = 'Ne s’est pas déplacé';
  sel.appendChild(o0);
  SIM.ctx.parties.forEach(function (q, i) {
    var o = document.createElement('option');
    o.value = q;
    o.textContent = 'Voté ' + partyName(q) + ' — ' +
      (SIM.ctx.gov[i] === 'INCUMBENT_COALITION' ? 'coalition sortante'
        : SIM.ctx.gov[i] === 'OPPOSITION' ? 'opposition' : 'autres');
    sel.appendChild(o);
  });
  sel.value = CTL.prior;
  sel.addEventListener('change', function () { CTL.prior = sel.value; render(); });
  c.appendChild(sel); host.appendChild(c);

  var foot = el('p', 'sub', 'El-Gharb · élection 2021 · participation précédente ' +
    pct(SIM.ctx.prevturnout, 1) + ' · ' + SIM.ctx.ncomp + ' profils politiques vérifiés.');
  foot.style.marginTop = '16px';
  host.appendChild(foot);

  render();

  function render() {
    var segs = host.querySelectorAll('.seg');
    var vals = [CTL.age, CTL.mil, CTL.act, CTL.qv];
    for (var gi = 0; gi < segs.length; gi++) {
      var bs = segs[gi].querySelectorAll('button');
      var opts = [['18_24', '25_34', '35_44', '45_59', '60_PLUS'], ['URBAN', 'RURAL'],
      ['ACTIVE_EMPLOYED', 'UNEMPLOYED', 'INACTIVE'], [0.2, 0.4, 0.6, 0.8, 1.0]][gi];
      for (var bi = 0; bi < bs.length; bi++) bs[bi].setAttribute('aria-pressed', String(opts[bi] === vals[gi]));
    }
    var cv = document.getElementById('c-conf-v'), bv = document.getElementById('c-bil-v');
    if (cv) cv.textContent = CTL.conf < .28 ? 'très faible' : CTL.conf < .45 ? 'faible' : CTL.conf < .62 ? 'moyenne' : CTL.conf < .8 ? 'élevée' : 'très élevée';
    if (bv) bv.textContent = CTL.bil < .28 ? 'très sévère' : CTL.bil < .45 ? 'sévère' : CTL.bil < .62 ? 'mitigé' : CTL.bil < .8 ? 'favorable' : 'très favorable';

    var d = decide(sigOf(), CTL.prior);
    drawGauge(d.part);

    var hb = $('#blocs'); clear(hb);
    d.blocs.forEach(function (v, i) { barRow(hb, BLOC_FR[i], v, BLOC_COL[i], pct(v, 1), true); });

    var hf = $('#demo-fact'); clear(hf);
    F.slice().sort(function (a, b2) { return d.fi[b2] - d.fi[a]; }).forEach(function (f) {
      barRow(hf, FACT_SHORT[f], d.fi[f] / 0.45, FACT_COL[f], pct(d.fi[f], 1), true);
    });

    var hp = $('#demo-parties'); clear(hp);
    var order = SIM.ctx.parties.map(function (q, i) { return [q, i]; })
      .sort(function (a, b2) { return d.pp[b2[1]] - d.pp[a[1]]; });
    order.forEach(function (o) {
      var i = o[1];
      var tag = SIM.ctx.gov[i] === 'INCUMBENT_COALITION' ? 'sortante'
        : SIM.ctx.gov[i] === 'OPPOSITION' ? 'opposition' : 'résiduel';
      barRow(hp, partyName(o[0]) + ' · ' + tag, d.pp[i] / 0.6,
        BLOC_COL[SIM.ctx.gov[i] === 'INCUMBENT_COALITION' ? 0 : (SIM.ctx.gov[i] === 'OPPOSITION' ? 1 : 2)],
        pct(d.pp[i], 1), true);
    });

    var hc = $('#demo-codes'); clear(hc);
    d.codes.forEach(function (c2) {
      hc.appendChild(el('span', 'chip ' + (CODE_TONE[c2] || ''), CODE_FR[c2] || c2));
    });

    var v = $('#verdict');
    clear(v);
    var top1 = F.slice().sort(function (a, b2) { return d.fi[b2] - d.fi[a]; });
    var ordered = order;
    var lead = ordered[0];
    var loyal = d.voted && lead[0] === CTL.prior;
    function b(t) { var s2 = el('b', null, t); return s2; }
    function hi(t) { var s2 = el('span', 'hi', t); return s2; }
    v.appendChild(document.createTextNode('Ce citoyen a '));
    v.appendChild(hi(pct(d.part, 0)));
    v.appendChild(document.createTextNode(' de chances de se déplacer, contre '));
    v.appendChild(b(pct(SIM.ctx.prevturnout, 0)));
    v.appendChild(document.createTextNode(' pour son territoire la fois précédente. '));
    if (d.voted) {
      var pOwn = d.pp[SIM.ctx.parties.indexOf(CTL.prior)];
      v.appendChild(document.createTextNode(loyal
        ? 'Il reste sur sa liste de la dernière fois, mais sans certitude : '
        : 'Il ne reste pas sur sa liste de la dernière fois — celle-ci ne garde que '));
      v.appendChild(b(pct(pOwn, 0)));
      v.appendChild(document.createTextNode(loyal ? ' du poids seulement. ' : ' du poids. '));
    } else {
      v.appendChild(document.createTextNode('N’ayant pas voté la fois précédente, rien ne l’attache à une liste. '));
    }
    v.appendChild(document.createTextNode('Ce qui pèse le plus dans sa décision : '));
    v.appendChild(b(factLabel(top1[0], d.voted)));
    v.appendChild(document.createTextNode(' (' + pct(d.fi[top1[0]], 0) + '), devant '));
    v.appendChild(b(factLabel(top1[1], d.voted)));
    v.appendChild(document.createTextNode(' (' + pct(d.fi[top1[1]], 0) + '). '));
    v.appendChild(document.createTextNode(d.gd < -0.004
      ? 'Son jugement sur le bilan sortant est négatif : il pénalise les listes de la coalition.'
      : d.gd > 0.004
        ? 'Son jugement sur le bilan sortant est positif : il avantage les listes de la coalition.'
        : 'Son jugement sur le bilan sortant est neutre : ce facteur ne tranche pas.'));
  }
}

function drawGauge(v) {
  var host = $('#gauge'); clear(host);
  var R = 46, C2 = 2 * Math.PI * R, S2 = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  S2.setAttribute('width', '112'); S2.setAttribute('height', '112'); S2.setAttribute('viewBox', '0 0 112 112');
  function circ(col, frac, wdt) {
    var c = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
    c.setAttribute('cx', '56'); c.setAttribute('cy', '56'); c.setAttribute('r', String(R));
    c.setAttribute('fill', 'none'); c.setAttribute('stroke', col); c.setAttribute('stroke-width', String(wdt));
    c.setAttribute('stroke-linecap', 'round');
    c.setAttribute('stroke-dasharray', (C2 * frac).toFixed(2) + ' ' + C2.toFixed(2));
    c.setAttribute('transform', 'rotate(-90 56 56)');
    return c;
  }
  S2.appendChild(circ('#0b111a', 1, 11));
  S2.appendChild(circ(v > 0.6 ? '#ffa24d' : v > 0.4 ? '#e9701f' : '#b25a1e', v, 11));
  host.appendChild(S2);
  var d = el('div');
  d.appendChild(el('div', 'g-val num', pct(v, 1)));
  d.appendChild(el('div', 'g-lab', v > 0.65 ? 'Se déplacera très probablement.'
    : v > 0.45 ? 'Déplacement incertain, légèrement favorable.'
      : v > 0.3 ? 'Déplacement peu probable.' : 'Restera très probablement chez lui.'));
  host.appendChild(d);
}

/* ── ce qui pèse ─────────────────────────────────────────────────────────── */

var forcesDim = null;

function forces() {
  var dims = Object.keys(DIM_FR);
  var host = $('#dims-forces'); clear(host);
  var all = el('button', null, 'Toute la société'); all.type = 'button';
  all.addEventListener('click', function () { forcesDim = null; drawForces(); });
  host.appendChild(all);
  dims.forEach(function (d) {
    var b = el('button', null, DIM_FR[d]); b.type = 'button';
    b.addEventListener('click', function () { forcesDim = d; drawForces(); });
    host.appendChild(b);
  });
  drawForces();
}

function drawForces() {
  var host = $('#dims-forces');
  var bs = host.querySelectorAll('button');
  var dims = Object.keys(DIM_FR);
  bs[0].setAttribute('aria-pressed', String(forcesDim === null));
  for (var i = 0; i < dims.length; i++) bs[i + 1].setAttribute('aria-pressed', String(forcesDim === dims[i]));

  var hb = $('#forces-bars'); clear(hb);
  var hd = $('#forces-diff'); clear(hd);

  if (forcesDim === null) {
    var g = S.global['*'];
    $('#forces-title').textContent = 'Ensemble de la société';
    $('#forces-sub').textContent = nf(g.n) + ' décisions · part moyenne de chaque force';
    var idx = F.map(function (f, j) { return [f, g.fact[j]]; }).sort(function (a, b) { return b[1] - a[1]; });
    idx.forEach(function (p) { barRow(hb, FACT_FR[p[0]], p[1] / 0.32, FACT_COL[p[0]], pct(p[1], 1), true); });
    var d2 = g.dom2, tot = g.n;
    Object.keys(d2).forEach(function (k) {
      barRow(hd, FACT_SHORT[k], d2[k] / tot, FACT_COL[k], pct(d2[k] / tot, 1), true);
    });
    $('#forces-note').textContent = 'Pour ' + pct(d2.social_protection_and_public_services / tot, 0) +
      ' des citoyens, ce qui départage vraiment les choix, une fois les habitudes mises de côté, ' +
      'ce sont les engagements sur la santé, l’école, le logement et la protection sociale.';
    return;
  }

  var seg = S.segments[forcesDim];
  var keys = Object.keys(seg).sort(function (a, b) { return seg[b].n - seg[a].n; });
  $('#forces-title').textContent = DIM_FR[forcesDim];
  $('#forces-sub').textContent = 'Part de chaque force, par population. Barre = poids de la force la plus lourde après l’inertie.';

  keys.forEach(function (k) {
    var s = seg[k];
    var order = F.map(function (f, j) { return [f, s.fact[j]]; })
      .filter(function (p) { return p[0] !== 'prior_vote_inertia' && p[0] !== 'turnout_habit'; })
      .sort(function (a, b) { return b[1] - a[1]; });
    barRow(hb, valFr(forcesDim, k) + ' · ' + FACT_SHORT[order[0][0]], order[0][1] / 0.20,
      FACT_COL[order[0][0]], pct(order[0][1], 1), true);
  });

  keys.forEach(function (k) {
    var s = seg[k], d2 = s.dom2, best = null;
    Object.keys(d2).forEach(function (f) { if (!best || d2[f] > d2[best]) best = f; });
    var second = Object.keys(d2).filter(function (f) { return f !== best; })
      .sort(function (a, b) { return d2[b] - d2[a]; })[0];
    if (!second) second = best;
    barRow(hd, valFr(forcesDim, k) + ' · ' + FACT_SHORT[second], d2[second] / s.n / 0.45,
      FACT_COL[second], pct(d2[second] / s.n, 0), true);
  });
  $('#forces-note').textContent = 'À gauche : la force la plus lourde une fois l’inertie retirée, ' +
    'et le poids qu’elle prend. À droite : la deuxième manière de décider la plus répandue dans cette ' +
    'population — c’est là que les groupes se séparent vraiment.';
}

/* ── sanction ────────────────────────────────────────────────────────────── */

var sancDim = 'age';

function sanction() {
  var g = S.global['*'];
  fill('#sanc-age', 'age', 'sanction');
  fill('#sanc-conf', 'confiance', 'sanction');

  var rows = [];
  Object.keys(DIM_FR).forEach(function (d) {
    var seg = S.segments[d];
    Object.keys(seg).forEach(function (k) {
      if (k === 'MISSING' || seg[k].n < 2000) return;
      rows.push([DIM_FR[d] + ' · ' + valFr(d, k), seg[k].sanction]);
    });
  });
  rows.sort(function (a, b) { return b[1] - a[1]; });
  var host = $('#sanc-top'); clear(host);
  rows.slice(0, 5).forEach(function (r) { barRow(host, r[0], r[1], '#d8553f', pct(r[1], 0), true); });
  rows.slice(-4).reverse().forEach(function (r) { barRow(host, r[0], r[1], '#2fa855', pct(r[1], 0), true); });

  function fill(sel, dim, field) {
    var h = $(sel); clear(h);
    var seg = S.segments[dim];
    var order = dim === 'age'
      ? ['18_24', '25_34', '35_44', '45_59', '60_PLUS']
      : ['bas', 'median', 'haut'];
    order.forEach(function (k) {
      if (!seg[k]) return;
      barRow(h, valFr(dim, k), seg[k][field], rampColour(seg[k][field]), pct(seg[k][field], 0), true);
    });
  }

  var dh = $('#dims-sanction'); clear(dh);
  Object.keys(DIM_FR).forEach(function (d) {
    var b = el('button', null, DIM_FR[d]); b.type = 'button';
    b.addEventListener('click', function () { sancDim = d; drawSancTbl(); });
    dh.appendChild(b);
  });
  drawSancTbl();
}

function drawSancTbl() {
  var dims = Object.keys(DIM_FR), bs = $('#dims-sanction').querySelectorAll('button');
  for (var i = 0; i < dims.length; i++) bs[i].setAttribute('aria-pressed', String(dims[i] === sancDim));
  var seg = S.segments[sancDim];
  var keys = Object.keys(seg).sort(function (a, b) { return seg[b].sanction - seg[a].sanction; });
  var t = $('#sanc-tbl'); clear(t);
  var thead = el('thead'), tr = el('tr');
  ['Population', 'Citoyens', 'Sanctionnent', 'Récompensent', 'Participation', 'Fidélité'].forEach(function (h) {
    tr.appendChild(el('th', null, h));
  });
  thead.appendChild(tr); t.appendChild(thead);
  var tb = el('tbody');
  keys.forEach(function (k) {
    var s = seg[k], r = el('tr');
    r.appendChild(el('td', null, valFr(sancDim, k)));
    r.appendChild(el('td', 'n', nf(s.n)));
    var td = el('td', 'n');
    td.appendChild(document.createTextNode(pct(s.sanction, 1)));
    var mb = el('span', 'minibar'), fi2 = el('i');
    fi2.style.background = rampColour(s.sanction);
    mb.appendChild(fi2); td.appendChild(mb);
    r.appendChild(td);
    requestAnimationFrame(function () { fi2.style.width = (s.sanction * 100) + '%'; });
    r.appendChild(el('td', 'n', pct(s.recompense, 1)));
    r.appendChild(el('td', 'n', pct(s.part, 1)));
    r.appendChild(el('td', 'n', s.fid === null ? '—' : pct(s.fid, 1)));
    tb.appendChild(r);
  });
  t.appendChild(tb);
}

/* ── bascule ─────────────────────────────────────────────────────────────── */

var fidDim = 'milieu';

function bascule() {
  var g = S.global['*'];
  drawFlow(g);

  var host = $('#fid-bands'); clear(host);
  var B = [
    ['Acquis', g.acquis, 'Plus de 65 % du poids reste sur la liste déjà choisie.'],
    ['Hésitants', g.hesitant, 'Entre 35 % et 65 % : la décision peut basculer.'],
    ['En voie de départ', g.partant, 'Moins de 35 % : la liste précédente n’est plus le choix probable.']
  ];
  B.forEach(function (b, i) {
    var r = el('div', 'band-row');
    r.appendChild(el('span', 't', b[0]));
    r.appendChild(el('b', 'num', pct(b[1], 1)));
    r.appendChild(el('span', 'd', b[2]));
    r.style.borderLeft = '3px solid ' + [ '#2fa855', '#ffa24d', '#d8553f' ][i];
    host.appendChild(r);
  });
  $('#bascule-note').textContent =
    'Parmi les citoyens ayant déjà voté, une minorité seulement est réellement acquise à son choix précédent. ' +
    'La majorité est hésitante — ce qui rend le programme et le jugement sur le bilan décisifs.';

  var dh = $('#dims-fid'); clear(dh);
  Object.keys(DIM_FR).forEach(function (d) {
    var b = el('button', null, DIM_FR[d]); b.type = 'button';
    b.addEventListener('click', function () { fidDim = d; drawFidTbl(); });
    dh.appendChild(b);
  });
  drawFidTbl();
}

function drawFlow(g) {
  var host = $('#flow'); clear(host);
  var W = 640, H = 300, PAD = 26, BW = 22;
  var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
  svg.setAttribute('class', 'flow-svg');
  svg.setAttribute('role', 'img');
  svg.setAttribute('aria-label', 'Bascule du poids électoral entre les camps');
  var NS = 'http://www.w3.org/2000/svg';

  var tot = g.flown[0] + g.flown[1] + g.flown[2];
  var left = [], y = PAD;
  for (var i = 0; i < 3; i++) {
    var h = (H - 2 * PAD - 24) * (g.flown[i] / tot);
    left.push({ y: y, h: h }); y += h + 12;
  }
  var rightTot = [0, 0, 0];
  for (i = 0; i < 3; i++) for (var j = 0; j < 3; j++) rightTot[j] += g.flow[i][j] * g.flown[i];
  var rSum = rightTot[0] + rightTot[1] + rightTot[2];
  var right = []; y = PAD;
  for (j = 0; j < 3; j++) {
    var h2 = (H - 2 * PAD - 24) * (rightTot[j] / rSum);
    right.push({ y: y, h: h2, cur: 0 }); y += h2 + 12;
  }

  for (i = 0; i < 3; i++) {
    var cur = left[i].y;
    for (j = 0; j < 3; j++) {
      var frac = g.flow[i][j];
      var th = left[i].h * frac;
      var y0 = cur, y1 = right[j].y + right[j].cur;
      cur += th; right[j].cur += th;
      var p = document.createElementNS(NS, 'path');
      var x0 = PAD + BW, x1 = W - PAD - BW;
      var mid = (x0 + x1) / 2;
      p.setAttribute('d', 'M' + x0 + ',' + y0 + ' C' + mid + ',' + y0 + ' ' + mid + ',' + y1 + ' ' + x1 + ',' + y1 +
        ' L' + x1 + ',' + (y1 + th) + ' C' + mid + ',' + (y1 + th) + ' ' + mid + ',' + (y0 + th) + ' ' + x0 + ',' + (y0 + th) + ' Z');
      p.setAttribute('fill', BLOC_COL[i]);
      p.setAttribute('opacity', i === j ? '.42' : '.19');
      var ti = document.createElementNS(NS, 'title');
      ti.textContent = BLOC_FR[i] + ' → ' + BLOC_FR[j] + ' : ' + pct(frac, 1) + ' du poids';
      p.appendChild(ti);
      svg.appendChild(p);
    }
  }
  for (i = 0; i < 3; i++) {
    [[PAD, left[i], 'start'], [W - PAD - BW, right[i], 'end']].forEach(function (o, side) {
      var r = document.createElementNS(NS, 'rect');
      r.setAttribute('x', String(o[0])); r.setAttribute('y', String(o[1].y));
      r.setAttribute('width', String(BW)); r.setAttribute('height', String(Math.max(2, o[1].h)));
      r.setAttribute('fill', BLOC_COL[i]); r.setAttribute('rx', '2');
      svg.appendChild(r);
      var t = document.createElementNS(NS, 'text');
      t.setAttribute('x', String(side ? o[0] - 8 : o[0] + BW + 8));
      t.setAttribute('y', String(o[1].y + o[1].h / 2 + 4));
      t.setAttribute('fill', '#aab7c9'); t.setAttribute('font-size', '11');
      t.setAttribute('text-anchor', side ? 'end' : 'start');
      t.textContent = side ? pct(rightTot[i] / rSum, 0) : BLOC_FR[i];
      svg.appendChild(t);
    });
  }
  var cap = document.createElementNS(NS, 'text');
  cap.setAttribute('x', String(PAD)); cap.setAttribute('y', String(H - 6));
  cap.setAttribute('fill', '#7c8aa0'); cap.setAttribute('font-size', '10.5');
  cap.textContent = 'Camp voté la fois précédente  →  répartition du poids maintenant';
  svg.appendChild(cap);
  host.appendChild(svg);

  var lg = $('#flow-legend'); clear(lg);
  BLOC_FR.forEach(function (b, i) {
    var s = el('span');
    var sq = el('i'); sq.style.background = BLOC_COL[i];
    s.appendChild(sq);
    s.appendChild(document.createTextNode(b + ' — ' + pct(g.flow[i][i], 0) + ' restent'));
    lg.appendChild(s);
  });
}

function drawFidTbl() {
  var dims = Object.keys(DIM_FR), bs = $('#dims-fid').querySelectorAll('button');
  for (var i = 0; i < dims.length; i++) bs[i].setAttribute('aria-pressed', String(dims[i] === fidDim));
  var seg = S.segments[fidDim];
  var keys = Object.keys(seg).filter(function (k) { return seg[k].fidn > 0; })
    .sort(function (a, b) { return seg[b].partant - seg[a].partant; });
  var t = $('#fid-tbl'); clear(t);
  var thead = el('thead'), tr = el('tr');
  ['Population', 'Ont déjà voté', 'Acquis', 'Hésitants', 'En voie de départ', 'Fidélité moyenne'].forEach(function (h) {
    tr.appendChild(el('th', null, h));
  });
  thead.appendChild(tr); t.appendChild(thead);
  var tb = el('tbody');
  keys.forEach(function (k) {
    var s = seg[k], r = el('tr');
    r.appendChild(el('td', null, valFr(fidDim, k)));
    r.appendChild(el('td', 'n', nf(s.fidn)));
    r.appendChild(el('td', 'n', pct(s.acquis, 1)));
    r.appendChild(el('td', 'n', pct(s.hesitant, 1)));
    var td = el('td', 'n');
    td.appendChild(document.createTextNode(pct(s.partant, 1)));
    var mb = el('span', 'minibar'), f2 = el('i');
    f2.style.background = '#d8553f'; mb.appendChild(f2); td.appendChild(mb);
    requestAnimationFrame(function () { f2.style.width = (s.partant / 0.35 * 100) + '%'; });
    r.appendChild(td);
    r.appendChild(el('td', 'n', pct(s.fid, 1)));
    tb.appendChild(r);
  });
  t.appendChild(tb);
}

/* ── qui écoute quoi ─────────────────────────────────────────────────────── */

function ecoute() {
  var host = $('#ecoute-cards'); clear(host);
  var g = S.global['*'];
  var SPECS = [
    ['Le programme social', 'sociaux', '#e9701f',
      'Décisions où l’attente sur la santé, l’école, le logement ou la protection sociale est citée comme moteur.'],
    ['La figure locale', 'locale', '#d55181',
      'Décisions où une candidature locale vérifiée fait pencher la balance. Dans ce corpus, seuls quelques territoires documentent des candidatures.'],
    ['Le territoire', 'terr', '#6e8bff',
      'Décisions où ce qui est promis au territoire — désenclavement, services, équité — est cité comme moteur.']
  ];
  SPECS.forEach(function (sp) {
    var c = el('div', 'card pad');
    c.appendChild(el('h3', null, sp[0]));
    var v = valueOf(g, sp[1]);
    var big = el('div', 'num', pct(v, 1));
    big.style.font = '700 34px/1 ui-monospace, Consolas, monospace';
    big.style.letterSpacing = '-.04em';
    big.style.color = sp[2];
    big.style.margin = '10px 0 4px';
    c.appendChild(big);
    c.appendChild(el('p', 'sub', sp[3]));
    var rows = [];
    Object.keys(DIM_FR).forEach(function (d) {
      var seg = S.segments[d];
      Object.keys(seg).forEach(function (k) {
        if (k === 'MISSING' || seg[k].n < 2000) return;
        rows.push([valFr(d, k), valueOf(seg[k], sp[1])]);
      });
    });
    rows.sort(function (a, b) { return b[1] - a[1]; });
    var top = rows.slice(0, 5);
    var mx = Math.max(0.02, top[0][1]);
    var bars = el('div', 'bars');
    top.forEach(function (r) { barRow(bars, r[0], r[1] / mx, sp[2], pct(r[1], 0), true); });
    var cap = el('p', 'sub', 'Populations les plus concernées');
    cap.style.marginTop = '14px';
    c.appendChild(cap);
    c.appendChild(bars);
    host.appendChild(c);
  });

  var ch = $('#chains'); clear(ch);
  var tot = S.meta.rows;
  S.enchainements.slice(0, 8).forEach(function (e) {
    barRow(ch, FACT_SHORT[e.a] + ' → ' + FACT_SHORT[e.b], e.n / tot / 0.45,
      FACT_COL[e.b], pct(e.n / tot, 1), true);
  });
}

function valueOf(s, kind) {
  var c = s.codes || {};
  if (kind === 'sociaux') return c.SOCIAL_PROTECTION_PUBLIC_SERVICES_FIT || 0;
  if (kind === 'locale') return s.locale;
  if (kind === 'terr') return c.TERRITORIAL_RURAL_FIT || 0;
  return 0;
}

/* ── portraits ───────────────────────────────────────────────────────────── */

var K = {}, FIL = { age: '', mi: '', ac: '', qv: '', pr: '' }, SEL = -1;

function portraits() {
  P.cles.forEach(function (k, i) { K[k] = i; });
  var host = $('#filters'); clear(host);
  var SPECS = [
    ['age', 'Âge', [['18_24', '18–24 ans'], ['25_34', '25–34 ans'], ['35_44', '35–44 ans'], ['45_59', '45–59 ans'], ['60_PLUS', '60 ans et plus']]],
    ['mi', 'Milieu', [['URBAN', 'Urbain'], ['RURAL', 'Rural']]],
    ['ac', 'Situation', [['ACTIVE_EMPLOYED', 'En emploi'], ['UNEMPLOYED', 'Au chômage'], ['INACTIVE', 'Hors emploi']]],
    ['qv', 'Niveau de vie', [['0.2', 'Le plus modeste'], ['0.4', 'Modeste'], ['0.6', 'Médian'], ['0.8', 'Aisé'], ['1', 'Le plus aisé']]],
    ['pr', 'La fois précédente', [['ABSTAIN', 'Ne s’est pas déplacé'], ['VOTE', 'A voté']]]
  ];
  SPECS.forEach(function (sp) {
    var w = el('div');
    var l = el('label', null, sp[1]); l.htmlFor = 'f-' + sp[0];
    w.appendChild(l);
    var s = document.createElement('select'); s.id = 'f-' + sp[0];
    var o = document.createElement('option'); o.value = ''; o.textContent = 'Tous';
    s.appendChild(o);
    sp[2].forEach(function (v) {
      var oo = document.createElement('option'); oo.value = v[0]; oo.textContent = v[1];
      s.appendChild(oo);
    });
    s.addEventListener('change', function () { FIL[sp[0]] = s.value; SEL = -1; drawGallery(); });
    w.appendChild(s); host.appendChild(w);
  });
  drawGallery();
}

function matches(a) {
  if (FIL.age && a[K.age] !== FIL.age) return false;
  if (FIL.mi && a[K.mi] !== FIL.mi) return false;
  if (FIL.ac && a[K.ac] !== FIL.ac) return false;
  if (FIL.qv && String(a[K.qv]) !== FIL.qv) return false;
  if (FIL.pr === 'ABSTAIN' && a[K.pr] !== 'ABSTAIN') return false;
  if (FIL.pr === 'VOTE' && a[K.pr] === 'ABSTAIN') return false;
  return true;
}

function drawGallery() {
  var list = P.agents.filter(matches);
  $('#gal-count').textContent = nf(list.length) + ' portraits correspondent · ' +
    (list.length > 48 ? 'les 48 premiers sont affichés' : 'tous affichés') + ' · cliquez pour ouvrir une décision';
  var host = $('#gallery'); clear(host);
  list.slice(0, 48).forEach(function (a, i) {
    var b = el('button', 'pcard'); b.type = 'button';
    b.setAttribute('aria-pressed', 'false');
    b.appendChild(el('div', 'id', a[K.id] + ' · ' + a[K.t]));
    b.appendChild(el('div', 'who', a[K.ans] + ' ans, ' + (a[K.sx] === 'F' ? 'femme' : 'homme') + ', ' +
      (a[K.mi] === 'RURAL' ? 'rural' : 'urbain')));
    b.appendChild(el('div', 'ctxt', (VAL_FR[a[K.ac]] || '—') + ' · ' + (VAL_FR[a[K.ed]] || '—')));
    var strip = el('div', 'strip');
    var fa = a[K.fa];
    var ord = F.map(function (f, j) { return [f, fa[j]]; }).sort(function (x, y) { return y[1] - x[1]; }).slice(0, 5);
    ord.forEach(function (o) {
      var s = el('i'); s.style.background = FACT_COL[o[0]]; s.style.flex = String(Math.max(0.05, o[1]));
      strip.appendChild(s);
    });
    b.appendChild(strip);
    var f = el('div', 'foot');
    f.appendChild(el('span', null, 'part. ' + pct(a[K.part], 0)));
    f.appendChild(el('span', null, a[K.pr] === 'ABSTAIN' ? 'abstenu' : 'fidélité ' + pct(a[K.fid], 0)));
    b.appendChild(f);
    b.addEventListener('click', function () { SEL = P.agents.indexOf(a); drawDetail(a); markSel(host); });
    host.appendChild(b);
  });
  if (list.length) { drawDetail(list[0]); SEL = P.agents.indexOf(list[0]); markSel(host); }
}

function markSel(host) {
  var bs = host.querySelectorAll('.pcard');
  var list = P.agents.filter(matches).slice(0, 48);
  for (var i = 0; i < bs.length; i++) bs[i].setAttribute('aria-pressed', String(P.agents.indexOf(list[i]) === SEL));
}

function drawDetail(a) {
  var host = $('#detail'); host.hidden = false; clear(host);
  var card = el('div', 'card pad');
  card.appendChild(el('div', 'eyebrow', 'Portrait de la société'));
  var g = el('div', 'detail-grid'); g.style.marginTop = '14px';

  var idc = el('div', 'idcard');
  var rows = [
    ['Âge', a[K.ans] + ' ans'],
    ['Sexe', a[K.sx] === 'F' ? 'Femme' : 'Homme'],
    ['Milieu', VAL_FR[a[K.mi]] || '—'],
    ['Études', VAL_FR[a[K.ed]] || '—'],
    ['Situation', VAL_FR[a[K.ac]] || '—'],
    ['Métier', a[K.occ] === 'MISSING' ? 'Non renseigné' : a[K.occ]],
    ['Foyer', (VAL_FR[a[K.fo]] || '—') + ' · ' + a[K.hh] + ' personnes'],
    ['Secteur', VAL_FR[a[K.se]] || '—'],
    ['Niveau de vie', 'Niveau ' + Math.round(a[K.qv] * 5) + ' sur 5'],
    ['Difficulté matérielle', pct(a[K.ha], 0)],
    ['Confiance institutions', pct(a[K.tr], 0)],
    ['Corruption ressentie', pct(a[K.co], 0)],
    ['Parle de politique', pct(a[K.di], 0)],
    ['La fois précédente', a[K.pr] === 'ABSTAIN' ? 'Ne s’est pas déplacé' : 'A voté pour ' + partyName(a[K.pr])]
  ];
  rows.forEach(function (r) {
    var d = el('div');
    d.appendChild(el('dt', null, r[0]));
    d.appendChild(el('dd', null, String(r[1])));
    idc.appendChild(d);
  });
  g.appendChild(idc);

  var right = el('div');
  var top = el('div', 'grid2');
  var c1 = el('div', 'card pad');
  c1.appendChild(el('h3', null, 'Participation'));
  var gv = el('div', 'num', pct(a[K.part], 1));
  gv.style.font = '700 40px/1 ui-monospace, Consolas, monospace';
  gv.style.letterSpacing = '-.04em';
  gv.style.color = a[K.part] > 0.6 ? '#ffa24d' : a[K.part] > 0.4 ? '#e9701f' : '#b25a1e';
  gv.style.margin = '8px 0 2px';
  c1.appendChild(gv);
  c1.appendChild(el('p', 'sub', a[K.part] > 0.65 ? 'Se déplacera très probablement.'
    : a[K.part] > 0.45 ? 'Déplacement incertain.' : 'Restera très probablement chez lui.'));
  var c2 = el('div', 'card pad');
  c2.appendChild(el('h3', null, 'Répartition entre les camps'));
  var bb = el('div', 'bars');
  a[K.bl].forEach(function (v, i) { barRow(bb, BLOC_FR[i], v, BLOC_COL[i], pct(v, 1), true); });
  c2.appendChild(bb);
  top.appendChild(c1); top.appendChild(c2);
  right.appendChild(top);

  var c3 = el('div', 'card pad'); c3.style.marginTop = '16px';
  c3.appendChild(el('h3', null, 'Ce qui a pesé'));
  var b3 = el('div', 'bars');
  F.map(function (f, j) { return [f, a[K.fa][j]]; }).sort(function (x, y) { return y[1] - x[1]; })
    .forEach(function (o) { barRow(b3, FACT_FR[o[0]], o[1] / 0.45, FACT_COL[o[0]], pct(o[1], 1), true); });
  c3.appendChild(b3);
  var ch = el('div', 'chips');
  a[K.rc].forEach(function (c) { ch.appendChild(el('span', 'chip ' + (CODE_TONE[c] || ''), CODE_FR[c] || c)); });
  c3.appendChild(ch);
  var nar = el('p', 'verdict'); nar.style.marginTop = '14px';
  nar.textContent = narrate(a);
  c3.appendChild(nar);
  right.appendChild(c3);
  g.appendChild(right);
  card.appendChild(g);
  host.appendChild(card);
}

/* Formulations destinées au texte courant : article inclus, déjà en minuscules. */
var FACT_PHRASE = {
  turnout_habit: 'son habitude d’aller voter',
  personal_economic_conditions: 'l’état de son budget',
  employment_and_income: 'l’emploi et les revenus',
  social_protection_and_public_services: 'les attentes de santé, d’école et de protection sociale',
  policy_program_fit: 'le reste des engagements de programme',
  governance_and_institutions: 'l’exigence de bonne gestion',
  territorial_rural_fit: 'l’attention portée à son territoire',
  government_reward_punishment: 'son jugement sur le bilan sortant',
  local_candidate_context: 'la figure locale',
  other_verified_context: 'le reste du contexte vérifié'
};

function factLabel(f, voted) {
  if (f === 'prior_vote_inertia') {
    return voted ? 'la fidélité à sa liste précédente, dans un territoire déjà orienté'
                 : 'l’orientation déjà installée dans son territoire';
  }
  return FACT_PHRASE[f] || FACT_FR[f].toLowerCase();
}

function narrate(a) {
  var f = F.map(function (x, j) { return [x, a[K.fa][j]]; }).sort(function (x, y) { return y[1] - x[1]; });
  var t = [];
  t.push('Profil de ' + a[K.ans] + ' ans, ' + (a[K.sx] === 'F' ? 'femme' : 'homme') + ', en milieu ' +
    (a[K.mi] === 'RURAL' ? 'rural' : 'urbain') + ', ' + (VAL_FR[a[K.ac]] || '').toLowerCase() +
    ', foyer de ' + a[K.hh] + ' personnes.');
  t.push(a[K.pr] === 'ABSTAIN'
    ? 'Ce profil ne s’était pas déplacé la fois précédente ; le modèle lui donne ' + pct(a[K.part], 0) + ' de chances d’aller voter cette fois.'
    : 'Ce profil avait voté pour ' + partyName(a[K.pr]) + ' ; la simulation lui donne ' + pct(a[K.part], 0) +
    ' de chances de se déplacer, et ' + pct(a[K.fid], 0) + ' de rester sur cette liste.');
  var vo = a[K.pr] !== 'ABSTAIN';
  t.push('La décision est portée d’abord par ' + factLabel(f[0][0], vo) + ' (' + pct(f[0][1], 0) +
    '), puis par ' + factLabel(f[1][0], vo) + ' (' + pct(f[1][1], 0) + ').');
  if (a[K.gd] < -0.004) t.push('Le jugement porté sur le bilan sortant est négatif : il pénalise la coalition en place.');
  else if (a[K.gd] > 0.004) t.push('Le jugement porté sur le bilan sortant est positif : il avantage la coalition en place.');
  else t.push('Le jugement porté sur le bilan sortant ne tranche pas.');
  return t.join(' ');
}

/* ── atlas ───────────────────────────────────────────────────────────────── */

var atlasMode = 'part';
var ATLAS_MODES = {
  part: ['Participation', function (t) { return t.part; }, function (t) { return pct(t.part, 1); }],
  fid: ['Fidélité moyenne', function (t) { return (t.fid - 0.35) / 0.35; }, function (t) { return pct(t.fid, 1); }],
  sanction: ['Sanction du bilan', function (t) { return t.sanction; }, function (t) { return pct(t.sanction, 1); }],
  locale: ['Poids de la figure locale', function (t) { return t.locale; }, function (t) { return pct(t.locale, 1); }],
  hard: ['Difficulté matérielle', function (t) { return t.hard; }, function (t) { return pct(t.hard, 1); }]
};

function atlas() {
  var host = $('#atlas-modes'); clear(host);
  Object.keys(ATLAS_MODES).forEach(function (m) {
    var b = el('button', null, ATLAS_MODES[m][0]); b.type = 'button';
    b.addEventListener('click', function () { atlasMode = m; drawAtlas(); });
    host.appendChild(b);
  });
  var lg = $('#atlas-legend'); clear(lg);
  lg.appendChild(el('span', null, 'Faible'));
  var ramp = el('div', 'ramp');
  RAMP.slice(1).forEach(function (c) { var i = el('i'); i.style.background = c; ramp.appendChild(i); });
  lg.appendChild(ramp);
  lg.appendChild(el('span', null, 'Élevé'));
  lg.appendChild(el('span', null, '· 184 tuiles, 512 décisions chacune · survolez une tuile'));
  drawAtlas();
  drawAtlasStats();
}

function drawAtlas() {
  var modes = Object.keys(ATLAS_MODES), bs = $('#atlas-modes').querySelectorAll('button');
  for (var i = 0; i < modes.length; i++) bs[i].setAttribute('aria-pressed', String(modes[i] === atlasMode));
  var spec = ATLAS_MODES[atlasMode];
  var host = $('#atlas-grid'); clear(host);
  var list = S.territoires.slice().sort(function (a, b) { return spec[1](b) - spec[1](a); });
  var tip = $('#tip');
  list.forEach(function (t) {
    var v = clip(spec[1](t), 0, 1);
    var d = el('div', 'tile');
    d.tabIndex = 0;
    d.style.background = rampColour(v);
    d.appendChild(el('span', null, Math.round(v * 100)));
    function show(ev) {
      clear(tip);
      tip.appendChild(el('b', null, t.t + ' · ' + t.e));
      [['Participation', pct(t.part, 1)], ['Précédemment', pct(t.part_prec, 1)],
      ['Fidélité', pct(t.fid, 1)], ['Sanction', pct(t.sanction, 1)],
      ['Figure locale', pct(t.locale, 1)],
      ['Force qui départage', FACT_SHORT[t.dom2] || t.dom2]].forEach(function (r) {
        var q = el('div', 'r');
        q.appendChild(el('span', null, r[0]));
        q.appendChild(el('b', null, r[1]));
        tip.appendChild(q);
      });
      tip.classList.add('on');
      var x = (ev.clientX || 0) + 14, y = (ev.clientY || 0) + 14;
      if (x > window.innerWidth - 280) x -= 300;
      if (y > window.innerHeight - 190) y -= 200;
      tip.style.left = x + 'px'; tip.style.top = y + 'px';
    }
    d.addEventListener('mouseenter', show);
    d.addEventListener('mousemove', show);
    d.addEventListener('focus', function () {
      var r = d.getBoundingClientRect();
      show({ clientX: r.left, clientY: r.bottom });
    });
    d.addEventListener('mouseleave', function () { tip.classList.remove('on'); });
    d.addEventListener('blur', function () { tip.classList.remove('on'); });
    host.appendChild(d);
  });
}

function drawAtlasStats() {
  var host = $('#atlas-stats'); clear(host);
  var T = S.territoires;
  var byPart = T.slice().sort(function (a, b) { return b.part - a.part; });
  var gaps = T.map(function (t) { return t.part - t.part_prec; }).sort(function (a, b) { return a - b; });
  var CARDS = [
    ['L’écart entre territoires', pct(byPart[0].part, 0) + ' → ' + pct(byPart[byPart.length - 1].part, 0),
      'Participation la plus haute et la plus basse. Le territoire pèse plus que n’importe quel trait individuel.'],
    ['Le modèle suit le passé', (gaps[Math.floor(gaps.length / 2)] >= 0 ? '+' : '') + nf(100 * gaps[Math.floor(gaps.length / 2)], 1) + ' pt',
      'Écart médian entre la participation simulée et celle du scrutin précédent du même territoire.'],
    ['Fidélité la plus fragile', pct(Math.min.apply(null, T.map(function (t) { return t.fid; })), 0),
      'Dans le territoire le moins stable, le citoyen moyen ne garde qu’une part minoritaire sur son choix précédent.']
  ];
  CARDS.forEach(function (c) {
    var d = el('div', 'card pad');
    d.appendChild(el('h3', null, c[0]));
    var b = el('div', 'num', c[1]);
    b.style.font = '700 30px/1 ui-monospace, Consolas, monospace';
    b.style.letterSpacing = '-.04em'; b.style.color = '#ffa24d'; b.style.margin = '10px 0 6px';
    d.appendChild(b);
    d.appendChild(el('p', 'sub', c[2]));
    host.appendChild(d);
  });
}

/* ── méthode ─────────────────────────────────────────────────────────────── */

function rules() {
  var host = $('#rules'); clear(host);
  var R = [
    ['Aucune prévision', 'Pas de résultat électoral',
      'Aucun score, aucune part de voix, aucun siège, aucun classement de partis n’est produit. Les agrégats sont bruts : aucun poids de population n’est appliqué, et le corpus n’en fournit aucun.'],
    ['Anonymat', 'Ni parti, ni territoire, ni date',
      'Dans l’espace public, les partis sont présentés avec leurs noms afin que la simulation soit lisible comme une véritable scène politique marocaine.'],
    ['Profils synthétiques', 'Personne n’est représenté',
      'Chaque citoyen est un profil statistique synthétique, pas une personne réelle. Aucune caractéristique sensible n’est déduite : ni religion, ni langue, ni origine.'],
    ['Preuve ou silence', 'Le manquant reste manquant',
      'Une information non vérifiée, absente ou contradictoire ne devient jamais un indice. Une priorité absente d’un programme signifie « non établie », jamais « refusée ».'],
    ['Deux lectures', 'Traitées à l’identique',
      'Le corpus contient deux lectures parallèles du même environnement. Elles ont été traitées exactement de la même façon, sans chercher à savoir laquelle jouait quel rôle. Leurs résultats sont d’ailleurs presque superposables.'],
    ['Décisions indépendantes', 'Chacun choisit de son côté',
      'Personne ne voit le choix d’un autre pendant cette étape. L’influence de la famille, des collègues, du voisinage ou des réseaux pourra être ajoutée dans une version suivante.']
  ];
  R.forEach(function (r) {
    var d = el('div', 'rule');
    d.appendChild(el('div', 'tag', r[0]));
    d.appendChild(el('h3', null, r[1]));
    d.appendChild(el('p', null, r[2]));
    host.appendChild(d);
  });
  twoReadings();
}

function twoReadings() {
  var host = document.getElementById('deux-lectures');
  if (!host) return;
  clear(host);
  var A = S.global.A, B = S.global.B;
  var ROWS = [
    ['Participation moyenne', A.part, B.part, 1],
    ['Fidélité moyenne', A.fid, B.fid, 1],
    ['Sanctionnent le bilan', A.sanction, B.sanction, 1],
    ['Récompensent le bilan', A.recompense, B.recompense, 1],
    ['Poids sur la coalition sortante', A.blocs[0], B.blocs[0], 1],
    ['Poids sur l’opposition', A.blocs[1], B.blocs[1], 1]
  ];
  var t = el('table', 'seg-tbl');
  var th = el('thead'), tr = el('tr');
  ['Mesure', 'Lecture A', 'Lecture B', 'Écart'].forEach(function (h) { tr.appendChild(el('th', null, h)); });
  th.appendChild(tr); t.appendChild(th);
  var tb = el('tbody');
  ROWS.forEach(function (r) {
    var row = el('tr');
    row.appendChild(el('td', null, r[0]));
    row.appendChild(el('td', 'n', pct(r[1], 2)));
    row.appendChild(el('td', 'n', pct(r[2], 2)));
    var d = Math.abs(r[1] - r[2]);
    var td = el('td', 'n', (d < 0.0001 ? '< 0,01' : nf(100 * d, 2)) + ' pt');
    td.style.color = d < 0.01 ? '#2fa855' : '#ffa24d';
    row.appendChild(td);
    tb.appendChild(row);
  });
  t.appendChild(tb);
  var sc = el('div', 'tbl-scroll'); sc.appendChild(t);
  host.appendChild(sc);
}

/* ── animation d'apparition & sommaire actif ─────────────────────────────── */

function reveal() {
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { rootMargin: '0px 0px -8% 0px' });
  document.querySelectorAll('.rise').forEach(function (n) { io.observe(n); });
  /* Si l'observateur ne se declenche pas (iframe auto-dimensionnee, viewport sans
     defilement), les blocs resteraient a opacity:0. Filet de securite. */
  setTimeout(function () {
    document.querySelectorAll('.rise').forEach(function (n) { n.classList.add('in'); });
  }, 800);
}

function spy() {
  var links = Array.prototype.slice.call(document.querySelectorAll('nav.jump a'));
  var secs = links.map(function (a) { return document.querySelector(a.getAttribute('href')); });
  var io = new IntersectionObserver(function (es) {
    es.forEach(function (e) {
      if (!e.isIntersecting) return;
      var i = secs.indexOf(e.target);
      links.forEach(function (l, j) { l.classList.toggle('on', j === i); });
    });
  }, { rootMargin: '-45% 0px -50% 0px' });
  secs.forEach(function (s) { if (s) io.observe(s); });
}
