"""Focused, credential-free browser regression test for real city zoom controls."""
import asyncio
import base64
import json
from pathlib import Path
from playwright.async_api import async_playwright
from app.demo import build_demo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evidence'

async def exercise(width, height):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context = await browser.new_context(viewport={'width':width,'height':height}, device_scale_factor=1)
        page = await context.new_page()
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        html = (ROOT/'app/static/index.html').read_text()
        html = html.replace('<link rel="stylesheet" href="/static/styles.css">', '')
        html = html.replace('<script defer src="/static/world.js"></script>', '').replace('<script defer src="/static/app.js"></script>', '')
        await page.set_content(html, wait_until='domcontentloaded')
        css = (ROOT/'app/static/styles.css').read_text()
        art = base64.b64encode((ROOT/'app/static/city-concept.png').read_bytes()).decode()
        css = css.replace("url('/static/city-concept.png')", "url('data:image/png;base64," + art + "')")
        await page.add_style_tag(content=css)
        demo=build_demo()
        await page.evaluate('''window.__GRAPH__=null;
          window.fetch=async (input,opts)=>{
           const path=String(input), g=window.__GRAPH__;
           const session={authenticated:true,guest:true,user:null,csrf:'csrf-fixture',repositories:[{id:'demo',owner:'Orbit',name:'Orbit Commerce',fullName:'Orbit/Orbit Commerce',updatedAt:1}],activeRepo:'demo',aiConfigured:false};
           let response=path==='/api/session'?session:path.startsWith('/api/my-repos/')?{id:'demo',graph:g}:path==='/api/tour'?{mode:'guided',steps:[]}:{};
           return new Response(JSON.stringify(response),{status:200,headers:{'Content-Type':'application/json'}});
          };''')
        await page.evaluate('(graph)=>{window.__GRAPH__=graph}', demo)
        await page.add_script_tag(content=(ROOT/'app/static/world.js').read_text())
        await page.evaluate('''(() => { window.RepoWorldRenderer=class extends window.RepoWorldRenderer{
          constructor(...args){super(...args);window.__TEST_RENDERER=this;}
        }; return true; })()''')
        await page.add_script_tag(content=(ROOT/'app/static/app.js').read_text())
        await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
        await page.wait_for_function('window.__TEST_RENDERER && window.__TEST_RENDERER.nodes.length > 0', timeout=15000)
        await page.wait_for_timeout(400)
        assert await page.locator('#canvasStage').is_visible()
        rect=await page.locator('#worldCanvas').bounding_box()
        x=rect['x']+rect['width']*.28
        y=rect['y']+rect['height']*.47
        coords=await page.evaluate('''({x,y})=>{
          const r=window.__TEST_RENDERER;
          const p=r.screenToWorldOnPlane(x,y,0);
          return {x:p.x,z:p.z,oldDistance:r.distance};
        }''',{'x':x-rect['x'],'y':y-rect['y']})
        await page.screenshot(path=str(OUT/f'zoom-overview-{width}.png'))
        await page.mouse.move(x,y)
        await page.mouse.wheel(0,-20)
        await page.wait_for_timeout(420)
        outcome=await page.evaluate('''(arg)=>{
          const r=window.__TEST_RENDERER;
          const projection=r.project(arg.x,0,arg.z);
          return {x:projection.x,z:projection.y,distance:r.distance,target:r.targetDistance,
                  overview:r.overviewDistance,issues:r.issueHitAreas.length};
        }''',coords)
        dx=abs(outcome['x']-(x-rect['x']))
        dy=abs(outcome['z']-(y-rect['y']))
        assert dx<1.0 and dy<1.0, (width,dx,dy)
        assert outcome['distance']<coords['oldDistance']
        assert outcome['distance']>coords['oldDistance']*.85, 'Small scroll must not zoom too far'
        # Zoom follows the same control model regardless of viewport size.
        await page.mouse.wheel(0,-120)
        await page.wait_for_timeout(250)
        assert await page.evaluate('window.__TEST_RENDERER.distance < window.__TEST_RENDERER.overviewDistance')
        await page.screenshot(path=str(OUT/f'zoom-detail-{width}.png'))
        await page.locator('#worldCanvas').dblclick(position={'x':rect['width']*.45,'y':rect['height']*.42})
        await page.wait_for_timeout(120)
        assert await page.evaluate('Math.abs(window.__TEST_RENDERER.distance-window.__TEST_RENDERER.overviewDistance)<.01')
        assert not await page.evaluate('document.documentElement.scrollWidth > innerWidth')
        assert not errors, errors
        print(f'{width}x{height}: pointer-lock drift=({dx:.3f},{dy:.3f}) px; first step distance={outcome["distance"]:.2f}/{coords["oldDistance"]:.2f}; browser errors={errors}')
        await context.close()
        await browser.close()

async def main():
    OUT.mkdir(exist_ok=True)
    await exercise(1440,900)
    await exercise(390,844)

if __name__=='__main__':asyncio.run(main())
