/* A nonmodal reading suggestion, revealed once the paper's scoring batch ends. */
(() => {
  function create({onRate,onOpen}) {
    const host=document.createElement('lens-recommendations');
    host.hidden=true;
    const root=host.attachShadow({mode:'open'});
    const sheet=new CSSStyleSheet();
    sheet.replaceSync(`
      :host{all:initial;position:fixed;right:20px;bottom:20px;z-index:2147482900;display:block;width:min(390px,calc(100vw - 24px));color:#242329;font:13px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--accent:#85283d;--muted:#615966}
      :host([hidden]),[hidden]{display:none!important}*{box-sizing:border-box}
      .panel{background:#fff;border-radius:8px;box-shadow:0 8px 32px #24232930;max-height:min(620px,calc(100vh - 100px));overflow:auto;overscroll-behavior:contain;padding:20px;scrollbar-color:#bdb1b8 #fff}
      .heading{display:flex;gap:16px;align-items:flex-start}h2{font:23px/1.25 Georgia,"Times New Roman",serif;letter-spacing:-.02em;margin:0;text-wrap:pretty}p{margin:0}.context{margin-top:9px;color:var(--muted);font-size:12px}
      button{font:inherit;color:inherit;background:#fff;cursor:pointer;border:1px solid #c7bfc8;border-radius:6px;min-height:36px;padding:7px 10px}button:hover{background:#f9eef1;color:var(--accent)}button:disabled{opacity:.65;cursor:wait}button:focus-visible,a:focus-visible{outline:2px solid var(--accent);outline-offset:3px}
      .close{border:0;padding:0;flex:none;min-height:30px;width:30px;display:grid;place-items:center}.list{list-style:none;padding:0;margin:18px 0 0}.paper{padding:16px 0;border-top:1px solid #e3dce2}.paper:last-child{padding-bottom:0}.paper-top{display:flex;gap:14px;align-items:baseline}.title{font:18px/1.38 Georgia,"Times New Roman",serif;letter-spacing:-.01em;overflow-wrap:anywhere;color:inherit;text-decoration:none;text-underline-offset:3px}.title:hover{color:var(--accent);text-decoration:underline}.score{color:#3a654b;white-space:nowrap;font-size:12px;font-weight:650;font-variant-numeric:tabular-nums;margin-left:auto}.authors{font-size:12px;color:var(--muted);margin-top:6px}.actions{display:flex;gap:7px;margin-top:10px}.actions button{font-size:12px;font-weight:600}.save[aria-pressed=true]{background:#f9eef1;color:var(--accent);border-color:#b98698}.status{color:var(--muted);font-size:12px;margin-top:16px}.status:empty{display:none}
      .launcher{display:block;margin:10px 0 0 auto;background:#85283d;color:#fff;border:0;box-shadow:0 4px 16px #24232920;font-size:13px;font-weight:600}.launcher:hover{background:#6e2032;color:#fff}.launcher:focus-visible{outline-offset:4px}::selection{background:#eed4dc;color:#4e1725}
      @media(max-width:480px){:host{right:12px;bottom:12px}.panel{padding:18px;max-height:calc(100dvh - 90px)}h2{font-size:22px}}
    `);
    root.adoptedStyleSheets=[sheet];
    root.innerHTML=`<section class="panel" role="dialog" aria-labelledby="lens-top-heading" aria-describedby="lens-top-context" hidden>
      <div class="heading"><h2 id="lens-top-heading">Top matches in this paper</h2><button class="close" aria-label="Close top citation matches"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>
      <p class="context" id="lens-top-context"></p><ul class="list"></ul><p class="status" role="status"></p>
      </section><button class="launcher" aria-expanded="false" aria-controls="lens-top-panel">Lens · Checking citations…</button>`;
    document.body.append(host);
    const $=selector=>root.querySelector(selector);
    const panel=$('.panel');panel.id='lens-top-panel';
    let report=null,ratings={},announced=false,open=false;
    const format=value=>`${value>=.995?'>99':Math.round(value*100)}% match`;
    function reveal({focus=false}={}) {
      if(open)return;
      open=true;panel.hidden=false;$('.launcher').setAttribute('aria-expanded','true');
      if(focus)$('.close').focus();
      if(!matchMedia('(prefers-reduced-motion: reduce)').matches)panel.animate?.([
        {opacity:0,transform:'translateY(8px)'},{opacity:1,transform:'translateY(0)'}
      ],{duration:220,easing:'cubic-bezier(.16,1,.3,1)'});
    }
    function hide() {
      const hadFocus=panel.contains(root.activeElement);
      open=false;panel.hidden=true;$('.launcher').setAttribute('aria-expanded','false');
      if(hadFocus)$('.launcher').focus();
    }
    $('.close').addEventListener('click',hide);
    $('.launcher').addEventListener('click',()=>open?hide():reveal({focus:true}));
    root.addEventListener('keydown',event=>{if(event.key==='Escape'&&open){event.stopPropagation();hide();}});
    function applyRatings() {
      for(const button of root.querySelectorAll('.save')) {
        const saved=ratings[button.dataset.id]===1;
        button.setAttribute('aria-pressed',String(saved));button.textContent=saved?'Saved':'Interested';
        button.setAttribute('aria-label',`${saved?'Remove interest in':'Save'} ${button.dataset.title}`);
      }
    }
    function render() {
      const focused=root.activeElement;
      const id=focused?.closest('.paper')?.querySelector('.save')?.dataset.id;
      const action=focused?.classList.contains('save')?'save':focused?.tagName==='A'?'title':id?'lens':null;
      const list=$('.list');list.replaceChildren();
      const papers=report.papers.filter(row=>ratings[row.paper.id]!==-1).slice(0,5);
      $('.context').textContent=report.papers.length?`${report.papers.length} ${report.papers.length===1?'paper':'papers'} scored from these references${report.unavailable?` · ${report.unavailable} could not be scored`:''}.`:'No citation match scores are available yet. Hover a reference to retry its lookup.';
      if(report.papers.length&&!papers.length)$('.context').textContent='You’ve marked all scored papers Not for me.';
      for(const row of papers) {
        const item=document.createElement('li');item.className='paper';
        const top=document.createElement('div');top.className='paper-top';
        const title=document.createElement('a');title.className='title';title.textContent=row.paper.title;
        title.href=`https://arxiv.org/abs/${row.paper.id.split('/').map(encodeURIComponent).join('/')}`;title.target='_blank';title.rel='noopener noreferrer';
        const score=document.createElement('span');score.className='score';score.textContent=format(row.match);top.append(title,score);
        const authors=document.createElement('p');authors.className='authors';authors.textContent=(row.paper.authors||[]).slice(0,2).join(', ')+(row.paper.authors?.length>2?' et al.':'');
        const actions=document.createElement('div');actions.className='actions';
        const save=document.createElement('button');save.className='save';save.dataset.id=row.paper.id;save.dataset.title=row.paper.title;
        save.addEventListener('click',async()=>{
          save.disabled=true;$('.status').textContent='Saving your rating…';
          try {
            const result=await onRate(row.paper.id,ratings[row.paper.id]===1?0:1);
            updateRatings(result.ratings);$('.status').textContent=ratings[row.paper.id]===1?'Saved to your Interested papers.':'Interest removed.';
          } catch(error){$('.status').textContent=error.message;}
          finally{save.disabled=false;}
        });
        const lens=document.createElement('button');lens.textContent='Open in Lens';lens.addEventListener('click',()=>onOpen(row.citation));
        actions.append(save,lens);item.append(top,authors,actions);list.append(item);
      }
      applyRatings();
      $('.launcher').textContent='Lens · Top citations';
      if(id) {
        const row=[...root.querySelectorAll('.paper')].find(row=>row.querySelector('.save').dataset.id===id);
        (row?.querySelector(action==='lens'?'.actions button:last-child':`.${action}`)||$('.close')).focus();
      }
      return papers.length;
    }
    function updateRatings(next) {
      ratings=next||{};
      if(report) {
        const expected=report.papers.filter(row=>ratings[row.paper.id]!==-1).slice(0,5).map(row=>row.paper.id);
        const rendered=[...root.querySelectorAll('.save')].map(button=>button.dataset.id);
        if(expected.join(',')!==rendered.join(',')){render();return;}
      }
      applyRatings();
    }
    return {host,root,
      begin(){host.hidden=false;$('.launcher').textContent='Lens · Checking citations…';$('.context').textContent='Checking this paper’s references for your best matches…';$('.status').textContent='';panel.setAttribute('aria-busy','true');},
      complete(next){
        report=next;panel.setAttribute('aria-busy','false');host.hidden=false;$('.status').textContent='';const count=render();
        if(count&&!announced){announced=true;reveal();}
      },
      updateRatings,
      hide,
      suspend(){hide();host.hidden=true;},
    };
  }
  globalThis.LensRecommendationPopup={create};
})();
