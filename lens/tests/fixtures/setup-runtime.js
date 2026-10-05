/* Development transport: a dummy pairing key, real API calls to this companion. */
(() => {
  const session=fetch('/api/session').then(response=>response.json());
  const listeners=[];
  let paired=localStorage.getItem('lens-setup-fixture-paired')==='true';
  window.chrome={
    storage:{local:{async get(){return {onboardingComplete:localStorage.getItem('lens-setup-fixture-complete')==='true'};},async set(value){if(value.onboardingComplete)localStorage.setItem('lens-setup-fixture-complete','true');}}},
    runtime:{id:'lens-setup-development-fixture',onMessage:{addListener:callback=>listeners.push(callback)},async sendMessage(message){
      if(message.type==='current'||message.type==='citationCurrent')return {ok:true,data:null};
      if(message.type==='pair') {
        if(message.token!=='lens-preview-pair-key-for-testing-only')return {ok:false,error:'Use the dummy pairing key shown in this local fixture.'};
        paired=true;localStorage.setItem('lens-setup-fixture-paired','true');
        return chrome.runtime.sendMessage({type:'api',path:'/api/status'});
      }
      if(message.type!=='api')return {ok:false,error:'Unsupported fixture action.'};
      if(!paired)return {ok:false,error:'Connect Lens with a pairing key first.'};
      const {token}=await session;
      const response=await fetch(message.path,{method:message.body===undefined?'GET':'POST',headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json'},...(message.body===undefined?{}:{body:JSON.stringify(message.body)})});
      const data=await response.json();
      if(response.ok&&message.body!==undefined)setTimeout(()=>listeners.forEach(callback=>callback({type:'changed'})),0);
      return response.ok?{ok:true,data}:{ok:false,error:data.error};
    }}
  };
  addEventListener('DOMContentLoaded',()=>{
    const note=document.querySelector('#preview-note');note.hidden=false;
    note.textContent='Setup interaction fixture · Dummy pairing key: lens-preview-pair-key-for-testing-only. Writes use this companion’s profile.';
  });
})();
