/* Local-only transport fixture; the production popup and citation detector run unchanged. */
(() => {
  const session=fetch('/api/session').then(r=>r.json());
  const listeners=[];
  const requestCounts={};
  window.chrome={runtime:{onMessage:{addListener:fn=>listeners.push(fn)},
    async sendMessage(message) {
      if(message.type==='open') {window.open(`/?citation=${encodeURIComponent(window.lensFixtureCitation?.id||'')}`,'lens-citation-panel');return {ok:true};}
      if(message.type==='citation') {window.lensFixtureCitation=message.citation;return {ok:true};}
      if(message.type==='page')return {ok:true};
      if(message.type==='api') {
        const allowed=['/api/paper','/api/paper-match','/api/rate','/api/status','/api/resolve-reference'];
        if(!allowed.includes(message.path.split('?')[0]))return {ok:false,error:'Unsupported fixture request.'};
        requestCounts[message.path]=(requestCounts[message.path]||0)+1;
        document.documentElement.dataset.lensFixtureRequests=JSON.stringify(requestCounts);
        const {token}=await session;
        const response=await fetch(message.path,{method:message.body===undefined?'GET':'POST',
          headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},
          ...(message.body===undefined?{}:{body:JSON.stringify(message.body)})});
        const data=await response.json();
        if(message.path==='/api/rate'&&response.ok)setTimeout(()=>listeners.forEach(fn=>fn({type:'changed'})),0);
        return response.ok?{ok:true,data}:{ok:false,error:data.error};
      }
      return {ok:false,error:'Unsupported fixture action.'};
    }
  }};
})();
