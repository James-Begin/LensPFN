const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../extension/citation-prefetch.js'),'utf8');
function make(request) {
  const context={setTimeout};vm.runInNewContext(source,context);
  return context.LensCitationPrefetch.create(request);
}
const tick=()=>new Promise(resolve=>setTimeout(resolve,5));
async function until(condition) {for(let i=0;i<100;i++){if(condition())return;await tick();}throw new Error('Queue did not settle');}

test('prefetch warms unique citations, limits work to one request, and reuses scores on hover',async()=>{
  const calls=[];let active=0,maxActive=0;
  const queue=make(async path=>{calls.push(path);active++;maxActive=Math.max(maxActive,active);await tick();active--;return {id:new URL(path,'http://localhost').searchParams.get('id'),match:.72};});
  queue.warm(['a','b','a']);
  await until(()=>calls.length===4&&active===0);
  assert.equal(maxActive,1);
  assert.equal((await queue.match('a')).match,.72);
  assert.equal((await queue.paper('b')).id,'b');
  assert.equal(calls.length,4);
});
test('a hovered citation jumps ahead of remaining background metadata work',async()=>{
  const calls=[];let release;
  const gate=new Promise(resolve=>{release=resolve;});
  const queue=make(async path=>{calls.push(path);if(calls.length===1)await gate;return {match:.61};});
  queue.warm(['a','b','c']);await until(()=>calls.length===1);
  const visible=queue.paper('c');release();await visible;
  assert.deepEqual(calls.slice(0,2),['/api/paper?id=a','/api/paper?id=c']);
  await until(()=>calls.length===6);
});
test('refresh invalidates scores while preserving cached metadata',async()=>{
  const calls=[];
  const queue=make(async path=>{calls.push(path);return {match:calls.length/10};});
  const paper=await queue.paper('a');const first=await queue.match('a');
  queue.invalidate();
  assert.equal(await queue.paper('a'),paper);
  const second=await queue.match('a');
  assert.notEqual(first.match,second.match);
  assert.equal(calls.filter(path=>path.startsWith('/api/paper?')).length,1);
  assert.equal(calls.filter(path=>path.startsWith('/api/paper-match?')).length,2);
});
test('temporary unavailable scores can be retried rather than cached forever',async()=>{
  let calls=0;
  const queue=make(async()=>({match:++calls===1?null:.67}));
  assert.equal((await queue.match('a')).match,null);
  assert.equal((await queue.match('a')).match,.67);
});
