/* Canonical paper previews and personal match estimates beside HTML citations. */
(() => {
  if (!/^\/html\//.test(location.pathname)) return;
  const paperId = location.pathname.split('/')[2]?.replace(/v\d+$/, '');
  const idPattern = /^(?:\d{4}\.\d{4,5}|[a-zA-Z-]+(?:\.[A-Z]{2})?\/\d{7})$/;
  if (paperId && idPattern.test(paperId)) {
    const title = document.querySelector('meta[name="citation_title"]')?.content ||
      document.querySelector('h1.ltx_title_document, h1')?.textContent?.trim() || 'This paper';
    chrome.runtime.sendMessage({type:'page',paper:{id:paperId,title}}).catch(() => {});
  }

  const style = new CSSStyleSheet();
  style.replaceSync('.lens-citation-active{background:#f9eef1!important;box-shadow:0 0 0 3px #f9eef1!important;text-decoration:underline!important;text-decoration-color:#8c253b!important}');
  document.adoptedStyleSheets=[...document.adoptedStyleSheets,style];

  const resolvedReferences=new Map();

  function citationFor(target) {
    const anchor=target.closest?.('a[href]');
    if(!anchor)return null;
    let url,fragment;
    try {
      url=new URL(anchor.getAttribute('href'),location.href);
      const current=new URL(location.href);
      if(url.origin!==current.origin||url.pathname!==current.pathname)return null;
      fragment=decodeURIComponent(url.hash.slice(1));
    } catch{return null;}
    if(!fragment)return null;
    const targetEntry=document.getElementById(fragment);
    if(!targetEntry)return null;
    const bibEntry=targetEntry.closest('.ltx_bibitem, [role="doc-biblioentry"]');
    if(!bibEntry&&!/\bbib\b|^bib[.\-_]/i.test(fragment))return null;
    const parsed=LensReferenceParser.parse(bibEntry||targetEntry,location.href);
    if(!parsed.reference)return null;
    parsed.id=resolvedReferences.get(parsed.reference)||parsed.id;
    return {anchor,citation:{...parsed,label:anchor.textContent.trim()||'Citation'}};
  }

  let active = null;
  let pending = null;
  let closing = null;
  let ticket = 0;
  let skipFocus=false;
  let citationVersion=null;
  let latestRatings=null;
  let syncing=null;
  let syncAgain=false;
  let warmed=false;
  async function request(path,body) {
    const reply=await chrome.runtime.sendMessage({type:'api',path,...(body===undefined?{}:{body})});
    if(!reply?.ok) {
      const error=new Error(reply?.error||'Open Lens and connect the companion to preview papers.');
      error.offline=Boolean(reply?.offline);throw error;
    }
    return reply.data;
  }
  const prefetch=LensCitationPrefetch.create(request);
  const suggestions=LensRecommendationPopup.create({
    onRate:(id,rating)=>request('/api/rate',{id,rating}),
    onOpen:citation=>{
      chrome.runtime.sendMessage({type:'citation',citation}).catch(()=>{});
      chrome.runtime.sendMessage({type:'open'}).catch(()=>{});
    }
  });
  const recommendations=LensCitationRecommendations.create({prefetch,currentId:paperId,
    onResolved:(reference,id)=>resolvedReferences.set(reference,id),
    onComplete:report=>suggestions.complete(report)
  });
  function collectCitations() {
    const references=new Map();
    for(const anchor of document.querySelectorAll('a[href]')) {
      const found=citationFor(anchor);
      if(found)references.set(found.citation.id?`id:${found.citation.id}`:`ref:${found.citation.reference}`,found.citation);
    }
    return [...references.values()];
  }
  async function syncStatus() {
    if(syncing){syncAgain=true;return syncing;}
    syncing=(async()=>{
      do {
        syncAgain=false;
        try {
          const status=await request('/api/status');
          const version=`${status.citation_session}:${status.citation_revision}:${status.citation_day}:${Boolean(status.tabpfn_configured)}`;
          const changed=citationVersion!==null&&version!==citationVersion;
          citationVersion=version;latestRatings=status.ratings||{};
          suggestions.updateRatings(latestRatings);
          if(changed){recommendations.invalidate();prefetch.invalidate();warmed=false;}
          if(!status.tabpfn_configured||status.need_ratings!==0)suggestions.suspend();
          if(!warmed&&status.tabpfn_configured&&status.need_ratings===0) {
            warmed=true;
            const citations=collectCitations();
            if(citations.length){suggestions.begin();recommendations.run(citations);}
          }
          if(active&&!popup.host.hidden) {
            const found=citationFor(active);
            if(found?.citation.id) {
              popup.updateRating(latestRatings[found.citation.id]||0);
              if(changed)load(found);
            }
          }
        } catch { /* Hover lookup remains usable after pairing or reconnecting. */ }
      } while(syncAgain);
    })().finally(()=>{syncing=null;});
    return syncing;
  }
  const popup=LensCitationPopup.create({
    onRate:async(id,rating)=>request('/api/rate',{id,rating}),
    onOpen:()=>chrome.runtime.sendMessage({type:'open'}).catch(()=>{}),
    onResolve:id=>linkPaper(id),
    onDismiss:()=>{clearTimeout(pending);clearTimeout(closing);ticket++;returnFocus();}
  });
  async function load(found) {
    const current=++ticket;
    if(!found.citation.id) {
      popup.resolving();
      try {
        const result=await prefetch.resolve(found.citation);
        if(current!==ticket)return;
        if(result.state==='resolved'&&result.candidates?.[0])await linkPaper(result.candidates[0].id,found.citation.reference,current);
        else popup.updateResolution(result);
      } catch(error) {if(current===ticket)popup.error(error.message);}
      return;
    }
    const id=found.citation.id;
    popup.beginMatch();
    try {
      const paper=await prefetch.paper(id);
      if(current!==ticket)return;
      popup.updatePaper(paper);
      const match=await prefetch.match(id);
      if(current===ticket)popup.updateMatch({...match,rating:latestRatings?latestRatings[id]||0:match.rating});
    } catch(error) {if(current===ticket)popup.error(error.message);}
  }
  async function linkPaper(id,reference=null,expectedTicket=null) {
    const found=citationFor(active);
    if(!found||(reference&&found.citation.reference!==reference))throw new Error('The highlighted reference changed. Try again.');
    const current=expectedTicket??++ticket;
    const hadPopupFocus=popup.host.contains(document.activeElement);
    const paper=await prefetch.paper(id);
    if(current!==ticket||active!==found.anchor)throw new Error('The highlighted reference changed. Try again.');
    if(paper.id!==id)throw new Error('Lens could not verify that arXiv paper.');
    resolvedReferences.set(found.citation.reference,id);
    const linked={...found, citation:{...found.citation,id}};
    chrome.runtime.sendMessage({type:'citation',citation:linked.citation}).catch(()=>{});
    popup.show(active,linked.citation);popup.updatePaper(paper);
    if(hadPopupFocus)popup.root.querySelector('a.title')?.focus();
    load(linked);
    if(expectedTicket===null){warmed=false;syncStatus();}
    return paper;
  }
  function dismiss() {clearTimeout(pending);clearTimeout(closing);ticket++;popup.hide();}
  function returnFocus() {skipFocus=true;active?.focus();skipFocus=false;}
  function leave() {
    clearTimeout(pending);clearTimeout(closing);
    closing=setTimeout(()=>{
      if(popup.host.matches(':hover')||active?.matches(':hover')||popup.host.contains(document.activeElement)||document.activeElement===active)return;
      dismiss();
    },280);
  }
  function activate(target) {
    const found = citationFor(target);
    if (!found) return;
    clearTimeout(closing);
    if(found.anchor===active&&!popup.host.hidden)return;
    active?.classList.remove('lens-citation-active');
    active = found.anchor;
    active.classList.add('lens-citation-active');
    chrome.runtime.sendMessage({type:'citation',citation:found.citation}).catch(() => {});
    popup.show(active,found.citation);load(found);
  }
  document.addEventListener('pointerover', event => {
    clearTimeout(pending);
    const found = citationFor(event.target);
    if (found) {clearTimeout(closing);pending = setTimeout(() => activate(found.anchor), 180);}
  });
  document.addEventListener('pointerout', event => {
    if (citationFor(event.target)) leave();
  });
  document.addEventListener('focusin', event => {if(!skipFocus)activate(event.target);});
  document.addEventListener('focusout',leave);
  document.addEventListener('keydown',event=>{
    if(event.key==='Escape'&&!popup.host.hidden){dismiss();returnFocus();}
    if(event.key==='ArrowDown'&&document.activeElement===active&&!popup.host.hidden){event.preventDefault();(popup.root.querySelector('a[href]')||popup.root.querySelector('.close')).focus();}
  });
  document.addEventListener('pointerdown',event=>{if(!event.composedPath().includes(popup.host)&&!citationFor(event.target))dismiss();});
  popup.host.addEventListener('pointerenter',()=>{clearTimeout(closing);});
  popup.host.addEventListener('pointerleave',leave);
  chrome.runtime.onMessage.addListener(message=>{
    if(message.type==='changed')syncStatus();
  });
  syncStatus();
})();
