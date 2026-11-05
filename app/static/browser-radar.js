/* RepoWorld browser-only public GitHub issue fallback.
   GitHub REST supports CORS for read-only requests from any origin. This
   module never uses credentials or claims that the server verified the feed. */
(function(){
  'use strict';
  const PUBLIC_REPO=/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/;
  async function loadBrowserIssues(graph){
    if(graph?.source!=='github')throw Error('Browser fallback requires an imported public GitHub city.');
    let parts;
    try{
      const url=new URL(graph.url);
      const value=url.pathname.replace(/^\/+|\/+$/g,'');
      if(url.protocol!=='https:'||url.hostname!=='github.com'||url.search||url.hash||!PUBLIC_REPO.test(value))throw Error('Invalid public repository');
      parts=value.split('/');
    }catch{throw Error('Cannot safely identify the public GitHub repository for the browser issue feed.');}
    const [owner,repo]=parts;
    const url='https://api.github.com/repos/'+encodeURIComponent(owner)+'/'+encodeURIComponent(repo)+'/issues?state=open&sort=updated&direction=desc&per_page=30&page=1';
    const controller=typeof AbortController==='function'?new AbortController():null;
    const timer=controller?setTimeout(()=>controller.abort(),13000):null;
    let response;
    try{response=await fetch(url,{mode:'cors',credentials:'omit',headers:{Accept:'application/vnd.github+json'},...(controller?{signal:controller.signal}:{})});}
    catch{throw Error('GitHub could not be reached directly from this browser. Retry later or configure a server-side GITHUB_TOKEN.');}
    finally{if(timer!==null)clearTimeout(timer);}
    if(response.status===403||response.status===429)throw Error('GitHub is also rate-limiting this browser. Try later or configure a server-side GITHUB_TOKEN.');
    if(!response.ok)throw Error("GitHub's browser issue feed returned HTTP "+response.status+'.');
    let raw;
    try{raw=await response.json();}catch{throw Error('GitHub returned unreadable public issue data.');}
    if(!Array.isArray(raw))throw Error('GitHub returned an unexpected public issue list.');
    const paths=[];
    for(const node of (graph.nodes||[]).slice(0,72)){
      if(typeof node?.id!=='string')continue;
      const indexed=Array.isArray(node.fileIndex)?node.fileIndex:node.files;
      for(const path of (Array.isArray(indexed)?indexed:[]).slice(0,45)){
        if(typeof path==='string'&&path.includes('/')&&path.length>=7&&path.length<=300)
          paths.push({path,nodeId:node.id});
      }
    }
    function mentioned(text,path){
      // Treat reported source paths as lexical hints only, never as evidence
      // that a source file was fetched or that its defect was reproduced.
      const hay=text.toLowerCase(),needle=path.toLowerCase();
      const boundary=/[a-z0-9_./-]/;
      let at=hay.indexOf(needle);
      while(at!==-1){
        const before=at?hay[at-1]:'',after=hay[at+needle.length]||'';
        if((!before||!boundary.test(before))&&(!after||!boundary.test(after)))return true;
        at=hay.indexOf(needle,at+1);
      }
      return false;
    }
    const issues=[];
    const byNode={};
    for(const row of raw.slice(0,30)){
      if(!row||row.pull_request||row.state!=='open'||!Number.isInteger(row.number)||row.number<=0||row.number>1e9)continue;
      const title=String(row.title||'').slice(0,240),body=String(row.body||'').slice(0,1500);
      const text=title+'\n'+body;
      const matches=[],seen=new Set();
      for(const entry of paths){
        if(matches.length>=3)break;
        if(seen.has(entry.nodeId)||!mentioned(text,entry.path))continue;
        seen.add(entry.nodeId);
        matches.push({nodeId:entry.nodeId,confidence:'suggested',path:entry.path,
          evidence:'Browser-fetched issue text mentions this path; server and source not verified.'});
        const bucket=byNode[entry.nodeId]||(byNode[entry.nodeId]={referenced:[],suggested:[]});
        bucket.suggested.push(row.number);
      }
      issues.push({number:row.number,title,body,updatedAt:String(row.updated_at||'').slice(0,35),
        url:'https://github.com/'+owner+'/'+repo+'/issues/'+row.number,
        labels:(Array.isArray(row.labels)?row.labels:[]).slice(0,8).filter(x=>x&&typeof x.name==='string').map(x=>x.name.slice(0,80)),
        snippet:body.replace(/\s+/g,' ').trim().slice(0,240),commentsCount:Number.isInteger(row.comments)?Math.max(0,Math.min(9999,row.comments)):0,
        matches});
    }
    const placed=issues.filter(issue=>issue.matches.length).length;
    return {issues,byNode,total:issues.length,placed,unplaced:issues.length-placed,
      partial:raw.length>=30,browserFallback:true,
      scope:'Read-only GitHub issue feed fetched by this browser, not independently verified by RepoWorld server. First 30 records only; pull requests excluded. Building links are unverified path suggestions. Source evidence and AI issue investigations require authenticated server-side GitHub access.'};
  }

  window.RepoWorldBrowserIssueRadar=loadBrowserIssues;
})();
