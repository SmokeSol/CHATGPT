/* ATLAS // native anti-abuse participation bridge.
   ATLAS Proof-of-Work protects ticket issuance without any third-party account.
   Submit remains frictionless. No secret or collective directional result is exposed here. */
(function(){
  'use strict';
  window.ATLAS_ABUSE_V1=true;
  var API=(typeof READER_API!=='undefined'&&READER_API)||'https://slgkvmjikvenhkioqglt.supabase.co/functions/v1/agent-society-participation';
  var cfg=null;

  function rid(){
    var k='atlas-browser-id-v1',v=localStorage.getItem(k);
    if(v&&v.length>=16)return v;
    v=(crypto.randomUUID?crypto.randomUUID():Array.from(crypto.getRandomValues(new Uint8Array(24))).map(function(x){return x.toString(16).padStart(2,'0');}).join(''));
    localStorage.setItem(k,v);return v;
  }
  function getJson(url,opt){
    return fetch(url,opt).then(function(r){
      return r.json().catch(function(){return{};}).then(function(j){
        if(!r.ok){var e=new Error(j.error||'REQUEST_FAILED');e.code=j.error;e.status=r.status;throw e;}
        return j;
      });
    });
  }
  function loadConfig(force){
    if(cfg&&!force)return Promise.resolve(cfg);
    return getJson(API+'/security-config',{cache:'no-store'}).then(function(x){cfg=x;return x;});
  }
  function humanError(e){
    var c=e&&e.code||e&&e.message||'';
    if(c==='RATE_LIMITED')return 'La limite de participations a été atteinte pour le moment.';
    if(c==='PARTICIPATION_TICKET_INVALID')return 'Le ticket de participation a expiré. Recommencez la vérification.';
    if(c==='POW_CHALLENGE_EXPIRED')return 'La vérification a expiré. Relancez simplement la participation.';
    if(c==='POW_INVALID')return 'La vérification locale n’a pas abouti. Réessayez.';
    if(c==='PROTECTION_NOT_CONFIGURED')return 'La protection anti-abus n’est pas disponible.';
    return 'La participation n’a pas pu être préparée. Réessayez.';
  }
  function bytesFor(text){return new TextEncoder().encode(text);}
  function leadingZeroBits(buf){
    var a=new Uint8Array(buf),n=0,i,b,mask;
    for(i=0;i<a.length;i++){
      b=a[i];
      if(b===0){n+=8;continue;}
      for(mask=128;(b&mask)===0;mask>>=1)n++;
      break;
    }
    return n;
  }
  function digest(text){return crypto.subtle.digest('SHA-256',bytesFor(text));}
  function solvePow(ch,progress){
    var browser=rid(),prefix=String(ch.nonce)+'|'+browser+'|',counter=0,batchSize=32,lastPaint=0;
    var expires=new Date(ch.expires_at).getTime(),difficulty=Number(ch.difficulty_bits||16);
    function batch(){
      if(Date.now()>expires){var ex=new Error('POW_CHALLENGE_EXPIRED');ex.code='POW_CHALLENGE_EXPIRED';return Promise.reject(ex);}
      var jobs=[],counters=[];
      for(var i=0;i<batchSize;i++){var c=counter+i;counters.push(c);jobs.push(digest(prefix+c));}
      return Promise.all(jobs).then(function(hashes){
        for(var j=0;j<hashes.length;j++){
          if(leadingZeroBits(hashes[j])>=difficulty)return counters[j];
        }
        counter+=batchSize;
        if(counter-lastPaint>=4096){
          lastPaint=counter;
          if(progress)progress(counter,difficulty);
          return new Promise(function(resolve){requestAnimationFrame(resolve);}).then(batch);
        }
        return batch();
      });
    }
    return batch();
  }
  function powTicket(){
    return loadConfig(true).then(function(c){
      if(!c.protection_ready||c.protection_mode!=='POW'){
        var e=new Error('PROTECTION_NOT_CONFIGURED');e.code='PROTECTION_NOT_CONFIGURED';throw e;
      }
      var box=modalShell('Vérification anti-abus','Une vérification locale avant de participer.','Votre navigateur calcule une petite preuve cryptographique. Aucun compte, aucun CAPTCHA et aucun service tiers.');
      var status=readerEl('p','reader-modal-lead','Préparation de la preuve…');box.appendChild(status);
      box.appendChild(readerEl('p','reader-modal-foot','La preuve est liée à ce navigateur et expire rapidement. L’adresse IP brute n’est pas conservée.'));
      return getJson(API+'/challenge',{
        method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({browser_id:rid()})
      }).then(function(ch){
        status.textContent='Vérification en cours…';
        return solvePow(ch,function(attempts,bits){
          status.textContent='Vérification en cours · '+attempts.toLocaleString('fr-FR')+' essais · difficulté '+bits+' bits';
        }).then(function(counter){
          status.textContent='Preuve validée. Création du ticket…';
          return getJson(API+'/ticket',{
            method:'POST',headers:{'content-type':'application/json'},
            body:JSON.stringify({browser_id:rid(),challenge_id:ch.challenge_id,counter:String(counter)})
          });
        });
      });
    });
  }
  function finishClaim(provider,ticket){
    return getJson(API+'/claim',{
      method:'POST',headers:{'content-type':'application/json'},
      body:JSON.stringify({provider:provider,browser_id:rid(),participation_ticket:ticket.participation_ticket})
    }).then(function(claim){
      ACTIVE_CONTRIBUTION={provider:provider,claim_token:claim.claim_token};
      localStorage.setItem('atlas-active-contribution',JSON.stringify(ACTIVE_CONTRIBUTION));
      var pp=claim.payload&&claim.payload.context&&claim.payload.voter_batch
        ?Promise.resolve(claim.payload)
        :(claim.files?loadContributionFiles(claim.files):Promise.reject(new Error('CLAIM_PAYLOAD_MISSING')));
      return pp.then(function(payload){
        return copyText(contributionPrompt(payload)).then(function(){showContributionReady(provider);});
      });
    });
  }
  window.claimContribution=function(provider){
    powTicket().then(function(t){return finishClaim(provider,t);})
      .catch(function(e){closeModal();toast('Participation protégée',humanError(e));});
  };

  function issueMcpTicket(){
    powTicket().then(function(t){
      return copyText(t.participation_ticket).then(function(){
        var box=modalShell('Ticket MCP','Ticket copié.','Dans Claude connecté à ATLAS, appelez l’outil « participer » avec ce ticket. Il est à usage unique et expire rapidement.');
        var code=readerEl('code','reader-ticket',t.participation_ticket.slice(0,8)+'…'+t.participation_ticket.slice(-6));box.appendChild(code);
        box.appendChild(readerEl('p','reader-modal-foot','Ne partagez pas ce ticket : il réserve une seule participation et ne peut pas être réutilisé.'));
      });
    }).catch(function(e){closeModal();toast('Ticket MCP',humanError(e));});
  }
  function addMcpButton(){
    var card=document.querySelector('.contrib-main');
    if(!card||document.getElementById('atlas-mcp-ticket'))return;
    var b=readerEl('button','cta','Utiliser un LLM connecté (MCP)');
    b.type='button';b.id='atlas-mcp-ticket';b.addEventListener('click',issueMcpTicket);card.appendChild(b);
  }
  function protectionState(){
    loadConfig(true).then(function(c){
      var note=document.getElementById('count-society-note');
      if(c.protection_ready&&c.protection_mode==='POW'&&note)note.textContent='protection anti-abus active · sans compte';
      var b=document.getElementById('atlas-mcp-ticket');if(b)b.disabled=!(c.protection_ready&&c.protection_mode==='POW');
    }).catch(function(){});
  }
  if(document.readyState==='loading'){
    document.addEventListener('DOMContentLoaded',function(){addMcpButton();protectionState();});
  }else{addMcpButton();protectionState();}
}());
