/* Renderer smoke tests run with Node's built-in test runner, without a browser.
   These do NOT replace full human-in-browser QA. */
const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');

const source = fs.readFileSync(path.join(__dirname, '../static/world.js'), 'utf8');

function world(options={}) {
  const gradient = {addColorStop(){}};
  const context2d = new Proxy({
    createLinearGradient(){return gradient;},createRadialGradient(){return gradient;},
    measureText(s){return {width:s.length*6};},
  }, {get(t,p){return p in t ? t[p] : function(){};}});
  const tooltip={hidden:true,style:{},replaceChildren(){},append(){}};
  const events={};
  const canvas={
    width:0,height:0,style:{},
    getContext(){return context2d;},
    getBoundingClientRect(){return {width:850,height:500,left:0,top:0};},
    addEventListener(type,fn){events[type]=fn;},
    setPointerCapture(){},
  };
  const window={matchMedia(){return {matches:false};},devicePixelRatio:1};
  const sandbox={
    window, document:{getElementById(){return tooltip;},createElement(){return {textContent:''};}},
    ResizeObserver:class { observe(){} disconnect(){} },
    requestAnimationFrame(){return 1;},cancelAnimationFrame(){},
    performance:{now(){return 1000;}},console,
  };
  vm.runInNewContext(source,sandbox);
  const renderer=new window.RepoWorldRenderer(canvas,options);
  return {renderer,canvas,events,tooltip};
}

const graph={nodes:[
  {id:'src/web',name:'Web',kind:'frontend',fileCount:12},
  {id:'src/api',name:'API',kind:'api',fileCount:17},
  {id:'src/db',name:'Data',kind:'database',fileCount:4},
],edges:[
  {source:'src/web',target:'src/api',type:'import'},
  {source:'src/api',target:'src/db',type:'import'},
]};

test('renderer creates a real perspective projection with finite coords',()=>{
  const {renderer}=world();renderer.setGraph(graph);renderer.render(1000);
  const pt=renderer.project(5,2,-3);
  assert.ok(Number.isFinite(pt.x)&&Number.isFinite(pt.y)&&Number.isFinite(pt.depth));
  assert.equal(renderer.nodes.length,3);
  assert.equal(renderer.hitAreas.length,3);
  assert.notEqual(renderer.project(0,1,0).y,renderer.project(0,0,0).y);
  assert.notEqual(renderer.project(0,0,0).scale,renderer.project(0,0,10).scale);
});

test('graph scene uses only observed links, and highlights static path',()=>{
  const {renderer}=world();renderer.setGraph(graph);renderer.setMode('flows');
  const path=renderer.pickPathEdges();
  assert.ok(path.size>=1&&path.size<=graph.edges.length);
  assert.ok([...path].every(e=>e.type==='import'));
});

test('camera and selection controls work',()=>{
  const {renderer,events}=world();renderer.setGraph(graph);
  renderer.setSelected('src/db',{focus:true});assert.equal(renderer.selected,'src/db');
  assert.notEqual(renderer.targetPan.x,0);
  events.keydown({key:'ArrowRight',preventDefault(){}});
  assert.notEqual(renderer.yaw,-.68);
  events.wheel({deltaY:-90,preventDefault(){}});
  assert.ok(renderer.targetDistance<renderer.overviewDistance);
  renderer.render(1040);renderer.render(1080);
  assert.ok(renderer.distance<renderer.overviewDistance);
  renderer.resetCamera();assert.equal(renderer.yaw,-.71);
  assert.equal(renderer.targetPan.x,0);
});

test('renderer rejects unknown map modes and unknown module selections',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  renderer.setMode('not-a-mode');assert.equal(renderer.mode,'structure');
  renderer.setSelected('not-present');assert.equal(renderer.selected,null);
});

