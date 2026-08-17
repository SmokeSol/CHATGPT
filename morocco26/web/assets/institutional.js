(()=>{
  const text=(el,value)=>{if(el&&el.textContent!==value)el.textContent=value};
  const html=(el,value)=>{if(el&&el.innerHTML!==value)el.innerHTML=value};

  function relabelTab(id,label){
    const el=document.querySelector(`#tab-${id}`);
    if(!el)return;
    const badge=el.querySelector('i');
    const badgeHtml=badge?badge.outerHTML:'';
    if(el.dataset.institutionalLabel!==label){el.innerHTML=`${label}${badgeHtml}`;el.dataset.institutionalLabel=label;}
  }

  function reorderNavigation(){
    const nav=document.querySelector('#nav');
    if(!nav)return;
    ['overview','territories','candidates','parties','signals','methodology','history'].forEach(id=>{
      const tab=document.querySelector(`#tab-${id}`);if(tab)nav.appendChild(tab);
    });
  }

  function polishCandidates(){
    const view=document.querySelector('#view-candidates');
    if(!view)return;
    const head=view.querySelector('.candidates-head');
    if(head){
      const kicker=head.querySelector('.section-kicker');
      const title=head.querySelector('h2');
      const desc=head.querySelector('p');
      text(kicker,'Intelligence territoriale · Candidatures 2026');
      text(title,'Candidatures documentées par circonscription');
      text(desc,'Un répertoire bilingue consolidant annonces officielles et sources de référence, relié aux 92 circonscriptions locales pour une lecture opérationnelle du terrain électoral.');
      const badgeLabel=head.querySelector('.edition-badge span');
      text(badgeLabel,'COUVERTURE DOCUMENTAIRE');
    }

    const separation=view.querySelector('.v1-separation');
    if(separation){
      text(separation.querySelector('.v1-separation-mark'),'395');
      text(separation.querySelector('b'),'Projection de référence');
      text(separation.querySelector('span'),'La projection publiée reste distincte de la documentation des candidatures et évolue uniquement lorsque de nouveaux éléments sont suffisamment établis et quantifiables.');
      text(separation.querySelector('.v1-separation-status'),'RÉFÉRENCE CONSERVÉE');
    }

    view.querySelectorAll('.v1-kpi span').forEach(el=>{
      const replacements={
        'identités territoriales arabes':'territoires bilingues',
        'fiches candidatures':'fiches candidatures',
        'circonscriptions couvertes':'circonscriptions couvertes',
        'partis structurés':'partis documentés',
        'PJD arabe + latin':'fiches PJD bilingues',
        'investiture en attente':'investitures à confirmer'
      };
      if(replacements[el.textContent.trim()])text(el,replacements[el.textContent.trim()]);
    });

    const note=view.querySelector('.candidate-no-impact');
    if(note)html(note,'<b>Lecture documentaire.</b> Les candidatures et investitures sont présentées comme éléments de contexte territorial. La projection n’évolue que lorsque leur effet peut être établi selon une règle explicite et homogène.');
  }

  function polishGlobal(){
    relabelTab('overview','Synthèse');
    relabelTab('territories','Carte territoriale');
    relabelTab('candidates','Candidatures');
    relabelTab('parties','Partis');
    relabelTab('signals','Veille 2026');
    relabelTab('methodology','Méthode');
    relabelTab('history','Historique');
    reorderNavigation();

    const status=document.querySelector('#status-detail');
    if(status && /F0|couche factuelle|delta|V1/i.test(status.textContent)){
      text(status,'Projection territoriale de référence · candidatures 2026 documentées · couverture bilingue des 92 circonscriptions locales.');
    }
    polishCandidates();
  }

  let scheduled=false;
  const schedule=()=>{
    if(scheduled)return;scheduled=true;
    requestAnimationFrame(()=>{scheduled=false;polishGlobal();});
  };
  const observer=new MutationObserver(schedule);
  observer.observe(document.documentElement,{subtree:true,childList:true,characterData:true});
  document.addEventListener('DOMContentLoaded',schedule,{once:true});
  schedule();
})();
