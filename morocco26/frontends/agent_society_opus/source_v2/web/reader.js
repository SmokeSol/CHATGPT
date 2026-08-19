'use strict';

/* Couche lecteur. Toute la plomberie reste invisible ; le langage visuel reste celui d’Opus. */
window.ATLAS_PARTY_NAMES = {
  Q_01: 'PAM', Q_02: 'Autres', Q_03: 'RNI', Q_04: 'PPS', Q_05: 'Mouvement populaire',
  Q_06: 'PJD', Q_07: 'Union constitutionnelle', Q_08: 'USFP', Q_09: 'Istiqlal'
};

var READER_API = 'https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation';
var READER_DATA = null;
var ACTIVE_CONTRIBUTION = null;
var ASSISTANTS = {
  chatgpt: { label: 'ChatGPT', url: 'https://chatgpt.com/' },
  claude: { label: 'Claude', url: 'https://claude.ai/new' },
  other: { label: 'Une autre IA', url: null }
};

function reader$(s) { return document.querySelector(s); }
function readerPct(v) { return (100 * Number(v || 0)).toLocaleString('fr-FR', {maximumFractionDigits:1}) + ' %'; }
function readerClear(n) { if (!n) return; while (n.firstChild) n.removeChild(n.firstChild); }
function readerEl(tag, cls, txt) { var n=document.createElement(tag); if(cls)n.className=cls; if(txt!==undefined)n.textContent=txt; return n; }
function toast(title, body) {
  var n=reader$('.reader-toast');
  if(!n){ n=readerEl('div','reader-toast'); document.body.appendChild(n); }
  readerClear(n); n.appendChild(readerEl('b',null,title)); n.appendChild(readerEl('p',null,body));
  n.classList.add('on'); clearTimeout(toast.t); toast.t=setTimeout(function(){n.classList.remove('on');},4600);
}

function partyRows(host, values, real) {
  readerClear(host);
  var entries=Object.keys(values || {}).map(function(k){return [k,Number(values[k])];}).sort(function(a,b){return b[1]-a[1];}).slice(0,9);
  var max=Math.max.apply(null,entries.map(function(x){return x[1];}).concat([.01]));
  entries.forEach(function(x){
    var r=readerEl('div','party-row'+(real?' real':''));
    r.appendChild(readerEl('span','name',x[0]));
    var track=readerEl('div','track'), fill=readerEl('i','fill'); track.appendChild(fill); r.appendChild(track);
    r.appendChild(readerEl('span','value',readerPct(x[1]))); host.appendChild(r);
    requestAnimationFrame(function(){fill.style.width=Math.min(100,100*x[1]/max)+'%';});
  });
}

function renderTerritory() {
  if(!READER_DATA) return;
  var y=reader$('#reader-year').value, slug=reader$('#reader-territory').value;
  var all=READER_DATA.years[y].territories, t=all.find(function(x){return x.slug===slug;}) || all[0];
  reader$('#reader-location').textContent=t.name;
  reader$('#reader-location-sub').textContent=t.prefprov+' · '+t.region+' · '+t.seats+' sièges';
  reader$('#reader-location-kicker').textContent='Circonscription · '+y;
  partyRows(reader$('#reader-sim-parties'),t.simulation,false);
  partyRows(reader$('#reader-real-parties'),t.real,true);
  var nat=reader$('#reader-national'); readerClear(nat);
  var a=readerEl('div'); a.appendChild(readerEl('b',null,t.leader_sim)); a.appendChild(readerEl('span',null,'en tête dans la société artificielle')); nat.appendChild(a);
  var b=readerEl('div'); b.appendChild(readerEl('b',null,t.leader_real)); b.appendChild(readerEl('span',null,'en tête dans le vote réel')); nat.appendChild(b);
}

