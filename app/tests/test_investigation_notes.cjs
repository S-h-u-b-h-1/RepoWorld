/* Offline note formatter: canonical links and evidence disclosures. */
const test=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
const src=fs.readFileSync(path.join(__dirname,'../static/investigation-notes.js'),'utf8');
function formatter(){
  const context={window:{},URL};
  vm.runInNewContext(src,context);
  return context.window.RepoWorldInvestigationNotes;
}
const graph={source:'github',url:'https://github.com/testowner/demo-city',
 nodes:[{id:'api',name:'API'}]};
const issue={number:12,title:'Login fails on refresh',snippet:'User reports a retry issue.',
 matches:[{nodeId:'api',confidence:'referenced',path:'services/api/login.py'}]};
test('copies canonical source notes without asserting reproduced bugs',()=>{
  const run=formatter();
  const notes=run({graph,issue,guide:{mode:'ai',sourceScope:'commit-pinned',
    answer:'Inspect login handler first.',steps:['Read login.py'],tests:['Run test_login'],
    sources:[{file:'services/api/login.py',evidence:'excerpt',
      url:'https://github.com/testowner/demo-city/blob/'+'a'.repeat(40)+'/services/api/login.py#L10-L20'}]}});
  assert.match(notes,/https:\/\/github\.com\/testowner\/demo-city\/issues\/12/);
  assert.match(notes,/AI-generated suggestion \(not verified\)/);
  assert.match(notes,/Fetched source excerpt, review before citing/);
  assert.match(notes,/Proposed tests \(not run\)/);
  assert.match(notes,/not a reproduced defect or verified fix/);
  assert.ok(notes.length<6501);
});
test('browser-only issue feed never exports AI or source verification',()=>{
  const run=formatter();
  const notes=run({graph,issue:{...issue,matches:[{nodeId:'api',confidence:'observed',path:'services/api/login.py'}]},
    browserFallback:true,guide:{mode:'ai',answer:'Verified fix',
       sources:[{file:'services/api/login.py',evidence:'excerpt',url:'https://github.com/testowner/demo-city/blob/main/services/api/login.py'}]}});
  assert.match(notes,/Browser-fetched issue suggestion, unverified by server/);
  assert.match(notes,/No server-side issue investigation or source verification was performed/);
  assert.doesNotMatch(notes,/AI-generated suggestion/);
  assert.match(notes,/No fetched source excerpts were confirmed/);
});
test('untrusted issue text and foreign source links cannot inject Markdown links',()=>{
  const run=formatter();
  const notes=run({graph,issue:{number:13,title:'](https://attacker.test) #attack\n##fake',
    snippet:'Click [malicious](https://attacker.test) now.',matches:[{nodeId:'fake',confidence:'observed',path:'bad.js'}]},
    guide:{mode:'navigation',answer:'Read the file',
      sources:[{file:'secret.js',evidence:'excerpt',url:'https://evil.example/a'},
        {file:'services/api/login.py',evidence:'excerpt',
         url:'https://github.com/testowner/demo-city/blob/main/services/other/file.py'}]}});
  assert.doesNotMatch(notes,/]\(https:\/\/attacker\.test\)/);
  assert.doesNotMatch(notes,/##fake/);
  assert.doesNotMatch(notes,/evil\.example/);
  assert.doesNotMatch(notes,/bad\.js/);
  assert.match(notes,/Deterministic file navigation \(not a model response\)/);
});
test('rejects nonpublic, unusual or cross-origin repository and issue IDs',()=>{
  const run=formatter();
  for(const url of ['http://github.com/a/b','https://github.com.evil.test/a/b',
    'https://github.com/a/b?token=secret','https://github.com/a/../other']){
    assert.throws(()=>run({graph:{...graph,url},issue}),/Invalid public repository URL/);
  }
  assert.throws(()=>run({graph,issue:{...issue,number:0}}),/open GitHub issue/);
  assert.throws(()=>run({graph:{...graph,source:'demo'},issue}),/public GitHub/);
});
test('independent public-source evidence can be copied without upgrading browser issue trust',()=>{
  const run=formatter();
  const notes=run({graph,issue,browserFallback:true,
    guide:{mode:'source-lead',issueVerified:false,assistantUsed:false,
      sourceFilesRead:1,sourceScope:'live-branch',
      sources:[{file:'services/api/login.py',evidence:'excerpt',
        url:'https://github.com/testowner/demo-city/blob/HEAD/services/api/login.py#L12-L30'}]}});
  assert.match(notes,/issue #12/);
  assert.match(notes,/separately, but the issue itself was not server-verified/);
  assert.match(notes,/Separately fetched public source; issue not verified/);
  assert.match(notes,/browser-only issue feed; public source independently inspected; issue not verified/);
  assert.doesNotMatch(notes,/AI-generated suggestion/);
});
test('browser fallback refuses fabricated model source notes without source-lead provenance',()=>{
  const run=formatter();
  const notes=run({graph,issue,browserFallback:true,guide:{mode:'ai',sourceFilesRead:1,
    sources:[{file:'services/api/login.py',evidence:'excerpt',
      url:'https://github.com/testowner/demo-city/blob/HEAD/services/api/login.py'}]}});
  assert.match(notes,/No fetched source excerpts were confirmed/);
  assert.doesNotMatch(notes,/Separately fetched public source/);
});

test('full issue body takes priority over a truncated GitHub snippet',()=>{
  const run=formatter();
  const notes=run({graph,issue:{...issue,
    snippet:'This is fixed for stream m',
    body:'It is not possible to edit stream names. Update (maintainer): This is fixed for stream messages; recipients need a separate check.'}});
  assert.match(notes,/This is fixed for stream messages/);
  assert.match(notes,/recipients need a separate check/);
  assert.doesNotMatch(notes,/stream m\\n/);
});
test('long report is shortened at a sensible boundary and never silently cut',()=>{
  const run=formatter();
  const report='First complete claim. '+('This issue describes navigation behavior and useful context. '.repeat(40));
  const notes=run({graph,issue:{...issue,snippet:'Tiny clipped',body:report}});
  assert.match(notes,/Report shortened; read the original GitHub issue/);
  assert.ok(notes.length<6501);
  assert.doesNotMatch(notes,/Tiny clipped/);
});
test('independent source notes distinguish filename hints from identifier observations',()=>{
  const run=formatter();
  const notes=run({graph,issue,browserFallback:true,guide:{
    mode:'source-lead',issueVerified:false,assistantUsed:false,sourceFilesRead:2,
    sources:[{file:'services/api/login.py',evidence:'excerpt',matchKind:'path-hint',matchedSymbols:[],
      url:'https://github.com/testowner/demo-city/blob/HEAD/services/api/login.py#L10-L20'},
      {file:'services/api/recipient.py',evidence:'excerpt',matchKind:'symbol',matchedSymbols:['edit_recipient'],
      url:'https://github.com/testowner/demo-city/blob/HEAD/services/api/recipient.py#L4-L15'}]}});
  assert.match(notes,/search candidate only; no reported identifier confirmed/);
  assert.match(notes,/identifier text observed/);
  assert.match(notes,/edit\\_recipient/);
  assert.match(notes,/issue not verified/);
});
