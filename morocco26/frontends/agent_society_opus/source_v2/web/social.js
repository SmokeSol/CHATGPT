/* ATLAS // Société — démonstrateur social public.
   Ceci est une vue illustrative non calibrée. Le protocole scientifique de
   calibration/holdout vit dans source_v2/social/ et n'est jamais remplacé par
   ce code de présentation. Aucun outcome historique n'est lu ici. */
(function () {
  "use strict";

  var RELATIONS = ["family", "work", "neighborhood"];
  var LIVE_API = "https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-social";
  var AGE = {"18_24":21,"25_34":29,"35_44":39,"45_59":51,"60_PLUS":68};
  var state = {config:null, agents:[], selected:0, round:"R1", enabled:{family:true,work:true,neighborhood:true}, liveGraph:null, liveSampleLoaded:false};

  function byId(id){ return document.getElementById(id); }
  function clip(x, lo, hi){ return Math.max(lo, Math.min(hi, x)); }
  function num(x, d){ var n=Number(x); return Number.isFinite(n)?n:d; }
  function same(a,b){ return a!=null && b!=null && a!=="" && b!=="" && a===b ? 1 : 0; }
  function close(a,b,scale){ return clip(1-Math.abs(num(a,.5)-num(b,.5))/scale,0,1); }
  function age(a){ return num(a.ans, AGE[a.age] || 40); }
  function norm(p){ var s=p.reduce(function(a,b){return a+Math.max(1e-12,b);},0); return p.map(function(x){return Math.max(1e-12,x)/s;}); }
  function entropy01(p){
    p=norm(p); if(p.length<2){return 0;}
    var h=0; p.forEach(function(x){h-=x*Math.log(Math.max(1e-12,x));});
    return clip(h/Math.log(p.length),0,1);
  }
  function logit(p){ p=clip(p,1e-9,1-1e-9); return Math.log(p/(1-p)); }
  function sigmoid(x){ return x>=0 ? 1/(1+Math.exp(-x)) : Math.exp(x)/(1+Math.exp(x)); }
  function qv(a){ return num(a.qv,.6); }
  function active(a){ return a.ac==="ACTIVE_EMPLOYED"; }

  function familyScore(a,b){
    var gap=Math.abs(age(a)-age(b));
    var ageFit=Math.max(Math.exp(-gap/16), .82*Math.exp(-Math.abs(gap-27)/15));
    return .27*same(a.fo,b.fo)+.18*close(qv(a),qv(b),.55)+.13*same(a.mi,b.mi)+
      .14*close(num(a.hh,5),num(b.hh,5),6)+.10*same(a.ms,b.ms)+.13*ageFit+.05*(1-same(a.sx,b.sx));
  }
  function workScore(a,b){
    if(!active(a)||!active(b)){return 0;}
    return .38*same(a.se,b.se)+.14*same(a.occ,b.occ)+.14*close(qv(a),qv(b),.55)+
      .10*same(a.mi,b.mi)+.12*same(a.ed,b.ed)+.12*close(age(a),age(b),35);
  }
  function neighborhoodScore(a,b){
    return .38*same(a.mi,b.mi)+.26*close(qv(a),qv(b),.55)+.10*close(age(a),age(b),45)+
      .09*same(a.fo,b.fo)+.08*same(a.se,b.se)+.09*same(a.ed,b.ed);
  }
  var SCORE={family:familyScore,work:workScore,neighborhood:neighborhoodScore};

  function contactsFor(i, relation){
    if(state.liveGraph && state.liveGraph.nodes && state.liveGraph.nodes[i]){return (state.liveGraph.nodes[i].relations[relation]||[]).map(function(e){return {i:Number(e.i),w:Number(e.w)};});}
    var cfg=state.config.relations[relation], a=state.agents[i], scored=[];
    state.agents.forEach(function(b,j){
      if(j===i){return;}
      var s=SCORE[relation](a,b);
      if(s>0.18){scored.push({i:j,s:s});}
    });
    scored.sort(function(x,y){ return y.s-x.s || x.i-y.i; });
    scored=scored.slice(0, cfg.top_k);
    var total=scored.reduce(function(x,e){return x+e.s;},0);
    return total ? scored.map(function(e){return {i:e.i,w:e.s/total};}) : [];
  }

  function exposure(rows, i, relation, field){
    var edges=contactsFor(i,relation); if(!edges.length){return null;}
    if(field==="part"){
      return edges.reduce(function(s,e){return s+e.w*rows[e.i].part;},0);
    }
    var n=rows[i].pp.length, out=new Array(n).fill(0);
    edges.forEach(function(e){ for(var k=0;k<n;k++){ out[k]+=e.w*rows[e.i].pp[k]; } });
    return norm(out);
  }

  function poolParty(self, exps){
    var p=norm(self), sus=.12+.88*entropy01(p), total=0;
    RELATIONS.forEach(function(r){if(state.enabled[r]&&exps[r]){total+=state.config.relations[r].lambda;}});
    if(total<=0){return p.slice();}
    var scale=Math.min(.92,total)/total, score=p.map(function(x){return Math.log(Math.max(1e-12,x));});
    for(var k=0;k<p.length;k++){
      var base=Math.log(Math.max(1e-12,p[k])), d=0;
      RELATIONS.forEach(function(r){
        if(!state.enabled[r]||!exps[r]){return;}
        var lam=state.config.relations[r].lambda*scale;
        d+=lam*(Math.log(Math.max(1e-12,exps[r][k]))-base);
      });
      score[k]=Math.exp(base+sus*d);
    }
    return norm(score);
  }
  function poolTurnout(self, exps){
    var t=clip(self,1e-9,1-1e-9), amb=1-Math.min(1,2*Math.abs(t-.5)), sus=.18+.82*amb, total=0;
    RELATIONS.forEach(function(r){if(state.enabled[r]&&exps[r]!=null){total+=state.config.relations[r].lambda;}});
    if(total<=0){return self;}
    var scale=Math.min(.92,total)/total, base=logit(t), d=0;
    RELATIONS.forEach(function(r){
      if(!state.enabled[r]||exps[r]==null){return;}
      d+=state.config.relations[r].lambda*scale*(logit(exps[r])-base);
    });
    return sigmoid(base+sus*d);
  }
  function round(rows){
    return rows.map(function(row,i){
      var pe={},te={}; RELATIONS.forEach(function(r){pe[r]=exposure(rows,i,r,"pp");te[r]=exposure(rows,i,r,"part");});
      return Object.assign({},row,{pp:poolParty(row.pp,pe),part:poolTurnout(row.part,te)});
    });
  }
  function simulatedRows(){
    var r0=state.agents.map(function(a){return Object.assign({},a,{pp:a.pp.slice()});});
    if(state.round==="R0"){return r0;}
    var r1=round(r0); return state.round==="R2" ? round(r1) : r1;
  }

  function parsePortraits(pack){
    var keys=pack.cles||[], groups={};
    (pack.agents||[]).forEach(function(row){
      var a={}; keys.forEach(function(k,i){a[k]=row[i];});
      if(!Array.isArray(a.pp)||!a.pp.length){return;}
      var key=[a.c,a.e,a.t,a.pp.length].join("|");
      (groups[key]||(groups[key]=[])).push(a);
    });
    var best=[]; Object.keys(groups).sort().forEach(function(k){if(groups[k].length>best.length){best=groups[k];}});
    return best.slice(0,32);
  }

  function el(tag, cls, text){ var n=document.createElement(tag); if(cls){n.className=cls;} if(text!=null){n.textContent=text;} return n; }
  function pct(x){return (100*x).toFixed(1).replace(".0","")+" %";}
  function agentLabel(a,i){ return (a.id||("A"+(i+1)))+" · "+(a.age||"âge ?")+" · "+(a.mi==="RURAL"?"rural":"urbain")+" · "+(a.ac==="ACTIVE_EMPLOYED"?"actif":"hors emploi"); }

  function renderProbabilities(target, row){
    target.textContent="";
    row.pp.forEach(function(p,i){
      var line=el("div","social-prob"), lab=el("b",null,"Q_"+String(i+1).padStart(2,"0"));
      var prog=el("progress"); prog.max=1; prog.value=p; prog.setAttribute("aria-label",lab.textContent+" "+pct(p));
      var out=el("output",null,pct(p)); line.append(lab,prog,out); target.appendChild(line);
    });
  }

  function renderContacts(i){
    var host=byId("social-exposures"); host.textContent="";
    RELATIONS.forEach(function(r){
      var cfg=state.config.relations[r], card=el("div","social-relation"+(state.enabled[r]?"":" off"));
      var head=el("div","social-relation-head"), title=el("b",null,cfg.label), lam=el("span",null,"λ "+cfg.lambda.toFixed(2)); head.append(title,lam); card.appendChild(head);
      var edges=contactsFor(i,r), list=el("div","social-contact-list");
      if(!edges.length){card.appendChild(el("p","social-empty",r==="work"?"Pas d’exposition professionnelle compatible pour ce profil.":"Pas de contact compatible dans cet échantillon public."));}
      else { edges.slice(0,5).forEach(function(e){var row=el("div","social-contact");row.append(el("span",null,agentLabel(state.agents[e.i],e.i)),el("span",null,(e.w*100).toFixed(0)+" %"));list.appendChild(row);}); card.appendChild(list); }
      host.appendChild(card);
    });
  }

  function render(){
    if(!state.agents.length){return;}
    var i=clip(state.selected,0,state.agents.length-1), before=state.agents[i], rows=simulatedRows(), after=rows[i];
    byId("social-before-title").textContent=agentLabel(before,i);
    byId("social-after-title").textContent=state.round==="R0"?"Même état — aucune influence appliquée":("Après "+state.round);
    renderProbabilities(byId("social-before"),before); renderProbabilities(byId("social-after"),after);
    byId("social-before-turnout").textContent=pct(before.part); byId("social-after-turnout").textContent=pct(after.part);
    var l1=before.pp.reduce(function(s,p,k){return s+Math.abs(p-after.pp[k]);},0);
    var maxK=0,maxD=0; before.pp.forEach(function(p,k){var d=Math.abs(p-after.pp[k]);if(d>maxD){maxD=d;maxK=k;}});
    byId("social-shift").textContent=(100*l1).toFixed(1)+" pts";
    byId("social-turnout-shift").textContent=((after.part-before.part)*100).toFixed(1)+" pts";
    byId("social-largest").textContent="Q_"+String(maxK+1).padStart(2,"0");
    byId("social-contacts").textContent=RELATIONS.reduce(function(s,r){return s+(state.enabled[r]?contactsFor(i,r).length:0);},0);
    renderContacts(i);
  }

  function bindControls(){
    var sel=byId("social-agent"); sel.textContent="";
    state.agents.forEach(function(a,i){var o=el("option",null,agentLabel(a,i));o.value=String(i);sel.appendChild(o);});
    sel.addEventListener("change",function(){state.selected=Number(sel.value)||0;render();});
    document.querySelectorAll("[data-social-relation]").forEach(function(btn){
      btn.addEventListener("click",function(){var r=btn.getAttribute("data-social-relation");state.enabled[r]=!state.enabled[r];btn.setAttribute("aria-pressed",state.enabled[r]?"true":"false");render();});
    });
    document.querySelectorAll("[data-social-round]").forEach(function(btn){
      btn.addEventListener("click",function(){state.round=btn.getAttribute("data-social-round");document.querySelectorAll("[data-social-round]").forEach(function(b){b.setAttribute("aria-pressed",b===btn?"true":"false");});render();});
    });
  }

  function fail(err){ var box=byId("social-app"); if(box){box.innerHTML="";box.appendChild(el("p","social-error","La démonstration sociale n’a pas pu charger ses données. Le reste de l’expérience reste disponible."));} if(window.console){console.error("ATLAS social demo",err);} }

  function ensureLiveStatusUI(){
    if(byId("social-live-grid")){return;}
    var notice=document.querySelector(".social-notice"); if(!notice){return;}
    var grid=el("div","social-summary"); grid.id="social-live-grid"; grid.setAttribute("aria-label","Pipeline social réel");
    [["social-live-r0","contributions R0 validées"],["social-live-r12","lots passés en R1 / R2"],["social-live-family","liens famille construits"],["social-live-work","liens collègues construits"],["social-live-neighborhood","liens voisinage construits"]].forEach(function(x){var m=el("div","social-metric");m.append(el("b",null,"0"),el("span",null,x[1]));m.firstChild.id=x[0];grid.appendChild(m);});
    var note=el("p","note","Le flux réel est raccordé. Les choix collectifs restent cachés pendant la collecte pour ne pas influencer les prochaines contributions."); note.id="social-live-note";
    notice.append(grid,note);
  }

  function installContributionBridge(){
    if(typeof window.claimContribution!=="function"||typeof READER_API==="undefined"){return;}
    window.claimContribution=function(provider){
      var choices=typeof reader$==="function"?reader$(".assistant-choices"):null;if(choices){choices.classList.add("busy");}
      fetch(READER_API+"/claim",{method:"POST",headers:{"content-type":"application/json"},body:JSON.stringify({provider:provider})}).then(function(r){return r.json().then(function(j){if(!r.ok){throw j;}return j;});}).then(function(claim){
        ACTIVE_CONTRIBUTION={provider:provider,claim_token:claim.claim_token};localStorage.setItem("atlas-active-contribution",JSON.stringify(ACTIVE_CONTRIBUTION));
        var pp=claim.payload&&claim.payload.context&&claim.payload.voter_batch?Promise.resolve(claim.payload):(claim.files?loadContributionFiles(claim.files):Promise.reject(new Error("CLAIM_PAYLOAD_MISSING")));
        return pp.then(function(payload){return copyText(contributionPrompt(payload)).then(function(){showContributionReady(provider);});});
      }).catch(function(){closeModal();toast("L’expérience ouvre très bientôt","La participation n’a pas pu être préparée. Réessayez dans quelques instants.");});
    };
  }

  function liveAgent(profile,row){
    var keys=Object.keys(row.conditional_party_probabilities||{}).sort();
    return {id:profile.weighted_archetype_id,age:profile.age_band,ans:profile.age_years,sx:profile.sex,mi:profile.urban_rural,ed:profile.education_level,ac:profile.activity_status,qv:profile.latent_national_quintile,pp:keys.map(function(k){return Number(row.conditional_party_probabilities[k]);}),part:Number(row.turnout_probability)};
  }
  function refreshAgentSelect(){
    var sel=byId("social-agent"); if(!sel){return;} sel.textContent=""; state.agents.forEach(function(a,i){var o=el("option",null,agentLabel(a,i));o.value=String(i);sel.appendChild(o);}); state.selected=0; sel.value="0";
  }
  function loadRevealedSample(){
    if(state.liveSampleLoaded){return Promise.resolve(true);}
    return fetch(LIVE_API+"/sample",{cache:"no-store"}).then(function(r){if(!r.ok){throw new Error("social sample "+r.status);}return r.json();}).then(function(sample){
      if(!sample.available||!Array.isArray(sample.profiles)||!Array.isArray(sample.r0)){return false;}
      state.liveGraph=sample.graph; state.agents=sample.profiles.map(function(p,i){return liveAgent(p,sample.r0[i]);}); state.liveSampleLoaded=true; refreshAgentSelect(); render();
      var badge=byId("social-status"); if(badge){badge.textContent="Données participatives révélées · R0 → R1 → R2";}
      var note=byId("social-live-note"); if(note){note.textContent="La révélation est ouverte : ce démonstrateur utilise désormais un vrai lot R0 collecté et son graphe famille / collègues / voisinage. Les boutons recalculent R1/R2 sur ce graphe.";}
      return true;
    }).catch(function(err){if(window.console){console.warn("ATLAS revealed social sample",err);}return false;});
  }

  function setLiveText(id,value){ var n=byId(id); if(n){n.textContent=String(value==null?0:value);} }
  function loadLiveStatus(){
    return fetch(LIVE_API+"/status",{cache:"no-store"}).then(function(r){if(!r.ok){throw new Error("social live "+r.status);}return r.json();}).then(function(s){
      var completed=Number(s.completed||0), socialized=Number(s.socialized||0);
      if(state.config&&s.config&&s.config.lambdas){RELATIONS.forEach(function(r){if(state.config.relations[r]){state.config.relations[r].lambda=Number(s.config.lambdas[r]);}});}
      setLiveText("social-live-r0",completed); setLiveText("social-live-r12",socialized);
      setLiveText("social-live-family",Number(s.family_edges||0));
      setLiveText("social-live-work",Number(s.work_edges||0));
      setLiveText("social-live-neighborhood",Number(s.neighborhood_edges||0));
      var badge=byId("social-status");
      if(badge){badge.textContent=socialized ? (socialized+" contribution"+(socialized>1?"s":"")+" reliée"+(socialized>1?"s":"")+" à R1/R2") : "Pipeline social relié — en attente des premières contributions";badge.classList.add("live");}
      var note=byId("social-live-note");
      if(note){note.textContent=socialized ? "Chaque contribution validée devient un R0 immuable, puis famille, collègues et voisinage produisent R1 et R2 automatiquement. Les directions de vote restent cachées pendant la collecte." : "Le raccordement R0 → famille / collègues / voisinage → R1 → R2 est actif. Les choix collectifs restent cachés pendant la collecte.";}
      if(s.results_revealed){loadRevealedSample();}
      return s;
    }).catch(function(err){
      var note=byId("social-live-note"); if(note){note.textContent="Le démonstrateur reste disponible ; l’état du pipeline réel n’a pas pu être chargé dans cette vue.";}
      if(window.console){console.warn("ATLAS social live status",err);}
      return null;
    });
  }

  function boot(){
    if(!byId("social-app")){return;}
    installContributionBridge(); ensureLiveStatusUI();
    Promise.all([
      fetch("data/social_config.json",{cache:"no-store"}).then(function(r){if(!r.ok){throw new Error("social config "+r.status);}return r.json();}),
      fetch("data/portraits.json").then(function(r){if(!r.ok){throw new Error("portraits "+r.status);}return r.json();})
    ]).then(function(x){
      state.config=x[0]; state.agents=parsePortraits(x[1]); if(state.agents.length<2){throw new Error("not enough compatible public portraits");}
      byId("social-status").textContent=state.config.label; bindControls(); render();
      loadLiveStatus(); window.setInterval(loadLiveStatus,60000);
    }).catch(fail);
  }
  if(document.readyState==="loading"){document.addEventListener("DOMContentLoaded",boot);}else{boot();}
}());