function populateTerritories() {
  if(!READER_DATA) return;
  var y=reader$('#reader-year').value, host=reader$('#reader-territory'); readerClear(host);
  var groups={}; READER_DATA.years[y].territories.forEach(function(t){(groups[t.region]||(groups[t.region]=[])).push(t);});
  Object.keys(groups).sort().forEach(function(region){
    var g=document.createElement('optgroup'); g.label=region;
    groups[region].forEach(function(t){var o=document.createElement('option');o.value=t.slug;o.textContent=t.name;g.appendChild(o);});
    host.appendChild(g);
  });
  if(y==='2021') host.value='el-gharb';
  renderTerritory();
}

function loadMaroc() {
  var inline=document.getElementById('d-maroc');
  var source=inline?Promise.resolve(JSON.parse(inline.textContent)):fetch('data/maroc.json').then(function(r){if(!r.ok)throw new Error('maroc');return r.json();});
  return source.then(function(d){
    READER_DATA=d; populateTerritories();
    reader$('#reader-year').addEventListener('change',populateTerritories);
    reader$('#reader-territory').addEventListener('change',renderTerritory);
  }).catch(function(){toast('Le Maroc est là','La navigation territoriale n’a pas pu être chargée dans cette prévisualisation.');});
}

function readerKpis() {
  var foot=reader$('#foot-hash'); if(foot)foot.textContent='2016 · 2021 · 2026';
  var host=reader$('#kpis'); if(!host)return; readerClear(host);
  [
    ['92','circonscriptions à explorer'],
    ['2016 · 2021','deux élections pour éprouver la société'],
    ['RNI · PAM · PJD','et les autres partis du paysage marocain'],
    ['2026','le rendez-vous où la société devra choisir avant le réel']
  ].forEach(function(k){var d=readerEl('div','kpi');d.appendChild(readerEl('b','num',k[0]));d.appendChild(readerEl('span',null,k[1]));host.appendChild(d);});
}

function setProgress(st) {
  var completed=Number(st && st.completed || 0), target=Number(st && st.target || 2944);
  var pc=Math.max(0,Math.min(100,target?100*completed/target:0));
  var bar=reader$('#prog-society'); if(bar)bar.style.width=pc+'%';
  var count=reader$('#count-society'); if(count)count.textContent=completed ? Math.round(pc)+' % accomplie' : 'La société prend vie';
  var note=reader$('#count-society-note'); if(note)note.textContent=st && st.ready ? 'l’expérience est ouverte' : 'ouverture des participations';
  var h=reader$('#hero-fid'); if(h)h.textContent=Math.round(pc)+' %';
  var btn=reader$('#join-society'); if(btn){btn.disabled=!(st && st.ready);btn.textContent=st && st.ready?'Participer':'Ouverture très bientôt';}
  var open=st && st.ready;
  document.querySelectorAll('.readonly, .contrib-main .eyebrow').forEach(function(n){n.textContent=open?'Expérience ouverte':'Bientôt ouverte';});
}

function refreshProgress() {
  fetch(READER_API+'/status',{cache:'no-store'}).then(function(r){return r.json();}).then(setProgress).catch(function(){setProgress({completed:0,target:2944,ready:false});});
}

function closeModal() { var m=reader$('.reader-modal'); if(m)m.remove(); }
function modalShell(kicker,title,body) {
  closeModal();
  var overlay=readerEl('div','reader-modal');
  var box=readerEl('div','reader-modal-box');
  var close=readerEl('button','reader-modal-close','×'); close.type='button';close.addEventListener('click',closeModal);
  box.appendChild(close); box.appendChild(readerEl('div','eyebrow',kicker)); box.appendChild(readerEl('h2',null,title)); box.appendChild(readerEl('p','reader-modal-lead',body));
  overlay.appendChild(box); overlay.addEventListener('click',function(e){if(e.target===overlay)closeModal();}); document.body.appendChild(overlay); return box;
}

