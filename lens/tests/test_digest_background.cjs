const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const modulePromise=import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(__dirname,'../extension/digest.js'),'utf8')).toString('base64'));
async function worker({offline=false,enabled=true,permission='granted'}={}) {
  const {createDigestCheck}=await modulePromise;
  const events={},calls=[],local={token:'test-only-pairing',digestEnabled:enabled};
  const event=name=>({addListener:fn=>events[name]=fn});
  const chrome={runtime:{id:'lens-test',onInstalled:event('install'),onStartup:event('startup'),onMessage:event('message'),sendMessage:async()=>{}},
    storage:{local:{get:async()=>local,set:async data=>Object.assign(local,data),setAccessLevel:async()=>{}},session:{set:async()=>{},get:async()=>({}),remove:async()=>{}}},
    sidePanel:{setPanelBehavior:async()=>{},open:async()=>{}},
    alarms:{onAlarm:event('alarm'),create:async(...args)=>calls.push(['alarm',...args]),clear:async()=>calls.push(['clear'])},
    notifications:{onClicked:event('notification'),getPermissionLevel:async()=>permission,create:async(...args)=>calls.push(['notification',...args])},
    tabs:{query:async()=>[],sendMessage:async()=>{},onActivated:event('activate'),onUpdated:event('updated'),onRemoved:event('removed')}};
  const fetch=async url=>{
    if(offline)throw Error('offline');
    calls.push(['request',url]);
    return {ok:true,json:async()=>url.endsWith('/api/status')?{digest_enabled:enabled}:url.endsWith('/api/digest')?{enabled,new_ids:['2207.01848'],papers:[{id:'2207.01848',title:'TabPFN',match:.91}]}:{ok:true}};
  };
  const source=fs.readFileSync(path.join(__dirname,'../extension/background.js'),'utf8').replace(/^import .*\n/,'');
  vm.runInNewContext(source,{chrome,fetch,AbortSignal,createDigestCheck});
  const message=(payload,sender={id:'lens-test'})=>new Promise(resolve=>events.message(payload,sender,resolve));
  return {events,calls,message};
}
test('browser alarm restores opt-in even when the companion is temporarily offline',async()=>{
  const {events,calls}=await worker({offline:true});events.startup();
  await new Promise(resolve=>setImmediate(resolve));
  assert.equal(calls[0][0],'alarm');assert.equal(calls[0][1],'lens-digest');assert.equal(calls[0][2].periodInMinutes,30);
});
test('native notification delivery precedes acknowledgment and permission denial does not acknowledge',async()=>{
  const ready=await worker();assert.equal((await ready.message({type:'checkDigest'})).data.notified,1);
  const delivered=ready.calls.findIndex(row=>row[0]==='notification');
  const acknowledged=ready.calls.findIndex(row=>row[1]?.endsWith('/api/digest-delivered'));
  assert.ok(delivered>=0&&acknowledged>delivered);
  const denied=await worker({permission:'denied'});const result=await denied.message({type:'checkDigest'});
  assert.match(result.data.notification_warning,/disabled/);assert.equal(denied.calls.filter(row=>row[0]==='notification'||row[1]?.endsWith('/api/digest-delivered')).length,0);
});
test('arXiv content cannot change digest preferences or invoke a digest notification',async()=>{
  const {message,calls}=await worker();const sender={id:'lens-test',tab:{id:7},url:'https://arxiv.org/html/2207.01848'};
  assert.equal((await message({type:'api',path:'/api/digest-preferences',body:{enabled:true}},sender)).ok,false);
  assert.equal((await message({type:'checkDigest'},sender)).ok,false);
  assert.equal(calls.length,0);
});
