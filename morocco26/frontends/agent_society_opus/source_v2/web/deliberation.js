/* ATLAS // Observable deliberation explorer.
   Displays structured model explanations and separately validated packet
   counterfactuals. Never labels generated prose as hidden chain-of-thought. */
(function(){
  'use strict';

  var FACTOR_FR={
    prior_vote_inertia:'mémoire du vote précédent',
    turnout_habit:'habitude de participation',
    personal_economic_conditions:'situation économique vécue',
    employment_and_income:'emploi et revenu',
    social_protection_and_public_services:'protection sociale et services publics',
    policy_program_fit:'adéquation avec le programme',
    governance_and_institutions:'confiance et institutions',
    territorial_rural_fit:'ancrage territorial',
    government_reward_punishment:'récompense ou sanction du bilan',
    local_candidate_context:'offre et candidat local',
    other_verified_context:'autre contexte vérifié'
  };
  var TRANSITION_FR={
    LOYALTY:'fidélité',SWITCH:'bascule',MOBILIZATION:'mobilisation',
    ABSTENTION_CONTINUITY:'abstention persistante',OPEN_FIELD:'choix ouvert'
  };
  var SCENARIO_FR={
    PRIOR_ANCHOR_ALTERNATIVE:'changer l’ancrage du vote passé',
    GOVERNMENT_OUTLOOK_REVERSE:'inverser le regard sur le bilan',
    RUNNER_LOCAL_STRENGTH:'renforcer l’alternative locale',
    TOP_RUNNER_PROGRAM_SWAP:'échanger les offres programmatiques',
    NONINFORMATIVE_METADATA_PLACEBO:'placebo non politique'
  };

  function node(tag,cls,text){var n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
  function pct(v,d){return (Number(v)*100).toFixed(d===undefined?0:d).replace('.',',')+' %';}
  function signed(v){var n=Number(v)*100;return (n>0?'+':'')+n.toFixed(1).replace('.',',')+' pts';}
  function clear(n){while(n.firstChild)n.removeChild(n.firstChild);}
  function addCss(){
    if(document.querySelector('link[data-atlas-deliberation]'))return;
    var link=document.createElement('link');link.rel='stylesheet';link.href='deliberation.css';link.dataset.atlasDeliberation='1';document.head.appendChild(link);
  }
  function addNav(){
    var list=document.querySelector('.jump ul');if(!list||list.querySelector('a[href="#deliberation"]'))return;
    var li=document.createElement('li'),a=document.createElement('a');a.href='#deliberation';a.textContent='Comprendre une décision';li.appendChild(a);
    var social=list.querySelector('a[href="#social"]');if(social&&social.parentNode)list.insertBefore(li,social.parentNode);else list.appendChild(li);
  }
  function insertSection(){
    var existing=document.getElementById('deliberation');if(existing)return existing;
    var anchor=document.getElementById('social')||document.getElementById('forces');
    var section=node('section','band tint');section.id='deliberation';
    section.innerHTML='\
      <div class="wrap">\
        <div class="band-head rise">\
          <h2>Comprendre <em>une décision</em>.</h2>\
          <p class="say">Le modèle décide d’abord sans récit. Un second contexte explique ensuite la décision gelée, preuve par preuve. Des packets modifiés rejouent enfin le même citoyen pour vérifier si le mécanisme annoncé produit réellement le mouvement attendu.</p>\
        </div>\
        <div class="delib-method rise" id="delib-method"></div>\
        <div class="delib-app rise" id="delib-app"></div>\
      </div>';
    if(anchor&&anchor.parentNode)anchor.parentNode.insertBefore(section,anchor);else document.querySelector('.shell').appendChild(section);
    return section;
  }

  function renderPending(prov){
    var method=document.getElementById('delib-method'),app=document.getElementById('delib-app');clear(method);clear(app);
    var badge=node('span','delib-status','PROTOCOLE PRÊT · DONNÉES À PRODUIRE');
    method.appendChild(badge);
    method.appendChild(node('p',null,(prov&&prov.labels&&prov.labels.long)||'La couche de délibération observable n’a pas encore été générée. E0 reste le contrôle déterministe public.'));
    var grid=node('div','delib-method-grid');
    [
      ['1 · Décision D0','Sol fixe participation et probabilités, sans prose explicative.'],
      ['2 · Délibération L0','Un contexte frais explique la décision déjà immuable à partir d’un catalogue de preuves fermé.'],
      ['3 · Ablations CF','Le même citoyen est réellement rejoué après changement du bilan, du candidat local, du programme ou du vote passé.'],
      ['Placebo','Une modification explicitement non politique vérifie que l’agent ne réagit pas au bruit.']
    ].forEach(function(x){var c=node('article','card pad');c.appendChild(node('h3',null,x[0]));c.appendChild(node('p','sub',x[1]));grid.appendChild(c);});
    app.appendChild(grid);
  }

  function option(select,value,label){var o=document.createElement('option');o.value=value;o.textContent=label;select.appendChild(o);}
  function driverCard(driver){
    var c=node('div','delib-driver');
    var head=node('div','delib-driver-head');head.appendChild(node('b',null,FACTOR_FR[driver.factor]||driver.factor));head.appendChild(node('span','delib-strength '+String(driver.strength).toLowerCase(),driver.strength));c.appendChild(head);
    c.appendChild(node('p',null,driver.explanation_fr));
    var ev=node('div','delib-evidence');(driver.evidence_ids||[]).forEach(function(id){ev.appendChild(node('code',null,id));});c.appendChild(ev);return c;
  }
  function miniBar(label,value,cls){
    var row=node('div','delib-prob-row '+(cls||''));var top=node('div','delib-prob-label');top.appendChild(node('span',null,label));top.appendChild(node('b',null,pct(value,1)));row.appendChild(top);var track=node('div','delib-track'),fill=node('i');fill.style.width=Math.max(0,Math.min(100,Number(value)*100))+'%';track.appendChild(fill);row.appendChild(track);return row;
  }

  function renderData(prov,data){
    var method=document.getElementById('delib-method'),app=document.getElementById('delib-app');clear(method);clear(app);
    var agents=Array.isArray(data.agents)?data.agents:[];
    if(!agents.length){renderPending(prov);return;}
    var badge=node('span','delib-status live','G0 · DÉLIBÉRATION OBSERVABLE');method.appendChild(badge);
    method.appendChild(node('p',null,(prov.labels&&prov.labels.long)||'Explications structurées produites après gel des décisions. Les effets causaux sont distingués des récits.'));

    var state={index:0,panel:'*',transition:'*'};
    var controls=node('div','delib-controls');
    var agentSel=document.createElement('select'),panelSel=document.createElement('select'),transitionSel=document.createElement('select');
    option(panelSel,'*','Tous les panels');Array.from(new Set(agents.map(function(a){return a.panel;}))).sort().forEach(function(v){option(panelSel,v,v);});
    option(transitionSel,'*','Toutes les transitions');Array.from(new Set(agents.map(function(a){return a.transition_type;}))).sort().forEach(function(v){option(transitionSel,v,TRANSITION_FR[v]||v);});
    [[panelSel,'Panel'],[transitionSel,'Comportement'],[agentSel,'Citoyen']].forEach(function(pair){var wrap=node('label','delib-control');wrap.appendChild(node('span',null,pair[1]));wrap.appendChild(pair[0]);controls.appendChild(wrap);});
    app.appendChild(controls);
    var display=node('div','delib-display');app.appendChild(display);

    function filtered(){return agents.filter(function(a){return(state.panel==='*'||a.panel===state.panel)&&(state.transition==='*'||a.transition_type===state.transition);});}
    function rebuildAgents(){var list=filtered();clear(agentSel);list.forEach(function(a,i){option(agentSel,String(i),(a.public_label||a.weighted_archetype_id)+' · '+(TRANSITION_FR[a.transition_type]||a.transition_type));});state.index=Math.min(state.index,Math.max(0,list.length-1));agentSel.value=String(state.index);render();}
    function render(){
      var list=filtered();clear(display);if(!list.length){display.appendChild(node('p','note','Aucun citoyen ne correspond aux filtres.'));return;}
      var a=list[state.index]||list[0];
      var header=node('div','delib-header card pad');var left=node('div');left.appendChild(node('div','eyebrow',(a.panel||'PANEL')+' · '+(a.public_territory||a.anonymous_territory_id||'')));left.appendChild(node('h3',null,a.public_label||a.weighted_archetype_id));left.appendChild(node('p','sub',(TRANSITION_FR[a.transition_type]||a.transition_type)+' · certitude '+String(a.decision_certainty_band||'').toLowerCase()));header.appendChild(left);var turn=node('div','delib-turnout');turn.appendChild(node('b',null,pct(a.turnout_probability,0)));turn.appendChild(node('span',null,'participation'));header.appendChild(turn);display.appendChild(header);

      var grid=node('div','delib-grid');
      var decision=node('article','card pad');decision.appendChild(node('h3',null,'Le choix gelé'));decision.appendChild(miniBar(a.top_party_label||a.top_party_id,a.top_party_probability,'top'));decision.appendChild(miniBar(a.runner_up_party_label||a.runner_up_party_id,a.runner_up_probability,'runner'));decision.appendChild(node('p','delib-margin','Marge : '+signed(a.decision_margin)));grid.appendChild(decision);
      var tension=node('article','card pad');tension.appendChild(node('h3',null,'Le conflit central'));tension.appendChild(node('p','delib-quote',a.central_conflict&&a.central_conflict.description_fr||'—'));var pair=node('div','chips');if(a.central_conflict){pair.appendChild(node('span','chip',FACTOR_FR[a.central_conflict.factor_a]||a.central_conflict.factor_a));pair.appendChild(node('span','chip',FACTOR_FR[a.central_conflict.factor_b]||a.central_conflict.factor_b));}tension.appendChild(pair);grid.appendChild(tension);display.appendChild(grid);

      var drivers=node('div','card pad delib-drivers');drivers.appendChild(node('h3',null,'Ce qui pousse réellement la décision'));(a.drivers||[]).forEach(function(d){drivers.appendChild(driverCard(d));});display.appendChild(drivers);

      var narratives=node('div','delib-narratives');[
        ['Pourquoi le premier choix ?',a.why_top_party_fr],['Pourquoi pas l’alternative ?',a.why_not_runner_up_fr],['Pourquoi voter — ou s’abstenir ?',a.turnout_deliberation_fr],['Où demeure l’incertitude ?',a.uncertainty_fr]
      ].forEach(function(x){var c=node('article','card pad');c.appendChild(node('h3',null,x[0]));c.appendChild(node('p',null,x[1]||'—'));narratives.appendChild(c);});display.appendChild(narratives);

      var summary=node('article','card pad delib-summary');summary.appendChild(node('h3',null,'Délibération observable'));summary.appendChild(node('p',null,a.observable_deliberation_summary_fr||'—'));summary.appendChild(node('small',null,'Il s’agit d’une explication produite après la décision, pas de la chaîne de pensée privée du modèle.'));display.appendChild(summary);

      var hypotheses=node('div','delib-grid');var flip=node('article','card pad');flip.appendChild(node('h3',null,'Condition de bascule proposée'));flip.appendChild(node('p',null,a.minimum_flip_hypothesis&&a.minimum_flip_hypothesis.description_fr||'—'));flip.appendChild(node('span','chip',FACTOR_FR[a.minimum_flip_hypothesis&&a.minimum_flip_hypothesis.lever]||'levier non classé'));hypotheses.appendChild(flip);var mob=node('article','card pad');mob.appendChild(node('h3',null,'Condition de participation proposée'));mob.appendChild(node('p',null,a.minimum_turnout_hypothesis&&a.minimum_turnout_hypothesis.description_fr||'—'));mob.appendChild(node('span','chip',FACTOR_FR[a.minimum_turnout_hypothesis&&a.minimum_turnout_hypothesis.lever]||'levier non classé'));hypotheses.appendChild(mob);display.appendChild(hypotheses);

      var cf=a.counterfactual;if(cf){
        var box=node('article','card pad delib-cf');var h=node('div','delib-cf-head');h.appendChild(node('h3',null,'Le récit résiste-t-il au test ?'));h.appendChild(node('span','delib-causal '+String(cf.causal_support_status||'').toLowerCase(),cf.causal_support_status||'—'));box.appendChild(h);box.appendChild(node('p','sub','Chaque ligne rejoue réellement ce même citoyen sous un packet modifié. Le placebo doit rester stable.'));
        var rows=node('div','delib-cf-list');Object.keys(cf.scenarios||{}).sort().forEach(function(key){var s=cf.scenarios[key],r=node('div','delib-cf-row');r.appendChild(node('b',null,SCENARIO_FR[key]||key));r.appendChild(node('span',null,'Alternative '+signed(s.runner_up_delta)+' · participation '+signed(s.turnout_delta)+' · JSD '+Number(s.party_jsd).toFixed(3)));rows.appendChild(r);});box.appendChild(rows);box.appendChild(node('p','delib-placebo '+(cf.placebo_stable?'ok':'bad'),cf.placebo_stable?'Placebo stable : le résultat ne réagit pas au bruit non politique.':'Placebo instable : cette explication ne peut pas être interprétée proprement.'));display.appendChild(box);
      }else{
        var pending=node('article','card pad delib-cf');pending.appendChild(node('h3',null,'Validation contrefactuelle en attente'));pending.appendChild(node('p','sub','Le récit est disponible, mais aucun packet modifié n’a encore rejoué ce citoyen. Il reste une hypothèse, pas une causalité.'));display.appendChild(pending);
      }
    }
    panelSel.addEventListener('change',function(){state.panel=panelSel.value;state.index=0;rebuildAgents();});transitionSel.addEventListener('change',function(){state.transition=transitionSel.value;state.index=0;rebuildAgents();});agentSel.addEventListener('change',function(){state.index=Number(agentSel.value)||0;render();});rebuildAgents();
  }

  function init(){
    addCss();addNav();insertSection();
    fetch('data/deliberation_provenance.json',{cache:'no-store'})
      .then(function(r){if(!r.ok)throw new Error('provenance '+r.status);return r.json();})
      .then(function(prov){if(!prov.available||!prov.data_path){renderPending(prov);return;}return fetch(prov.data_path,{cache:'no-store'}).then(function(r){if(!r.ok)throw new Error('data '+r.status);return r.json();}).then(function(data){renderData(prov,data);});})
      .catch(function(err){console.warn('[atlas] deliberation observatory unavailable',err);renderPending(null);});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
}());
