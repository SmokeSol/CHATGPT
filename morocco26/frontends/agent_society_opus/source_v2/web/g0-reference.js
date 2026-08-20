/* ATLAS // public reference switch.
   Before G0 exists, the existing E0 simulator remains visible and is labeled
   as a deterministic control. After a validated G0 promotion, this bridge
   replaces the deterministic slider output with a nearest-neighbour explorer
   over actual GPT-produced decisions from one frozen context. */
(function(){
  'use strict';

  var originalSimulator=window.simulator;
  var provenancePromise=fetch('data/reference_provenance.json',{cache:'no-store'})
    .then(function(r){if(!r.ok)throw new Error('reference provenance '+r.status);return r.json();});

  function provenanceBadge(ref){
    var head=document.querySelector('#demonstrateur .band-head');
    if(!head)return;
    var badge=document.getElementById('atlas-reference-provenance');
    if(!badge){
      badge=document.createElement('p');
      badge.id='atlas-reference-provenance';
      badge.className='note';
      badge.style.marginTop='14px';
      badge.style.maxWidth='920px';
      badge.style.borderLeft='3px solid #6e8bff';
      badge.style.paddingLeft='12px';
      head.appendChild(badge);
    }
    var label=ref&&ref.labels&&ref.labels.long;
    badge.textContent=label||'Provenance de la simulation indisponible.';
    badge.dataset.referenceId=ref&&ref.primary_reference_id||'UNKNOWN';
  }

  function fallback(ref){
    provenanceBadge(ref||{});
    if(typeof originalSimulator==='function')originalSimulator();
  }

  function loadEmpirical(ref){
    if(!ref.g0_available||!ref.g0_simulator_path)return Promise.reject(new Error('G0_NOT_AVAILABLE'));
    return fetch(ref.g0_simulator_path,{cache:'no-store'})
      .then(function(r){if(!r.ok)throw new Error('G0 simulator '+r.status);return r.json();})
      .then(function(data){renderEmpirical(ref,data);});
  }

  window.simulator=function(){
    provenancePromise.then(function(ref){
      provenanceBadge(ref);
      if(ref.primary_reference_kind==='CHATGPT_ACCOUNT_GPT_BASELINE'&&ref.g0_available){
        return loadEmpirical(ref).catch(function(err){
          console.warn('[atlas] G0 empirical explorer unavailable; E0 fallback',err);
          fallback(ref);
        });
      }
      fallback(ref);
    }).catch(function(err){
      console.warn('[atlas] reference provenance unavailable; E0 fallback',err);
      fallback(null);
    });
  };

  function renderEmpirical(ref,data){
    var records=Array.isArray(data.records)?data.records:[];
    if(!records.length)throw new Error('G0_EMPTY_RECORDS');
    var parties=(data.context&&data.context.available_party_ids)||Object.keys(records[0].conditional_party_probabilities||{}).sort();
    var factors=data.factors||window.F||[];
    var govStatus=(data.context&&data.context.gov_status)||{};
    var host=document.getElementById('controls');
    if(!host)throw new Error('G0_CONTROLS_MISSING');
    clear(host);

    var govValues=records.map(function(r){return Number(r.government_evaluation||0);});
    var govMin=Math.min.apply(null,govValues),govMax=Math.max.apply(null,govValues);
    if(!(govMax>govMin)){govMin=-1;govMax=1;}

    function segCtl(label,options,get,set){
      var c=el('div','ctl'),top=el('div','ctl-top'),lb=el('label',null,label),vv=el('span','v','');
      top.appendChild(lb);top.appendChild(vv);c.appendChild(top);
      var group=el('div','seg');
      options.forEach(function(o){
        var b=el('button',null,o[1]);b.type='button';b.dataset.value=String(o[0]);
        b.setAttribute('aria-pressed',String(get()===o[0]));
        b.addEventListener('click',function(){set(o[0]);render();});group.appendChild(b);
      });
      c.appendChild(group);host.appendChild(c);
    }
    function rangeCtl(id,label,get,set,fmt){
      var c=el('div','ctl'),top=el('div','ctl-top'),lb=el('label',null,label),vv=el('span','v',fmt(get()));
      lb.htmlFor=id;vv.id=id+'-v';top.appendChild(lb);top.appendChild(vv);c.appendChild(top);
      var input=document.createElement('input');input.type='range';input.min='0';input.max='100';input.step='1';input.id=id;input.value=String(Math.round(get()*100));
      input.addEventListener('input',function(){set(Number(input.value)/100);render();});c.appendChild(input);host.appendChild(c);
    }
    function confText(v){return v<.28?'très faible':v<.45?'faible':v<.62?'moyenne':v<.8?'élevée':'très élevée';}
    function bilanText(v){return v<.28?'très sévère':v<.45?'sévère':v<.62?'mitigé':v<.8?'favorable':'très favorable';}

    segCtl('Âge',[['18_24','18–24'],['25_34','25–34'],['35_44','35–44'],['45_59','45–59'],['60_PLUS','60 +']],function(){return CTL.age;},function(v){CTL.age=v;});
    segCtl('Milieu',[['URBAN','Urbain'],['RURAL','Rural']],function(){return CTL.mil;},function(v){CTL.mil=v;});
    segCtl('Situation',[['ACTIVE_EMPLOYED','En emploi'],['UNEMPLOYED','Au chômage'],['INACTIVE','Hors emploi']],function(){return CTL.act;},function(v){CTL.act=v;});
    segCtl('Niveau de vie',[[.2,'1'],[.4,'2'],[.6,'3'],[.8,'4'],[1,'5']],function(){return CTL.qv;},function(v){CTL.qv=v;});
    rangeCtl('c-conf','Confiance dans les institutions',function(){return CTL.conf;},function(v){CTL.conf=v;},confText);
    rangeCtl('c-bil','Jugement sur le bilan sortant',function(){return CTL.bil;},function(v){CTL.bil=v;},bilanText);

    var priorCtl=el('div','ctl'),priorTop=el('div','ctl-top'),priorLabel=el('label',null,'La fois précédente, il a…');
    priorLabel.htmlFor='c-prior';priorTop.appendChild(priorLabel);priorCtl.appendChild(priorTop);
    var prior=document.createElement('select');prior.id='c-prior';
    var abstain=document.createElement('option');abstain.value='ABSTAIN';abstain.textContent='Ne s’est pas déplacé';prior.appendChild(abstain);
    parties.forEach(function(q){var o=document.createElement('option');o.value=q;o.textContent='Voté '+q;prior.appendChild(o);});
    if(parties.indexOf(CTL.prior)<0&&CTL.prior!=='ABSTAIN')CTL.prior=parties[0];
    prior.value=CTL.prior;prior.addEventListener('change',function(){CTL.prior=prior.value;render();});priorCtl.appendChild(prior);host.appendChild(priorCtl);

    var source=el('p','sub','G0 · décisions réellement produites par '+(data.model||ref.model||'GPT')+' · contexte gelé '+((data.context&&data.context.label)||'anonymisé')+'. Les contrôles sélectionnent les citoyens GPT les plus proches ; aucune formule E0 ne recalcule leur vote.');
    source.style.marginTop='16px';host.appendChild(source);

    function categoryPenalty(a,b,weight){return a===b?0:weight;}
    function normalizedGov(r){return (Number(r.government_evaluation||0)-govMin)/(govMax-govMin);}
    function distance(r){
      return categoryPenalty(r.age_band,CTL.age,3.5)+
        categoryPenalty(r.urban_rural,CTL.mil,3.0)+
        categoryPenalty(r.activity_status,CTL.act,2.5)+
        categoryPenalty(r.prior_vote_or_abstention,CTL.prior,3.5)+
        2.0*Math.abs(Number(r.latent_national_quintile||.6)-Number(CTL.qv))+
        1.5*Math.abs(Number(r.trust||.5)-Number(CTL.conf))+
        1.5*Math.abs(normalizedGov(r)-Number(CTL.bil));
    }
    function nearest(){
      var ranked=records.map(function(r){return{r:r,d:distance(r)};}).sort(function(a,b){return a.d-b.d||String(a.r.weighted_archetype_id).localeCompare(String(b.r.weighted_archetype_id));});
      var top=ranked.slice(0,Math.min(7,ranked.length)),weights=top.map(function(x){return 1/Math.pow(.08+x.d,2);});
      var mass=weights.reduce(function(a,b){return a+b;},0),pp={},fi={},codes={},part=0,gd=0;
      parties.forEach(function(q){pp[q]=0;});factors.forEach(function(f){fi[f]=0;});
      top.forEach(function(x,i){
        var w=weights[i]/mass,r=x.r;part+=w*Number(r.turnout_probability);gd+=w*Number(r.government_evaluation||0);
        parties.forEach(function(q){pp[q]+=w*Number(r.conditional_party_probabilities[q]||0);});
        factors.forEach(function(f){fi[f]+=w*Number((r.factor_importance||{})[f]||0);});
        (r.reason_codes||[]).forEach(function(c){codes[c]=(codes[c]||0)+w;});
      });
      var bloc=[0,0,0];parties.forEach(function(q){var s=govStatus[q],i=s==='INCUMBENT_COALITION'?0:(s==='OPPOSITION'?1:2);bloc[i]+=pp[q];});
      return{part:part,pp:pp,fi:fi,codes:Object.keys(codes).sort(function(a,b){return codes[b]-codes[a]||a.localeCompare(b);}).slice(0,4),blocs:bloc,gd:gd,top:top};
    }

    function updatePressed(){
      var values=[CTL.age,CTL.mil,CTL.act,String(CTL.qv)];
      var groups=host.querySelectorAll('.seg');
      groups.forEach(function(g,i){g.querySelectorAll('button').forEach(function(b){var v=i===3?String(CTL.qv):String(values[i]);b.setAttribute('aria-pressed',String(b.dataset.value===v));});});
      var cv=document.getElementById('c-conf-v'),bv=document.getElementById('c-bil-v');if(cv)cv.textContent=confText(CTL.conf);if(bv)bv.textContent=bilanText(CTL.bil);
    }
    function render(){
      updatePressed();var d=nearest();drawGauge(d.part);
      var hb=document.getElementById('blocs');clear(hb);d.blocs.forEach(function(v,i){barRow(hb,BLOC_FR[i],v,BLOC_COL[i],pct(v,1),true);});
      var hf=document.getElementById('demo-fact');clear(hf);factors.slice().sort(function(a,b){return d.fi[b]-d.fi[a];}).forEach(function(f){barRow(hf,FACT_SHORT[f]||f,d.fi[f]/.45,FACT_COL[f]||'#6e8bff',pct(d.fi[f],1),true);});
      var hp=document.getElementById('demo-parties');clear(hp);parties.slice().sort(function(a,b){return d.pp[b]-d.pp[a];}).forEach(function(q){var s=govStatus[q],bi=s==='INCUMBENT_COALITION'?0:(s==='OPPOSITION'?1:2),tag=bi===0?'sortante':bi===1?'opposition':'résiduel';barRow(hp,q+' · '+tag,d.pp[q]/.6,BLOC_COL[bi],pct(d.pp[q],1),true);});
      var hc=document.getElementById('demo-codes');clear(hc);d.codes.forEach(function(c){hc.appendChild(el('span','chip '+(CODE_TONE[c]||''),CODE_FR[c]||c));});
      var verdict=document.getElementById('verdict');clear(verdict);var sortedF=factors.slice().sort(function(a,b){return d.fi[b]-d.fi[a];}),lead=parties.slice().sort(function(a,b){return d.pp[b]-d.pp[a];})[0];
      verdict.appendChild(document.createTextNode('Parmi les '+d.top.length+' décisions GPT les plus proches, la participation moyenne est '));
      verdict.appendChild(el('span','hi',pct(d.part,0)));
      verdict.appendChild(document.createTextNode('. La liste la plus probable est '));verdict.appendChild(el('b',null,lead));
      verdict.appendChild(document.createTextNode(' ('+pct(d.pp[lead],0)+'). Les facteurs les plus présents sont '));verdict.appendChild(el('b',null,FACT_SHORT[sortedF[0]]||sortedF[0]));
      verdict.appendChild(document.createTextNode(' puis '));verdict.appendChild(el('b',null,FACT_SHORT[sortedF[1]]||sortedF[1]));
      verdict.appendChild(document.createTextNode('. Il s’agit d’une interpolation entre sorties GPT effectivement gelées, pas d’une nouvelle décision calculée par E0.'));
    }
    render();
  }
}());
