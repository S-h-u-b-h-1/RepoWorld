/* RepoWorld v0.9.8: minimal city, source-scoped issue guide, and shareable public-repository entry points. */
(function(){
  'use strict';
  const $=id=>document.getElementById(id);
  const TYPES=window.REPOWORLD_DISTRICTS||{};
  const state={session:null,repos:[],activeId:null,graph:null,renderer:null,tour:null,tourIndex:-1,
    chosen:null,layer:'structure',busy:false,toast:null,impact:null,searchTimer:null,searchRevision:0,lastFindResults:[],
    radar:null,radarError:null,radarRevision:0,compassTab:'ask',chatHistory:[],chatBusy:false,assistantNode:null,assistantIssue:null,
    issueOpenNode:null,issueSelectedNumber:null,issueInsightCache:new Map(),issueInsightRevision:0};
  const esc=(s)=>String(s??'');
  const getNode=(id)=>state.graph?.nodes?.find(n=>n.id===id);
  const names={frontend:'Frontend Boulevard',api:'API Heights',service:'Service Quarter',database:'Data Harbor',
    library:'Utility Alley',security:'Identity Ward',infra:'Infra Grid',test:'Test Sector',docs:'Archive Row',core:'Core Nexus'};
  const colors=window.REPOWORLD_COLORS||{};
  // Share links encode only a public owner/repo name. They never contain a guest
  // session, CSRF value, server credential, saved-city ID, or source excerpt.
  const PUBLIC_REPO=/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/;
  const deepLinkedRepo=()=>{
    try{
      const value=new URLSearchParams(window.location?.search||'').get('repo')||'';
      return value.length<=150&&PUBLIC_REPO.test(value)&&!['.','..'].includes(value.split('/')[1])?value:null;
    }catch{return null;}
  };
  const kindLabel=k=>TYPES[k]?.name||names[k]||'Core Nexus';
  const setText=(id,value)=>{if($(id))$(id).textContent=esc(value);};
  const short=(s,n=46)=>esc(s).length>n?esc(s).slice(0,n-1)+'…':esc(s);
  const fileUrl=file=>state.graph.url+'/blob/'+encodeURIComponent(state.graph.branch)+'/'+file.split('/').map(encodeURIComponent).join('/');
  const toast=(msg,bad=false)=>{const e=$('toast');e.textContent=esc(msg);e.classList.toggle('error',bad);e.hidden=false;
    clearTimeout(state.toast);state.toast=setTimeout(()=>{e.hidden=true;},5500);};
  async function api(url,opts={}){
    const request={credentials:'same-origin',...opts};
    if(opts.method&&opts.method.toUpperCase()!=='GET'){
      request.headers={'Content-Type':'application/json','X-RepoWorld-CSRF':state.session?.csrf||'',...(opts.headers||{})};
    }
    const response=await fetch(url,request);
    let body;try{body=await response.json();}catch{throw Error('The server returned an unreadable response.');}
    if(!response.ok){
      const detail=Array.isArray(body.detail)
        ? body.detail.map(item=>item?.msg||'Invalid request').join('; ')
        : body.detail||body.error||`Request failed (HTTP ${response.status}).`;
      const cooldown=Number(response.headers?.get?.('Retry-After'));
      const hint=response.status===429&&Number.isFinite(cooldown)&&cooldown>0
        ? ` Try again in about ${Math.ceil(cooldown/60)} minute${cooldown>60?'s':''}.` : '';
      const error=new Error(String(detail)+hint);
      error.status=response.status;
      throw error;
    }
    return body;
  }
  const post=(path,object)=>api(path,{method:'POST',body:JSON.stringify(object)});
  function showView(){ $('loadingView').hidden=true; $('workspace').hidden=false; }
  function closePopovers(){ $('repoMenu').hidden=true; $('repoMenuButton').setAttribute('aria-expanded','false'); }
  function toggleMenu(id,button){const target=!$(id).hidden;closePopovers();$(id).hidden=target;$(button).setAttribute('aria-expanded',String(!target));}
  function startImport(){closePopovers();setText('importError','');$('importError').hidden=true;$('importDemo').hidden=true;$('importInput').value='';
    $('addRepoDialog').showModal();setTimeout(()=>$('importInput').focus(),50);}
  function hideImport(){if(!state.busy)$('addRepoDialog').close();}
  function showEmpty(){
    $('workspace').classList.add('is-empty');$('emptyState').hidden=false;$('canvasStage').hidden=true;
    $('mapCommandTrigger').hidden=true;$('mapTools').hidden=true;$('cityHint').hidden=true;$('worldStatus').hidden=true;
    $('inspector').hidden=true;$('tourPanel').hidden=true;$('issueDrawer').hidden=true;$('issueMapLegend').hidden=true;state.issueInsightRevision++;
    state.radar=null;state.radarError=null;state.radarRevision++;state.renderer?.setIssueMarkers?.({});
    setText('activeRepoTitle','RepoWorld');renderRepos();
  }
  function showCity(){
    $('workspace').classList.remove('is-empty');$('emptyState').hidden=true;$('canvasStage').hidden=false;
    $('mapCommandTrigger').hidden=false;$('cityHint').hidden=false;$('worldStatus').hidden=false;
  }
  function renderRepos(){
    const list=$('repoMenuItems');list.replaceChildren();
    $('refreshCurrentRepo').hidden=!(state.graph?.source==='github');
    $('copyCityLink').hidden=!(state.graph?.source==='github');
    if(!state.repos.length){const p=document.createElement('p');p.className='empty-small';p.textContent='No repositories added yet.';p.style.padding='0 10px';list.append(p);return;}
    for(const repo of state.repos){
      const row=document.createElement('button');row.type='button';row.className='repo-menu-item'+(repo.id===state.activeId?' active':'');
      const ico=document.createElement('span');ico.textContent='◇';ico.style.color='#9bd4ef';
      const copy=document.createElement('span');copy.style.flex='1';copy.style.minWidth='0';
      const title=document.createElement('strong');title.textContent=repo.name;
      const subtitle=document.createElement('small');subtitle.textContent=repo.fullName;
      copy.append(title,subtitle);row.append(ico,copy);
      if(repo.id===state.activeId){const active=document.createElement('span');active.className='active-spark';active.textContent='✓';row.append(active);}
      row.addEventListener('click',()=>selectRepo(repo.id));list.append(row);
    }
  }
  async function refreshSession(){
    const session=await api('/api/session');state.session=session;state.repos=session.repositories||[];state.activeId=session.activeRepo||null;
    return session;
  }
  function initializeRenderer(){
    if(!state.renderer){state.renderer=new window.RepoWorldRenderer($('worldCanvas'),{
      onSelect(id){hideIssueDrawer();clearImpact();state.chosen=id;renderInspector();$('inspector').scrollTop=0;$('inspector').hidden=false;$('tourPanel').hidden=true;},
      onIssueSelect(id){openIssueMarker(id);}
    });}
  }
  async function useGraph(graph){
    if(!graph?.nodes?.length){toast('This repository has no displayable modules.',true);showEmpty();return;}
    state.graph=graph;state.chosen=null;state.tour=null;state.tourIndex=-1;clearImpact();
    state.chatHistory=[];state.assistantNode=null;state.assistantIssue=null;state.radar=null;state.radarError=null;state.radarRevision++;
    state.issueOpenNode=null;state.issueSelectedNumber=null;state.issueInsightCache.clear();state.issueInsightRevision++;$('issueDrawer').hidden=true;$('issueMapLegend').hidden=true;
    $('assistantThread').replaceChildren();addAssistantWelcome();setText('issuesTabCount','');$('issuesTabCount').hidden=true;
    showCity();initializeRenderer();
    state.renderer.setGraph(graph);state.renderer.setMode('structure');state.renderer.setTraffic?.(false);
    // Prevent renderer's default internal selection from visually highlighting the first tower.
    state.renderer.selected=null;
    $('inspector').hidden=true;$('tourPanel').hidden=true;$('mapTools').hidden=true;$('issueDrawer').hidden=true;
    setText('activeRepoTitle',graph.name);
    setText('cityStatusText',graph.source==='demo'?'DEMO CITY':'PUBLIC GITHUB SNAPSHOT');
    setText('cityStatusCounts',`${new Set(graph.nodes.map(n=>n.kind)).size} DISTRICTS  ·  ${graph.nodes.length} BUILDINGS`);
    document.title=`${graph.name} — RepoWorld`;
    setLayer('structure');renderRepos();state.renderer.setIssueMarkers?.({});
    loadIssueRadar();
    try{state.tour=await post('/api/tour',{graph});updateTour();}catch(e){state.tour=null;}
  }
  async function selectRepo(id){
    if(!id)return showEmpty();
    closePopovers();
    const old=state.activeId;
    try{
      const stored=await api('/api/my-repos/'+encodeURIComponent(id));
      if(old!==id)await post('/api/me/active',{repoId:id});
      state.activeId=id;await useGraph(stored.graph);
    }catch(e){toast(e.message,true);}
  }
  async function importRepository(value){
    if(state.busy)return;
    const raw=esc(value).trim();if(!raw)return;
    state.busy=true;$('importButton').disabled=true;$('importButton').textContent='Constructing your city…';
    $('importError').hidden=true;$('importDemo').hidden=true;
    // Indicate a slow request without adding more permanent interface elements.
    const progressTimer=setTimeout(()=>{
      if(state.busy)$('importButton').textContent='Reading GitHub…';
    },9000);
    try{
      const result=await post('/api/my-repos',{url:raw});
      await refreshSession();state.activeId=result.id;
      $('addRepoDialog').close();await useGraph(result.graph);
      toast(`${result.graph.name} is ready. Drag the city to explore.`);
    }catch(e){setText('importError',e.message);$('importError').hidden=false;
      // A truthful, API-free exploration option when GitHub is throttling us.
      // This fixture is fictional and must never appear to be a real import.
      $('importDemo').hidden=e.status!==429;
    }
    finally{clearTimeout(progressTimer);state.busy=false;$('importButton').disabled=false;$('importButton').textContent='Create my city ↗';}
  }
  async function openFictionalDemo(){
    if(state.busy)return;
    state.busy=true;$('importDemo').disabled=true;
    try{
      const graph=await api('/api/demo');
      if(graph?.source!=='demo')throw Error('The server did not return a fictional demonstration city.');
      state.activeId=null;
      $('addRepoDialog').close();
      await useGraph(graph);
      toast('Fictional demo city loaded. No GitHub repository was imported.');
    }catch(e){setText('importError',e.message);$('importError').hidden=false;}
    finally{state.busy=false;$('importDemo').disabled=false;}
  }
  async function copyCityLink(){
    if(state.graph?.source!=='github')return;
    const repo=state.repos.find(item=>item.id===state.activeId)?.fullName||`${state.graph.owner||''}/${state.graph.name||''}`;
    if(!PUBLIC_REPO.test(repo)){toast('This city cannot be shared as a public GitHub link.',true);return;}
    const current=window.location;
    const origin=current?.origin, pathname=current?.pathname||'/';
    if(!origin||!/^https?:\/\//.test(origin)){toast('This page has no shareable web address.',true);return;}
    const url=`${origin}${pathname}?repo=${encodeURIComponent(repo)}`;
    closePopovers();
    try{
      if(!window.navigator?.clipboard?.writeText)throw Error('Clipboard is unavailable');
      await window.navigator.clipboard.writeText(url);
      const local=/^https?:\/\/(?:localhost|127\.0\.0\.1|\[::1\])(?::|$)/i.test(origin);
      toast(local?'Local preview link copied. A public deployment is needed to share it with others.':'Repository link copied. Visitors can import it without signing in.');
    }catch{
      // Clipboard access may be denied on non-HTTPS previews. Give an explicit
      // copyable fallback rather than claiming to have copied the link.
      if(typeof window.prompt==='function')window.prompt('Copy your public RepoWorld link:',url);
      else toast('Clipboard is unavailable in this browser.',true);
    }
  }
  async function refreshCodeIndex(){
    const url=state.graph?.url;if(!url||state.busy)return;
    state.busy=true;
    const button=$('refreshCurrentRepo');button.disabled=true;button.textContent='Refreshing code index…';
    try{
      const result=await post('/api/my-repos',{url,refresh:true});
      await refreshSession();state.activeId=result.id;
      closePopovers();await useGraph(result.graph);
      toast('Updated city and issue file index. No saved repositories were deleted.');
    }catch(e){toast('Could not refresh: '+e.message,true);}
    finally{state.busy=false;button.disabled=false;button.textContent='↻ Refresh code index';}
  }
  function setLayer(layer){
    state.layer=layer;state.renderer?.setMode(layer);
    document.querySelectorAll('[data-layer]').forEach(b=>b.classList.toggle('active',b.dataset.layer===layer));
  }
  function openTour(){
    if(!state.graph){toast('Add a repository to start the tour.');return;}
    $('mapTools').hidden=true;$('tourPanel').hidden=false;$('inspector').hidden=true;hideIssueDrawer();
    if(state.tourIndex<0)tourStep(1);else updateTour();
  }
  function updateTour(){
    const tour=state.tour,steps=tour?.steps||[],n=state.tourIndex;
    const step=n>=0?steps[n]:null;
    setText('tourIndex',steps.length?`${String(Math.max(0,n)+1).padStart(2,'0')} / ${String(steps.length).padStart(2,'0')}`:'— / —');
    setText('tourTitle',step?.title||'Discover your architecture');
    setText('tourDescription',step?.description||'Every district tells a different part of your repository’s story.');
    setText('tourNext',n>=steps.length-1?'Restart tour →':'Next stop →');
    $('tourPrev').disabled=n<=0;
    setText('tourDisclosure',tour?.mode==='ai'?'BharatCode-generated explanations can be mistaken. Verify them against the repository.':'Curated walkthrough based on available file groups and sampled static imports.');
  }
  function tourStep(delta){
    const steps=state.tour?.steps||[];if(!steps.length){toast('No tour is available for this repository.');return;}
    if(delta<0&&state.tourIndex<=0)return;
    if(delta>0&&state.tourIndex===steps.length-1)state.tourIndex=-1;
    state.tourIndex=Math.max(0,state.tourIndex+delta);
    const step=steps[state.tourIndex];
    if(getNode(step.nodeId)){state.renderer?.setSelected(step.nodeId,{focus:true});state.chosen=step.nodeId;}
    updateTour();
  }
  async function aiTour(){
    if(!state.session?.aiConfigured){toast('BharatCode AI needs BHARATCODE_API_KEY on the server. The curated tour still works.');return;}
    const button=$('aiTourButton');button.disabled=true;button.textContent='Generating AI tour…';
    try{state.tour=await post('/api/ai/tour',{graph:state.graph});state.tourIndex=-1;tourStep(1);}
    catch(e){toast(e.message,true);}finally{button.disabled=false;button.textContent='✧ Generate a BharatCode AI tour';}
  }
  async function askAi(){
    const question=$('aiQuestion').value.trim();if(!question)return;
    if(!state.session?.aiConfigured){toast('Set BHARATCODE_API_KEY on the server to ask questions.');return;}
    const button=$('askAiButton');button.disabled=true;$('aiResponse').hidden=false;setText('aiResponse','Thinking…');
    try{const answer=await post('/api/ai/ask',{graph:state.graph,question});setText('aiResponse',answer.answer||'No supported answer.');}
    catch(e){setText('aiResponse',e.message);}
    finally{button.disabled=false;}
  }
  function renderInspector(){
    const node=getNode(state.chosen);if(!node)return;
    const edges=state.graph.edges||[];
    const outs=edges.filter(e=>e.source===node.id),ins=edges.filter(e=>e.target===node.id);
    setText('inspectorGlyph',{frontend:'⌘',api:'{}',service:'⌁',database:'▤',library:'◈',security:'◇',infra:'▣',test:'✓',docs:'☷',core:'◎'}[node.kind]||'◇');
    $('inspectorGlyph').style.color=colors[node.kind]||'#a1ceff';
    setText('inspectorDistrict',kindLabel(node.kind).toUpperCase());setText('inspectorName',node.name);
    setText('inspectorPath',node.path||'Repository root');setText('inspectorDescription',node.description||'Files grouped by directory.');
    setText('inspectorFact',state.graph.source==='demo'?'Fictional demonstration data. Real imports are sampled when available.':`Inferred from file paths${node.sampled?' and sampled source imports':''}; actual behavior requires source review.`);
    setText('inspectorFiles',node.fileCount||0);setText('inspectorOut',outs.length);setText('inspectorIn',ins.length);
    const cons=$('inspectorConnections');cons.replaceChildren();
    for(const edge of [...outs,...ins].slice(0,8)){
      const outgoing=edge.source===node.id,other=getNode(outgoing?edge.target:edge.source);if(!other)continue;
      const item=document.createElement('button');item.type='button';item.className='connection-row';
      const copy=document.createElement('span');copy.style.minWidth='0';copy.style.flex='1';
      const title=document.createElement('strong');title.textContent=other.name;
      const subtitle=document.createElement('small');subtitle.textContent=outgoing?'Imports → '+other.path:'Imported by ← '+other.path;
      copy.append(title,subtitle);item.append(copy);
      item.addEventListener('click',()=>{clearImpact();state.chosen=other.id;state.renderer.setSelected(other.id,{focus:true});renderInspector();$('inspector').scrollTop=0;});cons.append(item);
    }
    if(!cons.children.length){const p=document.createElement('p');p.className='empty-small';p.textContent='No sampled import connections were observed here.';cons.append(p);}
    const symbols=$('inspectorSymbols');symbols.replaceChildren();
    const declarations=(node.symbols||[]).slice(0,8);
    $('inspectorSymbolsTitle').hidden=declarations.length===0;symbols.hidden=declarations.length===0;
    for(const sym of declarations){
      const row=document.createElement('div');row.className='file-row';
      const title=document.createElement('strong');title.textContent=`${sym.name}()`;
      const path=document.createElement('small');path.textContent=sym.file||'';
      row.append(title,path);symbols.append(row);
    }
    const files=$('inspectorFileList');files.replaceChildren();
    for(const f of (node.files||[]).slice(0,7)){
      const div=document.createElement('div');div.className='file-row';
      const link=document.createElement(state.graph.source==='github'?'a':'span');link.textContent=f;
      if(link.tagName==='A'){link.href=fileUrl(f);link.target='_blank';link.rel='noopener noreferrer';}
      div.append(link);files.append(div);
    }
    if(!files.children.length){const p=document.createElement('p');p.className='empty-small';p.textContent='No file paths in this snapshot.';files.append(p);}
    renderBuildingIssues(node.id);
  }
  function clearImpact(){
    state.impact=null;state.renderer?.setImpactTrace?.(null);
    $('impactPanel').hidden=true;setText('inspectorTrace','Trace change impact →');
  }
  function renderImpact(impact){
    if(!impact||impact.root!==state.chosen)return;
    $('impactPanel').hidden=false;
    setText('impactCount',`${impact.affectedCount} POSSIBLY AFFECTED`);
    const items=[...(impact.direct||[]),...(impact.indirect||[])];
    setText('impactMessage',items.length
      ? `${impact.direct.length} directly import this module; ${impact.indirect.length} more may depend on it through sampled import chains.`
      : 'No importing modules were observed in this limited sample. That does not prove the module is unused.');
    const parent=$('impactList');parent.replaceChildren();
    for(const entry of items.slice(0,16)){
      const button=document.createElement('button');button.type='button';button.className='impact-item';
      const title=document.createElement('strong');title.textContent=(entry.hops===1?'● ':'◇ ')+entry.name;
      const hint=document.createElement('small');hint.textContent=`${entry.hops} hop${entry.hops===1?'':'s'} · ${(entry.importPath||[]).join(' → ')}`;
      button.append(title,hint);
      button.addEventListener('click',()=>{
        clearImpact();state.chosen=entry.nodeId;state.renderer?.setSelected(entry.nodeId,{focus:true});renderInspector();
      });parent.append(button);
    }
    if(items.length>16){const more=document.createElement('p');more.className='empty-small';more.textContent=`+ ${items.length-16} more modules within the sampled import graph.`;parent.append(more);}
    setText('inspectorTrace','Clear trace');
  }
  async function traceImpact(){
    if(!state.graph||!state.chosen||!state.activeId)return;
    if(state.impact){clearImpact();setLayer('structure');return;}
    const nodeId=state.chosen;const button=$('inspectorTrace');
    button.disabled=true;setText('inspectorTrace','Tracing…');
    try{
      const impact=await api(`/api/my-repos/${encodeURIComponent(state.activeId)}/impact?nodeId=${encodeURIComponent(nodeId)}`);
      if(state.chosen!==nodeId)return;
      state.impact=impact;state.renderer?.setImpactTrace?.(impact);
      setLayer('dependencies');renderImpact(impact);
    }catch(e){toast(e.message,true);setText('inspectorTrace','Trace change impact →');}
    finally{button.disabled=false;}
  }
  function openFind(query='',tab='ask'){
    if(!state.graph)return;
    closePopovers();$('mapTools').hidden=true;hideIssueDrawer();
    const dialog=$('searchDialog');if(!dialog.open)dialog.showModal();
    if(query){$('searchInput').value=query;$('searchResults').replaceChildren();
      $('searchWelcome').hidden=true;state.lastFindResults=[];}
    setCompassTab(tab);
    if(query&&tab==='find')searchModules(query);
  }
  function setCompassTab(tab){
    state.compassTab=['ask','issues','find'].includes(tab)?tab:'ask';
    for(const name of ['ask','issues','find']){
      $(name+'Tab').hidden=name!==state.compassTab;
      const button=document.querySelector('[data-compass-tab="'+name+'"]');
      if(button){button.classList.toggle('active',name===state.compassTab);button.setAttribute('aria-pressed',String(name===state.compassTab));}
    }
    if(state.compassTab==='issues')renderIssueRadar();
    if(state.compassTab==='ask')$('assistantQuestion').focus();
    if(state.compassTab==='find')$('searchInput').focus();
  }
  function addAssistantWelcome(){
    const start=document.createElement('div');start.className='assistant-start';
    const title=document.createElement('strong');title.textContent='Your developer guide';
    const copy=document.createElement('span');copy.textContent='Ask how a feature works, how to approach a task, or where to start on an issue.';
    start.append(title,copy);$('assistantThread').append(start);
  }
  function setAssistantContext(nodeId=null,issueNumber=null){
    state.assistantNode=nodeId&&getNode(nodeId)?nodeId:null;
    state.assistantIssue=Number.isInteger(issueNumber)?issueNumber:null;
    const tags=[];if(state.assistantNode)tags.push('Building: '+(getNode(state.assistantNode)?.name||state.assistantNode));
    if(state.assistantIssue)tags.push('Issue #'+state.assistantIssue);
    $('assistantContext').hidden=!tags.length;setText('assistantContext',tags.join(' · '));
  }
  function assistantBubble(role,text){
    const box=document.createElement('div');box.className='chat-bubble '+role;
    if(role==='assistant'){const kicker=document.createElement('div');kicker.className='bubble-label';kicker.textContent='REPOWORLD GUIDE';box.append(kicker);}
    const content=document.createElement('p');content.textContent=text;box.append(content);
    $('assistantThread').append(box);$('assistantThread').scrollTop=$('assistantThread').scrollHeight;
    return box;
  }
  function assistantAnswer(box,result){
    box.replaceChildren();
    const kicker=document.createElement('div');kicker.className='bubble-label';
    kicker.textContent=result.mode==='ai'?'BHARATCODE · SOURCE-SCOPED AI':result.providerStatus==='timeout'?'BHARATCODE UNAVAILABLE · LOCAL PATH GUIDE':'LOCAL PATH GUIDE · NO AI KEY';box.append(kicker);
    readableParagraph(box,result.answer||'No supported answer.');
    const steps=Array.isArray(result.steps)?result.steps:[];
    if(steps.length){const ol=document.createElement('ol');for(const line of steps){const li=document.createElement('li');readableInline(li,line);ol.append(li);}box.append(ol);}
    const sourceRow=document.createElement('div');sourceRow.className='assistant-source-list';
    for(const entry of (result.sources||[]).slice(0,4)){
      if(!entry.url?.startsWith('https://github.com/'))continue;
      const link=document.createElement('a');link.href=entry.url;link.target='_blank';link.rel='noopener noreferrer';
      link.textContent='↗ '+(entry.file||'Source')+(entry.lineStart?` :${entry.lineStart}–${entry.lineEnd}`:'');sourceRow.append(link);
    }
    for(const id of (result.nodeIds||[]).slice(0,3)){
      const node=getNode(id);if(!node)continue;
      const b=document.createElement('button');b.type='button';b.className='assistant-node';b.textContent='⌖ '+node.name;
      b.addEventListener('click',()=>chooseSearchResult(id));sourceRow.append(b);
    }
    if(sourceRow.children.length)box.append(sourceRow);
    const meta=document.createElement('span');meta.className='assistant-meta';meta.textContent=result.disclosure||'Verify linked code before acting.';box.append(meta);
    $('assistantThread').scrollTop=$('assistantThread').scrollHeight;
  }
  async function sendAssistant(){
    const question=$('assistantQuestion').value.trim();if(!question||state.chatBusy||!state.activeId)return;
    state.chatBusy=true;$('assistantSend').disabled=true;setText('assistantSend','Working…');
    if(!state.chatHistory.length)$('assistantThread').replaceChildren();
    assistantBubble('user',question);$('assistantQuestion').value='';
    const answer=assistantBubble('assistant','Exploring relevant modules…');
    const repoId=state.activeId;
    try{
      const result=await post(`/api/my-repos/${encodeURIComponent(repoId)}/assistant`,{
        question,nodeId:state.assistantNode,issueNumber:state.assistantIssue,
        history:state.chatHistory.slice(-6)});
      if(repoId!==state.activeId)return;
      assistantAnswer(answer,result);
      state.chatHistory.push({role:'user',content:question},{role:'assistant',content:result.answer||''});
      state.chatHistory=state.chatHistory.slice(-6);
    }catch(e){answer.replaceChildren();const p=document.createElement('p');p.textContent=e.message;answer.append(p);}
    finally{state.chatBusy=false;$('assistantSend').disabled=false;setText('assistantSend','Send ↗');}
  }
  function hideIssueDrawer(){
    $('issueDrawer').hidden=true;state.issueOpenNode=null;state.issueSelectedNumber=null;
    state.issueInsightRevision++;
  }
  function issueFor(number){return (state.radar?.issues||[]).find(i=>i.number===number)||null;}
  function linkedIssues(nodeId){return (state.radar?.issues||[]).filter(i=>i.matches?.some(m=>m.nodeId===nodeId));}
  function openIssueMarker(nodeId,preferredNumber=null){
    if(!getNode(nodeId))return;
    const issues=linkedIssues(nodeId);
    if(!issues.length){toast('No open GitHub issue is currently linked to this building.');return;}
    openIssueDetails(issues.find(i=>i.number===preferredNumber)||issues[0],nodeId);
  }
  function openIssueDetails(issue,nodeId=null){
    if(!state.graph||!issueFor(issue?.number))return;
    hideIssueDrawer();
    $('searchDialog').open&&$('searchDialog').close();
    $('sceneTooltip').hidden=true;
    $('inspector').hidden=true;$('tourPanel').hidden=true;$('mapTools').hidden=true;
    state.issueOpenNode=getNode(nodeId)?nodeId:null;
    $('issueDrawer').hidden=false;
    const node=getNode(state.issueOpenNode),related=node?linkedIssues(node.id):[issue];
    setText('issueDrawerDistrict',node?kindLabel(node.kind).toUpperCase():'UNPLACED GITHUB ISSUE');
    setText('issueDrawerSubhead',node?`${related.length} open issue${related.length===1?'':'s'} associated with ${node.name}.`:'No reliable building placement is available for this issue.');
    const chooser=$('issueDrawerChooser'),select=$('issueDrawerSelect');
    select.replaceChildren();chooser.hidden=related.length<=1;
    for(const item of related){
      const option=document.createElement('option');option.value=String(item.number);
      option.textContent=`#${item.number} · ${item.title}`;select.append(option);
    }
    setText('issueDrawerChooseLabel',`CHOOSE FROM ${related.length} LINKED ISSUES`);
    showIssueDetail(issue,state.issueOpenNode);
    $('issueDrawer').scrollTop=0;
    $('closeIssueDrawer').focus();
  }
  function showIssueDetail(issue,nodeId){
    state.issueSelectedNumber=issue.number;
    const match=(issue.matches||[]).find(m=>m.nodeId===nodeId);
    setText('issueDrawerHeading',issue.title||'Untitled GitHub issue');
    setText('issueDetailIndex','OPEN ISSUE #'+issue.number);
    const tags=$('issueDetailLabels');tags.replaceChildren();
    for(const label of (issue.labels||[]).slice(0,3)){const span=document.createElement('span');span.textContent=label;tags.append(span);}
    const place=$('issuePlacement');place.replaceChildren();
    const status=document.createElement('strong');
    status.textContent=match?.confidence==='observed'?'● Identifier observed in public source':match?.confidence==='referenced'?'● Path referenced in issue':match?.confidence==='suggested'?'◌ Suggested building · unverified':'◇ No verified building location';
    status.className=['referenced','observed'].includes(match?.confidence)?'placement-referenced':'placement-suggested';
    place.append(status);
    if(match?.evidence){const why=document.createElement('small');why.textContent=match.evidence;place.append(why);}
    setText('issueDetailBody',issue.body?.trim()||issue.snippet?.trim()||'No issue description was provided. Open GitHub to read the full report and discussion.');
    $('issueOriginalReport').open=false;
    $('issueGithubLink').href=issue.url;
    $('issueGithubLink').textContent=issue.commentsCount>0?`Read issue and ${issue.commentsCount} GitHub comment${issue.commentsCount===1?'':'s'} ↗`:'Read full issue on GitHub ↗';
    $('issueDetail').hidden=false;
    $('issueDrawerSelect').value=String(issue.number);
    explainIssue(issue,nodeId);
  }
  // All model and GitHub text is untrusted. Build DOM nodes instead of HTML.
  function readableInline(target,value){
    const src=String(value||'').replace(/\*\*(.*?)\*\*/g,'$1');
    if(!src.includes('`')){target.textContent=src;return;}
    const pattern=/`([^`\n]{1,160})`/g;let pos=0;let hit;
    while((hit=pattern.exec(src))){
      if(hit.index>pos){const span=document.createElement('span');span.textContent=src.slice(pos,hit.index);target.append(span);}
      const code=document.createElement('code');code.textContent=hit[1];target.append(code);pos=pattern.lastIndex;
    }
    if(pos<src.length){const span=document.createElement('span');span.textContent=src.slice(pos);target.append(span);}
  }
  function readableParagraph(target,value,cls=''){
    const text=String(value||'').replace(/^(?:#{1,5}\s+|\s*[-*]\s+)/gm,'').trim();
    if(!text)return;
    const p=document.createElement('p');if(cls)p.className=cls;
    readableInline(p,text);target.append(p);
  }
  function insightSection(target,title,items,numbered=false){
    if(!items?.length)return;
    const section=document.createElement('section');section.className='insight-section';
    const heading=document.createElement('h3');heading.textContent=title;section.append(heading);
    const list=document.createElement(numbered?'ol':'ul');list.className='insight-list';
    for(const item of items){
      if(typeof item!=='string'||!item.trim())continue;
      const li=document.createElement('li');readableInline(li,item.trim());list.append(li);
    }
    if(list.children.length){section.append(list);target.append(section);}
  }
  function retainObservedIssueLocations(issueNumber,result){
    // Reconcile the current page's issue markers with *fetched* source evidence.
    // No persistence and no claims about verified defects or runtime behavior.
    const issue=issueFor(issueNumber);
    if(!issue||!state.graph||!Array.isArray(result?.observedLocations))return;
    const locations=result.observedLocations.filter(loc=>loc&&getNode(loc.nodeId)
      &&typeof loc.file==='string'&&loc.file.length<380
      &&loc.evidence==='identifier-observed'&&Array.isArray(loc.symbols)&&loc.symbols.length);
    if(!locations.length)return;
    const existing=(issue.matches||[]).filter(m=>m&&m.confidence==='referenced');
    const known=new Set(existing.map(m=>m.nodeId));
    for(const loc of locations.slice(0,3)){
      if(known.has(loc.nodeId))continue;
      known.add(loc.nodeId);
      existing.push({nodeId:loc.nodeId,confidence:'observed',path:loc.file,
        evidence:`Identifier ${loc.symbols[0]} appears in fetched source. Issue impact is unverified.`});
    }
    // A fresh source observation supersedes an unverified directory guess.
    issue.matches=existing;
    // Replace the old "unplaced" or guessed location text in the open panel.
    // Do not silently change the user's issue selector or navigate the camera.
    if(state.issueSelectedNumber===issueNumber&&!$('issueDrawer').hidden){
      const loc=locations[0],building=getNode(loc.nodeId);
      if(building){
        setText('issueDrawerDistrict',kindLabel(building.kind).toUpperCase()+' · SOURCE OBSERVED');
        setText('issueDrawerSubhead',`An identifier appears in ${loc.file}. The issue impact is not confirmed.`);
        const place=$('issuePlacement');place.replaceChildren();
        const status=document.createElement('strong');status.className='placement-referenced';
        status.textContent='● Identifier observed in fetched source';
        const detail=document.createElement('small');
        detail.textContent=`Mapped to ${building.name}; see source and investigation steps below.`;
        place.append(status,detail);
      }
    }
    const byNode={};let placed=0;
    for(const item of (state.radar.issues||[])){
      if(item.matches?.length)placed++;
      for(const match of (item.matches||[])){
        if(!getNode(match.nodeId))continue;
        const bucket=byNode[match.nodeId]||(byNode[match.nodeId]={referenced:[],suggested:[],observed:[]});
        const kind=match.confidence==='observed'?'observed':match.confidence==='referenced'?'referenced':'suggested';
        if(!bucket[kind].includes(item.number))bucket[kind].push(item.number);
      }
    }
    state.radar.byNode=byNode;state.radar.placed=placed;
    state.radar.unplaced=(state.radar.issues||[]).length-placed;
    state.renderer?.setIssueMarkers?.(byNode);
    setText('issueMapCount',`${state.radar.total} OPEN ISSUES · ${placed} ON MAP`);
    if(state.chosen)renderBuildingIssues(state.chosen);
  }
  function renderIssueInsight(result){
    const container=$('issueAiResult');container.replaceChildren();
    const isAi=result.mode==='ai';
    setText('issueAiHeading',isAi?'BHARATCODE · ISSUE GUIDE':result.providerStatus==='timeout'?'AI UNAVAILABLE · FILE GUIDE':'FILE GUIDE · AI NOT ACTIVE');
    const report=String(result.issueSummary||'').trim();
    const answer=String(result.answer||'No supported answer was returned.').trim();
    if(report){
      const title=document.createElement('div');title.className='insight-eyebrow';title.textContent='WHAT IS REPORTED';container.append(title);
      readableParagraph(container,report,'insight-lead');
      if(answer&&answer.toLowerCase()!==report.toLowerCase()){
        const details=document.createElement('details');details.className='insight-more';
        const summary=document.createElement('summary');summary.textContent='Read AI reasoning';details.append(summary);
        readableParagraph(details,answer);container.append(details);
      }
    }else{readableParagraph(container,answer,'insight-lead');}
    if(isAi&&!(result.sourceFilesRead>0)){
      const warning=document.createElement('div');warning.className='insight-warning';
      warning.textContent='No live source excerpt was available. Treat file suggestions as unverified.';
      container.append(warning);
    }
    if(isAi&&Array.isArray(result.unverifiedMentions)&&result.unverifiedMentions.length){
      const warning=document.createElement('div');warning.className='insight-warning';
      warning.textContent='Not confirmed by the inspected source: '+result.unverifiedMentions.slice(0,3).join(', ')+'. Check before changing code.';
      container.append(warning);
    }
    const seenLocations=(result.observedLocations||[]).filter(loc=>loc&&getNode(loc.nodeId)&&loc.evidence==='identifier-observed');
    if(seenLocations.length){
      const section=document.createElement('section');section.className='insight-section';
      const heading=document.createElement('h3');heading.textContent='CODE LOCATED IN THE CITY';section.append(heading);
      const hint=document.createElement('p');hint.className='observed-hint';
      hint.textContent='Identifiers appear in fetched source; the reported issue itself is not independently verified.';
      section.append(hint);
      for(const loc of seenLocations.slice(0,2)){
        const button=document.createElement('button');button.type='button';button.className='observed-source-location';
        const name=document.createElement('strong');name.textContent=loc.file;
        const detail=document.createElement('small');detail.textContent='Show '+(getNode(loc.nodeId)?.name||loc.nodeId)+' in city ↗';
        button.append(name,detail);
        button.addEventListener('click',()=>chooseSearchResult(loc.nodeId));
        section.append(button);
      }
      container.append(section);
    }
    insightSection(container,'WHAT THE SOURCE SHOWS',result.codeEvidence||[]);
    insightSection(container,'HOW TO INVESTIGATE',result.steps||[],true);
    insightSection(container,'TESTS TO CHECK · NOT RUN',result.tests||[]);
    const entries=(result.sources||[]).filter(e=>typeof e.url==='string'&&e.url.startsWith('https://github.com/')).slice(0,4);
    if(entries.length){
      const section=document.createElement('section');section.className='insight-section';
      const title=document.createElement('h3');title.textContent='SOURCE FILES';section.append(title);
      const sources=document.createElement('div');sources.className='issue-insight-sources';
      for(const entry of entries){
        const a=document.createElement('a');a.href=entry.url;a.target='_blank';a.rel='noopener noreferrer';
        const filename=document.createElement('span');filename.textContent=entry.file||'Source';a.append(filename);
        const secondary=document.createElement('small');
        secondary.textContent=entry.evidence==='excerpt'?(entry.lineStart?`Lines ${entry.lineStart}–${entry.lineEnd} · source excerpt`:'Source excerpt'):'Path only · not inspected';
        a.append(secondary);sources.append(a);
      }
      section.append(sources);container.append(section);
    }
    const note=document.createElement('p');note.className='insight-disclosure';
    note.textContent=isAi?'AI guidance, not a verified fix. Review code and run tests before editing.':(result.disclosure||'Code has not been inspected.');
    container.append(note);
    $('issueFollowUp').hidden=false;$('issueRetry').hidden=result.providerStatus!=='timeout';
  }
  async function explainIssue(issue,nodeId){
    if(state.radar?.browserFallback){
      $('issueRetry').hidden=true;$('issueFollowUp').hidden=false;
      setText('issueAiHeading','BROWSER GITHUB FEED · UNVERIFIED');
      setText('issueAiResult','The issue title and description came from your browser’s public GitHub request. RepoWorld’s server has not independently checked this report or inspected its source. Open the original issue to verify it. Enable a private server-side GITHUB_TOKEN for source-scoped issue investigation.');
      return;
    }
    const repoId=state.activeId,number=issue.number,key=`${repoId}:${number}:${nodeId||''}`,serial=++state.issueInsightRevision;
    const previous=state.issueInsightCache.get(key);
    if(previous){retainObservedIssueLocations(number,previous);renderIssueInsight(previous);return;}
    $('issueRetry').hidden=true;$('issueFollowUp').hidden=true;
    setText('issueAiHeading',state.session?.aiConfigured?'BHARATCODE · INVESTIGATING':'LOCAL FILE GUIDE');
    setText('issueAiResult',state.session?.aiConfigured?'Reading the reported issue and relevant public source files…':'Finding related paths in the saved repository snapshot…');
    const question=`Explain open issue #${number}: ${issue.title}. Summarize the reported problem, identify code evidence versus suggested locations, propose safe investigation steps and relevant tests, and cite only available source files.`.slice(0,650);
    try{
      const result=await post(`/api/my-repos/${encodeURIComponent(repoId)}/assistant`,{question,nodeId:nodeId||null,issueNumber:number,history:[]});
      if(repoId!==state.activeId||serial!==state.issueInsightRevision||state.issueSelectedNumber!==number||$('issueDrawer').hidden)return;
      state.issueInsightCache.set(key,result);retainObservedIssueLocations(number,result);renderIssueInsight(result);
    }catch(e){
      if(serial!==state.issueInsightRevision||$('issueDrawer').hidden)return;
      setText('issueAiHeading','ISSUE GUIDE · UNAVAILABLE');
      setText('issueAiResult',e.message+' The original issue remains available on GitHub.');
      $('issueRetry').hidden=false;$('issueFollowUp').hidden=false;
    }
  }
  function followUpIssue(){
    const issue=issueFor(state.issueSelectedNumber);if(!issue)return;
    const nodeId=state.issueOpenNode;
    if(state.radar?.browserFallback){
      setAssistantContext(nodeId,null);openFind('','ask');
      $('assistantQuestion').value=('Using only the imported file map, which modules might be relevant to: '+issue.title+'? The issue title came from my browser GitHub feed and was not verified by this server; avoid claims about a confirmed defect.').slice(0,650);
      $('assistantQuestion').focus();return;
    }
    setAssistantContext(nodeId,issue.number);openFind('','ask');
    $('assistantQuestion').value=`For issue #${issue.number} (${issue.title}), help me investigate the next step using source evidence.`.slice(0,650);
    $('assistantQuestion').focus();
  }
  async function loadIssueRadar(force=false){
    if(!state.activeId||!state.graph)return;
    const repoId=state.activeId,serial=++state.radarRevision;
    state.radar=null;state.radarError=null;setText('issueSummary','Checking open GitHub issues…');
    try{
      const data=await api(`/api/my-repos/${encodeURIComponent(repoId)}/issues${force?'?refresh=true':''}`);
      if(repoId!==state.activeId||serial!==state.radarRevision)return;
      state.radar=data;state.renderer?.setIssueMarkers?.(data.byNode||{});
      $('issueMapLegend').hidden=!data.total;
      setText('issueMapCount',`${data.total} OPEN ISSUE${data.total===1?'':'S'} · ${data.placed} ON MAP`);
      setText('issuesTabCount',data.total>0?data.total:'');$('issuesTabCount').hidden=!data.total;
    }catch(e){
      if(repoId!==state.activeId||serial!==state.radarRevision)return;
      // Fallback only for GitHub's provider quota, never our own guest quotas.
      if(e.status===429&&/GitHub/i.test(e.message)&&state.graph?.source==='github'){
        try{
          const direct=await window.RepoWorldBrowserIssueRadar(state.graph);
          if(repoId!==state.activeId||serial!==state.radarRevision)return;
          state.radar=direct;state.radarError=null;
          state.renderer?.setIssueMarkers?.(direct.byNode);
          $('issueMapLegend').hidden=!direct.total;
          setText('issueMapCount',direct.total+' OPEN ISSUES · '+direct.placed+' ON MAP');
          setText('issuesTabCount',direct.total>0?direct.total:'');$('issuesTabCount').hidden=!direct.total;
        }catch(browserError){
          if(repoId!==state.activeId||serial!==state.radarRevision)return;
          state.radarError=e.message+' Browser fallback: '+browserError.message;
          state.renderer?.setIssueMarkers?.({});$('issueMapLegend').hidden=true;
        }
      }else{state.radarError=e.message;state.renderer?.setIssueMarkers?.({});$('issueMapLegend').hidden=true;}
    }
    renderIssueRadar();if(state.chosen)renderBuildingIssues(state.chosen);
  }
  function issuePlacementName(match){
    const n=getNode(match.nodeId);return (match.confidence==='observed'?'Source observed: ':match.confidence==='referenced'?'Referenced: ':'Suggested: ')+(n?.name||match.nodeId);
  }
  function issueItem(issue){
    const row=document.createElement('div');row.className='issue-item';
    const heading=document.createElement('div');heading.className='issue-heading';
    const a=document.createElement('button');a.type='button';a.className='issue-title-button';a.textContent=issue.title;
    a.addEventListener('click',()=>openIssueDetails(issue,issue.matches?.[0]?.nodeId||null));
    const number=document.createElement('span');number.className='issue-number';number.textContent='#'+issue.number;
    heading.append(a,number);row.append(heading);
    if(issue.labels?.length){const tags=document.createElement('div');tags.className='issue-places';
      for(const label of issue.labels.slice(0,4)){const tag=document.createElement('span');tag.className='issue-label';tag.textContent=label;tags.append(tag);}row.append(tags);}
    const places=document.createElement('div');places.className='issue-places';
    if(!issue.matches?.length){const plain=document.createElement('span');plain.className='issue-plain';plain.textContent='No defensible building match';places.append(plain);}
    for(const match of (issue.matches||[]).slice(0,4)){
      const button=document.createElement('button');button.type='button';button.className='issue-place '+(match.confidence==='suggested'?'suggested':'');
      button.textContent=issuePlacementName(match);button.title=match.evidence||'';
      button.addEventListener('click',()=>{
        state.renderer?.setSelected(match.nodeId,{focus:true});
        openIssueMarker(match.nodeId,issue.number);
      });places.append(button);
    }row.append(places);
    const ask=document.createElement('button');ask.type='button';ask.className='assistant-node';ask.textContent='Discuss issue with assistant ↗';
    ask.addEventListener('click',()=>openIssueDetails(issue,issue.matches?.[0]?.nodeId||null));
    row.append(ask);return row;
  }
  function renderIssueRadar(){
    const area=$('issueList');area.replaceChildren();
    if(state.radarError){setText('issueSummary','Issue feed unavailable: '+state.radarError);return;}
    if(!state.radar){setText('issueSummary','Checking GitHub open issues…');return;}
    const info=state.radar;setText('issueSummary',(info.browserFallback?'BROWSER GITHUB FEED · UNVERIFIED BY SERVER · ':'')+`${info.total} open issues sampled · ${info.placed} placed · ${info.unplaced} unplaced${info.partial?' · Partial listing':''}`);
    for(const item of info.issues||[])area.append(issueItem(item));
    if(!area.children.length){const p=document.createElement('p');p.className='issue-plain';p.textContent='No open GitHub issues found in this sample.';area.append(p);}
    setText('issueDisclaimer',info.scope||'Issue locations are suggestions, not proven affected files.');
  }
  function renderBuildingIssues(nodeId){
    const container=$('buildingIssues'),list=$('buildingIssuesList');list.replaceChildren();
    const related=(state.radar?.issues||[]).filter(i=>i.matches?.some(m=>m.nodeId===nodeId));
    container.hidden=!related.length;
    setText('buildingIssueCount',related.length+' LINKED');
    const more=$('buildingIssuesMore');more.hidden=related.length<=3;
    more.textContent=`Browse all ${related.length} linked issues ↗`;
    more.onclick=()=>openIssueDetails(related[0],nodeId);
    for(const item of related.slice(0,3)){
      const match=item.matches.find(m=>m.nodeId===nodeId);
      const a=document.createElement('button');a.type='button';a.className='building-issue-row';a.addEventListener('click',()=>openIssueDetails(item,nodeId));
      const title=document.createElement('strong');title.textContent='#'+item.number+' '+item.title;
      const hint=document.createElement('small');hint.textContent=match?.confidence==='observed'?'SOURCE IDENTIFIER OBSERVED':match?.confidence==='referenced'?'PATH REFERENCED':'SUGGESTED ONLY';
      const action=document.createElement('span');action.className='building-issue-action';action.textContent='Investigate ↗';
      a.append(title,hint,action);list.append(a);
    }
  }
  function chooseSearchResult(nodeId){
    const node=getNode(nodeId);if(!node)return;hideIssueDrawer();
    $('searchDialog').close();clearImpact();state.chosen=node.id;
    state.renderer?.setSelected(node.id,{focus:true});renderInspector();$('inspector').scrollTop=0;
    $('inspector').hidden=false;$('tourPanel').hidden=true;
  }
  async function searchModules(query){
    clearTimeout(state.searchTimer);const serial=++state.searchRevision;
    const needle=esc(query).trim();
    const parent=$('searchResults');parent.replaceChildren();state.lastFindResults=[];
    $('searchWelcome').hidden=Boolean(needle);
    if(!state.graph||!state.activeId||needle.length<2){return;}
    // Never dispatch a request for every keystroke; ignore stale responses.
    const loading=document.createElement('p');loading.className='empty-small';loading.textContent='Searching imported code paths…';parent.append(loading);
    state.searchTimer=setTimeout(async()=>{
      try{
        const data=await api(`/api/my-repos/${encodeURIComponent(state.activeId)}/find?q=${encodeURIComponent(needle)}`);
        if(serial!==state.searchRevision||!$('searchDialog').open)return;
        parent.replaceChildren();state.lastFindResults=data.results||[];
        for(const [i,item] of state.lastFindResults.entries()){
          const result=document.createElement('button');result.type='button';result.className='search-result';
          const meta=document.createElement('div');meta.className='result-meta';
          const name=document.createElement('strong');name.textContent=item.name||item.path;
          const rank=document.createElement('span');rank.className='rank';rank.textContent=i===0?'BEST PATH MATCH':`MATCH ${i+1}`;
          meta.append(name,rank);
          const path=document.createElement('small');path.textContent=item.path;
          const context=document.createElement('span');context.className='match-context';
          context.textContent=item.symbols?.length?`Sampled declaration: ${item.symbols.slice(0,2).map(s=>s.name).join(' · ')}`:
            item.files?.length?`Matching file examples: ${item.files.slice(0,2).join(' · ')}`:'Matched its directory or module description';
          result.append(meta,path,context);result.addEventListener('click',()=>chooseSearchResult(item.nodeId));parent.append(result);
        }
        if(!state.lastFindResults.length){const p=document.createElement('p');p.className='empty-small';
          p.textContent='No matching path found in this snapshot. Try a shorter term or an exact filename. Unindexed files may still contain the feature.';parent.append(p);}
        setText('searchScope',data.scope||'Matches are based on directory names and filenames, not verified behavior.');
      }catch(e){if(serial!==state.searchRevision)return;parent.replaceChildren();const p=document.createElement('p');p.className='empty-small';p.textContent=e.message;parent.append(p);}
    },210);
  }
  function bindEvents(){
    $('repoMenuButton').addEventListener('click',()=>toggleMenu('repoMenu','repoMenuButton'));
    document.addEventListener('pointerdown',e=>{
      if(!e.target.closest('#repoMenuWrap'))closePopovers();
    });
    ['emptyAddRepo','addAnotherRepo'].forEach(id=>$(id).addEventListener('click',startImport));
    $('refreshCurrentRepo').addEventListener('click',refreshCodeIndex);
    $('copyCityLink').addEventListener('click',copyCityLink);
    $('closeImport').addEventListener('click',hideImport);
    $('importForm').addEventListener('submit',e=>{e.preventDefault();importRepository($('importInput').value);});
    $('importDemo').addEventListener('click',openFictionalDemo);
    $('addRepoDialog').addEventListener('cancel',e=>{if(state.busy)e.preventDefault();});
    $('mapCommandTrigger').addEventListener('click',()=>{setAssistantContext(null,null);openFind();});
    document.querySelectorAll('[data-compass-tab]').forEach(b=>b.addEventListener('click',()=>setCompassTab(b.dataset.compassTab)));
    $('assistantSend').addEventListener('click',sendAssistant);
    $('assistantQuestion').addEventListener('keydown',e=>{if(e.key==='Enter'&&(e.ctrlKey||e.metaKey)){e.preventDefault();sendAssistant();}});
    $('refreshIssues').addEventListener('click',()=>loadIssueRadar(true));
    $('issueMapLegend').addEventListener('click',()=>openFind('','issues'));
    $('issueDrawerSelect').addEventListener('change',()=>{const selected=issueFor(Number($('issueDrawerSelect').value));if(selected){showIssueDetail(selected,state.issueOpenNode);$('issueDrawer').scrollTop=0;}});
    $('closeIssueDrawer').addEventListener('click',hideIssueDrawer);
    $('issueRetry').addEventListener('click',()=>{const issue=issueFor(state.issueSelectedNumber);if(issue){state.issueInsightCache.delete(`${state.activeId}:${issue.number}:${state.issueOpenNode||''}`);explainIssue(issue,state.issueOpenNode);}});
    $('issueFollowUp').addEventListener('click',followUpIssue);
    $('inspectorAsk').addEventListener('click',()=>{setAssistantContext(state.chosen,null);openFind('','ask');});
    document.querySelectorAll('[data-layer]').forEach(b=>b.addEventListener('click',()=>setLayer(b.dataset.layer)));
    $('resetCamera').addEventListener('click',()=>{state.renderer?.resetCamera();$('mapTools').hidden=true;});
    $('tourButton').addEventListener('click',openTour);
    $('findButton').addEventListener('click',()=>openFind('','find'));
    $('closeSearch').addEventListener('click',()=>{$('searchDialog').close();state.searchRevision++;clearTimeout(state.searchTimer);});
    $('searchForm').addEventListener('submit',e=>{e.preventDefault();if(state.compassTab==='find'&&state.lastFindResults.length)chooseSearchResult(state.lastFindResults[0].nodeId);});
    document.querySelectorAll('[data-suggestion]').forEach(button=>button.addEventListener('click',()=>{
      const query=button.dataset.suggestion;$('searchInput').value=query;searchModules(query);
    }));
    $('quickTour').addEventListener('click',()=>{$('searchDialog').close();openTour();});
    $('showMapOptions').addEventListener('click',()=>{$('searchDialog').close();$('mapTools').hidden=false;});
    $('searchInput').addEventListener('input',()=>searchModules($('searchInput').value));
    $('closeInspector').addEventListener('click',()=>$('inspector').hidden=true);
    $('inspectorFocus').addEventListener('click',()=>{if(state.chosen)state.renderer?.setSelected(state.chosen,{focus:true});});
    $('inspectorTrace').addEventListener('click',traceImpact);
    $('exitImpact').addEventListener('click',()=>{clearImpact();setLayer('structure');});
    $('closeTour').addEventListener('click',()=>$('tourPanel').hidden=true);
    $('tourPrev').addEventListener('click',()=>tourStep(-1));$('tourNext').addEventListener('click',()=>tourStep(1));
    $('aiTourButton').addEventListener('click',aiTour);$('askAiButton').addEventListener('click',askAi);
    document.addEventListener('keydown',e=>{
      if(e.key==='Escape'){$('inspector').hidden=true;$('tourPanel').hidden=true;hideIssueDrawer();closePopovers();}
      if(((e.key==='/'&&!e.metaKey&&!e.ctrlKey)||(e.key.toLowerCase()==='k'&&(e.metaKey||e.ctrlKey)))
        &&state.graph&&!['TEXTAREA','INPUT'].includes(document.activeElement?.tagName)){e.preventDefault();openFind();}
    });
  }
  async function boot(){
    showView();
    try{
      await refreshSession();
      const requested=deepLinkedRepo();
      // A shared URL never triggers a network import or AI call automatically.
      // Existing browser snapshots open immediately; new browsers must confirm
      // the import explicitly, keeping anonymous API use under user control.
      const existing=requested&&state.repos.find(repo=>repo.fullName?.toLowerCase()===requested.toLowerCase());
      if(existing){
        await selectRepo(existing.id);
      }else{
        if(state.activeId)await selectRepo(state.activeId);else showEmpty();
        if(requested){
          startImport();
          $('importInput').value=requested;
        }
      }
    }catch(e){
      showEmpty();toast('Could not open this browser workspace: '+e.message,true);
    }
  }
  document.addEventListener('DOMContentLoaded',()=>{bindEvents();boot();});
})();
