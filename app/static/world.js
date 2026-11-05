/* RepoWorld Neon City: dependency-free, perspective-3D canvas renderer.
 * Districts group modules by heuristic path classification. Glowing links are
 * sampled STATIC IMPORTS, never asserted to be observed runtime traffic.
 */
(function () {
  'use strict';
  const COLORS = Object.freeze({
    frontend:'#b39ccc', api:'#8abfd3', service:'#b7b6d3', library:'#8dc5cb',
    database:'#8bc6b5', security:'#d0a0b1', infra:'#d9b18f',
    test:'#c6a9d7', docs:'#a7bad0', core:'#e0c7a3',
  });
  const DISTRICTS = Object.freeze({
    frontend:{name:'Frontend Boulevard',short:'Frontend',hint:'User interfaces, screens and components',icon:'◈'},
    api:{name:'API Heights',short:'API',hint:'Routes and interfaces to other services',icon:'⬡'},
    service:{name:'Service Quarter',short:'Services',hint:'Application and business-logic modules',icon:'◇'},
    database:{name:'Data Harbor',short:'Data',hint:'Storage, schema and state-related files',icon:'▥'},
    library:{name:'Utility Alley',short:'Libraries',hint:'Shared code, packages and helpers',icon:'✳'},
    security:{name:'Identity Ward',short:'Security',hint:'Security- and authentication-related paths',icon:'◆'},
    infra:{name:'Infra Grid',short:'Infrastructure',hint:'Deployment and infrastructure configuration',icon:'▦'},
    test:{name:'Test Sector',short:'Tests',hint:'Test suites and validation tooling',icon:'✦'},
    docs:{name:'Archive Row',short:'Docs',hint:'Documentation and design notes',icon:'☷'},
    core:{name:'Core Nexus',short:'Core',hint:'Repository root and foundational modules',icon:'◎'},
  });
  const DISTRICT_ORDER = ['frontend','api','service','library','database','core','security','infra','test','docs'];
  const PI2=Math.PI*2;
  const MIN_CAMERA_DISTANCE=36, MAX_CAMERA_DISTANCE=850;
  const clamp=(n,a,b)=>Math.max(a,Math.min(b,n));
  function rgb(hex){const c=(hex||'#ffffff').replace('#','');return [parseInt(c.slice(0,2),16)||0,parseInt(c.slice(2,4),16)||0,parseInt(c.slice(4,6),16)||0];}
  function rgba(hex,opacity){const [r,g,b]=rgb(hex);return `rgba(${r},${g},${b},${opacity})`;}
  function mix(from,to,t){const a=rgb(from),b=rgb(to);return `rgb(${a.map((v,i)=>Math.round(v*(1-t)+b[i]*t)).join(',')})`;}
  function hash(s){let h=2166136261;for(let i=0;i<String(s).length;i++){h^=s.charCodeAt(i);h=Math.imul(h,16777619);}return (h>>>0)/4294967295;}
  function rounded(ctx,x,y,w,h,r){if(w>0&&h>0){ctx.beginPath();ctx.roundRect(x,y,w,h,Math.max(0,Math.min(r,w/2,h/2)));}}
  function poly(ctx,points){ctx.beginPath();points.forEach((p,i)=>i?ctx.lineTo(p.x,p.y):ctx.moveTo(p.x,p.y));ctx.closePath();}

  class RepoWorldRenderer {
    constructor(canvas, options={}){
      this.canvas=canvas;this.ctx=canvas.getContext('2d',{alpha:false});
      this.onSelect=options.onSelect||(()=>{});this.onIssueSelect=options.onIssueSelect||(()=>{});this.onHover=options.onHover||(()=>{});
      this.nodes=[];this.edges=[];this.districts=[];this.hotspots=[];this.mode='structure';this.selected=null;this.hovered=null;this.impact=null;this.issueMarkers=new Map();
      this.yaw=-.71;this.pitch=.85;this.distance=140;this.targetDistance=140;this.overviewDistance=140;this.zoomAnchor=null;
      this.pan={x:0,z:0};this.targetPan={x:0,z:0};this.activeDistrict=null;
      this.width=0;this.height=0;this.pixelRatio=1;this.spin=false;this.traffic=true;
      this.isDragging=false;this.dragDistance=0;this.hitAreas=[];this.issueHitAreas=[];this.time=0;
      this.touchPointers=new Map();this.pinchDistance=0;this.pinchHappened=false;
      this.motion=!!window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;
      this.tooltip=document.getElementById('sceneTooltip');
      this.resizeObserver=new ResizeObserver(()=>this.resize());this.resizeObserver.observe(canvas);
      this.addEvents();this.resize();this.render();
    }
    resize(){
      const rect=this.canvas.getBoundingClientRect();
      this.width=Math.max(100,rect.width);this.height=Math.max(100,rect.height);
      this.pixelRatio=Math.min(window.devicePixelRatio||1,2);
      this.canvas.width=Math.round(this.width*this.pixelRatio);
      this.canvas.height=Math.round(this.height*this.pixelRatio);
      this.ctx.setTransform(this.pixelRatio,0,0,this.pixelRatio,0,0);
    }
    setGraph(graph){
      const groups=new Map();
      const nodes=(graph.nodes||[]).map(item=>({...item,kind:DISTRICTS[item.kind]?item.kind:'core',x:0,y:0,z:0}));
      for(const node of nodes){if(!groups.has(node.kind))groups.set(node.kind,[]);groups.get(node.kind).push(node);}
      const present=DISTRICT_ORDER.filter(kind=>groups.has(kind));
      const primary=groups.has('core')?'core':present.slice().sort((a,b)=>
        groups.get(b).reduce((v,n)=>v+(n.fileCount||1),0)-groups.get(a).reduce((v,n)=>v+(n.fileCount||1),0))[0];
      // Every module is a real clickable building. Previous 4.4-unit grid
      // spacing could overlap buildings up to 6.9 units wide. Keep a physical
      // gap at every density, including the 72-module graph limit.
      const TILE=7.9, PLATFORM_GAP=5.5;
      const positions=[[-.96,-.63],[.31,-1],[1,-.47],[-1,.28],[1,.29],
        [-.8,.88],[.18,1],[.82,.82],[-.32,-1.15]];
      const spiralSlot=index=>{
        let ring=1;
        while(index>=8*ring){index-=8*ring;ring++;}
        const side=2*ring;
        if(index<side)return {x:ring,z:-ring+index};
        index-=side;
        if(index<side)return {x:ring-index,z:ring};
        index-=side;
        if(index<side)return {x:-ring,z:ring-index};
        index-=side;
        return {x:-ring+index,z:-ring};
      };
      const planned=present.map(kind=>{
        const items=groups.get(kind),central=kind===primary;
        const columns=Math.max(1,Math.ceil(Math.sqrt(items.length)));
        const rows=Math.ceil(items.length/columns);
        items.sort((a,b)=>b.fileCount-a.fileCount||String(a.id).localeCompare(String(b.id)));
        items.forEach((node,i)=>{
          if(central){
            const slot=spiralSlot(i);
            node.x=slot.x*TILE;node.z=slot.z*TILE;
          }else{
            node.x=((i%columns)-(columns-1)/2)*TILE;
            node.z=(Math.floor(i/columns)-(rows-1)/2)*TILE;
          }
          node.width=clamp(1.65+Math.log2(Math.max(1,node.fileCount)+1)*.26,1.9,3.45);
          node.height=clamp(5.5+Math.log2(Math.max(1,node.fileCount)+1)*1.29+hash(node.id)*2.9,6.2,15.4);
          node.color=COLORS[kind];node.district=DISTRICTS[kind].name;
          node.landmark=false;node.degree=0;
        });
        const halfWidth=Math.max(central?15.2:7.5,...items.map(node=>Math.abs(node.x)+node.width+2));
        const halfDepth=Math.max(central?14.6:7.4,...items.map(node=>Math.abs(node.z)+node.width+2));
        return {kind,...DISTRICTS[kind],color:COLORS[kind],count:items.length,
          center:{x:0,z:0},halfWidth,halfDepth,nodes:items,central};
      });
      const positioned=[];
      // Keep the old floating-district orientation, but push each island
      // outward until its actual occupied bounds cannot overlap another.
      let satellite=0;
      for(const district of planned.filter(d=>d.central).concat(planned.filter(d=>!d.central))){
        if(!district.central){
          const [dx,dz]=positions[satellite++%positions.length];
          let found=false;
          for(let radius=28;radius<=700;radius+=3.5){
            const cx=dx*radius,cz=dz*radius;
            const overlaps=positioned.some(other=>
              Math.abs(cx-other.center.x)<district.halfWidth+other.halfWidth+PLATFORM_GAP &&
              Math.abs(cz-other.center.z)<district.halfDepth+other.halfDepth+PLATFORM_GAP);
            if(!overlaps){
              district.center={x:cx,z:cz};found=true;break;
            }
          }
          if(!found)throw Error('Unable to place a code district without collision');
          for(const node of district.nodes){node.x+=district.center.x;node.z+=district.center.z;}
        }
        positioned.push(district);
      }
      this.districts=positioned;
      this.nodes=nodes;this.issueMarkers=new Map();this.issueHitAreas=[];
      const lookup=new Map(nodes.map(n=>[n.id,n]));
      this.edges=(graph.edges||[]).map(edge=>({...edge,a:lookup.get(edge.source),b:lookup.get(edge.target)})).filter(e=>e.a&&e.b);
      for(const edge of this.edges){edge.a.degree++;edge.b.degree++;}
      this.hotspots=[...nodes].filter(n=>n.degree>=2).sort((a,b)=>b.degree-a.degree||b.fileCount-a.fileCount).slice(0,5);
      for(const district of this.districts){const main=[...district.nodes].sort((a,b)=>b.degree-a.degree||b.fileCount-a.fileCount)[0];if(main)main.landmark=true;}
      this.selected=null;this.hovered=null;this.activeDistrict=null;this.impact=null;
      // A repository with only three districts can still have far-apart islands.
      // Fit the *actual projected island bounds* instead of assuming fewer districts
      // always means a closer camera. This prevents clipped cities on first load.
      this.overviewDistance=this.fitOverviewDistance();
      this.resetCamera();
      // The initial empty frame may share this animation timestamp.
      // Never throttle the first real drawing after a repository switch.
      this.lastPaintAt=null;
    }
    getDistricts(){return this.districts.map(d=>({kind:d.kind,name:d.name,short:d.short,description:d.hint,count:d.count,color:d.color}));}
    getHotspots(){return [...this.hotspots];}
    setIssueMarkers(byNode){
      const ids=new Set(this.nodes.map(n=>n.id));this.issueMarkers=new Map();
      for(const [id,data] of Object.entries(byNode||{})){
        if(!ids.has(id))continue;
        this.issueMarkers.set(id,{referenced:Array.isArray(data.referenced)?data.referenced.length:0,
          suggested:Array.isArray(data.suggested)?data.suggested.length:0,
          observed:Array.isArray(data.observed)?data.observed.length:0});
      }
    }
    setMode(mode){if(['structure','dependencies','flows','hotspots'].includes(mode))this.mode=mode;}
    setTraffic(value){this.traffic=!!value;}
    setImpactTrace(trace){
      if(!trace){this.impact=null;return;}
      const ids=new Set(this.nodes.map(n=>n.id));
      if(!ids.has(trace.root)){this.impact=null;return;}
      this.impact={root:trace.root,
        direct:new Set((trace.direct||[]).map(i=>i.nodeId).filter(i=>ids.has(i))),
        indirect:new Set((trace.indirect||[]).map(i=>i.nodeId).filter(i=>ids.has(i))),
        edges:new Set((trace.edges||[]).filter(e=>ids.has(e.source)&&ids.has(e.target)).map(e=>e.source+'\0'+e.target))};
    }
    setSelected(id,{focus=false}={}){
      const node=this.nodes.find(n=>n.id===id);if(!node)return;
      this.selected=id;this.activeDistrict=focus?node.kind:this.activeDistrict;
      if(focus){this.zoomAnchor=null;this.targetPan={x:node.x,z:node.z};this.targetDistance=Math.min(this.distance,60);}
    }
    fitDistrictDistance(district){
      const original={distance:this.distance,yaw:this.yaw,pitch:this.pitch,pan:this.pan};
      this.yaw=-.54;this.pitch=.78;this.pan={...district.center};
      const side=this.width<600?18:Math.min(90,this.width*.085);
      const top=Math.min(116,this.height*.135),bottom=this.height-(this.width<600?90:110);
      const samples=[];
      for(const x of [-district.halfWidth,district.halfWidth])
        for(const z of [-district.halfDepth,district.halfDepth]){
          samples.push([district.center.x+x,0,district.center.z+z]);
          samples.push([district.center.x+x,-5,district.center.z+z]);
        }
      for(const node of district.nodes)samples.push([node.x,node.height+.37,node.z]);
      if(district.central)samples.push([0,27,0]);
      let fitted=MAX_CAMERA_DISTANCE;
      for(let distance=65;distance<=MAX_CAMERA_DISTANCE;distance+=5){
        this.distance=distance;
        const projected=samples.map(p=>this.project(...p));
        if(projected.every(p=>p.x>=side&&p.x<=this.width-side&&p.y>=top&&p.y<=bottom)){
          fitted=distance;break;
        }
      }
      this.distance=original.distance;this.yaw=original.yaw;
      this.pitch=original.pitch;this.pan=original.pan;
      return fitted;
    }
    focusDistrict(kind){
      const district=this.districts.find(d=>d.kind===kind);if(!district)return false;
      this.activeDistrict=kind;
      this.zoomAnchor=null;
      const distance=this.fitDistrictDistance(district);
      this.targetPan={...district.center};
      this.targetDistance=clamp(distance,65,MAX_CAMERA_DISTANCE);
      this.yaw=-.54;this.pitch=.78;
      return true;
    }
    focusHotspot(){
      const target=this.getHotspots()[0];if(!target)return null;
      this.setMode('hotspots');this.setSelected(target.id,{focus:true});return target;
    }
    fitOverviewDistance(){
      if(!this.districts.length)return 140;
      const old={distance:this.distance,yaw:this.yaw,pitch:this.pitch,pan:this.pan};
      this.yaw=-.71;this.pitch=.83;this.pan={x:0,z:0};
      const marginX=this.width<600?18:Math.min(92,this.width*.085);
      const top=Math.min(116,this.height*.135),bottom=this.height-(this.width<600?90:110);
      const sample=[];
      for(const d of this.districts){
        for(const x of [-d.halfWidth,d.halfWidth])for(const z of [-d.halfDepth,d.halfDepth]){
          sample.push([d.center.x+x,0,d.center.z+z]);
          sample.push([d.center.x+x,-5,d.center.z+z]);
        }
        for(const n of d.nodes)sample.push([n.x,n.height,n.z]);
      }
      if(this.districts.some(d=>d.central))sample.push([0,27,0]);
      let fitted=110;
      for(let distance=110;distance<=MAX_CAMERA_DISTANCE;distance+=5){
        this.distance=distance;
        const pixels=sample.map(point=>this.project(...point));
        const x=pixels.map(p=>p.x),y=pixels.map(p=>p.y);
        fitted=distance;
        if(Math.min(...x)>=marginX && Math.max(...x)<=this.width-marginX &&
           Math.min(...y)>=top && Math.max(...y)<=bottom)break;
      }
      this.distance=old.distance;this.yaw=old.yaw;this.pitch=old.pitch;this.pan=old.pan;
      return fitted;
    }
    resetCamera(){
      this.yaw=-.71;this.pitch=.83;this.pan={x:0,z:0};this.targetPan={x:0,z:0};
      this.distance=this.overviewDistance;this.targetDistance=this.overviewDistance;
      this.zoomAnchor=null;this.activeDistrict=null;
    }
    project(x,y,z){
      const dx=x-this.pan.x,dz=z-this.pan.z;
      const a=dx*Math.cos(this.yaw)-dz*Math.sin(this.yaw);
      const b=dx*Math.sin(this.yaw)+dz*Math.cos(this.yaw);
      const elevation=y*Math.cos(this.pitch)-b*Math.sin(this.pitch);
      const depth=y*Math.sin(this.pitch)+b*Math.cos(this.pitch);
      const focal=Math.min(this.width*1.30,this.height*1.90);
      const scale=focal/Math.max(10,this.distance+depth);
      return {x:this.width*.5+a*scale,y:this.height*.55-elevation*scale,depth,scale};
    }
    // Undo the perspective projection on a horizontal world plane. Using this
    // instead of a fixed zoom center lets the point under the cursor stay put.
    screenToWorldOnPlane(screenX,screenY,planeY=0,distance=this.distance,pan=this.pan){
      const focal=Math.min(this.width*1.30,this.height*1.90);
      const u=(screenX-this.width*.5)/focal;
      const v=(screenY-this.height*.55)/focal;
      const sin=Math.sin(this.pitch),cos=Math.cos(this.pitch);
      const denominator=sin-v*cos;
      // Near-horizon rays do not reliably intersect the selected plane.
      if(denominator<=.12)return null;
      const b=(v*(distance+planeY*sin)+planeY*cos)/denominator;
      const a=u*(distance+planeY*sin+b*cos);
      const x=pan.x+a*Math.cos(this.yaw)+b*Math.sin(this.yaw);
      const z=pan.z-a*Math.sin(this.yaw)+b*Math.cos(this.yaw);
      return Number.isFinite(x)&&Number.isFinite(z)?{x,z}:null;
    }
    zoomToward(factor,screenX=this.width*.5,screenY=this.height*.55){
      if(!Number.isFinite(factor)||factor<=0||Math.abs(factor-1)<1e-10)return;
      const cx=Number.isFinite(screenX)?clamp(screenX,0,this.width):this.width*.5;
      const cy=Number.isFinite(screenY)?clamp(screenY,0,this.height):this.height*.55;
      const issue=this.getIssueHit(cx,cy);
      const node=issue?this.nodes.find(n=>n.id===issue.nodeId):this.getHit(cx,cy);
      const planeY=node?node.height*.5:0;
      // Some screen rays (e.g. the horizon at extreme tilt) cannot meet the
      // ground; safely fall back to the center instead of jumping the camera.
      let x=cx,y=cy,elevation=planeY;
      let anchor=this.screenToWorldOnPlane(x,y,elevation);
      if(!anchor){x=this.width*.5;y=this.height*.55;elevation=0;
        anchor=this.screenToWorldOnPlane(x,y,0);}
      if(!anchor)return;
      this.zoomAnchor={x,y,planeY:elevation,world:anchor};
      this.targetDistance=clamp(this.targetDistance*factor,MIN_CAMERA_DISTANCE,MAX_CAMERA_DISTANCE);
      // A new zoom overrides an unfinished automatic district focus.
      this.targetPan={...this.pan};
    }
    addEvents(){
      // Restore the unobstructed city overview without adding another visible button.
      this.canvas.addEventListener('dblclick', e => {
        e.preventDefault();this.resetCamera();this.pan={x:0,z:0};
        if(this.tooltip)this.tooltip.hidden=true;
      });
      this.canvas.addEventListener('pointerdown',e=>{
        this.canvas.setPointerCapture(e.pointerId);
        // Orbit gestures should not compete with an in-flight anchored zoom.
        this.zoomAnchor=null;this.targetDistance=this.distance;
        if(e.pointerType==='touch'){
          const r=this.canvas.getBoundingClientRect();
          this.touchPointers.set(e.pointerId,{x:e.clientX-r.left,y:e.clientY-r.top});
          if(this.touchPointers.size===2){
            const [a,b]=[...this.touchPointers.values()];
            this.pinchDistance=Math.hypot(a.x-b.x,a.y-b.y);
            this.pinchHappened=true;this.isDragging=false;
            if(this.tooltip)this.tooltip.hidden=true;
            return;
          }
        }
        this.isDragging=true;this.dragDistance=0;
        this.lastPointer={x:e.clientX,y:e.clientY};this.lastInteraction=performance.now();
      });
      this.canvas.addEventListener('pointermove',e=>{
        const x=e.clientX,y=e.clientY;
        if(e.pointerType==='touch'&&this.touchPointers.has(e.pointerId)){
          const r=this.canvas.getBoundingClientRect();
          this.touchPointers.set(e.pointerId,{x:x-r.left,y:y-r.top});
          if(this.touchPointers.size>=2){
            const [a,b]=[...this.touchPointers.values()];
            const next=Math.hypot(a.x-b.x,a.y-b.y);
            if(next>8&&this.pinchDistance>8){
              this.zoomToward(clamp(this.pinchDistance/next,.78,1.28),(a.x+b.x)/2,(a.y+b.y)/2);
            }
            this.pinchDistance=next;this.pinchHappened=true;
            return;
          }
          if(this.pinchHappened)return;
        }
        if(this.isDragging){
          const dx=x-this.lastPointer.x,dy=y-this.lastPointer.y;this.dragDistance+=Math.abs(dx)+Math.abs(dy);
          if(e.shiftKey||e.buttons===2){
            // Pan in world coordinates under the cursor, respecting yaw/zoom.
            const r=this.canvas.getBoundingClientRect();
            const before=this.screenToWorldOnPlane(this.lastPointer.x-r.left,this.lastPointer.y-r.top);
            const after=this.screenToWorldOnPlane(x-r.left,y-r.top);
            if(before&&after){this.pan.x+=before.x-after.x;this.pan.z+=before.z-after.z;
              this.targetPan={...this.pan};}
          }else{this.yaw+=dx*.007;this.pitch=clamp(this.pitch+dy*.005,.57,1.11);}
          this.lastPointer={x,y};if(this.tooltip)this.tooltip.hidden=true;
        }else{const r=this.canvas.getBoundingClientRect();this.updateHover(x-r.left,y-r.top);}
      });
      this.canvas.addEventListener('pointerup',e=>{
        const afterPinch=e.pointerType==='touch'&&this.pinchHappened;
        if(e.pointerType==='touch'){
          this.touchPointers.delete(e.pointerId);
          if(this.touchPointers.size<2)this.pinchDistance=0;
          if(!this.touchPointers.size)this.pinchHappened=false;
        }
        if(!afterPinch&&this.isDragging&&this.dragDistance<6){
          const r=this.canvas.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;
          const issue=this.getIssueHit(x,y);
          if(issue){if(this.tooltip)this.tooltip.hidden=true;this.setSelected(issue.nodeId,{focus:false});this.onIssueSelect(issue.nodeId);}
          else {const hit=this.getHit(x,y);if(hit){this.setSelected(hit.id,{focus:false});this.onSelect(hit.id);}}
        }
        this.isDragging=false;
      });
      this.canvas.addEventListener('pointercancel',e=>{
        this.isDragging=false;this.touchPointers.delete(e.pointerId);
        if(this.touchPointers.size<2)this.pinchDistance=0;
        if(!this.touchPointers.size)this.pinchHappened=false;
      });
      this.canvas.addEventListener('pointerleave',()=>{if(!this.isDragging){this.hovered=null;if(this.tooltip)this.tooltip.hidden=true;}});
      this.canvas.addEventListener('contextmenu',e=>e.preventDefault());
      this.canvas.addEventListener('wheel',e=>{
        e.preventDefault();
        const rect=this.canvas.getBoundingClientRect();
        // Normalize pixels, lines, and pages; proportional zoom works with both
        // precise Mac trackpads and notched mouse wheels. Ctrl-wheel is pinch.
        const delta=(Number(e.deltaY)||0)*(e.deltaMode===1?16:e.deltaMode===2?this.height:1);
        const logFactor=clamp(delta*(e.ctrlKey?.0034:.0015),-.22,.22);
        this.zoomToward(Math.exp(logFactor),e.clientX-rect.left,e.clientY-rect.top);
      },{passive:false});
      this.canvas.addEventListener('keydown',e=>{
        if(['ArrowLeft','ArrowRight','ArrowUp','ArrowDown','+','=','-','Home','Enter'].includes(e.key))e.preventDefault();
        if(e.key==='ArrowLeft')this.yaw-=.14;
        if(e.key==='ArrowRight')this.yaw+=.14;
        if(e.key==='ArrowUp')this.pitch=clamp(this.pitch+.1,.57,1.11);
        if(e.key==='ArrowDown')this.pitch=clamp(this.pitch-.1,.57,1.11);
        if(e.key==='+'||e.key==='=')this.zoomToward(.88);
        if(e.key==='-')this.zoomToward(1/.88);
        if(e.key==='Home')this.resetCamera();
        if(e.key==='Enter'&&this.selected)this.onSelect(this.selected);
      });
    }
    getIssueHit(x,y){
      // Select a visible issue badge before its underlying building. Touch target
      // is larger than the painted circle, without blocking map rotation.
      const candidates=this.issueHitAreas.filter(p=>Math.hypot(p.x-x,p.y-y)<=p.hitRadius);
      return candidates.sort((a,b)=>Math.hypot(a.x-x,a.y-y)-Math.hypot(b.x-x,b.y-y)||a.depth-b.depth)[0]||null;
    }
    getHit(x,y){const hits=this.hitAreas.filter(h=>x>=h.x1&&x<=h.x2&&y>=h.y1&&y<=h.y2);return hits.sort((a,b)=>a.depth-b.depth)[0]?.node||null;}
    updateHover(x,y){
      const pin=this.getIssueHit(x,y);
      if(pin){
        this.hovered=pin.nodeId;
        this.canvas.style.cursor='pointer';
        if(this.tooltip){
          this.tooltip.replaceChildren();
          const title=document.createElement('strong');title.textContent=`${pin.count} open issue${pin.count===1?'':'s'} · ${pin.name}`;
          const text=document.createElement('span');text.textContent=pin.observed
            ? `${pin.observed} source identifier match${pin.observed===1?'':'es'} · Issue itself not confirmed`
            : pin.referenced
              ? `${pin.referenced} path reference${pin.referenced===1?'':'s'}${pin.suggested?` · ${pin.suggested} suggested`:''} · Click for issues`
              : `Suggested location only · Click for issues`;
          this.tooltip.append(title,text);this.tooltip.hidden=false;
          this.tooltip.style.left=clamp(x+15,7,this.width-255)+'px';this.tooltip.style.top=clamp(y-58,7,this.height-75)+'px';
        }
        this.onHover(this.hovered);return;
      }
      const hit=this.getHit(x,y);this.hovered=hit?.id||null;
      if(hit&&this.tooltip){
        this.canvas.style.cursor='pointer';this.tooltip.replaceChildren();
        const title=document.createElement('strong');title.textContent=hit.name;
        const subtitle=document.createElement('span');const issues=this.issueMarkers.get(hit.id);
        subtitle.textContent=`${hit.district} · ${hit.fileCount} files · ${hit.degree} sampled links`+(issues?.observed?` · ${issues.observed} source-matched issues`:issues?.referenced?` · ${issues.referenced} referenced issues`:issues?.suggested?` · ${issues.suggested} issue suggestions`:'');
        this.tooltip.append(title,subtitle);this.tooltip.hidden=false;
        this.tooltip.style.left=clamp(x+14,7,this.width-235)+'px';
        this.tooltip.style.top=clamp(y-53,7,this.height-75)+'px';
      }else{this.canvas.style.cursor='grab';if(this.tooltip)this.tooltip.hidden=true;}
      this.onHover(this.hovered);
    }
    drawSky(ctx){
      const w=this.width,h=this.height;
      const g=ctx.createLinearGradient(0,0,w,h);
      g.addColorStop(0,'#05070c');g.addColorStop(.46,'#0b111d');g.addColorStop(1,'#04060b');
      ctx.fillStyle=g;ctx.fillRect(0,0,w,h);
      const glow=ctx.createRadialGradient(w*.50,h*.46,8,w*.50,h*.46,Math.max(w,h)*.64);
      glow.addColorStop(0,'rgba(66,100,142,.16)');glow.addColorStop(.42,'rgba(34,59,91,.085)');glow.addColorStop(1,'rgba(4,7,13,0)');
      ctx.fillStyle=glow;ctx.fillRect(0,0,w,h);
      for(let i=0;i<55;i++){
        const x=hash('star-x'+i)*w,y=hash('star-y'+i)*h*.92;
        ctx.fillStyle='rgba(181,204,229,'+(.035+hash('alpha'+i)*.12)+')';
        ctx.beginPath();ctx.arc(x,y,hash('star-size'+i)>.95?1.25:.52,0,PI2);ctx.fill();
      }
      // Atmospheric clouds are scenery, never graph objects.
      for(let i=0;i<13;i++){
        const x=w*(hash('fog-x'+i)*1.4-.2),y=h*(.75+hash('fog-y'+i)*.35),r=w*(.12+hash('fog-r'+i)*.14);
        const cloud=ctx.createRadialGradient(x,y,0,x,y,r);
        cloud.addColorStop(0,'rgba(102,132,168,.034)');cloud.addColorStop(1,'rgba(6,11,21,0)');
        ctx.fillStyle=cloud;ctx.fillRect(x-r,y-r,r*2,r*2);
      }
    }
    drawFloor(){/* Floating architecture has no flat ground grid. */}
    islandVertices(d,y){const {x,z}=d.center,w=d.halfWidth,h=d.halfDepth;
      return [[x-w,y,z-h],[x+w,y,z-h],[x+w,y,z+h],[x-w,y,z+h]].map(v=>this.project(...v));}
    drawDistricts(ctx,now){
      const ordered=[...this.districts].sort((a,b)=>this.project(b.center.x,0,b.center.z).depth-this.project(a.center.x,0,a.center.z).depth);
      for(const d of ordered){
        const top=this.islandVertices(d,0),base=this.islandVertices(d,-2.4);
        const drop=this.islandVertices(d,-5.0);
        const cx=this.project(d.center.x,-2,d.center.z);
        ctx.save();
        const halo=ctx.createRadialGradient(cx.x,cx.y,0,cx.x,cx.y,Math.max(50,cx.scale*d.halfWidth*1.7));
        halo.addColorStop(0,rgba(d.color,.10));halo.addColorStop(1,rgba(d.color,0));
        ctx.fillStyle=halo;ctx.beginPath();ctx.ellipse(cx.x,cx.y,Math.max(40,cx.scale*d.halfWidth*1.9),Math.max(20,cx.scale*d.halfDepth*1.1),0,0,PI2);ctx.fill();
        // Suspended island's sculpted lower geometry.
        for(let side=0;side<4;side++){
          const next=(side+1)%4;
          poly(ctx,[base[side],base[next],drop[next],drop[side]]);
          ctx.fillStyle=side===0?'rgba(11,23,45,.78)':'rgba(5,13,29,.71)';ctx.fill();
          ctx.strokeStyle='rgba(99,137,182,.11)';ctx.lineWidth=.6;ctx.stroke();
        }
        for(let side=0;side<4;side++){
          const next=(side+1)%4;
          poly(ctx,[top[side],top[next],base[next],base[side]]);
          ctx.fillStyle=side%2===0?'#102039':'#0b172b';ctx.fill();
          ctx.strokeStyle=rgba(d.color,.23);ctx.lineWidth=.7;ctx.stroke();
        }
        poly(ctx,top);
        const surface=ctx.createLinearGradient(top[0].x,top[0].y,top[2].x,top[2].y);
        surface.addColorStop(0,'#15253a');surface.addColorStop(1,'#0d1828');ctx.fillStyle=surface;ctx.fill();
        ctx.strokeStyle=rgba(d.color,d.kind===this.activeDistrict?.88:.42);
        ctx.lineWidth=d.kind===this.activeDistrict?2:1.1;ctx.shadowBlur=12;ctx.shadowColor=rgba(d.color,.46);ctx.stroke();ctx.shadowBlur=0;
        // Warm perimeter lights are architecture accents, not dependency edges.
        ctx.strokeStyle='rgba(248,183,100,.56)';ctx.shadowColor='rgba(246,176,104,.4)';ctx.shadowBlur=8;ctx.lineWidth=1.25;
        ctx.beginPath();ctx.moveTo(top[2].x,top[2].y);ctx.lineTo(top[3].x,top[3].y);ctx.stroke();ctx.shadowBlur=0;
        // Rooftop ornamental grilles, clearly non-interactive.
        const steps=5;
        for(let t=1;t<steps;t++){
          const x=d.center.x-d.halfWidth+t*(2*d.halfWidth/steps);
          const a=this.project(x,.04,d.center.z-d.halfDepth+.8),b=this.project(x,.04,d.center.z+d.halfDepth-.8);
          ctx.strokeStyle='rgba(121,161,206,.064)';ctx.lineWidth=.7;
          ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
        }
        ctx.restore();
      }
    }
    drawRoads(ctx){
      // Golden elevated transit tracks are *decorative spatial orientation aids*,
      // not evidence of code imports, traffic or call flow.
      if(!this.districts.some(d=>d.central))return;
      for(const d of this.districts.filter(d=>!d.central)){
        const start=this.project(0,2,0),end=this.project(d.center.x,1.7,d.center.z);
        const len=Math.hypot(d.center.x,d.center.z)||1;
        const bend=7+hash('bend-'+d.kind)*4;
        const control=this.project(d.center.x*.5-d.center.z/len*bend,5.5,d.center.z*.5+d.center.x/len*bend);
        ctx.save();ctx.lineCap='round';
        const path=()=>{ctx.beginPath();ctx.moveTo(start.x,start.y);ctx.quadraticCurveTo(control.x,control.y,end.x,end.y);};
        path();ctx.strokeStyle='rgba(3,12,27,.88)';ctx.lineWidth=8;ctx.stroke();
        path();ctx.strokeStyle='rgba(79,115,152,.36)';ctx.lineWidth=5;ctx.stroke();
        path();ctx.strokeStyle='rgba(248,184,105,.35)';ctx.shadowColor='rgba(255,196,111,.42)';ctx.shadowBlur=8;ctx.lineWidth=2.6;ctx.stroke();ctx.shadowBlur=0;
        path();ctx.strokeStyle='rgba(254,210,136,.86)';ctx.lineWidth=.85;ctx.stroke();
        ctx.restore();
      }
    }
    drawDecorations(ctx){
      // Streetscape is decorative. Only prominent towers are graph modules.
      for(const d of this.districts){
        const cells=d.central?7:5,blocks=[];
        for(let row=0;row<cells;row++)for(let col=0;col<cells;col++){
          const idx=row*cells+col;
          const x=d.center.x+((col+.5)/cells*2-1)*(d.halfWidth-1.5);
          const z=d.center.z+((row+.5)/cells*2-1)*(d.halfDepth-1.5);
          if(d.central&&Math.hypot(x,z)<4.2)continue;
          const w=(d.central?.48:.41)+hash(d.kind+'-w-'+idx)*.25;
          const h=1.1+hash(d.kind+'-h-'+idx)*(d.central?4.5:3.7);
          if(d.nodes.some(n=>Math.abs(n.x-x)<n.width+w+.8 && Math.abs(n.z-z)<n.width+w+.8))continue;
          blocks.push({x,z,w,h,idx,depth:this.project(x,h/2,z).depth});
        }
        blocks.sort((a,b)=>b.depth-a.depth);
        for(const {x,z,w,h,idx} of blocks){
          const top=[[-w,h,-w],[w,h,-w],[w,h,w],[-w,h,w]].map(v=>this.project(x+v[0],v[1],z+v[2]));
          const bot=[[-w,0,-w],[w,0,-w],[w,0,w],[-w,0,w]].map(v=>this.project(x+v[0],v[1],z+v[2]));
          ctx.save();
          poly(ctx,[top[1],top[2],bot[2],bot[1]]);ctx.fillStyle=mix('#13283b',d.color,.18);ctx.fill();
          poly(ctx,[top[2],top[3],bot[3],bot[2]]);ctx.fillStyle=mix('#0b1a2c',d.color,.11);ctx.fill();
          poly(ctx,top);ctx.fillStyle=mix('#38506a',d.color,.18);ctx.fill();
          ctx.strokeStyle=rgba('#b9d9f4',.22);ctx.lineWidth=.5;ctx.stroke();
          if(idx%3===0){
            const a=this.project(x+w,h*.34,z+w),b=this.project(x+w,h*.86,z+w);
            ctx.strokeStyle='rgba(213,241,255,.45)';ctx.lineWidth=.7;
            ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
          }
          ctx.restore();
        }
      }
    }
    drawRepositoryBeacon(ctx){
      const main=this.districts.find(d=>d.central);if(!main)return;
      // A symbolic city landmark for the repository itself, not a claimed entrypoint.
      const x=0,z=0,w=2.85,h=20.5;
      const b=[[-w,0,-w],[w,0,-w],[w,0,w],[-w,0,w]].map(v=>this.project(x+v[0],v[1],z+v[2]));
      const t=[[-w,h,-w],[w,h,-w],[w,h,w],[-w,h,w]].map(v=>this.project(x+v[0],v[1],z+v[2]));
      ctx.save();
      poly(ctx,[b[1],b[2],t[2],t[1]]);
      const side=ctx.createLinearGradient(t[1].x,t[1].y,b[2].x,b[2].y);
      side.addColorStop(0,'#3a76ae');side.addColorStop(.45,'#123f70');side.addColorStop(1,'#081c39');ctx.fillStyle=side;ctx.fill();
      ctx.strokeStyle='rgba(179,220,255,.85)';ctx.lineWidth=1.8;ctx.shadowColor='#87bfff';ctx.shadowBlur=13;ctx.stroke();ctx.shadowBlur=0;
      poly(ctx,[b[2],b[3],t[3],t[2]]);
      const front=ctx.createLinearGradient(t[3].x,t[3].y,b[2].x,b[2].y);
      front.addColorStop(0,'#89b3df');front.addColorStop(.25,'#266194');front.addColorStop(1,'#071f47');ctx.fillStyle=front;ctx.fill();
      ctx.strokeStyle='rgba(206,235,255,.78)';ctx.lineWidth=1.4;ctx.stroke();
      poly(ctx,t);ctx.fillStyle='rgba(209,234,255,.87)';ctx.fill();
      // Architectural spire and inner illumination.
      const spire=this.project(x,h+5.5,z),roof=this.project(x,h,z);
      ctx.beginPath();ctx.moveTo(spire.x,spire.y);ctx.lineTo(roof.x,roof.y);
      ctx.strokeStyle='rgba(178,218,255,.87)';ctx.shadowBlur=17;ctx.shadowColor='#91c6ff';ctx.lineWidth=1.8;ctx.stroke();ctx.shadowBlur=0;
      const icon=this.project(x,h*.59,z+w+.06);
      ctx.fillStyle='#e1f6ff';ctx.font=`600 ${Math.max(9,Math.min(21,icon.scale*2.4))}px ui-monospace,monospace`;
      ctx.textAlign='center';ctx.textBaseline='middle';ctx.shadowBlur=15;ctx.shadowColor='#7cc7ff';ctx.fillText('</>',icon.x,icon.y);ctx.shadowBlur=0;
      // Thin gold orbital halo marks the city's symbolic hub.
      const halo=this.project(0,12,0);ctx.strokeStyle='rgba(252,206,138,.66)';ctx.lineWidth=1.1;
      ctx.shadowColor='rgba(255,185,91,.46)';ctx.shadowBlur=12;ctx.beginPath();ctx.ellipse(halo.x,halo.y,halo.scale*6.5,halo.scale*2.4,-.2,0,PI2);ctx.stroke();ctx.shadowBlur=0;
      ctx.restore();
    }
    pickPathEdges(){
      // Highlight a discovered chain of sampled static imports; NOT runtime execution.
      const starts=this.nodes.filter(n=>n.kind==='frontend');
      let current=this.nodes.find(n=>n.id===this.selected)||starts[0]||this.nodes[0];
      const used=new Set(),visited=new Set();
      for(let step=0;step<8&&current;step++){
        visited.add(current.id);
        const next=this.edges.find(e=>e.a.id===current.id&&!visited.has(e.b.id));
        if(!next)break;used.add(next);current=next.b;
      }
      return used;
    }
    drawEdges(ctx,now){
      const path=this.mode==='flows'?this.pickPathEdges():null;
      const hotspots=new Set(this.getHotspots().map(n=>n.id));
      for(const edge of this.edges){
        const traceEdge=this.impact?.edges.has(edge.a.id+'\0'+edge.b.id);
        if(this.impact&&!traceEdge)continue;
        const active=this.impact?traceEdge:this.mode==='flows'?path.has(edge):this.mode==='dependencies'||
          this.mode==='hotspots'?(this.mode==='dependencies'||hotspots.has(edge.a.id)||hotspots.has(edge.b.id)):
            edge.a.id===this.selected||edge.b.id===this.selected;
        if(this.mode==='structure'&&!active)continue;
        const cross=edge.a.kind!==edge.b.kind;
        const elevation=cross?2.1:.45;
        const p=this.project(edge.a.x,elevation+Math.min(edge.a.height,2),edge.a.z);
        const q=this.project(edge.b.x,elevation+Math.min(edge.b.height,2),edge.b.z);
        const mid=this.project((edge.a.x+edge.b.x)/2,Math.max(edge.a.height,edge.b.height)/2+(cross?3:1),(edge.a.z+edge.b.z)/2);
        const strength=this.impact?.89:this.mode==='structure'?(active?.63:.0):active?.85:.10;
        const accent=this.impact?'#f3c58b':this.mode==='hotspots'&&active?'#f0a2af':cross?'#9dcffe':'#91e2ef';
        ctx.save();ctx.lineWidth=active?cross?2.4:1.65:1.0;
        if(!active)ctx.setLineDash([2,7]);
        ctx.strokeStyle=rgba(accent,strength);ctx.shadowColor=rgba(accent,.9);ctx.shadowBlur=active?10:0;
        ctx.beginPath();ctx.moveTo(p.x,p.y);ctx.quadraticCurveTo(mid.x,mid.y,q.x,q.y);ctx.stroke();ctx.setLineDash([]);ctx.shadowBlur=0;
        if(active&&this.traffic&&!this.motion){
          // Animated particles are visualizations of static links, not packet traces.
          const t=(now*.00015+hash(edge.a.id+edge.b.id))%1;
          const x=(1-t)*(1-t)*p.x+2*(1-t)*t*mid.x+t*t*q.x;
          const y=(1-t)*(1-t)*p.y+2*(1-t)*t*mid.y+t*t*q.y;
          const glow=ctx.createRadialGradient(x,y,0,x,y,10);
          glow.addColorStop(0,rgba(accent,.8));glow.addColorStop(1,rgba(accent,0));
          ctx.fillStyle=glow;ctx.beginPath();ctx.arc(x,y,10,0,PI2);ctx.fill();
          ctx.fillStyle='#f4ffff';ctx.beginPath();ctx.arc(x,y,1.5,0,PI2);ctx.fill();
        }
        ctx.restore();
      }
    }
    drawBuilding(ctx,n,now){
      const selected=n.id===this.selected,hovered=n.id===this.hovered;
      const neighbors=this.edges.some(e=>e.a.id===this.selected&&e.b.id===n.id||e.b.id===this.selected&&e.a.id===n.id);
      const tracedDirect=this.impact?.direct.has(n.id),tracedIndirect=this.impact?.indirect.has(n.id);
      const traced=tracedDirect||tracedIndirect;
      const dim=this.impact?!selected&&!traced:this.mode==='dependencies'&&!selected&&!neighbors;
      const hot=this.mode==='hotspots'&&this.hotspots.some(item=>item.id===n.id);
      const color=tracedDirect?'#efbd89':tracedIndirect?'#b6acff':hot?'#ff5d89':n.color,w=n.width,h=n.height;
      const verts=[[-w,0,-w],[w,0,-w],[w,0,w],[-w,0,w],[-w,h,-w],[w,h,-w],[w,h,w],[-w,h,w]];
      const pts=verts.map(p=>this.project(n.x+p[0],p[1],n.z+p[2]));
      const depth=this.project(n.x,h*.5,n.z).depth;
      const roof=this.project(n.x,h,n.z),base=this.project(n.x,0,n.z);
      ctx.save();ctx.globalAlpha=dim?.30:1;
      const shadow=ctx.createRadialGradient(base.x,base.y,0,base.x,base.y,Math.max(14,base.scale*7));
      shadow.addColorStop(0,rgba(color,selected?.33:.17));shadow.addColorStop(1,rgba(color,0));
      ctx.fillStyle=shadow;ctx.beginPath();ctx.ellipse(base.x,base.y,Math.max(12,base.scale*7),Math.max(4,base.scale*3.4),0,0,PI2);ctx.fill();
      if(selected||hovered||hot||traced){
        const pulse=selected&&!this.motion?.12*Math.sin(now*.004):0;
        ctx.strokeStyle=rgba(color,selected?.78+pulse:hovered?.55:traced?.67:.4);ctx.lineWidth=selected?2.2:traced?1.8:1.3;
        ctx.shadowColor=color;ctx.shadowBlur=selected?18:traced?12:6;
        ctx.beginPath();ctx.ellipse(base.x,base.y,base.scale*(w*2+1.1),base.scale*(w+.5),0,0,PI2);ctx.stroke();ctx.shadowBlur=0;
      }
      const faces=[
        {ids:[0,1,5,4],bright:.20},{ids:[1,2,6,5],bright:.32},
        {ids:[2,3,7,6],bright:.16},{ids:[3,0,4,7],bright:.23},
        {ids:[4,5,6,7],bright:.50},
      ].sort((a,b)=>b.ids.reduce((t,i)=>t+pts[i].depth,0)-a.ids.reduce((t,i)=>t+pts[i].depth,0));
      for(const face of faces){
        poly(ctx,face.ids.map(i=>pts[i]));
        const fa=face.ids.reduce((t,i)=>t+pts[i].y,0)/4;
        const gd=ctx.createLinearGradient(roof.x,roof.y,base.x,base.y);
        gd.addColorStop(0,mix('#5b7d9c',color,face.bright+.19));
        gd.addColorStop(.52,mix('#1c3655',color,face.bright*.65));
        gd.addColorStop(1,mix('#0a1a2d',color,face.bright*.30));
        ctx.fillStyle=gd;ctx.fill();
        ctx.lineWidth=selected?1.4:.78;ctx.strokeStyle=rgba('#b6cde1',selected?.94:.45);
        ctx.shadowColor=rgba(color,.45);ctx.shadowBlur=selected?9:1;ctx.stroke();ctx.shadowBlur=0;
      }
      // Raised architectural crown restores the original tower silhouette.
      // These are still the exact modules from the imported repository.
      const capWidth=w*1.085,capHeight=.37;
      const rim=[[-capWidth,h,-capWidth],[capWidth,h,-capWidth],
        [capWidth,h,capWidth],[-capWidth,h,capWidth]].map(p=>this.project(n.x+p[0],p[1],n.z+p[2]));
      const crown=[[-capWidth,h+capHeight,-capWidth],[capWidth,h+capHeight,-capWidth],
        [capWidth,h+capHeight,capWidth],[-capWidth,h+capHeight,capWidth]].map(p=>this.project(n.x+p[0],p[1],n.z+p[2]));
      poly(ctx,[rim[1],rim[2],crown[2],crown[1]]);
      ctx.fillStyle=mix('#152d46',color,.27);ctx.fill();
      poly(ctx,[rim[2],rim[3],crown[3],crown[2]]);
      ctx.fillStyle=mix('#101e32',color,.19);ctx.fill();
      poly(ctx,crown);ctx.fillStyle=mix('#587890',color,.37);ctx.fill();
      ctx.strokeStyle=rgba(selected?'#f4fbff':color,selected?.96:.72);
      ctx.lineWidth=selected?1.8:1.1;ctx.stroke();
      // Windows and mullions follow the two camera-visible facades.
      const visibleX=Math.sin(this.yaw)<0?w:-w;
      const visibleZ=Math.cos(this.yaw)>0?-w:w;
      const facesVisible=[
        (side,y)=>this.project(n.x+visibleX+Math.sign(visibleX)*.025,y,n.z+side),
        (side,y)=>this.project(n.x+side,y,n.z+visibleZ+Math.sign(visibleZ)*.025)
      ];
      const detailed=roof.scale*w>=3.3;
      const floors=detailed?Math.min(this.width<650||this.nodes.length>45?4:8,Math.max(3,Math.floor(h/1.6))):0;
      for(let facadeIndex=0;facadeIndex<facesVisible.length;facadeIndex++){
        const point=facesVisible[facadeIndex];
        for(let lane=1;lane<=3&&detailed;lane++){
          const side=-w+2*w*lane/4;
          const a=point(side,.65),b=point(side,h-.35);
          ctx.strokeStyle=rgba('#bcd9f1',.18);
          ctx.lineWidth=.65;ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
        }
        for(let floor=1;floor<=floors;floor++){
          const y=h*(floor/(floors+1));
          const a=point(-w,y),b=point(w,y);
          ctx.strokeStyle=rgba('#b5d8f3',.23);ctx.lineWidth=.6;
          ctx.beginPath();ctx.moveTo(a.x,a.y);ctx.lineTo(b.x,b.y);ctx.stroke();
          for(let lane=1;lane<=3;lane++){
            if(hash(n.id+':'+facadeIndex+':'+floor+':'+lane)<.31)continue;
            const side=-w+2*w*lane/4,start=point(side,y+.19),end=point(side,Math.min(h-.28,y+.79));
            ctx.strokeStyle=rgba('#e0f2ff',.35+.40*hash(n.id+':light:'+floor+':'+lane));
            ctx.lineWidth=clamp(roof.scale*.19,1,2.05);
            ctx.beginPath();ctx.moveTo(start.x,start.y);ctx.lineTo(end.x,end.y);ctx.stroke();
          }
        }
      }
      // Landmarks have unmistakable light beacons; selected nodes get a tall hologram.
      if(n.landmark||selected){
        const beamHeight=selected?44:24;
        const glow=ctx.createLinearGradient(roof.x,roof.y-beamHeight,roof.x,roof.y+2);
        glow.addColorStop(0,rgba(color,0));glow.addColorStop(.70,rgba(color,.60));glow.addColorStop(1,rgba(color,.25));
        ctx.strokeStyle=glow;ctx.lineWidth=selected?2.8:1.8;
        ctx.shadowColor=color;ctx.shadowBlur=selected?15:7;
        ctx.beginPath();ctx.moveTo(roof.x,roof.y-beamHeight);ctx.lineTo(roof.x,roof.y);ctx.stroke();ctx.shadowBlur=0;
      }
      ctx.fillStyle=selected?'#efffff':color;ctx.beginPath();ctx.arc(roof.x,roof.y,selected?3:1.8,0,PI2);ctx.fill();
      ctx.restore();
      const xs=pts.map(p=>p.x),ys=pts.map(p=>p.y);
      return {node:n,x1:Math.min(...xs)-5,x2:Math.max(...xs)+5,y1:Math.min(...ys)-5,y2:Math.max(...ys)+5,
        depth,roof,selected,hovered,dim};
    }
    drawBuildingLabels(ctx,hits){
      // Avoid 60 overlapping file labels. Show district landmarks by default,
      // and reveal other names on selection, hover, or closer camera zoom.
      const candidates=hits.filter(h=>h.selected||h.hovered||(this.impact?.direct.has(h.node.id)&&this.distance<=92)||(h.node.landmark&&this.distance<=84)||this.distance<=58)
        .sort((a,b)=>Number(b.selected)-Number(a.selected)||Number(b.hovered)-Number(a.hovered)||Number(b.node.landmark)-Number(a.node.landmark));
      const placed=[];
      for(const h of candidates){
        const {node,roof,selected,hovered,dim}=h;if(dim&&!selected)continue;
        const label=node.name.length>19?node.name.slice(0,18)+'…':node.name;
        ctx.font=selected?'bold 14px system-ui':'600 12px system-ui';
        const width=clamp(ctx.measureText(label).width+28,67,210),x=roof.x-width/2,y=roof.y-(selected?39:32);
        if(x<4||x+width>this.width-4||y<4||y+26>this.height)continue;
        if(!selected&&!hovered&&placed.some(p=>x<p.x+p.w+4&&x+width>p.x-4&&y<p.y+26&&y+26>p.y))continue;
        ctx.save();rounded(ctx,x,y,width,26,6);
        ctx.fillStyle=selected?'rgba(22,32,67,.97)':'rgba(8,16,36,.89)';ctx.fill();
        ctx.strokeStyle=rgba(node.color,selected?.95:.55);ctx.lineWidth=selected?1.25:1;ctx.stroke();
        ctx.fillStyle=selected?'#ffffff':'#d8e7ff';ctx.textAlign='center';ctx.textBaseline='middle';
        ctx.fillText(label,roof.x,y+13);
        if(selected){ctx.strokeStyle=rgba(node.color,.75);ctx.beginPath();ctx.moveTo(roof.x,y+26);ctx.lineTo(roof.x,roof.y-1);ctx.stroke();}
        ctx.restore();placed.push({x,y,w:width});
      }
    }
    drawIssuePins(ctx,hits){
      // Overlay clickable, evidence-qualified issue pins. A badge is a pointer to
      // an OPEN GitHub issue, NOT a defect finding or a severity prediction.
      this.issueHitAreas=[];
      const placed=[];
      for(const hit of hits){
        const match=this.issueMarkers.get(hit.node.id);
        if(!match||(!match.referenced&&!match.suggested&&!match.observed)||hit.dim)continue;
        const count=match.referenced+match.suggested+match.observed,hasRef=match.referenced>0||match.observed>0;
        const roof=hit.roof,x=roof.x+14,y=roof.y-13;
        if(x<19||x>this.width-19||y<107||y>this.height-24)continue;
        // Declutter at the default skyline scale, but never render fake grouped
        // counts: the badge always belongs to one real module.
        if(placed.some(p=>Math.hypot(p.x-x,p.y-y)<29))continue;
        placed.push({x,y});
        ctx.save();
        ctx.shadowColor=hasRef?'#e7b57f':'#89bde0';ctx.shadowBlur=hasRef?15:6;
        ctx.beginPath();ctx.arc(x,y,13.5,0,PI2);
        ctx.fillStyle=hasRef?'rgba(73,46,31,.97)':'rgba(17,39,65,.96)';ctx.fill();
        ctx.strokeStyle=hasRef?'#f3c58b':'#9cbed8';ctx.lineWidth=1.3;ctx.stroke();
        ctx.shadowBlur=0;ctx.font='650 12px system-ui';ctx.fillStyle='#fff5e5';ctx.textAlign='center';ctx.textBaseline='middle';
        ctx.fillText(hasRef?String(count>9?'9+':count):'?',x,y+.5);ctx.restore();
        this.issueHitAreas.push({x,y,nodeId:hit.node.id,name:hit.node.name,
          referenced:match.referenced,suggested:match.suggested,observed:match.observed,count,hitRadius:26,depth:hit.depth});
      }
    }
    drawDistrictLabels(ctx){
      const labels=[];
      // Leading lines identify real (heuristically classified) code districts.
      for(const d of [...this.districts].sort((a,b)=>Number(b.central)-Number(a.central))){
        if(this.distance>=135 && !d.central && d.count<2 && !['api','test'].includes(d.kind))continue;
        if(this.width<650 && !d.central && !['api','database'].includes(d.kind))continue;
        const center=this.project(d.center.x,5,d.center.z);
        const anchor=this.project(d.center.x-d.halfWidth*.25,2,d.center.z-d.halfDepth*.15);
        const name=d.name.toUpperCase(),count=`${d.count} MODULE${d.count===1?'':'S'}`;
        const central=d.central;
        ctx.save();ctx.font='650 12px system-ui';
        const width=Math.min(235,Math.max(120,ctx.measureText(name).width+28));
        // Place plaque high enough to clear roofs, offset horizontally from island centre.
        const x=center.x+(central?Math.max(102,center.scale*8):(-d.center.x*.24)),
          y=center.y-(central?144:Math.min(106,71+center.scale*2.3));
        const clampedX=clamp(x-width*.5,7,this.width-width-7);
        const clampedY=clamp(y,98,this.height-55);
        if(labels.some(p=>clampedX<p.x+p.w+5&&clampedX+width>p.x-5&&clampedY<p.y+44&&clampedY+44>p.y)){
          ctx.restore();continue;
        }
        labels.push({x:clampedX,y:clampedY,w:width});
        ctx.strokeStyle=rgba('#bad5f1',.36);ctx.lineWidth=.85;
        ctx.beginPath();ctx.moveTo(anchor.x,anchor.y-5);ctx.lineTo(clampedX+width*.5,clampedY+38);ctx.stroke();
        ctx.fillStyle='rgba(7,16,28,.94)';rounded(ctx,clampedX,clampedY,width,44,6);ctx.fill();
        ctx.strokeStyle=rgba(d.color,.54);ctx.lineWidth=.8;ctx.stroke();
        ctx.fillStyle='#eaf4ff';ctx.font='650 12px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';
        ctx.fillText(name,clampedX+width*.5,clampedY+16);
        ctx.fillStyle='#b3c9dd';ctx.font='500 10px system-ui';ctx.fillText(count,clampedX+width*.5,clampedY+33);
        ctx.restore();
      }
    }
    render(now=performance.now()){
      // Preserve smooth gestures, but avoid repainting the idle skyline at 60 Hz.
      // In particular a large mobile city can be GPU/CPU intensive.
      const transitioning=this.isDragging||this.zoomAnchor||this.spin||
        Math.abs(this.targetDistance-this.distance)>.15||
        Math.abs(this.targetPan.x-this.pan.x)>.1||
        Math.abs(this.targetPan.z-this.pan.z)>.1;
      const minFrameMs=this.width<650?33:transitioning?16:60;
      if(this.lastPaintAt!=null&&now-this.lastPaintAt<minFrameMs){
        this.frame=requestAnimationFrame(t=>this.render(t));return;
      }
      this.lastPaintAt=now;
      const dt=Math.min(50,now-(this.lastTime||now));this.lastTime=now;this.time=now;
      if(this.spin&&!this.motion&&!this.isDragging)this.yaw+=dt*.00018;
      // Use time-based easing, not per-frame or fixed-unit jumps.
      const zoomEase=1-Math.exp(-dt/65);
      if(Math.abs(this.targetDistance-this.distance)>.025){
        this.distance+=(this.targetDistance-this.distance)*zoomEase;
      }else this.distance=this.targetDistance;
      if(this.zoomAnchor){
        const {x,y,planeY,world}=this.zoomAnchor;
        const local=this.screenToWorldOnPlane(x,y,planeY,this.distance,{x:0,z:0});
        if(local){this.pan={x:world.x-local.x,z:world.z-local.z};this.targetPan={...this.pan};}
        if(this.distance===this.targetDistance||!local)this.zoomAnchor=null;
      }else{
        const panEase=1-Math.exp(-dt/130);
        this.pan.x+=(this.targetPan.x-this.pan.x)*panEase;
        this.pan.z+=(this.targetPan.z-this.pan.z)*panEase;
      }
      const ctx=this.ctx;ctx.setTransform(this.pixelRatio,0,0,this.pixelRatio,0,0);
      this.drawSky(ctx);this.drawFloor(ctx);this.drawDistricts(ctx,now);this.drawRoads(ctx);
      this.drawDecorations(ctx);this.drawEdges(ctx,now);
      const ordered=[...this.nodes].sort((a,b)=>this.project(b.x,b.height/2,b.z).depth-this.project(a.x,a.height/2,a.z).depth);
      this.hitAreas=ordered.map(n=>this.drawBuilding(ctx,n,now));
      this.drawRepositoryBeacon(ctx);
      this.drawBuildingLabels(ctx,this.hitAreas);this.drawIssuePins(ctx,this.hitAreas);this.drawDistrictLabels(ctx);
      this.frame=requestAnimationFrame(t=>this.render(t));
    }
    destroy(){cancelAnimationFrame(this.frame);this.resizeObserver.disconnect();}
  }
  window.RepoWorldRenderer=RepoWorldRenderer;
  window.REPOWORLD_COLORS=COLORS;
  window.REPOWORLD_DISTRICTS=DISTRICTS;
})();
