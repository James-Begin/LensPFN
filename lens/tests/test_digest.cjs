const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const modulePromise=import('data:text/javascript;base64,'+Buffer.from(fs.readFileSync(path.join(__dirname,'../extension/digest.js'),'utf8')).toString('base64'));

test('alerts are opt-in, strictly above 80%, deduplicated and acknowledged after delivery',async()=>{
  const {createDigestCheck}=await modulePromise;
  const calls=[];
  const report={enabled:true,new_ids:['a','b','c','d'],papers:[{id:'a',match:.8},{id:'b',match:.81},{id:'b',match:.9},{id:'c',match:NaN},{id:'d',match:1.5}]};
  const request=async(route,body)=>{calls.push([route,body]);return report;};
  const check=createDigestCheck({request,deliver:async papers=>{assert.deepEqual(papers.map(p=>p.id),['b']);return true;}});
  assert.equal((await check()).notified,1);
  assert.deepEqual(calls[1],['/api/digest-delivered',{ids:['b']}]);
  report.enabled=false;calls.length=0;
  assert.equal((await check()).notified,0);
  assert.equal(calls.length,1);
});

test('denied or failed notifications stay pending and simultaneous checks coalesce',async()=>{
  const {createDigestCheck}=await modulePromise;
  const report={enabled:true,new_ids:['a'],papers:[{id:'a',match:.9}]};
  let reads=0,acks=0;
  const request=async(route)=>{if(route==='/api/digest')reads++;else acks++;return report;};
  const denied=createDigestCheck({request,deliver:async()=>false});
  const results=await Promise.all([denied(),denied()]);
  assert.equal(reads,1);assert.equal(acks,0);assert.match(results[0].notification_warning,/disabled/);
  const failed=createDigestCheck({request,deliver:async()=>{throw Error('delivery failed');}});
  await assert.rejects(failed(),/delivery failed/);assert.equal(acks,0);
});
