/* ATLAS // anti-abuse public participation bridge.
   Turnstile protects claim issuance; submit stays frictionless.
   No secret and no collective directional result is ever exposed here. */
(function(){
  'use strict';
  window.ATLAS_ABUSE_V1=true;
  var API=(typeof READER_API!=='undefined'&&READER_API)||'https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation';
  var cfg=null,scriptPromise=null;

  function rid(){
    var k='atlas-browser-id-v1',v=localStorage.getItem(k);
    if(v&&v.length>=16)return v;
    v=(crypto.randomUUID?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(24))).map(function(x){return x.toString(16).padStart(2,'0');}).join(''));
    localStorage.setItem(k,v);return v;
  }
  function getJson(url,opt){return fetch(url,opt).then(function(r){return r.json().catch(function(){return{};}).then(function(j){if(!r.ok){var e=new Error(j.error||'REQUEST_FAILED');e.code=j.error;e.status=r.status;throw e;}return j;});});}
  function loadConfig(force){if(cfg&&!force)return Promise.resolve(cfg);return getJson(API+'/security-config',{cache:'no-store'}).then(function(x){cfg=x;return x;});}
  function loadTurnstile(){
    if(window.turnstile)return Promise.resolve(window.turnstile);
    if(scriptPromise)return scriptPromise;
    scriptPromise=new Promise(function(resolve,reject){
      var s=document.createElement('script');s.src='https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit';s.async=true;s.defer=true;
      s.onload=function(){window.turnstile?resolve(window.turnstile):reject(new Error('TURNSTILE_LOAD_FAILED'));};s.onerror=function(){reject(new Error('TURNSTILE_LOAD_FAILED'));};document.head.appendChild(s);
    });return scriptPromise;
  }
  function humanError(e){
    var c=e&&e.code||e&&e.message||'';
    if(c==='PROTECTION_NOT_CONFIGURED')return 'La protection anti-abus n’est pas encore activée.';
    if(c==='RATE_LIMITED')return 'La limite de participations a été atteinte pour le moment.';
    if(c==='PARTICIPATION_TICKET_INVALID')return 'Le ticket de participation a expiré. Recommencez la vérification.';
    if(/^TURNSTILE_/.test(c))return 'La vérification anti-bot n’a pas abouti. Réessayez.';
    return 'La participation n’a pas pu être préparée. Réessayez.';
  }
  function ticketChallenge(provider,forMcp){
    return loadConfig(true).then(function(c){
      if(!c.protection_ready||!c.turnstile_site_key){var e=new Error('PROTECTION_NOT_CONFIGURED');e.code='PROTECTION_NOT_CONFIGURED';throw e;}
      var box=modalShell('Vérification','Une vérification rapide avant de participer.','Elle empêche un robot de remplir artificiellement la société. Aucun compte ATLAS n’est nécessaire.');
      var slot=readerEl('div','atlas-turnstile');slot.setAttribute('aria-label','Vérification anti-abus');box.appendChild(slot);
      var note=readerEl('p','reader-modal-foot','Un ticket unique de quelques minutes sera créé. Il ne contient ni votre adresse IP ni votre identité.');box.appendChild(note);
      return loadTurnstile().then(function(ts){return new Promise(function(resolve,reject){
        var done=false;
        function fail(code){if(done)return;done=true;var e=new Error(code);e.code=code;reject(e);}
        ts.render(slot,{sitekey:c.turnstile_site_key,action:'atlas_claim',appearance:'interaction-only',callback:function(tok){
          if(done)return;done=true;
          getJson(API+'/ticket',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({browser_id:rid(),turnstile_token:tok})}).then(resolve,reject);
        },'error-callback':function(){fail('TURNSTILE_FAILED');},'expired-callback':function(){fail('TURNSTILE_EXPIRED');},'timeout-callback':function(){fail('TURNSTILE_TIMEOUT');}});
      });});
    });
  }
  function finishClaim(provider,ticket){
    return getJson(API+'/claim',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({provider:provider,browser_id:rid(),participation_ticket:ticket.participation_ticket})}).then(function(claim){
      ACTIVE_CONTRIBUTION={provider:provider,claim_token:claim.claim_token};localStorage.setItem('atlas-active-contribution',JSON.stringify(ACTIVE_CONTRIBUTION));
      var pp=claim.payload&&claim.payload.context&&claim.payload.voter_batch?Promise.resolve(claim.payload):(claim.files?loadContributionFiles(claim.files):Promise.reject(new Error('CLAIM_PAYLOAD_MISSING')));
      return pp.then(function(payload){return copyText(contributionPrompt(payload)).then(function(){showContributionReady(provider);});});
    });
  }
  window.claimContribution=function(provider){
    ticketChallenge(provider,false).then(function(t){return finishClaim(provider,t);}).catch(function(e){closeModal();toast('Participation protégée',humanError(e));});
  };

  function issueMcpTicket(){
    ticketChallenge('claude',true).then(function(t){
      return copyText(t.participation_ticket).then(function(){
        var box=modalShell('Ticket MCP','Ticket copié.','Dans Claude connecté à ATLAS, appelez l’outil « participer » avec ce ticket. Il est à usage unique et expire rapidement.');
        var code=readerEl('code','reader-ticket',t.participation_ticket.slice(0,8)+'…'+t.participation_ticket.slice(-6));box.appendChild(code);
        box.appendChild(readerEl('p','reader-modal-foot','Ne partagez pas ce ticket : il réserve une seule participation et ne peut pas être réutilisé.'));
      });
    }).catch(function(e){closeModal();toast('Ticket MCP',humanError(e));});
  }
  function addMcpButton(){
    var card=document.querySelector('.contrib-main');if(!card||document.getElementById('atlas-mcp-ticket'))return;
    var b=readerEl('button','cta','Utiliser un LLM connecté (MCP)');b.type='button';b.id='atlas-mcp-ticket';b.addEventListener('click',issueMcpTicket);card.appendChild(b);
  }
  function protectionState(){
    loadConfig(true).then(function(c){
      var note=document.getElementById('count-society-note');
      if(!c.protection_ready&&note)note.textContent='protection anti-abus à activer';
      var b=document.getElementById('atlas-mcp-ticket');if(b)b.disabled=!c.protection_ready;
    }).catch(function(){});
  }
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){addMcpButton();protectionState();});else{addMcpButton();protectionState();}
}());
