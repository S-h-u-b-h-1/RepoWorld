"""Offline visual test fixture for guest landing, empty state, and city."""
import asyncio
from pathlib import Path
import json
import base64
from playwright.async_api import async_playwright
from app.demo import build_demo
from app.intelligence import find_modules,impact_trace
from app.issues import _assemble

BASE=Path(__file__).resolve().parents[2]
HTML=BASE/'app/static/index.html'
OUT=BASE/'evidence'
DEMO=build_demo()
RADAR=_assemble(DEMO,'fictional','demo',[
  {'number':101,'state':'open','title':'Session invalidation fails','body':'services/auth/src/sessions.ts', 'labels':[{'name':'bug'}]},
  {'number':102,'state':'open','title':'Checkout page layout broken','body':'apps/web/src/layout.tsx','labels':[{'name':'help wanted'}]},
  {'number':103,'state':'open','title':'General discussion','body':'Planning next release'},
  {'number':104,'state':'open','title':'Refresh token error in auth','body':'services/auth/src/sessions.ts', 'labels':[{'name':'bug'}]},
  {'number':105,'state':'open','title':'Fix session middleware','body':'services/auth/src/sessions.ts', 'labels':[{'name':'help wanted'}]},
  {'number':106,'state':'open','title':'Audit session cookie settings','body':'services/auth/src/sessions.ts'},
])

