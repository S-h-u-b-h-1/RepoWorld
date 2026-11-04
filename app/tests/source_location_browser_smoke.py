"""Offline Chromium acceptance: live-source marker in the minimal city.

No provider calls or tokens; use explicit, fictional public-code fixtures.
"""
import asyncio
import base64
import json
from pathlib import Path
from playwright.async_api import async_playwright
from app.demo import build_demo

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'evidence'
DEMO=build_demo()
ISSUE={'number':717,'title':'Add driver debug logging','body':'An improvement to browser logging was requested.',
       'url':'https://github.com/example/demo/issues/717','labels':['enhancement'],
       'matches':[],'commentsCount':0}
RADAR={'total':1,'placed':0,'unplaced':1,'issues':[ISSUE], 'byNode':{},'partial':False,
       'scope':'Fictional QA fixture; issue placement starts unknown.'}
LOCATION={'nodeId':'services/auth','file':'services/auth/src/sessions.ts','symbols':['rotateSession'],
          'evidence':'identifier-observed','url':'https://github.com/example/demo/blob/'+'a'*40+'/services/auth/src/sessions.ts#L22-L50',
          'lineStart':22,'lineEnd':50}
ANSWER={'mode':'ai','issueSummary':'The report requests more debugging information for browser sessions.',
        'answer':'Source text contains an identifier associated with sessions. The reported behavior is not reproduced.',
        'steps':['Inspect the referenced function in the current commit.'],
        'tests':['Run a logging regression test locally.'],'codeEvidence':['Source identifier rotateSession was observed in public source.'],
        'nodeIds':['services/auth'],'sourceFilesRead':1,'sources':[{'file':LOCATION['file'],'url':LOCATION['url'],
           'evidence':'excerpt','lineStart':22,'lineEnd':50}],
        'observedLocations':[LOCATION], 'disclosure':'This does not verify the issue.'}

async def verify(width,height):
    html=(ROOT/'app/static/index.html').read_text()
    for tag in ('<link rel="stylesheet" href="/static/styles.css">',
                '<script defer src="/static/world.js"></script>',
                '<script defer src="/static/app.js"></script>'):
        html=html.replace(tag,'')
    css=(ROOT/'app/static/styles.css').read_text()
    city=base64.b64encode((ROOT/'app/static/city-concept.png').read_bytes()).decode()
    css=css.replace("url('/static/city-concept.png')","url('data:image/png;base64,"+city+"')")
    session={'authenticated':True,'guest':True,'csrf':'fixture-only',
             'repositories':[{'id':'demo','owner':'Orbit','name':'Orbit Commerce','fullName':'Orbit/commerce'}],
             'activeRepo':'demo','aiConfigured':True}
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        page=await browser.new_page(viewport={'width':width,'height':height},device_scale_factor=1)
        errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
        await page.set_content(html)
        await page.add_style_tag(content=css)
        fixture={'session':session,'graph':DEMO,'radar':RADAR,'answer':ANSWER}
        await page.evaluate('''window.__FIXTURE__=%s;
            window.fetch=async(input,opts={})=>{
              const url=String(input),f=window.__FIXTURE__;
              let data=url==='/api/session'?f.session:
                url==='/api/my-repos/demo'?{id:'demo',graph:f.graph}:
                url.includes('/issues')?f.radar:
                url.includes('/assistant')?f.answer:
                url==='/api/tour'?{mode:'guided',steps:[]}:{error:'unexpected test request'};
              return new Response(JSON.stringify(data),{status:data.error?404:200,headers:{'Content-Type':'application/json'}});
            };
        ''' % json.dumps(fixture))
        await page.add_script_tag(content=(ROOT/'app/static/world.js').read_text())
        await page.evaluate('''(()=>{const Original=window.RepoWorldRenderer;
          window.RepoWorldRenderer=class extends Original{
            constructor(...args){super(...args);window.__renderer=this;}
          };})();''')
        await page.add_script_tag(content=(ROOT/'app/static/app.js').read_text())
        await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
        await page.locator('#mapCommandTrigger').wait_for(state='visible')
        await page.locator('#mapCommandTrigger').click()
        await page.locator('[data-compass-tab="issues"]').click()
        await page.locator('.issue-title-button').first.click()
        await page.locator('.observed-source-location').wait_for(state='visible',timeout=10000)
        observed=await page.evaluate('window.__renderer.issueMarkers.get("services/auth")?.observed')
        assert observed==1, observed
        assert 'SOURCE' in (await page.locator('#issueAiResult').inner_text())
        assert not await page.evaluate('document.documentElement.scrollWidth>innerWidth')
        assert not errors,errors
        OUT.mkdir(parents=True,exist_ok=True)
        await page.screenshot(path=str(OUT/f'source-to-city-{width}.png'))
        await page.locator('.observed-source-location').first.click()
        assert await page.locator('#inspector').is_visible()
        assert await page.locator('#issueDrawer').is_hidden()
        assert await page.locator('#inspectorName').inner_text()
        assert not errors,errors
        print(f'{width}x{height}: source-observed pin and source-to-city jump OK, no overflow/errors')
        await browser.close()

async def main():
    await verify(1440,900)
    await verify(390,844)

if __name__=='__main__':asyncio.run(main())
