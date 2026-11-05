/* RepoWorld v0.3 app-controller tests, no network or browser required. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/app.js'),'utf8');
const browserIssueSource=fs.readFileSync(path.join(__dirname,'../static/browser-radar.js'),'utf8');
const issueNotesSource=fs.readFileSync(path.join(__dirname,'../static/investigation-notes.js'),'utf8');
const GRAPH={name:'Demo City',owner:'testowner',branch:'main',source:'github',url:'https://github.com/testowner/demo-city',
  nodes:[{id:'web',name:'Web',kind:'frontend',path:'apps/web',fileCount:6,files:['apps/web/index.ts'],description:'Website'},
    {id:'api',name:'API',kind:'api',path:'services/api',fileCount:5,files:['services/api/index.py'],description:'API service'}],
  edges:[{source:'web',target:'api',type:'import'}],
  stats:{modules:2,files:11,dependencies:1,inspectedSources:2},warnings:[]};
class FakeElement{
  constructor(tag='div'){
    this.tagName=tag.toUpperCase();this.textContent='';this.value='';this.style={};this.hidden=false;this.disabled=false;
    this.children=[];this.dataset={};this.listeners={};this.attrs=new Map();this.classNames=new Set();this.src='';
    this.classList={add:n=>this.classNames.add(n),remove:n=>this.classNames.delete(n),
      toggle:(n,force)=>{const on=force===undefined?!this.classNames.has(n):force;if(on)this.classNames.add(n);else this.classNames.delete(n);return on;},
      contains:n=>this.classNames.has(n)};
  }
  addEventListener(type,callback){this.listeners[type]=callback;}
  setAttribute(n,v){this.attrs.set(n,v);}
  getAttribute(n){return this.attrs.get(n);}
  append(...children){this.children.push(...children);}
  replaceChildren(...children){this.children=[...children];}
  showModal(){this.hidden=false;this.open=true;}
  close(){this.hidden=true;this.open=false;}
  focus(){}
  closest(){return null;}
}
function makeApp({authenticated=true,active=true,assistantResult=null,multipleIssues=false,importFailure=null,issueFailure=null,issueFailureMessage=null,browserIssues=null,browserIssueError=null,sourceLeadResult=null,sourceLeadError=null,deepLink='',storedLastRepo=null,storageThrows=false}={}){
  const elements=new Map();
  const el=id=>{if(!elements.has(id))elements.set(id,new FakeElement(['importInput','aiQuestion','searchInput','assistantQuestion'].includes(id)?'input':'div'));return elements.get(id);};
  const layers=['structure','dependencies','flows','hotspots'].map(n=>Object.assign(new FakeElement('button'),{dataset:{layer:n}}));
  const compassTabs=['ask','issues','find'].map(n=>Object.assign(new FakeElement('button'),{dataset:{compassTab:n}}));
  const document={
    addEventListener(ev,fn){if(ev==='DOMContentLoaded')this.onload=fn;},
    getElementById:el,
    querySelectorAll(q){return q==='[data-layer]'?layers:q==='[data-compass-tab]'?compassTabs:[];},
    querySelector(q){const m=q.match(/\[data-compass-tab="(.*?)"\]/);return m?compassTabs.find(b=>b.dataset.compassTab===m[1]):null;},
    createElement(tag){return new FakeElement(tag);},
    activeElement:new FakeElement('div'),
  };
  const user={name:'Test User',username:'tester',provider:'github',email:'',avatar:''};
  const session=()=>({authenticated:true,guest:true,user:null,csrf:'csrf-test',
    repositories:active?[{id:'demo',owner:'testowner',name:'Demo City',fullName:'testowner/demo-city'}]:[],activeRepo:active?'demo':null,
    aiConfigured:false});
  const calls=[];
  async function fetchStub(url,opts={}){
    calls.push({url,opts});let body=null,code=200;
    if(url==='/api/session')body=session();
    else if(url==='/api/my-repos/demo')body={id:'demo',graph:GRAPH};
    else if(url==='/api/demo')body={...GRAPH,source:'demo',url:'',owner:'Repoworld Studio',name:'Orbit Commerce',warnings:['Fictional demonstration only.']};
    else if(typeof url==='string'&&url.startsWith('https://api.github.com/repos/')){
      if(browserIssueError){code=browserIssueError;body={message:'API rate limited from browser'};}
      else body=browserIssues||[];
    }
    else if(url==='/api/my-repos/demo/issues'){
      if(issueFailure){code=issueFailure;body={error:issueFailureMessage||'Server-side GitHub issue API rate limit reached.'};}
      else {
      const baseIssue={number:4,title:'Fix login in services/api/index.py',url:'https://github.com/testowner/demo-city/issues/4',labels:['bug'],body:'services/api/index.py\nLogin fails on expired sessions.',matches:[{nodeId:'api',confidence:'referenced',evidence:'Issue references services/api/index.py'}]};
      const unplaced={number:5,title:'Documentation',url:'https://github.com/testowner/demo-city/issues/5',labels:[],matches:[]};
      const extras=multipleIssues?[{number:717,title:'Add logging for api requests',url:'https://github.com/testowner/demo-city/issues/717',labels:['feature'],body:'services/api/index.py requires logging',matches:[{nodeId:'api',confidence:'referenced',evidence:'Issue references services/api/index.py'}]},{number:789,title:'Handle short commit messages',url:'https://github.com/testowner/demo-city/issues/789',labels:['bug'],body:'services/api/index.py prefix exception',matches:[{nodeId:'api',confidence:'referenced',evidence:'Issue references services/api/index.py'}]},{number:821,title:'Improve module error handling',url:'https://github.com/testowner/demo-city/issues/821',labels:['enhancement'],body:'services/api/index.py',matches:[{nodeId:'api',confidence:'referenced',evidence:'Issue references services/api/index.py'}]}]:[];
      body={total:2+extras.length,placed:1+extras.length,unplaced:1,partial:false,scope:'Mock public issues',issues:[baseIssue,...extras,unplaced],byNode:{api:{referenced:[4,...extras.map(e=>e.number)],suggested:[]}}};
      }
    }
    else if(url==='/api/my-repos/demo/source-lead'&&opts.method==='POST'){
      if(sourceLeadError){code=sourceLeadError;body={error:'Source lookup limit reached'};}
      else body=sourceLeadResult||{mode:'source-lead',issueVerified:false,assistantUsed:false,
        sourceFilesRead:1,sourceScope:'live-branch',
        sources:[{file:'services/api/index.py',evidence:'excerpt',
          url:'https://github.com/testowner/demo-city/blob/HEAD/services/api/index.py#L3-L8',
          matchKind:'symbol',matchedSymbols:['handleLogin'],
          preview:'3: def handleLogin(): pass'}],
        disclosure:'Browser issue remains unverified; source fetched separately.'};
    }
    else if(url==='/api/my-repos/demo/assistant'&&opts.method==='POST')body=assistantResult||{mode:'navigation',answer:'Start with API.',steps:['Read source'],nodeIds:['api'],sources:[{file:'services/api/index.py',url:'https://github.com/testowner/demo-city/blob/main/services/api/index.py'}],disclosure:'Navigation only'};
    else if(url==='/api/my-repos/demo/find?q=Where%20is%20login%20handled%3F')body={query:'Where is login handled?',results:[{nodeId:'api',name:'API',path:'services/api',kind:'api',files:['services/api/index.py']}],scope:'Path-based matches.'};
    else if(url==='/api/my-repos/demo/impact?nodeId=api')body={root:'api',direct:[{nodeId:'web',name:'Web',path:'apps/web',hops:1,importPath:['web','api']}],indirect:[],affectedCount:1,edges:[{source:'web',target:'api'}]};
    else if(url==='/api/tour')body={mode:'guided',steps:[
      {nodeId:'web',title:'Web district',description:'UI files'},
      {nodeId:'api',title:'API district',description:'Server files'}]};
    else if(url==='/api/my-repos'&&opts.method==='POST'){
      if(importFailure){code=importFailure.status;body={error:importFailure.message};}
      else {active=true;body={id:'demo',graph:GRAPH};}
    }
    else body={error:'Unavailable'},code=404;
    return {ok:code===200,status:code,headers:{get:key=>key==='Retry-After'?importFailure?.retryAfter||null:null},json:async()=>body};
  }
  let renderer;
  class Renderer{
    constructor(canvas,opts){renderer=this;this.onSelect=opts.onSelect;this.onIssueSelect=opts.onIssueSelect;this.onDistrictSelect=opts.onDistrictSelect;this.selected=null;}
    setGraph(graph){this.graph=graph;}
    getDistricts(){return [{kind:'frontend',name:'Frontend Boulevard',count:1},{kind:'api',name:'API Heights',count:1}];}
    focusDistrict(kind){this.focusedDistrict=kind;return true;}
    focusHotspot(){this.selected='api';this.mode='hotspots';return GRAPH.nodes[1];}
    cycleModule(step){this.cycles=(this.cycles||[]).concat(step);const node=GRAPH.nodes[step>0?0:1];this.selected=node.id;return node;}
    zoomToward(factor){this.zoomFactor=factor;}
    setIssueMarkers(data){this.issueMarkers=data;}
    setSelected(id){this.selected=id;}
    setMode(mode){this.mode=mode;}
    setTraffic(v){this.traffic=v;}
    setImpactTrace(trace){this.trace=trace;}
    resetCamera(){this.reset=true;}
  }
  const copied=[];
  const store=new Map();
  if(storedLastRepo!==null)store.set('repoworld:last-public-repo:v1',storedLastRepo);
  const localStorage={
    getItem(key){if(storageThrows)throw Error('Storage blocked');return store.has(key)?store.get(key):null;},
    setItem(key,value){if(storageThrows)throw Error('Storage blocked');store.set(key,String(value));}
  };
  const location={origin:'http://127.0.0.1:8004',pathname:'/',search:deepLink,assign(){}};
  const window={RepoWorldRenderer:Renderer,REPOWORLD_COLORS:{frontend:'#88ccff'},REPOWORLD_DISTRICTS:{frontend:{name:'Frontend Boulevard'},api:{name:'API Heights'}},
    setTimeout(){return 1;},clearTimeout(){},location,localStorage,navigator:{clipboard:{async writeText(value){copied.push(value);}}}};
  const sandbox={document,window,fetch:fetchStub,console,location,URLSearchParams,URL,
    clearTimeout(){},setTimeout(fn){fn();return 1;},encodeURIComponent,Response};
  vm.runInNewContext(browserIssueSource,sandbox);
  vm.runInNewContext(issueNotesSource,sandbox);
  vm.runInNewContext(source,sandbox);
  const flush=()=>new Promise(resolve=>setImmediate(resolve));
  async function boot(){document.onload();for(let i=0;i<4;i++)await flush();}
  return {document,window,el,layers,compassTabs,calls,copied,store,boot,get renderer(){return renderer;}};
}
test('new visitors land directly on Add GitHub repository, without signing in',async()=>{
  const ui=makeApp({authenticated:false,active:false});await ui.boot();
  assert.equal(ui.el('workspace').hidden,false);
  assert.equal(ui.el('emptyState').hidden,false);
  assert.equal(ui.renderer,undefined);
});
test('guest users without repositories get a single add-repo empty state',async()=>{
  const ui=makeApp({active:false});await ui.boot();
  assert.equal(ui.el('workspace').hidden,false);
  assert.equal(ui.el('emptyState').hidden,false);
  assert.equal(ui.el('canvasStage').hidden,true);
  assert.equal(ui.el('activeRepoTitle').textContent,'RepoWorld');
  ui.el('emptyAddRepo').listeners.click();
  assert.equal(ui.el('addRepoDialog').open,true);
});
test('free-tier recovery stores only a validated public name and never auto-imports',async()=>{
  const first=makeApp({active:false});await first.boot();
  assert.equal(first.el('reimportRecent').hidden,true);
  first.el('emptyAddRepo').listeners.click();
  first.el('importInput').value='testowner/demo-city';
  await first.el('importForm').listeners.submit({preventDefault(){}});
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.deepEqual(Array.from(first.store.entries()),[['repoworld:last-public-repo:v1','testowner/demo-city']]);
  const restored=makeApp({active:false,storedLastRepo:first.store.get('repoworld:last-public-repo:v1')});
  await restored.boot();
  assert.equal(restored.el('reimportRecent').hidden,false);
  assert.equal(restored.el('recentRepoName').textContent,'testowner/demo-city');
  assert.equal(restored.el('recentRepoHelp').hidden,false);
  assert.equal(restored.calls.filter(c=>c.url==='/api/my-repos'&&c.opts.method==='POST').length,0);
  restored.el('reimportRecent').listeners.click();
  assert.equal(restored.el('addRepoDialog').open,true);
  assert.equal(restored.el('importInput').value,'testowner/demo-city');
  assert.equal(restored.calls.filter(c=>c.url==='/api/my-repos'&&c.opts.method==='POST').length,0);
});
test('malformed or inaccessible browser storage never launches a repo request',async()=>{
  for(const storedLastRepo of ['https://evil.example/path','owner/..','owner/../repo','<script>','a'.repeat(500)]){
    const ui=makeApp({active:false,storedLastRepo});await ui.boot();
    assert.equal(ui.el('reimportRecent').hidden,true);
    assert.equal(ui.calls.filter(c=>c.url==='/api/my-repos'&&c.opts.method==='POST').length,0);
  }
  const blocked=makeApp({active:false,storageThrows:true});await blocked.boot();
  assert.equal(blocked.el('reimportRecent').hidden,true);
  blocked.el('emptyAddRepo').listeners.click();blocked.el('importInput').value='testowner/demo-city';
  await blocked.el('importForm').listeners.submit({preventDefault(){}});
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(blocked.el('activeRepoTitle').textContent,'Demo City');
});
test('saved repo boots into full-screen city with correct name and optional tools',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  assert.equal(ui.el('emptyState').hidden,true);
  assert.equal(ui.el('canvasStage').hidden,false);
  assert.equal(ui.el('activeRepoTitle').textContent,'Demo City');
  assert.equal(ui.renderer.graph.nodes.length,2);
  ui.el('mapCommandTrigger').listeners.click();
  assert.equal(ui.el('searchDialog').open,true);
  ui.compassTabs[2].listeners.click();
  ui.el('showMapOptions').listeners.click();
  assert.equal(ui.el('mapTools').hidden,false);
  ui.layers[1].listeners.click();
  assert.equal(ui.renderer.mode,'dependencies');
  ui.el('tourButton').listeners.click();
  assert.equal(ui.el('tourPanel').hidden,false);
  assert.equal(ui.el('tourTitle').textContent,'Web district');
  ui.el('tourNext').listeners.click();
  assert.equal(ui.el('tourTitle').textContent,'API district');
});
test('selecting a tower opens honest source inspector',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.renderer.onSelect('web');
  assert.equal(ui.el('inspector').hidden,false);
  assert.equal(ui.el('inspectorName').textContent,'Web');
  assert.equal(ui.el('inspectorOut').textContent,'1');
  assert.equal(ui.el('inspectorConnections').children.length,1);
});
test('import from an empty guest workspace persists as active city',async()=>{
  const ui=makeApp({active:false});await ui.boot();
  ui.el('emptyAddRepo').listeners.click();
  ui.el('importInput').value='testowner/demo-city';
  await ui.el('importForm').listeners.submit({preventDefault(){}});
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('activeRepoTitle').textContent,'Demo City');
  assert.equal(ui.el('canvasStage').hidden,false);
  assert.ok(ui.calls.some(c=>c.url==='/api/my-repos'&&c.opts.method==='POST'));
  assert.ok(ui.calls.some(c=>c.opts.headers?.['X-RepoWorld-CSRF']==='csrf-test'));
});

test('a GitHub rate limit is shown in the import modal with a retry time',async()=>{
  const ui=makeApp({active:false,importFailure:{status:429,message:'GitHub API rate limit reached.',retryAfter:'91'}});
  await ui.boot();
  ui.el('emptyAddRepo').listeners.click();
  ui.el('importInput').value='public/demo';
  await ui.el('importForm').listeners.submit({preventDefault(){}});
  for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('importError').hidden,false);
  assert.match(ui.el('importError').textContent,/GitHub API rate limit reached/);
  assert.match(ui.el('importError').textContent,/2 minutes/);
  assert.equal(ui.el('importButton').disabled,false);
});
test('GitHub rate limit exposes an explicitly fictional, API-free city preview',async()=>{
  const ui=makeApp({active:false,importFailure:{status:429,message:'GitHub API rate limit reached.',retryAfter:'840'}});
  await ui.boot();
  ui.el('emptyAddRepo').listeners.click();
  assert.equal(ui.el('importDemo').hidden,true);
  ui.el('importInput').value='pallets/flask';
  await ui.el('importForm').listeners.submit({preventDefault(){}});
  for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('importDemo').hidden,false);
  const githubCalls=ui.calls.filter(c=>c.url==='/api/my-repos').length;
  await ui.el('importDemo').listeners.click();
  for(let i=0;i<6;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('importDemo').disabled,false);
  assert.equal(ui.el('addRepoDialog').open,false);
  assert.equal(ui.el('cityStatusText').textContent,'DEMO CITY');
  assert.equal(ui.el('activeRepoTitle').textContent,'Orbit Commerce');
  assert.equal(ui.el('canvasStage').hidden,false);
  assert.equal(ui.calls.filter(c=>c.url==='/api/my-repos').length,githubCalls);
  assert.ok(ui.calls.some(c=>c.url==='/api/demo'));
});
test('one subtle city command opens grounded code compass with selectable result',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();
  assert.equal(ui.el('searchDialog').open,true);
  ui.compassTabs[2].listeners.click();
  ui.el('searchInput').value='Where is login handled?';
  ui.el('searchInput').listeners.input();
  for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('searchResults').children.length,1);
  assert.equal(ui.el('searchResults').children[0].children[1].textContent,'services/api');
  ui.el('searchResults').children[0].listeners.click();
  assert.equal(ui.el('inspector').hidden,false);
  assert.equal(ui.renderer.selected,'api');
  assert.ok(ui.calls.some(c=>c.url.includes('/find?q=')));
});
test('trace highlights only sampled reverse imports and can be dismissed',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.renderer.onSelect('api');
  await ui.el('inspectorTrace').listeners.click();
  assert.equal(ui.el('impactPanel').hidden,false);
  assert.equal(ui.el('impactCount').textContent,'1 POSSIBLY AFFECTED');
  assert.equal(ui.renderer.mode,'dependencies');
  assert.equal(ui.renderer.trace.root,'api');
  ui.el('exitImpact').listeners.click();
  assert.equal(ui.el('impactPanel').hidden,true);
  assert.equal(ui.renderer.trace,null);
});

test('open issue radar is visible inside existing command, not as new homepage button',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();
  ui.compassTabs[1].listeners.click();
  assert.equal(ui.el('issuesTab').hidden,false);
  assert.equal(ui.el('issueList').children.length,2);
  assert.equal(ui.el('issueSummary').textContent,'2 open issues sampled · 1 placed · 1 unplaced');
  assert.ok(ui.calls.some(c=>c.url==='/api/my-repos/demo/issues'));
});
test('assistant supports a building context and sends CSRF authenticated questions',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.renderer.onSelect('api');
  assert.equal(ui.el('buildingIssues').hidden,false);
  ui.el('inspectorAsk').listeners.click();
  assert.equal(ui.el('askTab').hidden,false);
  assert.ok(ui.el('assistantContext').textContent.includes('API'));
  ui.el('assistantQuestion').value='How does the API relate to the frontend?';
  await ui.el('assistantSend').listeners.click();
  assert.ok(ui.calls.some(c=>c.url==='/api/my-repos/demo/assistant'&&
    JSON.parse(c.opts.body).nodeId==='api'&&c.opts.headers['X-RepoWorld-CSRF']==='csrf-test'));
  assert.equal(ui.el('assistantThread').children.length,2); // welcome is hidden after the first message
});

test('assistant labels provider timeout honestly without another homepage control',async()=>{
  const ui=makeApp({active:true,assistantResult:{mode:'navigation',providerStatus:'timeout',answer:'BharatCode timed out. Start with api.',
    steps:['Inspect the linked files'],nodeIds:['api'],sources:[],disclosure:'AI was unavailable (provider timeout). This is not an AI answer.'}});
  await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();
  ui.el('assistantQuestion').value='Where should I start fixing sessions?';
  await ui.el('assistantSend').listeners.click();
  const assistantMessage=ui.el('assistantThread').children[1];
  assert.equal(assistantMessage.children[0].textContent,'BHARATCODE UNAVAILABLE · LOCAL PATH GUIDE');
  assert.equal(assistantMessage.children[1].textContent,'BharatCode timed out. Start with api.');
  assert.equal(ui.el('workspace').hidden,false);
  assert.equal(ui.el('canvasStage').hidden,false);
});


test('clicking a city issue pin opens report and automatically asks source-scoped assistant',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  assert.equal(ui.el('issueMapLegend').hidden,false);
  assert.ok(ui.renderer.issueMarkers.api.referenced.includes(4));
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<4;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDrawer').hidden,false);
  assert.ok(ui.el('issueDrawerHeading').textContent.includes('Fix login'));
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #4');
  assert.ok(ui.el('issuePlacement').children[0].textContent.includes('Path referenced'));
  assert.ok(ui.el('issueDetailBody').textContent.includes('Login fails'));
  const request=ui.calls.find(c=>c.url==='/api/my-repos/demo/assistant'&&c.opts.method==='POST');
  assert.ok(request);
  const payload=JSON.parse(request.opts.body);
  assert.equal(payload.issueNumber,4);
  assert.equal(payload.nodeId,'api');
  assert.ok(payload.question.includes('investigation steps'));
  assert.ok(ui.el('issueAiResult').children.length>0);
  assert.equal(ui.el('issueFollowUp').hidden,false);
  // Reopening an issue already explained in this session does not spend tokens again.
  ui.el('closeIssueDrawer').listeners.click();ui.renderer.onIssueSelect('api');
  assert.equal(ui.calls.filter(c=>c.url==='/api/my-repos/demo/assistant').length,1);
});

test('issue detail can be opened for an unplaced issue without inventing a building',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  const issueRow=ui.el('issueList').children[1];
  issueRow.children[0].children[0].listeners.click();
  for(let i=0;i<4;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDrawer').hidden,false);
  assert.equal(ui.el('issueDrawerDistrict').textContent,'UNPLACED GITHUB ISSUE');
  assert.ok(ui.el('issuePlacement').children[0].textContent.includes('No verified'));
  assert.equal(ui.el('issueGithubLink').href,'https://github.com/testowner/demo-city/issues/5');
  const req=ui.calls.find(c=>c.url==='/api/my-repos/demo/assistant');
  assert.equal(JSON.parse(req.opts.body).nodeId,null);
  assert.equal(JSON.parse(req.opts.body).issueNumber,5);
});

test('issue guide routes a follow-up into the existing assistant instead of creating new navigation',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<4;i++)await new Promise(resolve=>setImmediate(resolve));
  ui.el('issueFollowUp').listeners.click();
  assert.equal(ui.el('issueDrawer').hidden,true);
  assert.equal(ui.el('searchDialog').open,true);
  assert.equal(ui.el('askTab').hidden,false);
  assert.ok(ui.el('assistantContext').textContent.includes('Issue #4'));
  assert.ok(ui.el('assistantQuestion').value.includes('issue #4'));
});


test('building inspector exposes issues above metrics, with direct buttons and a browse-all action',async()=>{
  const ui=makeApp({active:true,multipleIssues:true});await ui.boot();
  ui.renderer.onSelect('api');
  assert.equal(ui.el('buildingIssues').hidden,false);
  assert.equal(ui.el('buildingIssueCount').textContent,'4 LINKED');
  const rows=ui.el('buildingIssuesList').children;
  assert.equal(rows.length,3);
  assert.equal(ui.el('buildingIssuesMore').hidden,false);
  assert.ok(ui.el('buildingIssuesMore').textContent.includes('all 4'));
  assert.ok(rows[1].children[0].textContent.includes('#717'));
  rows[1].listeners.click();
  for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #717');
  assert.equal(ui.el('issueDrawerSelect').value,'717');
  assert.equal(ui.el('issueDrawerChooser').hidden,false);
  assert.equal(ui.el('issueDrawerSelect').children.length,4);
  assert.ok(ui.calls.some(c=>c.url==='/api/my-repos/demo/assistant'&&JSON.parse(c.opts.body).issueNumber===717));
});

test('issue selector switches issue-number and assistant context, never silently choosing first',async()=>{
  const ui=makeApp({active:true,multipleIssues:true});await ui.boot();
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #4');
  const select=ui.el('issueDrawerSelect');
  select.value='789';select.listeners.change();
  for(let i=0;i<3;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #789');
  assert.ok(ui.el('issueDrawerHeading').textContent.includes('Handle short commit'));
  assert.ok(ui.calls.some(c=>c.url==='/api/my-repos/demo/assistant'&&JSON.parse(c.opts.body).issueNumber===789));
  assert.equal(ui.el('issueMapCount').textContent,'5 OPEN ISSUES · 4 ON MAP');
  ui.el('issueMapLegend').listeners.click();
  assert.equal(ui.el('searchDialog').open,true);
  assert.equal(ui.el('issuesTab').hidden,false);
});

test('source-observed issue file becomes a real map marker and a contextual jump, not a permanent button',async()=>{
  const sourceAnswer={mode:'ai',answer:'The source contains the referenced identifier.',issueSummary:'The issue reports a login error.',
    codeEvidence:['apps/web/index.ts mentions handleLogin in a public source excerpt.'],
    steps:['Inspect the code'],tests:['Run relevant login tests'],sourceFilesRead:1,
    sources:[{file:'apps/web/index.ts',url:'https://github.com/testowner/demo-city/blob/'+'a'.repeat(40)+'/apps/web/index.ts#L12-L29',lineStart:12,lineEnd:29,evidence:'excerpt'}],
    observedLocations:[{nodeId:'web',file:'apps/web/index.ts',symbols:['handleLogin'],evidence:'identifier-observed',
      url:'https://github.com/testowner/demo-city/blob/'+'a'.repeat(40)+'/apps/web/index.ts#L12-L29'}],
    disclosure:'Source observed; issue not verified.'};
  const ui=makeApp({active:true,assistantResult:sourceAnswer});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  ui.el('issueList').children[1].children[0].children[0].listeners.click();
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #5');
  assert.ok(ui.renderer.issueMarkers.web.observed.includes(5));
  assert.equal(ui.renderer.issueMarkers.api.referenced.includes(4),true);
  assert.equal(ui.el('issueMapCount').textContent,'2 OPEN ISSUES · 2 ON MAP');
  assert.match(ui.el('issueDrawerDistrict').textContent,/SOURCE OBSERVED/);
  assert.match(ui.el('issuePlacement').children[0].textContent,/Identifier observed/);
  const section=ui.el('issueAiResult').children.find(c=>c.children?.some(x=>x.textContent==='CODE LOCATED IN THE CITY'));
  assert.ok(section,'source-observed location appears inside existing issue panel');
  const jump=section.children.find(c=>c.className==='observed-source-location');
  assert.ok(jump);assert.match(jump.children[0].textContent,/apps\/web\/index.ts/);
  jump.listeners.click();
  assert.equal(ui.renderer.selected,'web');
  assert.equal(ui.el('inspector').hidden,false);
  assert.equal(ui.el('issueDrawer').hidden,true);
});

test('unverified path guesses cannot add source-observed markers',async()=>{
  const ui=makeApp({active:true,assistantResult:{mode:'ai',answer:'Maybe web.',sourceFilesRead:1,
    observedLocations:[],sources:[{file:'apps/web/index.ts',evidence:'path-only',url:'https://github.com/testowner/demo-city/blob/main/apps/web/index.ts'}]}});
  await ui.boot();ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  ui.el('issueList').children[1].children[0].children[0].listeners.click();
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.renderer.issueMarkers.web,undefined);
  assert.equal(ui.el('issueMapCount').textContent,'2 OPEN ISSUES · 1 ON MAP');
});


test('sharing a saved public city copies only owner/repo, never workspace credentials',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  assert.equal(ui.el('copyCityLink').hidden,false);
  await ui.el('copyCityLink').listeners.click();
  assert.equal(ui.copied.length,1);
  assert.equal(ui.copied[0],'http://127.0.0.1:8004/?repo=testowner%2Fdemo-city');
  assert.ok(!ui.copied[0].includes('csrf-test'));
  assert.ok(!ui.copied[0].includes('id=demo'));
});

test('shared repository links prefill import but never spend GitHub quota on page load',async()=>{
  const ui=makeApp({active:false,deepLink:'?repo=testowner%2Fdemo-city'});await ui.boot();
  assert.equal(ui.el('addRepoDialog').open,true);
  assert.equal(ui.el('importInput').value,'testowner/demo-city');
  assert.equal(ui.el('emptyState').hidden,false);
  assert.equal(ui.calls.filter(call=>call.url==='/api/my-repos'&&call.opts.method==='POST').length,0);
  assert.equal(ui.el('importButton').disabled,false);
});

test('share link selects an existing browser city without reimporting',async()=>{
  const ui=makeApp({active:true,deepLink:'?repo=TESTOWNER%2Fdemo-city'});await ui.boot();
  assert.equal(ui.el('activeRepoTitle').textContent,'Demo City');
  assert.equal(ui.el('addRepoDialog').open,undefined);
  assert.equal(ui.calls.filter(call=>call.url==='/api/my-repos'&&call.opts.method==='POST').length,0);
});

test('invalid or external deep links never start a repository fetch or import modal',async()=>{
  const ui=makeApp({active:false,deepLink:'?repo=https%3A%2F%2Fevil.example%2Fsecret'});await ui.boot();
  assert.equal(ui.el('emptyState').hidden,false);
  assert.equal(ui.el('addRepoDialog').open,undefined);
  assert.equal(ui.calls.filter(call=>call.url==='/api/my-repos').length,0);
});

test('Issue Radar browser fallback labels server-unverified hints after GitHub provider rate limit',async()=>{
  const raw=[
    {number:12,title:'Fix services/api/index.py login issue',state:'open',body:'services/api/index.py fails on invalid token',
      labels:[{name:'bug'}],comments:5,updated_at:'2026-11-05T09:00:00Z',html_url:'https://attacker.invalid/poison'},
    {number:13,title:'Docs only',state:'open',body:'needs more documentation',labels:[]},
    {number:14,title:'Pull request',state:'open',body:'services/api/index.py',pull_request:{url:'x'},labels:[]}
  ];
  const ui=makeApp({active:true,issueFailure:429,browserIssues:raw});await ui.boot();
  for(let i=0;i<7;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issuesTabCount').textContent,'2');
  assert.match(ui.el('issueMapCount').textContent,/2 OPEN ISSUES · 1 ON MAP/);
  assert.match(ui.el('issueSummary').textContent,/BROWSER GITHUB FEED · UNVERIFIED BY SERVER/);
  assert.deepEqual(Array.from(ui.renderer.issueMarkers.api?.suggested||[]),[12]);
  assert.equal(ui.renderer.issueMarkers.api?.referenced.length,0);
  const calls=ui.calls.filter(c=>c.url.startsWith('https://api.github.com/'));
  assert.equal(calls.length,1);
  assert.equal(calls[0].opts.credentials,'omit');
  assert.equal(calls[0].opts.mode,'cors');
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  assert.equal(ui.el('issueList').children.length,2);
  ui.el('issueList').children[0].children[0].children[0].listeners.click();
  assert.equal(ui.el('issueDetailIndex').textContent,'OPEN ISSUE #12');
  assert.equal(ui.el('issueGithubLink').href,'https://github.com/testowner/demo-city/issues/12');
  assert.match(ui.el('issueAiHeading').textContent,/UNVERIFIED/);
  assert.equal(ui.calls.filter(c=>c.url==='/api/my-repos/demo/assistant').length,0);
  assert.match(ui.el('issueAiResult').textContent,/not independently checked/);
  ui.el('issueFollowUp').listeners.click();
  assert.match(ui.el('assistantQuestion').value,/not verified/);
  assert.ok(!ui.el('assistantContext').textContent.includes('#12'));
});
test('browser issue fallback reports both GitHub quotas accurately without fabricating issues',async()=>{
  const ui=makeApp({active:true,issueFailure:429,browserIssueError:429});await ui.boot();
  for(let i=0;i<7;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.match(ui.el('issueSummary').textContent,/Browser fallback/);
  assert.match(ui.el('issueSummary').textContent,/also rate-limiting/);
  assert.equal(ui.el('issueMapLegend').hidden,true);
  assert.equal(ui.el('issuesTabCount').hidden,true);
});
test('RepoWorld guest quota cannot be bypassed by browser-direct issue requests',async()=>{
  const ui=makeApp({active:true,issueFailure:429,issueFailureMessage:'Too many requests. Try again shortly.'});
  await ui.boot();for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.calls.filter(c=>typeof c.url==='string'&&c.url.startsWith('https://api.github.com/')).length,0);
  assert.match(ui.el('issueSummary').textContent,/Too many requests/);
});
test('successful Issue Radar avoids browser API and retains server-qualified issue positions',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  for(let i=0;i<4;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.calls.filter(c=>typeof c.url==='string'&&c.url.startsWith('https://api.github.com/')).length,0);
  assert.equal(ui.renderer.issueMarkers.api.referenced[0],4);
  assert.doesNotMatch(ui.el('issueSummary').textContent,/BROWSER GITHUB FEED/);
});

test('temporary map controls focus districts, connected hubs and zoom, without new sidebar',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  assert.equal(ui.el('districtJump').children.length,3);
  ui.el('mapCommandTrigger').listeners.click();ui.el('showMapOptions').listeners.click();
  ui.el('districtJump').value='api';ui.el('districtJump').listeners.change();
  assert.equal(ui.renderer.focusedDistrict,'api');
  assert.equal(ui.el('mapTools').hidden,true);
  ui.el('showMapOptions').listeners.click();
  ui.el('zoomIn').listeners.click();assert.equal(ui.renderer.zoomFactor,.8);
  ui.el('zoomOut').listeners.click();assert.equal(ui.renderer.zoomFactor,1.25);
  ui.el('focusHub').listeners.click();
  assert.equal(ui.renderer.selected,'api');
  assert.equal(ui.renderer.mode,'hotspots');
  assert.equal(ui.el('inspector').hidden,false);
  assert.equal(ui.el('mapTools').hidden,true);
});

test('Issue Radar local search and categories filter only sampled records without extra GitHub fetches',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  assert.equal(ui.el('issueList').children.length,2);
  const count=ui.calls.length;
  ui.el('issueFilterText').value='login';ui.el('issueFilterText').listeners.input();
  assert.equal(ui.el('issueList').children.length,1);
  assert.match(ui.el('issueSummary').textContent,/1 of 2 sampled issues match/);
  ui.el('issueFilterText').value='';ui.el('issueFilterText').listeners.input();
  ui.el('issueFilterType').value='bug';ui.el('issueFilterType').listeners.change();
  assert.equal(ui.el('issueList').children.length,1);
  ui.el('issueFilterType').value='mapped';ui.el('issueFilterType').listeners.change();
  assert.equal(ui.el('issueList').children.length,1);
  ui.el('issueFilterType').value='good-first';ui.el('issueFilterType').listeners.change();
  assert.match(ui.el('issueList').children[0].textContent,/No sampled issues match/);
  ui.el('issueFilterType').value='all';ui.el('issueFilterType').listeners.change();
  assert.equal(ui.el('issueList').children.length,2);
  assert.equal(ui.calls.length,count);
});


test('map controls browse actual buildings, open the inspector and preserve source graph',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('mapCommandTrigger').listeners.click();
  ui.el('showMapOptions').listeners.click();
  ui.el('nextBuilding').listeners.click();
  assert.equal(ui.renderer.selected,'web');
  assert.equal(ui.el('inspector').hidden,false);
  assert.equal(ui.el('inspectorName').textContent,'Web');
  ui.el('showMapOptions').listeners.click();
  ui.el('previousBuilding').listeners.click();
  assert.equal(ui.renderer.selected,'api');
  assert.equal(ui.el('inspectorName').textContent,'API');
  assert.deepEqual(Array.from(ui.renderer.cycles),[1,-1]);
  assert.equal(ui.renderer.graph.edges.length,GRAPH.edges.length);
});

test('map controls are discoverable on every developer-console tab, not buried in Find code',()=>{
  const markup=fs.readFileSync(path.join(__dirname,'../static/index.html'),'utf8');
  const where=markup.indexOf('id="showMapOptions"');
  assert.ok(where>markup.indexOf('id="searchDialog"'));
  assert.ok(where<markup.indexOf('id="findTab"'));
  assert.equal(markup.split('id="showMapOptions"').length,2);
});

test('district focus hides competing overlays and keeps existing city graph intact',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.el('inspector').hidden=false;
  ui.renderer.onDistrictSelect('api');
  assert.equal(ui.el('inspector').hidden,true);
  assert.equal(ui.el('mapTools').hidden,true);
  assert.equal(ui.renderer.graph.nodes.length,GRAPH.nodes.length);
});

test('investigation notes copy the selected public issue and labeled source facts',async()=>{
  const reply={mode:'ai',sourceScope:'commit-pinned',answer:'Inspect the login handler.',
    sourceFilesRead:1,steps:['Read services/api/index.py'],tests:['Run login regression'],
    sources:[{file:'services/api/index.py',evidence:'excerpt',
      url:'https://github.com/testowner/demo-city/blob/'+'b'.repeat(40)+'/services/api/index.py#L7-L16'}]};
  const ui=makeApp({active:true,assistantResult:reply});await ui.boot();
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  await ui.el('issueCopyNotes').listeners.click();
  assert.equal(ui.copied.length,1);
  assert.match(ui.copied[0],/testowner\/demo-city\/issues\/4/);
  assert.match(ui.copied[0],/AI-generated suggestion \(not verified\)/);
  assert.match(ui.copied[0],/Fetched source excerpt, review before citing/);
  assert.match(ui.copied[0],/Tests \(not run\)/i);
  assert.equal(ui.calls.filter(x=>x.url.includes('/assistant')).length,1);
});
test('new issue selection cannot reuse previously fetched AI investigation notes',async()=>{
  const ui=makeApp({active:true,multipleIssues:true});await ui.boot();
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  ui.el('issueDrawerSelect').value='789';
  ui.el('issueDrawerSelect').listeners.change();
  await ui.el('issueCopyNotes').listeners.click();
  assert.equal(ui.copied.length,1);
  assert.match(ui.copied[0],/testowner\/demo-city\/issues\/789/);
  assert.doesNotMatch(ui.copied[0],/Issue: https:\/\/github\.com\/testowner\/demo-city\/issues\/4\b/);
});
test('browser fallback notes remain explicitly unverified and never invoke server assistant',async()=>{
  const feed=[{number:12,state:'open',title:'Fix services/api/index.py',body:'services/api/index.py bug',labels:[]}];
  const ui=makeApp({active:true,issueFailure:429,browserIssues:feed});await ui.boot();
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  ui.el('issueList').children[0].children[0].children[0].listeners.click();
  await ui.el('issueCopyNotes').listeners.click();
  assert.equal(ui.copied.length,1);
  assert.match(ui.copied[0],/browser-only issue feed; source unverified/);
  assert.doesNotMatch(ui.copied[0],/AI-generated suggestion/);
  assert.equal(ui.calls.filter(x=>x.url.includes('/assistant')).length,0);
});

test('browser-only issue allows explicit public source lookup without claiming issue verification',async()=>{
  const feed=[{number:774,state:'open',title:'Disable cycling to stream and recipients while editing',
    body:'It is not possible to edit stream name for stream messages.',labels:[]}];
  const ui=makeApp({active:true,issueFailure:429,browserIssues:feed});await ui.boot();
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  ui.el('issueList').children[0].children[0].children[0].listeners.click();
  assert.equal(ui.el('issueInspectSource').hidden,false);
  assert.equal(ui.calls.filter(x=>x.url.endsWith('/source-lead')).length,0);
  assert.match(ui.el('issueAiResult').textContent,/not independently checked/i);
  await ui.el('issueInspectSource').listeners.click();
  const lookups=ui.calls.filter(x=>x.url.endsWith('/source-lead'));
  assert.equal(lookups.length,1);
  assert.equal(lookups[0].opts.method,'POST');
  assert.match(JSON.parse(lookups[0].opts.body).title,/Disable cycling/);
  assert.match(ui.el('issueAiHeading').textContent,/ISSUE UNVERIFIED/);
  assert.equal(ui.el('issueNotesResult')?.textContent||'', '');
  assert.equal(ui.calls.filter(x=>x.url.endsWith('/assistant')).length,0);
  assert.ok(!ui.renderer.issueMarkers.api?.observed?.length);
  const section=ui.el('issueAiResult').children.find(c=>c.className==='insight-section');
  assert.ok(section);
  const source=section.children.find(c=>c.className==='source-lead-card');
  assert.ok(source);
  assert.equal(source.children[0].href,'https://github.com/testowner/demo-city/blob/HEAD/services/api/index.py#L3-L8');
  await ui.el('issueCopyNotes').listeners.click();
  assert.match(ui.copied[0],/browser-only issue feed; public source independently inspected; issue not verified/);
  assert.match(ui.copied[0],/Separately fetched public source; issue not verified/);
  assert.doesNotMatch(ui.copied[0],/AI-generated suggestion/);
});
test('browser issue source lookup handles no evidence and provider quota safely',async()=>{
  const feed=[{number:774,state:'open',title:'Disable cycling to recipients',
    body:'Edit message action',labels:[]}];
  const ui=makeApp({active:true,issueFailure:429,browserIssues:feed,
    sourceLeadResult:{mode:'source-lead',issueVerified:false,assistantUsed:false,
      sourceFilesRead:0,sourceScope:'unavailable',sources:[]}});
  await ui.boot();for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  ui.el('mapCommandTrigger').listeners.click();ui.compassTabs[1].listeners.click();
  ui.el('issueList').children[0].children[0].children[0].listeners.click();
  await ui.el('issueInspectSource').listeners.click();
  assert.match(ui.el('issueAiResult').children.map(x=>x.textContent||'').join(' '),
    /No public source excerpts were found/);
  await ui.el('issueCopyNotes').listeners.click();
  assert.match(ui.copied[0],/No fetched source excerpts were confirmed/);
  const quota=makeApp({active:true,issueFailure:429,browserIssues:feed,sourceLeadError:429});
  await quota.boot();for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  quota.el('mapCommandTrigger').listeners.click();quota.compassTabs[1].listeners.click();
  quota.el('issueList').children[0].children[0].children[0].listeners.click();
  await quota.el('issueInspectSource').listeners.click();
  assert.match(quota.el('issueAiHeading').textContent,/UNAVAILABLE/);
  assert.equal(quota.el('issueInspectSource').disabled,false);
  assert.equal(quota.calls.filter(x=>x.url.endsWith('/assistant')).length,0);
});
test('server-confirmed issues hide independent browser-only source lookup',async()=>{
  const ui=makeApp({active:true});await ui.boot();
  ui.renderer.onIssueSelect('api');
  for(let i=0;i<5;i++)await new Promise(resolve=>setImmediate(resolve));
  assert.equal(ui.el('issueInspectSource').hidden,true);
  assert.equal(ui.calls.filter(x=>x.url.endsWith('/source-lead')).length,0);
});
