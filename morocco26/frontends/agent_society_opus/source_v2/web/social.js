/* ATLAS bootstrap: install the public-reference switch, preserve the social core,
   then install the anti-abuse bridge last. */
(function(){
  'use strict';
  function load(src,done){
    var script=document.createElement('script');
    script.src=src;
    script.async=false;
    script.onload=done||function(){};
    document.body.appendChild(script);
  }
  load('g0-reference.js',function(){
    /* app.js loads its JSON asynchronously. Usually the reference switch is in
       place before boot(); if data won the race, rerender the simulator once. */
    if(window.S&&window.SIM&&typeof window.simulator==='function'){
      try{window.simulator();}catch(err){console.warn('[atlas] reference rerender',err);}
    }
    load('social-core.js',function(){
      load('abuse.js');
    });
  });
}());
