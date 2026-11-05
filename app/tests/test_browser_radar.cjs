/* Isolated browser-side Issue Radar fallback: no server/token/provider access. */
const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../static/browser-radar.js'),'utf8');
const graph={source:'github',url:'https://github.com/pallets/flask',nodes:[
  {id:'api',name:'API',fileIndex:['src/flask/app.py','src/flask/cli.py']},
  {id:'web',name:'Frontend',files:['src/web/index.ts']}
]};
function harness(value,{status=200}={}){
  const calls=[];
  const sandbox={window:{},URL,encodeURIComponent,fetch:async(url,options)=>{
    calls.push({url,options});return {ok:status===200,status,json:async()=>value};
  }};
  vm.runInNewContext(source,sandbox);
  return {calls,run:g=>sandbox.window.RepoWorldBrowserIssueRadar(g)};
}
test('browser fallback uses exact public GitHub CORS URL and no credentials',async()=>{
  const h=harness([{number:2,state:'open',title:'Fix src/flask/app.py',body:'src/flask/app.py error',labels:[{name:'bug'}],comments:5},
    {number:3,state:'open',title:'Docs',body:'Update README',labels:[]},
    {number:4,state:'open',title:'PR',pull_request:{url:'https://github.com'},body:'src/flask/app.py'}]);
  const result=await h.run(graph);
  assert.equal(h.calls.length,1);
  assert.match(h.calls[0].url,/^https:\/\/api\.github\.com\/repos\/pallets\/flask\/issues\?/);
  assert.equal(h.calls[0].options.mode,'cors');
  assert.equal(h.calls[0].options.credentials,'omit');
  assert.equal(h.calls[0].options.headers.Authorization,undefined);
  assert.equal(result.total,2);
  assert.equal(result.placed,1);
  assert.equal(result.browserFallback,true);
  assert.match(result.scope,/not independently verified/);
  assert.equal(result.issues[0].matches[0].confidence,'suggested');
  assert.equal(result.issues[0].url,'https://github.com/pallets/flask/issues/2');
  assert.deepEqual(Array.from(result.byNode.api.suggested),[2]);
});
test('browser direct fallback rejects untrusted git URL without network calls',async()=>{
  for(const url of ['http://github.com/pallets/flask','https://github.com.evil.net/pallets/flask',
                    'https://github.com/pallets/flask/extra','https://github.com/pallets/flask?token=x']){
    const h=harness([]);
    await assert.rejects(h.run({...graph,url}),/safely identify/);
    assert.equal(h.calls.length,0);
  }
});
test('suspicious issue metadata cannot inject a link or claim source verification',async()=>{
  const h=harness([{number:5,state:'open',title:'<script>alert(1)</script>',body:'x'.repeat(2000),
    html_url:'https://evil.example/steal', labels:[{name:'a'.repeat(200)}],comments:2000000}]);
  const result=await h.run(graph);
  assert.equal(result.issues[0].url,'https://github.com/pallets/flask/issues/5');
  assert.equal(result.issues[0].body.length,1500);
  assert.equal(result.issues[0].labels[0].length,80);
  assert.equal(result.issues[0].commentsCount,9999);
  assert.equal(result.issues[0].matches.length,0);
});
test('browser quota exhaustion stays visible instead of silently inventing issues',async()=>{
  const h=harness({message:'too many'}, {status:429});
  await assert.rejects(h.run(graph),/also rate-limiting/);
  assert.equal(h.calls.length,1);
});
test('only 30 results are considered and incomplete pages are labeled',async()=>{
  const issues=Array.from({length:45},(_,i)=>({number:i+1,state:'open',title:'Issue '+i}));
  const h=harness(issues);const result=await h.run(graph);
  assert.equal(result.total,30);
  assert.equal(result.partial,true);
});
