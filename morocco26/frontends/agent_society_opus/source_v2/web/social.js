/* ATLAS bootstrap: preserve the social core, then install the anti-abuse bridge last. */
(function(){
  'use strict';
  var core=document.createElement('script');
  core.src='social-core.js';
  core.async=false;
  core.onload=function(){
    var abuse=document.createElement('script');
    abuse.src='abuse.js';
    abuse.async=false;
    document.body.appendChild(abuse);
  };
  document.body.appendChild(core);
}());
