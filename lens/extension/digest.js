/* Only acknowledged, genuinely delivered alerts leave the pending digest. */
export function createDigestCheck({request,deliver}) {
  let checking=null;
  return function check() {
    if(checking)return checking;
    checking=(async()=>{
      const report=await request('/api/digest');
      if(!report.enabled)return {...report,notified:0};
      const pending=new Set(report.new_ids||[]);
      const papers=[...new Map((report.papers||[]).filter(p=>pending.has(p.id)&&Number.isFinite(p.match)&&p.match>.8&&p.match<=1).map(p=>[p.id,p])).values()];
      if(!papers.length)return {...report,notified:0};
      const delivered=await deliver(papers);
      if(!delivered)return {...report,notified:0,notification_warning:'Chrome notifications are disabled. Your high-match papers are still in the digest.'};
      await request('/api/digest-delivered',{ids:papers.map(p=>p.id)});
      return {...report,notified:papers.length};
    })().finally(()=>{checking=null;});
    return checking;
  };
}
