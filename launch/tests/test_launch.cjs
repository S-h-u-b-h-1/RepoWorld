const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const SCRIPT = fs.readFileSync(path.join(__dirname,'../launch.js'), 'utf8');
const HTML = fs.readFileSync(path.join(__dirname,'../index.html'), 'utf8');
const CSS = fs.readFileSync(path.join(__dirname,'../style.css'), 'utf8');
const BACKEND='https://repoworld-3b9e.onrender.com';

function launch(search='') {
  const timeouts=new Map();
  let nextTimer=1;
  const images=[];
  const redirects=[];
  const handlers=new Map();
  const el=new Map();
  for (const id of ['statusHeadline','statusDetail','statusIcon','retry','openDirect']) {
    el.set(id,{
      id,textContent:'',href:'',hidden:id==='retry',
      classList:{states:new Set(),toggle(name,enabled){if(enabled)this.states.add(name);else this.states.delete(name)}},
      addEventListener(event,cb){handlers.set(id+':'+event,cb)}
    });
  }
  class FakeImage {
    constructor(){this.onload=null;this.onerror=null;images.push(this)}
    set src(value){this._src=value}
    get src(){return this._src}
  }
  const window={location:{search,replace(url){redirects.push(url)}},
    addEventListener(event,cb){handlers.set('window:'+event,cb)},
    setTimeout(callback,ms){const id=nextTimer++;timeouts.set(id,{callback,ms});return id}
  };
  const sandbox={
    window,document:{getElementById:id=>el.get(id)},Image:FakeImage,
    URL,URLSearchParams,Date:{now:()=>1793890200000},
    clearTimeout(id){timeouts.delete(id)}
  };
  vm.runInNewContext(SCRIPT,sandbox,{filename:'launch.js'});
  const nextTimeout=(ms)=>{
    const entry=[...timeouts].find(([,item])=>item.ms===ms);
    assert.ok(entry,"Missing scheduled timeout "+ms+"ms");
    timeouts.delete(entry[0]);entry[1].callback();
  };
  return {el,images,redirects,handlers,timeouts,nextTimeout};
}

test('launch page is self-contained and has direct access even without JavaScript',()=>{
  assert.match(HTML,/<a id="openDirect"[^>]+https:\/\/repoworld-3b9e\.onrender\.com/);
  assert.match(HTML,/role="status" aria-live="polite"/);
  assert.match(HTML,/alt="Illustrative RepoWorld city visual fixture/);
  assert.match(HTML,/<script defer src="\.\/launch\.js"><\/script>/);
  assert.match(HTML,/Content-Security-Policy/);
  assert.match(CSS,/@media\(max-width:600px\)/);
  assert.match(CSS,/@media\(prefers-reduced-motion:reduce\)/);
});

test('probes only the static favicon and redirects after a real image load',()=>{
  const page=launch('?repo=pallets%2Fflask');
  assert.equal(page.images.length,1);
  assert.ok(page.images[0].src.startsWith(BACKEND+'/static/favicon.svg?launcher='));
  assert.ok(page.el.get('openDirect').href.includes('repo=pallets%2Fflask'));
  assert.equal(page.redirects.length,0);
  page.images[0].onload();
  assert.ok(page.el.get('statusIcon').classList.states.has('is-ready'));
  assert.equal(page.el.get('retry').hidden,true);
  page.nextTimeout(450);
  assert.equal(page.redirects.length,1);
  assert.equal(page.redirects[0],BACKEND+'/?repo=pallets%2Fflask');
});

test('invalid deep links are not propagated to backend',()=>{
  for(const search of ['?repo=owner%2F..','?repo=owner%2Frepo%2F../../secret','?repo=https%3A%2F%2Fevil.com','?repo=%3Cscript%3E']){
    const page=launch(search);
    assert.equal(page.el.get('openDirect').href,BACKEND+'/');
    page.images[0].onload();page.nextTimeout(450);
    assert.deepEqual(page.redirects,[BACKEND+'/']);
  }
});

test('probe errors retry a bounded number of times and expose explicit manual recovery',()=>{
  const page=launch();
  for(let attempt=1;attempt<=8;attempt++){
    const img=page.images[attempt-1];
    const fail=img.onerror;
    assert.equal(typeof fail,'function');
    fail();
    assert.equal(page.redirects.length,0);
    if(attempt<8){
      assert.equal(page.el.get('retry').hidden,true);
      page.nextTimeout(Math.min(attempt*3000,12000));
      assert.equal(page.images.length,attempt+1);
    }
  }
  assert.equal(page.el.get('retry').hidden,false);
  assert.ok(page.el.get('statusIcon').classList.states.has('is-error'));
  page.handlers.get('retry:click')();
  assert.equal(page.images.length,9);
  assert.equal(page.el.get('retry').hidden,true);
});

test('closing the page cancels pending network probe and no more redirects are scheduled',()=>{
  const page=launch();
  const image=page.images[0];
  assert.equal(typeof image.onload,'function');
  page.handlers.get('window:pagehide')();
  assert.equal(image.onload,null);
  assert.equal(image.onerror,null);
  assert.equal(page.timeouts.size,0);
  assert.equal(page.redirects.length,0);
});
