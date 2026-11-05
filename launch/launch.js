/* RepoWorld static launch page: fast first paint while the free backend wakes. */
(function(){
  'use strict';
  const BACKEND_ORIGIN='https://repoworld-3b9e.onrender.com';
  const MAX_ATTEMPTS=8;
  const PROBE_TIMEOUT_MS=85000;
  const MAX_QUERY_LENGTH=150;
  const PUBLIC_REPO=/^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?\/[A-Za-z0-9_.-]{1,100}$/;
  const byId=id=>document.getElementById(id);
  const statusHeadline=byId('statusHeadline');
  const statusDetail=byId('statusDetail');
  const statusIcon=byId('statusIcon');
  const retry=byId('retry');
  const direct=byId('openDirect');
  const query=new URLSearchParams(window.location.search);
  const requested=query.get('repo')||'';
  const target=new URL(BACKEND_ORIGIN+'/');
  if(requested.length<=MAX_QUERY_LENGTH&&PUBLIC_REPO.test(requested)&&!['.','..'].includes(requested.split('/')[1])){
    target.searchParams.set('repo',requested);
  }
  direct.href=target.toString();
  let active=false;
  let completed=false;
  let tries=0;
  let pendingTimeout=null;
  let backoffTimeout=null;
  let activeProbe=null;
  const setStatus=(headline,detail,icon)=>{
    statusHeadline.textContent=headline;
    statusDetail.textContent=detail;
    statusIcon.classList.toggle('is-ready',icon==='ready');
    statusIcon.classList.toggle('is-error',icon==='error');
  };
  function cancelProbe(){
    clearTimeout(pendingTimeout);
    clearTimeout(backoffTimeout);
    if(activeProbe){activeProbe.onload=null;activeProbe.onerror=null;activeProbe=null;}
    active=false;
  }
  function finished(){
    if(completed)return;
    completed=true;cancelProbe();retry.hidden=true;
    setStatus('RepoWorld is ready. Opening your city…','The free backend responded successfully.','ready');
    window.setTimeout(()=>window.location.replace(target.toString()),450);
  }
  function failed(){
    if(!active||completed)return;
    cancelProbe();
    if(tries>=MAX_ATTEMPTS){
      setStatus('The live city is taking longer than expected.','You can try again or use the direct link. There is no paid hosting requirement.','error');
      retry.hidden=false;
      return;
    }
    setStatus('Still waking the free workspace…','The first visit after inactivity may take longer. We are checking again.','waiting');
    backoffTimeout=window.setTimeout(probe,Math.min(tries*3000,12000));
  }
  function probe(){
    if(completed||active)return;
    tries+=1;active=true;retry.hidden=true;
    if(tries===1)setStatus('Connecting to the live city…','Starting the free application. We will open it when the server responds.','waiting');
    const image=new Image();
    activeProbe=image;
    image.referrerPolicy='no-referrer';
    pendingTimeout=window.setTimeout(failed,PROBE_TIMEOUT_MS);
    image.onload=finished;
    image.onerror=failed;
    // Only the live backend readiness endpoint can return a loadable SVG;
    // this avoids redirecting when static assets work but SQLite is unready.
    // Browsers may attach existing backend cookies; we never read them.
    image.src=BACKEND_ORIGIN+'/api/ready.svg?launcher='+Date.now()+'-'+tries;
  }
  retry.addEventListener('click',()=>{cancelProbe();tries=0;probe();});
  window.addEventListener('pagehide',cancelProbe,{once:true});
  probe();
})();
