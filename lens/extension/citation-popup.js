/* An isolated reading margin beside the citation, shared by the local interaction fixture. */
(() => {
  function create({onRate,onOpen,onDismiss,onResolve}) {
    const host=document.createElement('lens-citation-popup');
    host.hidden=true;
    const root=host.attachShadow({mode:'open'});
    const css=`
      :host{all:initial;position:fixed;z-index:2147483000;display:block;width:min(380px,calc(100vw - 24px));color:#242329;font:13px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;--accent:#85283d;--muted:#615966;--green:#3a654b}
      :host([hidden]){display:none!important}*{box-sizing:border-box}[hidden]{display:none!important}
      .card{background:#fff;border-radius:8px;box-shadow:0 8px 32px #24232930;max-height:min(480px,calc(100vh - 24px));overflow:auto;padding:18px 20px;overscroll-behavior:contain;scrollbar-color:#bdb1b8 #fff}
      .top{display:flex;gap:12px;align-items:center;margin-bottom:12px}.brand{font:700 21px/1.2 Georgia,"Times New Roman",serif;letter-spacing:-.02em}.match{margin-left:auto;color:var(--green);font-size:12px;font-weight:650;font-variant-numeric:tabular-nums;white-space:nowrap}.close{margin-left:auto;width:30px;height:30px;display:grid;place-items:center;padding:0}.match:not([hidden])+.close{margin-left:0}
      .match.loading{color:var(--muted)}.match-dots{display:inline-flex;gap:3px;margin-left:6px;vertical-align:middle}.match-dots i{width:3px;height:3px;border-radius:50%;background:currentColor;animation:match-pulse 1.1s ease-in-out infinite}.match-dots i:nth-child(2){animation-delay:120ms}.match-dots i:nth-child(3){animation-delay:240ms}.match:not(.loading) .match-dots{display:none}
      @keyframes match-pulse{0%,100%{opacity:.25}50%{opacity:1}}:host([hidden]) .match-dots i{animation:none}@media(prefers-reduced-motion:reduce){.match-dots i{animation:none;opacity:.65}}
      h2{font:20px/1.4 Georgia,"Times New Roman",serif;letter-spacing:-.01em;margin:0 0 8px;text-wrap:pretty}p{margin:0}.authors,.reference{font-size:12px;color:var(--muted);margin:8px 0}.reference{overflow-wrap:anywhere}.abstract{margin-top:12px;font-size:13px}.actions{display:flex;flex-wrap:wrap;gap:7px;margin-top:16px}.actions button,.actions a{min-height:36px;padding:7px 10px;border:1px solid #c7bfc8;border-radius:6px;font-size:12px;font-weight:600}.actions button[aria-pressed=true]{background:#f9eef1;border-color:#b98698;color:var(--accent)}
      .actions a{display:inline-flex;align-items:center}.link-reference{margin-top:12px}.link-reference label{display:block;margin:8px 0 4px}.link-reference input{width:100%;min-height:36px;padding:7px 9px;font:inherit;border:1px solid #c7bfc8;border-radius:6px;color:#242329;background:#fff;caret-color:var(--accent)}.link-reference button{min-height:36px;margin-top:7px;padding:7px 10px;border:1px solid #c7bfc8}.link-reference input:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
      button{font:inherit;cursor:pointer;background:none;color:inherit;border:0;border-radius:6px}button:hover{background:#f9eef1;color:var(--accent)}button:disabled{cursor:wait;opacity:.6}button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--accent);outline-offset:3px}a{color:inherit;text-decoration:none;text-underline-offset:3px}a:hover{color:var(--accent);text-decoration:underline}.feedback{color:var(--muted);font-size:12px;margin-top:10px;min-height:1.6em}details{margin-top:9px;font-size:12px;color:var(--muted)}details p{margin-top:8px;font-size:13px;color:#242329}summary{cursor:pointer}::selection{background:#eed4dc;color:#4e1725}
    `;
    const sheet=new CSSStyleSheet();sheet.replaceSync(css);root.adoptedStyleSheets=[sheet];
    root.innerHTML=`<section class="card" role="dialog" aria-label="Cited paper" aria-describedby="lens-popup-feedback">
      <div class="top"><span class="brand">Lens</span><span class="match" role="status" hidden><span class="match-label"></span><span class="match-dots" aria-hidden="true"><i></i><i></i><i></i></span></span><button class="close" aria-label="Close citation preview"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="m6 6 12 12M18 6 6 18"/></svg></button></div>
      <h2><a class="title" target="_blank" rel="noopener noreferrer"></a></h2><p class="authors" hidden></p><p class="reference"></p><p class="abstract" hidden></p><details hidden><summary>Full abstract</summary><p class="full-abstract"></p></details>
      <div class="actions"><button class="interested" aria-pressed="false" hidden>Interested</button><button class="disliked" aria-pressed="false" hidden>Not for me</button><a class="search" target="_blank" rel="noopener noreferrer" hidden>Find on arXiv</a><button class="open">Open in Lens</button></div><details class="link-reference" hidden><summary>Link an arXiv version</summary><form><label for="lens-reference-id">arXiv URL or paper ID</label><input id="lens-reference-id" class="reference-id" type="text" placeholder="https://arxiv.org/abs/…" autocomplete="off" required><button type="submit">Link paper</button></form></details><p class="feedback" id="lens-popup-feedback" role="status"></p>
    </section>`;
    document.body.append(host);
    const $=selector=>root.querySelector(selector);
    let anchor=null, citation=null, rating=0;
    function position() {
      if(host.hidden||!anchor)return;
      const rect=anchor.getBoundingClientRect();
      const width=host.getBoundingClientRect().width;
      const height=host.getBoundingClientRect().height;
      host.style.left=`${Math.max(12,Math.min(rect.left,innerWidth-width-12))}px`;
      const below=rect.bottom+10;
      const top=below+height<=innerHeight-12?below:rect.top-height-10;
      host.style.top=`${Math.max(12,Math.min(top,innerHeight-height-12))}px`;
    }
    function updateRating(value) {
      rating=value;
      $('.interested').setAttribute('aria-pressed',String(value===1));
      $('.disliked').setAttribute('aria-pressed',String(value===-1));
    }
    function beginMatch() {
      $('.match').hidden=false;$('.match').classList.add('loading');
      $('.match').setAttribute('aria-busy','true');$('.match-label').textContent='Checking match';position();
    }
    function finishMatch() {$('.match').classList.remove('loading');$('.match').setAttribute('aria-busy','false');}
    function hide() {host.hidden=true;}
    $('.close').addEventListener('click',()=>{hide();onDismiss();});
    $('.open').addEventListener('click',onOpen);
    $('.link-reference form').addEventListener('submit',async event=>{
      event.preventDefault();
      const id=LensReferenceParser.fromValue($('.reference-id').value);
      if(!id){$('.feedback').textContent='Paste an arXiv abstract, HTML, PDF URL, or paper ID.';return;}
      const reference=citation.reference;
      const button=$('.link-reference button');button.disabled=true;
      $('.feedback').textContent='Verifying the arXiv paper…';
      try {await onResolve(id);}
      catch(error){if(citation.reference===reference)$('.feedback').textContent=error.message;}
      finally{button.disabled=false;}
    });
    for(const [selector,value] of [['.interested',1],['.disliked',-1]]) {
      $(selector).addEventListener('click',async()=>{
        if(!citation?.id)return;
        const id=citation.id;
        const next=rating===value?0:value;
        $('.interested').disabled=true;$('.disliked').disabled=true;
        $('.feedback').textContent='Saving your rating…';
        try {
          const result=await onRate(id,next);
          if(citation?.id!==id)return;
          updateRating(result.ratings?.[id]||0);
          $('.feedback').textContent=next===0?'Rating removed.':next===1?'Saved as Interested.':'Saved as Not for me.';
        } catch(error) {if(citation?.id===id)$('.feedback').textContent=error.message;}
        finally {if(citation?.id===id){$('.interested').disabled=false;$('.disliked').disabled=false;}}
      });
    }
    window.addEventListener('resize',position);
    document.addEventListener('scroll',position,true);
    return {
      host,root,hide,position,updateRating,beginMatch,
      show(nextAnchor,nextCitation) {
        anchor=nextAnchor;citation=nextCitation;
        const details=citation.details||{};
        $('.title').textContent=details.title||(citation.id?`arXiv:${citation.id}`:'Cited reference');
        $('.title').removeAttribute('href');
        const referenceUrl=LensReferenceParser.safeUrl(details.url,location.href);
        if(referenceUrl)$('.title').href=referenceUrl;
        $('.reference').textContent=citation.reference;
        $('.reference').hidden=false;
        $('.search').href=LensReferenceParser.searchUrl(citation);$('.search').hidden=Boolean(citation.id);
        $('.link-reference').hidden=Boolean(citation.id);$('.link-reference').open=false;
        $('.reference-id').value='';
        for(const selector of ['.authors','.abstract','details','.match','.interested','.disliked'])$(selector).hidden=true;
        $('.interested').disabled=false;$('.disliked').disabled=false;
        $('details').open=false;updateRating(0);finishMatch();
        $('.authors').textContent=details.authors||details.publication||details.year||'';
        $('.authors').hidden=!$('.authors').textContent;
        $('.feedback').textContent=citation.id?'Looking up the paper…':'Looking for an arXiv version of this reference…';
        host.hidden=false;if(citation.id)beginMatch();position();
        if(!matchMedia('(prefers-reduced-motion: reduce)').matches)host.animate?.([
          {opacity:0,transform:'translateY(4px)'},{opacity:1,transform:'translateY(0)'}
        ],{duration:160,easing:'cubic-bezier(.16,1,.3,1)'});
      },
      resolving() {$('.feedback').textContent='Looking up this reference by DOI or title…';position();},
      updateResolution(result) {
        $('.feedback').textContent=result.warning;
        position();
      },
      updatePaper(paper) {
        $('.title').textContent=paper.title;
        $('.title').href=`https://arxiv.org/abs/${paper.id.split('/').map(encodeURIComponent).join('/')}`;
        $('.authors').textContent=(paper.authors||[]).slice(0,3).join(', ')+(paper.authors?.length>3?' et al.':'');
        $('.authors').hidden=!paper.authors?.length;
        $('.reference').hidden=true;
        $('.abstract').textContent=(paper.abstract||'').slice(0,260)+(paper.abstract?.length>260?'…':'');
        $('.abstract').hidden=!paper.abstract;
        $('.full-abstract').textContent=paper.abstract||'';
        $('details').hidden=!(paper.abstract?.length>260);
        $('.interested').hidden=false;$('.disliked').hidden=false;
        $('.feedback').textContent='Estimating your match…';position();
      },
      updateMatch(result) {
        finishMatch();updateRating(result.rating||0);
        $('.match').hidden=typeof result.match!=='number';
        $('.match-label').textContent=typeof result.match==='number'?`${result.match>=.995?'>99':Math.round(result.match*100)}% match`:'';
        $('.feedback').textContent=result.warning||'Based on your other paper ratings.';position();
      },
      error(text) {finishMatch();$('.match').hidden=true;$('.feedback').textContent=text;position();}
    };
  }
  globalThis.LensCitationPopup={create};
})();
