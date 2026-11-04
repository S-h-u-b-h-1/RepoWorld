"""Offline Chromium visual check for share-link entry points.

This fixture mocks the query-string parser because browser navigation to local
HTTP servers is blocked in some CI environments. Full browser URL routing is
covered separately by Node tests of the real application controller; the HTTP
endpoint retirement is checked with FastAPI ASGI tests. No network calls occur.
"""
from __future__ import annotations

import asyncio
import base64
import json
from pathlib import Path

from playwright.async_api import async_playwright

from app.demo import build_demo

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'evidence'


def offline_assets():
    html = (ROOT / 'app/static/index.html').read_text()
    for tag in ('<link rel="stylesheet" href="/static/styles.css">',
                '<script defer src="/static/world.js"></script>',
                '<script defer src="/static/app.js"></script>'):
        html = html.replace(tag, '')
    css = (ROOT / 'app/static/styles.css').read_text()
    image = base64.b64encode((ROOT / 'app/static/city-concept.png').read_bytes()).decode()
    css = css.replace("url('/static/city-concept.png')", "url('data:image/png;base64," + image + "')")
    return html, css


async def verify(page, session, graph, fake_search):
    errors=[]
    page.on('pageerror', lambda exception: errors.append(str(exception)))
    html,css=offline_assets()
    await page.set_content(html)
    await page.add_style_tag(content=css)
    await page.evaluate('''({session,graph,search})=>{
      window.__FETCH_LOG__=[];
      const Native=window.URLSearchParams;
      window.URLSearchParams=class extends Native {constructor(value){super(value||search)}};
      window.fetch=async(input,opts={})=>{
        const url=String(input);
        window.__FETCH_LOG__.push({url,method:opts.method||'GET'});
        let json=url==='/api/session'?session:
          url==='/api/my-repos/demo'?{id:'demo',graph}:
          url==='/api/my-repos/demo/issues'?{total:0,placed:0,unplaced:0,issues:[],byNode:{},partial:false}:
          url==='/api/tour'?{mode:'guided',steps:[]}:{error:'Unexpected URL'};
        return new Response(JSON.stringify(json),{status:json.error?404:200,headers:{'Content-Type':'application/json'}});
      };
    }''',{'session':session,'graph':graph,'search':fake_search})
    await page.add_script_tag(content=(ROOT / 'app/static/world.js').read_text())
    await page.add_script_tag(content=(ROOT / 'app/static/app.js').read_text())
    await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
    return errors


async def main():
    OUT.mkdir(parents=True,exist_ok=True)
    demo=build_demo()
    demo.update({'name':'demo-city','owner':'testowner','source':'github',
                 'url':'https://github.com/testowner/demo-city','branch':'main'})
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        for width,height in [(1440,900),(390,844)]:
            page=await browser.new_page(viewport={'width':width,'height':height})
            session={'authenticated':True,'guest':True,'csrf':'fixture', 'repositories':[],
                     'activeRepo':None,'aiConfigured':False}
            errors=await verify(page,session,demo,'?repo=openwisp%2Fopenwisp-utils')
            await page.locator('#addRepoDialog').wait_for(state='visible',timeout=10000)
            assert await page.locator('#importInput').input_value()=='openwisp/openwisp-utils'
            calls=await page.evaluate('window.__FETCH_LOG__')
            assert not any(item['method']=='POST' for item in calls),calls
            assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
            assert not errors,errors
            await page.screenshot(path=str(OUT/f'shared-link-invite-{width}.png'))
            print(f'{width}x{height}: share-link import prompt prefilled, no automatic import, no JS errors/overflow')
            await page.close()
        page=await browser.new_page(viewport={'width':1440,'height':900})
        session={'authenticated':True,'guest':True,'csrf':'fixture',
                 'repositories':[{'id':'demo','owner':'testowner','name':'demo-city','fullName':'testowner/demo-city'}],
                 'activeRepo':'demo','aiConfigured':False}
        errors=await verify(page,session,demo,'?repo=testowner%2Fdemo-city')
        await page.locator('#canvasStage').wait_for(state='visible',timeout=10000)
        assert await page.locator('#addRepoDialog').is_hidden()
        await page.locator('#repoMenuButton').click()
        assert await page.locator('#copyCityLink').is_visible()
        assert not errors,errors
        await page.screenshot(path=str(OUT/'shared-link-city-1440.png'))
        print('1440x900: existing city opens from same-repo link; copy-link menu action visible')
        await page.close()
        await browser.close()


if __name__=='__main__':asyncio.run(main())
