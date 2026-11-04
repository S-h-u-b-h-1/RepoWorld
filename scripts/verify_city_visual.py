"""Offline Chromium visual regression: geometry, 3D camera recovery, and minimal UI.

This is a *fictional fixture*; it never calls GitHub or BharatCode.
"""
import asyncio
import base64
import json
from pathlib import Path
from playwright.async_api import async_playwright

ROOT=Path(__file__).resolve().parents[1]
STATIC=ROOT/'app/static'
OUT=ROOT/'evidence'

def fixture_graph():
    nodes=[]
    for district,num,files in [('core',7,6),('docs',5,3),('test',1,9)]:
        for i in range(num):
            nodes.append({'id':f'{district}/module{i}', 'name':f'{district.title()} {i+1}',
                          'kind':district,'fileCount':files+i,'path':f'{district}/module{i}',
                          'description':'Fictional source module for camera regression.', 'files':[f'{district}/module{i}.py']})
    return {'name':'MCA (visual fixture)','owner':'Fixture','source':'demo','branch':'main','url':'https://github.com/example/fixture',
            'nodes':nodes,'edges':[{'source':nodes[i]['id'],'target':nodes[i+1]['id'],'type':'import'} for i in (0,1,3,7)],
            'stats':{'modules':len(nodes),'files':sum(n['fileCount'] for n in nodes),'dependencies':4}}

async def test(page,w,h):
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    html=(STATIC/'index.html').read_text().replace('<link rel="stylesheet" href="/static/styles.css">','').replace('<script defer src="/static/world.js"></script>','').replace('<script defer src="/static/app.js"></script>','')
    await page.set_content(html,wait_until='domcontentloaded')
    css=(STATIC/'styles.css').read_text()
    logo=base64.b64encode((STATIC/'city-concept.png').read_bytes()).decode()
    css=css.replace("url('/static/city-concept.png')", "url('data:image/png;base64,"+logo+"')")
    await page.add_style_tag(content=css)
    graph=fixture_graph()
    session={'authenticated':True,'guest':True,'user':None,'csrf':'safe-fixture',
        'repositories':[{'id':'fixture','owner':'Fixture','name':'MCA','fullName':'Fixture/MCA','updatedAt':1}],
        'activeRepo':'fixture','aiConfigured':False}
    await page.evaluate('''window.fetch=async function(input,options){
      let path=String(input),v=window.__DEMO__;
      let body=path==='/api/session'?v.session:path.startsWith('/api/my-repos/fixture/issues')?{issues:[],byModule:{}}:
          path.startsWith('/api/my-repos/')?{id:'fixture',graph:v.graph}:path==='/api/tour'?{steps:[],mode:'guided'}:{};
      return new Response(JSON.stringify(body),{status:200,headers:{'Content-Type':'application/json'}});
    };''')
    await page.evaluate(f'window.__DEMO__={json.dumps({"session":session,"graph":graph})}')
    await page.add_script_tag(content=(STATIC/'world.js').read_text())
    await page.evaluate('(() => { const Base=window.RepoWorldRenderer; window.RepoWorldRenderer=class extends Base { constructor(...a){super(...a);window.__city=this;} }; })()')
    await page.add_script_tag(content=(STATIC/'app.js').read_text())
    await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
    await page.wait_for_function('!!window.__city && window.__city.nodes.length===13',timeout=10000)
    await page.wait_for_timeout(350)
    assert await page.locator('#canvasStage').is_visible()
    assert not await page.locator('#inspector').is_visible()
    assert await page.evaluate('document.documentElement.scrollWidth<=window.innerWidth')
    dims=await page.evaluate('''() => {
      const r=window.__city;
      return {districts:r.districts.length,coreHeight:r.project(0,23.5,0).y,
        overview:r.overviewDistance,distance:r.distance,pitch:r.pitch,
        width:r.width,height:r.height};
    }''')
    assert dims['districts']==3, dims
    assert dims['distance']>=100, dims
    OUT.mkdir(exist_ok=True)
    await page.screenshot(path=str(OUT/f'restored-city-{w}.png'))
    # Reproduce a zoomed/low-angle camera, then verify the reset (without UI clutter).
    await page.evaluate('''() => { const r=window.__city; r.distance=15; r.pitch=.2;
      r.canvas.dispatchEvent(new WheelEvent('wheel',{deltaY:-9999,cancelable:true}));
      r.pitch=Math.max(.57,Math.min(1.11,r.pitch));
      r.canvas.dispatchEvent(new MouseEvent('dblclick',{bubbles:true,cancelable:true})); }''')
    await page.wait_for_timeout(100)
    recovery=await page.evaluate('''() => ({distance:window.__city.distance,
      overview:window.__city.overviewDistance,pitch:window.__city.pitch,
      target:window.__city.targetPan})''')
    assert recovery['distance']==recovery['overview'] and recovery['pitch']==.83, recovery
    assert recovery['target']=={'x':0,'z':0}, recovery
    assert not errors, errors
    print(w,h, 'pass', dims,'reset',recovery)

async def main():
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        for w,h in ((1440,900),(390,844)):
            ctx=await browser.new_context(viewport={'width':w,'height':h},device_scale_factor=1)
            page=await ctx.new_page()
            await test(page,w,h)
            await ctx.close()
        await browser.close()

if __name__=='__main__': asyncio.run(main())