test('Neon City groups nodes into districts and supports camera teleport',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  const districts=renderer.getDistricts();
  assert.equal(districts.length,3);
  assert.ok(districts.some(d=>d.kind==='frontend'&&d.name==='Frontend Boulevard'));
  assert.ok(districts.some(d=>d.kind==='database'&&d.name==='Data Harbor'));
  assert.equal(districts.reduce((count,d)=>count+d.count,0),3);
  assert.equal(renderer.focusDistrict('api'),true);
  assert.equal(renderer.activeDistrict,'api');
  assert.equal(renderer.focusDistrict('nonexistent'),false);
  renderer.resetCamera();
  assert.equal(renderer.activeDistrict,null);
});

test('Hotspots mean observed static connectivity, with no new invented edges',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  const hottest=renderer.getHotspots();
  assert.equal(hottest.length,1);
  assert.equal(hottest[0].id,'src/api');
  assert.equal(hottest[0].degree,2);
  const edgeCount=renderer.edges.length;
  const focused=renderer.focusHotspot();
  assert.equal(focused.id,'src/api');
  assert.equal(renderer.mode,'hotspots');
  assert.equal(renderer.selected,'src/api');
  assert.equal(renderer.edges.length,edgeCount);
  renderer.setTraffic(false);
  assert.equal(renderer.traffic,false);
});

test('change-impact renderer only highlights IDs and links in the loaded graph',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  const oldCount=renderer.edges.length;
  renderer.setImpactTrace({root:'src/db',direct:[{nodeId:'src/api'},{nodeId:'invented'}],
    indirect:[{nodeId:'src/web'}],edges:[{source:'src/api',target:'src/db'},{source:'invented',target:'src/db'}]});
  assert.equal(renderer.impact.root,'src/db');
  assert.deepEqual([...renderer.impact.direct],['src/api']);
  assert.deepEqual([...renderer.impact.indirect],['src/web']);
  assert.equal(renderer.impact.edges.size,1);
  assert.equal(renderer.edges.length,oldCount);
  renderer.render(1100);
  renderer.setImpactTrace(null);
  assert.equal(renderer.impact,null);
  renderer.setImpactTrace({root:'not-a-real-module',direct:[],indirect:[],edges:[]});
  assert.equal(renderer.impact,null);
});

test('issue markers are limited to existing buildings and never fabricate dependency edges',()=>{
  const {renderer}=world();renderer.setGraph(graph);const edges=renderer.edges.length;
  renderer.setIssueMarkers({'src/api':{referenced:[8,10],suggested:[]},'src/db':{referenced:[],suggested:[9]},'invented':{referenced:[1]}});
  assert.equal(renderer.issueMarkers.get('src/api').referenced,2);
  assert.equal(renderer.issueMarkers.get('src/db').suggested,1);
  assert.equal(renderer.issueMarkers.has('invented'),false);
  renderer.render(1300);assert.equal(renderer.edges.length,edges);
  renderer.setGraph(graph);assert.equal(renderer.issueMarkers.size,0);
});


test('open-issue city pins intercept clicks and open issue investigation before the building',()=>{
  const calls=[];
  const {renderer,events}=world({onIssueSelect:id=>calls.push(['issue',id]),onSelect:id=>calls.push(['building',id])});
  renderer.setGraph(graph);
  renderer.setIssueMarkers({'src/api':{referenced:[81],suggested:[88]}});
  renderer.render(1500);
  assert.equal(renderer.issueHitAreas.length,1);
  const pin=renderer.issueHitAreas.find(x=>x.nodeId==='src/api');
  assert.equal(pin.count,2);
  assert.ok(renderer.getIssueHit(pin.x,pin.y));
  events.pointerdown({pointerId:1,clientX:pin.x,clientY:pin.y});
  events.pointerup({clientX:pin.x,clientY:pin.y});
  assert.deepEqual(calls,[['issue','src/api']]);
  assert.equal(renderer.selected,'src/api');
  assert.equal(renderer.edges.length,2);
  renderer.setIssueMarkers({});renderer.render(1600);
  assert.equal(renderer.issueHitAreas.length,0);
});

