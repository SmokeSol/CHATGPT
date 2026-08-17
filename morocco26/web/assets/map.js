function renderLegend(id){
  const counts={HIGH:0,MEDIUM:0,LOW:0};D.constituencies.constituencies.forEach(c=>counts[c.uncertainty.label]=(counts[c.uncertainty.label]||0)+1);
  $(`#${id}`).innerHTML=['HIGH','MEDIUM','LOW'].map(k=>`<div><i style="background:${U_COLOR[k]}"></i>Incertitude ${String(U_LABEL[k]).toLowerCase()} · ${counts[k]}</div>`).join('');
}

function drawCartogram(svgId, cards, colorFn, onClick, selectedId=null, visibleSet=null){
  const svg=document.getElementById(svgId);if(!svg)return;
  const assignments=cartogramAssignments(cards);
  const r=14.4, sx=32, sy=25.5, ox=18, oy=18;
  const pts=(x,y)=>[[x-r,y],[x-r/2,y-r*.86],[x+r/2,y-r*.86],[x+r,y],[x+r/2,y+r*.86],[x-r/2,y+r*.86]].map(p=>p.join(',')).join(' ');
  svg.setAttribute('viewBox','0 0 430 535');
  svg.innerHTML=assignments.map(({card,col,row})=>{const x=ox+col*sx+(row%2?16:0),y=oy+row*sy;const dim=visibleSet&&!visibleSet.has(card.constituency_id);const sel=selectedId===card.constituency_id;const txt=abbr(card.name);return`<g class="hex atlas-hex ${dim?'dimmed':''} ${sel?'selected':''}" data-id="${esc(card.constituency_id)}"><title>${esc(card.name)} — ${esc(card.region)}</title><polygon points="${pts(x,y)}" fill="${colorFn(card)}"></polygon><text x="${x}" y="${y+2}">${esc(txt)}</text></g>`}).join('');
  svg.querySelectorAll('.hex').forEach(g=>g.addEventListener('click',()=>onClick?.(g.dataset.id)));
}
function cartogramAssignments(cards){
  const regs=[...new Set(cards.map(c=>c.region))];
  const exact=regs.every(r=>CARTOGRAM_CELLS[r])&&Object.keys(CARTOGRAM_CELLS).every(r=>cards.some(c=>c.region===r));
  if(!exact)return cards.map((card,i)=>({card,col:i%12,row:Math.floor(i/12)}));
  const out=[];
  for(const [region,cells] of Object.entries(CARTOGRAM_CELLS)){
    const list=cards.filter(c=>c.region===region).sort((a,b)=>a.name.localeCompare(b.name,'fr'));
    list.forEach((card,i)=>{const [col,row]=cells[i]||[0,0];out.push({card,col,row});});
  }
  return out;
}
function abbr(name){
  return String(name||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[^A-Za-z0-9 ]/g,' ').split(/\s+/).filter(Boolean).slice(0,2).map(x=>x.slice(0,2).toUpperCase()).join('');
}

boot();
