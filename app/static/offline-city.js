/* Explicit, browser-only backup of a public RepoWorld city map (no API). */
(function(){
  'use strict';
  const KEY='repoworld:offline-city:v1';
  const MAX_JSON_CHARS=1_600_000;
  const PUBLIC_REPO=/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/;
  const cap=(x,max)=>String(x??'').replace(/[\u0000-\u001f\u007f]/g,'').slice(0,max);
  const safePath=x=>typeof x==='string'&&x.length>0&&x.length<=400&&
    !x.startsWith('/')&&!x.includes('\\')&&!x.includes('\0')&&
    x.split('/').every(p=>p.length>0&&p!=='.'&&p!=='..'&&!p.startsWith('.env'));
  function extract(graph){
    if(graph?.source!=='github')throw Error('Only real public GitHub cities can be saved.');
    let url;
    try{url=new URL(graph.url);}catch{throw Error('Invalid GitHub city URL.');}
    const full=url.pathname.replace(/^\/+|\/+$/g,'');
    if(url.protocol!=='https:'||url.hostname!=='github.com'||url.port||url.search||url.hash||
      url.username||url.password||!PUBLIC_REPO.test(full)||
      graph.owner!==full.split('/')[0]||typeof graph.name!=='string'||!graph.name.trim()||graph.name.length>120)
      throw Error('Only canonical public owner/repo snapshots can be saved.');
    if(!Array.isArray(graph.nodes)||graph.nodes.length<1||graph.nodes.length>72)
      throw Error('This city exceeds the offline map limit.');
    if(!Array.isArray(graph.edges)||graph.edges.length>1000)
      throw Error('This city has too many sampled links.');
    const nodes=[],known=new Set();
    for(const node of graph.nodes){
      if(!node||!safePath(node.id)||!safePath(node.path||node.id)||
        typeof node.name!=='string'||!node.name.trim()||node.name.length>180||
        !/^[a-z]{2,20}$/.test(node.kind||'')||known.has(node.id))
        throw Error('City contains invalid module metadata.');
      known.add(node.id);
      const files=(Array.isArray(node.files)?node.files:[]).slice(0,16);
      if(!files.every(safePath))throw Error('Invalid public file path.');
      const symbols=(Array.isArray(node.symbols)?node.symbols:[]).slice(0,12)
        .filter(s=>s&&typeof s.name==='string'&&
          s.name.length<=120&&typeof s.file==='string'&&safePath(s.file))
        .map(s=>({name:cap(s.name,120),file:s.file}));
      nodes.push({
        id:node.id,path:node.path||node.id,name:cap(node.name,180),kind:node.kind,
        fileCount:Number.isInteger(node.fileCount)?Math.max(0,Math.min(100000,node.fileCount)):files.length,
        description:cap(node.description,500),
        files,symbols,sampled:node.sampled===true
      });
    }
    const edges=[];
    for(const edge of graph.edges){
      if(!edge||!known.has(edge.source)||!known.has(edge.target))continue;
      edges.push({source:edge.source,target:edge.target,
                  type:cap(edge.type||'import',24)});
    }
    const branch=cap(graph.branch||'HEAD',120);
    if(!branch||/[?#\\]/.test(branch)||branch.includes('..'))throw Error('Invalid public revision.');
    return {
      name:graph.name,owner:graph.owner,url:'https://github.com/'+full,
      source:'github',branch,language:cap(graph.language,60),
      description:cap(graph.description,400),stars:null,
      nodes,edges,
      stats:{modules:nodes.length,files:nodes.reduce((sum,n)=>sum+n.fileCount,0),
        dependencies:edges.length,inspectedSources:0,partial:true},
      warnings:['Browser-only cached public city. Map data may be outdated. Re-import for live GitHub issues, AI and source inspection.']
    };
  }
  function save(graph,storage){
    if(!storage?.setItem)throw Error('Browser storage is unavailable.');
    const value={version:1,savedAt:Date.now(),graph:extract(graph)};
    const serialized=JSON.stringify(value);
    if(serialized.length>MAX_JSON_CHARS)throw Error('This city is too large for a browser backup.');
    try{storage.setItem(KEY,serialized);}
    catch{throw Error('Browser storage is full or blocked; no offline backup was created.');}
    return {fullName:new URL(value.graph.url).pathname.slice(1),savedAt:value.savedAt};
  }
  function read(storage){
    try{
      const data=storage?.getItem?.(KEY);
      if(!data||data.length>MAX_JSON_CHARS)return null;
      const parsed=JSON.parse(data);
      if(parsed?.version!==1||!Number.isFinite(parsed.savedAt))return null;
      return {savedAt:parsed.savedAt,graph:extract(parsed.graph)};
    }catch{return null;}
  }
  // A portable JSON file is a manually transferred *offline public map*,
  // never a trusted server snapshot or a way to resurrect an old guest cookie.
  const FILE_FORMAT='repoworld-public-city-v1';
  function fileRecord(graph, savedAt=Date.now()){
    const safe=extract(graph);
    const value={format:FILE_FORMAT,version:1,
      savedAt:Number.isFinite(savedAt)&&savedAt>0?savedAt:Date.now(),graph:safe};
    const json=JSON.stringify(value);
    if(json.length>MAX_JSON_CHARS)throw Error('Public city file exceeds the size limit.');
    return {value,json};
  }
  function exportText(storage){
    const snapshot=read(storage);
    if(!snapshot)throw Error('Save a public city in this browser before downloading it.');
    // Re-sanitize rather than trusting localStorage contents, and never include
    // guest IDs, session cookies, CSRF tokens, model answers, or issue reports.
    return fileRecord(snapshot.graph,snapshot.savedAt).json;
  }
  function importText(input){
    if(typeof input!=='string'||input.length<20||input.length>MAX_JSON_CHARS)
      throw Error('Invalid or oversized RepoWorld public-city file.');
    let parsed;
    try{parsed=JSON.parse(input);}catch{throw Error('The city file is not valid JSON.');}
    if(!parsed||parsed.format!==FILE_FORMAT||parsed.version!==1||
       !Number.isFinite(parsed.savedAt)||parsed.savedAt<=0)
      throw Error('This is not a supported RepoWorld public-city file.');
    const record=fileRecord(parsed.graph,parsed.savedAt).value;
    return {savedAt:record.savedAt,graph:record.graph};
  }
  function restoreText(input,storage){
    const backup=importText(input);
    if(!storage?.setItem)throw Error('Browser storage is unavailable.');
    const safe=JSON.stringify({version:1,savedAt:backup.savedAt,graph:backup.graph});
    if(safe.length>MAX_JSON_CHARS)throw Error('This city is too large for browser storage.');
    try{storage.setItem(KEY,safe);}
    catch{throw Error('Browser storage is full or blocked; the city was not restored.');}
    return backup;
  }
  function fileName(graph){
    const safe=extract(graph);
    const repo=new URL(safe.url).pathname.split('/').filter(Boolean);
    return 'repoworld-'+repo.join('-').replace(/[^a-zA-Z0-9_.-]/g,'-')+'.json';
  }
  function clear(storage){
    try{storage?.removeItem?.(KEY);return true;}catch{return false;}
  }
  window.RepoWorldOfflineCity={save,read,clear,exportText,importText,restoreText,fileName,
    maxFileChars:MAX_JSON_CHARS,maxFileBytes:5_000_000};
})();