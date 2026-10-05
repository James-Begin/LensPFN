/* A complete scoring batch for this paper, using the shared citation queue. */
(() => {
  function create({prefetch,currentId,onResolved,onComplete}) {
    let generation=0;
    async function run(citations) {
      const current=++generation;
      const unique=new Map(citations.map(citation=>[citation.id?`id:${citation.id}`:`ref:${citation.reference}`,citation]));
      const scoring=new Map();
      async function evaluate(citation) {
        let id=citation.id;
        if(!id) {
          const result=await prefetch.resolve(citation,false);
          if(result.state!=='resolved'||!result.candidates?.[0])return {unavailable:true};
          id=result.candidates[0].id;
          if(current===generation)onResolved(citation.reference,id);
        }
        if(id===currentId)return {skipped:true};
        if(!scoring.has(id))scoring.set(id,(async()=>{
          const outcomes=await Promise.allSettled([prefetch.paper(id,false),prefetch.match(id,false)]);
          if(outcomes.some(result=>result.status==='rejected'))return {unavailable:true};
          const [paper,result]=outcomes.map(outcome=>outcome.value);
          if(paper.id!==id||!Number.isFinite(result.match)||result.match<0||result.match>1)return {unavailable:true};
          return {paper,match:result.match,rating:result.rating||0,citation:{...citation,id}};
        })());
        return scoring.get(id);
      }
      const results=await Promise.allSettled([...unique.values()].map(evaluate));
      if(current!==generation)return;
      const papers=new Map();let unavailable=0;
      for(const result of results) {
        if(result.status==='rejected'||result.value.unavailable){unavailable++;continue;}
        if(result.value.paper)papers.set(result.value.paper.id,result.value);
      }
      onComplete({papers:[...papers.values()].sort((a,b)=>b.match-a.match||a.paper.id.localeCompare(b.paper.id)),unavailable,total:unique.size});
    }
    return {run,invalidate(){generation++;}};
  }
  globalThis.LensCitationRecommendations={create};
})();
