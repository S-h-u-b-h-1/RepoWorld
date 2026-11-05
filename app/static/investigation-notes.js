/* Offline, evidence-aware investigation notes. No API calls or persistent storage. */
(function () {
  'use strict';
  const PUBLIC_REPO=/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/;
  function clean(value, limit=400) {
    return String(value==null?'':value).replace(/[\u0000-\u001f\u007f]/g,' ')
      .replace(/\s+/g,' ').trim().slice(0,limit);
  }
  function markdown(value, limit=400) {
    return clean(value,limit).replace(/\\/g,'\\\\')
      .replace(/([*_{}\[\]()#+.!|>])/g,'\\$1')
      .replace(new RegExp(String.fromCharCode(96),'g'),String.fromCharCode(92,96));
  }
  function repository(graph) {
    if(graph?.source!=='github')throw Error('Only public GitHub issue reports can be exported.');
    let url;
    try{url=new URL(graph.url);}catch{throw Error('Invalid public repository URL.');}
    const full=url.pathname.replace(/^\/+|\/+$/g,'');
    if(url.protocol!=='https:'||url.hostname!=='github.com'||url.port||url.username||
      url.password||url.search||url.hash||!PUBLIC_REPO.test(full)||
      ['.','..'].includes(full.split('/')[1])){
      throw Error('Invalid public repository URL.');
    }
    return {full,base:'https://github.com/'+full};
  }
  function validSource(entry, base) {
    if(!entry||entry.evidence!=='excerpt'||typeof entry.url!=='string')return null;
    let url;
    try{url=new URL(entry.url);}catch{return null;}
    if(url.protocol!=='https:'||url.hostname!=='github.com'||url.port||
      url.username||url.password||url.search||
      !url.pathname.startsWith(new URL(base).pathname+'/blob/')||
      !/^$|^#L[1-9]\d*(?:-L[1-9]\d*)?$/.test(url.hash))return null;
    const path=clean(entry.file,260);
    if(!path||path.startsWith('/')||path.includes('\\')||
      path.split('/').some(p=>['','.','..'].includes(p)))return null;
    return {path,url:url.href};
  }
  function render({graph,issue,guide=null,browserFallback=false}={}) {
    const {base}=repository(graph);
    const number=issue?.number;
    if(!Number.isSafeInteger(number)||number<1||number>1e9){
      throw Error('An open GitHub issue must be selected.');
    }
    const lines=[
      '# RepoWorld investigation notes — issue #'+number,
      '',
      'Repository: '+base,
      'Issue: '+base+'/issues/'+number,
      'Reported title: '+markdown(issue.title||'Untitled issue',210),
      '',
      '> These are investigation notes, not a reproduced defect or verified fix.',
      '',
      '## Reported context (unverified)'
    ];
    const report=markdown(issue.snippet||issue.body||'No report text available; read the original issue.',470);
    lines.push(report || 'Read the original GitHub issue for details.');
    lines.push('','## Possible code locations');
    const known=new Set((Array.isArray(graph.nodes)?graph.nodes:[])
      .filter(n=>n&&typeof n.id==='string').map(n=>n.id));
    const positions=(Array.isArray(issue.matches)?issue.matches:[])
      .filter(m=>m&&known.has(m.nodeId)).slice(0,5);
    if(!positions.length)lines.push('- None confidently located in this imported sample.');
    for(const place of positions){
      let label='Possible module, not verified';
      if(!browserFallback){
        if(place.confidence==='referenced')label='Path referenced by issue report, not inspected';
        if(place.confidence==='observed'){
          const observed=(Array.isArray(guide?.observedLocations)?guide.observedLocations:[])
            .some(o=>o&&o.evidence==='identifier-observed'&&o.nodeId===place.nodeId&&o.file===place.path);
          label=observed?'Identifier observed in fetched source; issue impact not proven':'Possible module, not verified';
        }
      }else label='Browser-fetched issue suggestion, unverified by server';
      lines.push('- '+label+': '+markdown(place.path||place.nodeId,260));
    }
    lines.push('','## Investigation guidance');
    if(browserFallback){
      lines.push('Issue feed was fetched directly by this browser and not independently checked by RepoWorld.');
      lines.push('No server-side issue investigation or source verification was performed.');
    }else if(guide?.mode==='ai'){
      lines.push('AI-generated suggestion (not verified): '+markdown(guide.answer,680));
    }else if(guide?.mode==='navigation'){
      lines.push('Deterministic file navigation (not a model response): '+markdown(guide.answer,680));
    }else{
      lines.push('No completed investigation guide is available. Check the issue and source directly.');
    }
    const pushList=(heading,items,count)=>{
      if(browserFallback||!Array.isArray(items)||!items.length)return;
      lines.push('',heading);
      for(const item of items.slice(0,count)){
        if(typeof item==='string'&&item.trim())lines.push('- '+markdown(item,280));
      }
    };
    pushList('### Suggested investigation steps',guide?.steps,4);
    pushList('### Proposed tests (not run)',guide?.tests,3);
    const sources=browserFallback?[]:(Array.isArray(guide?.sources)?guide.sources:[])
      .map(e=>validSource(e,base)).filter(Boolean).slice(0,4);
    lines.push('','## Source evidence');
    if(sources.length){
      for(const source of sources){
        lines.push('- Fetched source excerpt, review before citing: '+
          '['+markdown(source.path,260)+']('+source.url+')');
      }
    }else lines.push('- No fetched source excerpts were confirmed for this issue.');
    lines.push('','Scope: '+(browserFallback?'browser-only issue feed; source unverified':
      guide?.sourceScope==='commit-pinned'?'linked sources may be commit-pinned':
      guide?.sourceScope==='live-branch'?'public HEAD/branch evidence can change':
      'sampled repository paths only'));
    lines.push('RepoWorld cannot reproduce bugs, execute fixes or verify tests.');
    return lines.join('\n').slice(0,6500)+'\n';
  }
  window.RepoWorldInvestigationNotes=render;
})();