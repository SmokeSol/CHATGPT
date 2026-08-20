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
    load('social-core.js',function(){
      load('abuse.js');
    });
  });
}());