test('issue pin suggestion counts remain unverified, and no match means no pin',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  renderer.setIssueMarkers({'src/api':{referenced:[],suggested:[41]},'not-in-graph':{referenced:[99],suggested:[]}});
  renderer.render(1700);
  assert.equal(renderer.issueHitAreas.length,1);
  assert.equal(renderer.issueHitAreas[0].referenced,0);
  assert.equal(renderer.issueHitAreas[0].suggested,1);
  assert.equal(renderer.issueMarkers.has('not-in-graph'),false);
});


test('quiet neon retains distinct subdued district colors and true perspective',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  const palette=renderer.getDistricts().map(d=>d.color);
  assert.equal(new Set(palette).size,palette.length);
  assert.ok(palette.every(c=>/^#[0-9a-f]{6}$/i.test(c)));
  // Buildings are still projected in x, y and depth, with camera-dependent scale.
  const a=renderer.project(0,0,5),b=renderer.project(0,10,5),c=renderer.project(0,0,25);
  assert.notEqual(a.y,b.y);assert.notEqual(a.scale,c.scale);
  assert.ok(renderer.districts.every(d=>d.nodes.every(n=>n.height>0)));
});

test('overview camera fits a small repository with widely spaced islands',()=>{
  const {renderer,events}=world();
  renderer.width=1440;renderer.height=900;
  const nodes=[];
  for(const [kind,count] of [['core',7],['docs',5],['test',1]]){
    for(let i=0;i<count;i++)nodes.push({id:`${kind}/${i}`,name:`${kind} ${i}`,kind,fileCount:i+3});
  }
  renderer.setGraph({nodes,edges:[]});
  // The old fixed 105-unit overview hid the upper island in this configuration.
  assert.ok(renderer.overviewDistance>105);
  for(const district of renderer.districts){
    for(const x of [-district.halfWidth,district.halfWidth]){
      for(const z of [-district.halfDepth,district.halfDepth]){
        for(const y of [0,-5]){
          const pt=renderer.project(district.center.x+x,y,district.center.z+z);
          assert.ok(pt.x>=90&&pt.x<=1350,`X clipped: ${district.name}, ${pt.x}`);
          assert.ok(pt.y>=115&&pt.y<=790,`Y clipped: ${district.name}, ${pt.y}`);
        }
      }
    }
  }
  events.wheel({deltaY:-9999,preventDefault(){}});
  assert.ok(renderer.distance>=58,'camera can zoom beyond readable range');
  renderer.pitch=.2;
  events.dblclick({preventDefault(){}});
  assert.equal(renderer.pitch,.83);
  assert.equal(renderer.distance,renderer.overviewDistance);
  assert.equal(renderer.pan.x,0);
  assert.equal(renderer.targetPan.z,0);
});


test('cursor-focused zoom preserves a ground point while the camera eases',()=>{
  const {renderer,events}=world();renderer.setGraph(graph);
  const x=195,y=262;
  const ground=renderer.screenToWorldOnPlane(x,y,0);
  assert.ok(ground);
  const before=renderer.project(ground.x,0,ground.z);
  assert.ok(Math.abs(before.x-x)<.001&&Math.abs(before.y-y)<.001);
  const original=renderer.distance;
  events.wheel({deltaY:-92,deltaMode:0,clientX:x,clientY:y,preventDefault(){}});
  assert.ok(renderer.targetDistance<original);
  let t=1000;
  for(let i=0;i<35;i++)renderer.render(t+=16);
  const after=renderer.project(ground.x,0,ground.z);
  assert.ok(Math.abs(after.x-x)<.3,`Zoom drifted ${after.x-x}px horizontally`);
  assert.ok(Math.abs(after.y-y)<.3,`Zoom drifted ${after.y-y}px vertically`);
  assert.ok(Math.abs(renderer.distance-renderer.targetDistance)<.04);
});

test('precision wheel zoom supports tiny trackpad increments and line/page deltas',()=>{
  const {renderer,events}=world();renderer.setGraph(graph);
  const start=renderer.targetDistance;
  events.wheel({deltaY:-1,deltaMode:0,clientX:140,clientY:250,preventDefault(){}});
  const step=start-renderer.targetDistance;
  assert.ok(step>0 && step<start*.01,`trackpad step was ${step}`);
  const next=renderer.targetDistance;
  events.wheel({deltaY:-1,deltaMode:1,clientX:140,clientY:250,preventDefault(){}});
  assert.ok(next-renderer.targetDistance>step*10,'line-mode wheel should be normalized');
  const beforePage=renderer.targetDistance;
  events.wheel({deltaY:1,deltaMode:2,clientX:140,clientY:250,preventDefault(){}});
  assert.ok(renderer.targetDistance>beforePage);
  events.keydown({key:'+',preventDefault(){}});
  assert.ok(renderer.targetDistance<beforePage*1.26);
  events.keydown({key:'Home',preventDefault(){}});
  assert.equal(renderer.distance,renderer.overviewDistance);
  assert.equal(renderer.targetDistance,renderer.overviewDistance);
  assert.equal(renderer.zoomAnchor,null);
});

test('mouse wheel zoom remains bounded and cannot jump arbitrarily',()=>{
  const {renderer,events}=world();renderer.setGraph(graph);
  const initial=renderer.targetDistance;
  events.wheel({deltaY:-9999,deltaMode:0,clientX:430,clientY:270,preventDefault(){}});
  assert.ok(renderer.targetDistance>initial*.7,'one wheel event should not jump to maximum zoom');
  for(let i=0;i<65;i++)events.wheel({deltaY:-9999,deltaMode:0,clientX:430,clientY:270,preventDefault(){}});
  assert.equal(renderer.targetDistance,36);
  for(let i=0;i<90;i++)events.wheel({deltaY:9999,deltaMode:0,clientX:430,clientY:270,preventDefault(){}});
  assert.equal(renderer.targetDistance,850);
});

test('touch pinch zoom moves towards midpoint without accidentally selecting a module',()=>{
  const selections=[];
  const {renderer,events}=world({onSelect:id=>selections.push(id),onIssueSelect:id=>selections.push(id)});
  renderer.setGraph(graph);
  const original=renderer.targetDistance;
  events.pointerdown({pointerId:1,pointerType:'touch',clientX:320,clientY:210});
  events.pointerdown({pointerId:2,pointerType:'touch',clientX:420,clientY:210});
  events.pointermove({pointerId:1,pointerType:'touch',clientX:295,clientY:210});
  assert.ok(renderer.targetDistance<original);
  events.pointerup({pointerId:1,pointerType:'touch',clientX:295,clientY:210});
  events.pointerup({pointerId:2,pointerType:'touch',clientX:420,clientY:210});
  assert.deepEqual(selections,[]);
  assert.equal(renderer.touchPointers.size,0);
  assert.equal(renderer.pinchHappened,false);
});

test('inverted projection matches perspective positions for roofs and districts',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  renderer.yaw=-.23;renderer.pitch=.86;
  for(const [x,y,z] of [[-18,0,10],[4,5,6],[0,13,0]]){
    const projected=renderer.project(x,y,z);
    const restored=renderer.screenToWorldOnPlane(projected.x,projected.y,y);
    assert.ok(restored,`no plane intersection for ${x},${y},${z}`);
    assert.ok(Math.abs(restored.x-x)<1e-7,`x mismatch ${restored.x} vs ${x}`);
    assert.ok(Math.abs(restored.z-z)<1e-7,`z mismatch ${restored.z} vs ${z}`);
  }
});