function assistantChooser() {
  var box=modalShell('Participer','Avec quelle IA souhaitez-vous entrer dans l’expérience ?','Choisissez simplement l’assistant que vous utilisez déjà.');
  var choices=readerEl('div','assistant-choices');
  [['chatgpt','ChatGPT','Continuer avec ChatGPT'],['claude','Claude','Continuer avec Claude'],['other','other','Utiliser une autre IA']].forEach(function(x){
    var b=readerEl('button','assistant-choice');b.type='button';
    var icon=readerEl('span','assistant-icon',x[1]==='other'?'↗':x[1].charAt(0));
    var text=readerEl('span');text.appendChild(readerEl('b',null,x[2]));text.appendChild(readerEl('small',null,x[0]==='other'?'Vous resterez dans le même parcours.':'Vous gardez votre compte habituel.'));
    b.appendChild(icon);b.appendChild(text);b.addEventListener('click',function(){claimContribution(x[0]);});choices.appendChild(b);
  });
  box.appendChild(choices);
  box.appendChild(readerEl('p','reader-modal-foot','Votre mot de passe et vos conversations ne passent jamais par ATLAS.'));
}


function loadGzipJson(url) {
  return fetch(url,{cache:'no-store'}).then(function(r){
    if(!r.ok) throw new Error('asset');
    return r.arrayBuffer();
  }).then(function(buf){
    if(typeof DecompressionStream==='undefined') throw new Error('gzip');
    var stream=new Blob([buf]).stream().pipeThrough(new DecompressionStream('gzip'));
    return new Response(stream).text();
  }).then(function(txt){ return JSON.parse(txt); });
}

function loadContributionFiles(files) {
  if(!files) return Promise.reject(new Error('files'));
  return Promise.all([
    fetch(files.prompt,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('prompt');return r.text();}),
    fetch(files.schema,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('schema');return r.json();}),
    loadGzipJson(files.context),
    loadGzipJson(files.voter)
  ]).then(function(x){
    return {judge_prompt:x[0],output_schema:x[1],context:x[2],voter_batch:x[3]};
  });
}

function contributionPrompt(payload) {
  var prompt=payload && (payload.judge_prompt || payload.prompt) || '';
  var context=payload && payload.context || {};
  var voters=payload && (payload.voter_batch || payload.voters) || {};
  var schema=payload && payload.output_schema || {};
  return [
    'Vous participez à la Société artificielle du Maroc.',
    'Suivez exactement les instructions ci-dessous. N’utilisez aucune information extérieure et ne cherchez pas à identifier l’élection ou les partis.',
    '',prompt,'',
    'CONTEXTE FOURNI :',JSON.stringify(context),'',
    'CITOYENS FOURNIS :',JSON.stringify(voters),'',
    'FORMAT ATTENDU :',JSON.stringify(schema),'',
    'Retournez uniquement les objets demandés, sans commentaire avant ou après.'
  ].join('\n');
}

function copyText(text) {
  if(navigator.clipboard && navigator.clipboard.writeText)return navigator.clipboard.writeText(text);
  return new Promise(function(resolve,reject){var ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();try{document.execCommand('copy')?resolve():reject();}catch(e){reject(e);}ta.remove();});
}

function claimContribution(provider) {
  var choices=reader$('.assistant-choices'); if(choices)choices.classList.add('busy');
  fetch(READER_API+'/claim',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({provider:provider})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw j;return j;});}).then(function(claim){
    ACTIVE_CONTRIBUTION={provider:provider,claim_token:claim.claim_token};
    localStorage.setItem('atlas-active-contribution',JSON.stringify(ACTIVE_CONTRIBUTION));
    return loadContributionFiles(claim.files).then(function(payload){
      return copyText(contributionPrompt(payload)).then(function(){showContributionReady(provider);});
    });
  }).catch(function(){closeModal();toast('L’expérience ouvre très bientôt','Tout est prêt côté interface. Les participations seront activées dès que la société sera ouverte.');});
}

function showContributionReady(provider) {
  var a=ASSISTANTS[provider]||ASSISTANTS.other;
  var box=modalShell('Votre participation est prête','Ouvrez votre IA et laissez-la participer.','Nous avons préparé tout ce dont elle a besoin et l’avons copié pour vous.');
  var steps=readerEl('div','reader-simple-steps');
  [['1','Ouvrez '+a.label],['2','Collez ce qui vient d’être copié et envoyez'],['3','Quand votre IA a terminé, copiez sa réponse et revenez ici']].forEach(function(x){var r=readerEl('div');r.appendChild(readerEl('b',null,x[0]));r.appendChild(readerEl('span',null,x[1]));steps.appendChild(r);});
  box.appendChild(steps);
  if(a.url){var open=readerEl('button','cta primary','Ouvrir '+a.label);open.type='button';open.addEventListener('click',function(){window.open(a.url,'_blank','noopener');});box.appendChild(open);}
  var done=readerEl('button','cta','J’ai terminé avec mon IA');done.type='button';done.addEventListener('click',showPasteResult);box.appendChild(done);
}

