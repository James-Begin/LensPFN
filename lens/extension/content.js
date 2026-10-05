(() => {
  if (!/^\/(abs)\//.test(location.pathname)) return;
  const rawId = document.querySelector('meta[name="citation_arxiv_id"]')?.content || location.pathname.split('/abs/')[1];
  const id = rawId?.replace(/v\d+$/, '');
  if (!id || !/^(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})$/.test(id)) return;
  const title = document.querySelector('meta[name="citation_title"]')?.content ||
    document.querySelector('h1.title')?.textContent?.replace(/^Title:\s*/, '').trim() || 'This paper';
  chrome.runtime.sendMessage({type:'page', paper:{id,title}}).catch(() => {});
  const after = document.querySelector('h1.title') || document.querySelector('.abstract');
  if (!after || document.getElementById('lens-arxiv-root')) return;
  const host = document.createElement('div');
  host.id = 'lens-arxiv-root';
  host.setAttribute('role','complementary');
  host.setAttribute('aria-label','Lens paper rating');
  after.insertAdjacentElement('afterend', host);
  const shadow = host.attachShadow({mode:'closed'});
  shadow.innerHTML = `<style>
    :host{display:block;margin:16px 0 18px;font:13px/1.4 -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#332930}
    .lens{display:flex;align-items:center;gap:9px;flex-wrap:wrap;padding:12px 14px;background:#fbf8f9;border:1px solid #e6dfe2;border-radius:5px}
    strong{font:700 17px Georgia,serif;color:#752037;margin-right:5px}
    .prompt{font-size:12px;color:#655b61;margin-right:auto}
    button{font:600 12px -apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;min-height:30px;padding:5px 10px;background:white;color:#483a41;border:1px solid #cfc3c8;border-radius:4px;cursor:pointer}
    button:hover{border-color:#8c253b;color:#8c253b}button:focus-visible{outline:2px solid #8c253b;outline-offset:2px}
    button.active{background:#8c253b;color:#fff;border-color:#8c253b}button:disabled{opacity:.5;cursor:wait}
    .open{border:0;background:none;color:#752037;text-decoration:underline;text-underline-offset:3px}
    .message{flex-basis:100%;color:#8c253b;font-size:12px}
    @media(max-width:700px){.prompt{flex-basis:100%}}
  </style><div class="lens"><strong>Lens</strong><span class="prompt">Make this part of your reading taste</span><button type="button" id="like" aria-pressed="false">Interested</button><button type="button" id="dislike" aria-pressed="false">Not for me</button><button type="button" class="open" id="open">Open shortlist →</button><span class="message" id="message" role="status" hidden></span></div>`;
  const like=shadow.querySelector('#like'), dislike=shadow.querySelector('#dislike'), message=shadow.querySelector('#message');
  let selected=0;
  function call(type, extra={}) { return chrome.runtime.sendMessage({type,...extra}).then(reply => {
    if (!reply?.ok) throw new Error(reply?.error || 'Lens is unavailable.');
    return reply.data;
  }); }
  function paint(value) {
    selected=value;
    like.classList.toggle('active',value===1); dislike.classList.toggle('active',value===-1);
    like.setAttribute('aria-pressed',String(value===1)); dislike.setAttribute('aria-pressed',String(value===-1));
  }
  function notice(text) { message.textContent=text; message.hidden=!text; }
  async function refresh() {
    try { const status=await call('api',{path:'/api/status'}); paint(status.ratings[id] || 0); notice(''); }
    catch { notice('Start the local Lens companion and connect it from the side panel.'); }
  }
  async function setRating(value) {
    like.disabled=dislike.disabled=true;
    try {
      const next=value===selected?0:value;
      const status=await call('api',{path:'/api/rate',body:{id,rating:next}});
      paint(status.ratings[id] || 0);
      notice(next ? 'Saved to your Lens library.' : 'Rating removed.');
    } catch(error) { notice(error.message); }
    finally { like.disabled=dislike.disabled=false; }
  }
  like.addEventListener('click',()=>setRating(1)); dislike.addEventListener('click',()=>setRating(-1));
  shadow.querySelector('#open').addEventListener('click',async()=>{
    try { await call('open'); } catch { notice('Open Lens from the browser toolbar.'); }
  });
  chrome.runtime.onMessage.addListener(message => {if(message.type==='changed') refresh();});
  refresh();
})();