test('issue markers distinguish fetched-source identifiers from issue path mentions',()=>{
  const {renderer}=world();renderer.setGraph(graph);
  renderer.setIssueMarkers({'src/db':{observed:[717],referenced:[],suggested:[]}});
  assert.equal(renderer.issueMarkers.get('src/db').observed,1);
  assert.equal(renderer.issueMarkers.get('src/db').referenced,0);
  const before=renderer.edges.length;renderer.render(1100);
  assert.equal(renderer.edges.length,before);
});

test('architectural façades keep module towers prominent and bounds finite after orbit',()=>{
  const {renderer}=world();renderer.setGraph({nodes:[
    {id:'src/a',name:'A',kind:'api',fileCount:1},
    {id:'src/b',name:'B',kind:'frontend',fileCount:140},
    {id:'src/c',name:'C',kind:'docs',fileCount:7}
  ],edges:[]});
  assert.ok(renderer.nodes.every(n=>n.height>=6.2&&n.height<=15.4));
  assert.ok(renderer.nodes.every(n=>n.width>=1.9&&n.width<=3.45));
  renderer.render(2000);renderer.yaw=1.1;renderer.render(2040);
  renderer.yaw=-2.4;renderer.render(2080);
  assert.equal(renderer.hitAreas.length,3);
  assert.ok(renderer.hitAreas.every(x=>Number.isFinite(x.roof.x)&&Number.isFinite(x.roof.y)));
  assert.equal(renderer.edges.length,0);
});