function cleanModelText(text) {
  text=String(text||'').trim();
  text=text.replace(/^```(?:json|jsonl)?\s*/i,'').replace(/```\s*$/,'').trim();
  try{var arr=JSON.parse(text);if(Array.isArray(arr))return arr;}catch(e){}
  var rows=[];text.split(/\r?\n/).forEach(function(line){line=line.trim().replace(/^```(?:json)?/,'').replace(/```$/,'');if(!line)return;try{rows.push(JSON.parse(line));}catch(e){}});return rows;
}

function showPasteResult() {
  var box=modalShell('Dernière étape','Ramenez simplement la réponse de votre IA.','Collez-la ci-dessous. Nous nous chargeons du reste.');
  var ta=document.createElement('textarea');ta.className='reader-paste';ta.placeholder='Collez ici la réponse de votre IA…';box.appendChild(ta);
  var submit=readerEl('button','cta primary','Valider ma participation');submit.type='button';submit.addEventListener('click',function(){submitContribution(ta.value,submit);});box.appendChild(submit);
  if(navigator.clipboard&&navigator.clipboard.readText)navigator.clipboard.readText().then(function(t){if(t)ta.value=t;}).catch(function(){});
}

function submitContribution(text,button) {
  var active=ACTIVE_CONTRIBUTION; if(!active){try{active=JSON.parse(localStorage.getItem('atlas-active-contribution')||'null');}catch(e){}}
  if(!active){toast('Recommencez la participation','La participation en cours n’a pas été retrouvée.');closeModal();return;}
  var rows=cleanModelText(text);button.disabled=true;button.textContent='Validation…';
  fetch(READER_API+'/submit',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({claim_token:active.claim_token,model_label:(ASSISTANTS[active.provider]||ASSISTANTS.other).label,output_rows:rows})}).then(function(r){return r.json().then(function(j){if(!r.ok)throw j;return j;});}).then(function(){
    localStorage.removeItem('atlas-active-contribution');ACTIVE_CONTRIBUTION=null;closeModal();refreshProgress();toast('Merci. Vous faites maintenant partie de la société.','Votre contribution a été validée. Les choix collectifs resteront cachés jusqu’à la révélation.');
  }).catch(function(){button.disabled=false;button.textContent='Valider ma participation';toast('La réponse n’a pas pu être validée','Copiez toute la réponse produite par votre IA, puis essayez à nouveau.');});
}

function readerMethod() {
  var host=reader$('#rules'); if(!host)return; readerClear(host);
  [
    ['UNE SOCIÉTÉ, PAS UN SONDAGE','Chaque citoyen est un profil synthétique construit à partir de données démographiques et sociales. Il ne représente aucune personne réelle.'],
    ['LE MAROC POLITIQUE','Les partis, les programmes, le contexte national et les figures locales correspondent à l’environnement de chaque élection.'],
    ['DES CHOIX INDÉPENDANTS','Chaque décision se forme sans voir celle des autres. Le résultat collectif reste fermé jusqu’à la fin.'],
    ['2016 → 2021 → 2026','Le passé sert à éprouver l’expérience. Le vrai rendez-vous est 2026, quand la société devra choisir avant de connaître le résultat réel.']
  ].forEach(function(x){var r=readerEl('div','rule');r.appendChild(readerEl('div','tag',x[0]));r.appendChild(readerEl('h3',null,x[1].split('.')[0]+'.'));r.appendChild(readerEl('p',null,x[1]));host.appendChild(r);});
}



