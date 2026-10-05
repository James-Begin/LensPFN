const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../extension/onboarding.js'),'utf8').replaceAll('export ','');
const context={};vm.runInNewContext(source,context);
test('new readers see the real training requirements',()=>{
  const summary=context.setupSummary({likes:0,dislikes:0,need_ratings:30,match_after:30,tabpfn_configured:false});
  assert.match(summary,/0 of 30/);assert.match(summary,/3 Interested and 3 Not for me/);
});
test('existing profiles keep their saved rating count and readiness',()=>{
  assert.match(context.setupSummary({likes:12,dislikes:25,need_ratings:0,tabpfn_configured:true}),/37 saved ratings are ready/);
});
test('a ready rating profile without provider access does not claim match scores are ready',()=>{
  assert.doesNotMatch(context.setupSummary({likes:12,dislikes:25,need_ratings:0,tabpfn_configured:false}),/are ready for personalized match scores/);
});