test('dense 72-module cities never overlap real buildings or district footprints',()=>{
  const {renderer}=world();
  const kinds=['core','frontend','api','service','library','database','security','infra','test','docs'];
  const nodes=Array.from({length:72},(_,i)=>({id:'dense/'+i,name:'Module '+i,
    kind:kinds[i%kinds.length],fileCount:1+(i*41)%250}));
  renderer.setGraph({nodes,edges:[]});
  assert.equal(renderer.nodes.length,72);
  for(const district of renderer.districts){
    for(let i=0;i<district.nodes.length;i++){
      const a=district.nodes[i];
      assert.ok(Math.abs(a.x-district.center.x)+a.width<=district.halfWidth-1.5);
      assert.ok(Math.abs(a.z-district.center.z)+a.width<=district.halfDepth-1.5);
      for(let j=i+1;j<district.nodes.length;j++){
        const b=district.nodes[j];
        assert.ok(Math.abs(a.x-b.x)>=a.width+b.width+.5||
                  Math.abs(a.z-b.z)>=a.width+b.width+.5,
                  'overlapping modules '+a.id+' and '+b.id);
      }
      if(district.central)assert.ok(Math.abs(a.x)>=a.width+2.85+.5||
                                    Math.abs(a.z)>=a.width+2.85+.5,
                                    'module overlaps the illustrative beacon');
    }
  }
  for(let i=0;i<renderer.districts.length;i++)for(let j=i+1;j<renderer.districts.length;j++){
    const a=renderer.districts[i],b=renderer.districts[j];
    assert.ok(Math.abs(a.center.x-b.center.x)>=a.halfWidth+b.halfWidth+5||
              Math.abs(a.center.z-b.center.z)>=a.halfDepth+b.halfDepth+5,
              'overlapping floating districts '+a.kind+' and '+b.kind);
  }
  renderer.render(2000);
  assert.equal(renderer.hitAreas.length,72);
});

test('single dominant district uses roomier spiral and camera fits all module crowns',()=>{
  const {renderer}=world();
  const nodes=Array.from({length:72},(_,i)=>({id:'core/'+i,name:'Core '+i,kind:'core',fileCount:12+i}));
  renderer.setGraph({nodes,edges:[]});
  assert.equal(renderer.districts.length,1);
  assert.ok(renderer.districts[0].halfWidth>=30);
  assert.ok(renderer.focusDistrict('core'));
  renderer.distance=renderer.targetDistance;
  renderer.pan={...renderer.targetPan};
  for(const node of renderer.nodes){
    const p=renderer.project(node.x,node.height+.37,node.z);
    assert.ok(p.x>=0&&p.x<=renderer.width&&p.y>=0&&p.y<=renderer.height);
  }
});

test('small mobile canvas suppresses sub-pixel windows and throttles idle frames',()=>{
  const {renderer}=world();
  renderer.width=390;renderer.height=844;renderer.setGraph(graph);
  renderer.render(2000);
  const painted=renderer.lastPaintAt;
  renderer.render(2012);
  assert.equal(renderer.lastPaintAt,painted);
  renderer.render(2040);
  assert.equal(renderer.lastPaintAt,2040);
  const d=renderer.fitOverviewDistance();
  assert.ok(d<=850 && d>=110);
});
