/* Keep familiar papers in motion; let new entries arrive with a bounded stagger. */
export function replacePaperList(list,rows,{animate=false,reducedMotion=matchMedia('(prefers-reduced-motion: reduce)').matches}={}) {
  const previous=new Map();
  for(const row of list.children) {
    for(const animation of row.getAnimations?.()||[])animation.cancel();
    previous.set(row.dataset.paperId,row.getBoundingClientRect().top);
  }
  list.replaceChildren(...rows);
  if(!animate||reducedMotion)return;
  let entering=0;
  for(const row of rows) {
    if(!row.animate)continue;
    const before=previous.get(row.dataset.paperId);
    if(before===undefined) {
      row.animate([{opacity:0,transform:'translateX(10px)'},{opacity:1,transform:'translateX(0)'}],
        {duration:280,delay:Math.min(entering++*28,168),fill:'backwards',easing:'cubic-bezier(.16,1,.3,1)'});
    } else {
      const delta=before-row.getBoundingClientRect().top;
      if(Math.abs(delta)>1)row.animate([{transform:`translateY(${delta}px)`},{transform:'translateY(0)'}],
        {duration:300,easing:'cubic-bezier(.16,1,.3,1)'});
    }
  }
}
