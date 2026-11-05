const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const code=fs.readFileSync(path.join(__dirname,'../static/offline-city.js'),'utf8');
function util(){
  const ctx={window:{},URL,Date};
  vm.runInNewContext(code,ctx);
  return ctx.window.RepoWorldOfflineCity;
}
function storage(){
  const map=new Map();return {
    getItem:k=>map.get(k)||null,
    setItem:(k,v)=>map.set(k,v),
    removeItem:k=>map.delete(k),map
  };
}
function graph(){
  return {source:'github',url:'https://github.com/zulip/zulip-terminal',owner:'zulip',name:'zulip-terminal',
    branch:'HEAD',language:'Python',description:'Public terminal client',nodes:[
      {id:'zulipterminal/ui_tools',name:'UI Tools',kind:'frontend',
       path:'zulipterminal/ui_tools',fileCount:2,
       files:['zulipterminal/ui_tools/boxes.py','zulipterminal/ui_tools/messages.py'],
       symbols:[{name:'get_box',file:'zulipterminal/ui_tools/boxes.py'}]}
    ],edges:[]};
}
test('opt-in backup keeps public map metadata only, not arbitrary secrets',()=>{
  const u=util(),s=storage(),g=graph();
  g.extraSecret='should-never-persist';
  g.nodes[0].evilToken='secret';
  assert.deepEqual(Object.keys(u.save(g,s)).sort(),['fullName','savedAt']);
  const record=u.read(s);
  assert.equal(record.graph.url,'https://github.com/zulip/zulip-terminal');
  assert.equal(record.graph.nodes[0].name,'UI Tools');
  const raw=[...s.map.values()][0];
  assert.doesNotMatch(raw,/should-never-persist|evilToken|csrf|token_hash/);
  assert.equal(record.graph.warnings.length,1);
  assert.match(record.graph.warnings[0],/cached public city/);
});
test('offline backup is repeatable, clearable, and limited to one city',()=>{
  const u=util(),s=storage();
  u.save(graph(),s);
  assert.equal(u.read(s).graph.name,'zulip-terminal');
  const second={...graph(),url:'https://github.com/pallets/flask',owner:'pallets',name:'flask'};
  u.save(second,s);
  assert.equal(u.read(s).graph.name,'flask');
  assert.equal(s.map.size,1);
  assert.equal(u.clear(s),true);
  assert.equal(u.read(s),null);
});
test('rejects injected graph origins, private-ish paths, oversized data and invalid modules',()=>{
  const u=util(),s=storage();
  for(const bad of [
    {...graph(),url:'https://github.com.evil.example/zulip/zulip-terminal'},
    {...graph(),url:'http://github.com/zulip/zulip-terminal'},
    {...graph(),url:'https://github.com/zulip/zulip-terminal?token=abcd'},
    {...graph(),source:'demo'},
    {...graph(),nodes:[{...graph().nodes[0],files:['../../secret.py']}]},
    {...graph(),nodes:[{...graph().nodes[0],id:'../escape'}]},
    {...graph(),nodes:[]},
    {...graph(),nodes:Array.from({length:73},(_,i)=>({...graph().nodes[0],id:'mod'+i,path:'mod'+i}))},
  ])assert.throws(()=>u.save(bad,s),/public|invalid|limit|exceeds/i);
  assert.equal(u.read(s),null);
  const tooBig=graph();tooBig.nodes[0].description='Z'.repeat(2_000_000);
  // User data is trimmed at capture time; stored snapshots remain capped.
  u.save(tooBig,s);
  assert.ok([...s.map.values()][0].length<1_600_000);
});
test('corrupted or malicious stored data does not load',()=>{
  const u=util(),s=storage();
  s.setItem('repoworld:offline-city:v1','{malformed');
  assert.equal(u.read(s),null);
  u.save(graph(),s);
  const data=JSON.parse(s.getItem('repoworld:offline-city:v1'));
  data.graph.url='https://evil.example/zulip/zulip-terminal';
  s.setItem('repoworld:offline-city:v1',JSON.stringify(data));
  assert.equal(u.read(s),null);
  assert.equal(u.read({getItem(){throw Error('blocked');}}),null);
  assert.throws(()=>u.save(graph(),{setItem(){throw Error('full');}}),/full or blocked/);
});

test('portable public city file roundtrips into a new browser with no server data',()=>{
  const u=util(),first=storage(),second=storage(),g=graph();
  g.cookie='never-copy-me';g.nodes[0].answer='model-output-no';
  u.save(g,first);
  const text=u.exportText(first);
  assert.match(text,/"format":"repoworld-public-city-v1"/);
  assert.doesNotMatch(text,/never-copy-me|model-output-no/);
  const output=u.importText(text);
  assert.equal(output.graph.url,'https://github.com/zulip/zulip-terminal');
  const transferred=u.restoreText(text,second);
  assert.equal(transferred.graph.nodes[0].id,'zulipterminal/ui_tools');
  assert.equal(u.read(second).graph.nodes[0].files[1],'zulipterminal/ui_tools/messages.py');
  assert.equal(u.fileName(transferred.graph),'repoworld-zulip-zulip-terminal.json');
  assert.deepEqual(Array.from(first.map.keys()),Array.from(second.map.keys()));
});
test('file restore rejects malformed, forged, oversized and misleading snapshots',()=>{
  const u=util(),s=storage();
  u.save(graph(),s);const valid=u.exportText(s);
  for(const candidate of [
    '{bad-json',
    JSON.stringify({version:1,graph:graph()}),
    JSON.stringify({...JSON.parse(valid),format:'some-other-application'}),
    JSON.stringify({...JSON.parse(valid),graph:{...graph(),url:'https://github.com.evil.tld/a/b'}}),
    JSON.stringify({...JSON.parse(valid),graph:{...graph(),source:'demo'}}),
    JSON.stringify({...JSON.parse(valid),graph:{...graph(),nodes:[{...graph().nodes[0],files:['../../.env']}]}}),
    'x'.repeat(u.maxFileChars+1),
  ]){
    assert.throws(()=>u.importText(candidate),/not valid|not a supported|Invalid|oversized|public|invalid/i);
  }
  assert.equal(u.read(s).graph.name,'zulip-terminal');
});
test('file restore enforces local storage size and never overwrites on parse failure',()=>{
  const u=util(),s=storage();u.save(graph(),s);
  const before=s.map.get('repoworld:offline-city:v1');
  const json=u.exportText(s);
  assert.throws(()=>u.restoreText('bad',s),/Invalid/);
  assert.equal(s.map.get('repoworld:offline-city:v1'),before);
  assert.throws(()=>u.restoreText(json,{setItem(){throw Error('denied');}}),/full or blocked/);
});