function readerEditorial() {
  var html = {
    '#forces .band-head h2': 'Ce qui pèse <em>dans un vote</em>.',
    '#sanction .band-head h2': 'Quand le bilan <em>change un choix</em>.',
    '#bascule .band-head h2': 'Ceux qui <em>changent d’avis</em>.',
    '#ecoute .band-head h2': 'Programme, candidat, territoire : <em>qu’est-ce qui compte ?</em>',
    '#portraits .band-head h2': 'Des vies. <em>Des choix.</em>'
  };
  Object.keys(html).forEach(function(sel){var n=reader$(sel);if(n)n.innerHTML=html[sel];});
  var text = {
    '#forces .band-head .say': 'Un vote n’a jamais une seule cause. Situation personnelle, habitudes, programme, bilan, territoire : regardez ce qui fait réellement bouger les choix dans la société.',
    '#sanction .band-head .say': 'Le regard sur l’action publique ne pèse pas de la même manière pour tout le monde. Âge, confiance, situation de vie : voyez où le bilan fait vraiment bouger le vote.',
    '#bascule .band-head .say': 'Certains restent fidèles, d’autres hésitent, d’autres basculent. Regardez où les habitudes tiennent — et où elles se fissurent.',
    '#ecoute .band-head .say': 'La politique n’entre pas dans toutes les vies par la même porte. Découvrez ce qui capte l’attention selon les profils.',
    '#portraits .band-head .say': 'Parcourez des citoyens de la société artificielle : des situations différentes, des attentes différentes, des décisions différentes.',
    '#demo-fact': ''
  };
  Object.keys(text).forEach(function(sel){var n=reader$(sel);if(n && sel!=='#demo-fact')n.textContent=text[sel];});
  var demoSub=document.querySelector('#demonstrateur .decision .card:nth-child(3) .sub');
  if(demoSub)demoSub.textContent='Ce qui compte dans sa décision';
}

function publiciseRenderedLabels() {
  var map={'1':'PAM','2':'Autres','3':'RNI','4':'PPS','5':'Mouvement populaire','6':'PJD','7':'Union constitutionnelle','8':'USFP','9':'Istiqlal'};
  document.querySelectorAll('#detail, #verdict-card, #demonstrateur').forEach(function(root){
    var walker=document.createTreeWalker(root,NodeFilter.SHOW_TEXT);var n;
    while((n=walker.nextNode())){if(!n.nodeValue||n.parentNode&&/SCRIPT|STYLE/.test(n.parentNode.nodeName))continue;var next=n.nodeValue
      .replace(/\bliste\s+([1-9])\b/gi,function(_,d){return map[d]||_;})
      .replace(/\bAgents\b/g,'Citoyens')
      .replace(/\bagents\b/g,'citoyens')
      .replace(/\bCet agent\b/g,'Ce citoyen')
      .replace(/\bun agent\b/g,'un citoyen')
      .replace(/\bl’agent\b/g,'le citoyen')
      .replace(/\bl'agent\b/g,'le citoyen');
      /* Assigner nodeValue emet une mutation characterData meme a valeur egale :
         sans ce test, l'observateur ci-dessous se rappelle lui-meme sans fin. */
      if(next!==n.nodeValue)n.nodeValue=next;}
  });
}

function readerBoot() {
  loadMaroc(); readerEditorial(); readerMethod(); readerKpis(); refreshProgress(); setInterval(refreshProgress,60000);
  var join=reader$('#join-society'); if(join)join.addEventListener('click',assistantChooser);
  setTimeout(function(){readerEditorial();readerKpis();refreshProgress();readerMethod();publiciseRenderedLabels();},800);
  var demo=reader$('#demonstrateur');
  var OBS_OPTS={subtree:true,childList:true,characterData:true};
  var obs=new MutationObserver(function(){
    obs.disconnect();
    try{publiciseRenderedLabels();}finally{if(demo)obs.observe(demo,OBS_OPTS);}
  });
  if(demo)obs.observe(demo,OBS_OPTS);
  try{ACTIVE_CONTRIBUTION=JSON.parse(localStorage.getItem('atlas-active-contribution')||'null');}catch(e){}
}

if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',readerBoot);else readerBoot();