async def render(mode, width, height):
    async with async_playwright() as p:
        browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        context=await browser.new_context(viewport={'width':width,'height':height},device_scale_factor=1)
        page=await context.new_page()
        errors=[]
        page.on('pageerror', lambda e: errors.append(str(e)))
        html=HTML.read_text()
        html=html.replace('<link rel="stylesheet" href="/static/styles.css">','')
        html=html.replace('<script defer src="/static/world.js"></script>','').replace('<script defer src="/static/app.js"></script>','')
        await page.set_content(html,wait_until='domcontentloaded')
        css=(BASE/'app/static/styles.css').read_text()
        img=base64.b64encode((BASE/'app/static/city-concept.png').read_bytes()).decode()
        css=css.replace("url('/static/city-concept.png')","url('data:image/png;base64,"+img+"')")
        await page.add_style_tag(content=css)
        session={'authenticated':True,'guest':True,'user':None,
                 'csrf':'fixturecsrf','repositories':[{'id':'demo','owner':'Orbit','name':'Orbit Commerce','fullName':'Orbit/Orbit Commerce','updatedAt':1}] if mode=='city' else [],
                 'activeRepo':'demo' if mode=='city' else None,'aiConfigured':False}
        await page.evaluate('''window.__ISSUE_CALLS=[]; window.fetch=async function(input, options){
          const path=String(input); const data=window.__FIXTURE__;
          let body;
          if(path==='/api/session') body=data.session;
          else if(path.startsWith('/api/my-repos/demo/find')) body=data.find;
          else if(path.startsWith('/api/my-repos/demo/impact')) body=data.impact;
          else if(path.startsWith('/api/my-repos/demo/issues')) body=data.radar;
          else if(path.startsWith('/api/my-repos/demo/assistant')){window.__ISSUE_CALLS.push(JSON.parse(options.body||'{}').issueNumber); body={mode:'ai',answer:'The report describes a session invalidation problem in the authentication service. The visible excerpt defines a session helper, but no test has been executed.',issueSummary:'The report says that session invalidation may reject a rotated token.',codeEvidence:['The fetched source contains `rotateSession` in the auth service. Runtime behavior is not verified.'],steps:['Read the helper and reproduce the reported symptom.','Check direct importers before changing shared behavior.'],tests:['Add a regression test that rotates a token and asserts the expected session state.'],sourceFilesRead:1,nodeIds:['services/auth'],sources:[{file:'services/auth/src/sessions.ts',url:'https://github.com/example/commerce/blob/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa/services/auth/src/sessions.ts#L36-L80',lineStart:36,lineEnd:80,commit:'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',evidence:'excerpt'}],disclosure:'AI guidance with source excerpts; no code executed.'};}
          else if(path.startsWith('/api/my-repos/')) body={id:'demo',graph:data.graph};
          else if(path==='/api/tour') body={mode:'guided',steps:data.graph.nodes.slice(0,5).map((n,i)=>({nodeId:n.id,title:'Stop '+(i+1),description:n.description}))};
          else body={error:'mock unavailable'};
          return new Response(JSON.stringify(body),{status:body.error?404:200,headers:{'Content-Type':'application/json'}});
        };''')
        await page.evaluate(f'window.__FIXTURE__ = {json.dumps({"session":session,"graph":DEMO,"find":find_modules(DEMO,"Where is login handled?"),"impact":impact_trace(DEMO,"services/auth"),"radar":RADAR})};')
        await page.add_script_tag(content=(BASE/'app/static/world.js').read_text())
        await page.evaluate('(() => { window.RepoWorldRenderer=class extends window.RepoWorldRenderer {constructor(...args){super(...args);window.__testRenderer=this;}}; return true; })()')
        await page.add_script_tag(content=(BASE/'app/static/app.js').read_text())
        await page.evaluate('document.dispatchEvent(new Event("DOMContentLoaded"))')
        await page.wait_for_timeout(1600)
        view=await page.locator('#workspace').is_visible()
        city=await page.locator('#canvasStage').is_visible()
        empty=await page.locator('#emptyState').is_visible()
        overflow=await page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
        print(mode,width,height,'workspace',view,'city',city,'empty',empty,'overflow',overflow,'errors',errors)
        await page.screenshot(path=str(OUT/f'{mode}-{width}.png'),full_page=True)
        if mode=='city':
            # Browser-level interaction: click a REAL projected issue marker,
            # not the underlying building nor a mock button in a separate list.
            pin=await page.evaluate("window.__testRenderer.issueHitAreas.find(p => p.nodeId === 'services/auth')")
            assert pin and pin['nodeId'], 'Expected at least one visible issue marker on the city'
            rect=await page.locator('#worldCanvas').bounding_box()
            await page.mouse.click(rect['x']+pin['x'],rect['y']+pin['y'])
            await page.locator('#issueDrawer:not([hidden])').wait_for()
            await page.locator('#issueAiResult p').first.wait_for()
            assert 'ISSUE #' in await page.locator('#issueDetailIndex').inner_text()
            assert await page.locator('#issueDrawerChooser').is_visible()
            assert not await page.locator('#issueOriginalReport').evaluate('(el)=>el.open')
            assert await page.locator('#issueAiResult .insight-section').count()>=3
            assert await page.locator('#issueAiResult .issue-insight-sources a').count()==1
            assert await page.locator('#issueDrawerSelect option').count()==4
            await page.locator('#issueDrawerSelect').select_option('104')
            assert '#104' in await page.locator('#issueDetailIndex').inner_text()
            assert await page.evaluate('window.__ISSUE_CALLS.at(-1)')==104
            # Switching to a different issue retains the exact building context.
            assert await page.locator('#issuePlacement').is_visible()
            assert await page.locator('#issueGithubLink').get_attribute('href')
            await page.screenshot(path=str(OUT/f'issue-investigate-{width}.png'),full_page=True)
            await page.click('#closeIssueDrawer')
            await page.evaluate("window.__testRenderer.onSelect('services/auth')")
            assert await page.locator('#buildingIssues').is_visible()
            assert await page.locator('#buildingIssuesMore').is_visible()
            # The issue list should be near the top, not below offscreen metrics.
            assert await page.evaluate("document.querySelector('#buildingIssues').getBoundingClientRect().top < 600")
            await page.screenshot(path=str(OUT/f'building-issues-{width}.png'),full_page=True)
            await page.locator('#buildingIssuesMore').click()
            assert await page.locator('#issueDrawerSelect option').count()==4
            await page.click('#closeIssueDrawer')
            await page.evaluate("window.__testRenderer.onSelect('services/auth')")
            await page.locator('#buildingIssuesList .building-issue-row').nth(1).click()
            assert '#104' in await page.locator('#issueDetailIndex').inner_text()
            await page.click('#closeIssueDrawer')
            await page.click('#issueMapLegend')
            assert await page.locator('#issuesTab').is_visible()
            await page.locator('#searchDialog').evaluate('(el)=>el.close()')
            await page.click('#mapCommandTrigger')
            assert await page.locator('#searchDialog').is_visible()
            assert await page.locator('#askTab').is_visible()
            await page.locator('#assistantQuestion').fill('How can I improve session invalidation?')
            await page.click('#assistantSend')
            await page.wait_for_selector('.chat-bubble.assistant .assistant-meta')
            await page.screenshot(path=str(OUT/f'assistant-{width}.png'),full_page=True)
            await page.click('button[data-compass-tab="issues"]')
            await page.wait_for_selector('.issue-item')
            await page.screenshot(path=str(OUT/f'issues-{width}.png'),full_page=True)
            await page.click('button[data-compass-tab="find"]')
            await page.locator('#searchInput').fill('Where is login handled?')
            await page.wait_for_selector('.search-result')
            await page.screenshot(path=str(OUT/f'find-{width}.png'),full_page=True)
            await page.locator('.search-result').first.click()
            assert await page.locator('#inspector').is_visible()
            await page.click('#inspectorTrace')
            await page.wait_for_selector('#impactPanel:not([hidden])')
            assert 'POSSIBLY AFFECTED' in await page.locator('#impactCount').inner_text()
            await page.screenshot(path=str(OUT/f'trace-{width}.png'),full_page=True)
            await page.click('#closeInspector')
            await page.click('#mapCommandTrigger')
            await page.click('button[data-compass-tab="find"]')
            await page.click('#showMapOptions')
            await page.click('button[data-layer="dependencies"]')
            assert await page.locator('button[data-layer="dependencies"]').get_attribute('class')=='active'
            await page.click('#tourButton')
            assert await page.locator('#tourPanel').is_visible()
            await page.click('#closeTour')
            await page.click('#repoMenuButton')
            assert await page.locator('#repoMenu').is_visible()
        assert not errors
        assert not overflow
        await context.close();await browser.close()

async def main():
    OUT.mkdir(exist_ok=True)
    html=HTML.read_text().replace('href="/static/styles.css"','href="visual-fixture.css"')\
        .replace('src="/static/world.js"','src="../app/static/world.js"')\
        .replace('src="/static/app.js"','src="../app/static/app.js"')
    (OUT/'visual-fixture.html').write_text(html)
    css=(BASE/'app/static/styles.css').read_text().replace("url('/static/city-concept.png')","url('../app/static/city-concept.png')")
    (OUT/'visual-fixture.css').write_text(css)
    for mode in ['empty','city']:
        await render(mode,1440,900)
    await render('empty',390,844)
    await render('city',390,844)

if __name__=='__main__':asyncio.run(main())
